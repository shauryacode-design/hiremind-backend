from pydantic import BaseModel


class CandidateQuestion(BaseModel):
    question: str
    request_id: str