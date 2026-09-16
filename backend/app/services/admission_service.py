"""招生筛选服务 —— **所有者：倪嵩**。

见 docs/00_协作规范.md §3 文件所有权表。莫炜钧只调用，不修改。

────────────────────────────────────────────────────────────────
倪嵩：这个文件现在是个**占位桩**，接口签名已经按契约 §4.10 冻结，你实现函数体即可。
不要改签名 —— /api/search 依赖它。
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

参考 SQL 骨架：

    select distinct u.school_id
    from school_admission a
    join school_unit u on u.unit_id = a.unit_id
    where (%(source_province)s is null or a.source_province = %(source_province)s)
      and (%(year)s            is null or a.year            = %(year)s)
      and (%(category)s        is null or a.category        = %(category)s)
      and (%(batch)s           is null or a.batch           = %(batch)s)

注意：category / batch 是来源原始口径，不要做全国统一映射（§1.3）。
"""

from typing import Any


class AdmissionFilterNotImplemented(NotImplementedError):
    """招生筛选尚未实现。

    /api/search 捕获它并返回 501，而不是**悄悄忽略招生条件**——
    忽略会返回"看起来对但其实没筛"的结果，那比报错更糟。
    """


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

    raise AdmissionFilterNotImplemented(
        "招生筛选服务尚未实现（app/services/admission_service.py，负责人：倪嵩）。"
        "在此之前 /api/search 的 admission 条件不可用，以免返回未筛选的结果。"
    )


def filter_meta() -> dict[str, Any]:
    """给 /api/meta/filters 用的字典。同样由倪嵩实现。"""
    raise AdmissionFilterNotImplemented(
        "/api/meta/filters 尚未实现（负责人：倪嵩）。"
    )
