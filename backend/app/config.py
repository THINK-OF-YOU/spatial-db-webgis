"""配置读取。

只从环境变量 / backend/.env 读，**不硬编码任何凭据**。
.env 已在 .gitignore 里，不会进仓库。
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

# 只允许连这一个库。见 docs/00_协作规范.md §1.1。
REQUIRED_DATABASE = "gaokao3"

# 明令禁止连接的库：gaokao 是已冻结的历史库，任何连接都不允许。
FORBIDDEN_DATABASES = {"gaokao"}


class Settings:
    pg_host: str = os.getenv("PGHOST", "127.0.0.1")
    pg_port: int = int(os.getenv("PGPORT", "5432"))
    pg_database: str = os.getenv("PGDATABASE", REQUIRED_DATABASE)
    pg_user: str = os.getenv("PGUSER", "postgres")
    pg_password: str = os.getenv("PGPASSWORD", "")

    pg_pool_min: int = int(os.getenv("PG_POOL_MIN", "1"))
    pg_pool_max: int = int(os.getenv("PG_POOL_MAX", "8"))

    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if o.strip()
    ]

    @property
    def connect_kwargs(self) -> dict:
        """psycopg2.connect 的参数。

        `options` 里的 default_transaction_read_only=on 是**服务端强制**的只读
        保证——不是说好了只读，是这个连接根本写不了。见协作规范 §1.1。
        """
        kw = {
            "host": self.pg_host,
            "port": self.pg_port,
            "dbname": self.pg_database,
            "user": self.pg_user,
            "application_name": "gaokao-v1-api",
            "options": "-c default_transaction_read_only=on",
        }
        if self.pg_password:
            kw["password"] = self.pg_password
        return kw

    def validate_database(self) -> None:
        """启动时校验库名。连错库直接拒绝启动，不要等查到错数据才发现。"""
        db = (self.pg_database or "").strip()
        if db in FORBIDDEN_DATABASES:
            raise RuntimeError(
                f"拒绝连接数据库 {db!r}：这是已冻结的历史库，全程不得触碰。"
                f" 请把 PGDATABASE 设为 {REQUIRED_DATABASE}。"
            )
        if db != REQUIRED_DATABASE:
            logger.warning(
                "PGDATABASE=%r 不是 %r。V1 只验证过 %r，换库请自行确认表结构与数据范围。",
                db,
                REQUIRED_DATABASE,
                REQUIRED_DATABASE,
            )


settings = Settings()
