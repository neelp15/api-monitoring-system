import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_incident_email(
    subject: str,
    body: str,
) -> bool:
    """Send an incident notification email using SMTP."""
    required_settings = (
        settings.smtp_username,
        settings.smtp_password,
        settings.alert_from_email,
        settings.alert_to_email,
    )

    if not all(required_settings):
        logger.warning(
            "Email alert skipped: SMTP settings are incomplete."
        )
        return False

    message = EmailMessage()
    message["From"] = settings.alert_from_email
    message["To"] = settings.alert_to_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=(settings.smtp_port == 465),
            start_tls=(settings.smtp_port == 587),
            timeout=30,
        )

        logger.info("Incident email sent successfully.")
        return True

    except Exception as exc:
        logger.error(
            "Email delivery failed (%s): %s",
            type(exc).__name__,
            str(exc),
        )
        return False
