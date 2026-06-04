from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from psycopg2 import Error


class HistoryRepositoryError(Exception):
    """Ошибка работы с историей документов и отправок."""


def calculate_file_hash(path: Path) -> str:
    sha256 = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def register_generated_document(
    conn,
    template_key: str,
    document_type: str,
    file_path: Path,
    created_by: int | None,
    client_id: int | None = None,
    contract_id: int | None = None,
) -> int:
    query = """
        INSERT INTO generated_documents (
            template_key,
            document_type,
            client_id,
            contract_id,
            created_by,
            file_name,
            file_path,
            file_hash
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """

    try:
        file_hash = calculate_file_hash(file_path) if file_path.exists() else None
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    template_key,
                    document_type,
                    client_id,
                    contract_id,
                    created_by,
                    file_path.name,
                    str(file_path),
                    file_hash,
                ),
            )
            row = cur.fetchone()
        return int(row["id"])
    except Error as exc:
        raise HistoryRepositoryError(f"Ошибка регистрации документа: {exc}") from exc


def register_dispatch_requested(
    conn,
    document_id: int,
    sent_by: int | None,
    recipient_email: str,
    original_recipient_email: str | None,
    subject: str,
) -> int:
    query = """
        INSERT INTO document_dispatches (
            document_id,
            sent_by,
            recipient_email,
            original_recipient_email,
            subject,
            status
        )
        VALUES (%s, %s, %s, %s, %s, 'send_requested')
        RETURNING id
    """

    try:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    document_id,
                    sent_by,
                    recipient_email,
                    original_recipient_email,
                    subject,
                ),
            )
            row = cur.fetchone()
        return int(row["id"])
    except Error as exc:
        raise HistoryRepositoryError(f"Ошибка регистрации отправки: {exc}") from exc


def mark_dispatch_sent(conn, dispatch_id: int) -> None:
    query = """
        UPDATE document_dispatches
        SET status = 'sent',
            sent_at = NOW(),
            error_message = NULL
        WHERE id = %s
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query, (dispatch_id,))
            if cur.rowcount == 0:
                raise HistoryRepositoryError(f"Отправка id={dispatch_id} не найдена.")
    except HistoryRepositoryError:
        raise
    except Error as exc:
        raise HistoryRepositoryError(f"Ошибка обновления статуса отправки: {exc}") from exc


def mark_dispatch_failed(conn, dispatch_id: int, error_message: str) -> None:
    query = """
        UPDATE document_dispatches
        SET status = 'failed',
            error_message = %s
        WHERE id = %s
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query, (error_message, dispatch_id))
            if cur.rowcount == 0:
                raise HistoryRepositoryError(f"Отправка id={dispatch_id} не найдена.")
    except HistoryRepositoryError:
        raise
    except Error as exc:
        raise HistoryRepositoryError(f"Ошибка записи ошибки отправки: {exc}") from exc


def list_document_dispatches(
    conn,
    limit: int = 200,
    offset: int = 0,
    only_user_id: int | None = None,
    status: str | None = None,
    company_search: str | None = None,
) -> list[dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []

    if only_user_id is not None:
        filters.append("dd.sent_by = %s")
        params.append(only_user_id)

    if status:
        filters.append("dd.status = %s")
        params.append(status)

    if company_search:
        filters.append("(c.company_full_name ILIKE %s OR c.company_short_name ILIKE %s)")
        params.extend([f"%{company_search}%", f"%{company_search}%"])

    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)

    query = f"""
        SELECT
            dd.id AS dispatch_id,
            dd.status,
            dd.recipient_email,
            dd.original_recipient_email,
            dd.subject,
            dd.created_at AS dispatch_created_at,
            dd.sent_at,
            dd.error_message,

            gd.id AS document_id,
            gd.template_key,
            gd.document_type,
            gd.file_name,
            gd.file_path,
            gd.created_at AS document_created_at,

            c.id AS client_id,
            c.company_full_name,
            c.company_short_name,

            ct.id AS contract_id,
            ct.contract_number,

            u.id AS sent_by_id,
            u.full_name AS sent_by_full_name,
            u.username AS sent_by_username
        FROM document_dispatches dd
        JOIN generated_documents gd ON gd.id = dd.document_id
        LEFT JOIN clients c ON c.id = gd.client_id
        LEFT JOIN contracts ct ON ct.id = gd.contract_id
        LEFT JOIN app_users u ON u.id = dd.sent_by
        {where_sql}
        ORDER BY COALESCE(dd.sent_at, dd.created_at) DESC, dd.id DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [dict(row) for row in rows]
    except Error as exc:
        raise HistoryRepositoryError(f"Ошибка чтения журнала отправок: {exc}") from exc


def list_generated_documents(
    conn,
    limit: int = 200,
    offset: int = 0,
    only_user_id: int | None = None,
) -> list[dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []

    if only_user_id is not None:
        filters.append("gd.created_by = %s")
        params.append(only_user_id)

    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)

    query = f"""
        SELECT
            gd.id,
            gd.template_key,
            gd.document_type,
            gd.file_name,
            gd.file_path,
            gd.file_hash,
            gd.created_at,
            c.company_full_name,
            c.company_short_name,
            ct.contract_number,
            u.full_name AS created_by_full_name,
            u.username AS created_by_username
        FROM generated_documents gd
        LEFT JOIN clients c ON c.id = gd.client_id
        LEFT JOIN contracts ct ON ct.id = gd.contract_id
        LEFT JOIN app_users u ON u.id = gd.created_by
        {where_sql}
        ORDER BY gd.created_at DESC, gd.id DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [dict(row) for row in rows]
    except Error as exc:
        raise HistoryRepositoryError(f"Ошибка чтения истории документов: {exc}") from exc
