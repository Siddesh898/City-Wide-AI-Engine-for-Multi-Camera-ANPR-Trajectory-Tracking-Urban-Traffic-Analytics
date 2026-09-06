"""Shared DB helper for backend (M4) and analytics routes (M5)."""
import os
import psycopg2
import psycopg2.extras

DSN = os.getenv("PG_DSN", "host=localhost dbname=anpr user=anpr password=anpr")


def get_conn():
    conn = psycopg2.connect(DSN)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn
