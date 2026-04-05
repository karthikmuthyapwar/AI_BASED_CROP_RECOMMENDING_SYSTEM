import logging
import smtplib
from email.message import EmailMessage

from backend.app.config import settings

logger = logging.getLogger(__name__)


def send_verification_email(recipient_email: str, code: str) -> bool:
    subject = "Your Crop Advisor verification code"
    body = (
        "Hello,\n\n"
        f"Your verification code is: {code}\n"
        "The code expires in 10 minutes.\n\n"
        "Regards,\nAI Crop Advisor"
    )

    if not settings.smtp_host or not settings.smtp_sender:
        logger.warning(
            "SMTP not configured. Verification code for %s is %s",
            recipient_email,
            code,
        )
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_sender
    msg["To"] = recipient_email
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)

    return True
