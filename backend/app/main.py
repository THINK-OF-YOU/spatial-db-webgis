"""FastAPI 入口。

所有者：莫炜钧。**其余三人不要改本文件**——路由已一次性注册好，
各自只改自己那个 router 文件。见 docs/00_协作规范.md §3 冲突点①。

启动：
    cd backend
    uvicorn app.main:app --reload --port 8000
    → http://127.0.0.1:8000/docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admissions, colleges, majors, map, meta, search, spatial
from app.config import settings
from app.db.pool import close_pool, get_cursor, init_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_pool()
    logger.info("启动完成，数据库 %s（只读）", settings.pg_database)
    yield
    close_pool()


app = FastAPI(
    title="高校志愿填报空间查询原型 V1",
    description=(
        "PostgreSQL / PostGIS → FastAPI。\n\n"
        "**全程只读**，不修改任何业务数据。\n\n"
        "坐标统一 WGS84 / EPSG:4326，GeoJSON 坐标顺序 `[lon, lat]`。"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由注册 ────────────────────────────────────────────────────────
# 谁的文件谁实现，不要来这里加路由。
# API 10（周边交通）挂在 colleges.router 上，所以这里没有新增一行。
# API 11/12/13（专业）是 2026-09-17 数据库恢复专业语义链之后新增的，
# 单独一个 majors.router —— 原计划 10 个接口，现在是 14 个。
API_PREFIX = "/api"

app.include_router(colleges.router, prefix=API_PREFIX)   # 莫炜钧  1, 2, 10
app.include_router(map.router, prefix=API_PREFIX)        # 莫炜钧  5, 6
app.include_router(spatial.router, prefix=API_PREFIX)    # 莫炜钧  7, 8
app.include_router(search.router, prefix=API_PREFIX)     # 莫炜钧  9（总集成）
app.include_router(majors.router, prefix=API_PREFIX)     # 莫炜钧  11, 12, 13
app.include_router(meta.router, prefix=API_PREFIX)       # 倪嵩    4
app.include_router(admissions.router, prefix=API_PREFIX) # 倪嵩    3


@app.get("/api/health", tags=["meta"])
def health():
    """连通性自检。返回真实库名与三个关键表的行数。"""
    with get_cursor() as cur:
        cur.execute(
            """
            select current_database() as database,
                   (select count(*) from college)         as college,
                   (select count(*) from campus)          as campus,
                   (select count(*) from poi_transport)   as poi_transport
            """
        )
        row = dict(cur.fetchone())

    return {
        "data": {
            "status": "ok",
            "database": row["database"],
            "read_only": True,
            "counts": {
                "college": row["college"],
                "campus": row["campus"],
                "poi_transport": row["poi_transport"],
            },
        }
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底异常处理。

    沿用 FastAPI 的 {"detail": "..."} 形状，但**不把数据库内部错误原样吐给前端**。
    """
    logger.exception("未处理异常 %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请查看后端日志"},
    )
