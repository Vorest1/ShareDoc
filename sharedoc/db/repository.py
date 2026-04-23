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
            ct.representative_id,
            ct.ikz,
            ct.contract_number,
            ct.contract_date,
            ct.contact_full_name,
            ct.contact_phone,
            ct.contact_email,
            ct.listeners_count,
            ct.total_price,
            ct.notes,

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

            p.program_name,
            p.training_start_date,
            p.training_end_date,
            p.program_hours,
            p.unit_price,
            p.reply_deadline,

            COALESCE(rep_explicit.short_fio_dative, rep_primary.short_fio_dative) AS short_fio_dative,
            COALESCE(rep_explicit.name_patronymic, rep_primary.name_patronymic) AS name_patronymic,
            COALESCE(rep_explicit.position_genitive, rep_primary.position_genitive) AS position_genitive,
            COALESCE(rep_explicit.full_name_genitive, rep_primary.full_name_genitive) AS full_name_genitive,
            COALESCE(rep_explicit.position_nominative, rep_primary.position_nominative) AS position_nominative,
            COALESCE(rep_explicit.initials, rep_primary.initials) AS initials,
            COALESCE(rep_explicit.basis, rep_primary.basis) AS basis,
            COALESCE(rep_explicit.email, rep_primary.email) AS representative_email,
            COALESCE(rep_explicit.phone, rep_primary.phone) AS representative_phone
        FROM contracts ct
        JOIN clients c
            ON c.id = ct.client_id
        JOIN programs p
            ON p.id = ct.program_id
        LEFT JOIN client_addresses addr
            ON addr.client_id = c.id
        LEFT JOIN client_representatives rep_explicit
            ON rep_explicit.id = ct.representative_id
        LEFT JOIN client_representatives rep_primary
            ON rep_primary.client_id = c.id
           AND rep_primary.is_primary = TRUE
           AND ct.representative_id IS NULL
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