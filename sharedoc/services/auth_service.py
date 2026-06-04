from __future__ import annotations

from sharedoc.db.audit_repository import write_audit_log
from sharedoc.db.auth_repository import (
    AuthRepositoryError,
    AuthUser,
    AuthenticationError,
    authenticate_user,
)
from sharedoc.db.connection import DatabaseConnectionError, get_connection


class AuthServiceError(Exception):
    """Ошибка сервиса авторизации."""


def login(username: str, password: str, ip_address: str | None = None) -> AuthUser:
    conn = None
    try:
        conn = get_connection()
        user = authenticate_user(conn, username, password)
        write_audit_log(
            conn,
            action="login",
            user_id=user.id,
            entity_type="app_users",
            entity_id=user.id,
            ip_address=ip_address,
        )
        conn.commit()
        return user
    except AuthenticationError:
        if conn is not None:
            conn.rollback()
        raise
    except (DatabaseConnectionError, AuthRepositoryError) as exc:
        if conn is not None:
            conn.rollback()
        raise AuthServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()
