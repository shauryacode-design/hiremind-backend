from app.schemas.interview_result import InterviewResult
from app.services.ai.ai_provider import generate_structured

def generate_final_interview_result(
    target_role: str,
    resume_analysis: dict,
    interview_plan: dict,
    conversation: list,
    elapsed_minutes: float
) -> InterviewResult:

    prompt = f"""
You are HireMind, a professional AI interview evaluator.

The candidate has completed their interview.

Target role:
{target_role}

Candidate resume analysis:
{resume_analysis}

Original interview plan:
{interview_plan}

Complete interview conversation:

IMPORTANT:
The conversation is stored as a list of interview turns.

Each turn represents ONE completed candidate answer and contains:
- question: the question asked by HireMind
- answer: the candidate's answer
- evaluation: HireMind's evaluation of that answer
- next_question: the question generated after that answer

Therefore:
- Count each turn as one completed candidate answer.
- Evaluate ALL turns in the conversation.
- Do not assume that only the final turn represents the interview.
- Do not describe the interview as having only one completed question unless
  the conversation list actually contains exactly one turn.

Conversation:
{conversation}

Total interview duration:
{elapsed_minutes:.1f} minutes

Evaluate the candidate's overall interview performance.

IMPORTANT:

1. Evaluate the candidate based ONLY on the interview conversation,
   resume analysis, target role, and interview context.

2. Do not invent skills, experience, projects, or achievements.

3. Individual answer scores stored in the conversation are useful
   evidence, but do not simply calculate the final score by taking
   their average.

4. Evaluate the candidate across these areas:
   - technical knowledge
   - problem solving
   - communication

5. Consider:
   - correctness of answers
   - technical depth
   - ability to explain reasoning
   - ability to handle follow-up questions
   - practical understanding
   - consistency
   - clarity of communication
   - weaknesses demonstrated during the interview

6. Do not penalize the candidate simply because they did not know
   an advanced concept unless that concept was reasonably relevant
   to the target role.

7. The interview duration should provide context, but do not
   automatically penalize a candidate simply for taking longer.

8. If the candidate took unusually long to answer questions,
   consider whether this affected interview performance, but do
   not make timing the primary evaluation factor.

9. Identify the most important strengths demonstrated during the
   interview.

10. Identify the most important areas the candidate should improve.

11. List the major topics that were actually discussed.

12. Give concise but useful final feedback.

13. Give a professional recommendation based on the candidate's
    demonstrated performance for the target role.

The result should be honest and balanced.

Return only the structured response requested by the schema.
"""

    return generate_structured(
        prompt,
        InterviewResult
    )