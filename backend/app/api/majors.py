"""专业接口 —— **所有者：莫炜钧**。

见 docs/00_协作规范.md §3 文件所有权表。

────────────────────────────────────────────────────────────────
**2026-09-17 新增。** 此前专业语义链全空（契约里也据此写了
`major_mapping: false` 的示例），数据库恢复把专业表达与 Tier 1 标准映射
入库之后，专业查询才成立，才有的这三个接口。

对接文档：**docs/02_专业API对接文档.md**（前端照那一份写即可，比本文件细）。

    GET /api/colleges/{school_id}/majors      某高校的招生专业录取事实
    GET /api/majors                           教育部标准专业目录（字典）
    GET /api/majors/{major_id}/colleges       反查：招这个标准专业的高校

⚠️ 三个接口都绕不开同一件事：**专业是两层语义**。

    来源招生专业表达   raw_major_name   覆盖率 98.62%
    标准专业           std_major        覆盖率 37.80%（Tier 1 精确映射）

  未建立标准映射 **不代表** 该校没有这个专业。所以：

  - 列表接口同时返回两层，`std_major` 可以是 null，**但那一行不会被丢掉**；
  - 两个「按标准专业查」的入口（`std_major_id` 筛选、反查接口）只覆盖
    那 37.80%，一律带 STD_MAJOR_FILTER_COVERAGE 警告，不许静默。
────────────────────────────────────────────────────────────────
"""

from fastapi import APIRouter, HTTPException, Query

from app.schemas.common import MAX_PAGE_SIZE, paginate
from app.services import major_service
from app.warnings import SOURCE_VOCABULARY, STD_MAJOR_FILTER_COVERAGE, dedupe

router = APIRouter(tags=["major"])

# 契约写死的取值，越界一律 422，不静默钳制（同 transport 的 mode 口径）。
MAPPING_VALUES = ("all", "mapped", "unmapped")


@router.get("/colleges/{school_id}/majors")
def college_majors(
    school_id: int,
    source_province: str | None = Query(None, description="生源省，如 河南省"),
    year: int | None = Query(None, ge=2000, le=2100, description="年份，如 2024"),
    category: str | None = Query(None, description="科类/选科，来源原始口径，如 理科"),
    batch: str | None = Query(None, description="批次，来源原始口径，如 本科一批"),
    candidate_rank: int | None = Query(
        None,
        ge=1,
        description="考生位次。提供后按 expr_id 返回当前考试上下文中最接近位次的代表事实。",
    ),
    std_major_id: int | None = Query(
        None,
        description="按标准专业筛选。⚠️ 只覆盖已建立 Tier 1 映射的记录（37.80%），"
                    "查不到不代表该校没招这个专业。",
    ),
    mapping: str | None = Query(
        None,
        description=f"只看某一类映射状态，取值 {MAPPING_VALUES}。"
                    "mapped=已归入标准专业；unmapped=未归一（**专业是存在的**）。",
    ),
    q: str | None = Query(None, description="按来源专业名或标准专业名模糊搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    """某高校的招生专业录取事实。

    一行 = 一个(来源专业表达 × 生源省 × 年份 × 科类 × 批次)组合下的录取分数。
    来源专业表达和标准专业**分两个字段返回，不合并**——见文件头说明。
    """
    if mapping is not None and mapping not in MAPPING_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"mapping 只允许 {list(MAPPING_VALUES)}，收到 {mapping!r}",
        )

    if candidate_rank is not None and (
        not source_province or year is None or not category
    ):
        raise HTTPException(
            status_code=422,
            detail="candidate_rank 模式必须同时提供 source_province、year、category",
        )

    items, total, display_deduplicated, no_name = major_service.list_college_majors(
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

    warnings = []
    # 按标准专业筛 = 只在 37.80% 的已映射事实上检索，必须说清楚，
    # 否则前端会把「只有 5 条」当成「该校只招 5 个专业」。
    if std_major_id is not None:
        warnings.append(STD_MAJOR_FILTER_COVERAGE)
    if category is not None or batch is not None:
        warnings.append(SOURCE_VOCABULARY)

    result = paginate(items, total, page, page_size, dedupe(warnings))
    # 与 /admissions 的 display_deduplicated 同口径：仅对**全部展示字段完全一致**
    # 的记录做精确合并（契约 §4.4），不是数据库去重。
    result["display_deduplicated"] = display_deduplicated
    # 该校被排除在外的、来源未提供专业名的记录条数（全库 22,325 条中的一部分）。
    # 不放进 warnings[]：那是全组冻结的文案表，且这里要的是一个**数字**，
    # 前端可以自己组织句子（「另有 46 条录取记录来源未提供专业名」）。
    result["facts_without_major_name"] = no_name
    result["candidate_profile_applied"] = candidate_rank is not None
    result["candidate_profile"] = (
        {
            "source_province": source_province,
            "year": year,
            "category": category,
            "batch": batch,
            "rank": candidate_rank,
        }
        if candidate_rank is not None
        else None
    )
    return result


@router.get("/majors")
def list_std_majors(
    q: str | None = Query(None, description="按标准专业名或专业代码模糊搜索"),
    education_level: str | None = Query(
        None, description="培养层次，库里真实取值只有 本科 / 专科 / 职业本科"
    ),
    discipline: str | None = Query(None, description="学科门类，如 工学"),
    category: str | None = Query(None, description="专业类，如 计算机类"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    """教育部标准专业目录（字典）。

    全表 1,874 行、1,711 个专业名，与高校无关。前端用它做「按标准专业筛选」的
    搜索框/下拉，拿到 `major_id` 后再传给另两个接口。
    """
    items, total = major_service.list_std_majors(
        q=q,
        education_level=education_level,
        discipline=discipline,
        category=category,
        page=page,
        page_size=page_size,
    )
    return paginate(items, total, page, page_size)


@router.get("/majors/{major_id}/colleges")
def colleges_by_major(
    major_id: int,
    source_province: str | None = Query(None, description="生源省，如 河南省"),
    year: int | None = Query(None, ge=2000, le=2100, description="年份，如 2024"),
    category: str | None = Query(None, description="科类/选科，来源原始口径"),
    batch: str | None = Query(None, description="批次，来源原始口径"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    """反查：招收这个**标准专业**的高校。

    ⚠️ 纯 Tier 1 查询，**天生只覆盖 37.7984% 的录取事实**。查到 20 所不代表
    全国只有 20 所招这个专业。响应里一律带覆盖警告，前端必须展示，
    **不要**把这个列表渲染成「开设该专业的全部高校」。
    """
    major = major_service.get_std_major(major_id)
    if major is None:
        raise HTTPException(
            status_code=404, detail=f"未找到 major_id={major_id} 的标准专业"
        )

    items, total = major_service.list_colleges_by_major(
        major_id=major_id,
        source_province=source_province,
        year=year,
        category=category,
        batch=batch,
        page=page,
        page_size=page_size,
    )

    warnings = [STD_MAJOR_FILTER_COVERAGE]
    if category is not None or batch is not None:
        warnings.append(SOURCE_VOCABULARY)

    result = paginate(items, total, page, page_size, dedupe(warnings))
    # 把反查的是哪个标准专业一并回给前端，省一次请求，也避免前端拿错 id 时
    # 渲染出一份「名字对不上」的列表却看不出来。
    result["std_major"] = major
    return result
