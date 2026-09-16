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

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["admission"])


@router.get("/colleges/{school_id}/admissions")
def college_admissions(school_id: int):
    raise HTTPException(
        status_code=501,
        detail=(
            "/api/colleges/{school_id}/admissions 尚未实现"
            "（owner：倪嵩，见《任务执行书》附录 B）。"
        ),
    )
