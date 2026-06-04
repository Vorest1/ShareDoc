from __future__ import annotations

from typing import Any

from psycopg2 import Error
from psycopg2.extras import Json


class AuditRepositoryError(Exception):
    """Ошибка записи или чтения аудита."""


def write_audit_log(
    conn,
    action: str,
    user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> int:
    query = """
        INSERT INTO audit_log (
            user_id,
            action,
            entity_type,
            entity_id,
            details,
            ip_address
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """

    try:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    user_id,
                    action,
                    entity_type,
                    entity_id,
                    Json(details or {}),
                    ip_address,
                ),
            )
            row = cur.fetchone()
        return int(row["id"])
    except Error as exc:
        raise AuditRepositoryError(f"Ошибка записи аудита: {exc}") from exc


def list_audit_log(
    conn,
    limit: int = 200,
    offset: int = 0,
    user_id: int | None = None,
    action: str | None = None,
) -> list[dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []

    if user_id is not None:
        filters.append("al.user_id = %s")
        params.append(user_id)

    if action:
        filters.append("al.action = %s")
        params.append(action)

    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)

    query = f"""
        SELECT
            al.id,
            al.user_id,
            u.full_name AS user_full_name,
            u.username,
            al.action,
            al.entity_type,
            al.entity_id,
            al.details,
            al.ip_address,
            al.created_at
        FROM audit_log al
        LEFT JOIN app_users u ON u.id = al.user_id
        {where_sql}
        ORDER BY al.created_at DESC, al.id DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [dict(row) for row in rows]
    except Error as exc:
        raise AuditRepositoryError(f"Ошибка чтения аудита: {exc}") from exc
