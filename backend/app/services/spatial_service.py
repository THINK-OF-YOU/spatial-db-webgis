"""空间查询服务。

所有者：莫炜钧。见 docs/00_协作规范.md §3 文件所有权表。

距离一律用 geom::geography 走**米制测地距离**。
直接对 geometry 传米数是在比"度"——这是本项目历史上踩过的坑。
"""

from app.db.pool import get_cursor
from app.warnings import INCLUDE_CANDIDATE_CAMPUS, dedupe

# §3.3 冻结：附近高校**默认只使用 CONFIRMED**，用户主动开启后才纳入 CANDIDATE。
DEFAULT_VERIFY_STATUSES = ["CONFIRMED"]

ALL_VERIFY_STATUSES = ["CONFIRMED", "CANDIDATE"]


def resolve_verify_status(raw: list[str] | None) -> list[str]:
    """把前端传来的状态列表收敛到合法的两个值。空 → 默认 CONFIRMED。"""
    if not raw:
        return list(DEFAULT_VERIFY_STATUSES)
    allowed = [s for s in raw if s in ALL_VERIFY_STATUSES]
    return allowed or list(DEFAULT_VERIFY_STATUSES)


def nearby(
    lon: float,
    lat: float,
    radius_km: float,
    verify_status: list[str] | None = None,
    limit: int = 20,
) -> tuple[list[dict], list[str]]:
    """参考点 + 半径内的校区。返回 (items, warnings)。"""
    statuses = resolve_verify_status(verify_status)
    radius_m = radius_km * 1000.0

    with get_cursor() as cur:
        cur.execute(
            """
            select c.school_id,
                   c.std_name            as school_name,
                   cp.campus_id,
                   cp.campus_name,
                   cp.verify_status,
                   st_distance(
                       cp.geom::geography,
                       st_setsrid(st_makepoint(%(lon)s, %(lat)s), 4326)::geography
                   ) as distance_m
            from campus cp
            join college c on c.school_id = cp.school_id
            where cp.geom is not null
              and cp.verify_status = any(%(statuses)s)
              and st_dwithin(
                      cp.geom::geography,
                      st_setsrid(st_makepoint(%(lon)s, %(lat)s), 4326)::geography,
                      %(radius_m)s
                  )
            order by distance_m
            limit %(limit)s
            """,
            {
                "lon": lon,
                "lat": lat,
                "radius_m": radius_m,
                "statuses": statuses,
                "limit": max(1, min(limit, 200)),
            },
        )
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        r["distance_km"] = round(r.pop("distance_m") / 1000.0, 2)

    warnings: list[str] = []
    if "CANDIDATE" in statuses:
        warnings.append(INCLUDE_CANDIDATE_CAMPUS)

    return rows, dedupe(warnings)


def within(
    geometry: dict,
    verify_status: list[str] | None = None,
    limit: int = 500,
) -> tuple[list[dict], list[str]]:
    """GeoJSON Polygon 内的校区。

    边界语义**固定为 ST_Within**（点在面内），不混用 ST_Intersects。
    副作用：正好落在多边形边界上的点会被排除。用户手绘多边形时这几乎不会发生，
    但规则要写清楚，免得以后有人以为漏了数据。

    返回 (items, warnings)。
    """
    statuses = resolve_verify_status(verify_status)

    with get_cursor() as cur:
        cur.execute(
            """
            with poly as (
                select st_setsrid(st_geomfromgeojson(%(geojson)s), 4326) as g
            )
            select c.school_id,
                   c.std_name as school_name,
                   cp.campus_id,
                   cp.campus_name,
                   cp.verify_status,
                   st_x(cp.geom) as lon,
                   st_y(cp.geom) as lat
            from campus cp
            join college c on c.school_id = cp.school_id
            cross join poly
            where cp.geom is not null
              and cp.verify_status = any(%(statuses)s)
              and st_within(cp.geom, poly.g)
            order by c.school_id, cp.campus_id
            limit %(limit)s
            """,
            {
                "geojson": _as_geojson_text(geometry),
                "statuses": statuses,
                "limit": max(1, min(limit, 2000)),
            },
        )
        rows = [dict(r) for r in cur.fetchall()]

    warnings: list[str] = []
    if "CANDIDATE" in statuses:
        warnings.append(INCLUDE_CANDIDATE_CAMPUS)

    return rows, dedupe(warnings)


def _as_geojson_text(geometry: dict) -> str:
    """把几何体转成 ST_GeomFromGeoJSON 能吃的字符串。

    注意 ST_GeomFromGeoJSON 不保留 SRID，所以外面必须再套 st_setsrid。
    """
    import json

    return json.dumps(geometry, ensure_ascii=False)
