import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import CheckResult, Monitor
from app.services.checker import check_monitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5


def monitor_is_due(
    db: Session,
    monitor: Monitor,
    now: datetime,
) -> bool:
    """Return True when a monitor is due for another check."""
    statement = (
        select(CheckResult)
        .where(CheckResult.monitor_id == monitor.id)
        .order_by(CheckResult.checked_at.desc(), CheckResult.id.desc())
        .limit(1)
    )

    latest_result = db.scalars(statement).first()

    if latest_result is None:
        return True

    last_checked = latest_result.checked_at

    # PostgreSQL stores timezone-aware timestamps.
    if last_checked.tzinfo is None:
        last_checked = last_checked.replace(tzinfo=timezone.utc)

    next_check_time = last_checked + timedelta(
        seconds=monitor.interval_seconds
    )

    return now >= next_check_time


def run_worker() -> None:
    """Continuously check active monitors when they are due."""
    logger.info("API monitoring worker started.")

    while True:
        db = SessionLocal()

        try:
            monitors = list(
                db.scalars(
                    select(Monitor).where(Monitor.is_active.is_(True))
                ).all()
            )

            for monitor in monitors:
                try:
                    # Refresh the schedule after earlier checks finish.
                    now = datetime.now(timezone.utc)

                    if not monitor_is_due(db, monitor, now):
                        continue

                    logger.info(
                        "Checking monitor %s: %s",
                        monitor.id,
                        monitor.name,
                    )

                    result = check_monitor(db, monitor)

                    logger.info(
                        "Monitor %s result: %s (HTTP %s, %s ms)",
                        monitor.id,
                        result.status,
                        result.status_code,
                        result.response_time_ms,
                    )

                except Exception:
                    db.rollback()
                    logger.exception(
                        "Failed to process monitor %s",
                        monitor.id,
                    )

        except Exception:
            db.rollback()
            logger.exception("Worker encountered a database error.")

        finally:
            db.close()

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_worker()