from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg2 import Error

from sharedoc.security.passwords import hash_password, verify_password


class AuthRepositoryError(Exception):
    """Ошибка работы с пользователями и авторизацией."""


class AuthenticationError(Exception):
    """Неверный логин/пароль или пользователь отключен."""


@dataclass(frozen=True)
class AuthUser:
    id: int
    username: str
    full_name: str
    email: str
    role_code: str
    role_name: str
    is_active: bool
    permissions: set[str]


def _load_permissions(conn, role_id: int) -> set[str]:
    query = """
        SELECT p.code
        FROM app_role_permissions rp
        JOIN app_permissions p ON p.id = rp.permission_id
        WHERE rp.role_id = %s
        ORDER BY p.code
    """

    with conn.cursor() as cur:
        cur.execute(query, (role_id,))
        rows = cur.fetchall()

    return {str(row["code"]) for row in rows}


def _build_user(conn, row: dict[str, Any]) -> AuthUser:
    permissions = _load_permissions(conn, int(row["role_id"]))
    return AuthUser(
        id=int(row["id"]),
        username=str(row["username"]),
        full_name=str(row["full_name"]),
        email=str(row.get("email") or ""),
        role_code=str(row["role_code"]),
        role_name=str(row["role_name"]),
        is_active=bool(row["is_active"]),
        permissions=permissions,
    )


def authenticate_user(conn, username: str, password: str) -> AuthUser:
    query = """
        SELECT
            u.id,
            u.username,
            u.password_hash,
            u.full_name,
            u.email,
            u.role_id,
            u.is_active,
            r.code AS role_code,
            r.name AS role_name
        FROM app_users u
        JOIN app_roles r ON r.id = u.role_id
        WHERE u.username = %s
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query, (username,))
            row = cur.fetchone()

        if row is None:
            raise AuthenticationError("Неверный логин или пароль.")

        if not bool(row["is_active"]):
            raise AuthenticationError("Учетная запись заблокирована.")

        if not verify_password(password, str(row["password_hash"])):
            raise AuthenticationError("Неверный логин или пароль.")

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE app_users SET last_login_at = NOW() WHERE id = %s",
                (int(row["id"]),),
            )

        return _build_user(conn, dict(row))

    except AuthenticationError:
        raise
    except Error as exc:
        raise AuthRepositoryError(f"Ошибка авторизации пользователя: {exc}") from exc


def get_user_by_id(conn, user_id: int) -> AuthUser:
    query = """
        SELECT
            u.id,
            u.username,
            u.full_name,
            u.email,
            u.role_id,
            u.is_active,
            r.code AS role_code,
            r.name AS role_name
        FROM app_users u
        JOIN app_roles r ON r.id = u.role_id
        WHERE u.id = %s
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            row = cur.fetchone()

        if row is None:
            raise AuthRepositoryError(f"Пользователь с id={user_id} не найден.")

        return _build_user(conn, dict(row))
    except AuthRepositoryError:
        raise
    except Error as exc:
        raise AuthRepositoryError(f"Ошибка чтения пользователя: {exc}") from exc


def list_users(conn) -> list[dict[str, Any]]:
    query = """
        SELECT
            u.id,
            u.username,
            u.full_name,
            u.email,
            r.code AS role_code,
            r.name AS role_name,
            u.is_active,
            u.created_at,
            u.updated_at,
            u.last_login_at
        FROM app_users u
        JOIN app_roles r ON r.id = u.role_id
        ORDER BY u.id
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
        return [dict(row) for row in rows]
    except Error as exc:
        raise AuthRepositoryError(f"Ошибка чтения списка пользователей: {exc}") from exc


def list_roles(conn) -> list[dict[str, Any]]:
    query = """
        SELECT id, code, name, description
        FROM app_roles
        ORDER BY id
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
        return [dict(row) for row in rows]
    except Error as exc:
        raise AuthRepositoryError(f"Ошибка чтения списка ролей: {exc}") from exc


def create_user(
    conn,
    username: str,
    password: str,
    full_name: str,
    email: str | None,
    role_code: str,
) -> int:
    query = """
        INSERT INTO app_users (
            username,
            password_hash,
            full_name,
            email,
            role_id
        )
        SELECT %s, %s, %s, %s, r.id
        FROM app_roles r
        WHERE r.code = %s
        RETURNING id
    """

    try:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    username,
                    hash_password(password),
                    full_name,
                    email,
                    role_code,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise AuthRepositoryError(f"Роль '{role_code}' не найдена.")

        return int(row["id"])
    except AuthRepositoryError:
        raise
    except Error as exc:
        raise AuthRepositoryError(f"Ошибка создания пользователя: {exc}") from exc


def update_user(
    conn,
    user_id: int,
    full_name: str,
    email: str | None,
) -> None:
    query = """
        UPDATE app_users
        SET full_name = %s,
            email = %s
        WHERE id = %s
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query, (full_name, email, user_id))
            if cur.rowcount == 0:
                raise AuthRepositoryError(f"Пользователь с id={user_id} не найден.")
    except AuthRepositoryError:
        raise
    except Error as exc:
        raise AuthRepositoryError(f"Ошибка изменения пользователя: {exc}") from exc


def update_user_role(conn, user_id: int, role_code: str) -> None:
    query = """
        UPDATE app_users
        SET role_id = r.id
        FROM app_roles r
        WHERE app_users.id = %s
          AND r.code = %s
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, role_code))
            if cur.rowcount == 0:
                raise AuthRepositoryError(
                    f"Пользователь id={user_id} или роль '{role_code}' не найдены."
                )
    except AuthRepositoryError:
        raise
    except Error as exc:
        raise AuthRepositoryError(f"Ошибка назначения роли: {exc}") from exc


def set_user_active(conn, user_id: int, is_active: bool) -> None:
    query = """
        UPDATE app_users
        SET is_active = %s
        WHERE id = %s
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query, (is_active, user_id))
            if cur.rowcount == 0:
                raise AuthRepositoryError(f"Пользователь с id={user_id} не найден.")
    except AuthRepositoryError:
        raise
    except Error as exc:
        raise AuthRepositoryError(f"Ошибка изменения статуса пользователя: {exc}") from exc


def change_password(conn, user_id: int, new_password: str) -> None:
    query = """
        UPDATE app_users
        SET password_hash = %s
        WHERE id = %s
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query, (hash_password(new_password), user_id))
            if cur.rowcount == 0:
                raise AuthRepositoryError(f"Пользователь с id={user_id} не найден.")
    except AuthRepositoryError:
        raise
    except Error as exc:
        raise AuthRepositoryError(f"Ошибка изменения пароля: {exc}") from exc
