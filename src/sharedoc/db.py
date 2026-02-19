import psycopg2
from psycopg2.extras import RealDictCursor
from sharedoc.config import DB


def get_contract_data(contract_id: int) -> dict:
    conn = psycopg2.connect(
        host=DB.host,
        database=DB.dbname,
        user=DB.user,
        password=DB.password,
        port=DB.port,
    )

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    c.contract_id,
                    c.number AS contract_number,
                    c.date,
                    o.name  AS client_name,
                    o.address
                FROM contract c
                JOIN organization o ON o.organization_id = c.organization_id
                WHERE c.contract_id = %s
                """,
                (contract_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Contract not found: contract_id={contract_id}")
            return dict(row)
    finally:
        conn.close()
