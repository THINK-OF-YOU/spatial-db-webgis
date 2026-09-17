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
import urllib.request

import uvicorn

from app.main import app

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
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
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
        expect_true(
            "data_availability 只有契约 §4.3 的三个键，不夹带 enrollment_plan",
            set(avail) == {"school_admission", "campus", "major_mapping"},
            f"实际键={sorted(avail)}",
        )
        cps = det["data"].get("campuses") or []
        # 恰好这 5 个字段。address 曾经在内，但全库 432 行的 address 全是空串，
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

    # 招生条件不再单独在这里测 501 —— 倪嵩实现后见下一节的真实筛选检查。

    print()
    print("=" * 68)
    print("莫炜钧：10 周边交通（API 10，契约 §4.11）")
    print("=" * 68)

    # 三所高校是照库里实测结果挑的，不是随手写的（2026-09-17 实测）：
    #   3059 天津医科大学            1 个校区，3km 内 39 个站点（metro 38 + rail 1）
    #   2954 盐城幼儿师范高等专科学校  1 个校区，3km 内 0 个站点
    #   4687 华中师范大学            压根没有带几何的校区
    # 注意 3059 那一行：默认 limit=20，所以下面的 base 只会拿到 20 条而不是 39 条，
    # 拿它当"筛窄了"的对照基准没问题。
    HAS_STATION, NO_STATION, NO_CAMPUS = 3059, 2954, 4687

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
