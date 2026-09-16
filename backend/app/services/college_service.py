"""College 查询服务。

所有者：莫炜钧。见 docs/00_协作规范.md §3 文件所有权表。
"""

from app.db.pool import get_cursor
from app.schemas.common import MAX_PAGE_SIZE, offset_of

# has_admission 用**预聚合**而不是逐行 EXISTS：
# school_unit.school_id 上没有独立索引（勘察报告 §2.2 P3 登记项），
# 逐行 EXISTS 会退化成反复扫小表 2,952 次。预聚合只扫一遍。
_SELECT = """
    c.school_id,
    trim(c.national_code)                  as national_code,
    c.std_name                             as name,
    c.edu_level,
    c.reg_province,
    (cp.school_id is not null)             as has_campus,
    (ad.school_id is not null)             as has_admission
"""

_FROM = """
    from college c
    left join (select distinct school_id from campus) cp
           on cp.school_id = c.school_id
    left join (
        select distinct u.school_id
        from school_unit u
        join school_admission a on a.unit_id = u.unit_id
    ) ad on ad.school_id = c.school_id
"""

# 只按数据库原始值筛选。reg_province 里装的是**市名**，不是省名——
# 按原值用，不改名不扩展。见协作规范 §5.1。
_WHERE = """
    where (%(q)s is null or c.std_name ilike '%%' || %(q)s || '%%')
      and (%(edu_level)s is null or c.edu_level = %(edu_level)s)
      and (%(reg_province)s is null or c.reg_province = %(reg_province)s)
"""


def list_colleges(
    q: str | None = None,
    edu_level: str | None = None,
    reg_province: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """高校列表 / 搜索 / 基础筛选。返回 (items, total)。"""
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    params = {
        "q": q or None,
        "edu_level": edu_level or None,
        "reg_province": reg_province or None,
    }

    with get_cursor() as cur:
        cur.execute(f"select count(*) as n from college c {_WHERE}", params)
        total = cur.fetchone()["n"]

        cur.execute(
            f"""
            select {_SELECT} {_FROM} {_WHERE}
            order by c.school_id
            limit %(limit)s offset %(offset)s
            """,
            {**params, "limit": page_size, "offset": offset_of(page, page_size)},
        )
        items = [dict(r) for r in cur.fetchall()]

    return items, total


def get_college(school_id: int) -> dict | None:
    """单个高校主数据。"""
    with get_cursor() as cur:
        cur.execute(
            f"select {_SELECT} {_FROM} where c.school_id = %(sid)s",
            {"sid": school_id},
        )
        row = cur.fetchone()
    return dict(row) if row else None


def list_campuses_of(school_id: int) -> list[dict]:
    """某高校的校区点。只返回业务字段，不含 source / transform_method 等内部列。"""
    with get_cursor() as cur:
        cur.execute(
            """
            select campus_id,
                   campus_name,
                   address,
                   verify_status,
                   st_x(geom) as lon,
                   st_y(geom) as lat
            from campus
            where school_id = %(sid)s and geom is not null
            order by campus_id
            """,
            {"sid": school_id},
        )
        return [dict(r) for r in cur.fetchall()]


def college_availability(school_id: int) -> dict:
    """data_availability —— 告诉前端这个学校哪些数据真的能拿到。

    专业语义链为空（admission_major_expression / admission_major_group /
    expr_major_map / group_expr 都是 0 行），所以 major_mapping 恒为 false。
    见协作规范 §1.3 与勘察报告 §2.1。
    """
    with get_cursor() as cur:
        cur.execute(
            """
            select
              exists(select 1 from campus
                      where school_id = %(sid)s and geom is not null) as campus,
              exists(select 1 from school_unit u
                      join school_admission a on a.unit_id = u.unit_id
                     where u.school_id = %(sid)s)                    as school_admission,
              exists(select 1 from school_unit u
                      join enrollment_plan e on e.unit_id = u.unit_id
                     where u.school_id = %(sid)s)                    as enrollment_plan
            """,
            {"sid": school_id},
        )
        row = dict(cur.fetchone())

    row["major_mapping"] = False  # 专业语义链为空，V1 不提供
    return row
