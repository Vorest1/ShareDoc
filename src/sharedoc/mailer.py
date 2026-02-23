import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path

from sharedoc.config import SMTP

EMAIL_SUBJECT = "\u0414\u043e\u0433\u043e\u0432\u043e\u0440 \u043d\u0430 \u043e\u043a\u0430\u0437\u0430\u043d\u0438\u0435 \u0443\u0441\u043b\u0443\u0433"
EMAIL_BODY = (
    "\u041f\u0440\u0438\u0441\u044b\u043b\u0430\u0435\u043c \u0434\u043e\u0433\u043e\u0432\u043e\u0440 "
    "\u043d\u0430 \u043e\u043a\u0430\u0437\u0430\u043d\u0438\u0435 \u0443\u0441\u043b\u0443\u0433\n"
    "\u0421 \u0443\u0432\u0430\u0436\u0435\u043d\u0438\u0435\u043c, \u0412\u043b\u0430\u0434!"
)


def send_contract_email(document_path: Path) -> None:
    if not SMTP.user or not SMTP.password:
        raise RuntimeError("SMTP_USER and SMTP_PASSWORD must be set")

    message = EmailMessage()
    message["Subject"] = EMAIL_SUBJECT
    message["From"] = SMTP.from_email or SMTP.user
    message["To"] = SMTP.to_email
    message.set_content(EMAIL_BODY)

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

    with smtplib.SMTP(SMTP.host, SMTP.port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(SMTP.user, SMTP.password)
        smtp.send_message(message)
