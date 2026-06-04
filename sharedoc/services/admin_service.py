from __future__ import annotations

from typing import Any

from sharedoc.db.admin_repository import (
    AdminRepositoryError,
    create_row,
    delete_row,
    get_row,
    list_admin_entities,
    list_rows,
    update_row,
)
from sharedoc.db.audit_repository import write_audit_log
from sharedoc.db.auth_repository import (
    AuthRepositoryError,
    AuthUser,
    create_user,
    list_roles,
    list_users,
    set_user_active,
    update_user,
    update_user_role,
)
from sharedoc.db.connection import DatabaseConnectionError, get_connection
from sharedoc.security.roles import AccessDeniedError, require_permission


class AdminServiceError(Exception):
    """Ошибка административного сервиса."""


def _require_admin_data_access(actor: AuthUser, permission: str) -> None:
    require_permission(permission, actor.permissions)


def get_admin_entities(actor: AuthUser) -> list[dict[str, Any]]:
    _require_admin_data_access(actor, "data.read")
    return list_admin_entities()


def admin_list_rows(
    actor: AuthUser,
    entity: str,
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
) -> list[dict[str, Any]]:
    _require_admin_data_access(actor, "data.read")

    conn = None
    try:
        conn = get_connection()
        return list_rows(conn, entity, limit=limit, offset=offset, search=search)
    except (DatabaseConnectionError, AdminRepositoryError, AccessDeniedError) as exc:
        raise AdminServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def admin_get_row(actor: AuthUser, entity: str, row_id: int) -> dict[str, Any]:
    _require_admin_data_access(actor, "data.read")

    conn = None
    try:
        conn = get_connection()
        return get_row(conn, entity, row_id)
    except (DatabaseConnectionError, AdminRepositoryError, AccessDeniedError) as exc:
        raise AdminServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def admin_create_row(actor: AuthUser, entity: str, data: dict[str, Any]) -> int:
    _require_admin_data_access(actor, "data.create")

    conn = None
    try:
        conn = get_connection()
        row_id = create_row(conn, entity, data)
        write_audit_log(
            conn,
            action="admin_create_row",
            user_id=actor.id,
            entity_type=entity,
            entity_id=row_id,
            details={"data": data},
        )
        conn.commit()
        return row_id
    except (DatabaseConnectionError, AdminRepositoryError, AccessDeniedError) as exc:
        if conn is not None:
            conn.rollback()
        raise AdminServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def admin_update_row(actor: AuthUser, entity: str, row_id: int, data: dict[str, Any]) -> None:
    _require_admin_data_access(actor, "data.update")

    conn = None
    try:
        conn = get_connection()
        update_row(conn, entity, row_id, data)
        write_audit_log(
            conn,
            action="admin_update_row",
            user_id=actor.id,
            entity_type=entity,
            entity_id=row_id,
            details={"data": data},
        )
        conn.commit()
    except (DatabaseConnectionError, AdminRepositoryError, AccessDeniedError) as exc:
        if conn is not None:
            conn.rollback()
        raise AdminServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def admin_delete_row(actor: AuthUser, entity: str, row_id: int) -> None:
    _require_admin_data_access(actor, "data.delete")

    conn = None
    try:
        conn = get_connection()
        delete_row(conn, entity, row_id)
        write_audit_log(
            conn,
            action="admin_delete_row",
            user_id=actor.id,
            entity_type=entity,
            entity_id=row_id,
        )
        conn.commit()
    except (DatabaseConnectionError, AdminRepositoryError, AccessDeniedError) as exc:
        if conn is not None:
            conn.rollback()
        raise AdminServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def admin_list_users(actor: AuthUser) -> list[dict[str, Any]]:
    require_permission("users.read", actor.permissions)

    conn = None
    try:
        conn = get_connection()
        return list_users(conn)
    except (DatabaseConnectionError, AuthRepositoryError, AccessDeniedError) as exc:
        raise AdminServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def admin_list_roles(actor: AuthUser) -> list[dict[str, Any]]:
    require_permission("users.read", actor.permissions)

    conn = None
    try:
        conn = get_connection()
        return list_roles(conn)
    except (DatabaseConnectionError, AuthRepositoryError, AccessDeniedError) as exc:
        raise AdminServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def admin_create_user(
    actor: AuthUser,
    username: str,
    password: str,
    full_name: str,
    email: str | None,
    role_code: str,
) -> int:
    require_permission("users.create", actor.permissions)

    conn = None
    try:
        conn = get_connection()
        user_id = create_user(conn, username, password, full_name, email, role_code)
        write_audit_log(
            conn,
            action="create_user",
            user_id=actor.id,
            entity_type="app_users",
            entity_id=user_id,
            details={"username": username, "role_code": role_code},
        )
        conn.commit()
        return user_id
    except (DatabaseConnectionError, AuthRepositoryError, AccessDeniedError) as exc:
        if conn is not None:
            conn.rollback()
        raise AdminServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def admin_update_user(
    actor: AuthUser,
    user_id: int,
    full_name: str,
    email: str | None,
) -> None:
    require_permission("users.update", actor.permissions)

    conn = None
    try:
        conn = get_connection()
        update_user(conn, user_id, full_name, email)
        write_audit_log(
            conn,
            action="update_user",
            user_id=actor.id,
            entity_type="app_users",
            entity_id=user_id,
            details={"full_name": full_name, "email": email},
        )
        conn.commit()
    except (DatabaseConnectionError, AuthRepositoryError, AccessDeniedError) as exc:
        if conn is not None:
            conn.rollback()
        raise AdminServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def admin_update_user_role(actor: AuthUser, user_id: int, role_code: str) -> None:
    require_permission("roles.assign", actor.permissions)

    conn = None
    try:
        conn = get_connection()
        update_user_role(conn, user_id, role_code)
        write_audit_log(
            conn,
            action="update_user_role",
            user_id=actor.id,
            entity_type="app_users",
            entity_id=user_id,
            details={"role_code": role_code},
        )
        conn.commit()
    except (DatabaseConnectionError, AuthRepositoryError, AccessDeniedError) as exc:
        if conn is not None:
            conn.rollback()
        raise AdminServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def admin_set_user_active(actor: AuthUser, user_id: int, is_active: bool) -> None:
    require_permission("users.update", actor.permissions)

    conn = None
    try:
        conn = get_connection()
        set_user_active(conn, user_id, is_active)
        write_audit_log(
            conn,
            action="set_user_active",
            user_id=actor.id,
            entity_type="app_users",
            entity_id=user_id,
            details={"is_active": is_active},
        )
        conn.commit()
    except (DatabaseConnectionError, AuthRepositoryError, AccessDeniedError) as exc:
        if conn is not None:
            conn.rollback()
        raise AdminServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()
