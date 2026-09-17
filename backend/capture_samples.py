"""抓取 13 个接口的真实请求/响应，生成 docs/01_接口样例.md。

在 backend 目录下运行：

    ./.venv/Scripts/python.exe capture_samples.py

为什么用脚本生成而不是手写文档：**样例必须是实测的**，不能是抄的、编的。
跑这个脚本会真的起服务、真的查 gaokao3、把响应原样写进文档。接口改了重跑一次，
文档不会和实现漂移。

只读，不改任何数据。
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import uvicorn

from app.main import app

HOST = "127.0.0.1"
PORT = 8127
BASE = f"http://{HOST}:{PORT}"
OUT = Path(__file__).resolve().parent.parent / "docs" / "01_接口样例.md"

# 单个响应的截断长度。Province 级 GeoJSON 有 34 个 feature，几何很长，
# 全塞进文档没人看。截断处会显式标注，不假装是完整响应。
MAX_CHARS = 620


def call(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    # 查询串里有中文（q=大学）时必须百分号编码：urllib 的请求行只能是 ASCII。
    # 文档里打印的 curl 仍用原文，因为 curl 会直接把 UTF-8 字节发出去，
    # 服务端也接受——那才是人手敲的样子。
    url = BASE + urllib.parse.quote(path, safe="/?&=%")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def fmt(raw: str) -> str:
    """美化 JSON；太长就截断并标注。"""
    try:
        pretty = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        pretty = raw
    if len(pretty) > MAX_CHARS:
        return pretty[:MAX_CHARS] + f"\n  …（已截断，原响应 {len(pretty)} 字符；完整响应看 /docs）"
    return pretty


def curl(method: str, path: str, body: dict | None = None) -> str:
    # 用 $BASE 而不是抓取时的真实端口：抓取跑在临时端口上，写死进文档会误导读者。
    if body is None:
        return f"curl \"$BASE{path}\""
    return (
        f"curl -X {method} \"$BASE{path}\" \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -d '{json.dumps(body, ensure_ascii=False)}'"
    )


def section(lines: list[str], title: str, method: str, path: str, body=None, note: str = ""):
    status, raw = call(method, path, body)
    lines.append(f"### {title}")
    lines.append("")
    if note:
        lines.append(note)
        lines.append("")
    lines.append("请求：")
    lines.append("")
    lines.append("```bash")
    lines.append(curl(method, path, body))
    lines.append("```")
    lines.append("")
    lines.append(f"响应 `{status}`：")
    lines.append("")
    lines.append("```json")
    lines.append(fmt(raw))
    lines.append("```")
    lines.append("")
    return json.loads(raw) if status == 200 else None


def main() -> int:
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.time() + 30
    while not server.started and time.time() < deadline:
        time.sleep(0.1)
    if not server.started:
        print("服务未启动")
        return 1

    # 先用真实数据挑出参考点与招生条件，避免样例里出现"因为猜错组合所以 0 条"
    _, raw = call("GET", "/api/map/campuses?bbox=73,18,135,54&verify_status=CONFIRMED"
                         "&verify_status=CANDIDATE")
    lon, lat = 114.36, 30.54
    for feat in json.loads(raw).get("features", []):
        coords = (feat.get("geometry") or {}).get("coordinates")
        if isinstance(coords, list) and len(coords) == 2:
            lon, lat = coords
            break

    _, raw = call("GET", "/api/colleges/2953/admissions")
    rec = (json.loads(raw).get("items") or [{}])[0]
    cond = {k: rec.get(k) for k in ("source_province", "year", "category") if rec.get(k)}

    L: list[str] = []
    L.append("# 接口请求/响应样例（实测）")
    L.append("")
    L.append("> **本文件由 `backend/capture_samples.py` 自动生成，不要手改。**")
    L.append("> 所有样例都是真跑一次服务、真查 `gaokao3` 拿到的响应，不是手写的。")
    L.append("> 接口变了就重跑脚本，文档不会和实现漂移。")
    L.append("")
    L.append(f"生成时间：{time.strftime('%Y-%m-%d %H:%M')}　数据库：`gaokao3`（只读）")
    L.append("")
    L.append("启动方式见 `README.md`。下面样例里的 `$BASE` 指你本机跑起来的服务地址，"
             "默认是 `http://127.0.0.1:8000`：")
    L.append("")
    L.append("```bash")
    L.append("export BASE=http://127.0.0.1:8000")
    L.append("```")
    L.append("")
    L.append("响应是抓取时的**原样输出**。GeoJSON 类的响应很长，超长部分已截断并标注了"
             "「已截断」——没有截断的都是完整响应。")
    L.append("")
    L.append("---")
    L.append("")

    L.append("## 接口清单")
    L.append("")
    L.append("| # | 接口 | 负责人 |")
    L.append("|---|---|---|")
    L.append("| 1 | `GET /api/colleges` | 莫炜钧 |")
    L.append("| 2 | `GET /api/colleges/{school_id}` | 莫炜钧 |")
    L.append("| 3 | `GET /api/colleges/{school_id}/admissions` | 倪嵩 |")
    L.append("| 4 | `GET /api/meta/filters` | 倪嵩 |")
    L.append("| 5 | `GET /api/map/campuses` | 莫炜钧 |")
    L.append("| 6 | `GET /api/map/regions` | 莫炜钧 |")
    L.append("| 7 | `GET /api/spatial/nearby` | 莫炜钧 |")
    L.append("| 8 | `POST /api/spatial/within` | 莫炜钧 |")
    L.append("| 9 | `POST /api/search` | 莫炜钧（总集成） |")
    L.append("| 10 | `GET /api/colleges/{school_id}/transport` | 莫炜钧 |")
    L.append("| 11 | `GET /api/colleges/{school_id}/majors` | 莫炜钧 |")
    L.append("| 12 | `GET /api/majors` | 莫炜钧 |")
    L.append("| 13 | `GET /api/majors/{major_id}/colleges` | 莫炜钧 |")
    L.append("")
    L.append("> 11–13 是 2026-09-17 数据库恢复专业语义链之后新增的，"
             "详细对接说明见 **`docs/02_专业API对接文档.md`**。")
    L.append("")
    L.append("---")
    L.append("")

    L.append("## 1–2　College　`api/colleges.py`")
    L.append("")
    det = section(L, "1. 高校列表 / 搜索", "GET", "/api/colleges?page_size=3")
    first = (det or {}).get("items", [{}])[0].get("school_id", 1)
    section(
        L, "1b. 高校列表 + 筛选条件", "GET",
        "/api/colleges?q=大学&edu_level=本科&page_size=3",
        note="`q` 走名称模糊匹配；`edu_level` 只接受库里真实值（`本科` / `高职（专科）`）。",
    )
    section(L, "2. 高校详情", "GET", f"/api/colleges/{first}",
            note="返回 `college` / `campuses` / `data_availability` 三部分。"
                 "Campus 只给业务字段，**原始 source 等内部列不外泄**。")
    section(L, "2b. 详情：不存在的 school_id", "GET", "/api/colleges/999999999",
            note="不存在的 id 返回 `404`，不是空对象。")

    L.append("## 3–4　招生（倪嵩）`api/admissions.py` / `api/meta.py`")
    L.append("")
    section(L, "3. 历史投档记录", "GET", "/api/colleges/2953/admissions?page_size=2",
            note="数据链固定 College → SchoolUnit → SchoolAdmission。"
                 "`display_deduplicated=true` 表示接口层对**展示字段完全一致**的记录做了精确合并"
                 "（契约 §4.4），不是数据库去重。")
    section(L, "4. 筛选元数据", "GET", "/api/meta/filters",
            note="五个下拉项全部取自数据库真实 distinct 值，前端不得硬编码。")

    L.append("## 5–6　地图　`api/map.py`")
    L.append("")
    section(L, "5. Campus 点位（按视野裁剪）", "GET",
            "/api/map/campuses?bbox=114.28,30.48,114.45,30.60"
            "&verify_status=CONFIRMED&verify_status=CANDIDATE",
            note="GeoJSON FeatureCollection。**坐标顺序固定 `[lon, lat]`**。"
                 "properties 只保留契约 §4.6 的 5 个字段。")
    section(L, "5b. Campus 点位（按学校取）", "GET",
            "/api/map/campuses?school_ids=3059&school_ids=2954")
    section(L, "6. 行政区（默认只给省级）", "GET", "/api/map/regions",
            note="契约 §4.7 明确「不要求一次性传全国所有几何」，所以不传 `level` 时"
                 "只返回省（34 个），要市级必须显式下钻。")
    section(L, "6b. 行政区下钻到市", "GET", "/api/map/regions?parent_adcode=420000",
            note="`parent_adcode` 返回该行政区的下一级。")

    L.append("## 7–8　空间　`api/spatial.py`")
    L.append("")
    section(L, "7. 参考点 + 半径", "GET",
            f"/api/spatial/nearby?lon={lon:.4f}&lat={lat:.4f}&radius_km=50"
            "&verify_status=CONFIRMED&verify_status=CANDIDATE&limit=3",
            note="距离用 `geom::geography` 米制测地距离，对外返回 km。"
                 "**不传 `verify_status` 时默认只查 CONFIRMED**（§3.3 冻结口径），"
                 "而全库只有 4 个 CONFIRMED 校区，所以默认很可能为空——这不是 bug。")
    section(L, "7b. 不传 verify_status（默认只 CONFIRMED）", "GET",
            f"/api/spatial/nearby?lon={lon:.4f}&lat={lat:.4f}&radius_km=50",
            note="对照上一条：默认口径下大概率查不到，前端要提供「包含候选校区」开关。")
    section(L, "8. 自定义 Polygon", "POST", "/api/spatial/within",
            {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [lon - 0.2, lat - 0.2], [lon + 0.2, lat - 0.2],
                        [lon + 0.2, lat + 0.2], [lon - 0.2, lat + 0.2],
                        [lon - 0.2, lat - 0.2],
                    ]],
                },
                "verify_status": ["CONFIRMED", "CANDIDATE"],
            },
            note="边界语义**固定 `ST_Within`**（点在面内），全接口只用这一个语义，"
                 "不混用 `ST_Intersects`。副作用：正好落在边界上的点会被排除。")
    section(L, "8b. 非面几何被拒", "POST", "/api/spatial/within",
            {"geometry": {"type": "Point", "coordinates": [lon, lat]}},
            note="只收 Polygon / MultiPolygon，其他几何类型返回 `422`。")

    L.append("## 9　综合查询　`api/search.py`")
    L.append("")
    section(L, "9. 招生 + 空间组合", "POST", "/api/search",
            {"admission": cond, "spatial": {
                "reference_point": {"lon": lon, "lat": lat}, "radius_km": 300,
                "include_candidate_campus": True}},
            note=f"`admission` 取自 school_id=2953 的真实投档记录：`{cond}`。"
                 "招生子查询由倪嵩的 `admission_service.filter_school_ids()` 提供，"
                 "`/search` 本身不写第二套招生 SQL。")
    section(L, "9b. 无空间条件（业务不变量：不排除无 Campus 高校）", "POST", "/api/search",
            {"college": {"edu_level": "本科"}},
            note="**没有空间条件时，没有 Campus 的 College 必须照常出现在结果里**"
                 "（§3.5 Gate 项）。只有启用空间条件后才允许被排除，并用 warnings 说明。")
    section(L, "9c. 有空间条件（出现「空间覆盖不足」提示）", "POST", "/api/search",
            {"spatial": {"reference_point": {"lon": lon, "lat": lat}, "radius_km": 50}},
            note="启用空间条件后，无 Campus 的高校不能参与空间筛选，"
                 "此时必须给出 warnings 说明覆盖不足。")
    section(L, "9d. 只给 reference_point、不给 radius_km", "POST", "/api/search",
            {"spatial": {"reference_point": {"lon": lon, "lat": lat}}},
            note="契约 §4.10 的示例把两者成对给出，未规定单独给参考点的语义。"
                 "当前实现：**不筛，只算距离**（不会 500）。")

    L.append("## 10　周边交通　`api/colleges.py` + `services/spatial_service.py`")
    L.append("")
    section(L, "10. 高校周边交通站点（成功样例）", "GET",
            "/api/colleges/3059/transport",
            note="以该校全部有几何的 Campus 为基准点，距离取到**最近** Campus 的直线距离，"
                 "按 `distance_km` 升序。站点名以 OSM 原名 `name` 为准；`name_zh` 大量缺失，"
                 "缺失返回 `null`，**不推算、不用别的值填充**。")
    section(L, "10b. 按类型过滤 + 收窄半径", "GET",
            "/api/colleges/3059/transport?mode=metro&radius_km=1&limit=3")
    section(L, "10c. 【查不到样例】有校区，但半径内没有站点", "GET",
            "/api/colleges/2954/transport",
            note="**这是要求的那组「查不到站点、只返回 warnings」样例。**"
                 "`items` 为空数组，`warnings` 说明数据覆盖不足。"
                 "`poi_transport` 覆盖不齐（抽样 200 个校区仅 73% 能在 3 km 内找到交通点），"
                 "所以「查不到」是常态——前端**绝不能**渲染成「该高校周边没有交通站点」。")
    section(L, "10d. 【查不到样例】压根没有带几何的校区", "GET",
            "/api/colleges/4687/transport",
            note="两种「查不到」必须分开说：这条是「缺校区」，10c 是「缺交通数据」。"
                 "全库 2,952 所高校只有 432 所有校区，前者是常见情况而非边缘情况，"
                 "混成一条会把「缺校区」错说成「缺交通数据」。")
    section(L, "10e. 参数越界 -> 422", "GET", "/api/colleges/3059/transport?mode=train",
            note="`mode` 只允许库内真实值 `rail / metro / airport / rail_halt`。"
                 "越界一律 422，**不静默钳制、也不忽略**——宁可让调用方看见错误，"
                 "也不要返回一个「看起来筛过了其实没筛」的结果。同样适用于 "
                 "`radius_km > 20` 与 `limit > 200`。")

    L.append("---")
    L.append("")

    L.append("## 11–13　专业　`api/majors.py` + `services/major_service.py`")
    L.append("")
    section(L, "11. 高校招生专业（两层语义同时返回）", "GET",
            "/api/colleges/5334/majors?page_size=3",
            note="一行 = 一个（来源专业表达 × 生源省 × 年份 × 科类 × 批次）组合下的录取分数。"
                 "**`raw_major_name`（来源招生专业表达，覆盖 98.62%）与 `std_major`"
                 "（教育部标准专业，Tier 1 精确映射，覆盖 37.80%）是两个不同的概念**，"
                 "分两个字段返回、不合并。`std_major` 为 `null` 只说明来源专业名没有被"
                 "规则 v1 精确归一，**不代表该校没有这个专业**——所以这一行不会被丢掉。"
                 "`facts_without_major_name` 是该校另有几条录取记录来源压根没给专业名"
                 "（全库 22,325 条），被排除但**不是静默排除**。")
    section(L, "11b. 只看未建立标准映射的（std_major=null）", "GET",
            "/api/colleges/5334/majors?mapping=unmapped&page_size=3",
            note="这 62% 的记录必须照常查得到。前端渲染时把 `std_major` 为 null 的行标成"
                 "「来源专业名，未归一」，**不要**显示成「无专业」，更不要隐藏。")
    section(L, "11c. 按标准专业筛选（带覆盖警告）", "GET",
            "/api/colleges/5334/majors?std_major_id=2294&page_size=3",
            note="`major_id` 从接口 12 拿。⚠️ 这是**只覆盖 37.80%** 的查询，"
                 "响应必定带 warnings，前端必须展示。对照 11 的 `total=4435`，"
                 "这里只剩 22 条——差额不是「没有」，是「规则没归一」。")
    section(L, "11d. 参数越界 -> 422", "GET",
            "/api/colleges/5334/majors?mapping=bogus",
            note="`mapping` 只允许 `all` / `mapped` / `unmapped`，越界一律 422，"
                 "不静默钳制（同 API 10 的 `mode` 口径）。")
    section(L, "11e. 不存在的高校 -> 空列表而非 404", "GET",
            "/api/colleges/999999999/majors",
            note="与 `/admissions` 同口径：高校子资源在高校不存在时返回空列表。"
                 "前端要靠接口 2 的 404 来发现高校不存在，别指望这里报错。")
    section(L, "12. 标准专业目录（字典 + 搜索）", "GET", "/api/majors?page_size=3",
            note="全表 1,874 行 / 1,711 个专业名，**与高校无关**，是教育部标准专业目录。"
                 "前端用它做「按标准专业筛选」的搜索框，拿到 `major_id` 再传给 11 / 13。"
                 "不返回 `status`（全表都是 `candidate_baseline`，是内部 QC 标记）。")
    section(L, "12b. 按名称搜索", "GET", "/api/majors?q=计算机&page_size=3",
            note="`q` 同时匹配专业名与**专业代码**（如 `080901`）。")
    section(L, "13. 反查：招这个标准专业的高校", "GET",
            "/api/majors/2294/colleges?page_size=3",
            note="⚠️ 纯 Tier 1 查询，**天生只覆盖 37.7984% 的录取事实**。"
                 "查到 778 所不代表全国只有 778 所招这个专业。响应必带覆盖警告，"
                 "前端**不要**把它渲染成「开设该专业的全部高校」。"
                 "`fact_count` 是录取事实条数，**不是招生人数**"
                 "（招生人数是 `admit_count`，按省/年/批次分行给，见接口 11）。")
    section(L, "13b. 不存在的专业 -> 404", "GET", "/api/majors/999999999/colleges",
            note="专业不存在返回 `404`；而不存在的高校调接口 11 返回的是空列表——"
                 "**两者口径不同**，别混。")

    L.append("---")
    L.append("")
    L.append("## 附：需要倪嵩提供的服务函数接口")
    L.append("")
    L.append("`/api/search`（莫炜钧总集成）不自己写招生 SQL，只调倪嵩的 service。"
             "约定如下，**签名已冻结，不要改**：")
    L.append("")
    L.append("`app/services/admission_service.py`")
    L.append("")
    L.append("| 函数 | 用途 | 返回 |")
    L.append("|---|---|---|")
    L.append("| `filter_school_ids(source_province, year, category, batch)` | "
             "`/api/search` 的招生子查询 | `None` = 没启用任何招生条件，调用方**不过滤**；"
             "`list[int]` = 只保留这些 school_id（空列表表示无匹配） |")
    L.append("| `filter_meta()` | `/api/meta/filters` 的五个下拉项 | "
             "`{years, source_provinces, edu_levels, categories, batches}`，全部取自库里 distinct |")
    L.append("| `list_admissions(school_id, source_province, year, category, batch, page, page_size)` | "
             "`/api/colleges/{id}/admissions` | `(items, total, display_deduplicated)` |")
    L.append("")
    L.append("边界（附录 B）：数据链固定 **College → SchoolUnit → SchoolAdmission**；"
             "不要把 `EnrollmentPlan` 或 `MajorAdmission` 引进来；"
             "`category` / `batch` 是来源原始口径，不做全国统一映射。")
    L.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n"：Windows 上 write_text 默认会把 \n 翻成 \r\n，而 git 又会把
    # CRLF 归一成 LF，于是每次重跑都白报一次「文件已修改」。这里直接写 LF。
    OUT.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print(f"已写入 {OUT}（{len(L)} 行）")

    server.should_exit = True
    time.sleep(0.3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
