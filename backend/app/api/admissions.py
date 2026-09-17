"""学校历史投档接口 —— **所有者：倪嵩**。

见 docs/00_协作规范.md §3 文件所有权表。莫炜钧在骨架阶段先把文件建好
并在 main.py 注册，倪嵩直接实现本文件，**不要改 main.py**。

────────────────────────────────────────────────────────────────
倪嵩：契约见《任务执行书》§4.4。

    GET /api/colleges/{school_id}/admissions
    可选参数：source_province、year、category、batch、page、page_size
    只有 school_id 必填。

数据链固定 College → SchoolUnit → SchoolAdmission（§1.3、附录 B 第三条）。

要点：
- 缺失值返回 null，不填 0、不推算。
- 数据库原始记录不删不改不去重；接口层**仅允许**对"最终返回给用户的
  全部展示字段完全一致"的记录做精确展示合并，并返回
  display_deduplicated=true。不要做模糊合并或自然键推断。
- category / batch 是来源原始口径。
────────────────────────────────────────────────────────────────
"""

from fastapi import APIRouter, HTTPException, Query

from app.schemas.common import MAX_PAGE_SIZE, paginate
from app.services import admission_service
from app.warnings import SOURCE_VOCABULARY, dedupe

router = APIRouter(tags=["admission"])


@router.get("/colleges/{school_id}/admissions")
def college_admissions(
    school_id: int,
    source_province: str | None = Query(None, description="生源省，如 湖南省 / 浙江省"),
    year: int | None = Query(None, ge=2000, le=2100, description="年份，如 2024"),
    category: str | None = Query(None, description="科类/选科，来源原始口径，如 物理类 / 综合"),
    batch: str | None = Query(None, description="批次，来源原始口径，如 本科批 / 普通类一段"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    """查询某高校的历史投档录取记录。

    数据链：College → SchoolUnit → SchoolAdmission。
    缺失值返回 null，不填 0、不推算。
    category / batch 为来源数据原始口径。
    """
    items, total, display_deduplicated = admission_service.list_admissions(
        school_id=school_id,
        source_province=source_province,
        year=year,
        category=category,
        batch=batch,
        page=page,
        page_size=page_size,
    )

    # 构造 warnings
    warnings = []
    # 涉及 category 或 batch 筛选，加来源口径警告
    if category is not None or batch is not None:
        warnings.append(SOURCE_VOCABULARY)
    # 展示合并**不再往 warnings 里塞文案**：
    # 契约 §4.4 写的是「明确 display_deduplicated=true 或等价提示」，下面第 71 行
    # 已经返回了这个字段，前端据此展示即可，信息没丢。
    # warnings[] 的文案是冻结的（§5.4，目前 5 类），新增一类要全组确认，
    # 不能在这里临时编一句。原先那句「本次结果已对完全一致的展示记录做精确去重」
    # 就是临时编的，不在冻结表里，2026-09-17 移除（莫炜钧经授权改）。
    warnings = dedupe(warnings)

    result = paginate(items, total, page, page_size, warnings)
    # 附加展示合并标记 —— 这是契约 §4.4 认可的展示合并信号
    result["display_deduplicated"] = display_deduplicated

    return result
