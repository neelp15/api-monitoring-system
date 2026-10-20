from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Incident, Monitor

router = APIRouter(
    prefix="/api/v1/incidents",
    tags=["Incidents"],
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
def list_incidents(
    status_filter: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[dict]:
    """List incidents, optionally filtered by status."""
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=422,
            detail="Limit must be between 1 and 100",
        )

    if status_filter is not None and status_filter not in {
        "open",
        "resolved",
    }:
        raise HTTPException(
            status_code=422,
            detail="Status must be 'open' or 'resolved'",
        )

    statement = select(Incident).order_by(Incident.id.desc())

    if status_filter is not None:
        statement = statement.where(
            Incident.status == status_filter
        )

    incidents = list(
        db.scalars(statement.limit(limit)).all()
    )

    return [
        {
            "id": incident.id,
            "monitor_id": incident.monitor_id,
            "monitor_name": db.get(
                Monitor, incident.monitor_id
            ).name,
            "status": incident.status,
            "started_at": incident.started_at,
            "resolved_at": incident.resolved_at,
            "description": incident.description,
        }
        for incident in incidents
    ]


@router.get("/{incident_id}")
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Retrieve one incident by ID."""
    incident = db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found",
        )

    monitor = db.get(Monitor, incident.monitor_id)

    return {
        "id": incident.id,
        "monitor_id": incident.monitor_id,
        "monitor_name": monitor.name if monitor else None,
        "status": incident.status,
        "started_at": incident.started_at,
        "resolved_at": incident.resolved_at,
        "description": incident.description,
    }
