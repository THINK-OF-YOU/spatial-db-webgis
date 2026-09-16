"""空间查询接口：参考点半径、自定义 Polygon。

所有者：莫炜钧。契约见《任务执行书》§4.8 / §4.9。

距离一律米制测地距离（geom::geography），对外返回 km。
"""

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services import spatial_service as svc

router = APIRouter(tags=["spatial"])


@router.get("/spatial/nearby")
def nearby(
    lon: float = Query(..., ge=-180, le=180, description="参考点经度"),
    lat: float = Query(..., ge=-90, le=90, description="参考点纬度"),
    radius_km: float = Query(..., gt=0, le=2000, description="半径（公里）"),
    verify_status: list[str] | None = Query(
        None,
        description="不传则**只用 CONFIRMED**（§3.3 冻结口径）。要含候选点显式传 CONFIRMED 和 CANDIDATE。",
    ),
    limit: int = Query(20, ge=1, le=200),
):
    """参考点 + 半径内的校区。

    ⚠️ 默认只查 CONFIRMED。当前全库只有 4 个 CONFIRMED 校区，
       所以不传 verify_status 时结果很可能为空——这不是 bug。
       前端要提供"包含候选校区"开关，用户主动开启后才传 CANDIDATE。
    """
    items, warnings = svc.nearby(
        lon=lon,
        lat=lat,
        radius_km=radius_km,
        verify_status=verify_status,
        limit=limit,
    )
    return {"items": items, "warnings": warnings}


class WithinRequest(BaseModel):
    geometry: dict[str, Any] = Field(..., description="GeoJSON Polygon")
    verify_status: list[str] | None = Field(
        None, description="不传则只用 CONFIRMED"
    )


@router.post("/spatial/within")
def within(req: WithinRequest):
    """GeoJSON Polygon 内的校区。

    边界语义固定 **ST_Within**（点在面内），全接口只用这一个语义。
    """
    geom_type = (req.geometry or {}).get("type")
    if geom_type not in ("Polygon", "MultiPolygon"):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=f"geometry.type 只支持 Polygon / MultiPolygon，收到 {geom_type!r}",
        )

    items, warnings = svc.within(req.geometry, verify_status=req.verify_status)
    return {"items": items, "total": len(items), "warnings": warnings}
