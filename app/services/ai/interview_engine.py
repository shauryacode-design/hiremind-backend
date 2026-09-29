from difflib import SequenceMatcher
import json

from app.schemas.interview_response import NextInterviewQuestion
from app.services.ai.ai_provider import generate_structured

QUESTION_STOP_WORDS = {
   "a", "about", "and", "are", "can", "do", "how", "in", "of",
   "the", "to", "typically", "when", "you"
}
MAX_RECENT_TURNS = 8
MAX_PREVIOUS_QUESTIONS = 12
MAX_FOLLOW_UPS = 3


def _truncate_context(value: str, limit: int) -> str:
   if len(value) <= limit:
      return value

   marker = " ...[truncated]... "
   remaining = limit - len(marker)
   prefix_length = remaining // 2
   return value[:prefix_length] + marker + value[-(remaining - prefix_length):]


def _compact_resume_analysis(resume_analysis: dict) -> dict:
   relevant_fields = (
      "professional_profile",
      "technical_skills",
      "education",
      "work_experience",
      "projects",
      "strengths",
      "suitable_job_roles",
      "interview_focus_areas",
   )
   compact = {}

   for field in relevant_fields:
      value = resume_analysis.get(field)
      if isinstance(value, str):
         compact[field] = _truncate_context(value, 700)
      elif isinstance(value, list):
         compact[field] = [
            _truncate_context(str(item), 180)
            for item in value[:10]
         ]

   return compact


def _compact_interview_plan(interview_plan: dict) -> dict:
   questions = [
      {
         "topic": _truncate_context(str(question.get("topic", "")), 120),
         "question": _truncate_context(str(question.get("question", "")), 220),
         "difficulty": str(question.get("difficulty", "")),
      }
      for question in interview_plan.get("questions", [])[:8]
   ]
   return {
      "interview_strategy": _truncate_context(
         str(interview_plan.get("interview_strategy", "")),
         700
      ),
      "questions": questions,
   }


def _compact_conversation(conversation: list) -> dict:
   answer_turns = [
      turn for turn in conversation
      if turn.get("entry_type") != "candidate_question"
   ]
   earlier_turns = answer_turns[:-MAX_RECENT_TURNS]
   recent_turns = answer_turns[-MAX_RECENT_TURNS:]

   earlier_questions = [
      _truncate_context(str(turn.get("question", "")), 120)
      for turn in earlier_turns[-MAX_PREVIOUS_QUESTIONS:]
   ]
   compact_turns = []
   covered_topics = []
   follow_ups_by_topic = {}
   follow_ups_used = sum(
      1
      for turn in answer_turns
      if (turn.get("next_question") or {}).get("action") == "follow_up"
   )
   for turn in answer_turns:
      topic = turn.get("topic") or (turn.get("next_question") or {}).get("topic")
      if topic and topic not in covered_topics:
         covered_topics.append(topic)
      next_question = turn.get("next_question") or {}
      if (
         next_question.get("topic")
         and next_question.get("action") == "follow_up"
      ):
         follow_up_topic = next_question["topic"]
         follow_ups_by_topic[follow_up_topic] = (
            follow_ups_by_topic.get(follow_up_topic, 0) + 1
         )

   for index, turn in enumerate(recent_turns):
      answer_limit = 3200 if index == len(recent_turns) - 1 else 350
      topic = turn.get("topic") or (turn.get("next_question") or {}).get("topic")
      compact_turns.append({
         "question": _truncate_context(str(turn.get("question", "")), 240),
         "answer": _truncate_context(str(turn.get("answer", "")), answer_limit),
         "topic": topic,
         "next_topic": (turn.get("next_question") or {}).get("topic"),
      })

   return {
      "earlier_questions": earlier_questions,
      "recent_question_answers": compact_turns,
      "covered_topics": covered_topics,
      "follow_ups_used": follow_ups_used,
      "follow_ups_by_topic": follow_ups_by_topic,
   }


def _normalize_question(question: str) -> str:
   return " ".join(
      "".join(
         character.lower() if character.isalnum() else " "
         for character in question
      ).split()
   )


def _equivalent_question(first: str, second: str) -> bool:
   first_normalized = _normalize_question(first)
   second_normalized = _normalize_question(second)

   if not first_normalized or not second_normalized:
      return False

   if first_normalized == second_normalized:
      return True

   first_terms = {
      term for term in first_normalized.split()
      if term not in QUESTION_STOP_WORDS
   }
   second_terms = {
      term for term in second_normalized.split()
      if term not in QUESTION_STOP_WORDS
   }
   shared_terms = first_terms & second_terms
   if (
      len(shared_terms) >= 3
      and len(shared_terms) / min(len(first_terms), len(second_terms)) >= 0.8
   ):
      return True

   return SequenceMatcher(
      None,
      first_normalized,
      second_normalized
   ).ratio() >= 0.92


def _previous_questions(conversation: list) -> list[str]:
   questions = []
   for turn in conversation:
      if turn.get("question"):
         questions.append(_truncate_context(turn["question"], 180))
      next_question = turn.get("next_question")
      if next_question and next_question.get("question"):
         questions.append(_truncate_context(next_question["question"], 180))
   return questions[-MAX_PREVIOUS_QUESTIONS:]

def generate_next_interview_question(
    target_role: str,
    mode: str,
    resume_analysis: dict,
    interview_plan: dict,
    conversation: list,
    elapsed_minutes: float,
    target_duration_minutes: int,
    retrieved_resume_context: list[str] | None = None,
) -> NextInterviewQuestion:
   resume_context = json.dumps(
      _compact_resume_analysis(resume_analysis),
      ensure_ascii=True,
      separators=(",", ":"),
   )
   plan_context = json.dumps(
      _compact_interview_plan(interview_plan),
      ensure_ascii=True,
      separators=(",", ":"),
   )
   conversation_context = json.dumps(
      _compact_conversation(conversation),
      ensure_ascii=True,
      separators=(",", ":"),
   )
   resume_evidence = [
      _truncate_context(str(chunk), 500)
      for chunk in (retrieved_resume_context or [])[:3]
   ]

   prompt = f"""
   You are HireMind, conducting a professional real-world job interview.

   Target role:
   {target_role}

   Interview mode:
   {mode}

   Candidate resume analysis:
   {resume_context}

   Retrieved resume evidence:
   {resume_evidence}

   Original interview plan:
   {plan_context}

   Previous conversation:
   {conversation_context}

   Current elapsed interview time:
   {elapsed_minutes:.1f} minutes

   Target interview duration:
   approximately {target_duration_minutes} minutes

   Your job is to evaluate the candidate's latest answer and decide
   what the interviewer should ask next.

   IMPORTANT INTERVIEW BEHAVIOR:

   1. This must feel like a real professional interview, not a quiz.

   2. NEVER simply follow the original question list in order.

   3. Use the candidate's latest answer to decide whether a meaningful
      follow-up question is appropriate.

   4. Ask a follow-up only when the latest answer contains an important
      detail, gap, or claim that genuinely needs clarification.

   5. Track how deeply the current topic has been explored.

   6. A topic should normally receive only a small number of
      meaningful follow-up questions before moving to another topic.

   7. If the candidate's latest answer provides enough information
      about the current topic, move naturally to another relevant
      topic.

   8. Do not repeatedly ask about the same topic simply because
      another follow-up question is technically possible.

   9. If the candidate gives short, hesitant, vague, or repetitive
      answers on the same topic, prefer moving to another topic
      rather than stretching the conversation.

   10. When moving to a new topic, select it based on:
      - target role
      - resume
      - candidate's demonstrated skills
      - topics not yet sufficiently explored
      - interview plan

   11. Never announce that you are "changing topics" because of the
      interview algorithm. Make the transition conversational and
      natural.

   12. Do not keep asking follow-up questions on the same topic if the
      conversation is becoming repetitive or stretched.

   13. Ask exactly ONE question at a time.

   14. Never combine two independent questions using "and",
   "also", "as well as", or similar wording.

   15. A follow-up should focus on ONE specific aspect of the
   candidate's previous answer.

   16. If multiple areas need to be explored, choose the most
   important one now and save the other area for a later question.

   17. Do not invent candidate experience, projects, technologies,
      responsibilities, or achievements.

   18. Questions must be based on the candidate's actual resume,
      target role, previous answers, and interview context.

   18a. When retrieved resume evidence is provided, use it as
   supporting evidence for the current question.

   18b. Do not assume information that is not present in either
   the resume analysis or retrieved resume evidence.

   18c. Retrieved evidence is more specific context for the current
   topic, but it does not override the actual candidate's answers.

   19. Do not treat every omitted part of a previous question as
   a mandatory follow-up.

   Use interviewer judgment.
    INTERVIEW COVERAGE AND PACING:

      - The target duration is approximately {target_duration_minutes} minutes.
      - Do not end the core interview merely because the planned topics have
         each received one question. Treat the target duration as a real pacing
         goal, not just a maximum. Unless the candidate explicitly asks to stop,
         do not choose "wrap_up" before 80% of the target duration when a
         relevant planned topic or useful, unanswered interview dimension remains.
      - Near the target duration, wrap up naturally once the most important
         areas have been assessed. Do not force the interview to last exactly
         30 minutes with filler or repetitive questions.
    - Cover no more than 6 distinct role/resume evaluation topics, in
       addition to a brief opening introduction. Prefer 5-6 important
       topics over exhaustive coverage of the entire resume.
    - Use the original plan as a pool of questions, not a required
       checklist. Track which topics have already been covered from the
       conversation and prioritize important uncovered topics.
      - Across the entire interview, ask no more than {MAX_FOLLOW_UPS}
         follow-up questions total. Normally ask at most one follow-up on a
         topic; use another only if essential and still within the total limit.
         Do not repeatedly revisit a topic or ask follow-ups just to fill time.
      - Ask distinct primary questions across the selected topics. Make each
         question open-ended enough to invite the candidate to explain their
         approach, reasoning, and outcome without combining multiple questions.
    - Do not stop based on a fixed number of answers. Candidate answer
       length and elapsed time should guide pacing instead.
    - Before about 20 minutes, explore answers normally while keeping
       the topic and follow-up limits.
    - From about 20 minutes onward, skip optional follow-ups and move
       efficiently through the highest-priority uncovered topics.
    - From about 25 minutes onward, ask concise questions only for the
       most important uncovered topics; avoid deep dives and low-priority
       areas so the core interview can finish near 30 minutes.
   - At or beyond the target duration, use "wrap_up" if the core topics
       are covered. If one critical topic is still missing, ask one concise
       final question about it, then wrap up after its answer. Do not start
       additional discussion threads or exceed the 6-topic maximum.
    - If the candidate gives a short, vague, hesitant, or repetitive
       answer, move on rather than stretching the conversation.
    - Do not turn the interview into a checklist of every detail in the
       plan. The action "wrap_up" moves to the final candidate-questions
       phase when the core interview is complete.

   ANSWER EVALUATION:

   Evaluate the candidate's latest answer.

   Give a score from 0 to 100 for that individual answer.

   Identify concise strengths and improvements.

   Do not reveal this evaluation as an interruption during the
   interview. It will be stored for the final results.

   MODE RULES:

   If mode is "mock":

   - Do NOT provide a preferred answer.
   - The candidate should answer completely on their own.

   If mode is "answer_practice":

   - Provide a strong preferred answer for the NEW question.
   - The answer must be based only on information actually supported
   by the candidate's resume and interview context.
   - Do not invent experience.
   - The preferred answer should demonstrate a strong professional
   way of answering the question.
   - It should NOT be overly long.
   - The candidate should be able to explain it naturally in their
   own words.
   - Never tell the candidate to memorize it.

   The preferred answer is guidance, not a script.

   For answer_practice mode, the preferred answer must NOT be an
   exact answer the candidate is required to repeat.

   IMPORTANT:

   If action is "wrap_up", the question should be a natural
   transition toward ending the core interview. Do not abruptly say
   that time has expired.

   Return only the structured response requested by the schema.
   """

   result = generate_structured(
        prompt,
        NextInterviewQuestion
   )

   previous_questions = _previous_questions(conversation)
   minimum_wrap_up_minutes = target_duration_minutes * 0.8

   if (
      result.action == "wrap_up"
      and elapsed_minutes < minimum_wrap_up_minutes
   ):
      history = _compact_conversation(conversation)
      covered_topics = set(history["covered_topics"])
      follow_ups_by_topic = history["follow_ups_by_topic"]

      for next_planned_question in interview_plan.get("questions", []):
         if any(
            _equivalent_question(
               next_planned_question["question"],
               previous_question
            )
            for previous_question in previous_questions
         ):
            continue

         topic = next_planned_question.get("topic", "")
         is_existing_topic = topic in covered_topics
         if is_existing_topic:
            if (
               history["follow_ups_used"] >= MAX_FOLLOW_UPS
               or follow_ups_by_topic.get(topic, 0) >= 1
            ):
               continue
            result.action = "follow_up"
         else:
            if len(covered_topics) >= 6:
               continue
            result.action = "new_topic"

         result.question = next_planned_question["question"]
         result.topic = topic
         result.difficulty = next_planned_question["difficulty"]
         result.preferred_answer = next_planned_question.get("preferred_answer")
         break

   if any(
      _equivalent_question(result.question, previous_question)
      for previous_question in previous_questions
   ):
      retry_prompt = f"""
      {prompt}

      The generated question was a duplicate. Generate a genuinely different
      question. It may remain on the same topic only if it tests a different
      concrete aspect. Do not use any of these previous questions:
      {previous_questions}
      """
      result = generate_structured(
         retry_prompt,
         NextInterviewQuestion
      )

   if any(
      _equivalent_question(result.question, previous_question)
      for previous_question in previous_questions
   ):
      plan_questions = interview_plan.get("questions", [])
      fallback_question = next(
         (
            question for question in plan_questions
            if not any(
               _equivalent_question(
                  question["question"],
                  previous_question
               )
               for previous_question in previous_questions
            )
         ),
         None
      )
      if fallback_question:
         result.question = fallback_question["question"]
         result.topic = fallback_question["topic"]
         result.difficulty = fallback_question["difficulty"]

   return result