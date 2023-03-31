import sqlite3

DB_NAME = 'z5364199'


def get_db():
    connection = sqlite3.connect(f'{DB_NAME}.db', check_same_thread=False)
    return connection


def execute_query(query, params=()):
    with get_db() as connection:
        cursor = connection.execute(query, params)
        result = cursor.fetchall()
        connection.commit()
    return result
