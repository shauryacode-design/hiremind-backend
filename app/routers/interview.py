from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.models.interview import Interview
from app.models.resume import Resume
from app.models.user import User
from app.schemas.interview import InterviewCreate
from app.schemas.interview_response import InterviewAnswer
from app.services.ai.candidate_questions import answer_candidate_question
from app.services.ai.gemini import GeminiServiceError
from app.services.ai.interview_evaluator import generate_final_interview_result
from app.services.ai.interview_planner import create_interview_plan
from app.services.rag.resume_retriever import retrieve_relevant_chunks
from app.utils.security import get_current_user

from app.schemas.candidate_question import CandidateQuestion

router = APIRouter(prefix="/interviews", tags=["Interviews"])


def _answer_turns(conversation: list) -> list:
    return [
        turn for turn in conversation if turn.get("entry_type") != "candidate_question"
    ]


def _find_request_turn(conversation: list, request_id: str) -> dict | None:
    for turn in conversation:
        if turn.get("request_id") == request_id:
            return turn
    return None


def _normalize_question(question: str) -> str:
    return " ".join(
        "".join(
            character.lower() if character.isalnum() else " " for character in question
        ).split()
    )


@router.post("/")
def create_interview(
    interview_data: InterviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = (
        db.query(Resume)
        .filter(
            Resume.id == interview_data.resume_id, Resume.user_id == current_user.id
        )
        .first()
    )

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")

    if not resume.analysis:
        raise HTTPException(status_code=400, detail="Resume has not been analyzed yet.")

    try:
        interview_plan = create_interview_plan(
            target_role=interview_data.target_role, resume_analysis=resume.analysis
        )
    except GeminiServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    interview = Interview(
        user_id=current_user.id,
        resume_id=resume.id,
        target_role=interview_data.target_role,
        mode=interview_data.mode,
        interview_plan=interview_plan.model_dump(),
        status="created",
    )

    db.add(interview)
    db.commit()
    db.refresh(interview)

    return {
        "message": "Interview created successfully.",
        "interview_id": interview.id,
        "target_role": interview.target_role,
        "mode": interview.mode,
        "status": interview.status,
        "interview_plan": interview.interview_plan,
    }


@router.get("/")
def get_interview_history(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    interviews = (
        db.query(Interview)
        .filter(Interview.user_id == current_user.id)
        .order_by(Interview.created_at.desc())
        .all()
    )

    return {
        "message": "Interviews retrieved successfully.",
        "interviews": [
            {
                "interview_id": interview.id,
                "target_role": interview.target_role,
                "mode": interview.mode,
                "status": interview.status,
                "overall_score": (
                    interview.result.get("overall_score") if interview.result else None
                ),
                "duration_minutes": (
                    round(
                        (interview.completed_at - interview.started_at).total_seconds()
                        / 60,
                        2,
                    )
                    if interview.started_at and interview.completed_at
                    else None
                ),
                "created_at": interview.created_at.isoformat(),
            }
            for interview in interviews
        ],
    }


@router.delete("/{interview_id}")
def delete_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.user_id == current_user.id)
        .with_for_update()
        .first()
    )

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    db.delete(interview)
    db.commit()

    return {"message": "Interview deleted successfully.", "interview_id": interview_id}


@router.get("/{interview_id}")
def get_interview_details(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.user_id == current_user.id)
        .with_for_update()
        .first()
    )

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    duration_minutes = None

    if interview.started_at:
        end_time = interview.completed_at or datetime.now(UTC)

        duration_minutes = round(
            (end_time - interview.started_at).total_seconds() / 60, 2
        )
    # Build a clean conversation history for the frontend.
    conversation_history = []

    for turn in interview.conversation or []:
        # Normal interviewer question + candidate answer
        if turn.get("entry_type") != "candidate_question":
            conversation_history.append({
                "type": "interview",
                "question": turn.get("question", ""),
                "answer": turn.get("answer", ""),
                "evaluation": turn.get("evaluation"),
                "question_index": turn.get("question_index"),
                "answered_at": turn.get("answered_at"),
                "elapsed_seconds": turn.get("elapsed_seconds"),
            })

        # Candidate question phase
        else:
            response = turn.get("response") or {}

            conversation_history.append({
                "type": "candidate_question",
                "question": turn.get("question", ""),
                "answer": response.get("answer", ""),
            })
   
    return {
        "interview_id": interview.id,
        "target_role": interview.target_role,
        "mode": interview.mode,
        "status": interview.status,
        "duration_minutes": duration_minutes,
        "created_at": interview.created_at.isoformat(),
        "result": interview.result,
        "conversation": conversation_history,
    }


@router.post("/{interview_id}/start")
def start_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.user_id == current_user.id)
        .with_for_update()
        .first()
    )

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    # If already running, return the current question instead
    # of resetting the interview.
    if interview.status == "in_progress":
        return _build_current_interview_response(interview)

    if interview.status == "candidate_questions":
        raise HTTPException(
            status_code=400,
            detail="Interview is already in the candidate questions phase.",
        )

    if interview.status == "completed":
        raise HTTPException(
            status_code=400, detail="Interview has already been completed."
        )

    if interview.status != "created":
        raise HTTPException(status_code=400, detail="Interview cannot be started.")

    if not interview.interview_plan:
        raise HTTPException(status_code=400, detail="Interview plan not found.")

    questions = interview.interview_plan.get("questions", [])

    if not questions:
        raise HTTPException(status_code=400, detail="No interview questions available.")

    interview.current_question_index = 0
    interview.status = "in_progress"
    interview.conversation = []
    interview.started_at = datetime.now(UTC)
    interview.completed_at = None

    db.commit()
    db.refresh(interview)

    first_question = questions[0]

    return {
        "message": "Interview started successfully.",
        "interview_id": interview.id,
        "status": interview.status,
        "question_number": 1,
        "question": first_question["question"],
        "topic": first_question["topic"],
        "difficulty": first_question["difficulty"],
        "preferred_answer": (
            first_question.get("preferred_answer")
            if interview.mode == "answer_practice"
            else None
        ),
    }


@router.post("/{interview_id}/answer")
def submit_answer(
    interview_id: int,
    answer_data: InterviewAnswer,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    if not answer_data.answer.strip():
        raise HTTPException(status_code=400, detail="Answer cannot be empty.")

    if not answer_data.request_id.strip() or answer_data.question_index < 0:
        raise HTTPException(
            status_code=400,
            detail="A valid answer request ID and question index are required.",
        )

    conversation = interview.conversation or []
    existing_turn = _find_request_turn(conversation, answer_data.request_id)

    if existing_turn:
        stored_response = existing_turn.get("response")
        if stored_response:
            return stored_response
        raise HTTPException(
            status_code=409, detail="This answer request is already being processed."
        )

    if interview.status != "in_progress":
        raise HTTPException(
            status_code=400, detail="Interview is not currently in progress."
        )

    if not interview.started_at:
        raise HTTPException(status_code=400, detail="Interview start time not found.")

    if answer_data.question_index != interview.current_question_index:
        raise HTTPException(
            status_code=409,
            detail="This answer belongs to an older interview question.",
        )

    for turn in conversation:
        if (
            turn.get("processing")
            and turn.get("question_index") == interview.current_question_index
        ):
            raise HTTPException(
                status_code=409,
                detail="Another answer for the current interview question is being processed.",
            )

    elapsed_seconds = (datetime.now(UTC) - interview.started_at).total_seconds()

    elapsed_minutes = elapsed_seconds / 60

    current_question = _get_current_question(interview)
    current_topic = _get_current_topic(interview)

    conversation.append(
        {
            "request_id": answer_data.request_id,
            "processing": True,
            "question": current_question,
            "topic": current_topic,
            "answer": answer_data.answer,
            "answered_at": datetime.now(UTC).isoformat(),
            "elapsed_seconds": round(elapsed_seconds, 2),
            "question_index": interview.current_question_index,
        }
    )

    interview.conversation = conversation
    flag_modified(interview, "conversation")
    db.flush()

    rag_query = f"""
    Target role: {interview.target_role}

    Current interview question:
    {current_question}

    Candidate's answer:
    {answer_data.answer}
    """

    from app.services.ai.interview_engine import generate_next_interview_question

    
    try:
        retrieved_resume_context = retrieve_relevant_chunks(
            db=db, resume_id=interview.resume_id, query=rag_query, limit=3
        )

        result = generate_next_interview_question(
            target_role=interview.target_role,
            mode=interview.mode,
            resume_analysis=_get_resume_analysis(interview, db),
            interview_plan=interview.interview_plan,
            conversation=conversation,
            elapsed_minutes=elapsed_minutes,
            target_duration_minutes=interview.target_duration_minutes,
            retrieved_resume_context=retrieved_resume_context,
        )

       

    except GeminiServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    finalized_interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    

    if not finalized_interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    conversation = finalized_interview.conversation or []
    turn = _find_request_turn(conversation, answer_data.request_id)
    if not turn:
        raise HTTPException(
            status_code=409,
            detail="Interview state changed while this answer was processing.",
        )

    stored_response = turn.get("response")
    if stored_response:
        return stored_response

    if (
        finalized_interview.status != "in_progress"
        or finalized_interview.current_question_index != answer_data.question_index
    ):
        raise HTTPException(
            status_code=409,
            detail="Interview state changed while this answer was processing.",
        )

    turn.pop("processing", None)
    turn["evaluation"] = result.evaluation.model_dump()

    completed_answers = max(
        len(_answer_turns(conversation)), finalized_interview.current_question_index + 1
    )

    turn["next_question"] = {
        "question": result.question,
        "topic": result.topic,
        "difficulty": result.difficulty,
        "action": result.action,
        "preferred_answer": (
            result.preferred_answer
            if finalized_interview.mode == "answer_practice"
            else None
        ),
    }
    if result.action == "wrap_up":
        finalized_interview.status = "candidate_questions"
    else:
        finalized_interview.current_question_index += 1

    result_question = result.question
    result_topic = result.topic
    result_difficulty = result.difficulty

    response = {
        "message": "Answer evaluated successfully.",
        "interview_id": finalized_interview.id,
        "status": finalized_interview.status,
        "elapsed_minutes": round(elapsed_minutes, 2),
        "action": result.action,
        "question": result_question,
        "topic": result_topic,
        "difficulty": result_difficulty,
        "question_number": (
            finalized_interview.current_question_index + 1
            if finalized_interview.status == "in_progress"
            else completed_answers
        ),
        "evaluation": result.evaluation.model_dump(),
    }

    if finalized_interview.mode == "answer_practice":
        response["preferred_answer"] = result.preferred_answer
        response["practice_note"] = (
            "Do not use the exact answer shown. "
            "Use it as guidance and explain the answer "
            "naturally in your own words."
        )

    turn["response"] = response

    # Mark the JSON column as modified because we changed
    # nested objects inside the conversation list.
    finalized_interview.conversation = conversation
    flag_modified(finalized_interview, "conversation")

    

    db.commit()
    db.refresh(finalized_interview)

    return response


def _get_current_question(interview: Interview) -> str:
    conversation = interview.conversation or []

    if conversation:
        last_turn = conversation[-1]

        next_question = last_turn.get("next_question")

        if next_question:
            return next_question["question"]

    questions = interview.interview_plan.get("questions", [])

    index = interview.current_question_index

    if index < len(questions):
        return questions[index]["question"]

    return "Adaptive interview question"


def _get_current_topic(interview: Interview) -> str:
    conversation = interview.conversation or []

    if conversation:
        next_question = conversation[-1].get("next_question")
        if next_question and next_question.get("topic"):
            return next_question["topic"]

    questions = interview.interview_plan.get("questions", [])
    index = interview.current_question_index
    if index < len(questions):
        return questions[index].get("topic", "")

    return ""


def _get_resume_analysis(interview: Interview, db: Session) -> dict:

    resume = db.query(Resume).filter(Resume.id == interview.resume_id).first()

    if not resume or not resume.analysis:
        return {}

    return resume.analysis


def _build_current_interview_response(interview: Interview):
    question = _get_current_question(interview)

    topic = ""
    difficulty = ""

    conversation = interview.conversation or []

    if conversation:
        last_turn = conversation[-1]
        next_question = last_turn.get("next_question")

        if next_question:
            topic = next_question.get("topic", "")
            difficulty = next_question.get("difficulty", "")

    if not topic or not difficulty:
        questions = interview.interview_plan.get("questions", [])

        index = interview.current_question_index

        if index < len(questions):
            topic = questions[index].get("topic", "")
            difficulty = questions[index].get("difficulty", "")

    preferred_answer = None

    if interview.mode == "answer_practice":
        if conversation:
            last_turn = conversation[-1]
            next_question = last_turn.get("next_question")

            if next_question:
                preferred_answer = next_question.get("preferred_answer")

        if preferred_answer is None:
            questions = interview.interview_plan.get("questions", [])
            index = interview.current_question_index

            if index < len(questions):
                preferred_answer = questions[index].get("preferred_answer")

    return {
        "message": "Interview is already in progress.",
        "interview_id": interview.id,
        "status": interview.status,
        "question_number": interview.current_question_index + 1,
        "question": question,
        "topic": topic,
        "difficulty": difficulty,
        "preferred_answer": preferred_answer,
    }


@router.post("/{interview_id}/candidate-question")
def candidate_question(
    interview_id: int,
    question_data: CandidateQuestion,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.user_id == current_user.id)
        .with_for_update()
        .first()
    )

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    if not question_data.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if not question_data.request_id.strip():
        raise HTTPException(
            status_code=400, detail="A valid candidate question request ID is required."
        )

    conversation = interview.conversation or []
    existing_request = _find_request_turn(conversation, question_data.request_id)

    if existing_request:
        stored_response = existing_request.get("response")
        if stored_response:
            return stored_response
        raise HTTPException(
            status_code=409,
            detail="This candidate question request is already being processed.",
        )

    if interview.status != "candidate_questions":
        raise HTTPException(
            status_code=400, detail="Candidate questions are not available yet."
        )

    normalized_question = _normalize_question(question_data.question)
    for turn in conversation:
        if turn.get("entry_type") != "candidate_question":
            continue
        if _normalize_question(
            turn.get("question", "")
        ) == normalized_question and turn.get("response"):
            return turn["response"]
        if _normalize_question(
            turn.get("question", "")
        ) == normalized_question and turn.get("processing"):
            raise HTTPException(
                status_code=409,
                detail="This candidate question is already being processed.",
            )

    resume = db.query(Resume).filter(Resume.id == interview.resume_id).first()

    if not resume or not resume.analysis:
        raise HTTPException(status_code=400, detail="Resume analysis not available.")

    conversation.append(
        {
            "entry_type": "candidate_question",
            "request_id": question_data.request_id,
            "question": question_data.question,
            "processing": True,
        }
    )
    interview.conversation = conversation
    flag_modified(interview, "conversation")
    db.flush()

    try:
        result = answer_candidate_question(
            target_role=interview.target_role,
            resume_analysis=resume.analysis,
            question=question_data.question,
        )
    except GeminiServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    finalized_interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not finalized_interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    turn = _find_request_turn(
        finalized_interview.conversation or [], question_data.request_id
    )
    if not turn:
        raise HTTPException(
            status_code=409,
            detail="Interview state changed while the candidate question was processing.",
        )

    stored_response = turn.get("response")
    if stored_response:
        return stored_response

    turn.pop("processing", None)
    response = {
        "message": "Candidate question answered successfully.",
        "interview_id": finalized_interview.id,
        "answer": result.answer,
    }
    turn["response"] = response
    finalized_interview.conversation = finalized_interview.conversation or []
    flag_modified(finalized_interview, "conversation")
    db.commit()

    return response


@router.post("/{interview_id}/complete")
def complete_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.user_id == current_user.id)
        .with_for_update()
        .first()
    )

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    if interview.status == "completed":
        return {
            "message": "Interview is already completed.",
            "interview_id": interview.id,
            "status": interview.status,
            "duration_minutes": (
                round(
                    (interview.completed_at - interview.started_at).total_seconds()
                    / 60,
                    2,
                )
                if interview.completed_at and interview.started_at
                else 0
            ),
            "result": interview.result,
        }

    if interview.status == "completing":
        raise HTTPException(
            status_code=409, detail="Interview completion is already being processed."
        )

    if interview.status != "candidate_questions":
        raise HTTPException(
            status_code=400, detail="Interview is not ready to be completed."
        )

    if not interview.started_at:
        raise HTTPException(status_code=400, detail="Interview start time not found.")

    elapsed_seconds = (datetime.now(UTC) - interview.started_at).total_seconds()

    elapsed_minutes = elapsed_seconds / 60

    conversation = _answer_turns(interview.conversation or [])

    interview.status = "completing"
    db.commit()

    try:
        result = generate_final_interview_result(
            target_role=interview.target_role,
            resume_analysis=_get_resume_analysis(interview, db),
            interview_plan=interview.interview_plan,
            conversation=conversation,
            elapsed_minutes=elapsed_minutes,
        )
    except GeminiServiceError as exc:
        cleanup_interview = (
            db.query(Interview)
            .filter(Interview.id == interview_id)
            .with_for_update()
            .first()
        )
        if cleanup_interview and cleanup_interview.status == "completing":
            cleanup_interview.status = "candidate_questions"
            db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        cleanup_interview = (
            db.query(Interview)
            .filter(Interview.id == interview_id)
            .with_for_update()
            .first()
        )
        if cleanup_interview and cleanup_interview.status == "completing":
            cleanup_interview.status = "candidate_questions"
            db.commit()
        raise

    # Save the final AI-generated result in PostgreSQL
    finalized_interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not finalized_interview or finalized_interview.status != "completing":
        raise HTTPException(
            status_code=409,
            detail="Interview completion state changed while the report was generated.",
        )

    finalized_interview.result = result.model_dump()
    finalized_interview.status = "completed"
    finalized_interview.completed_at = datetime.now(UTC)

    db.commit()
    db.refresh(finalized_interview)

    return {
        "message": "Interview completed successfully.",
        "interview_id": finalized_interview.id,
        "status": finalized_interview.status,
        "duration_minutes": round(elapsed_minutes, 2),
        "result": result.model_dump(),
    }
