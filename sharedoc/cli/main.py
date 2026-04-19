from __future__ import annotations

import argparse
import sys
from typing import Any

from ..db.connection import DatabaseConnectionError, get_connection
from ..db.repository import (
    RepositoryError,
    fetch_contract_by_id,
    fetch_contract_by_number,
    list_contracts,
)
from ..documents.context_builder import format_date_contract, format_money
from ..documents.renderer import DocumentRenderError, render_document
from ..mail.mailer import MailerError, send_document_email


def fatal(message: str, exit_code: int = 1) -> None:
    print(f"Ошибка: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def print_contracts(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("В таблице contracts нет записей.")
        return

    for row in rows:
        print(
            f"[{row['id']}] "
            f"№ {row['contract_number']} | "
            f"{format_date_contract(row['contract_date'])} | "
            f"{row['company_short_name']} | "
            f"{row['program_name']} | "
            f"слушателей: {row['listeners_count']} | "
            f"сумма: {format_money(row['total_price'])}"
        )


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Генерация документов из существующей PostgreSQL БД через docxtpl"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-contracts", help="Показать договоры из БД")

    render_parser = subparsers.add_parser("render", help="Сгенерировать документ")
    render_parser.add_argument(
        "--template",
        required=True,
        choices=["scientific_guidance", "qualification", "contract_offer"],
        help="Какой шаблон использовать",
    )

    group = render_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--contract-id", type=int, help="ID договора")
    group.add_argument("--contract-number", help="Номер договора")

    render_parser.add_argument(
        "--send-email",
        action="store_true",
        help="После генерации отправить документ на тестовую почту разработчика",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    conn = None

    try:
        conn = get_connection()

        if args.command == "list-contracts":
            rows = list_contracts(conn)
            print_contracts(rows)
            return

        if args.command == "render":
            if args.contract_id is not None:
                bundle = fetch_contract_by_id(conn, args.contract_id)
            else:
                bundle = fetch_contract_by_number(conn, args.contract_number)

            try:
                output_path = render_document(bundle, args.template)
            except DocumentRenderError as exc:
                fatal(str(exc))

            print(f"Документ успешно сформирован: {output_path}")

            if args.send_email:
                subject, body = build_email_payload(args.template, bundle)

                try:
                    send_document_email(
                        document_path=output_path,
                        subject=subject,
                        body=body,
                    )
                except MailerError as exc:
                    fatal(f"Документ сформирован, но письмо не отправлено: {exc}")

                print("Документ успешно отправлен на тестовую почту разработчика.")

            return

        fatal("Неизвестная команда.")

    except DatabaseConnectionError as exc:
        fatal(str(exc))
    except RepositoryError as exc:
        fatal(str(exc))
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()