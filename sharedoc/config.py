from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class DbConfig:
    host: str = os.getenv("DB_HOST", "127.0.0.1")
    port: int = int(os.getenv("DB_PORT", "5432"))
    dbname: str = os.getenv("DB_NAME", "ClientBase")
    user: str = os.getenv("DB_USER", "postgres")
    password: str = os.getenv("DB_PASSWORD", "admin")


@dataclass(frozen=True)
class AppConfig:
    base_dir: Path = Path(__file__).resolve().parent
    template_dir: Path = base_dir / "template"
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", str(Path.cwd() / "output")))


@dataclass(frozen=True)
class SmtpConfig:
    host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port: int = int(os.getenv("SMTP_PORT", "465"))
    user: str = os.getenv("SMTP_USER", "")
    password: str = os.getenv("SMTP_PASSWORD", "")
    from_email: str = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", ""))
    to_email: str = os.getenv("SMTP_TO", "")
    timeout: int = int(os.getenv("SMTP_TIMEOUT", "20"))
    use_ssl: bool = _env_bool("SMTP_USE_SSL", True)
    use_starttls: bool = _env_bool("SMTP_USE_STARTTLS", False)


DB = DbConfig()
APP = AppConfig()
SMTP = SmtpConfig()