from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.interview import Interview
from app.models.user import User
from app.utils.security import get_current_user

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get("/")
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get all interviews belonging to the logged-in user
    interviews = (
        db.query(Interview)
        .filter(Interview.user_id == current_user.id)
        .all()
    )

    total_interviews = len(interviews)

    completed_interviews = [
        interview
        for interview in interviews
        if interview.status == "completed"
    ]

    completed_count = len(completed_interviews)

    # Get scores only from completed interviews that have a result
    scores = [
        interview.result.get("overall_score")
        for interview in completed_interviews
        if interview.result
        and interview.result.get("overall_score") is not None
    ]

    average_score = (
        round(sum(scores) / len(scores), 2)
        if scores
        else 0
    )

    best_score = max(scores) if scores else None

    return {
        "message": "Dashboard retrieved successfully.",
        "summary": {
            "total_interviews": total_interviews,
            "completed_interviews": completed_count,
            "average_score": average_score,
            "best_score": best_score
        }
    }