
import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CheckResult, Incident, Monitor
from app.services.alerts import send_incident_email
from app.services.url_safety import validate_public_url

logger = logging.getLogger(__name__)


def _send_email_safely(subject: str, body: str) -> None:
    """Send an email without allowing email failures to undo database changes."""
    try:
        sent = asyncio.run(send_incident_email(subject, body))
        if not sent:
            logger.warning("Alert email was not delivered: %s", subject)
    except Exception:
        logger.exception("Unexpected error while sending alert email.")


def check_monitor(db: Session, monitor: Monitor) -> CheckResult:
    status_code = None
    error_message = None
    result_status = "down"

    start = time.perf_counter()

    try:
        validate_public_url(monitor.url)

        with httpx.Client(
            timeout=monitor.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = client.get(monitor.url)

        status_code = response.status_code

        if 200 <= status_code < 400:
            result_status = "up"
        else:
            error_message = f"HTTP status {status_code}"

    except ValueError as exc:
        error_message = str(exc)

    except httpx.TimeoutException:
        result_status = "timeout"
        error_message = "Request timed out."

    except httpx.HTTPError as exc:
        error_message = f"HTTP request failed: {type(exc).__name__}"

    except Exception:
        logger.exception(
            "Unexpected error while checking monitor %s",
            monitor.id,
        )
        error_message = "Unexpected error during HTTP check."

    response_time_ms = round((time.perf_counter() - start) * 1000)

    result = CheckResult(
        monitor_id=monitor.id,
        status_code=status_code,
        response_time_ms=response_time_ms,
        status=result_status,
        error_message=error_message,
    )

    new_incident = None
    resolved_incident = None

    try:
        db.add(result)

        open_incident = db.scalars(
            select(Incident)
            .where(
                Incident.monitor_id == monitor.id,
                Incident.status == "open",
            )
            .order_by(Incident.id.desc())
            .limit(1)
        ).first()

        if result_status == "up":
            if open_incident is not None:
                open_incident.status = "resolved"
                open_incident.resolved_at = datetime.now(timezone.utc)
                resolved_incident = open_incident

        elif open_incident is None:
            new_incident = Incident(
                monitor_id=monitor.id,
                status="open",
                description=(
                    f"Monitor is {result_status}. "
                    f"{error_message or 'The API returned an unsuccessful response.'}"
                ),
            )
            db.add(new_incident)

        # Save the check and incident changes before attempting email delivery.
        db.commit()
        db.refresh(result)

        if new_incident is not None:
            db.refresh(new_incident)

        if resolved_incident is not None:
            db.refresh(resolved_incident)

    except Exception:
        db.rollback()
        logger.exception(
            "Failed to save check or incident for monitor %s",
            monitor.id,
        )
        raise

    # Send notifications only after the database transaction succeeds.
    if new_incident is not None:
        logger.warning("New incident detected for monitor %s", monitor.id)

        _send_email_safely(
            subject=f"[API Monitor] API DOWN: {monitor.name}",
            body=(
                "A monitored API has become unavailable.\n\n"
                f"Monitor: {monitor.name}\n"
                f"URL: {monitor.url}\n"
                f"Status: {result_status}\n"
                f"HTTP status code: {status_code}\n"
                f"Error: {error_message or 'No additional details'}\n"
                f"Incident ID: {new_incident.id}\n"
                f"Detected at (UTC): "
                f"{datetime.now(timezone.utc).isoformat()}\n"
            ),
        )

    if resolved_incident is not None:
        logger.info("Incident %s resolved for monitor %s",
                    resolved_incident.id, monitor.id)

        _send_email_safely(
            subject=f"[API Monitor] API RECOVERED: {monitor.name}",
            body=(
                "A previously unavailable API has recovered.\n\n"
                f"Monitor: {monitor.name}\n"
                f"URL: {monitor.url}\n"
                f"Current status: UP\n"
                f"Incident ID: {resolved_incident.id}\n"
                f"Resolved at (UTC): "
                f"{resolved_incident.resolved_at.isoformat()}\n"
            ),
        )

    return result
