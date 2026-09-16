"""综合查询：招生 + College + 地域 + 空间。

所有者：莫炜钧（总集成）。招生子查询由倪嵩提供，见
app/services/admission_service.py。契约见《任务执行书》§4.10。

业务不变量（§3.5，Gate 项）：
    **没有空间条件时，没有 Campus 的 College 仍要正常出现在结果里。**
    只有启用空间条件后，无可用 Campus 的高校才不能参与空间筛选，
    并且必须通过 warnings 说明空间覆盖不足。
"""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.pool import get_cursor
from app.schemas.common import MAX_PAGE_SIZE, offset_of
from app.services import admission_service
from app.services.spatial_service import ALL_VERIFY_STATUSES
from app.warnings import (
    INCLUDE_CANDIDATE_CAMPUS,
    NO_CAMPUS_EXCLUDED,
    SOURCE_VOCABULARY,
    dedupe,
)

router = APIRouter(tags=["search"])


class AdmissionCond(BaseModel):
    source_province: str | None = None
    year: int | None = None
    category: str | None = None
    batch: str | None = None


class CollegeCond(BaseModel):
    edu_level: str | None = None


class RefPoint(BaseModel):
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)


class SpatialCond(BaseModel):
    reference_point: RefPoint | None = None
    radius_km: float | None = Field(None, gt=0, le=2000)
    include_candidate_campus: bool = False
    geometry: dict | None = Field(
        None, description="GeoJSON Polygon；与参考点同时给出时取交集"
    )


class SearchRequest(BaseModel):
    admission: AdmissionCond | None = None
    college: CollegeCond | None = None
    regions: list[str] = Field(
        default_factory=list, description="目标行政区 adcode 列表（注意：不是生源省）"
    )
    spatial: SpatialCond | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=MAX_PAGE_SIZE)


# ── 基础集合：College + 地域 + 招生 ─────────────────────────────────
# regions 传的是 adcode；库里 college.reg_province 装的是**市名**，
# 所以按名字匹配，并把选中行政区的下两级名字一起纳入（省→市→区）。
# 见协作规范 §5.1。
_BASE_CTE = """
    select c.school_id
    from college c
    where (%(edu_level)s is null or c.edu_level = %(edu_level)s)
      and (
            %(region_adcodes)s is null
            or c.reg_province = any(
                select a.name from admin_region a
                where a.adcode = any(%(region_adcodes)s)
                   or a.parent_adcode = any(%(region_adcodes)s)
                   or a.parent_adcode in (
                        select a2.adcode from admin_region a2
                        where a2.parent_adcode = any(%(region_adcodes)s)
                   )
            )
          )
      and (%(admission_ids)s is null or c.school_id = any(%(admission_ids)s))
"""


@router.post("/search")
def search(req: SearchRequest):
    warnings: list[str] = []

    # ── 招生条件：交给倪嵩的 service，本接口不写第二套招生 SQL ──────────
    admission_ids: list[int] | None = None
    if req.admission:
        try:
            admission_ids = admission_service.filter_school_ids(
                source_province=req.admission.source_province,
                year=req.admission.year,
                category=req.admission.category,
                batch=req.admission.batch,
            )
        except admission_service.AdmissionFilterNotImplemented as exc:
            # 不静默忽略招生条件——那会返回"看起来筛过了其实没筛"的结果，
            # 比报错更糟。
            raise HTTPException(status_code=501, detail=str(exc)) from exc

        if req.admission.category or req.admission.batch:
            warnings.append(SOURCE_VOCABULARY)

    # ── 空间条件 ────────────────────────────────────────────────────
    spatial = req.spatial
    predicates: list[str] = []
    params: dict = {
        "edu_level": (req.college.edu_level if req.college else None) or None,
        "region_adcodes": req.regions or None,
        "admission_ids": admission_ids,
    }

    if spatial:
        statuses = (
            list(ALL_VERIFY_STATUSES)
            if spatial.include_candidate_campus
            else ["CONFIRMED"]
        )
        params["statuses"] = statuses
        if spatial.include_candidate_campus:
            warnings.append(INCLUDE_CANDIDATE_CAMPUS)

        if spatial.geometry:
            predicates.append(
                "st_within(cp.geom,"
                " st_setsrid(st_geomfromgeojson(%(s_geojson)s), 4326))"
            )
            params["s_geojson"] = json.dumps(spatial.geometry, ensure_ascii=False)

        if spatial.reference_point and spatial.radius_km:
            predicates.append(
                "st_dwithin(cp.geom::geography,"
                " st_setsrid(st_makepoint(%(s_lon)s, %(s_lat)s), 4326)::geography,"
                " %(s_radius_m)s)"
            )
            params["s_lon"] = spatial.reference_point.lon
            params["s_lat"] = spatial.reference_point.lat
            params["s_radius_m"] = spatial.radius_km * 1000.0

    spatial_enabled = bool(predicates)

    # ── 拼 CTE ─────────────────────────────────────────────────────
    ctes = f"with base as ({_BASE_CTE})"

    if spatial_enabled:
        ctes += f"""
        , spatial_hit as (
            select distinct cp.school_id
            from campus cp
            where cp.geom is not null
              and cp.verify_status = any(%(statuses)s)
              and {' and '.join(predicates)}
        )
        """
        # 只有启用空间条件后，无 Campus 的高校才被排除
        eligible = (
            "select b.school_id from base b"
            " where b.school_id in (select school_id from spatial_hit)"
        )
    else:
        eligible = "select school_id from base"

    # 有参考点时附带距参考点最近的一个校区距离（§3.4 学校卡片字段）
    distance_select = "null::double precision as distance_m"
    distance_join = ""
    if spatial and spatial.reference_point:
        distance_select = (
            "st_distance(np.geom::geography,"
            " st_setsrid(st_makepoint(%(s_lon)s, %(s_lat)s), 4326)::geography) as distance_m"
        )
        distance_join = """
            left join lateral (
                select c2.geom
                from campus c2
                where c2.school_id = c.school_id and c2.geom is not null
                order by c2.geom <-> st_setsrid(st_makepoint(%(s_lon)s, %(s_lat)s), 4326)
                limit 1
            ) np on true
        """

    page_sql = f"""
        {ctes},
        eligible as ({eligible})
        select c.school_id,
               trim(c.national_code)      as national_code,
               c.std_name                 as name,
               c.edu_level,
               c.reg_province,
               (hc.school_id is not null) as has_campus,
               {distance_select}
        from eligible e
        join college c on c.school_id = e.school_id
        left join (select distinct school_id from campus where geom is not null) hc
               on hc.school_id = c.school_id
        {distance_join}
        order by c.school_id
        limit %(limit)s offset %(offset)s
    """

    count_sql = f"{ctes} select count(*) as n from ({eligible}) t"

    page, page_size = req.page, req.page_size

    with get_cursor() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()["n"]

        cur.execute(
            page_sql,
            {**params, "limit": page_size, "offset": offset_of(page, page_size)},
        )
        items = [dict(r) for r in cur.fetchall()]

        # 空间覆盖不足的提示：符合非空间条件、但压根没有 Campus 的高校有多少
        if spatial_enabled:
            cur.execute(
                f"""
                {ctes}
                select count(*) as n
                from base b
                where not exists (
                    select 1 from campus cp
                    where cp.school_id = b.school_id and cp.geom is not null
                )
                """,
                params,
            )
            if cur.fetchone()["n"] > 0:
                warnings.append(NO_CAMPUS_EXCLUDED)

    for it in items:
        d = it.pop("distance_m", None)
        it["distance_km"] = round(d / 1000.0, 2) if d is not None else None

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "warnings": dedupe(warnings),
    }
