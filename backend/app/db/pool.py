"""数据库连接池。

V1 全程只读。这里的只读不是"约定"，是**服务端强制**的：
连接参数带 default_transaction_read_only=on，任何 INSERT/UPDATE/DELETE
都会直接被 PostgreSQL 拒绝。见 docs/00_协作规范.md §1.1。
"""

import logging
from contextlib import contextmanager

from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from app.config import settings

logger = logging.getLogger(__name__)

_pool: ThreadedConnectionPool | None = None


def init_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        settings.validate_database()
        _pool = ThreadedConnectionPool(
            settings.pg_pool_min,
            settings.pg_pool_max,
            **settings.connect_kwargs,
        )
        logger.info(
            "数据库连接池已建立：%s@%s:%s/%s（只读）",
            settings.pg_user,
            settings.pg_host,
            settings.pg_port,
            settings.pg_database,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("数据库连接池已关闭")


@contextmanager
def get_cursor():
    """借一个字典游标。

    退出时**一律 rollback，永不 commit** —— 本应用没有写操作。
    """
    pool = init_pool()
    conn = pool.getconn()
    try:
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)
