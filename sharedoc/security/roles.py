from __future__ import annotations

ROLE_ADMIN = "admin"
ROLE_EMPLOYEE = "employee"
ROLE_MANAGER = "manager"

ADMIN_ROLES = {ROLE_ADMIN}
DOCUMENT_WORK_ROLES = {ROLE_EMPLOYEE, ROLE_MANAGER}
MANAGER_ROLES = {ROLE_MANAGER}


class AccessDeniedError(Exception):
    """Недостаточно прав для выполнения операции."""


def require_role(role_code: str, allowed_roles: set[str]) -> None:
    if role_code not in allowed_roles:
        raise AccessDeniedError("Недостаточно прав для выполнения операции.")


def require_permission(permission_code: str, permissions: set[str]) -> None:
    if permission_code not in permissions:
        raise AccessDeniedError("Недостаточно прав для выполнения операции.")
