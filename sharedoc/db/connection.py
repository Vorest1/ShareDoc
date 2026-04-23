from __future__ import annotations

import psycopg2
from psycopg2 import OperationalError           # обработка ошибок подключения
from psycopg2.extras import RealDictCursor      # возвращение строк в виде словаря ( название поля, значение поля), а не списка (значение поля1, значение поля2, ...)
                                                #  а не списка (значение поля1, значение поля2, ...)
from sharedoc.config import DB


class DatabaseConnectionError(Exception):
    """Ошибка подключения к PostgreSQL."""


def get_connection():
    try:
        conn = psycopg2.connect(
            host=DB.host,
            port=DB.port,
            dbname=DB.dbname,
            user=DB.user,
            password=DB.password,
            cursor_factory=RealDictCursor,
        )

        with conn.cursor() as cur:      # проверка успешного подключения к БД
            cur.execute("SELECT 1")
            cur.fetchone()

        return conn

    except OperationalError as exc:
        raise DatabaseConnectionError(
            "Не удалось подключиться к PostgreSQL. "
            "Проверьте параметры подключения в config.py / .env: "
            f"host={DB.host}, port={DB.port}, dbname={DB.dbname}, user={DB.user}. "
            f"Текст ошибки: {exc}"
        ) from exc