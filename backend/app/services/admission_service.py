"""招生筛选服务 —— **所有者：倪嵩**。

见 docs/00_协作规范.md §3 文件所有权表。本文件归倪嵩，**他人只读**；
确实要改先在群里说，由 owner 改（下面那次是经授权的一次性例外）。

────────────────────────────────────────────────────────────────
**已于 2026-09-17 实现**（此前是占位桩，骨架里的 AdmissionFilterNotImplemented
类已随之移除）。本文件现在提供六个函数：

    ranked_admission_references()  CandidateProfile V1 每校代表事实
    multi_year_admission_summary() CandidateProfile V2.1 学校级多年摘要
    candidate_profile_contexts()   CandidateProfile V1 有效考试上下文
    filter_school_ids()   /api/search 的招生子查询；无条件时返回 None
    filter_meta()         /api/meta/filters 的五个下拉项
    list_admissions()     /api/colleges/{school_id}/admissions 的明细查询

函数签名按契约 §4.10 冻结，**不要改签名** —— /api/search 依赖 filter_school_ids。

2026-09-17 莫炜钧经授权改过一次：**只改了本段文档字符串**（原文仍自称"占位桩"，
已不成立），函数体与 SQL 一行未动。
────────────────────────────────────────────────────────────────

契约约定的调用方式（莫炜钧的 /api/search 这样用）：

    from app.services import admission_service
    school_ids = admission_service.filter_school_ids(
        source_province="湖南省", year=2024, category="物理类", batch=None
    )
    # 返回 None      → 没有启用招生条件，不要过滤
    # 返回 list[int] → 只保留这些 school_id（含空列表：无匹配）

数据链固定 College → SchoolUnit → SchoolAdmission。
不要把 EnrollmentPlan 或 MajorAdmission 引进来（§1.3、附录 B 第三条）。

注意：category / batch 是来源原始口径，不要做全国统一映射（§1.3）。
"""

from typing import Any

from app.db.pool import get_cursor


def candidate_profile_contexts() -> list[dict[str, Any]]:
    """返回可用于 CandidateProfile 位次查询的真实考试上下文。

    仅 ``min_rank`` 非空的 SchoolAdmission 才能支撑 V1 位次参考。去重在
    PostgreSQL 内完成；``batch`` 可为 NULL，代表该真实上下文没有批次值，
    前端的“全部批次”仍由 UI 自己表达，不伪造成数据库取值。
    """
    sql = """
        SELECT DISTINCT
            source_province,
            year,
            category,
            batch
        FROM school_admission
        WHERE min_rank IS NOT NULL
          AND source_province IS NOT NULL
          AND source_province <> ''
          AND year IS NOT NULL
          AND category IS NOT NULL
          AND category <> ''
        ORDER BY source_province, year DESC, category, batch NULLS FIRST
    """
    with get_cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    return [dict(row) for row in rows]


def ranked_admission_references(
    *,
    source_province: str,
    year: int,
    category: str,
    rank: int,
    rank_ahead: int,
    rank_behind: int,
    batch: str | None = None,
) -> list[dict[str, Any]]:
    """返回位次窗口内每所高校唯一且确定的代表历史投档事实。

    过滤与代表事实选择都在 PostgreSQL 完成；Python 只接收每校一行的结果。
    同校按 ``ABS(min_rank - rank)`` 最近优先；完全同距时依次按
    ``min_rank``、``school_admission.id`` 排序，保证结果可复现。
    """
    lower = max(1, rank - rank_ahead)
    upper = rank + rank_behind
    sql = """
        WITH ranked AS (
            SELECT
                u.school_id,
                a.id AS admission_id,
                a.unit_id,
                u.unit_name,
                a.source_province,
                a.year,
                a.category,
                a.batch,
                a.min_score,
                a.min_rank,
                a.min_rank - %(rank)s AS rank_gap,
                ROW_NUMBER() OVER (
                    PARTITION BY u.school_id
                    ORDER BY
                        ABS(a.min_rank - %(rank)s),
                        a.min_rank,
                        a.id
                ) AS choice_order
            FROM school_admission a
            JOIN school_unit u ON u.unit_id = a.unit_id
            WHERE a.source_province = %(source_province)s
              AND a.year = %(year)s
              AND a.category = %(category)s
              AND (%(batch)s IS NULL OR a.batch = %(batch)s)
              AND a.min_rank IS NOT NULL
              AND a.min_rank >= %(lower)s
              AND a.min_rank <= %(upper)s
        )
        SELECT
            school_id,
            admission_id,
            unit_id,
            unit_name,
            source_province,
            year,
            category,
            batch,
            min_score,
            min_rank,
            rank_gap
        FROM ranked
        WHERE choice_order = 1
        ORDER BY ABS(rank_gap), min_rank, admission_id, school_id
    """
    params = {
        "source_province": source_province,
        "year": year,
        "category": category,
        "batch": batch,
        "rank": rank,
        "lower": lower,
        "upper": upper,
    }
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [
        {
            "school_id": row["school_id"],
            "admission_id": row["admission_id"],
            "unit_id": row["unit_id"],
            "unit_name": row["unit_name"],
            "source_province": row["source_province"],
            "year": row["year"],
            "category": row["category"],
            "batch": row["batch"],
            "min_score": (
                float(row["min_score"]) if row["min_score"] is not None else None
            ),
            "min_rank": int(row["min_rank"]),
            "rank_gap": int(row["rank_gap"]),
        }
        for row in rows
    ]


def multi_year_admission_summary(
    *,
    school_id: int,
    source_province: str,
    main_year: int,
    category: str,
    candidate_rank: int,
    batch: str | None = None,
) -> dict[str, Any]:
    """返回某高校在严格 CandidateProfile 口径下的多年度历史参考。

    年份集合来自全库同生源省、同科类且不晚于主参考年的真实年份，而不是
    该校自身的年份。由此，学校缺失的年份仍会以 ``no_record`` 明确返回。
    ``batch`` 只过滤学校事实，不参与年份集合生成，也不做任何名称映射。

    代表事实只从 ``min_rank`` 非空的原始 SchoolAdmission 中选择；与考生位次
    等距时依次按 ``min_rank``、``school_admission.id``，保证结果稳定可复现。
    """
    sql = """
        WITH comparable_years AS (
            SELECT DISTINCT a.year
            FROM school_admission a
            WHERE a.source_province = %(source_province)s
              AND a.category = %(category)s
              AND a.year IS NOT NULL
              AND a.year <= %(main_year)s
        ),
        college_facts AS (
            SELECT
                a.id AS admission_id,
                a.unit_id,
                u.unit_name,
                a.year,
                a.batch,
                a.min_score,
                a.min_rank
            FROM school_admission a
            JOIN school_unit u ON u.unit_id = a.unit_id
            WHERE u.school_id = %(school_id)s
              AND a.source_province = %(source_province)s
              AND a.category = %(category)s
              AND a.year IS NOT NULL
              AND a.year <= %(main_year)s
              AND (%(batch)s IS NULL OR a.batch = %(batch)s)
        ),
        year_counts AS (
            SELECT year, COUNT(*) AS record_count
            FROM college_facts
            GROUP BY year
        ),
        ranked_references AS (
            SELECT
                admission_id,
                unit_id,
                unit_name,
                year,
                batch,
                min_score,
                min_rank,
                min_rank - %(candidate_rank)s AS rank_gap,
                ROW_NUMBER() OVER (
                    PARTITION BY year
                    ORDER BY
                        ABS(min_rank - %(candidate_rank)s),
                        min_rank,
                        admission_id
                ) AS choice_order
            FROM college_facts
            WHERE min_rank IS NOT NULL
        )
        SELECT
            y.year,
            COALESCE(c.record_count, 0) AS record_count,
            r.admission_id,
            r.unit_id,
            r.unit_name,
            r.batch,
            r.min_score,
            r.min_rank,
            r.rank_gap
        FROM comparable_years y
        LEFT JOIN year_counts c ON c.year = y.year
        LEFT JOIN ranked_references r
          ON r.year = y.year AND r.choice_order = 1
        ORDER BY y.year DESC
    """
    params = {
        "school_id": school_id,
        "source_province": source_province,
        "main_year": main_year,
        "category": category,
        "candidate_rank": candidate_rank,
        "batch": batch,
    }
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    years: list[dict[str, Any]] = []
    for row in rows:
        record_count = int(row["record_count"])
        if record_count == 0:
            status = "no_record"
            reference_admission = None
        elif row["admission_id"] is None:
            status = "rank_unavailable"
            reference_admission = None
        else:
            status = "reference_available"
            reference_admission = {
                "admission_id": int(row["admission_id"]),
                "unit_id": int(row["unit_id"]),
                "unit_name": row["unit_name"],
                "batch": row["batch"],
                "min_score": (
                    float(row["min_score"])
                    if row["min_score"] is not None
                    else None
                ),
                "min_rank": int(row["min_rank"]),
                "rank_gap": int(row["rank_gap"]),
            }
        years.append(
            {
                "year": int(row["year"]),
                "status": status,
                "record_count": record_count,
                "reference_admission": reference_admission,
            }
        )

    return {
        "school_id": school_id,
        "context": {
            "source_province": source_province,
            "main_year": main_year,
            "category": category,
            "batch": batch,
            "candidate_rank": candidate_rank,
        },
        "years": years,
    }


def filter_school_ids(
    source_province: str | None = None,
    year: int | None = None,
    category: str | None = None,
    batch: str | None = None,
) -> list[int] | None:
    """按招生条件返回符合条件的 school_id 列表。

    Returns:
        None       没有启用任何招生条件 → 调用方不过滤
        list[int]  符合条件的 school_id（空列表表示无匹配）
    """
    if not any([source_province, year, category, batch]):
        return None

    sql = """
        SELECT DISTINCT u.school_id
        FROM school_admission a
        JOIN school_unit u ON u.unit_id = a.unit_id
        WHERE (%(source_province)s IS NULL OR a.source_province = %(source_province)s)
          AND (%(year)s IS NULL OR a.year = %(year)s)
          AND (%(category)s IS NULL OR a.category = %(category)s)
          AND (%(batch)s IS NULL OR a.batch = %(batch)s)
    """
    with get_cursor() as cur:
        cur.execute(sql, {
            "source_province": source_province,
            "year": year,
            "category": category,
            "batch": batch,
        })
        rows = cur.fetchall()

    return [row["school_id"] for row in rows]


def filter_meta() -> dict[str, Any]:
    """给 /api/meta/filters 用的字典。

    从数据库真实值生成：
        years / source_provinces / edu_levels / categories / batches

    要点（附录 B 第四条）：
    - 从数据库真实值生成，不要硬编码全国 category / batch。
    - category / batch 是来源原始口径，不要自行造全国统一映射。
    - 可以去空值、合理排序，但不要改数据库。
    """
    with get_cursor() as cur:
        # years：从 school_admission 去重
        cur.execute("SELECT DISTINCT year FROM school_admission WHERE year IS NOT NULL ORDER BY year")
        years = [row["year"] for row in cur.fetchall()]

        # source_provinces：从 school_admission 去重
        cur.execute("SELECT DISTINCT source_province FROM school_admission WHERE source_province IS NOT NULL AND source_province != '' ORDER BY source_province")
        source_provinces = [row["source_province"] for row in cur.fetchall()]

        # edu_levels：从 college 去重
        cur.execute("SELECT DISTINCT edu_level FROM college WHERE edu_level IS NOT NULL AND edu_level != '' ORDER BY edu_level")
        edu_levels = [row["edu_level"] for row in cur.fetchall()]

        # categories：从 school_admission 去重，去空值
        cur.execute("SELECT DISTINCT category FROM school_admission WHERE category IS NOT NULL AND category != '' ORDER BY category")
        categories = [row["category"] for row in cur.fetchall()]

        # batches：从 school_admission 去重，去空值
        cur.execute("SELECT DISTINCT batch FROM school_admission WHERE batch IS NOT NULL AND batch != '' ORDER BY batch")
        batches = [row["batch"] for row in cur.fetchall()]

    return {
        "years": years,
        "source_provinces": source_provinces,
        "edu_levels": edu_levels,
        "categories": categories,
        "batches": batches,
    }


def list_admissions(
    school_id: int,
    source_province: str | None = None,
    year: int | None = None,
    category: str | None = None,
    batch: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int, bool]:
    """查询某高校的历史投档记录。

    数据链固定 College → SchoolUnit → SchoolAdmission。

    Returns:
        (items, total, display_deduplicated)
        items: 分页后的记录列表
        total: 符合条件的总记录数（合并后）
        display_deduplicated: 是否做了展示合并
    """
    offset = max(page - 1, 0) * page_size

    # 基础查询：三表 JOIN
    base_sql = """
        FROM school_admission a
        JOIN school_unit u ON u.unit_id = a.unit_id
        JOIN college c ON c.school_id = u.school_id
        WHERE c.school_id = %(school_id)s
          AND (%(source_province)s IS NULL OR a.source_province = %(source_province)s)
          AND (%(year)s IS NULL OR a.year = %(year)s)
          AND (%(category)s IS NULL OR a.category = %(category)s)
          AND (%(batch)s IS NULL OR a.batch = %(batch)s)
    """

    params = {
        "school_id": school_id,
        "source_province": source_province,
        "year": year,
        "category": category,
        "batch": batch,
    }

    # 展示字段列表（用于精确展示合并）
    display_fields = [
        "a.source_province",
        "a.year",
        "a.category",
        "a.batch",
        "a.subject_req",
        "a.min_score",
        "a.min_rank",
        "a.control_score",
        "a.score_diff",
        "a.admit_count",
    ]
    display_select = ", ".join(display_fields)

    # 先查总数（合并后）
    count_sql = f"""
        SELECT COUNT(*) as total
        FROM (
            SELECT DISTINCT {display_select}
            {base_sql}
        ) AS deduped
    """
    with get_cursor() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()["total"]

    # 查分页数据（合并后）
    data_sql = f"""
        SELECT DISTINCT {display_select}
        {base_sql}
        ORDER BY a.year DESC, a.source_province, a.category, a.batch
        LIMIT %(page_size)s OFFSET %(offset)s
    """
    params["page_size"] = page_size
    params["offset"] = offset

    with get_cursor() as cur:
        cur.execute(data_sql, params)
        rows = cur.fetchall()

    items = []
    for row in rows:
        items.append({
            "source_province": row["source_province"],
            "year": row["year"],
            "category": row["category"],
            "batch": row["batch"],
            "subject_req": row["subject_req"],
            "min_score": float(row["min_score"]) if row["min_score"] is not None else None,
            "min_rank": int(row["min_rank"]) if row["min_rank"] is not None else None,
            "control_score": float(row["control_score"]) if row["control_score"] is not None else None,
            "score_diff": float(row["score_diff"]) if row["score_diff"] is not None else None,
            "admit_count": row["admit_count"],
        })

    # 判断是否做了展示合并：如果原始行数 > 合并后行数，说明做了合并
    raw_count_sql = f"SELECT COUNT(*) as raw_total {base_sql}"
    with get_cursor() as cur:
        cur.execute(raw_count_sql, params)
        raw_total = cur.fetchone()["raw_total"]

    display_deduplicated = raw_total > total

    return items, total, display_deduplicated
