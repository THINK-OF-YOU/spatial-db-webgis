"""ScoreRange 只读查询服务。

V2.0 只负责把一个精确分数解析为可解释的参考位次。解析成功后，调用方
继续把该位次交给既有 CandidateProfile V1；本模块不参与高校筛选。
"""

from typing import Any, Literal

from app.db.pool import get_cursor


ScoreResolutionStatus = Literal[
    "resolved",
    "ambiguous",
    "not_found",
    "unsupported_context",
]


def score_range_contexts() -> list[dict[str, Any]]:
    """返回具备精确 score + cumulative_count 数据的考试上下文。

    ``valid_score_count`` 只统计能得到唯一累计人数的分数；歧义分数另行
    计数。category 为 NULL/空字符串的记录明确排除，不做任何科类猜测。
    """
    sql = """
        WITH score_groups AS (
            SELECT
                source_province,
                year,
                category,
                score,
                COUNT(DISTINCT cumulative_count) AS rank_count
            FROM score_range
            WHERE source_province IS NOT NULL
              AND source_province <> ''
              AND year IS NOT NULL
              AND category IS NOT NULL
              AND category <> ''
              AND score IS NOT NULL
              AND cumulative_count IS NOT NULL
            GROUP BY source_province, year, category, score
        )
        SELECT
            source_province,
            year,
            category,
            COUNT(*) FILTER (WHERE rank_count = 1) AS valid_score_count,
            COUNT(*) FILTER (WHERE rank_count > 1) AS ambiguous_score_count,
            MIN(score) AS min_score,
            MAX(score) AS max_score
        FROM score_groups
        GROUP BY source_province, year, category
        HAVING COUNT(*) > 0
        ORDER BY source_province, year DESC, category
    """
    with get_cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    return [
        {
            "source_province": row["source_province"],
            "year": row["year"],
            "category": row["category"],
            "valid_score_count": int(row["valid_score_count"]),
            "ambiguous_score_count": int(row["ambiguous_score_count"]),
            "min_score": int(row["min_score"]),
            "max_score": int(row["max_score"]),
        }
        for row in rows
    ]


def resolve_score_rank(
    *,
    source_province: str,
    year: int,
    category: str,
    score: int,
) -> dict[str, Any]:
    """按考试上下文和整数分数精确解析累计人数。

    batch 不参与解析：正式库审计未发现同一省/年/科类/分数跨 batch 重叠，
    现有歧义也无法由 batch 消除。字段本身是最终依据；不做邻近分数、插值
    或 category NULL 映射。
    """
    sql = """
        SELECT
            EXISTS (
                SELECT 1
                FROM score_range
                WHERE source_province = %(source_province)s
                  AND year = %(year)s
                  AND category = %(category)s
                  AND score IS NOT NULL
                  AND cumulative_count IS NOT NULL
            ) AS context_supported,
            COUNT(*) FILTER (WHERE score = %(score)s) AS matching_row_count,
            COUNT(DISTINCT cumulative_count)
                FILTER (WHERE score = %(score)s) AS distinct_rank_count,
            MIN(cumulative_count)
                FILTER (WHERE score = %(score)s) AS sole_rank
        FROM score_range
        WHERE source_province = %(source_province)s
          AND year = %(year)s
          AND category = %(category)s
          AND score IS NOT NULL
          AND cumulative_count IS NOT NULL
    """
    params = {
        "source_province": source_province,
        "year": year,
        "category": category,
        "score": score,
    }
    with get_cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()

    if not row["context_supported"]:
        status: ScoreResolutionStatus = "unsupported_context"
        resolved_rank = None
    elif row["matching_row_count"] == 0:
        status = "not_found"
        resolved_rank = None
    elif row["distinct_rank_count"] > 1:
        status = "ambiguous"
        resolved_rank = None
    else:
        status = "resolved"
        resolved_rank = int(row["sole_rank"])

    return {
        "source_province": source_province,
        "year": year,
        "category": category,
        "score": score,
        "status": status,
        "resolved_rank": resolved_rank,
        "matching_row_count": int(row["matching_row_count"]),
        "distinct_rank_count": int(row["distinct_rank_count"]),
    }
