"""公共响应信封。

契约见《任务执行书》§4.1：
    分页列表  {"items": [], "total": 0, "page": 1, "page_size": 20, "warnings": []}
    单对象    {"data": {}}
    错误      沿用 FastAPI 的 {"detail": "..."}

字段一律 snake_case，API ↔ 前端不做二次映射。
"""

from typing import Any

from pydantic import BaseModel, Field

MAX_PAGE_SIZE = 100


class Page(BaseModel):
    """分页列表信封。"""

    items: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    warnings: list[str] = Field(default_factory=list)


class Single(BaseModel):
    """单对象信封。"""

    data: Any = None


def paginate(
    items: list[Any],
    total: int,
    page: int,
    page_size: int,
    warnings: list[str] | None = None,
) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "warnings": warnings or [],
    }


def offset_of(page: int, page_size: int) -> int:
    return max(page - 1, 0) * page_size


def feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def point_feature(lon: float, lat: float, properties: dict) -> dict:
    """构造一个 Point Feature。

    ⚠️ GeoJSON 坐标顺序固定 [longitude, latitude]，不是 [lat, lon]。
       见 docs/00_协作规范.md §1.2。
    """
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties,
    }
