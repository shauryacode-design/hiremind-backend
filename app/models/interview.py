from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id"),
        nullable=False
    )

    target_role: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    mode: Mapped[str] = mapped_column(
        String(30),
        default="mock",
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="created",
        nullable=False
    )

    interview_plan: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    current_question_index: Mapped[int] = mapped_column(
        default=0,
        nullable=False
    )

    conversation: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True
    )

    result: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    target_duration_minutes: Mapped[int] = mapped_column(
        default=30,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        nullable=False
    )