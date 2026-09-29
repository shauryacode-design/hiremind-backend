from pydantic import BaseModel


class InterviewResult(BaseModel):
    overall_score: int
    technical_knowledge: int
    problem_solving: int
    communication: int
    strengths: list[str]
    improvements: list[str]
    topics_covered: list[str]
    final_feedback: str
    recommendation: str