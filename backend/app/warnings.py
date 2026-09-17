"""warnings 统一文案。

**已于 2026-09-16 全组冻结，逐字不得改写。** 见 docs/00_协作规范.md §5.4。
**2026-09-17 新增 4、5 两类**（周边交通接口 API 10，见执行书 §4.11 / §4.12），
原有三类未动。

后端负责判断触发，前端只负责展示，不各自编。
返回字符串数组，不做错误码体系，前端统一去重展示。

需要新增文案时先提，不要临时编。
"""

# 触发：空间筛选确实排除了无 Campus 高校
NO_CAMPUS_EXCLUDED = "部分符合招生条件的高校因缺少校区空间数据未参与空间筛选"

# 触发：查询或展示涉及 category 或 batch
SOURCE_VOCABULARY = "当前科类/批次使用来源数据原始口径"

# 触发：空间查询包含 CANDIDATE
INCLUDE_CANDIDATE_CAMPUS = "本次空间查询包含候选校区"

# 触发：指定高校有校区，但半径内一个 poi_transport 点都没有。
# poi_transport 覆盖不齐，抽样 200 个校区只有 73% 能在 3 km 内找到交通点，
# 所以"查不到"是常态，不能让前端显示成"周边没有站点"。
NO_TRANSPORT_DATA = "部分高校周边缺少交通设施数据"

# 触发：指定高校压根没有带几何的校区，周边查询无从做起。
# 全库 2,952 所高校只有 432 所有校区，这是**常见情况**不是边缘情况，
# 所以要和上一条分开说——否则会把"缺校区"错说成"缺交通数据"。
NO_CAMPUS_FOR_QUERY = "该校暂无可用校区数据，无法进行周边查询"


def dedupe(items: list[str]) -> list[str]:
    """去重并保持顺序。"""
    seen: set[str] = set()
    out: list[str] = []
    for w in items:
        if w and w not in seen:
            seen.add(w)
            out.append(w)
    return out
