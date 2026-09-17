"""筛选元数据接口 —— **所有者：倪嵩**。

见 docs/00_协作规范.md §3 文件所有权表。莫炜钧在骨架阶段先把文件建好
并在 main.py 注册，倪嵩直接实现本文件，**不要改 main.py**。

────────────────────────────────────────────────────────────────
倪嵩：契约见《任务执行书》§4.5。

    GET /api/meta/filters

返回当前数据库**真实可用**的：
    years / source_provinces / edu_levels / categories / batches

要点（附录 B 第四条）：
- 从数据库真实值生成，不要硬编码全国 category / batch。
- category / batch 是来源原始口径，不要自行造全国统一映射。
- 可以去空值、合理排序，但不要改数据库。

参考：school_admission 里 2023—2025 三年、30 个生源省、
category 17 个值、batch 174 个值；college.edu_level 只有两个值。
────────────────────────────────────────────────────────────────
"""

from fastapi import APIRouter

from app.services import admission_service
from app.warnings import SOURCE_VOCABULARY, dedupe

router = APIRouter(tags=["meta"])


@router.get("/meta/filters")
def meta_filters():
    """返回筛选器元数据：年份、生源省、办学层次、科类、批次。

    category / batch 为来源数据原始口径，未做全国统一标准化。
    """
    meta = admission_service.filter_meta()

    # 涉及 category / batch，加来源口径警告
    warnings = dedupe([SOURCE_VOCABULARY])

    return {
        "data": meta,
        "warnings": warnings,
    }
