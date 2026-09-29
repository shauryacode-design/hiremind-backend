from typing import Literal

from pydantic import BaseModel


class InterviewAnswer(BaseModel):
    answer: str
    request_id: str
    question_index: int


class InterviewEvaluation(BaseModel):
    score: int
    strengths: list[str]
    improvements: list[str]


class NextInterviewQuestion(BaseModel):

    action: Literal[
        "follow_up",
        "new_topic",
        "wrap_up"
    ]

    question: str

    topic: str

    difficulty: str

    preferred_answer: str | None = None

    evaluation: InterviewEvaluation