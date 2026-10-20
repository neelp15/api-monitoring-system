
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Monitor(Base):
    __tablename__ = "monitors"

    __table_args__ = (
        CheckConstraint(
            "interval_seconds >= 30",
            name="ck_monitors_interval_minimum",
        ),
        CheckConstraint(
            "timeout_seconds > 0",
            name="ck_monitors_timeout_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    interval_seconds: Mapped[int] = mapped_column(
        Integer, default=60, nullable=False
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, default=10, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
