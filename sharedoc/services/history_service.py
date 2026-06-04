from __future__ import annotations

from pathlib import Path
from typing import Any

from sharedoc.db.connection import DatabaseConnectionError, get_connection
from sharedoc.db.history_repository import (
    HistoryRepositoryError,
    list_document_dispatches,
    list_generated_documents,
    mark_dispatch_failed,
    mark_dispatch_sent,
    register_dispatch_requested,
    register_generated_document,
)
from sharedoc.security.roles import AccessDeniedError, require_permission
from sharedoc.db.auth_repository import AuthUser


class HistoryServiceError(Exception):
    """Ошибка сервиса истории документов."""


def save_generated_document_record(
    actor: AuthUser,
    template_key: str,
    document_type: str,
    file_path: Path,
    client_id: int | None = None,
    contract_id: int | None = None,
) -> int:
    require_permission("documents.generate", actor.permissions)

    conn = None
    try:
        conn = get_connection()
        document_id = register_generated_document(
            conn,
            template_key=template_key,
            document_type=document_type,
            file_path=file_path,
            created_by=actor.id,
            client_id=client_id,
            contract_id=contract_id,
        )
        conn.commit()
        return document_id
    except (DatabaseConnectionError, HistoryRepositoryError, AccessDeniedError) as exc:
        if conn is not None:
            conn.rollback()
        raise HistoryServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def create_dispatch_record(
    actor: AuthUser,
    document_id: int,
    recipient_email: str,
    original_recipient_email: str | None,
    subject: str,
) -> int:
    require_permission("documents.send", actor.permissions)

    conn = None
    try:
        conn = get_connection()
        dispatch_id = register_dispatch_requested(
            conn,
            document_id=document_id,
            sent_by=actor.id,
            recipient_email=recipient_email,
            original_recipient_email=original_recipient_email,
            subject=subject,
        )
        conn.commit()
        return dispatch_id
    except (DatabaseConnectionError, HistoryRepositoryError, AccessDeniedError) as exc:
        if conn is not None:
            conn.rollback()
        raise HistoryServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def set_dispatch_sent(dispatch_id: int) -> None:
    conn = None
    try:
        conn = get_connection()
        mark_dispatch_sent(conn, dispatch_id)
        conn.commit()
    except (DatabaseConnectionError, HistoryRepositoryError) as exc:
        if conn is not None:
            conn.rollback()
        raise HistoryServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def set_dispatch_failed(dispatch_id: int, error_message: str) -> None:
    conn = None
    try:
        conn = get_connection()
        mark_dispatch_failed(conn, dispatch_id, error_message)
        conn.commit()
    except (DatabaseConnectionError, HistoryRepositoryError) as exc:
        if conn is not None:
            conn.rollback()
        raise HistoryServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def get_my_dispatches(actor: AuthUser, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
    require_permission("documents.view_own_history", actor.permissions)

    conn = None
    try:
        conn = get_connection()
        return list_document_dispatches(conn, limit=limit, offset=offset, only_user_id=actor.id)
    except (DatabaseConnectionError, HistoryRepositoryError, AccessDeniedError) as exc:
        raise HistoryServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def get_all_dispatches(
    actor: AuthUser,
    limit: int = 200,
    offset: int = 0,
    status: str | None = None,
    company_search: str | None = None,
) -> list[dict[str, Any]]:
    require_permission("documents.view_all_history", actor.permissions)

    conn = None
    try:
        conn = get_connection()
        return list_document_dispatches(
            conn,
            limit=limit,
            offset=offset,
            status=status,
            company_search=company_search,
        )
    except (DatabaseConnectionError, HistoryRepositoryError, AccessDeniedError) as exc:
        raise HistoryServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def get_my_documents(actor: AuthUser, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
    require_permission("documents.view_own_history", actor.permissions)

    conn = None
    try:
        conn = get_connection()
        return list_generated_documents(conn, limit=limit, offset=offset, only_user_id=actor.id)
    except (DatabaseConnectionError, HistoryRepositoryError, AccessDeniedError) as exc:
        raise HistoryServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()
