"""后端骨架冒烟测试 —— 实跑一次数据库，确认接口连通、返回形状符合契约。

在 backend 目录下运行：

    ./.venv/Scripts/python.exe smoke_test.py

特点：
- 只读。不改任何数据；连接本身被服务端强制为 default_transaction_read_only=on。
- 自带服务：在 127.0.0.1:8123 起一个临时 uvicorn，跑完自动退出，不用另开终端。
- 组员拿到仓库后先跑这个，确认自己本机的 .env / 数据库通了再写业务代码。

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

    check(
        "search 带招生条件 -> 501（倪嵩未实现，故意 501 而不是静默忽略）",
        "POST",
        "/api/search",
        {"admission": {"source_province": "湖北省", "year": 2024}},
        expect=501,
    )

    print()
    print("=" * 68)
    print("倪嵩：3 投档记录 / 4 筛选元数据（骨架阶段为 501 占位）")
    print("=" * 68)

    sid = first_id if first_id is not None else 1
    check(
        f"colleges/{sid}/admissions -> 501",
        "GET",
        f"/api/colleges/{sid}/admissions",
        expect=501,
    )
    check("meta/filters -> 501", "GET", "/api/meta/filters", expect=501)

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
