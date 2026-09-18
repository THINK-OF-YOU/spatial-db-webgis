"""通用 College 接口。

所有者：莫炜钧。契约见《任务执行书》§4.2 / §4.3 / §4.11。
"""

from fastapi import APIRouter, HTTPException, Query

from app.schemas.common import MAX_PAGE_SIZE, paginate
from app.services import college_service as svc
from app.services.spatial_service import (
    TRANSPORT_MODES,
    nearby_transport,
    transport_summary,
)

router = APIRouter(tags=["college"])


@router.get("/colleges")
def list_colleges(
    q: str | None = Query(None, description="按学校名称模糊搜索"),
    edu_level: str | None = Query(None, description="办学层次，如 本科 / 高职（专科）"),
    reg_province: str | None = Query(
        None,
        description="登记地区。注意：库里该字段装的是**市名**（如 长春市），不是省名。",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    items, total = svc.list_colleges(
        q=q,
        edu_level=edu_level,
        reg_province=reg_province,
        page=page,
        page_size=page_size,
    )
    return paginate(items, total, page, page_size)


@router.get("/colleges/{school_id}")
def get_college(school_id: int):
    college = svc.get_college(school_id)
    if college is None:
        raise HTTPException(status_code=404, detail=f"未找到 school_id={school_id} 的高校")

    return {
        "data": {
            "college": college,
            "campuses": svc.list_campuses_of(school_id),
            "data_availability": svc.college_availability(school_id),
        }
    }


@router.get("/colleges/{school_id}/transport")
def college_transport(
    school_id: int,
    radius_km: float = Query(3.0, gt=0, le=20, description="搜索半径（km），默认 3，上限 20"),
    mode: list[str] | None = Query(
        None, description=f"可重复传，只看这些类型。取值限于 {TRANSPORT_MODES}"
    ),
    limit: int = Query(20, ge=1, le=200),
):
    """指定高校周边的交通站点（铁路 / 地铁 / 机场）。

    以该校全部带几何的 Campus 为基准点，返回半径内的站点，
    距离是到**最近**那个校区 的直线距离（geom::geography 测地距离，对外给 km）。

    站点名以 OSM 原名 name 为准；name_zh 大量缺失（rail 33%、metro 43%），
    缺失时返回 null，不推算、不用别的值填充。

    数据来自 OpenStreetMap，**ODbL 许可**，界面与导出须署名
    © OpenStreetMap contributors。
    """
    # 不在库里、但契约写死的值一律 422 挡掉，免得前端传错值被静默忽略
    bad = sorted(set(mode or []) - set(TRANSPORT_MODES))
    if bad:
        raise HTTPException(
            status_code=422,
            detail=f"mode 只允许 {TRANSPORT_MODES}，收到非法值 {bad}",
        )

    items, warnings = nearby_transport(
        school_id=school_id,
        radius_km=radius_km,
        modes=mode,
        limit=limit,
    )

    return {
        "items": items,
        "total": len(items),
        "warnings": warnings,
    }


@router.get("/colleges/{school_id}/transport/summary")
def college_transport_summary(school_id: int):
    """高校最近交通设施事实摘要。

    metro / rail / airport 各自在有界范围内独立求最近点，距离均为交通设施
    坐标到最近 Campus 坐标的测地直线距离，不代表步行、驾车或通勤距离。
    """
    items, warnings = transport_summary(school_id)
    return {
        "school_id": school_id,
        "items": items,
        "warnings": warnings,
    }
