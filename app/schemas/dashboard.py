from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_interviews: int
    completed_interviews: int
    average_score: float
    best_score: int | None