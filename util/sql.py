import sqlite3
import util.constants as const

def get_db():
    connection = sqlite3.connect(f'{const.DB_NAME}.db', check_same_thread=False)
    return connection


def execute_query(query, params=()):
    with get_db() as connection:
        cursor = connection.execute(query, params)
        result = cursor.fetchall()
        connection.commit()
    return result
