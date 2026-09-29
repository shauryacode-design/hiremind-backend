from typing import Literal

from pydantic import BaseModel


class InterviewCreate(BaseModel):

    resume_id: int

    target_role: str

    mode: Literal["mock", "answer_practice"] = "mock"