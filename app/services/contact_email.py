from email.message import EmailMessage
import smtplib

from app.config import settings


def send_contact_email(name: str, email: str, subject: str, message: str) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST is not configured")
    if not settings.contact_email_from:
        raise RuntimeError("CONTACT_EMAIL_FROM is not configured")
    if not settings.contact_email_to:
        raise RuntimeError("CONTACT_EMAIL_TO is not configured")

    email_message = EmailMessage()
    email_message["Subject"] = f"[CVbot Contact] {subject}"
    email_message["From"] = settings.contact_email_from
    email_message["To"] = settings.contact_email_to
    email_message["Reply-To"] = email
    email_message.set_content(
        "New contact form submission:\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Subject: {subject}\n\n"
        "Message:\n"
        f"{message}\n"
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(email_message)
