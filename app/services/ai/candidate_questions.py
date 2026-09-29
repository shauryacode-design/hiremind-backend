from app.services.ai.ai_provider import generate_structured
from pydantic import BaseModel


class CandidateQuestionResponse(BaseModel):
    answer: str


def answer_candidate_question(
    target_role: str,
    resume_analysis: dict,
    question: str
) -> CandidateQuestionResponse:

    prompt = f"""
You are HireMind, a professional AI interviewer.

The core technical interview has ended.

Target role:
{target_role}

Candidate resume analysis:
{resume_analysis}

The candidate has asked the following question:

{question}

Answer the candidate professionally and naturally.

Rules:
- Answer the actual question directly.
- Keep the response concise but useful.
- Do not invent company-specific information.
- Do not claim knowledge that is unavailable.
- If the question is about the interview, explain professionally.
- If the question is about the role, give general professional
  guidance unless the resume provides relevant context.
- Do not restart the interview.
- Do not ask another interview question.
"""

    return generate_structured(
        prompt,
        CandidateQuestionResponse
    )