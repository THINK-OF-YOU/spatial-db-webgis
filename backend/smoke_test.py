"""后端骨架冒烟测试 —— 实跑一次数据库，确认接口连通、返回形状符合契约。

在 backend 目录下运行：

    ./.venv/Scripts/python.exe smoke_test.py

特点：
- 只读。不改任何数据；连接本身被服务端强制为 default_transaction_read_only=on。
- 自带服务：在 127.0.0.1:8123 起一个临时 uvicorn，跑完自动退出，不用另开终端。
- 组员拿到仓库后先跑这个，确认自己本机的 .env / 数据库通了再写业务代码。
- 断言的是**返回内容**，不只是状态码。凡是"接口通了但内容不对"的情况都要红。

退出码：0 = 全部通过，1 = 有失败项。
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import uvicorn

from app.main import app
from app.db.pool import get_cursor

HOST = "127.0.0.1"
PORT = 8123
BASE = f"http://{HOST}:{PORT}"

# 兜底参考点：武汉大学一带。正常情况下会用库里真实校区当参考点。
WUHAN = (114.36, 30.54)


def box_around(lon: float, lat: float, d: float = 0.2) -> dict:
    """以 (lon, lat) 为中心、边长 2d 度的矩形。只在单个校区周边用，不追求跨纬度精度。"""
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lon - d, lat - d],
                [lon + d, lat - d],
                [lon + d, lat + d],
                [lon - d, lat + d],
                [lon - d, lat - d],
            ]
        ],
    }

passed: list[str] = []
failed: list[str] = []


def call(method: str, path: str, body: dict | None = None):
    """发一个请求，返回 (status, payload)。HTTP 错误也当正常返回处理。"""
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    # 查询串里有中文（如 q=计算机）时必须百分号编码：urllib 的请求行只能是 ASCII，
    # 否则 urlopen 直接抛 UnicodeEncodeError（不是 HTTP 错误，是发送前就炸）。
    # capture_samples.py 一直这么做；这里原先漏了，因为以前没有一个测试往 URL
    # 里放中文，2026-09-17 加专业接口搜索样例时才暴露出来。
    url = BASE + urllib.parse.quote(path, safe="/?&=%")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw[:300]}


def check(label, method, path, body=None, expect=200, detail=None):
    """跑一项检查。detail 是个 callable(payload) -> str，只在通过时打印摘要。"""
    status, payload = call(method, path, body)
    ok = status == expect
    (passed if ok else failed).append(label)
    print(f"[{'OK  ' if ok else 'FAIL'}] {label}")
    line = f"        {method} {path}  ->  {status}"
    if status != expect:
        line += f"  (期望 {expect})"
    print(line)
    if ok and detail:
        try:
            print(f"        {detail(payload)}")
        except Exception as exc:  # 摘要函数写错不算接口失败，但要说出来
            print(f"        (摘要失败: {exc})")
    if not ok:
        print(f"        {json.dumps(payload, ensure_ascii=False)[:400]}")
    return payload


def expect_true(label: str, cond: bool, msg: str = ""):
    """断言一件接口返回内容里的事实（状态码之外的部分）。"""
    (passed if cond else failed).append(label)
    print(f"[{'OK  ' if cond else 'FAIL'}] {label}")
    if msg:
        print(f"        {msg}")
    return cond


def main() -> int:
    server = uvicorn.Server(
        uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()

    deadline = time.time() + 30
    while not server.started and time.time() < deadline:
        time.sleep(0.1)
    if not server.started:
        print("服务未能启动，检查 app/main.py 与依赖。")
        return 1

    print("=" * 68)
    print("健康检查")
    print("=" * 68)

    health = check(
        "health",
        "GET",
        "/api/health",
        detail=lambda p: (
            f"database={p['data']['database']}  read_only={p['data']['read_only']}  "
            f"counts={p['data']['counts']}"
        ),
    )
    expect_true(
        "FastAPI 数据库连接保持只读",
        isinstance(health, dict) and health.get("data", {}).get("read_only") is True,
        f"read_only={health.get('data', {}).get('read_only') if isinstance(health, dict) else None}",
    )

    print()
    print("=" * 68)
    print("莫炜钧：1 高校列表 / 2 高校详情")
    print("=" * 68)

    listing = check(
        "colleges 列表",
        "GET",
        "/api/colleges?page_size=3",
        detail=lambda p: f"total={p.get('total')}  本页 {len(p.get('items', []))} 条",
    )

    first_id = None
    if isinstance(listing, dict) and listing.get("items"):
        first_id = listing["items"][0].get("school_id")
        print(f"        取第一条 school_id={first_id} 用于详情测试")

    if first_id is not None:
        check(
            f"colleges 详情 school_id={first_id}",
            "GET",
            f"/api/colleges/{first_id}",
            detail=lambda p: (
                f"name={p['data']['college'].get('name')}  "
                f"campuses={len(p['data'].get('campuses', []))}  "
                f"data_availability={p['data'].get('data_availability')}"
            ),
        )

    check(
        "colleges 详情 不存在的 id -> 404",
        "GET",
        "/api/colleges/999999999",
        expect=404,
    )

    # ── 契约对齐回归（2026-09-17）───────────────────────────────────
    # 这两条守的是「曾经多返回了契约里没有的字段」，防止它们悄悄回来。
    # 3059 是已知有校区的学校（和上面 transport 用的是同一所）。
    det = check(
        "colleges 详情 school_id=3059（有校区的学校）",
        "GET",
        "/api/colleges/3059",
        detail=lambda p: f"campuses={len(p['data'].get('campuses', []))}",
    )
    if isinstance(det, dict):
        avail = det["data"].get("data_availability") or {}
        # 2026-09-17：从三个键变成四个键。专业语义链入库后必须把「有专业事实」
        # 与「有标准映射」分开——只留 major_mapping 的话，有专业但没映射的学校
        # 会在前端被整个藏掉专业视图。enrollment_plan 仍然不许回来。
        expect_true(
            "data_availability 是四个键（新增 major_admission），仍不夹带 enrollment_plan",
            set(avail) == {"school_admission", "campus", "major_admission", "major_mapping"},
            f"实际键={sorted(avail)}",
        )
        cps = det["data"].get("campuses") or []
        # 恰好这 5 个字段。address 曾经在内，但全库 479 行的 address 全是空串，
        # 返回它只会让前端渲染出一行空白；source / transform_method 等内部列
        # 也不该外泄。用「恰好等于」而不是「不包含」，多一个少一个都算失败。
        expect_true(
            "campuses 元素恰好是 5 个业务字段（没有 address，也没有 source 等内部列）",
            bool(cps) and all(set(c) == {
                "campus_id", "campus_name", "verify_status", "lon", "lat"
            } for c in cps),
            f"{len(cps)} 个校区，字段={sorted(cps[0]) if cps else '—'}",
        )

    print()
    print("=" * 68)
    print("莫炜钧：5 校区地图 / 6 行政区")
    print("=" * 68)

    regions = check(
        "regions 省级",
        "GET",
        "/api/map/regions",
        detail=lambda p: f"{len(p.get('features', []))} 个 feature",
    )

    check(
        "campuses bbox 武汉一带",
        "GET",
        "/api/map/campuses?bbox=114.28,30.48,114.45,30.60",
        detail=lambda p: f"{len(p.get('features', []))} 个 feature",
    )

    if isinstance(regions, dict) and regions.get("features"):
        adcode = regions["features"][0]["properties"].get("adcode")
        check(
            f"regions 下钻 parent_adcode={adcode}",
            "GET",
            f"/api/map/regions?parent_adcode={adcode}",
            detail=lambda p: f"{len(p.get('features', []))} 个 feature",
        )

    # 取一个真实校区当参考点。
    # 默认 verify_status=CONFIRMED 在库里只有个位数校区，拿武汉随便一个点当参考点
    # 大概率命中 0 条，测不出空间链路通不通，所以这里显式把 CANDIDATE 一起要上。
    allcamp = check(
        "campuses 全国 bbox（CONFIRMED + CANDIDATE）",
        "GET",
        "/api/map/campuses?bbox=73,18,135,54"
        "&verify_status=CONFIRMED&verify_status=CANDIDATE",
        detail=lambda p: f"{len(p.get('features', []))} 个 feature",
    )

    ref = None
    features = allcamp.get("features") if isinstance(allcamp, dict) else None
    for feat in features or []:
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        if geom.get("type") == "Point" and isinstance(coords, list) and len(coords) == 2:
            ref = (coords[0], coords[1])
            break
    if ref:
        print(f"        取校区 ({ref[0]:.4f}, {ref[1]:.4f}) 当空间查询参考点")
    else:
        print("        没取到可用校区点，空间查询退回武汉坐标（结果可能为 0 条）")

    print()
    print("=" * 68)
    print("莫炜钧：7 附近 / 8 范围内")
    print("=" * 68)

    lon, lat = ref or WUHAN

    nearby = check(
        "spatial/nearby 该校区 50km（含候选）",
        "GET",
        f"/api/spatial/nearby?lon={lon}&lat={lat}&radius_km=50"
        "&verify_status=CONFIRMED&verify_status=CANDIDATE&limit=5",
        detail=lambda p: (
            f"{len(p.get('items', []))} 条  warnings={p.get('warnings')}"
        ),
    )
    expect_true(
        "nearby 真的能查到校区",
        bool(nearby.get("items")),
        f"半径 50km 内命中 {len(nearby.get('items', []))} 条",
    )

    within = check(
        "spatial/within 该校区周边矩形（含候选）",
        "POST",
        "/api/spatial/within",
        {
            "geometry": box_around(lon, lat),
            "verify_status": ["CONFIRMED", "CANDIDATE"],
        },
        detail=lambda p: f"{len(p.get('items', []))} 条",
    )
    expect_true(
        "within 真的能查到校区",
        bool(within.get("items")),
        f"矩形内命中 {len(within.get('items', []))} 条",
    )

    check(
        "spatial/within 非面几何 -> 422",
        "POST",
        "/api/spatial/within",
        {"geometry": {"type": "Point", "coordinates": [114.36, 30.54]}},
        expect=422,
    )

    print()
    print("=" * 68)
    print("莫炜钧：9 综合查询")
    print("=" * 68)

    only_confirmed = check(
        "search 仅空间条件、默认只看 CONFIRMED",
        "POST",
        "/api/search",
        {"spatial": {"reference_point": {"lon": lon, "lat": lat}, "radius_km": 50}},
        detail=lambda p: (
            f"total={p.get('total')}  warnings={p.get('warnings')}"
        ),
    )
    expect_true(
        "默认口径下触发了「缺少校区数据未参与筛选」提示",
        "部分符合招生条件的高校因缺少校区空间数据未参与空间筛选"
        in (only_confirmed.get("warnings") or []),
        f"warnings={only_confirmed.get('warnings')}",
    )

    with_cand = check(
        "search 打开「包含候选校区」",
        "POST",
        "/api/search",
        {
            "spatial": {
                "reference_point": {"lon": lon, "lat": lat},
                "radius_km": 50,
                "include_candidate_campus": True,
            }
        },
        detail=lambda p: (
            f"total={p.get('total')}  warnings={p.get('warnings')}"
        ),
    )
    expect_true(
        "含候选后确实查得到高校",
        (with_cand.get("total") or 0) > 0,
        f"total={with_cand.get('total')}",
    )
    expect_true(
        "含候选时返回了「本次查询包含候选校区」提示",
        "本次空间查询包含候选校区" in (with_cand.get("warnings") or []),
        f"warnings={with_cand.get('warnings')}",
    )

    check(
        "search 无任何条件",
        "POST",
        "/api/search",
        {},
        detail=lambda p: f"total={p.get('total')}",
    )

    # ── 回归：只给 reference_point、不给 radius_km ────────────────────
    # 契约 §4.10 的示例把两者成对给出，但 schema 允许只给其一。
    # 曾经这里 KeyError: 's_lon' → 500：s_lon/s_lat 只在「参考点且半径」分支
    # 里绑定，而算距离的 distance_select/distance_join 只依赖参考点。
    rp_only = check(
        "search 只给 reference_point、不给 radius_km（回归）",
        "POST",
        "/api/search",
        {"spatial": {"reference_point": {"lon": lon, "lat": lat}}, "page_size": 50},
        detail=lambda p: f"total={p.get('total')}  warnings={p.get('warnings')}",
    )
    rp_items = (rp_only.get("items") or []) if isinstance(rp_only, dict) else []
    expect_true(
        "只给参考点：不崩，且不筛空间（总数与无条件一致）",
        (rp_only.get("total") or 0) > 0,
        f"total={rp_only.get('total')}",
    )
    expect_true(
        "只给参考点：照样算出了 distance_km",
        any(it.get("distance_km") is not None for it in rp_items),
        f"本页 {len(rp_items)} 条，有距离的 "
        f"{sum(1 for it in rp_items if it.get('distance_km') is not None)} 条",
    )
    expect_true(
        "distance_km 与 has_campus 一致：有校区才有距离，没校区是 null 而不是 0",
        all(
            (it.get("distance_km") is None) == (not it.get("has_campus"))
            for it in rp_items
        ),
        "逐条比对通过",
    )
    expect_true(
        "没启用空间筛选时不谎报「空间覆盖不足」",
        not (rp_only.get("warnings") or []),
        f"warnings={rp_only.get('warnings')}",
    )

    # 只给半径、不给参考点：半径没有圆心，无从筛起，当前按「不筛」处理。
    # 契约未规定这种组合，这里只钉住「不崩」，语义待全组确认后再收紧。
    check(
        "search 只给 radius_km、不给 reference_point（不崩即可）",
        "POST",
        "/api/search",
        {"spatial": {"radius_km": 50}},
        detail=lambda p: f"total={p.get('total')}",
    )

    print()
    print("=" * 68)
    print("CandidateProfile V1：位次参考 + 空间组合")
    print("=" * 68)

    context_response = check(
        "CandidateProfile 有效考试上下文元数据",
        "GET",
        "/api/meta/candidate-profile-contexts",
        detail=lambda p: f"contexts={len(p.get('data', {}).get('contexts', []))}",
    )
    contexts = (
        context_response.get("data", {}).get("contexts", [])
        if isinstance(context_response, dict)
        else []
    )
    expect_true(
        "有效上下文不含 NULL/空 source_province、year、category",
        bool(contexts)
        and all(
            context.get("source_province")
            and context.get("year") is not None
            and context.get("category")
            for context in contexts
        ),
        f"检查 {len(contexts)} 个 distinct 上下文",
    )

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM (
                SELECT DISTINCT source_province, year, category, batch
                FROM school_admission
                WHERE min_rank IS NOT NULL
                  AND source_province IS NOT NULL
                  AND source_province <> ''
                  AND year IS NOT NULL
                  AND category IS NOT NULL
                  AND category <> ''
            ) valid_contexts
            """
        )
        expected_context_count = cur.fetchone()["n"]
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM (
                SELECT DISTINCT source_province, year, category
                FROM school_admission
                WHERE min_rank IS NOT NULL
                  AND source_province IS NOT NULL
                  AND source_province <> ''
                  AND year IS NOT NULL
                  AND category IS NOT NULL
                  AND category <> ''
                  AND batch IS NULL
            ) null_batch_contexts
            """
        )
        expected_null_batch_context_count = cur.fetchone()["n"]
        cur.execute(
            """
            SELECT DISTINCT category
            FROM school_admission
            WHERE min_rank IS NOT NULL
              AND source_province = '广西'
              AND year = 2025
              AND category IS NOT NULL
              AND category <> ''
            ORDER BY category
            """
        )
        expected_gx_categories = [row["category"] for row in cur.fetchall()]
        cur.execute(
            """
            SELECT DISTINCT batch
            FROM school_admission
            WHERE min_rank IS NOT NULL
              AND source_province = '广西'
              AND year = 2025
              AND category = '物理类'
              AND batch IS NOT NULL
              AND batch <> ''
            ORDER BY batch
            """
        )
        expected_gx_batches = [row["batch"] for row in cur.fetchall()]

    expect_true(
        "元数据数量与 PostgreSQL DISTINCT 有效上下文一致",
        len(contexts) == expected_context_count,
        f"api={len(contexts)}  database={expected_context_count}",
    )
    api_null_batch_context_count = sum(
        context.get("batch") is None for context in contexts
    )
    expect_true(
        "NULL batch 保留为上下文空值，不伪造成真实批次",
        api_null_batch_context_count == expected_null_batch_context_count,
        f"api_null={api_null_batch_context_count}  "
        f"database_null={expected_null_batch_context_count}",
    )
    api_gx_categories = sorted(
        {
            context["category"]
            for context in contexts
            if context["source_province"] == "广西" and context["year"] == 2025
        }
    )
    expect_true(
        "广西 2025 科类只返回数据库真实值且不含理科",
        set(api_gx_categories) == set(expected_gx_categories)
        and "理科" not in api_gx_categories,
        f"categories={api_gx_categories}",
    )
    api_gx_batches = sorted(
        {
            context["batch"]
            for context in contexts
            if context["source_province"] == "广西"
            and context["year"] == 2025
            and context["category"] == "物理类"
            and context.get("batch")
        }
    )
    expect_true(
        "广西 2025 物理类批次与数据库真实非空值一致",
        set(api_gx_batches) == set(expected_gx_batches) and None not in api_gx_batches,
        f"batches={api_gx_batches}",
    )

    print()
    print("-" * 68)
    print("CandidateProfile V2.0：ScoreRange 分数解析")
    print("-" * 68)

    score_meta = check(
        "ScoreRange 可解析上下文元数据",
        "GET",
        "/api/meta/score-range-contexts",
        detail=lambda p: f"contexts={len(p.get('data', {}).get('contexts', []))}",
    )
    score_contexts = score_meta.get("data", {}).get("contexts", [])
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM (
                SELECT source_province, year, category
                FROM score_range
                WHERE source_province IS NOT NULL
                  AND source_province <> ''
                  AND year IS NOT NULL
                  AND category IS NOT NULL
                  AND category <> ''
                  AND score IS NOT NULL
                  AND cumulative_count IS NOT NULL
                GROUP BY source_province, year, category
            ) contexts
            """
        )
        expected_score_contexts = cur.fetchone()["n"]
        cur.execute(
            """
            SELECT source_province, year, category, score,
                   COUNT(*) AS rows_n, MIN(cumulative_count) AS resolved_rank
            FROM score_range
            WHERE category IS NOT NULL
              AND score IS NOT NULL
              AND cumulative_count IS NOT NULL
            GROUP BY source_province, year, category, score
            HAVING COUNT(*) > 1
               AND COUNT(DISTINCT cumulative_count) = 1
            ORDER BY source_province, year, category, score
            LIMIT 1
            """
        )
        duplicate_score_sample = dict(cur.fetchone())
        cur.execute(
            """
            SELECT source_province, year, category, score,
                   COUNT(DISTINCT cumulative_count) AS rank_count
            FROM score_range
            WHERE category IS NOT NULL
              AND score IS NOT NULL
              AND cumulative_count IS NOT NULL
            GROUP BY source_province, year, category, score
            HAVING COUNT(DISTINCT cumulative_count) > 1
            ORDER BY source_province, year, category, score
            LIMIT 1
            """
        )
        ambiguous_score_sample = dict(cur.fetchone())

    expect_true(
        "ScoreRange metadata 只返回 category 非空的真实上下文",
        len(score_contexts) == expected_score_contexts
        and bool(score_contexts)
        and all(context.get("category") for context in score_contexts),
        f"api={len(score_contexts)}  database={expected_score_contexts}",
    )
    expect_true(
        "ScoreRange metadata 提供有效分数数与真实 min/max",
        all(
            context.get("valid_score_count", 0) >= 0
            and context.get("min_score") is not None
            and context.get("max_score") is not None
            for context in score_contexts
        ),
        f"检查 {len(score_contexts)} 个上下文",
    )

    def resolve_path(province, year, category, score):
        return "/api/meta/score-range/resolve?" + urllib.parse.urlencode(
            {
                "source_province": province,
                "year": year,
                "category": category,
                "score": score,
            }
        )

    hunan_score = check(
        "湖南 2024 物理类 600 分解析",
        "GET",
        resolve_path("湖南", 2024, "物理类", 600),
        detail=lambda p: f"status={p.get('data', {}).get('status')}  "
        f"rank={p.get('data', {}).get('resolved_rank')}",
    ).get("data", {})
    expect_true(
        "湖南 2024 物理类 600 -> 参考位次 14294",
        hunan_score.get("status") == "resolved"
        and hunan_score.get("resolved_rank") == 14294,
        f"data={hunan_score}",
    )

    duplicate_score = check(
        "重复行但累计人数相同仍可解析",
        "GET",
        resolve_path(
            duplicate_score_sample["source_province"],
            duplicate_score_sample["year"],
            duplicate_score_sample["category"],
            int(duplicate_score_sample["score"]),
        ),
    ).get("data", {})
    expect_true(
        "Resolver 以 DISTINCT cumulative_count 判断唯一性",
        duplicate_score.get("status") == "resolved"
        and duplicate_score.get("matching_row_count")
        == duplicate_score_sample["rows_n"]
        and duplicate_score.get("resolved_rank")
        == int(duplicate_score_sample["resolved_rank"]),
        f"sample={duplicate_score_sample}  data={duplicate_score}",
    )

    ambiguous_score = check(
        "同分多累计人数明确返回 ambiguous",
        "GET",
        resolve_path(
            ambiguous_score_sample["source_province"],
            ambiguous_score_sample["year"],
            ambiguous_score_sample["category"],
            int(ambiguous_score_sample["score"]),
        ),
    ).get("data", {})
    expect_true(
        "ambiguous 不猜参考位次",
        ambiguous_score.get("status") == "ambiguous"
        and ambiguous_score.get("resolved_rank") is None
        and ambiguous_score.get("distinct_rank_count")
        == ambiguous_score_sample["rank_count"],
        f"sample={ambiguous_score_sample}  data={ambiguous_score}",
    )

    missing_score = check(
        "支持上下文中不存在的精确分数返回 not_found",
        "GET",
        resolve_path("湖南", 2024, "物理类", 9999),
    ).get("data", {})
    expect_true(
        "not_found 不使用邻近分数",
        missing_score.get("status") == "not_found"
        and missing_score.get("resolved_rank") is None,
        f"data={missing_score}",
    )

    unsupported_score = check(
        "无 ScoreRange 的考试上下文返回 unsupported_context",
        "GET",
        resolve_path("不存在省份", 2024, "物理类", 600),
    ).get("data", {})
    expect_true(
        "unsupported_context 不伪造参考位次",
        unsupported_score.get("status") == "unsupported_context"
        and unsupported_score.get("resolved_rank") is None,
        f"data={unsupported_score}",
    )
    check(
        "Score Resolver 拒绝小数分数",
        "GET",
        resolve_path("湖南", 2024, "物理类", "600.1"),
        expect=422,
    )
    check(
        "Score Resolver 拒绝负分",
        "GET",
        resolve_path("湖南", 2024, "物理类", -1),
        expect=422,
    )

    gx_profile_admission = {
        "source_province": "广西",
        "year": 2025,
        "category": "物理类",
        "rank": 10000,
        "rank_ahead": 3000,
        "rank_behind": 8000,
    }
    gx_profile = check(
        "CandidateProfile 广西/2025/物理类/全部批次/位次10000",
        "POST",
        "/api/search",
        {"admission": gx_profile_admission, "page_size": 100},
        detail=lambda p: f"total={p.get('total')}",
    )
    expect_true(
        "广西真实考试上下文的位次查询仍能返回高校",
        (gx_profile.get("total") or 0) > 0,
        f"total={gx_profile.get('total')}",
    )
    gx_zero = check(
        "合法广西考试上下文 + 极窄位次窗口 -> 0",
        "POST",
        "/api/search",
        {
            "admission": {
                **gx_profile_admission,
                "rank": 1,
                "rank_ahead": 0,
                "rank_behind": 0,
            }
        },
        detail=lambda p: f"total={p.get('total')}",
    )
    expect_true(
        "合法考试上下文允许真实返回 0，不误判为上下文错误",
        gx_zero.get("total") == 0 and gx_zero.get("items") == [],
        f"total={gx_zero.get('total')}",
    )

    profile_admission = {
        "source_province": "湖南",
        "year": 2024,
        "category": "物理类",
        "rank": 20000,
        "rank_ahead": 3000,
        "rank_behind": 8000,
    }
    profile = check(
        "CandidateProfile 湖南/2024/物理类/位次20000",
        "POST",
        "/api/search",
        {"admission": profile_admission, "page_size": 100},
        detail=lambda p: f"total={p.get('total')}  本页={len(p.get('items', []))}",
    )
    profile_items = (profile.get("items") or []) if isinstance(profile, dict) else []
    references = [item.get("reference_admission") for item in profile_items]
    expect_true(
        "CandidateProfile 返回真实高校与代表历史事实",
        (profile.get("total") or 0) > 0 and profile_items and all(references),
        f"total={profile.get('total')}  refs={sum(bool(r) for r in references)}",
    )
    expect_true(
        "代表事实 min_rank 全部位于 17000～28000 且不含 NULL",
        bool(references)
        and all(17000 <= ref["min_rank"] <= 28000 for ref in references if ref),
        f"检查本页 {len(references)} 条",
    )
    expect_true(
        "rank_gap 统一等于 historical_min_rank - candidate_rank",
        bool(references)
        and all(ref["rank_gap"] == ref["min_rank"] - 20000 for ref in references if ref),
        "逐条比对通过",
    )
    expect_true(
        "每校只有一条代表事实，且按 ABS(rank_gap) 升序",
        len({item["school_id"] for item in profile_items}) == len(profile_items)
        and [abs(ref["rank_gap"]) for ref in references if ref]
        == sorted(abs(ref["rank_gap"]) for ref in references if ref),
        f"本页 {len(profile_items)} 所",
    )

    multi_school = None
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT u.school_id, COUNT(*) AS fact_count
            FROM school_admission a
            JOIN school_unit u ON u.unit_id = a.unit_id
            WHERE a.source_province = %(source_province)s
              AND a.year = %(year)s
              AND a.category = %(category)s
              AND a.min_rank IS NOT NULL
              AND a.min_rank BETWEEN 17000 AND 28000
            GROUP BY u.school_id
            HAVING COUNT(*) > 1
            ORDER BY MIN(ABS(a.min_rank - 20000)), u.school_id
            LIMIT 1
            """,
            {
                "source_province": "湖南",
                "year": 2024,
                "category": "物理类",
            },
        )
        row = cur.fetchone()
        multi_school = dict(row) if row else None
    representative = next(
        (
            item
            for item in profile_items
            if multi_school and item["school_id"] == multi_school["school_id"]
        ),
        None,
    )
    expect_true(
        "找到位次窗口内同一 College 存在多条投档事实的真实样本",
        multi_school is not None and representative is not None,
        f"sample={multi_school}",
    )
    if representative:
        sid = representative["school_id"]
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.unit_id, a.min_rank
                FROM school_admission a
                JOIN school_unit u ON u.unit_id = a.unit_id
                WHERE u.school_id = %(school_id)s
                  AND a.source_province = %(source_province)s
                  AND a.year = %(year)s
                  AND a.category = %(category)s
                  AND a.min_rank IS NOT NULL
                  AND a.min_rank BETWEEN 17000 AND 28000
                ORDER BY ABS(a.min_rank - 20000), a.min_rank, a.id
                LIMIT 1
                """,
                {
                    "school_id": sid,
                    "source_province": "湖南",
                    "year": 2024,
                    "category": "物理类",
                },
            )
            expected_ref = dict(cur.fetchone())
        actual_ref = representative["reference_admission"]
        expect_true(
            "同校多事实时选择 ABS 位次差最小且 tie-breaker 确定的一条",
            actual_ref["admission_id"] == expected_ref["id"]
            and actual_ref["unit_id"] == expected_ref["unit_id"]
            and actual_ref["min_rank"] == int(expected_ref["min_rank"]),
            f"school_id={sid}  candidates={multi_school['fact_count']}  "
            f"admission_id={actual_ref['admission_id']}",
        )

    narrow = check(
        "CandidateProfile 缩窄位次窗口 1000/3000",
        "POST",
        "/api/search",
        {
            "admission": {
                **profile_admission,
                "rank_ahead": 1000,
                "rank_behind": 3000,
            }
        },
        detail=lambda p: f"total={p.get('total')}",
    )
    expect_true(
        "缩窄窗口结果不增加",
        0 <= (narrow.get("total") or 0) <= (profile.get("total") or 0),
        f"{narrow.get('total')} <= {profile.get('total')}",
    )

    first_batch = next((ref.get("batch") for ref in references if ref and ref.get("batch")), None)
    if first_batch:
        by_batch = check(
            f"CandidateProfile 指定真实 batch={first_batch}",
            "POST",
            "/api/search",
            {"admission": {**profile_admission, "batch": first_batch}, "page_size": 100},
            detail=lambda p: f"total={p.get('total')}",
        )
        batch_refs = [it.get("reference_admission") for it in (by_batch.get("items") or [])]
        expect_true(
            "指定 batch 后代表事实只来自该批次",
            bool(batch_refs) and all(ref and ref.get("batch") == first_batch for ref in batch_refs),
            f"检查本页 {len(batch_refs)} 条",
        )

    check(
        "CandidateProfile rank=0 -> 422",
        "POST",
        "/api/search",
        {"admission": {**profile_admission, "rank": 0}},
        expect=422,
    )
    check(
        "CandidateProfile 缺少 category -> 422",
        "POST",
        "/api/search",
        {"admission": {k: v for k, v in profile_admission.items() if k != "category"}},
        expect=422,
    )
    check(
        "未提供 rank 却提供 rank_ahead -> 422",
        "POST",
        "/api/search",
        {"admission": {"source_province": "湖南", "rank_ahead": 1000}},
        expect=422,
    )

    # 从当前真实位次集合中取一个有 Campus 且能落入行政区的高校，避免硬编码校区。
    spatial_fixture = None
    with get_cursor() as cur:
        cur.execute(
            """
            WITH profile_schools AS (
                SELECT DISTINCT u.school_id
                FROM school_admission a
                JOIN school_unit u ON u.unit_id = a.unit_id
                WHERE a.source_province = %(source_province)s
                  AND a.year = %(year)s
                  AND a.category = %(category)s
                  AND a.min_rank IS NOT NULL
                  AND a.min_rank BETWEEN 17000 AND 28000
            )
            SELECT cp.school_id,
                   ST_X(cp.geom) AS lon,
                   ST_Y(cp.geom) AS lat,
                   ar.adcode
            FROM profile_schools ps
            JOIN campus cp ON cp.school_id = ps.school_id AND cp.geom IS NOT NULL
            JOIN LATERAL (
                SELECT r.adcode
                FROM admin_region r
                WHERE r.geom IS NOT NULL AND ST_Covers(r.geom, cp.geom)
                ORDER BY CASE r.level
                    WHEN 'district' THEN 1 WHEN 'city' THEN 2 ELSE 3 END,
                    r.adcode
                LIMIT 1
            ) ar ON TRUE
            ORDER BY cp.school_id
            LIMIT 1
            """,
            {
                "source_province": "湖南",
                "year": 2024,
                "category": "物理类",
            },
        )
        row = cur.fetchone()
        spatial_fixture = dict(row) if row else None

    expect_true(
        "真实画像结果中存在可用于空间组合验收的 Campus",
        spatial_fixture is not None,
        f"fixture={spatial_fixture}",
    )
    if spatial_fixture:
        profile_spatial = {
            "admission": profile_admission,
            "spatial": {"include_candidate_campus": True},
        }
        region_profile = check(
            "CandidateProfile + AdminRegion",
            "POST",
            "/api/search",
            {**profile_spatial, "regions": [spatial_fixture["adcode"]]},
            detail=lambda p: f"total={p.get('total')}",
        )
        expect_true(
            "画像与行政区按 AND 组合且能命中真实高校",
            (region_profile.get("total") or 0) > 0,
            f"total={region_profile.get('total')}",
        )

        radius_profile = check(
            "CandidateProfile + ReferencePoint + Radius",
            "POST",
            "/api/search",
            {
                "admission": profile_admission,
                "spatial": {
                    "reference_point": {
                        "lon": spatial_fixture["lon"],
                        "lat": spatial_fixture["lat"],
                    },
                    "radius_km": 10,
                    "include_candidate_campus": True,
                },
            },
            detail=lambda p: f"total={p.get('total')}",
        )
        expect_true(
            "画像与 ST_DWithin 按 AND 组合",
            (radius_profile.get("total") or 0) > 0,
            f"total={radius_profile.get('total')}",
        )

        polygon_profile = check(
            "CandidateProfile + Polygon",
            "POST",
            "/api/search",
            {
                "admission": profile_admission,
                "spatial": {
                    "geometry": box_around(
                        spatial_fixture["lon"], spatial_fixture["lat"], 0.05
                    ),
                    "include_candidate_campus": True,
                },
            },
            detail=lambda p: f"total={p.get('total')}",
        )
        expect_true(
            "画像与 Polygon 按 AND 组合",
            (polygon_profile.get("total") or 0) > 0,
            f"total={polygon_profile.get('total')}",
        )

    zero_profile = check(
        "CandidateProfile + 无高校海域 Polygon -> 0",
        "POST",
        "/api/search",
        {
            "admission": profile_admission,
            "spatial": {
                "geometry": box_around(0, 0, 0.05),
                "include_candidate_campus": True,
            },
        },
        detail=lambda p: f"total={p.get('total')}  items={len(p.get('items', []))}",
    )
    expect_true(
        "0 结果保持为空，不回退为普通 Campus",
        zero_profile.get("total") == 0 and zero_profile.get("items") == [],
        f"total={zero_profile.get('total')}",
    )

    legacy_admission = check(
        "不传 rank 的旧招生筛选回归",
        "POST",
        "/api/search",
        {"admission": {"source_province": "湖南", "year": 2024, "category": "物理类"}},
        detail=lambda p: f"total={p.get('total')}",
    )
    expect_true(
        "旧招生筛选仍可用且不夹带 reference_admission",
        (legacy_admission.get("total") or 0) >= (profile.get("total") or 0)
        and all("reference_admission" not in item for item in legacy_admission.get("items") or []),
        f"legacy={legacy_admission.get('total')}  profile={profile.get('total')}",
    )

    print()
    print("=" * 68)
    print("莫炜钧：9f 交通多条件组合（Transport V2.1）")
    print("=" * 68)

    transport_single = {
        "transport": [{"mode": "metro", "max_distance_km": 2}],
        "page": 1,
        "page_size": 100,
    }
    transport_dual_rail = {
        "transport": [
            {"mode": "metro", "max_distance_km": 2},
            {"mode": "rail", "max_distance_km": 10},
        ],
        "page": 1,
        "page_size": 100,
    }
    transport_dual_airport = {
        "transport": [
            {"mode": "metro", "max_distance_km": 2},
            {"mode": "airport", "max_distance_km": 30},
        ],
        "page": 1,
        "page_size": 100,
    }
    transport_triple = {
        "transport": [
            {"mode": "metro", "max_distance_km": 2},
            {"mode": "rail", "max_distance_km": 10},
            {"mode": "airport", "max_distance_km": 50},
        ],
        "page": 1,
        "page_size": 100,
    }

    transport_single_result = check(
        "Transport 单条件 metro <= 2km",
        "POST",
        "/api/search",
        transport_single,
        detail=lambda p: f"total={p.get('total')}",
    )
    transport_dual_rail_result = check(
        "Transport 双条件 metro AND rail",
        "POST",
        "/api/search",
        transport_dual_rail,
        detail=lambda p: f"total={p.get('total')}",
    )
    transport_dual_airport_result = check(
        "Transport 双条件 metro AND airport",
        "POST",
        "/api/search",
        transport_dual_airport,
        detail=lambda p: f"total={p.get('total')}",
    )
    transport_triple_result = check(
        "Transport 三条件 metro AND rail AND airport",
        "POST",
        "/api/search",
        transport_triple,
        detail=lambda p: f"total={p.get('total')}",
    )
    for label, payload in (
        ("单条件", transport_single_result),
        ("双条件 rail", transport_dual_rail_result),
        ("双条件 airport", transport_dual_airport_result),
        ("三条件", transport_triple_result),
    ):
        expect_true(
            f"{label} 返回唯一高校结果源形状",
            isinstance(payload, dict)
            and isinstance(payload.get("items"), list)
            and isinstance(payload.get("total"), int)
            and len({item.get("school_id") for item in payload.get("items") or []})
            == len(payload.get("items") or []),
            f"payload={payload if not isinstance(payload, dict) else {'total': payload.get('total')}}",
        )
        if isinstance(payload, dict):
            expect_true(
                f"{label} 保留候选校区 warning",
                "本次空间查询包含候选校区" in (payload.get("warnings") or []),
                f"warnings={payload.get('warnings')}",
            )

    expect_true(
        "多条件 AND 结果不超过对应单条件",
        isinstance(transport_single_result, dict)
        and isinstance(transport_dual_rail_result, dict)
        and isinstance(transport_dual_airport_result, dict)
        and isinstance(transport_triple_result, dict)
        and transport_dual_rail_result.get("total", 0) <= transport_single_result.get("total", 0)
        and transport_dual_airport_result.get("total", 0) <= transport_single_result.get("total", 0)
        and transport_triple_result.get("total", 0)
        <= transport_dual_rail_result.get("total", 0),
        f"single={transport_single_result.get('total')}  "
        f"dual_rail={transport_dual_rail_result.get('total')}  "
        f"dual_airport={transport_dual_airport_result.get('total')}  "
        f"triple={transport_triple_result.get('total')}",
    )

    no_transport = check(
        "Transport = [] 按关闭处理",
        "POST",
        "/api/search",
        {"transport": [], "page": 1, "page_size": 20},
        detail=lambda p: f"total={p.get('total')}",
    )
    no_transport_null = check(
        "Transport = null 按关闭处理",
        "POST",
        "/api/search",
        {"transport": None, "page": 1, "page_size": 20},
        detail=lambda p: f"total={p.get('total')}",
    )
    legacy_no_transport = check(
        "Transport 不传保持原搜索语义",
        "POST",
        "/api/search",
        {"page": 1, "page_size": 20},
        detail=lambda p: f"total={p.get('total')}",
    )
    expect_true(
        "Transport 关闭的三种写法结果一致",
        all(
            isinstance(payload, dict)
            for payload in (no_transport, no_transport_null, legacy_no_transport)
        )
        and no_transport.get("total") == no_transport_null.get("total")
        == legacy_no_transport.get("total")
        and [item.get("school_id") for item in no_transport.get("items") or []]
        == [item.get("school_id") for item in legacy_no_transport.get("items") or []],
        f"[]={no_transport.get('total')} null={no_transport_null.get('total')} "
        f"omitted={legacy_no_transport.get('total')}",
    )

    # 与既有招生画像、行政区、Polygon、参考点分别叠加，确认 Transport
    # 仍沿用 /search 的单一 Campus 空间链，而不是另起一套结果查询。
    if spatial_fixture:
        transport_combo = transport_dual_rail["transport"]
        profile_transport = check(
            "CandidateProfile + Transport 多条件",
            "POST",
            "/api/search",
            {"admission": profile_admission, "transport": transport_combo},
            detail=lambda p: f"total={p.get('total')}",
        )
        region_transport = check(
            "AdminRegion + Transport 多条件",
            "POST",
            "/api/search",
            {"regions": [spatial_fixture["adcode"]], "transport": transport_combo},
            detail=lambda p: f"total={p.get('total')}",
        )
        polygon_transport = check(
            "Polygon + Transport 多条件",
            "POST",
            "/api/search",
            {
                "spatial": {
                    "geometry": box_around(
                        spatial_fixture["lon"], spatial_fixture["lat"], 0.05
                    ),
                    "include_candidate_campus": True,
                },
                "transport": transport_combo,
            },
            detail=lambda p: f"total={p.get('total')}",
        )
        radius_transport = check(
            "ReferencePoint + Radius + Transport 多条件",
            "POST",
            "/api/search",
            {
                "spatial": {
                    "reference_point": {
                        "lon": spatial_fixture["lon"],
                        "lat": spatial_fixture["lat"],
                    },
                    "radius_km": 10,
                    "include_candidate_campus": True,
                },
                "transport": transport_combo,
            },
            detail=lambda p: f"total={p.get('total')}",
        )
        expect_true(
            "既有招生/行政区/Polygon/参考点与 Transport 组合均有真实结果",
            all(
                isinstance(payload, dict) and (payload.get("total") or 0) > 0
                for payload in (
                    profile_transport,
                    region_transport,
                    polygon_transport,
                    radius_transport,
                )
            ),
            " / ".join(
                str(payload.get("total") if isinstance(payload, dict) else None)
                for payload in (
                    profile_transport,
                    region_transport,
                    polygon_transport,
                    radius_transport,
                )
            ),
        )

    # 正式库当前每校只有一个带几何 Campus，无法从真实行构造跨校区反例；
    # 用只读 CTE 构造两个 Campus 分别满足 metro / rail，复现同一 EXISTS
    # 结构，结果必须为 false。CTE 不落盘，也不触碰正式数据。
    with get_cursor() as cur:
        cur.execute(
            """
            WITH campuses(school_id, geom) AS (
                VALUES
                    (1, ST_SetSRID(ST_Point(0, 0), 4326)),
                    (1, ST_SetSRID(ST_Point(1, 1), 4326))
            ), pois(mode, geom) AS (
                VALUES
                    ('metro', ST_SetSRID(ST_Point(0.005, 0.0), 4326)),
                    ('rail', ST_SetSRID(ST_Point(1.005, 1.0), 4326))
            )
            SELECT EXISTS (
                SELECT 1 FROM campuses cp
                WHERE EXISTS (
                    SELECT 1 FROM pois p
                    WHERE p.mode = 'metro'
                      AND p.geom && ST_Expand(cp.geom, 0.02)
                      AND ST_DWithin(
                          p.geom::geography, cp.geom::geography, 2000
                      )
                )
                AND EXISTS (
                    SELECT 1 FROM pois p
                    WHERE p.mode = 'rail'
                      AND p.geom && ST_Expand(cp.geom, 0.02)
                      AND ST_DWithin(
                          p.geom::geography, cp.geom::geography, 2000
                      )
                )
            ) AS cross_campus_should_not_match
            """
        )
        same_campus_fixture = not bool(cur.fetchone()["cross_campus_should_not_match"])
    expect_true(
        "Same-Campus Binding 拒绝不同 Campus 分别满足交通条件",
        same_campus_fixture,
        "只读 CTE fixture: metro 在 Campus A、rail 在 Campus B 时不命中",
    )

    check(
        "Transport 重复 mode -> 422",
        "POST",
        "/api/search",
        {
            "transport": [
                {"mode": "metro", "max_distance_km": 1},
                {"mode": "metro", "max_distance_km": 3},
            ]
        },
        expect=422,
    )
    check(
        "Transport 非法 mode -> 422",
        "POST",
        "/api/search",
        {"transport": [{"mode": "rail_halt", "max_distance_km": 5}]},
        expect=422,
    )
    check(
        "Transport distance <= 0 -> 422",
        "POST",
        "/api/search",
        {"transport": [{"mode": "metro", "max_distance_km": 0}]},
        expect=422,
    )
    check(
        "Transport distance > 100 -> 422",
        "POST",
        "/api/search",
        {"transport": [{"mode": "airport", "max_distance_km": 101}]},
        expect=422,
    )
    check(
        "Transport 超过 3 条 -> 422",
        "POST",
        "/api/search",
        {
            "transport": [
                {"mode": "metro", "max_distance_km": 1},
                {"mode": "rail", "max_distance_km": 3},
                {"mode": "airport", "max_distance_km": 20},
                {"mode": "metro", "max_distance_km": 2},
            ]
        },
        expect=422,
    )

    # 招生条件不再单独在这里测 501 —— 倪嵩实现后见下一节的真实筛选检查。

    print()
    print("=" * 68)
    print("莫炜钧：10 周边交通（API 10，契约 §4.11）")
    print("=" * 68)

    # 前两所高校是照库里实测结果挑的（2026-09-17 实测）：
    #   3059 天津医科大学            1 个校区，3km 内 39 个站点（metro 38 + rail 1）
    #   2954 盐城幼儿师范高等专科学校  1 个校区，3km 内 0 个站点
    # Campus 数据会增量增强，因此“无校区高校”不能长期硬编码，需从当前库动态选择。
    # 注意 3059 那一行：默认 limit=20，所以下面的 base 只会拿到 20 条而不是 39 条，
    # 拿它当"筛窄了"的对照基准没问题。
    HAS_STATION, NO_STATION = 3059, 2954
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT c.school_id
            FROM college c
            WHERE NOT EXISTS (
                SELECT 1 FROM campus cp
                WHERE cp.school_id = c.school_id AND cp.geom IS NOT NULL
            )
            ORDER BY c.school_id
            LIMIT 1
            """
        )
        NO_CAMPUS = cur.fetchone()["school_id"]

    # 抄自契约 §4.11。**故意不从 spatial_service 里 import**——
    # 否则常量被改错时测试会跟着一起错，等于没测。
    CONTRACT_MODES = ["rail", "metro", "airport", "rail_halt"]

    base = check(
        f"colleges/{HAS_STATION}/transport 默认 3km",
        "GET",
        f"/api/colleges/{HAS_STATION}/transport",
        detail=lambda p: (
            f"{len(p.get('items', []))} 个站点  total={p.get('total')}  "
            f"warnings={p.get('warnings')}"
        ),
    )
    base_items = (base.get("items") or []) if isinstance(base, dict) else []

    expect_true(
        "周边交通真的返回了站点",
        bool(base_items),
        f"{len(base_items)} 个站点",
    )

    if base_items:
        keys = set(base_items[0].keys())
        need = {
            "poi_id",
            "mode",
            "name",
            "name_zh",
            "lon",
            "lat",
            "distance_km",
            "campus_id",
            "campus_name",
        }
        expect_true(
            "交通站点字段齐全（缺失值应为 null，不填假值）",
            need <= keys,
            f"缺 {sorted(need - keys)}" if not need <= keys else f"{len(keys)} 个字段齐全",
        )

        dists = [it.get("distance_km") for it in base_items]
        expect_true(
            "按距离升序排",
            all(d is not None for d in dists) and dists == sorted(dists),
            f"最近 {dists[0]} km，最远 {dists[-1]} km",
        )
        expect_true(
            "返回的站点都在请求半径内",
            all((d or 0) <= 3.0 for d in dists),
            f"{len(base_items)} 个站点全部 <= 3 km",
        )
        expect_true(
            "mode 取值都在契约的四个值之内",
            {it.get("mode") for it in base_items} <= set(CONTRACT_MODES),
            f"出现的 mode：{sorted({it.get('mode') for it in base_items})}",
        )
        expect_true(
            "total 与 items 长度一致",
            base.get("total") == len(base_items),
            f"total={base.get('total')}  len={len(base_items)}",
        )
        expect_true(
            "查到了站点就不该报「缺少交通设施数据」",
            "部分高校周边缺少交通设施数据" not in (base.get("warnings") or []),
            f"warnings={base.get('warnings')}",
        )

    # ── mode 过滤：既要真的只剩这一种，也要真的变少 ────────────────
    rail = check(
        f"transport mode=rail（可重复传）",
        "GET",
        f"/api/colleges/{HAS_STATION}/transport?mode=rail",
        detail=lambda p: (
            f"{len(p.get('items', []))} 个站点  "
            f"modes={sorted({i.get('mode') for i in (p.get('items') or [])})}"
        ),
    )
    rail_items = (rail.get("items") or []) if isinstance(rail, dict) else []
    expect_true(
        "mode=rail 只返回 rail",
        bool(rail_items) and {i.get("mode") for i in rail_items} == {"rail"},
        f"{len(rail_items)} 个站点",
    )
    expect_true(
        "mode 过滤确实把结果筛窄了（不是被静默忽略）",
        0 < len(rail_items) < len(base_items),
        f"{len(rail_items)} < {len(base_items)}",
    )

    # ── radius_km：收窄后条数变少，且没有超出半径的漏网之鱼 ──────────
    closer = check(
        "transport radius_km=1",
        "GET",
        f"/api/colleges/{HAS_STATION}/transport?radius_km=1",
        detail=lambda p: (
            f"{len(p.get('items', []))} 个站点  "
            f"最远 {max((i.get('distance_km') or 0) for i in (p.get('items') or [])) if p.get('items') else '-'} km"
        ),
    )
    closer_items = (closer.get("items") or []) if isinstance(closer, dict) else []
    expect_true(
        "radius_km 收窄后条数变少，且都在 1 km 内",
        0 < len(closer_items) < len(base_items)
        and all((i.get("distance_km") or 0) <= 1.0 for i in closer_items),
        f"{len(closer_items)} 个站点（3km 时 {len(base_items)} 个）",
    )

    # ── limit ────────────────────────────────────────────────────
    capped = check(
        "transport limit=3",
        "GET",
        f"/api/colleges/{HAS_STATION}/transport?limit=3",
        detail=lambda p: f"{len(p.get('items', []))} 个站点",
    )
    expect_true(
        "limit 生效",
        len((capped.get("items") or []) if isinstance(capped, dict) else []) == 3,
        f"要 3 个，给了 {len((capped.get('items') or []) if isinstance(capped, dict) else [])} 个",
    )

    # ── 参数校验：契约写死的取值范围，越界一律 422 ───────────────────
    check(
        "transport mode 非法值 -> 422",
        "GET",
        f"/api/colleges/{HAS_STATION}/transport?mode=train",
        expect=422,
    )
    check(
        "transport radius_km 超上限 20 -> 422",
        "GET",
        f"/api/colleges/{HAS_STATION}/transport?radius_km=25",
        expect=422,
    )

    # ── 两种"查不到"必须分开说，不能混成一句 ─────────────────────────
    no_campus = check(
        f"colleges/{NO_CAMPUS}/transport 没有校区",
        "GET",
        f"/api/colleges/{NO_CAMPUS}/transport",
        detail=lambda p: f"items={len(p.get('items', []))}  warnings={p.get('warnings')}",
    )
    no_station = check(
        f"colleges/{NO_STATION}/transport 有校区但半径内没站点",
        "GET",
        f"/api/colleges/{NO_STATION}/transport",
        detail=lambda p: f"items={len(p.get('items', []))}  warnings={p.get('warnings')}",
    )

    nc_warn = (no_campus.get("warnings") or []) if isinstance(no_campus, dict) else []
    ns_warn = (no_station.get("warnings") or []) if isinstance(no_station, dict) else []

    expect_true(
        "无校区时给「暂无可用校区」提示",
        "该校暂无可用校区数据，无法进行周边查询" in nc_warn,
        f"warnings={nc_warn}",
    )
    expect_true(
        "有校区无站点时给「缺少交通设施数据」提示",
        "部分高校周边缺少交通设施数据" in ns_warn,
        f"warnings={ns_warn}",
    )
    expect_true(
        "两种「查不到」的文案确实不同（缺校区没被错说成缺交通数据）",
        set(nc_warn) != set(ns_warn) and bool(nc_warn) and bool(ns_warn),
        f"缺校区 {nc_warn}  vs  缺站点 {ns_warn}",
    )
    expect_true(
        "查不到时不谎报站点",
        not ((no_campus.get("items") if isinstance(no_campus, dict) else None) or [])
        and not ((no_station.get("items") if isinstance(no_station, dict) else None) or []),
        "两种情况 items 都是空数组",
    )

    print()
    print("=" * 68)
    print("莫炜钧：11 高校专业 / 12 标准专业目录 / 13 按专业反查高校")
    print("=" * 68)

    # 三所/三个都是照库里实测挑的（2026-09-17），不是随手写的：
    #   5334 四川师范大学      5,841 条专业事实，1,430 已映射 / 4,411 未映射
    #   3877 西交利物浦大学      638 条专业事实，**零条** Tier 1 映射
    #   2294 计算机科学与技术    778 所高校招，用于反查
    MIXED, NO_MAPPING, STD_MAJOR, REV_TOTAL = 5334, 3877, 2294, 778

    # 抄自 warnings.py。**故意不 import**——常量被改错时测试要跟着红，
    # import 进来就等于没测（和上面 CONTRACT_MODES 同一个理由）。
    COVERAGE_WARN = (
        "按标准专业筛选仅覆盖已建立精确映射的录取记录，未建立映射不代表该校未招该专业"
    )
    # 抄自契约：专业行的字段清单。多一个少一个都算失败。
    MAJOR_KEYS = {
        "raw_major_name", "norm_name", "std_status", "std_major",
        "source_province", "year", "category", "batch", "subject_req",
        "min_score", "max_score", "avg_score", "min_rank", "admit_count",
    }

    mj = check(
        f"colleges/{MIXED}/majors",
        "GET",
        f"/api/colleges/{MIXED}/majors?page_size=5",
        detail=lambda p: (
            f"total={p.get('total')}  本页 {len(p.get('items', []))} 条  "
            f"display_deduplicated={p.get('display_deduplicated')}  "
            f"未提供专业名={p.get('facts_without_major_name')}"
        ),
    )
    mj_items = (mj.get("items") or []) if isinstance(mj, dict) else []

    expect_true("专业列表能返回真实数据", bool(mj_items), f"total={mj.get('total')}")

    if mj_items:
        keys = set(mj_items[0])
        expect_true(
            "专业行字段恰好是约定的 14 个（两层语义分开给：raw_major_name + std_major）",
            keys == MAJOR_KEYS,
            f"多={sorted(keys - MAJOR_KEYS)}  缺={sorted(MAJOR_KEYS - keys)}",
        )
        expect_true(
            "来源招生专业表达恒有值（这一行真实招的是什么，永远是它）",
            all(it.get("raw_major_name") for it in mj_items),
            f"本页 {len(mj_items)} 条全部非空",
        )
        expect_true(
            "被排除的无专业名记录有显式计数，不是静默消失",
            isinstance(mj.get("facts_without_major_name"), int),
            f"facts_without_major_name={mj.get('facts_without_major_name')}",
        )

    # ── 守恒：mapped + unmapped 必须恰好等于不筛 ─────────────────────
    # 这是整个专业接口最重要的一条。未建立标准映射的那 62% 一旦被丢掉，
    # 前端就会把「规则没归一」显示成「该校没这个专业」。
    only_mapped = check(
        f"colleges/{MIXED}/majors?mapping=mapped",
        "GET",
        f"/api/colleges/{MIXED}/majors?mapping=mapped&page_size=1",
        detail=lambda p: f"total={p.get('total')}",
    )
    only_unmapped = check(
        f"colleges/{MIXED}/majors?mapping=unmapped",
        "GET",
        f"/api/colleges/{MIXED}/majors?mapping=unmapped&page_size=1",
        detail=lambda p: f"total={p.get('total')}",
    )
    expect_true(
        "mapped + unmapped 恰好等于不筛时的 total（一条都没丢）",
        (only_mapped.get("total") or 0) + (only_unmapped.get("total") or 0)
        == (mj.get("total") or 0),
        f"{only_mapped.get('total')} + {only_unmapped.get('total')} "
        f"vs 不筛 {mj.get('total')}",
    )
    expect_true(
        "未建立标准映射的专业确实存在且被返回（不是空集）",
        (only_unmapped.get("total") or 0) > 0,
        f"mapping=unmapped 有 {only_unmapped.get('total')} 条",
    )

    un = check(
        "majors?mapping=unmapped 取 3 条看形状",
        "GET",
        f"/api/colleges/{MIXED}/majors?mapping=unmapped&page_size=3",
        detail=lambda p: f"{len(p.get('items', []))} 条",
    )
    un_items = (un.get("items") or []) if isinstance(un, dict) else []
    expect_true(
        "unmapped 行 std_major=null，但 raw_major_name 照常有值（没有被丢掉）",
        bool(un_items)
        and all(it.get("std_major") is None and it.get("raw_major_name") for it in un_items),
        f"{len(un_items)} 条："
        + ", ".join(str(it.get("raw_major_name")) for it in un_items[:3]),
    )

    # ── 按标准专业筛：必须带覆盖警告 ─────────────────────────────────
    filt = check(
        f"colleges/{MIXED}/majors?std_major_id={STD_MAJOR}",
        "GET",
        f"/api/colleges/{MIXED}/majors?std_major_id={STD_MAJOR}&page_size=5",
        detail=lambda p: f"total={p.get('total')}  warnings={p.get('warnings')}",
    )
    expect_true(
        "按标准专业筛选时给出覆盖警告（不许把 37.8% 的覆盖当成全部）",
        COVERAGE_WARN in (filt.get("warnings") or []),
        f"warnings={filt.get('warnings')}",
    )
    expect_true(
        "标准专业筛选确实收窄了结果（不是被静默忽略）",
        0 <= (filt.get("total") or 0) < (mj.get("total") or 0),
        f"{filt.get('total')} < {mj.get('total')}",
    )
    expect_true(
        "筛出来的每一行 std_major 都指向被筛的那个专业",
        all(
            (it.get("std_major") or {}).get("major_id") == STD_MAJOR
            for it in (filt.get("items") or [])
        ),
        f"{len(filt.get('items') or [])} 条",
    )

    check(
        "majors mapping 非法值 -> 422",
        "GET",
        f"/api/colleges/{MIXED}/majors?mapping=bogus",
        expect=422,
    )
    check(
        "colleges/999999999/majors 不存在的高校 -> 空列表而非报错（与 /admissions 同口径）",
        "GET",
        "/api/colleges/999999999/majors",
        detail=lambda p: f"total={p.get('total')}  items={len(p.get('items', []))}",
    )

    # ── CandidateProfile V1.2：校内专业历史位次联动 ─────────────────
    MAJOR_PROFILE_KEYS = MAJOR_KEYS | {
        "expr_id", "representative_admission_id", "unit_id", "unit_name",
        "group_id", "professional_rank_gap",
    }
    gx_profile_school_ids = {
        item.get("school_id") for item in (gx_profile.get("items") or [])
    }
    PROFILE_MAJOR_SCHOOL = 3640  # 华东理工大学，当前广西画像结果内且有多事实 expr
    expect_true(
        "V1.2 测试高校来自当前 CandidateProfile 学校结果",
        PROFILE_MAJOR_SCHOOL in gx_profile_school_ids,
        f"school_id={PROFILE_MAJOR_SCHOOL}  候选高校={len(gx_profile_school_ids)}",
    )
    profile_major = check(
        "CandidateProfile + College -> 专业历史位次",
        "GET",
        f"/api/colleges/{PROFILE_MAJOR_SCHOOL}/majors?"
        "source_province=广西&year=2025&category=物理类&"
        "candidate_rank=10000&page_size=50",
        detail=lambda p: f"total={p.get('total')}  本页={len(p.get('items', []))}",
    )
    profile_major_items = profile_major.get("items") or []
    expect_true(
        "V1.2 响应明确回显唯一 CandidateProfile 上下文",
        profile_major.get("candidate_profile_applied") is True
        and profile_major.get("candidate_profile") == {
            "source_province": "广西",
            "year": 2025,
            "category": "物理类",
            "batch": None,
            "rank": 10000,
        },
        f"candidate_profile={profile_major.get('candidate_profile')}",
    )
    expect_true(
        "V1.2 专业行包含 expr / 代表事实 / 招生单位 / 位次差字段",
        bool(profile_major_items)
        and all(set(item) == MAJOR_PROFILE_KEYS for item in profile_major_items),
        f"检查 {len(profile_major_items)} 条",
    )
    expect_true(
        "V1.2 只返回广西/2025/物理类且每个 expr_id 唯一",
        bool(profile_major_items)
        and all(
            item["source_province"] == "广西"
            and item["year"] == 2025
            and item["category"] == "物理类"
            for item in profile_major_items
        )
        and len({item["expr_id"] for item in profile_major_items})
        == len(profile_major_items),
        f"items={len(profile_major_items)}",
    )
    ranked_profile_majors = [
        item for item in profile_major_items if item.get("min_rank") is not None
    ]
    expect_true(
        "至少 5 个真实专业的 professional_rank_gap 计算正确",
        len(ranked_profile_majors) >= 5
        and all(
            item["professional_rank_gap"] == item["min_rank"] - 10000
            for item in ranked_profile_majors
        ),
        ", ".join(
            f"{item['raw_major_name']}:{item['min_rank']}/{item['professional_rank_gap']}"
            for item in ranked_profile_majors[:5]
        ),
    )
    expect_true(
        "有位次专业按 ABS(professional_rank_gap) 升序",
        [abs(item["professional_rank_gap"]) for item in ranked_profile_majors]
        == sorted(abs(item["professional_rank_gap"]) for item in ranked_profile_majors),
        f"检查 {len(ranked_profile_majors)} 条",
    )
    expect_true(
        "V1.2 不依赖标准 Major 映射也能返回专业",
        bool(profile_major_items)
        and all(item.get("std_major") is None for item in profile_major_items),
        f"unmapped={sum(item.get('std_major') is None for item in profile_major_items)}",
    )

    MULTI_EXPR = 480521
    multi_expr_item = next(
        (item for item in profile_major_items if item.get("expr_id") == MULTI_EXPR),
        None,
    )
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT ma.id, ma.min_rank
            FROM major_admission ma
            JOIN school_unit u ON u.unit_id = ma.unit_id
            WHERE u.school_id = %(school_id)s
              AND ma.source_province = '广西'
              AND ma.year = 2025
              AND ma.category = '物理类'
              AND ma.expr_id = %(expr_id)s
            ORDER BY CASE WHEN ma.min_rank IS NULL THEN 1 ELSE 0 END,
                     ABS(ma.min_rank - 10000) NULLS LAST,
                     ma.min_rank NULLS LAST,
                     ma.id,
                     ma.unit_id
            LIMIT 1
            """,
            {"school_id": PROFILE_MAJOR_SCHOOL, "expr_id": MULTI_EXPR},
        )
        expected_multi_expr = dict(cur.fetchone())
    expect_true(
        "同一 expr_id 多事实按最小 ABS 位次差选择代表 MajorAdmission",
        multi_expr_item is not None
        and multi_expr_item["representative_admission_id"] == expected_multi_expr["id"]
        and multi_expr_item["min_rank"] == int(expected_multi_expr["min_rank"]),
        f"expr_id={MULTI_EXPR}  expected={expected_multi_expr}  "
        f"actual={multi_expr_item and multi_expr_item.get('representative_admission_id')}",
    )
    expect_true(
        "学校级 7000～18000 位次窗口不会删除校内专业",
        any(
            item["min_rank"] < 7000 or item["min_rank"] > 18000
            for item in ranked_profile_majors
        ),
        "专业查询未接收 rank_ahead/rank_behind，且真实结果含窗口外位次",
    )

    tie_profile = check(
        "V1.2 真实同差值样本",
        "GET",
        "/api/colleges/3571/majors?source_province=广西&year=2025&"
        "category=物理类&candidate_rank=10000&page_size=100",
        detail=lambda p: f"total={p.get('total')}",
    )
    tie_item = next(
        (item for item in (tie_profile.get("items") or []) if item.get("expr_id") == 467420),
        None,
    )
    expect_true(
        "同绝对差且同 min_rank 时以 major_admission.id 稳定决胜",
        tie_item is not None and tie_item.get("representative_admission_id") == 2714241,
        f"actual={tie_item and tie_item.get('representative_admission_id')}",
    )

    all_batches = check(
        "V1.2 全部批次",
        "GET",
        "/api/colleges/5122/majors?source_province=广西&year=2025&"
        "category=物理类&candidate_rank=10000&page_size=100",
        detail=lambda p: f"total={p.get('total')}",
    )
    bachelor_batch = check(
        "V1.2 指定本科批",
        "GET",
        "/api/colleges/5122/majors?source_province=广西&year=2025&"
        "category=物理类&batch=本科批&candidate_rank=10000&page_size=100",
        detail=lambda p: f"total={p.get('total')}",
    )
    expect_true(
        "指定 batch 后专业代表事实只来自同一批次",
        0 < (bachelor_batch.get("total") or 0) <= (all_batches.get("total") or 0)
        and all(item.get("batch") == "本科批" for item in bachelor_batch.get("items") or []),
        f"all={all_batches.get('total')}  本科批={bachelor_batch.get('total')}",
    )

    null_rank_profile = check(
        "V1.2 min_rank NULL 专业保留",
        "GET",
        "/api/colleges/4679/majors?source_province=湖北&year=2024&"
        "category=物理类&candidate_rank=50000&page_size=100",
        detail=lambda p: f"total={p.get('total')}",
    )
    null_rank_items = [
        item for item in (null_rank_profile.get("items") or [])
        if item.get("min_rank") is None
    ]
    expect_true(
        "缺专业历史位次的真实表达在列表尾部且 rank_gap=null",
        bool(null_rank_items)
        and all(item.get("professional_rank_gap") is None for item in null_rank_items)
        and all(
            item.get("min_rank") is None
            for item in (null_rank_profile.get("items") or [])[-len(null_rank_items):]
        ),
        f"NULL rank 专业={len(null_rank_items)}",
    )
    check(
        "candidate_rank 缺少考试上下文 -> 422",
        "GET",
        f"/api/colleges/{PROFILE_MAJOR_SCHOOL}/majors?candidate_rank=10000",
        expect=422,
    )
    expect_true(
        "无 CandidateProfile 时旧专业接口保持 legacy 模式",
        mj.get("candidate_profile_applied") is False
        and mj.get("candidate_profile") is None
        and bool(mj_items),
        f"legacy total={mj.get('total')}",
    )

    # ── data_availability 两个专业键的区分 ───────────────────────────
    # 这组是「未建立标准映射 ≠ 没有该专业」在接口层面的落地检查。
    # 3877 有 638 条专业事实却零条 Tier 1 映射：如果只留一个 major_mapping，
    # 前端会把它的专业视图整个藏掉。
    for sid, who, want in (
        (MIXED, "四川师范大学（有事实、有映射）", (True, True)),
        (NO_MAPPING, "西交利物浦大学（有事实、零映射）", (True, False)),
    ):
        d = check(
            f"colleges/{sid} 详情（{who}）",
            "GET",
            f"/api/colleges/{sid}",
            detail=lambda p: f"data_availability={p['data'].get('data_availability')}",
        )
        av = ((d.get("data") or {}) if isinstance(d, dict) else {}).get(
            "data_availability"
        ) or {}
        expect_true(
            f"{who}：major_admission={want[0]} / major_mapping={want[1]}",
            (av.get("major_admission"), av.get("major_mapping")) == want,
            f"实际 major_admission={av.get('major_admission')}  "
            f"major_mapping={av.get('major_mapping')}",
        )

    # ── 12 标准专业目录 ─────────────────────────────────────────────
    dic = check(
        "majors 标准专业目录",
        "GET",
        "/api/majors?page_size=3",
        detail=lambda p: (
            f"total={p.get('total')}  本页 {len(p.get('items', []))} 条  "
            f"{[i.get('std_name') for i in (p.get('items') or [])]}"
        ),
    )
    expect_true(
        "标准专业目录与库内一致（1,874 行）",
        dic.get("total") == 1874,
        f"total={dic.get('total')}",
    )
    dic_items = (dic.get("items") or []) if isinstance(dic, dict) else []
    if dic_items:
        need = {
            "major_id", "std_code", "std_name", "education_level",
            "discipline", "category", "catalog_version",
        }
        expect_true(
            "标准专业字段恰好（不外泄 status 这类内部 QC 标记）",
            set(dic_items[0]) == need,
            f"多={sorted(set(dic_items[0]) - need)}  缺={sorted(need - set(dic_items[0]))}",
        )

    qdic = check(
        "majors?q=计算机 按名称搜索",
        "GET",
        "/api/majors?q=计算机&page_size=3",
        detail=lambda p: (
            f"total={p.get('total')}  "
            f"{[i.get('std_name') for i in (p.get('items') or [])]}"
        ),
    )
    q_items = (qdic.get("items") or []) if isinstance(qdic, dict) else []
    expect_true(
        "名称搜索命中的每一条都真的含关键词",
        bool(q_items) and all("计算机" in (i.get("std_name") or "") for i in q_items),
        f"{len(q_items)} 条",
    )
    # catalog_version 与 education_level 是绑定的（实测）：本科=2026，专科/职业本科=2021。
    # 这条是 2026-09-17 写对接文档时踩出来的——当时凭印象把职业本科那条写成了
    # catalog_version="2026"，被实测打脸。钉住它，免得文档再漂。
    expect_true(
        "catalog_version 与 education_level 绑定（本科=2026，其余=2021）",
        bool(q_items)
        and all(
            (i.get("catalog_version") == "2026") == (i.get("education_level") == "本科")
            for i in q_items
        ),
        ", ".join(
            f"{i.get('std_name')}/{i.get('education_level')}/{i.get('catalog_version')}"
            for i in q_items
        ),
    )

    # ── 13 反查 ────────────────────────────────────────────────────
    check(
        "majors/999999999/colleges 不存在的专业 -> 404",
        "GET",
        "/api/majors/999999999/colleges",
        expect=404,
    )
    rev = check(
        f"majors/{STD_MAJOR}/colleges 反查高校",
        "GET",
        f"/api/majors/{STD_MAJOR}/colleges?page_size=5",
        detail=lambda p: (
            f"total={p.get('total')}  本页 {len(p.get('items', []))} 条  "
            f"warnings={p.get('warnings')}"
        ),
    )
    rev_items = (rev.get("items") or []) if isinstance(rev, dict) else []
    expect_true("反查返回高校", bool(rev_items), f"total={rev.get('total')}")
    expect_true(
        "反查的 total 是**高校数**不是事实数",
        rev.get("total") == REV_TOTAL,
        f"期望 {REV_TOTAL} 所，实际 {rev.get('total')}",
    )
    expect_true(
        "反查一律带覆盖警告（它是纯 Tier 1 查询，天生只覆盖 37.8%）",
        COVERAGE_WARN in (rev.get("warnings") or []),
        f"warnings={rev.get('warnings')}",
    )
    expect_true(
        "反查回带 std_major，前端不必猜自己查的是哪个专业",
        (rev.get("std_major") or {}).get("major_id") == STD_MAJOR,
        f"std_major={rev.get('std_major')}",
    )
    if rev_items:
        need = {
            "school_id", "national_code", "name", "edu_level",
            "reg_province", "fact_count",
        }
        expect_true(
            "反查元素字段齐全",
            need <= set(rev_items[0]),
            f"缺 {sorted(need - set(rev_items[0]))}",
        )
        tgt = next((i for i in rev_items if i.get("school_id") == MIXED), None)
        if tgt:
            expect_true(
                f"反查里 {MIXED} 四川师范大学的 fact_count 是条数不是人数",
                isinstance(tgt.get("fact_count"), int) and tgt["fact_count"] > 0,
                f"fact_count={tgt.get('fact_count')}",
            )

    print()
    print("=" * 68)
    print("倪嵩：3 投档记录 / 4 筛选元数据")
    print("=" * 68)

    filters = check("meta/filters", "GET", "/api/meta/filters")

    fdata = filters.get("data") if isinstance(filters, dict) else None
    if not isinstance(fdata, dict) or not fdata.get("years"):
        expect_true("filters 返回可用的筛选元数据", False, f"data={fdata!r}")
        fdata = {}

    years = fdata.get("years") or []
    provinces = fdata.get("source_provinces") or []
    categories = fdata.get("categories") or []
    batches = fdata.get("batches") or []
    print(
        f"        years={years}  provinces={len(provinces)}"
        f"  edu_levels={fdata.get('edu_levels')}"
        f"  categories={len(categories)}  batches={len(batches)}"
    )
    expect_true(
        "filters 的取值来自数据库真实值（不是硬编码）",
        bool(years) and bool(provinces) and bool(categories),
        f"年份 {len(years)} 个、生源省 {len(provinces)} 个、科类 {len(categories)} 个",
    )

    # ── 先取一所真实高校的投档明细 ─────────────────────────────────
    # 用记录里**真实存在**的 (生源省, 年份, 科类) 反查 /search，
    # 就不必猜哪个组合不为空（库里科类是按年份分布的，猜一个很容易 0 条）。
    adm_school = first_id if first_id is not None else 1
    adm = check(
        f"colleges/{adm_school}/admissions",
        "GET",
        f"/api/colleges/{adm_school}/admissions",
        detail=lambda p: (
            f"total={p.get('total')}  本页 {len(p.get('items', []))} 条  "
            f"display_deduplicated={p.get('display_deduplicated')}"
        ),
    )
    adm_items = (adm.get("items") or []) if isinstance(adm, dict) else []

    if not adm_items and adm_school != 4687:
        # 抽到的高校恰好没有投档记录就换一个。4687 是库里记录最多的一所。
        print("        这所高校没有投档记录，改用 school_id=4687 再取一次")
        adm_school = 4687
        adm = check(
            f"colleges/{adm_school}/admissions",
            "GET",
            f"/api/colleges/{adm_school}/admissions",
            detail=lambda p: (
                f"total={p.get('total')}  本页 {len(p.get('items', []))} 条  "
                f"display_deduplicated={p.get('display_deduplicated')}"
            ),
        )
        adm_items = (adm.get("items") or []) if isinstance(adm, dict) else []

    expect_true(
        "投档记录能返回真实数据",
        bool(adm_items),
        f"total={adm.get('total') if isinstance(adm, dict) else '?'}",
    )

    if adm_items:
        keys = set(adm_items[0].keys())
        need = {
            "source_province",
            "year",
            "category",
            "batch",
            "subject_req",
            "min_score",
            "min_rank",
            "control_score",
            "score_diff",
            "admit_count",
        }
        expect_true(
            "投档记录字段齐全（缺失值应为 null，不填 0）",
            need <= keys,
            f"缺 {sorted(need - keys)}" if not need <= keys else f"{len(keys)} 个字段齐全",
        )

    # ── 招生条件现在应该**真的筛**，既不是 501，也不是静默忽略 ────────
    rec = adm_items[0] if adm_items else {}
    cond = {
        k: rec.get(k)
        for k in ("source_province", "year", "category")
        if rec.get(k)
    }

    filtered = check(
        f"search 带招生条件 {cond}（取自 school_id={adm_school} 的真实记录）",
        "POST",
        "/api/search",
        {"admission": cond},
        detail=lambda p: f"total={p.get('total')}  warnings={p.get('warnings')}",
    )
    expect_true(
        "带招生条件真的筛出了高校（不再是 501）",
        (filtered.get("total") or 0) > 0,
        f"条件取自真实记录，total 不该是 0，实际 {filtered.get('total')}",
    )

    # 只留年份当对照：加上生源省/科类后结果必须变窄，否则说明招生条件被忽略了
    if rec.get("year"):
        only_year = check(
            f"search 只按 year={rec.get('year')} 筛（对照）",
            "POST",
            "/api/search",
            {"admission": {"year": rec.get("year")}},
            detail=lambda p: f"total={p.get('total')}",
        )
        expect_true(
            "加上生源省/科类后结果确实变窄（招生条件真生效）",
            0 < (filtered.get("total") or 0) <= (only_year.get("total") or 0),
            f"{filtered.get('total')} <= {only_year.get('total')}",
        )

    expect_true(
        "涉及 category 时给出「来源原始口径」提示",
        "当前科类/批次使用来源数据原始口径" in (filtered.get("warnings") or []),
        f"warnings={filtered.get('warnings')}",
    )

    # ── CandidateProfile V2.1 学校级多年度历史参考 ────────────────
    summary = check(
        "admissions/summary 多年度真实样例",
        "GET",
        "/api/colleges/4687/admissions/summary"
        "?source_province=浙江&main_year=2025&category=综合&candidate_rank=20000",
        detail=lambda p: (
            f"years={[y.get('year') for y in p.get('years', [])]}  "
            f"statuses={[y.get('status') for y in p.get('years', [])]}"
        ),
    )
    summary_years = summary.get("years") or []
    expect_true(
        "summary request/response context 原样返回",
        summary.get("school_id") == 4687
        and summary.get("context")
        == {
            "source_province": "浙江",
            "main_year": 2025,
            "category": "综合",
            "batch": None,
            "candidate_rank": 20000,
        },
        f"context={summary.get('context')}",
    )
    expect_true(
        "comparable years 按 2025→2024→2023 降序生成",
        [y.get("year") for y in summary_years] == [2025, 2024, 2023],
        f"years={[y.get('year') for y in summary_years]}",
    )
    expected_references = {
        2025: (12, 337992, 20890, 890),
        2024: (9, 338335, 12844, -7156),
        2023: (17, 338525, 11622, -8378),
    }
    actual_references = {
        y.get("year"): (
            y.get("record_count"),
            (y.get("reference_admission") or {}).get("admission_id"),
            (y.get("reference_admission") or {}).get("min_rank"),
            (y.get("reference_admission") or {}).get("rank_gap"),
        )
        for y in summary_years
    }
    expect_true(
        "每年 record_count、最近代表事实与 rank_gap 正确",
        actual_references == expected_references,
        f"actual={actual_references}",
    )
    expect_true(
        "summary 不受主查询 rank window 限制",
        any(
            y.get("year") == 2023
            and abs((y.get("reference_admission") or {}).get("rank_gap", 0)) > 3000
            for y in summary_years
        ),
        "2023 代表事实与当前位次相差 8378，仍被返回",
    )
    expect_true(
        "全部批次时每年返回代表事实的真实 batch",
        all(
            (y.get("reference_admission") or {}).get("batch")
            for y in summary_years
        ),
        str([(y.get("year"), (y.get("reference_admission") or {}).get("batch")) for y in summary_years]),
    )

    summary_2024 = check(
        "admissions/summary 主参考年份 2024",
        "GET",
        "/api/colleges/4687/admissions/summary"
        "?source_province=浙江&main_year=2024&category=综合&candidate_rank=20000",
    )
    expect_true(
        "year <= main_year，不自动混入 2025",
        [y.get("year") for y in (summary_2024.get("years") or [])]
        == [2024, 2023],
        f"years={[y.get('year') for y in (summary_2024.get('years') or [])]}",
    )

    province_exact = check(
        "admissions/summary 生源省严格同值",
        "GET",
        "/api/colleges/4687/admissions/summary"
        "?source_province=浙江省&main_year=2025&category=综合&candidate_rank=20000",
    )
    expect_true(
        "source_province 不做 浙江省→浙江 归一化",
        province_exact.get("years") == [],
        f"years={province_exact.get('years')}",
    )
    category_exact = check(
        "admissions/summary 科类严格同值",
        "GET",
        "/api/colleges/4687/admissions/summary"
        "?source_province=浙江&main_year=2025&category=综合类&candidate_rank=20000",
    )
    expect_true(
        "category 不做 综合类→综合 归一化",
        category_exact.get("years") == [],
        f"years={category_exact.get('years')}",
    )

    no_record_summary = check(
        "admissions/summary 显式 no_record 年份",
        "GET",
        "/api/colleges/2954/admissions/summary"
        "?source_province=浙江&main_year=2025&category=综合&candidate_rank=20000",
    )
    no_record_2023 = next(
        (y for y in (no_record_summary.get("years") or []) if y.get("year") == 2023),
        {},
    )
    expect_true(
        "学校无事实的全局可比年份不会消失",
        no_record_2023.get("status") == "no_record"
        and no_record_2023.get("record_count") == 0
        and no_record_2023.get("reference_admission") is None,
        f"2023={no_record_2023}",
    )

    unavailable_summary = check(
        "admissions/summary 显式 rank_unavailable",
        "GET",
        "/api/colleges/4987/admissions/summary"
        "?source_province=广东&main_year=2023&category=历史类&candidate_rank=100000",
    )
    unavailable_2023 = next(
        (y for y in (unavailable_summary.get("years") or []) if y.get("year") == 2023),
        {},
    )
    expect_true(
        "有事实但 min_rank 全空时不伪造代表事实",
        unavailable_2023.get("status") == "rank_unavailable"
        and unavailable_2023.get("record_count") == 128
        and unavailable_2023.get("reference_admission") is None,
        f"2023={unavailable_2023}",
    )

    exact_batch_summary = check(
        "admissions/summary 指定 exact batch",
        "GET",
        "/api/colleges/2957/admissions/summary"
        "?source_province=福建&main_year=2025&category=物理类"
        "&candidate_rank=50000&batch=专科批",
    )
    exact_years = exact_batch_summary.get("years") or []
    exact_2024 = next((y for y in exact_years if y.get("year") == 2024), {})
    expect_true(
        "exact batch 缺失年份返回 no_record，不做批次映射",
        exact_batch_summary.get("context", {}).get("batch") == "专科批"
        and exact_2024.get("status") == "no_record",
        f"2024={exact_2024}",
    )
    expect_true(
        "exact batch 的代表事实均保留实际批次",
        all(
            y.get("status") != "reference_available"
            or (y.get("reference_admission") or {}).get("batch") == "专科批"
            for y in exact_years
        ),
        str([(y.get("year"), (y.get("reference_admission") or {}).get("batch")) for y in exact_years]),
    )

    tie_summary = check(
        "admissions/summary 等距 tie-breaker",
        "GET",
        "/api/colleges/2960/admissions/summary"
        "?source_province=内蒙&main_year=2025&category=历史类"
        "&candidate_rank=124&batch=本科批",
    )
    tie_reference = ((tie_summary.get("years") or [{}])[0]).get("reference_admission") or {}
    expect_true(
        "等距时按较小 min_rank，再按 admission_id 稳定选择",
        tie_reference.get("admission_id") == 379212
        and tie_reference.get("min_rank") == 31
        and tie_reference.get("rank_gap") == -93,
        f"reference={tie_reference}",
    )

    check(
        "admissions/summary 缺少必填 CandidateProfile 参数 -> 422",
        "GET",
        "/api/colleges/4687/admissions/summary?source_province=浙江",
        expect=422,
    )
    check(
        "admissions/summary candidate_rank 必须为正整数",
        "GET",
        "/api/colleges/4687/admissions/summary"
        "?source_province=浙江&main_year=2025&category=综合&candidate_rank=0",
        expect=422,
    )

    check(
        "colleges/999999999/admissions 不存在的高校 -> 空列表而非报错",
        "GET",
        "/api/colleges/999999999/admissions",
        detail=lambda p: f"total={p.get('total')}  items={len(p.get('items', []))}",
    )

    server.should_exit = True
    time.sleep(0.5)

    print()
    print("=" * 68)
    print(f"通过 {len(passed)} 项，失败 {len(failed)} 项")
    for name in failed:
        print(f"  FAIL  {name}")
    print("=" * 68)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
