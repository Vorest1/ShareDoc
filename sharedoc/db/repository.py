from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg2 import Error


class RepositoryError(Exception):
    """Ошибка чтения данных из БД."""


@dataclass(frozen=True)
class ContractBundle:
    contract: dict[str, Any]
    students: list[dict[str, Any]]


def fetch_contract_by_id(conn, contract_id: int) -> ContractBundle:
    contract_query = """
        SELECT
            ct.id AS contract_id,
            ct.client_id,
            ct.program_id,
            ct.ikz,
            ct.contract_number,
            ct.contract_date,
            ct.company_contact_full_name,
            ct.company_contact_phone,
            ct.company_contact_email,
            ct.listeners_count,
            ct.total_price,
            ct.reply_deadline,

            c.company_full_name,
            c.company_short_name,
            c.company_legal_address,
            c.company_postal_address,
            c.company_mailing_address,
            c.company_ogrn,
            c.company_inn,
            c.company_kpp,
            c.company_bank_account,
            c.company_corr_account,
            c.company_bik,
            c.company_bank_name,
            c.company_payment_recipient,
            c.representative_short_fio_dative,
            c.representative_email,
            c.representative_name_patronymic,
            c.representative_position_genitive,
            c.representative_full_name_genitive,
            c.representative_position_nominative,
            c.representative_initials,
            c.representative_basis,

            p.program_name,
            p.training_start_date,
            p.training_end_date,
            p.program_hours,
            p.unit_price
        FROM contracts ct
        JOIN clients c ON c.id = ct.client_id
        JOIN programs p ON p.id = ct.program_id
        WHERE ct.id = %s
    """

    students_query = """
        SELECT
            row_no,
            full_name,
            phone,
            email
        FROM contract_students
        WHERE contract_id = %s
        ORDER BY row_no
    """

    try:
        with conn.cursor() as cur:
            cur.execute(contract_query, (contract_id,))
            contract_row = cur.fetchone()

            if contract_row is None:
                raise RepositoryError(f"Договор с id={contract_id} не найден.")

            cur.execute(students_query, (contract_id,))
            student_rows = cur.fetchall()

        return ContractBundle(
            contract=dict(contract_row),
            students=[dict(row) for row in student_rows],
        )

    except RepositoryError:
        raise
    except Error as exc:
        raise RepositoryError(f"Ошибка чтения договора из БД: {exc}") from exc


def fetch_contract_by_number(conn, contract_number: str) -> ContractBundle:
    query = """
        SELECT id
        FROM contracts
        WHERE contract_number = %s
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query, (contract_number,))
            row = cur.fetchone()

            if row is None:
                raise RepositoryError(
                    f"Договор с номером '{contract_number}' не найден."
                )

        return fetch_contract_by_id(conn, int(row["id"]))

    except RepositoryError:
        raise
    except Error as exc:
        raise RepositoryError(f"Ошибка поиска договора по номеру: {exc}") from exc


def list_contracts(conn) -> list[dict[str, Any]]:
    query = """
        SELECT
            ct.id,
            ct.contract_number,
            ct.contract_date,
            c.company_short_name,
            p.program_name,
            ct.listeners_count,
            ct.total_price
        FROM contracts ct
        JOIN clients c ON c.id = ct.client_id
        JOIN programs p ON p.id = ct.program_id
        ORDER BY ct.id
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

        return [dict(row) for row in rows]

    except Error as exc:
        raise RepositoryError(f"Ошибка чтения списка договоров: {exc}") from exc