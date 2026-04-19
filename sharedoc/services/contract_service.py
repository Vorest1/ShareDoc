from __future__ import annotations

from pathlib import Path
from typing import Any

from ..db.connection import DatabaseConnectionError, get_connection
from ..db.repository import (
    RepositoryError,
    fetch_contract_by_id,
    fetch_contract_by_number,
    list_contracts,
)
from ..documents.renderer import DocumentRenderError, render_document
from ..mail.mailer import MailerError, send_document_email


class ServiceError(Exception):
    """Общая ошибка сервисного слоя."""


def build_email_payload(template_key: str, bundle: Any) -> tuple[str, str]:
    contract = bundle.contract
    contract_number = contract.get("contract_number", "")
    program_name = contract.get("program_name", "")

    if template_key == "contract_offer":
        subject = f"Договор № {contract_number} на обучение"
        body = (
            f"Направляем договор № {contract_number} "
            f"по программе «{program_name}» во вложении.\n\n"
            "С уважением,\n"
            "ФГАНУ ЦИТиС"
        )
        return subject, body

    if template_key == "qualification":
        subject = f"Документ по программе «{program_name}»"
        body = (
            f"Направляем документ по программе повышения квалификации "
            f"«{program_name}» во вложении.\n\n"
            "С уважением,\n"
            "ФГАНУ ЦИТиС"
        )
        return subject, body

    if template_key == "scientific_guidance":
        subject = f"Документ по программе «{program_name}»"
        body = (
            f"Направляем документ по программе "
            f"«{program_name}» во вложении.\n\n"
            "С уважением,\n"
            "ФГАНУ ЦИТиС"
        )
        return subject, body

    subject = "Документы"
    body = (
        "Направляем сформированный документ во вложении.\n\n"
        "С уважением,\n"
        "ФГАНУ ЦИТиС"
    )
    return subject, body


def get_contracts_summary() -> list[dict[str, Any]]:
    conn = None
    try:
        conn = get_connection()
        return list_contracts(conn)
    except (DatabaseConnectionError, RepositoryError) as exc:
        raise ServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def generate_document_by_id(contract_id: int, template_key: str) -> Path:
    conn = None
    try:
        conn = get_connection()
        bundle = fetch_contract_by_id(conn, contract_id)
        return render_document(bundle, template_key)
    except (DatabaseConnectionError, RepositoryError, DocumentRenderError) as exc:
        raise ServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def generate_document_by_number(contract_number: str, template_key: str) -> Path:
    conn = None
    try:
        conn = get_connection()
        bundle = fetch_contract_by_number(conn, contract_number)
        return render_document(bundle, template_key)
    except (DatabaseConnectionError, RepositoryError, DocumentRenderError) as exc:
        raise ServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def generate_and_send_document_by_id(contract_id: int, template_key: str) -> Path:
    conn = None
    try:
        conn = get_connection()
        bundle = fetch_contract_by_id(conn, contract_id)
        output_path = render_document(bundle, template_key)

        subject, body = build_email_payload(template_key, bundle)
        send_document_email(
            document_path=output_path,
            subject=subject,
            body=body,
        )
        return output_path

    except (
        DatabaseConnectionError,
        RepositoryError,
        DocumentRenderError,
        MailerError,
    ) as exc:
        raise ServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def generate_and_send_document_by_number(contract_number: str, template_key: str) -> Path:
    conn = None
    try:
        conn = get_connection()
        bundle = fetch_contract_by_number(conn, contract_number)
        output_path = render_document(bundle, template_key)

        subject, body = build_email_payload(template_key, bundle)
        send_document_email(
            document_path=output_path,
            subject=subject,
            body=body,
        )
        return output_path

    except (
        DatabaseConnectionError,
        RepositoryError,
        DocumentRenderError,
        MailerError,
    ) as exc:
        raise ServiceError(str(exc)) from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass