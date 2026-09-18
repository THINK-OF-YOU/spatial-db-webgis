"""专业（招生专业 / 标准专业）查询服务。

所有者：莫炜钧。见 docs/00_协作规范.md §3 文件所有权表。

────────────────────────────────────────────────────────────────
**2026-09-17 数据库恢复（专业语义链入库）之后新增。** 此前专业链全空，
本文件不存在。

专业数据是**两层语义，不是同一个概念**，接口必须分开表达，不能混成一个
「专业」字段：

  第一层　来源招生专业表达
          major_admission --expr_id--> admission_major_expression.raw_major_name
          高校在生源省实际投放的那个专业名，原样来自来源数据，
          例如「计算机科学与技术（创新实验班）」「工科试验班（信息类）」。
          覆盖 1,594,990 / 1,617,315 条正式事实（98.6196%）。

  第二层　标准专业
          admission_major_expression --expr_major_map--> major.std_name
          教育部标准专业目录里的专业，例如「计算机科学与技术」。
          本轮只入库 **Tier 1 精确映射**：68,292 条 expr、覆盖 611,319 条事实
          （37.7984%）。expr_major_map 实测是严格 1:1，一个 expr 只映一个专业，
          所以下面的 LEFT JOIN 不会放大行数。

⚠️ **未建立标准映射 ≠ 该校没有这个专业。**
   一条事实没有 Tier 1 映射，只说明它的来源专业名没有被规则 v1 精确归一，
   专业本身是存在的。由此定下三条实现纪律：

   1. `raw_major_name` **永远返回**，它是这一行真实招的是什么；
   2. `std_major` 允许为 null，且 **不得因为它是 null 就丢掉这一行**；
   3. 凡按标准专业筛选（std_major_id / 反查接口），结果只覆盖那 37.80%，
      必须在 warnings 里说明，不能让前端把「筛出来只有 5 所」当成事实。
────────────────────────────────────────────────────────────────

数据链（**全程只读**）：

    College → SchoolUnit → MajorAdmission → AdmissionMajorExpression
                                              └→ (ExprMajorMap) → Major

`admission_major_group` / `group_expr` 当前都是 0 行（专业组本轮未恢复），
所以本服务**完全不涉及专业组**，也不返回任何专业组字段。等专业组入库后
再单独加接口，不要在这里预留半成品字段。

关于 22,325 条 `expr_id IS NULL` 的事实：它们是来源里**专业名为空**的记录
（异常原因 EMPTY_MAJOR_NAME_GROUP），仍有分数和人数。因为本接口回答的是
「该校招哪些专业」，一行没有专业名的记录回答不了这个问题、渲染出来就是一
行空白，所以用 INNER JOIN 表达式表把它们排除在外；**但排除不是静默的**，
`list_college_majors()` 会一并返回被排除的条数，由接口层交给前端说明。
"""

from typing import Any

from app.db.pool import get_cursor
from app.schemas.common import MAX_PAGE_SIZE, offset_of

# 展示字段。同时用于两处：SELECT DISTINCT（精确展示合并）和「合并前」计数。
# 只有这些字段全部相同才算重复行——和契约 §4.4 对投档记录的口径一致。
_MJ_DISPLAY = """
    ma.source_province,
    ma.year,
    ma.category,
    ma.batch,
    ma.subject_req,
    e.raw_major_name,
    e.norm_name,
    e.std_status,
    maj.major_id,
    maj.std_code,
    maj.std_name,
    maj.education_level as std_education_level,
    ma.min_score,
    ma.max_score,
    ma.avg_score,
    ma.min_rank,
    ma.admit_count
"""

# join 表达式表是 INNER：正好把 22,325 条没有专业名的记录挡在外面（见模块说明）。
# expr_major_map 是 1:1，下面两个 LEFT JOIN 不会放大行数。
_MJ_FROM = """
    from major_admission ma
    join school_unit u on u.unit_id = ma.unit_id
    join admission_major_expression e on e.expr_id = ma.expr_id
    left join expr_major_map m on m.expr_id = ma.expr_id
    left join major maj on maj.major_id = m.major_id
"""

_MJ_WHERE = """
    where u.school_id = %(school_id)s
      and (%(source_province)s is null or ma.source_province = %(source_province)s)
      and (%(year)s is null or ma.year = %(year)s)
      and (%(category)s is null or ma.category = %(category)s)
      and (%(batch)s is null or ma.batch = %(batch)s)
      and (%(std_major_id)s is null or m.major_id = %(std_major_id)s)
      and (%(q)s is null
           or e.raw_major_name ilike '%%' || %(q)s || '%%'
           or maj.std_name     ilike '%%' || %(q)s || '%%')
"""


def _major_item(row: dict) -> dict:
    """把一行结果拼成对外形状。

    专业的两层在这里显式分成两个字段，**不合并**：
        raw_major_name  第一层，来源专业表达，恒有值
        std_major       第二层，标准专业，未映射时为 null
    """
    std_major = None
    if row["major_id"] is not None:
        std_major = {
            "major_id": row["major_id"],
            "std_code": row["std_code"],
            "std_name": row["std_name"],
            "education_level": row["std_education_level"],
        }

    def _f(v):
        return float(v) if v is not None else None

    item = {
        "raw_major_name": row["raw_major_name"],
        "norm_name": row["norm_name"],
        "std_status": row["std_status"],
        "std_major": std_major,
        "source_province": row["source_province"],
        "year": row["year"],
        "category": row["category"],
        "batch": row["batch"],
        "subject_req": row["subject_req"],
        "min_score": _f(row["min_score"]),
        "max_score": _f(row["max_score"]),
        "avg_score": _f(row["avg_score"]),
        "min_rank": int(row["min_rank"]) if row["min_rank"] is not None else None,
        "admit_count": row["admit_count"],
    }
    if "expr_id" in row:
        item.update(
            {
                "expr_id": row["expr_id"],
                "representative_admission_id": row["admission_id"],
                "unit_id": row["unit_id"],
                "unit_name": row["unit_name"],
                "group_id": row["group_id"],
                "professional_rank_gap": (
                    int(row["professional_rank_gap"])
                    if row["professional_rank_gap"] is not None
                    else None
                ),
            }
        )
    return item


def _facts_without_major_name(cur, school_id: int) -> int:
    """返回该校来源未提供专业名的事实数；保持旧接口的全校统计口径。"""
    cur.execute(
        """
        select count(*) as n
        from major_admission ma
        join school_unit u on u.unit_id = ma.unit_id
        where u.school_id = %(school_id)s and ma.expr_id is null
        """,
        {"school_id": school_id},
    )
    return cur.fetchone()["n"]


def _list_candidate_profile_college_majors(
    *,
    school_id: int,
    source_province: str,
    year: int,
    category: str,
    batch: str | None,
    candidate_rank: int,
    std_major_id: int | None,
    mapping: str | None,
    q: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int, bool, int]:
    """CandidateProfile V1.2：每个 expr_id 选择一条可追溯的代表事实。

    `min_rank` 非空事实优先，再按 ABS(min_rank - candidate_rank)、min_rank、
    major_admission.id、unit_id 稳定排序。只有全部候选都缺位次时才选择 NULL
    事实，因此不会把当前考试上下文中真实存在的专业误判为不存在。
    """
    params: dict[str, Any] = {
        "school_id": school_id,
        "source_province": source_province,
        "year": year,
        "category": category,
        "batch": batch or None,
        "candidate_rank": candidate_rank,
        "std_major_id": std_major_id,
        "q": q or None,
    }
    extra = ""
    if mapping == "mapped":
        extra = " and maj.major_id is not null"
    elif mapping == "unmapped":
        extra = " and maj.major_id is null"

    ranked_sql = f"""
        select ma.id as admission_id,
               ma.expr_id,
               ma.group_id,
               ma.unit_id,
               u.unit_name,
               ma.source_province,
               ma.year,
               ma.category,
               ma.batch,
               ma.subject_req,
               e.raw_major_name,
               e.norm_name,
               e.std_status,
               maj.major_id,
               maj.std_code,
               maj.std_name,
               maj.education_level as std_education_level,
               ma.min_score,
               ma.max_score,
               ma.avg_score,
               ma.min_rank,
               ma.admit_count,
               case when ma.min_rank is null then null
                    else ma.min_rank - %(candidate_rank)s end as professional_rank_gap,
               row_number() over (
                   partition by ma.expr_id
                   order by case when ma.min_rank is null then 1 else 0 end,
                            abs(ma.min_rank - %(candidate_rank)s) nulls last,
                            ma.min_rank nulls last,
                            ma.id,
                            ma.unit_id
               ) as representative_order
        {_MJ_FROM}
        where u.school_id = %(school_id)s
          and ma.source_province = %(source_province)s
          and ma.year = %(year)s
          and ma.category = %(category)s
          and (%(batch)s is null or ma.batch = %(batch)s)
          and (%(std_major_id)s is null or m.major_id = %(std_major_id)s)
          and (%(q)s is null
               or e.raw_major_name ilike '%%' || %(q)s || '%%'
               or maj.std_name ilike '%%' || %(q)s || '%%')
          {extra}
    """

    with get_cursor() as cur:
        cur.execute(
            f"select count(*) as n from ({ranked_sql}) ranked "
            "where representative_order = 1",
            params,
        )
        total = cur.fetchone()["n"]
        facts_without_major_name = _facts_without_major_name(cur, school_id)
        cur.execute(
            f"""
            select *
            from ({ranked_sql}) ranked
            where representative_order = 1
            order by case when min_rank is null then 1 else 0 end,
                     abs(professional_rank_gap) nulls last,
                     min_rank nulls last,
                     raw_major_name,
                     expr_id
            limit %(limit)s offset %(offset)s
            """,
            {**params, "limit": page_size, "offset": offset_of(page, page_size)},
        )
        rows = cur.fetchall()

    return (
        [_major_item(row) for row in rows],
        total,
        False,
        facts_without_major_name,
    )


def list_college_majors(
    school_id: int,
    source_province: str | None = None,
    year: int | None = None,
    category: str | None = None,
    batch: str | None = None,
    candidate_rank: int | None = None,
    std_major_id: int | None = None,
    mapping: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int, bool, int]:
    """某高校的招生专业录取事实。

    Args:
        mapping: None/"all" 不过滤；"mapped" 只看已建立标准映射的；
                 "unmapped" 只看未映射的（**这些不是"没有专业"，只是没归一**）。

    Returns:
        (items, total, display_deduplicated, facts_without_major_name)
        total: 精确展示合并**之后**的条数
        display_deduplicated: 合并前后条数不同则为 True
        facts_without_major_name: 该校**被排除**的、来源未提供专业名的记录条数。
            必须交给前端说明，不能让这批记录无声消失。
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    if candidate_rank is not None:
        if not source_province or year is None or not category:
            raise ValueError(
                "candidate_rank 模式必须同时提供 source_province、year、category"
            )
        return _list_candidate_profile_college_majors(
            school_id=school_id,
            source_province=source_province,
            year=year,
            category=category,
            batch=batch,
            candidate_rank=candidate_rank,
            std_major_id=std_major_id,
            mapping=mapping,
            q=q,
            page=page,
            page_size=page_size,
        )

    params: dict[str, Any] = {
        "school_id": school_id,
        "source_province": source_province or None,
        "year": year,
        "category": category or None,
        "batch": batch or None,
        "std_major_id": std_major_id,
        "q": q or None,
    }

    # mapping 的两个取值只影响 WHERE，不拼用户输入，直接拼常量片段。
    extra = ""
    if mapping == "mapped":
        extra = " and maj.major_id is not null"
    elif mapping == "unmapped":
        extra = " and maj.major_id is null"

    with get_cursor() as cur:
        # 合并前的原始条数
        cur.execute(f"select count(*) as n {_MJ_FROM} {_MJ_WHERE}{extra}", params)
        raw_total = cur.fetchone()["n"]

        # 合并后的总数
        cur.execute(
            f"select count(*) as n from (select distinct {_MJ_DISPLAY} "
            f"{_MJ_FROM} {_MJ_WHERE}{extra}) t",
            params,
        )
        total = cur.fetchone()["n"]

        # 被排除的无专业名记录：只按学校算，**不受其它筛选条件影响**。
        # 它回答的是「这所学校的专业数据整体缺了多少」，跟着筛选条件变会让
        # 同一个数字在不同筛选下忽大忽小，前端没法解释。
        facts_without_major_name = _facts_without_major_name(cur, school_id)

        cur.execute(
            f"""
            select distinct {_MJ_DISPLAY}
            {_MJ_FROM} {_MJ_WHERE}{extra}
            order by ma.year desc nulls last,
                     ma.source_province,
                     ma.category,
                     ma.batch,
                     e.raw_major_name
            limit %(limit)s offset %(offset)s
            """,
            {**params, "limit": page_size, "offset": offset_of(page, page_size)},
        )
        rows = cur.fetchall()

    items = [_major_item(r) for r in rows]
    return items, total, raw_total > total, facts_without_major_name


def list_std_majors(
    q: str | None = None,
    education_level: str | None = None,
    discipline: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """教育部标准专业目录（major 字典表）的查询。返回 (items, total)。

    这是**字典**，不是事实：全表 1,874 行 / 1,711 个专业名，与高校无关。
    前端用它填「按标准专业筛选」的下拉/搜索，拿到的 major_id 再传给
    list_college_majors() 或 list_colleges_by_major()。

    不返回 `status`（全表都是 candidate_baseline，是内部 QC 标记，
    逐行返回只会让前端多渲染一个无意义的字段）；`catalog_version` 保留，
    它是这份目录的版本出处。两个字段的取值都在对接文档里写明了。
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    params = {
        "q": q or None,
        "education_level": education_level or None,
        "discipline": discipline or None,
        "category": category or None,
    }

    where = """
        where (%(q)s is null
               or m.std_name ilike '%%' || %(q)s || '%%'
               or m.std_code ilike '%%' || %(q)s || '%%')
          and (%(education_level)s is null or m.education_level = %(education_level)s)
          and (%(discipline)s is null or m.discipline = %(discipline)s)
          and (%(category)s is null or m.category = %(category)s)
    """

    with get_cursor() as cur:
        cur.execute(f"select count(*) as n from major m {where}", params)
        total = cur.fetchone()["n"]

        cur.execute(
            f"""
            select m.major_id,
                   m.std_code,
                   m.std_name,
                   m.education_level,
                   m.discipline,
                   m.category,
                   m.catalog_version
            from major m
            {where}
            order by m.std_code, m.education_level
            limit %(limit)s offset %(offset)s
            """,
            {**params, "limit": page_size, "offset": offset_of(page, page_size)},
        )
        rows = cur.fetchall()

    return [dict(r) for r in rows], total


def get_std_major(major_id: int) -> dict | None:
    """单个标准专业。给反查接口做存在性判断。"""
    with get_cursor() as cur:
        cur.execute(
            """
            select major_id, std_code, std_name, education_level,
                   discipline, category, catalog_version
            from major where major_id = %(mid)s
            """,
            {"mid": major_id},
        )
        row = cur.fetchone()
    return dict(row) if row else None


def list_colleges_by_major(
    major_id: int,
    source_province: str | None = None,
    year: int | None = None,
    category: str | None = None,
    batch: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """反查：招这个**标准专业**的高校。返回 (items, total)。

    ⚠️ 这是纯 Tier 1 查询（INNER JOIN expr_major_map），所以**天生只覆盖
    37.7984% 的录取事实**。查到 20 所不代表只有 20 所招这个专业，
    只代表有 20 所的来源专业名被规则 v1 精确归一到这个标准专业。
    接口层必须给 warnings，前端必须展示。

    fact_count 是该校这个专业下的录取事实条数（合并前），只用来排序和给个
    量级，不是「招生人数」——招生人数是 admit_count，按省/年/批次分行给。
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    params = {
        "major_id": major_id,
        "source_province": source_province or None,
        "year": year,
        "category": category or None,
        "batch": batch or None,
    }

    from_sql = """
        from major_admission ma
        join school_unit u on u.unit_id = ma.unit_id
        join expr_major_map m on m.expr_id = ma.expr_id
        join college c on c.school_id = u.school_id
    """
    where = """
        where m.major_id = %(major_id)s
          and (%(source_province)s is null or ma.source_province = %(source_province)s)
          and (%(year)s is null or ma.year = %(year)s)
          and (%(category)s is null or ma.category = %(category)s)
          and (%(batch)s is null or ma.batch = %(batch)s)
    """

    with get_cursor() as cur:
        cur.execute(
            f"select count(distinct u.school_id) as n {from_sql} {where}", params
        )
        total = cur.fetchone()["n"]

        cur.execute(
            f"""
            select c.school_id,
                   trim(c.national_code) as national_code,
                   c.std_name            as name,
                   c.edu_level,
                   c.reg_province,
                   count(*)              as fact_count
            {from_sql} {where}
            group by c.school_id, c.national_code, c.std_name, c.edu_level, c.reg_province
            order by fact_count desc, c.school_id
            limit %(limit)s offset %(offset)s
            """,
            {**params, "limit": page_size, "offset": offset_of(page, page_size)},
        )
        rows = cur.fetchall()

    return [dict(r) for r in rows], total
