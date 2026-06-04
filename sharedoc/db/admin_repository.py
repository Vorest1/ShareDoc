from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg2 import Error
from psycopg2 import sql


class AdminRepositoryError(Exception):
    """Ошибка административного CRUD-доступа к данным."""


@dataclass(frozen=True)
class AdminEntityConfig:
    table: str
    pk: str
    columns: tuple[str, ...]
    readonly_columns: tuple[str, ...] = ("id", "created_at", "updated_at")
    order_by: str = "id"

    @property
    def editable_columns(self) -> tuple[str, ...]:
        blocked = set(self.readonly_columns)
        return tuple(column for column in self.columns if column not in blocked)


ADMIN_ENTITIES: dict[str, AdminEntityConfig] = {
    "clients": AdminEntityConfig(
        table="clients",
        pk="id",
        columns=(
            "id",
            "company_full_name",
            "company_short_name",
            "ogrn",
            "inn",
            "kpp",
            "bank_account",
            "corr_account",
            "bik",
            "bank_name",
            "payment_recipient",
            "organization_email",
            "created_at",
            "updated_at",
        ),
        order_by="company_short_name",
    ),
    "client_representatives": AdminEntityConfig(
        table="client_representatives",
        pk="id",
        columns=(
            "id",
            "client_id",
            "short_fio_dative",
            "name_patronymic",
            "position_genitive",
            "full_name_genitive",
            "position_nominative",
            "initials",
            "basis",
            "email",
            "phone",
            "is_primary",
            "created_at",
            "updated_at",
        ),
        order_by="id",
    ),
    "client_addresses": AdminEntityConfig(
        table="client_addresses",
        pk="id",
        columns=(
            "id",
            "client_id",
            "postal_code",
            "region",
            "city",
            "settlement",
            "street",
            "house",
            "building",
            "premises",
            "created_at",
            "updated_at",
        ),
        order_by="id",
    ),
    "programs": AdminEntityConfig(
        table="programs",
        pk="id",
        columns=(
            "id",
            "program_name",
            "training_start_date",
            "training_end_date",
            "program_hours",
            "unit_price",
            "reply_deadline",
            "created_at",
            "updated_at",
        ),
        order_by="training_start_date",
    ),
    "contracts": AdminEntityConfig(
        table="contracts",
        pk="id",
        columns=(
            "id",
            "client_id",
            "program_id",
            "representative_id",
            "ikz",
            "contract_number",
            "contract_date",
            "contact_full_name",
            "contact_phone",
            "contact_email",
            "listeners_count",
            "total_price",
            "notes",
            "created_at",
            "updated_at",
        ),
        order_by="id",
    ),
    "contract_students": AdminEntityConfig(
        table="contract_students",
        pk="id",
        columns=(
            "id",
            "contract_id",
            "row_no",
            "full_name",
            "phone",
            "email",
            "created_at",
        ),
        readonly_columns=("id", "created_at"),
        order_by="contract_id",
    ),
    "generated_documents": AdminEntityConfig(
        table="generated_documents",
        pk="id",
        columns=(
            "id",
            "template_key",
            "document_type",
            "client_id",
            "contract_id",
            "created_by",
            "file_name",
            "file_path",
            "file_hash",
            "created_at",
        ),
        readonly_columns=("id", "created_at"),
        order_by="created_at",
    ),
    "document_dispatches": AdminEntityConfig(
        table="document_dispatches",
        pk="id",
        columns=(
            "id",
            "document_id",
            "sent_by",
            "recipient_email",
            "original_recipient_email",
            "subject",
            "status",
            "created_at",
            "sent_at",
            "error_message",
        ),
        readonly_columns=("id", "created_at", "sent_at"),
        order_by="created_at",
    ),
}


def get_entity_config(entity: str) -> AdminEntityConfig:
    config = ADMIN_ENTITIES.get(entity)
    if config is None:
        raise AdminRepositoryError(f"Сущность '{entity}' не разрешена для CRUD-доступа.")
    return config


def list_admin_entities() -> list[dict[str, Any]]:
    return [
        {
            "entity": entity,
            "table": config.table,
            "pk": config.pk,
            "columns": list(config.columns),
            "editable_columns": list(config.editable_columns),
        }
        for entity, config in ADMIN_ENTITIES.items()
    ]


def _validate_columns(config: AdminEntityConfig, data: dict[str, Any]) -> dict[str, Any]:
    allowed = set(config.editable_columns)
    invalid = sorted(set(data) - allowed)
    if invalid:
        raise AdminRepositoryError(
            "Недопустимые поля для изменения: " + ", ".join(invalid)
        )
    return {key: value for key, value in data.items() if key in allowed}


def list_rows(
    conn,
    entity: str,
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
) -> list[dict[str, Any]]:
    config = get_entity_config(entity)
    params: list[Any] = []
    where_sql = sql.SQL("")

    if search:
        text_columns = [
            column for column in config.columns
            if column not in {config.pk, "created_at", "updated_at"}
        ]
        conditions = [
            sql.SQL("CAST({column} AS TEXT) ILIKE %s").format(
                column=sql.Identifier(column)
            )
            for column in text_columns
        ]
        where_sql = sql.SQL("WHERE ") + sql.SQL(" OR ").join(conditions)
        params.extend([f"%{search}%"] * len(text_columns))

    query = sql.SQL("""
        SELECT {columns}
        FROM {table}
        {where_sql}
        ORDER BY {order_by} DESC
        LIMIT %s OFFSET %s
    """).format(
        columns=sql.SQL(", ").join(sql.Identifier(column) for column in config.columns),
        table=sql.Identifier(config.table),
        where_sql=where_sql,
        order_by=sql.Identifier(config.order_by),
    )
    params.extend([limit, offset])

    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [dict(row) for row in rows]
    except Error as exc:
        raise AdminRepositoryError(f"Ошибка чтения таблицы {config.table}: {exc}") from exc


def get_row(conn, entity: str, row_id: int) -> dict[str, Any]:
    config = get_entity_config(entity)
    query = sql.SQL("""
        SELECT {columns}
        FROM {table}
        WHERE {pk} = %s
    """).format(
        columns=sql.SQL(", ").join(sql.Identifier(column) for column in config.columns),
        table=sql.Identifier(config.table),
        pk=sql.Identifier(config.pk),
    )

    try:
        with conn.cursor() as cur:
            cur.execute(query, (row_id,))
            row = cur.fetchone()
        if row is None:
            raise AdminRepositoryError(f"Запись id={row_id} не найдена в {config.table}.")
        return dict(row)
    except AdminRepositoryError:
        raise
    except Error as exc:
        raise AdminRepositoryError(f"Ошибка чтения записи {config.table}: {exc}") from exc


def create_row(conn, entity: str, data: dict[str, Any]) -> int:
    config = get_entity_config(entity)
    cleaned = _validate_columns(config, data)
    if not cleaned:
        raise AdminRepositoryError("Нет данных для создания записи.")

    columns = list(cleaned.keys())
    values = [cleaned[column] for column in columns]

    query = sql.SQL("""
        INSERT INTO {table} ({columns})
        VALUES ({placeholders})
        RETURNING {pk}
    """).format(
        table=sql.Identifier(config.table),
        columns=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        placeholders=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        pk=sql.Identifier(config.pk),
    )

    try:
        with conn.cursor() as cur:
            cur.execute(query, values)
            row = cur.fetchone()
        return int(row[config.pk])
    except Error as exc:
        raise AdminRepositoryError(f"Ошибка создания записи {config.table}: {exc}") from exc


def update_row(conn, entity: str, row_id: int, data: dict[str, Any]) -> None:
    config = get_entity_config(entity)
    cleaned = _validate_columns(config, data)
    if not cleaned:
        raise AdminRepositoryError("Нет данных для изменения записи.")

    columns = list(cleaned.keys())
    values = [cleaned[column] for column in columns]
    values.append(row_id)

    query = sql.SQL("""
        UPDATE {table}
        SET {assignments}
        WHERE {pk} = %s
    """).format(
        table=sql.Identifier(config.table),
        assignments=sql.SQL(", ").join(
            sql.SQL("{column} = %s").format(column=sql.Identifier(column))
            for column in columns
        ),
        pk=sql.Identifier(config.pk),
    )

    try:
        with conn.cursor() as cur:
            cur.execute(query, values)
            if cur.rowcount == 0:
                raise AdminRepositoryError(f"Запись id={row_id} не найдена в {config.table}.")
    except AdminRepositoryError:
        raise
    except Error as exc:
        raise AdminRepositoryError(f"Ошибка изменения записи {config.table}: {exc}") from exc


def delete_row(conn, entity: str, row_id: int) -> None:
    config = get_entity_config(entity)
    query = sql.SQL("""
        DELETE FROM {table}
        WHERE {pk} = %s
    """).format(
        table=sql.Identifier(config.table),
        pk=sql.Identifier(config.pk),
    )

    try:
        with conn.cursor() as cur:
            cur.execute(query, (row_id,))
            if cur.rowcount == 0:
                raise AdminRepositoryError(f"Запись id={row_id} не найдена в {config.table}.")
    except AdminRepositoryError:
        raise
    except Error as exc:
        raise AdminRepositoryError(f"Ошибка удаления записи {config.table}: {exc}") from exc
