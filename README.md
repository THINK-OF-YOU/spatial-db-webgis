# 全国高校志愿填报空间数据库暨地理查询原型 V1

武汉大学 遥感信息工程学院《空间数据库实习》课程项目 · 第 13 组

PostgreSQL / PostGIS → FastAPI → Vue 3 + Leaflet

---

## 这是什么

把已经建好的高考招生空间数据库（`gaokao3`）接成一个可演示的 PC 端 GIS 原型，
跑通"**招生条件筛选 + 空间条件筛选**"的组合查询：

- 高校列表 / 搜索 / 详情
- 按生源省、年份、科类、批次查历史投档
- 高校周边交通站点（铁路 / 地铁 / 机场，直线距离）
- Campus 与行政区上 Leaflet 地图，CONFIRMED / CANDIDATE 区分
- 参考点 + 半径、Polygon 空间选区（PostGIS `ST_DWithin` / `ST_Distance`）

**V1 全程只读**，不写任何业务数据。

---

## 目录结构

```
.
├── backend/            FastAPI 后端
│   └── app/
│       ├── main.py         入口、路由注册、CORS
│       ├── db/             连接池、配置
│       ├── api/            路由模块（colleges / map / spatial / search / majors / meta / admissions）
│       ├── schemas/        Pydantic 请求响应模型
│       └── services/       查询服务
├── frontend/           Vue 3 + Leaflet 前端
│   └── src/
│       ├── stores/         Pinia（核心只有一个 useSearchStore）
│       ├── api/            接口封装
│       ├── views/          页面
│       ├── components/     组件（含 map/ 地图组件）
│       └── mocks/          契约一致的 Mock 数据
├── sql/                SQL 脚本
│   ├── init.sql
│   ├── query/              KNN、半径、统计查询（文件名带作者前缀）
│   └── data/               数据导入脚本
└── docs/
    ├── 00_协作规范.md      ★ 开工前必读
    ├── 01_接口样例.md      13 个接口的实测请求/响应（自动生成，勿手改）
    └── 02_专业API对接文档.md  ★ 前端做专业视图看这份
```

`docs/01_接口样例.md` 由 `backend/capture_samples.py` 真跑一遍服务生成，里面的响应是
`gaokao3` 的实际返回，不是手写的。接口改了就在 `backend/` 下重跑一次脚本，文档不会和实现漂移：

```bash
cd backend
./.venv/Scripts/python.exe capture_samples.py   # 会临时起一个服务，跑完自动退出
```

**专业接口（11–13）**是 2026-09-17 数据库恢复专业语义链之后新增的，前端对接看
[`docs/02_专业API对接文档.md`](docs/02_专业API对接文档.md)。有一件事必须先知道：

> 专业是**两层语义**。「来源招生专业表达」覆盖 98.62%，「标准专业」只覆盖 37.80%
> （本轮只入库 Tier 1 精确映射）。**未建立标准映射 ≠ 该校没有这个专业**——
> 六成以上的记录 `std_major` 是 `null`，但分数位次都是真的，必须照常显示。

---

## 数据库

| 项 | 值 |
|---|---|
| 库名 | **`gaokao3`** |
| 版本 | PostgreSQL 18.6 + PostGIS 3.6.2 |
| 坐标 | WGS84 / EPSG:4326 |
| 权限 | **只读** |

> ⚠️ **只能连 `gaokao3`。** 不要连 `gaokao`（已冻结的历史库）或 `gaokao2`（缺 `poi_transport` 等表）。
> ⚠️ 全程只读：禁止 `INSERT / UPDATE / DELETE / ALTER / DROP / CREATE`，禁止建视图和索引。

连接配置写在 `backend/.env`，**不入库**。复制 `backend/.env.example` 后填本机值：

```
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=gaokao3
PGUSER=postgres
PGPASSWORD=
```

---

## 启动

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

打开 http://127.0.0.1:8000/docs 看 OpenAPI。

**先自检再写代码**——确认自己本机的 `.env` 与数据库是通的：

```bash
cd backend
.venv\Scripts\python.exe smoke_test.py
```

脚本自带服务（临时占用 8123 端口），把 13 个接口挨个实打一遍，
并断言返回内容本身（不只是状态码）。全 OK 才动手。

> Windows 控制台是 GBK。用 psql 跑含中文的 SQL 时先 `chcp 65001`，
> 并且**必须用 `-f 文件` 而不是 `-c "..."`**，否则中文会被 GBK 破坏，
> 报 `invalid byte sequence for encoding "UTF8"`。

### 前端

```bash
cd frontend
npm install
npm run dev
```

---

## 协作

**开工前先读 [`docs/00_协作规范.md`](docs/00_协作规范.md)。** 里面写了：

- 数据库、坐标系、业务不变量三类硬红线
- 分支模型（`main` 保护 / `dev` 快车道 / `feature/*`）
- **文件所有权表**——防冲突靠这张表，不靠人眼 review
- 已知冲突点的处理办法
- 给各组员 AI agent 的提示词约束段

接口路径与字段以《V1 前后端开发任务执行书》**§4 API Contract** 为准（四人各持一份正文）。
**契约变更必须全组确认，个人 agent 不得自行决定。**

提交信息用 `feat: / fix: / docs: `，别写"更新"、"改了"。

---

## 分工

| 成员 | 角色 |
|---|---|
| 莫炜钧 | 后端主负责人 / 集成——FastAPI 骨架、College API、地图与空间 API、`/search` 总集成 |
| 倪嵩 | 招生后端——`/meta/filters`、`/colleges/{id}/admissions`、招生子查询 |
| 高天恒 | GIS 前端——Leaflet、Campus、AdminRegion、参考点、距离圈、绘制 |
| 范传智 | Vue 业务前端——布局、筛选、列表、详情 Drawer、对比、CSV 导出 |

---

## 数据来源与署名

交通设施 POI 来自 OpenStreetMap，**ODbL 许可**，须署名 **© OpenStreetMap contributors**。

---

## 已知限制（照实写，不掩盖）

- Campus 432 点，仅覆盖 2,952 所 College 的 14.63%；其中 `CONFIRMED` 仅 4 个。
  且这 432 点分属 432 所不同高校，**每校最多 1 个带几何的校区**——所以"多校区取最近"
  那条路径目前走不到，别当成已测。
- `poi_transport` 约 1.9 万 POI，覆盖不齐：metro 只覆盖 29 省，`name_zh` 约 2/3 缺失。
  抽样 200 个校区，仅 73% 能在 3 km 内找到交通点——**"查不到"是常见情况**，
  接口用 `warnings` 区分"缺校区"与"缺交通数据"，前端不得显示成"周边没有站点"。
- 专业语义链（Expression / Group / Map）当前为空，V1 **不提供专业录取与专业组筛选**。
- `category` / `batch` 是来源原始口径，未做全国统一标准化。
- `college.reg_province` 实际存的是**市**名，不是省名。
