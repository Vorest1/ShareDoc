from __future__ import annotations

import getpass
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from sharedoc.db.auth_repository import create_user
from sharedoc.db.connection import get_connection


def main() -> None:
    username = input("Логин администратора: ").strip()
    full_name = input("ФИО администратора: ").strip()
    email = input("Email администратора: ").strip() or None

    password = getpass.getpass("Пароль администратора: ")
    password_repeat = getpass.getpass("Повторите пароль: ")

    if password != password_repeat:
        raise SystemExit("Пароли не совпадают.")

    conn = None

    try:
        conn = get_connection()

        user_id = create_user(
            conn,
            username=username,
            password=password,
            full_name=full_name,
            email=email,
            role_code="admin",
        )

        conn.commit()
        print(f"Администратор создан, id={user_id}")

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()