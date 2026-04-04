import os
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

db_pool = psycopg2.pool.SimpleConnectionPool(
    1, 20,
    dsn=DATABASE_URL
)

def get_conn():
    return db_pool.getconn()

def put_conn(conn):
    db_pool.putconn(conn)