from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from psycopg2 import Error

from sharedoc.db.connection import DatabaseConnectionError, get_connection
from sharedoc.db.repository import (
    ContractBundle,
    RepositoryError,
    fetch_contract_by_id,
    fetch_contract_by_number,
    list_contracts,
)
from sharedoc.documents.renderer import DocumentRenderError, render_document
from sharedoc.mail.mailer import MailerError, get_development_recipient, send_document_email
from sharedoc.db.auth_repository import AuthUser
from sharedoc.services.history_service import (
    HistoryServiceError,
    create_dispatch_record,
    save_generated_document_record,
    set_dispatch_failed,
    set_dispatch_sent,
)


LETTER_TEMPLATE_KEYS = {"qualification", "scientific_guidance"}
CONTRACT_TEMPLATE_KEYS = {"contract_offer"}

PROGRAM_NAME_BY_TEMPLATE = {
    "qualification": "Пользователь абонентского пункта ФИС ФРДО",
    "scientific_guidance": "Научное руководство в аспирантуре (адъюнктуре)",
}


class BackendError(Exception):
    """Ошибка слоя GUI/backend."""


@dataclass(frozen=True)
class ClientSummary:
    client_id: int
    company_full_name: str
    company_short_name: str
    email: str


@dataclass(frozen=True)
class ClientPreview:
    client_id: int
    company_full_name: str
    company_short_name: str
    representative_name: str
    representative_phone: str
    email: str


@dataclass(frozen=True)
class ContractSummary:
    contract_id: int
    contract_number: str
    contract_date: str
    company_short_name: str
    program_name: str
    listeners_count: str
    total_price: str


@dataclass(frozen=True)
class ContractPreview:
    contract_id: int
    contract_number: str
    company_full_name: str
    company_short_name: str
    contact_full_name: str
    contact_phone: str
    contact_email: str
    program_name: str
    training_period: str
    listeners_count: str
    total_price: str
    raw_bundle: ContractBundle


@dataclass(frozen=True)
class GeneratedDocument:
    file_path: Path
    to_email: str
    subject: str
    label: str
    document_id: int | None = None
    client_id: int | None = None
    contract_id: int | None = None
    template_key: str = ""


def _format_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _format_money(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        formatted = f"{value:,.2f}".replace(",", " ").replace(".", ",")
        return f"{formatted} ₽"
    if isinstance(value, (int, float)):
        formatted = f"{value:,.2f}".replace(",", " ").replace(".", ",")
        return f"{formatted} ₽"
    return str(value)


def _build_training_period(contract: dict[str, Any]) -> str:
    start = _format_date(contract.get("training_start_date"))
    end = _format_date(contract.get("training_end_date"))
    if start and end:
        return f"{start} — {end}"
    return start or end or ""


def _build_email_payload(template_key: str, bundle: ContractBundle) -> tuple[str, str]:
    contract = bundle.contract
    contract_number = str(contract.get("contract_number", "") or "")
    program_name = str(contract.get("program_name", "") or "")
    company_short_name = str(contract.get("company_short_name", "") or "")

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
        subject = f"Письмо по программе «{program_name}»"
        body = (
            f"Направляем письмо для организации «{company_short_name}» "
            f"по программе повышения квалификации «{program_name}».\n\n"
            "С уважением,\n"
            "ФГАНУ ЦИТиС"
        )
        return subject, body

    if template_key == "scientific_guidance":
        subject = f"Письмо по программе «{program_name}»"
        body = (
            f"Направляем письмо для организации «{company_short_name}» "
            f"по программе «{program_name}».\n\n"
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


def _build_contract_preview_from_bundle(bundle: ContractBundle) -> ContractPreview:
    contract = bundle.contract
    return ContractPreview(
        contract_id=int(contract["contract_id"]),
        contract_number=str(contract.get("contract_number", "") or ""),
        company_full_name=str(contract.get("company_full_name", "") or ""),
        company_short_name=str(contract.get("company_short_name", "") or ""),
        contact_full_name=str(contract.get("contact_full_name", "") or ""),
        contact_phone=str(contract.get("contact_phone", "") or ""),
        contact_email=str(contract.get("contact_email", "") or ""),
        program_name=str(contract.get("program_name", "") or ""),
        training_period=_build_training_period(contract),
        listeners_count=str(contract.get("listeners_count", "") or ""),
        total_price=_format_money(contract.get("total_price")),
        raw_bundle=bundle,
    )


def list_client_summaries() -> list[ClientSummary]:
    query = """
        SELECT
            c.id AS client_id,
            c.company_full_name,
            c.company_short_name,
            COALESCE(rep.email, c.organization_email, '') AS email
        FROM clients c
        LEFT JOIN client_representatives rep
            ON rep.client_id = c.id
           AND rep.is_primary = TRUE
        ORDER BY c.company_short_name, c.company_full_name
    """

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

        return [
            ClientSummary(
                client_id=int(row["client_id"]),
                company_full_name=str(row.get("company_full_name", "") or ""),
                company_short_name=str(row.get("company_short_name", "") or ""),
                email=str(row.get("email", "") or ""),
            )
            for row in rows
        ]

    except (DatabaseConnectionError, Error) as exc:
        raise BackendError(f"Ошибка загрузки списка компаний: {exc}") from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_client_preview_by_id(client_id: int) -> ClientPreview:
    query = """
        SELECT
            c.id AS client_id,
            c.company_full_name,
            c.company_short_name,
            COALESCE(rep.name_patronymic, '') AS representative_name,
            COALESCE(rep.phone, '') AS representative_phone,
            COALESCE(rep.email, c.organization_email, '') AS email
        FROM clients c
        LEFT JOIN client_representatives rep
            ON rep.client_id = c.id
           AND rep.is_primary = TRUE
        WHERE c.id = %s
    """

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(query, (client_id,))
            row = cur.fetchone()

        if row is None:
            raise BackendError(f"Компания с id={client_id} не найдена.")

        return ClientPreview(
            client_id=int(row["client_id"]),
            company_full_name=str(row.get("company_full_name", "") or ""),
            company_short_name=str(row.get("company_short_name", "") or ""),
            representative_name=str(row.get("representative_name", "") or ""),
            representative_phone=str(row.get("representative_phone", "") or ""),
            email=str(row.get("email", "") or ""),
        )

    except DatabaseConnectionError as exc:
        raise BackendError(str(exc)) from exc
    except Error as exc:
        raise BackendError(f"Ошибка чтения компании: {exc}") from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_client_previews_by_ids(client_ids: list[int]) -> list[ClientPreview]:
    if not client_ids:
        return []

    query = """
        SELECT
            c.id AS client_id,
            c.company_full_name,
            c.company_short_name,
            COALESCE(rep.name_patronymic, '') AS representative_name,
            COALESCE(rep.phone, '') AS representative_phone,
            COALESCE(rep.email, c.organization_email, '') AS email
        FROM clients c
        LEFT JOIN client_representatives rep
            ON rep.client_id = c.id
           AND rep.is_primary = TRUE
        WHERE c.id = ANY(%s)
    """

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(query, (client_ids,))
            rows = cur.fetchall()

        rows_by_id = {int(row["client_id"]): row for row in rows}
        previews: list[ClientPreview] = []

        for client_id in client_ids:
            row = rows_by_id.get(int(client_id))
            if row is None:
                raise BackendError(f"Компания с id={client_id} не найдена.")

            previews.append(
                ClientPreview(
                    client_id=int(row["client_id"]),
                    company_full_name=str(row.get("company_full_name", "") or ""),
                    company_short_name=str(row.get("company_short_name", "") or ""),
                    representative_name=str(row.get("representative_name", "") or ""),
                    representative_phone=str(row.get("representative_phone", "") or ""),
                    email=str(row.get("email", "") or ""),
                )
            )

        return previews

    except DatabaseConnectionError as exc:
        raise BackendError(str(exc)) from exc
    except Error as exc:
        raise BackendError(f"Ошибка чтения компаний: {exc}") from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def list_contract_summaries() -> list[ContractSummary]:
    conn = None
    try:
        conn = get_connection()
        rows = list_contracts(conn)

        return [
            ContractSummary(
                contract_id=int(row["id"]),
                contract_number=str(row["contract_number"]),
                contract_date=_format_date(row.get("contract_date")),
                company_short_name=str(row.get("company_short_name", "") or ""),
                program_name=str(row.get("program_name", "") or ""),
                listeners_count=str(row.get("listeners_count", "")),
                total_price=_format_money(row.get("total_price")),
            )
            for row in rows
        ]

    except (DatabaseConnectionError, RepositoryError) as exc:
        raise BackendError(str(exc)) from exc
    except Exception as exc:
        raise BackendError(f"Ошибка загрузки списка договоров: {exc}") from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_contract_preview_by_id(contract_id: int) -> ContractPreview:
    conn = None
    try:
        conn = get_connection()
        bundle = fetch_contract_by_id(conn, contract_id)
        return _build_contract_preview_from_bundle(bundle)

    except (DatabaseConnectionError, RepositoryError) as exc:
        raise BackendError(str(exc)) from exc
    except Exception as exc:
        raise BackendError(f"Ошибка чтения договора: {exc}") from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_contract_previews_by_ids(contract_ids: list[int]) -> list[ContractPreview]:
    if not contract_ids:
        return []

    conn = None
    try:
        conn = get_connection()
        previews: list[ContractPreview] = []
        for contract_id in contract_ids:
            bundle = fetch_contract_by_id(conn, int(contract_id))
            previews.append(_build_contract_preview_from_bundle(bundle))
        return previews

    except (DatabaseConnectionError, RepositoryError) as exc:
        raise BackendError(str(exc)) from exc
    except Exception as exc:
        raise BackendError(f"Ошибка чтения договоров: {exc}") from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_contract_preview_by_number(contract_number: str) -> ContractPreview:
    conn = None
    try:
        conn = get_connection()
        bundle = fetch_contract_by_number(conn, contract_number)
        return _build_contract_preview_from_bundle(bundle)

    except (DatabaseConnectionError, RepositoryError) as exc:
        raise BackendError(str(exc)) from exc
    except Exception as exc:
        raise BackendError(f"Ошибка поиска договора: {exc}") from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _get_program_for_template(conn, template_key: str) -> dict[str, Any]:
    program_name = PROGRAM_NAME_BY_TEMPLATE.get(template_key)
    if not program_name:
        raise BackendError(
            f"Для шаблона '{template_key}' не настроена программа."
        )

    query = """
        SELECT
            id,
            program_name,
            training_start_date,
            training_end_date,
            program_hours,
            unit_price,
            reply_deadline
        FROM programs
        WHERE program_name = %s
        ORDER BY training_start_date DESC, id DESC
        LIMIT 1
    """

    with conn.cursor() as cur:
        cur.execute(query, (program_name,))
        row = cur.fetchone()

    if row is None:
        raise BackendError(
            f"Программа '{program_name}' для шаблона '{template_key}' не найдена в таблице programs."
        )

    return dict(row)


def _build_letter_bundle(conn, client_id: int, template_key: str) -> ContractBundle:
    client_query = """
        SELECT
            c.id AS client_id,
            c.company_full_name,
            c.company_short_name,
            c.ogrn,
            c.inn,
            c.kpp,
            c.bank_account,
            c.corr_account,
            c.bik,
            c.bank_name,
            c.payment_recipient,
            c.organization_email,

            addr.postal_code AS address_postal_code,
            addr.region AS address_region,
            addr.city AS address_city,
            addr.settlement AS address_settlement,
            addr.street AS address_street,
            addr.house AS address_house,
            addr.building AS address_building,
            addr.premises AS address_premises,

            rep.id AS representative_id,
            rep.short_fio_dative,
            rep.name_patronymic,
            rep.position_genitive,
            rep.full_name_genitive,
            rep.position_nominative,
            rep.initials,
            rep.basis,
            rep.email AS representative_email,
            rep.phone AS representative_phone
        FROM clients c
        LEFT JOIN client_addresses addr
            ON addr.client_id = c.id
        LEFT JOIN client_representatives rep
            ON rep.client_id = c.id
           AND rep.is_primary = TRUE
        WHERE c.id = %s
    """

    with conn.cursor() as cur:
        cur.execute(client_query, (client_id,))
        client_row = cur.fetchone()

    if client_row is None:
        raise BackendError(f"Компания с id={client_id} не найдена.")

    program = _get_program_for_template(conn, template_key)
    client = dict(client_row)

    contract_like = {
        "contract_id": None,
        "client_id": client["client_id"],
        "program_id": program["id"],
        "representative_id": client.get("representative_id"),
        "ikz": "",
        "contract_number": "",
        "contract_date": None,
        "contact_full_name": "",
        "contact_phone": "",
        "contact_email": client.get("representative_email")
        or client.get("organization_email")
        or "",
        "listeners_count": 0,
        "total_price": Decimal("0.00"),
        "notes": "",
        "company_full_name": client.get("company_full_name"),
        "company_short_name": client.get("company_short_name"),
        "ogrn": client.get("ogrn"),
        "inn": client.get("inn"),
        "kpp": client.get("kpp"),
        "bank_account": client.get("bank_account"),
        "corr_account": client.get("corr_account"),
        "bik": client.get("bik"),
        "bank_name": client.get("bank_name"),
        "payment_recipient": client.get("payment_recipient"),
        "organization_email": client.get("organization_email"),
        "address_postal_code": client.get("address_postal_code"),
        "address_region": client.get("address_region"),
        "address_city": client.get("address_city"),
        "address_settlement": client.get("address_settlement"),
        "address_street": client.get("address_street"),
        "address_house": client.get("address_house"),
        "address_building": client.get("address_building"),
        "address_premises": client.get("address_premises"),
        "program_name": program.get("program_name"),
        "training_start_date": program.get("training_start_date"),
        "training_end_date": program.get("training_end_date"),
        "program_hours": program.get("program_hours"),
        "unit_price": program.get("unit_price"),
        "reply_deadline": program.get("reply_deadline"),
        "short_fio_dative": client.get("short_fio_dative"),
        "name_patronymic": client.get("name_patronymic"),
        "position_genitive": client.get("position_genitive"),
        "full_name_genitive": client.get("full_name_genitive"),
        "position_nominative": client.get("position_nominative"),
        "initials": client.get("initials"),
        "basis": client.get("basis"),
        "representative_email": client.get("representative_email"),
        "representative_phone": client.get("representative_phone"),
    }

    return ContractBundle(contract=contract_like, students=[])


def generate_document_for_client(template_key: str, client_id: int) -> Path:
    documents = generate_documents_for_clients(template_key, [client_id])
    return documents[0].file_path


def generate_documents_for_clients(
    template_key: str,
    client_ids: list[int],
    actor: AuthUser | None = None,
) -> list[GeneratedDocument]:
    if template_key not in LETTER_TEMPLATE_KEYS:
        raise BackendError(
            "Для генерации по компании допустимы только шаблоны писем."
        )
    if not client_ids:
        raise BackendError("Не выбраны компании для генерации документов.")

    conn = None
    try:
        conn = get_connection()
        generated: list[GeneratedDocument] = []

        for client_id in client_ids:
            bundle = _build_letter_bundle(conn, int(client_id), template_key)
            output_path = render_document(bundle, template_key)
            subject, _ = _build_email_payload(template_key, bundle)
            document_id: int | None = None
            if actor is not None:
                document_id = save_generated_document_record(
                    actor=actor,
                    template_key=template_key,
                    document_type="letter",
                    file_path=output_path,
                    client_id=int(client_id),
                    contract_id=None,
                )
            generated.append(
                GeneratedDocument(
                    file_path=output_path,
                    to_email=str(bundle.contract.get("representative_email") or bundle.contract.get("organization_email") or ""),
                    subject=subject,
                    label=str(bundle.contract.get("company_full_name") or bundle.contract.get("company_short_name") or f"client_{client_id}"),
                    document_id=document_id,
                    client_id=int(client_id),
                    contract_id=None,
                    template_key=template_key,
                )
            )

        return generated

    except (DatabaseConnectionError, DocumentRenderError, HistoryServiceError) as exc:
        raise BackendError(str(exc)) from exc
    except Error as exc:
        raise BackendError(f"Ошибка генерации документа по компаниям: {exc}") from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def generate_document_for_contract(template_key: str, contract_id: int) -> Path:
    documents = generate_documents_for_contracts(template_key, [contract_id])
    return documents[0].file_path


def generate_documents_for_contracts(
    template_key: str,
    contract_ids: list[int],
    actor: AuthUser | None = None,
) -> list[GeneratedDocument]:
    if template_key not in CONTRACT_TEMPLATE_KEYS:
        raise BackendError(
            "Для генерации по договору допустим только шаблон договора."
        )
    if not contract_ids:
        raise BackendError("Не выбраны договоры для генерации документов.")

    conn = None
    try:
        conn = get_connection()
        generated: list[GeneratedDocument] = []

        for contract_id in contract_ids:
            bundle = fetch_contract_by_id(conn, int(contract_id))
            output_path = render_document(bundle, template_key)
            subject, _ = _build_email_payload(template_key, bundle)
            contract = bundle.contract
            document_id: int | None = None
            if actor is not None:
                document_id = save_generated_document_record(
                    actor=actor,
                    template_key=template_key,
                    document_type="contract",
                    file_path=output_path,
                    client_id=int(contract.get("client_id")) if contract.get("client_id") is not None else None,
                    contract_id=int(contract_id),
                )
            generated.append(
                GeneratedDocument(
                    file_path=output_path,
                    to_email=str(contract.get("contact_email") or ""),
                    subject=subject,
                    label=str(contract.get("contract_number") or f"contract_{contract_id}"),
                    document_id=document_id,
                    client_id=int(contract.get("client_id")) if contract.get("client_id") is not None else None,
                    contract_id=int(contract_id),
                    template_key=template_key,
                )
            )

        return generated

    except (
        DatabaseConnectionError,
        RepositoryError,
        DocumentRenderError,
        HistoryServiceError,
    ) as exc:
        raise BackendError(str(exc)) from exc
    except Exception as exc:
        raise BackendError(f"Ошибка генерации документа по договорам: {exc}") from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def send_document(
    file_path: Path,
    to_email: str,
    subject: str,
    body: str,
    cc: str | None = None,
    actor: AuthUser | None = None,
    document_id: int | None = None,
) -> None:
    if not file_path.exists():
        raise BackendError(f"Файл не найден: {file_path}")

    if not to_email:
        raise BackendError("Не указан email получателя.")

    dispatch_id: int | None = None
    try:
        if actor is not None and document_id is not None:
            dispatch_id = create_dispatch_record(
                actor=actor,
                document_id=document_id,
                recipient_email=get_development_recipient(),
                original_recipient_email=to_email,
                subject=subject,
            )

        send_document_email(
            document_path=file_path,
            to_email=to_email,
            subject=subject,
            body=body,
        )

        if dispatch_id is not None:
            set_dispatch_sent(dispatch_id)

    except MailerError as exc:
        if dispatch_id is not None:
            try:
                set_dispatch_failed(dispatch_id, str(exc))
            except HistoryServiceError:
                pass
        raise BackendError(str(exc)) from exc
    except HistoryServiceError as exc:
        raise BackendError(str(exc)) from exc
    except Exception as exc:
        if dispatch_id is not None:
            try:
                set_dispatch_failed(dispatch_id, str(exc))
            except HistoryServiceError:
                pass
        raise BackendError(f"Ошибка отправки письма: {exc}") from exc
