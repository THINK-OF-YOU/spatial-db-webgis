"""地图接口：Campus 与 AdminRegion 的 GeoJSON。

所有者：莫炜钧。契约见《任务执行书》§4.6 / §4.7。

⚠️ GeoJSON 坐标顺序固定 [longitude, latitude]。
"""

from fastapi import APIRouter, HTTPException, Query

from app.db.pool import get_cursor
from app.schemas.common import feature_collection, point_feature

router = APIRouter(tags=["map"])

_VALID_STATUSES = {"CONFIRMED", "CANDIDATE"}
_VALID_LEVELS = {"province", "city", "district"}


@router.get("/map/campuses")
def map_campuses(
    verify_status: list[str] | None = Query(
        None, description="可重复传。不传则 CONFIRMED 与 CANDIDATE 都返回。"
    ),
    bbox: str | None = Query(
        None,
        description="min_lon,min_lat,max_lon,max_lat，用于按当前视野裁剪",
    ),
    school_ids: list[int] | None = Query(None, description="可重复传，只看这些学校"),
):
    """Campus 点位 GeoJSON。

    地图浏览允许 CONFIRMED 与 CANDIDATE 同时显示（§3.3），
    但 properties 里必须带 verify_status，前端要分样式渲染。
    """
    params: dict = {}
    where = ["cp.geom is not null"]

    if verify_status:
        bad = set(verify_status) - _VALID_STATUSES
        if bad:
            raise HTTPException(
                status_code=422,
                detail=f"verify_status 只允许 {sorted(_VALID_STATUSES)}，收到非法值 {sorted(bad)}",
            )
        where.append("cp.verify_status = any(%(statuses)s)")
        params["statuses"] = verify_status

    if school_ids:
        where.append("cp.school_id = any(%(school_ids)s)")
        params["school_ids"] = school_ids

    if bbox:
        try:
            min_lon, min_lat, max_lon, max_lat = (float(v) for v in bbox.split(","))
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="bbox 格式应为 min_lon,min_lat,max_lon,max_lat",
            )
        where.append(
            "cp.geom && st_makeenvelope(%(min_lon)s, %(min_lat)s,"
            " %(max_lon)s, %(max_lat)s, 4326)"
        )
        params.update(
            min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat
        )

    sql = f"""
        select cp.campus_id,
               cp.school_id,
               c.std_name  as school_name,
               cp.campus_name,
               cp.verify_status,
               st_x(cp.geom) as lon,
               st_y(cp.geom) as lat
        from campus cp
        join college c on c.school_id = cp.school_id
        where {' and '.join(where)}
        order by cp.campus_id
    """

    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    # properties 只保留契约里的 5 个字段，内部列不外泄
    features = [
        point_feature(
            r["lon"],
            r["lat"],
            {
                "campus_id": r["campus_id"],
                "school_id": r["school_id"],
                "school_name": r["school_name"],
                "campus_name": r["campus_name"],
                "verify_status": r["verify_status"],
            },
        )
        for r in rows
    ]
    return feature_collection(features)


@router.get("/map/regions")
def map_regions(
    level: str | None = Query(
        None, description="province / city / district。不传默认只返回 province，避免一次性传全国几何。"
    ),
    parent_adcode: str | None = Query(None, description="返回该行政区的下一级"),
    simplify: float = Query(
        0.0,
        ge=0.0,
        description="简化容差（度）。0=不简化。0.01 约等于 1km，能显著减小体积。",
    ),
):
    """行政区 GeoJSON，用于地图高亮和地域选择。

    契约 §4.7 明确"不要求一次性传全国所有几何"。所以不传 level 时
    只给 province（34 个），要市级必须显式传 level=city 或 parent_adcode。
    """
    params: dict = {}
    where = ["geom is not null"]

    if level:
        if level not in _VALID_LEVELS:
            raise HTTPException(
                status_code=422,
                detail=f"level 只允许 {sorted(_VALID_LEVELS)}，收到 {level!r}",
            )
        where.append("level = %(level)s")
        params["level"] = level
    elif not parent_adcode:
        where.append("level = 'province'")
        params["level"] = None

    if parent_adcode:
        where.append("parent_adcode = %(parent_adcode)s")
        params["parent_adcode"] = parent_adcode

    geom_expr = (
        "st_simplifypreservetopology(geom, %(simplify)s)"
        if simplify > 0
        else "geom"
    )
    params["simplify"] = simplify

    with get_cursor() as cur:
        cur.execute(
            f"""
            select adcode, name, level, parent_adcode, children_num,
                   st_asgeojson({geom_expr}, 6) as gj
            from admin_region
            where {' and '.join(where)}
            order by adcode
            """,
            params,
        )
        rows = cur.fetchall()

    import json

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(r["gj"]),
            "properties": {
                "adcode": r["adcode"],
                "name": r["name"],
                "level": r["level"],
                "parent_adcode": r["parent_adcode"],
                "children_num": r["children_num"],
            },
        }
        for r in rows
    ]
    return feature_collection(features)
