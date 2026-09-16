"""warnings 统一文案。

**已于 2026-09-16 全组冻结，逐字不得改写。** 见 docs/00_协作规范.md §5.4。

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


def dedupe(items: list[str]) -> list[str]:
    """去重并保持顺序。"""
    seen: set[str] = set()
    out: list[str] = []
    for w in items:
        if w and w not in seen:
            seen.add(w)
            out.append(w)
    return out
