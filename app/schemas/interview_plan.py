from pydantic import BaseModel


class InterviewQuestion(BaseModel):

    question: str
    topic: str
    difficulty: str
    preferred_answer: str

class InterviewPlan(BaseModel):
    interview_strategy: str
    questions: list[InterviewQuestion]