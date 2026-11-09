"""Outgoing email over SMTP.

Set SMTP_HOST (and usually SMTP_USER / SMTP_PASSWORD / SMTP_FROM) to send real
mail. With no SMTP_HOST the message is written to the server log instead, so
local development works without a mail account; never rely on that in production.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("unicompass.mailer")


class MailerError(Exception):
    """The message could not be handed to the mail server."""


def smtp_configured() -> bool:
    if not settings.SMTP_HOST:
        return False
    # Gmail refuses anonymous sending, so without a login treat it as not set up yet.
    if "gmail.com" in settings.SMTP_HOST.lower() and not (settings.SMTP_USER and settings.SMTP_PASSWORD):
        return False
    return True


def _send_sync(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER or "no-reply@unicompass.local"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    if settings.SMTP_SSL:
        server: smtplib.SMTP = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15, context=context)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
    with server:
        if not settings.SMTP_SSL and settings.SMTP_STARTTLS:
            server.starttls(context=context)
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send a message. Returns False (after logging it) when SMTP is not configured."""
    if not smtp_configured():
        logger.warning("SMTP is not configured; email to %s not sent.\nSubject: %s\n%s", to, subject, body)
        return False
    try:
        await asyncio.to_thread(_send_sync, to, subject, body)
    except smtplib.SMTPAuthenticationError as exc:
        logger.error("SMTP login was rejected (for Gmail use an App Password, not your normal password): %s", exc)
        raise MailerError("The mail server rejected its login. Please try again later.") from exc
    except Exception as exc:  # smtplib raises a wide family of errors
        logger.error("Could not send email to %s: %s", to, exc)
        raise MailerError("Could not send the email. Please try again shortly.") from exc
    return True


if __name__ == "__main__":  # python -m app.services.mailer you@example.com
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m app.services.mailer <recipient-email>")
    if not smtp_configured():
        raise SystemExit("SMTP_HOST is not set in backend/.env")
    try:
        _send_sync(sys.argv[1], "UniCompass SMTP test", "If you can read this, outgoing email works.")
    except smtplib.SMTPAuthenticationError as exc:
        raise SystemExit(f"Login rejected: {exc}\nFor Gmail use a 16-character App Password (2-Step Verification must be on).")
    except Exception as exc:
        raise SystemExit(f"Failed: {type(exc).__name__}: {exc}")
    print(f"Sent a test email to {sys.argv[1]} via {settings.SMTP_HOST}:{settings.SMTP_PORT}")
