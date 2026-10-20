from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import CheckResult, Monitor
from app.schemas.check_result import CheckResultResponse

router = APIRouter(
    prefix="/api/v1/monitors",
    tags=["Check History"],
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for one request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get(
    "/{monitor_id}/checks",
    response_model=list[CheckResultResponse],
)
def list_monitor_checks(
    monitor_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[CheckResult]:
    """Return recent health-check results for a monitor."""
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=422,
            detail="Limit must be between 1 and 100",
        )

    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(
            status_code=404,
            detail="Monitor not found",
        )

    statement = (
        select(CheckResult)
        .where(CheckResult.monitor_id == monitor_id)
        .order_by(CheckResult.checked_at.desc(), CheckResult.id.desc())
        .limit(limit)
    )

    return list(db.scalars(statement).all())
