from __future__ import annotations

import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from smtplib import SMTPException

from ..config import SMTP


DEFAULT_EMAIL_SUBJECT = "Документы"
DEFAULT_EMAIL_BODY = (
    "Направляем сформированный документ во вложении.\n\n"
    "С уважением,\n"
    "ФГАНУ ЦИТиС"
)


class MailerError(Exception):
    """Ошибка отправки письма."""


def _smtp_attempts() -> list[tuple[int, bool, bool]]:
    attempts: list[tuple[int, bool, bool]] = []
    use_ssl = SMTP.use_ssl or SMTP.port == 465
    attempts.append((SMTP.port, use_ssl, SMTP.use_starttls))

    if SMTP.host.lower() in {"smtp.gmail.com", "smtp.googlemail.com"}:
        for fallback in ((587, False, True), (465, True, False)):
            if fallback not in attempts:
                attempts.append(fallback)

    return attempts


def _smtp_hosts() -> list[str]:
    hosts = [SMTP.host]
    if SMTP.host.lower() == "smtp.gmail.com":
        hosts.append("smtp.googlemail.com")
    return hosts


def get_development_recipient() -> str:
    recipient = (SMTP.dev_force_recipient or SMTP.to_email or "").strip()
    if not recipient:
        raise MailerError("Не указан email разработчика для тестовой отправки")
    return recipient


def send_document_email(
    document_path: Path,
    to_email: str | None = None,
    subject: str | None = None,
    body: str | None = None,
) -> None:
    recipient = get_development_recipient()

    if not document_path.exists():
        raise MailerError(f"Файл для отправки не найден: {document_path}")

    if not SMTP.user or not SMTP.password:
        raise MailerError("SMTP_USER и SMTP_PASSWORD должны быть заданы")

    message = EmailMessage()
    message["Subject"] = subject or DEFAULT_EMAIL_SUBJECT
    message["From"] = SMTP.from_email or SMTP.user
    message["To"] = recipient

    # Для отладки сохраняем, кому письмо "хотели" отправить по бизнес-логике.
    if to_email:
        message["X-Original-Requested-To"] = to_email

    message.set_content(body or DEFAULT_EMAIL_BODY)

    mime_type, _ = mimetypes.guess_type(document_path.name)
    if mime_type:
        maintype, subtype = mime_type.split("/", 1)
    else:
        maintype, subtype = "application", "octet-stream"

    with document_path.open("rb") as file:
        message.add_attachment(
            file.read(),
            maintype=maintype,
            subtype=subtype,
            filename=document_path.name,
        )

    context = ssl.create_default_context()
    errors: list[str] = []

    for host in _smtp_hosts():
        for port, use_ssl, use_starttls in _smtp_attempts():
            try:
                if use_ssl:
                    with smtplib.SMTP_SSL(
                        host,
                        port,
                        timeout=SMTP.timeout,
                        context=context,
                    ) as smtp:
                        smtp.login(SMTP.user, SMTP.password)
                        smtp.send_message(message)
                        return

                with smtplib.SMTP(host, port, timeout=SMTP.timeout) as smtp:
                    smtp.ehlo()

                    if use_starttls:
                        if not smtp.has_extn("starttls"):
                            raise MailerError("SMTP-сервер не поддерживает STARTTLS")
                        smtp.starttls(context=context)
                        smtp.ehlo()

                    smtp.login(SMTP.user, SMTP.password)
                    smtp.send_message(message)
                    return

            except (OSError, SMTPException, MailerError) as exc:
                mode = "SSL" if use_ssl else ("STARTTLS" if use_starttls else "PLAIN")
                errors.append(f"{host}:{port} {mode} -> {exc.__class__.__name__}: {exc}")

    raise MailerError("Не удалось отправить письмо. " + " | ".join(errors))