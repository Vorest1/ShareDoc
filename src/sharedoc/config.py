import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class DbConfig:
    host: str = os.getenv("DB_HOST", "127.0.0.1")
    port: int = int(os.getenv("DB_PORT", "5432"))
    dbname: str = os.getenv("DB_NAME", "ClientBase")
    user: str = os.getenv("DB_USER", "postgres")
    password: str = os.getenv("DB_PASSWORD", "admin")


@dataclass(frozen=True)
class SmtpConfig:
    host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port: int = int(os.getenv("SMTP_PORT", "587"))
    user: str = os.getenv("SMTP_USER", "")
    password: str = os.getenv("SMTP_PASSWORD", "")
    from_email: str = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", ""))
    to_email: str = os.getenv("SMTP_TO", "khristoforov.volodya@gmail.com")


DB = DbConfig()
SMTP = SmtpConfig()
