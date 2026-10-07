"""Create online feedback tables for an existing installation (idempotent)."""
import sys
from pathlib import Path
import pymysql
from dotenv import dotenv_values
root=Path(__file__).resolve().parents[1]
env=dotenv_values(root/'services/gateway/.env')
connection=pymysql.connect(host=env['MYSQL_HOST'],port=int(env['MYSQL_PORT']),user=env['MYSQL_USER'],
                          password=env['MYSQL_PASSWORD'],database=env['MYSQL_DB'],charset='utf8mb4')
# The SQL creates three new tables; no existing data is modified.
try:
    with connection.cursor() as cursor:
        for statement in (root/'infrastructure/mysql/05-online-feedback.sql').read_text().split(';'):
            statement=statement.strip()
            if statement and not statement.startswith('USE '): cursor.execute(statement)
    connection.commit()
    print('Online feedback tables ready')
finally:
    connection.close()
