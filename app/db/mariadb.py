"""MariaDB connection pool for AD user & group management.

Uses DBUtils PooledDB for connection pooling (reuse connections, no TCP handshake per query).
Fallback to direct pymysql if DBUtils not available.
"""
import pymysql
from dbutils.pooled_db import PooledDB
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

_pool = None


def _get_pool() -> PooledDB:
    """Get or create connection pool (singleton)."""
    global _pool
    if _pool is None:
        s = get_settings()
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=10,
            mincached=2,
            maxcached=5,
            blocking=True,
            host=s.mariadb_host,
            port=int(s.mariadb_port),
            user=s.mariadb_user,
            password=s.mariadb_password,
            database=s.mariadb_database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
        logger.info("mariadb_pool_initialized", max=10, cached=2)
    return _pool


def get_maria_conn():
    """Get a pooled MariaDB connection."""
    return _get_pool().connection()


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    """Execute SELECT and return all rows."""
    conn = get_maria_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    """Execute SELECT and return one row."""
    conn = get_maria_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()


def execute(sql: str, params: tuple = ()) -> int:
    """Execute INSERT/UPDATE/DELETE and return affected rows."""
    conn = get_maria_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount
    finally:
        conn.close()


def execute_lastid(sql: str, params: tuple = ()) -> int:
    """Execute INSERT and return last insert ID."""
    conn = get_maria_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()
