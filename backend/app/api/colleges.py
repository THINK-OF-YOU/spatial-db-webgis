"""通用 College 接口。

所有者：莫炜钧。契约见《任务执行书》§4.2 / §4.3。
"""

from fastapi import APIRouter, HTTPException, Query

from app.schemas.common import MAX_PAGE_SIZE, paginate
from app.services import college_service as svc

router = APIRouter(tags=["college"])


@router.get("/colleges")
def list_colleges(
    q: str | None = Query(None, description="按学校名称模糊搜索"),
    edu_level: str | None = Query(None, description="办学层次，如 本科 / 高职（专科）"),
    reg_province: str | None = Query(
        None,
        description="登记地区。注意：库里该字段装的是**市名**（如 长春市），不是省名。",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    items, total = svc.list_colleges(
        q=q,
        edu_level=edu_level,
        reg_province=reg_province,
        page=page,
        page_size=page_size,
    )
    return paginate(items, total, page, page_size)


@router.get("/colleges/{school_id}")
def get_college(school_id: int):
    college = svc.get_college(school_id)
    if college is None:
        raise HTTPException(status_code=404, detail=f"未找到 school_id={school_id} 的高校")

    return {
        "data": {
            "college": college,
            "campuses": svc.list_campuses_of(school_id),
            "data_availability": svc.college_availability(school_id),
        }
    }
