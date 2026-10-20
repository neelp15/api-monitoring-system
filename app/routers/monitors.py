
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import CheckResult, Monitor
from app.schemas.check_result import CheckResultResponse
from app.schemas.monitor import (
    MonitorCreate,
    MonitorResponse,
    MonitorUpdate,
)
from app.services.checker import check_monitor


router = APIRouter(
    prefix="/api/v1/monitors",
    tags=["Monitors"],
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for one request."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "",
    response_model=MonitorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_monitor(
    payload: MonitorCreate,
    db: Session = Depends(get_db),
) -> Monitor:
    """Create a new API monitor."""
    monitor = Monitor(
        name=payload.name,
        url=str(payload.url),
        interval_seconds=payload.interval_seconds,
        timeout_seconds=payload.timeout_seconds,
    )

    db.add(monitor)
    db.commit()
    db.refresh(monitor)

    return monitor


@router.get(
    "",
    response_model=list[MonitorResponse],
)
def list_monitors(
    db: Session = Depends(get_db),
) -> list[Monitor]:
    """Return all monitors, newest first."""
    statement = select(Monitor).order_by(Monitor.id.desc())

    return list(db.scalars(statement).all())


@router.get(
    "/{monitor_id}/checks",
    response_model=list[CheckResultResponse],
)
def get_monitor_checks(
    monitor_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[CheckResult]:
    """Return recent check results for a monitor."""
    monitor = db.get(Monitor, monitor_id)

    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Limit must be between 1 and 100",
        )

    statement = (
        select(CheckResult)
        .where(CheckResult.monitor_id == monitor_id)
        .order_by(CheckResult.checked_at.desc())
        .limit(limit)
    )

    return list(db.scalars(statement).all())


@router.get(
    "/{monitor_id}",
    response_model=MonitorResponse,
)
def get_monitor(
    monitor_id: int,
    db: Session = Depends(get_db),
) -> Monitor:
    """Return a monitor by its ID."""
    monitor = db.get(Monitor, monitor_id)

    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found",
        )

    return monitor


@router.patch(
    "/{monitor_id}",
    response_model=MonitorResponse,
)
def update_monitor(
    monitor_id: int,
    payload: MonitorUpdate,
    db: Session = Depends(get_db),
) -> Monitor:
    """Update the supplied monitor fields."""
    monitor = db.get(Monitor, monitor_id)

    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found",
        )

    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"'{field}' cannot be null",
            )

        if field == "url":
            value = str(value)

        setattr(monitor, field, value)

    db.commit()
    db.refresh(monitor)

    return monitor


@router.delete(
    "/{monitor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_monitor(
    monitor_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a monitor by its ID."""
    monitor = db.get(Monitor, monitor_id)

    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found",
        )

    db.delete(monitor)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{monitor_id}/check",
    response_model=CheckResultResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_monitor_check(
    monitor_id: int,
    db: Session = Depends(get_db),
) -> CheckResult:
    """Run one HTTP availability check and store its result."""
    monitor = db.get(Monitor, monitor_id)

    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found",
        )

    if not monitor.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Monitor is inactive",
        )

    return check_monitor(db, monitor)
