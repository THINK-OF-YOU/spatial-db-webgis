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
    """某高校的校区点。只返回业务字段，不含 source / transform_method 等内部列。

    **不返回 campus.address**：全表 432 行的 address 全是空串（2026-09-17 实测，
    count(address)=0），返回它只会让前端渲染出一行空白；而且要按「缺失值返回
    null」的口径，空串本身就不该原样给出。契约 §4.3 的字段清单里也没有它。
    """
    with get_cursor() as cur:
        cur.execute(
            """
            select campus_id,
                   campus_name,
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

    ⚠️ **2026-09-17 变更：从三个键变成四个键。**
    契约 §4.3 的示例只有 school_admission / campus / major_mapping，
    这里多了 `major_admission`。属于约定的契约变更（先实现、执行书后补），
    已同步给前端，见 docs/02_专业API对接文档.md。

    为什么非拆不可——专业是**两层语义**（详见 services/major_service.py 开头）：

        来源招生专业表达  98.62% 的事实有
        标准专业(Tier 1)  37.80% 的事实有

    全库 2,952 所高校里 2,747 所有专业事实，但只有 2,586 所有至少一条 Tier 1
    标准映射。如果只留一个 `major_mapping` 表示「有没有专业数据」，那么
    major_mapping=false 的学校在前端会被整个藏掉专业视图——**可它明明有专业，
    只是来源专业名没被规则 v1 精确归一**。这正是「未建立标准映射 ≠ 没有该专业」
    那个坑。拆成两个键，前端才能说清：

        有 120 条专业录取记录，其中 45 条已归入标准专业

    两个键的分工：
        major_admission  该校有没有**专业录取事实**（决定专业视图显不显示）
        major_mapping    该校有没有**已建立标准映射**的事实（决定能不能按
                         标准专业筛，以及要不要给覆盖警告）

    `enrollment_plan` 依旧**刻意不返回**：附录 B 第三条要求「不要把 EnrollmentPlan
    或 MajorAdmission 引入核心页面」，且 §4.3 字段清单里没有它。原先返回过一个
    enrollment_plan 布尔值，2026-09-17 移除。

    （注：附录 B 第三条同时点名了 MajorAdmission，那是专业语义链入库**之前**定的
    规矩——当时该表没有任何专业数据。2026-09-17 专业接口经**全组确定**为新增范围，
    该限制对专业接口不再适用；但**核心页面**（API 1 / 2 / 9）仍然不引入专业数据，
    这里只多返回两个布尔值，不夹带任何专业记录。）
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
                      join major_admission ma on ma.unit_id = u.unit_id
                     where u.school_id = %(sid)s)                    as major_admission,
              exists(select 1 from school_unit u
                      join major_admission ma on ma.unit_id = u.unit_id
                      join expr_major_map m on m.expr_id = ma.expr_id
                     where u.school_id = %(sid)s)                    as major_mapping
            """,
            {"sid": school_id},
        )
        row = dict(cur.fetchone())

    return row
