"""招生筛选服务 —— **所有者：倪嵩**。

见 docs/00_协作规范.md §3 文件所有权表。本文件归倪嵩，**他人只读**；
确实要改先在群里说，由 owner 改（下面那次是经授权的一次性例外）。

────────────────────────────────────────────────────────────────
**已于 2026-09-17 实现**（此前是占位桩，骨架里的 AdmissionFilterNotImplemented
类已随之移除）。本文件现在提供三个函数：

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
