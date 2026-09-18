"""空间查询服务。

所有者：莫炜钧。见 docs/00_协作规范.md §3 文件所有权表。

距离一律用 geom::geography 走**米制测地距离**。
直接对 geometry 传米数是在比"度"——这是本项目历史上踩过的坑。
"""

from app.db.pool import get_cursor
from app.warnings import (
    INCLUDE_CANDIDATE_CAMPUS,
    NO_CAMPUS_FOR_QUERY,
    NO_TRANSPORT_DATA,
    dedupe,
)

# §3.3 冻结：附近高校**默认只使用 CONFIRMED**，用户主动开启后才纳入 CANDIDATE。
DEFAULT_VERIFY_STATUSES = ["CONFIRMED"]

ALL_VERIFY_STATUSES = ["CONFIRMED", "CANDIDATE"]

# poi_transport.mode 的库内真实取值（2026-09-17 实测，全部 18,996 行）：
# rail 10,687 / metro 7,792 / airport 329 / rail_halt 188。
# 契约 §4.11 把它写死成这四个值——不接受别的，免得前端传了错值被静默忽略。
TRANSPORT_MODES = ["rail", "metro", "airport", "rail_halt"]

# Transport V2 搜索与摘要不把 rail_halt 当作筛选类型。
TRANSPORT_SEARCH_MODES = ["metro", "rail", "airport"]

# 摘要只在合理范围内按类型分别寻找最近 POI，避免无界全国距离扫描。
TRANSPORT_SUMMARY_RADIUS_KM = {
    "metro": 10.0,
    "rail": 30.0,
    "airport": 80.0,
}


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


def nearby_transport(
    school_id: int,
    radius_km: float = 3.0,
    modes: list[str] | None = None,
    limit: int = 20,
) -> tuple[list[dict], list[str]]:
    """指定高校周边的交通站点。返回 (items, warnings)。

    数据链 College → Campus → poi_transport（§4.11）。基准点是该校**全部**带几何的
    Campus，每个站点只保留到**最近**那个 Campus 的距离，并按这个距离升序。

    距离用 geom::geography 算米制测地距离，对外给 km —— 与 nearby() 同一套口径。

    取"最近校区"用的是 KNN（`<->`）定候选 + geography 定精确距离：`<->` 在 geometry
    上是按度比的，直接拿它当距离会挑错，只能用来挑候选。
    **注意：当前库里 479 个带几何的 Campus 分属 479 所不同高校，每校最多 1 个**
    （2026-09-18 实测），所以这条 lateral 现在永远只命中那一个校区——
    也就是说"多校区取最近"这条路径**目前没有被数据走到**，是照着校区数据将来变多
    写的。别以为它被测过。

    `env` 那层是必要的：poi_transport 有 18,996 行，不加 bbox 预筛的话 lateral 要跑
    18,996 次，实测 1.2 s；加上之后走 idx_poi_transport_geom 的 GiST 索引，
    同样结果 64 ms。度→米的换算按校区里**最大纬度**取 cos，宁可框大一点，
    也不漏掉真命中的点（框大只是多算几行，框小会丢数据）。
    """
    radius_m = radius_km * 1000.0

    with get_cursor() as cur:
        # 先看这所学校到底有没有可用校区 —— 没有的话是另一回事，不能混报
        cur.execute(
            """
            select count(*) as n
            from campus
            where school_id = %(school_id)s and geom is not null
            """,
            {"school_id": school_id},
        )
        if cur.fetchone()["n"] == 0:
            return [], dedupe([NO_CAMPUS_FOR_QUERY])

        cur.execute(
            """
            with base as (
                select cp.campus_id, cp.campus_name, cp.geom
                from campus cp
                where cp.school_id = %(school_id)s
                  and cp.geom is not null
            ),
            env as (
                select st_expand(
                           st_envelope(st_collect(geom)),
                           %(radius_m)s / 111320.0
                             / greatest(cos(radians(max(abs(st_y(geom))))), 0.01)
                       ) as box
                from base
            )
            select p.poi_id,
                   p.mode,
                   p.name,
                   p.name_zh,
                   st_x(p.geom) as lon,
                   st_y(p.geom) as lat,
                   near.campus_id,
                   near.campus_name,
                   near.distance_m
            from poi_transport p
            cross join env
            cross join lateral (
                select b.campus_id,
                       b.campus_name,
                       st_distance(p.geom::geography, b.geom::geography) as distance_m
                from base b
                order by b.geom <-> p.geom
                limit 1
            ) near
            where p.geom && env.box
              and (%(modes)s is null or p.mode = any(%(modes)s))
              and near.distance_m <= %(radius_m)s
            order by near.distance_m, p.poi_id
            limit %(limit)s
            """,
            {
                "school_id": school_id,
                "modes": modes or None,
                "radius_m": radius_m,
                "limit": max(1, min(limit, 200)),
            },
        )
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        r["distance_km"] = round(r.pop("distance_m") / 1000.0, 2)

    warnings: list[str] = []
    if not rows:
        # 有校区但半径内没有站点——poi_transport 覆盖不齐，这是常态。
        # 必须说清楚，不能让前端把"查不到"显示成"周边没有站点"。
        warnings.append(NO_TRANSPORT_DATA)

    return rows, dedupe(warnings)


def transport_summary(school_id: int) -> tuple[dict[str, dict | None], list[str]]:
    """返回指定高校每种主要交通设施各自最近的一条真实事实。

    metro / rail / airport 分别在自己的搜索半径内求最近值，因此不会因最近
    若干 POI 全是 metro 而错误地把 rail / airport 判成缺失。每个候选仍同时
    绑定一个 Campus，并按 geography 测地距离做最终排序。
    """
    empty = {mode: None for mode in TRANSPORT_SEARCH_MODES}

    with get_cursor() as cur:
        cur.execute(
            """
            select count(*) as n
            from campus
            where school_id = %(school_id)s and geom is not null
            """,
            {"school_id": school_id},
        )
        if cur.fetchone()["n"] == 0:
            return empty, dedupe([NO_CAMPUS_FOR_QUERY])

        cur.execute(
            """
            with base as (
                select cp.campus_id, cp.campus_name, cp.geom
                from campus cp
                where cp.school_id = %(school_id)s
                  and cp.geom is not null
            ),
            modes(mode, radius_m, sort_order) as (
                values
                    ('metro'::text, %(metro_radius_m)s::double precision, 1),
                    ('rail'::text, %(rail_radius_m)s::double precision, 2),
                    ('airport'::text, %(airport_radius_m)s::double precision, 3)
            )
            select m.mode,
                   hit.poi_id,
                   hit.name,
                   hit.name_zh,
                   hit.lon,
                   hit.lat,
                   hit.campus_id,
                   hit.campus_name,
                   hit.distance_m
            from modes m
            left join lateral (
                select p.poi_id,
                       p.name,
                       p.name_zh,
                       st_x(p.geom) as lon,
                       st_y(p.geom) as lat,
                       cp.campus_id,
                       cp.campus_name,
                       st_distance(p.geom::geography, cp.geom::geography) as distance_m
                from base cp
                join poi_transport p
                  on p.mode = m.mode
                 and p.geom is not null
                 and p.geom && st_expand(
                        cp.geom,
                        m.radius_m / 111320.0
                          / greatest(cos(radians(abs(st_y(cp.geom)))), 0.01)
                     )
                 and st_dwithin(
                        p.geom::geography,
                        cp.geom::geography,
                        m.radius_m
                     )
                order by distance_m, p.poi_id, cp.campus_id
                limit 1
            ) hit on true
            order by m.sort_order
            """,
            {
                "school_id": school_id,
                "metro_radius_m": TRANSPORT_SUMMARY_RADIUS_KM["metro"] * 1000.0,
                "rail_radius_m": TRANSPORT_SUMMARY_RADIUS_KM["rail"] * 1000.0,
                "airport_radius_m": TRANSPORT_SUMMARY_RADIUS_KM["airport"] * 1000.0,
            },
        )
        rows = [dict(row) for row in cur.fetchall()]

    items: dict[str, dict | None] = dict(empty)
    for row in rows:
        mode = row.pop("mode")
        distance_m = row.pop("distance_m", None)
        if row.get("poi_id") is None or distance_m is None:
            continue
        row["mode"] = mode
        row["distance_km"] = round(distance_m / 1000.0, 2)
        items[mode] = row

    warnings: list[str] = []
    if any(item is None for item in items.values()):
        warnings.append(NO_TRANSPORT_DATA)
    return items, dedupe(warnings)


def _as_geojson_text(geometry: dict) -> str:
    """把几何体转成 ST_GeomFromGeoJSON 能吃的字符串。

    注意 ST_GeomFromGeoJSON 不保留 SRID，所以外面必须再套 st_setsrid。
    """
    import json

    return json.dumps(geometry, ensure_ascii=False)
