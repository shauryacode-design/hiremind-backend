from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserUpdate
from app.utils.security import get_current_user

router = APIRouter(
    prefix="/profile",
    tags=["Profile"]
)


@router.get("/")
def get_profile(
    current_user: User = Depends(get_current_user)
):
    return {
        "message": "Profile retrieved successfully.",
        "profile": {
            "id": current_user.id,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "email": current_user.email,
            "created_at": current_user.created_at,
        }
    }


@router.put("/")
def update_profile(
    profile_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    current_user.first_name = profile_data.first_name
    current_user.last_name = profile_data.last_name

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Profile updated successfully.",
        "profile": {
            "id": current_user.id,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "email": current_user.email,
            "created_at": current_user.created_at,
        }
    }