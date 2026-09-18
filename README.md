# 全国高校志愿填报空间数据库暨地理查询原型系统 (WebGIS)

> 武汉大学 遥感信息工程学院 · 2024级《空间数据库实习》第 13 组课程项目  
> 技术架构：`PostgreSQL 18.6` + `PostGIS 3.6.2` → `FastAPI` (Python) → `Vue 3` + `Leaflet` (TypeScript)

---

## 目录
- [一、项目简介与最新能力](#一项目简介与最新能力)
- [二、运行前置条件（Prerequisites）](#二运行前置条件prerequisites)
- [三、快速启动指引（Quickstart）](#三快速启动指引quickstart)
  - [方式 A：Windows 一键快速启动（推荐）](#方式-awindows-一键快速启动推荐)
  - [方式 B：手动分步启动（常规开发）](#方式-b手动分步启动常规开发)
- [四、后端连通性冒烟测试（必跑自检）](#四后端连通性冒烟测试必跑自检)
- [五、常见报错与避坑指南（FAQ）](#五常见报错与避坑指南faq)
- [六、工程目录结构](#六工程目录结构)
- [七、组内分工与协作红线规范](#七组内分工与协作红线规范)
- [八、开源协议与数据署名声明](#八开源协议与数据署名声明)

---

## 一、项目简介与最新能力

本项目构建了一个面向高考志愿填报辅助决策的高性能空间查询原型系统。系统深度整合招生录取大盘与高校空间地理属性，跑通“**招生事实约束 ∧ 空间拓扑筛选 ∧ 交通便利度圈选**”的复合检索链路：

1. **高校基础与多维检索**：涵盖教育部 2,952 所普通高校，支持院校层次、办学性质、属地等常规属性过滤；
2. **考生位次画像（CandidateProfile）**：支持基于生源省份、高考年份、科类与考生位次，动态匹配高校历年投档线与位次差（`rank_gap`），支持位次浮动窗口查询；
3. **空间与地理拓扑查询**：
   - **多级行政区覆盖**：基于 PostGIS `ST_Covers` 实现跨省、跨市行政区多边形包含筛选；
   - **空间几何选区**：支持前端交互式绘制多边形（GeoJSON Polygon）进行点位包含查询（`ST_Within`）；
   - **参考点距离**：基于 PostGIS `geography` 椭球测地距离（`ST_DWithin` / `ST_Distance`）计算任意点周边高校。
4. **真实交通设施（Transport POI）分析**：
   - 整合全国 1.89 万条真实铁路客运站、地铁站、民航机场 POI；
   - 计算高校各校区到最近交通设施的实际直线测地距离；
5. **专业录取与语义映射**：
   - 支持教育部标准专业目录（1,874 个专业）查询；
   - 打通高校具体招生专业表达（覆盖率 98.6%）与标准专业代码的关联，并呈现专业级历史录取分数。

> ⚠️ **核心准则**：系统**全程只读（Read-Only）**，不修改、不篡改底层任何业务事实与空间点位。

---

## 二、运行前置条件（Prerequisites）

在运行本项目前，请确保您的电脑上已安装并配置好以下基础环境：

| 依赖环境 | 建议版本 | 说明 |
| :--- | :--- | :--- |
| **PostgreSQL + PostGIS** | `PostgreSQL 18.x` + `PostGIS 3.6+` | 本地必须已导入并存在 **`gaokao3`** 数据库 |
| **Python** | `Python 3.11+`（推荐 3.11 或 3.12） | 后端 FastAPI 运行环境，自带 `pip` |
| **Node.js & npm** | `Node.js >= 20.19.0` 或 `>= 22.12.0` | 前端 Vue 3 + Vite 构建与运行环境 |
| **终端编码** | UTF-8 (`chcp 65001`) | Windows 终端请务必采用 UTF-8 编码，防止中文路径与输出乱码 |

---

## 三、快速启动指引（Quickstart）

### 方式 A：Windows 一键快速启动（推荐）

如果您在 Windows 环境下运行，根目录已提供一键自动化拉起脚本：

1. 双击运行根目录下的 **`start_dev.bat`**；
2. 脚本将自动完成：
   - 检查并从 `.env.example` 初始化 `backend/.env`；
   - 在独立窗口中激活虚拟环境并启动 FastAPI 后端（端口 8000）；
   - 在独立窗口中启动 Vite 前端开发服务器（端口 5173）；
   - 自动调用默认浏览器打开系统：`http://localhost:5173/`。

---

### 方式 B：手动分步启动（常规开发）

#### 步骤 1：配置后端环境变量
后端通过 `backend/.env` 读取数据库连接信息（该文件不入 Git 仓库）。  
首次使用请复制模板并配置您本机的数据库密码：

```bash
# 进入后端目录
cd backend

# 复制配置文件模板（Windows CMD 使用 copy，PowerShell 使用 cp）
copy .env.example .env
```

打开 `backend/.env`，核对以下关键配置项（重点修改密码）：
```ini
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=gaokao3
PGUSER=postgres
PGPASSWORD=您的PostgreSQL密码   # 例如：123456789
```

#### 步骤 2：启动后端服务 (FastAPI)
```bash
cd backend

# 1. 创建并激活 Python 虚拟环境
python -m venv .venv
.venv\Scripts\activate      # Windows CMD/PowerShell
# source .venv/bin/activate # macOS/Linux

# 2. 安装后端 Python 依赖
pip install -r requirements.txt

# 3. 启动开发服务器（支持热重载）
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
启动成功后，浏览器打开 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) 即可查看全部交互式 OpenAPI 接口文档。

#### 步骤 3：启动前端服务 (Vue 3 + Vite)
另开一个命令行终端：
```bash
cd frontend

# 1. 安装前端依赖
npm install

# 2. 启动前端 Vite 开发服务器
npm run dev
```
控制台将输出前端访问地址，打开浏览器访问：[http://localhost:5173/](http://localhost:5173/)。

---

## 四、后端连通性冒烟测试（必跑自检）

**在编写任何业务代码或怀疑环境异常时，请优先运行内置的冒烟测试脚本！**

```bash
cd backend
.venv\Scripts\python.exe smoke_test.py
```

- **自动化全覆盖**：脚本会在 `127.0.0.1:8123` 端口自动拉起独立只读服务实例；
- **全量业务断言**：自动实测全部 14 个核心接口（包括位次画像、综合查询、空间圈选、交通距离、专业目录等共 **217 项严格断言**）；
- **通过标志**：末尾输出 `通过 217 项，失败 0 项`。如果出现失败项，脚本会精准定位具体 SQL 或契约不匹配之处。

---

## 五、常见报错与避坑指南（FAQ）

### Q1: 后端启动报 `psycopg2.OperationalError: password authentication failed`
- **原因**：`backend/.env` 中的 `PGPASSWORD` 与您本机 PostgreSQL 的实际密码不一致。
- **解决**：编辑 `backend/.env`，将 `PGPASSWORD=` 改为您的正确密码，保存后重启后端即可。

### Q2: 后端启动报 `FATAL: database "gaokao3" does not exist`
- **原因**：连接配置中的数据库名称不正确，或者您本地尚未恢复 `gaokao3` 数据库。
- **解决**：
  1. 确认 PostgreSQL 中是否存在名为 `gaokao3` 的数据库（系统有硬校验，不可指向旧的 `gaokao` 或 `gaokao2`）；
  2. 确认 `backend/.env` 中的 `PGDATABASE=gaokao3`。

### Q3: 启动后报 `FATAL: the database system is starting up`
- **原因**：PostgreSQL 正在进行崩溃恢复或回放 WAL 日志。
- **解决**：这是数据库自动恢复过程，通常只需静候 5~10 秒，待数据库日志提示就绪后重新请求即可。

### Q4: Windows 终端运行脚本中文乱码或报 `invalid byte sequence for encoding "UTF8"`
- **原因**：Windows 默认代码页是 GBK（CP936）。
- **解决**：
  - 在终端中首先运行 `chcp 65001` 切换为 UTF-8 编码；
  - 运行 SQL 脚本时务必使用 `psql -f filename.sql`，严禁在控制台使用 `psql -c "含中文SQL"`。

### Q5: 前端页面显示空白或接口请求报 `Network Error` / `404` / `500`
- **排查步骤**：
  1. 确认后端终端中 uvicorn 正在监听 `127.0.0.1:8000`；
  2. 在浏览器中访问 `http://127.0.0.1:8000/docs` 验证后端是否正常存活；
  3. 检查 `backend/.env` 中 `CORS_ORIGINS` 是否包含了 `http://localhost:5173`。

### Q6: 前端 `npm install` 下载依赖很慢甚至超时
- **解决**：切换至国内 npm 镜像源：
  ```bash
  npm config set registry https://registry.npmmirror.com
  ```

---

## 六、工程目录结构

```text
spatial-db-webgis/
├── start_dev.bat               # Windows 一键启动后端与前端开发服务脚本
├── README.md                   # 本说明文档
├── backend/                    # FastAPI 后端项目
│   ├── .env.example            # 环境变量配置模板
│   ├── requirements.txt        # Python 依赖包清单
│   ├── smoke_test.py           # 217项接口与数据连通性冒烟测试套件
│   ├── capture_samples.py      # 自动化生成真实响应样例脚本
│   └── app/
│       ├── main.py             # FastAPI 应用入口、全局中间件、生命周期管理
│       ├── config.py           # Pydantic 环境变量校验与配置中心
│       ├── warnings.py         # 业务规范警告信息枚举
│       ├── db/
│       │   └── pool.py         # PostgreSQL 只读连接池管理
│       ├── schemas/            # Pydantic 请求与响应结构定义
│       ├── services/           # 招生、空间与底层 SQL 运算核心服务
│       └── api/                # API 路由层（colleges, search, spatial, majors 等）
├── frontend/                   # Vue 3 前端项目
│   ├── package.json            # 前端工程配置与依赖
│   ├── vite.config.ts          # Vite 构建与代理配置
│   └── src/
│       ├── main.ts             # 前端入口
│       ├── App.vue             # 页面根布局与主应用组件
│       ├── api/                # Axios / fetch 接口封装层
│       ├── stores/             # Pinia 状态管理（useSearchStore）
│       ├── types/              # TypeScript 类型契约定义
│       ├── components/         # 业务组件库（详情抽屉、招生统计等）
│       │   ├── map/            # Leaflet 地图核心图层与工具栏组件
│       │   └── transport/      # 交通设施查询面板与逻辑
│       └── views/              # 视图页面（SearchView 等）
├── sql/                        # SQL 脚本与查询归档
│   ├── init.sql                # 基础扩展初始化
│   ├── query/                  # 空间拓扑、KNN、多边形统计查询脚本归档
│   └── data/                   # 历史数据迁移与校准脚本
└── docs/                       # 核心设计文档
    ├── 00_协作规范.md          # 团队协作守则、分支模型与防冲突规范（★必读）
    ├── 01_接口样例.md          # 后端 14 个 API 的实测请求与响应数据样例
    └── 02_专业API对接文档.md  # 专业多层语义与前端接入详解说明
```

---

## 七、组内分工与协作红线规范

### 1. 成员分工与文件所有权（Ownership）

为避免团队协作中产生严重代码冲突，各模块划分了明确的负责人：

| 成员 | 模块分工 | 核心所有权范围（仅负责人可修改） |
| :--- | :--- | :--- |
| **莫炜钧** | 后端主负责人 / 系统总集成 | `backend/app/main.py`、`api/colleges.py`、`api/spatial.py`、`api/search.py` 总集成、连接池与环境 |
| **倪嵩** | 招生业务后端 | `backend/app/api/admissions.py`、`services/admission_service.py`、招生子查询与元数据 |
| **高天恒** | GIS 前端开发 | `frontend/src/components/map/*`（Leaflet 地图、Campus 图层、AdminRegion 图层、绘图交互） |
| **范传智** | 业务前端开发 | `frontend/src/views/*`、`components/CollegeDetailPanel.vue`、表格展示、对比与交互布局 |

> 详细协同规则与冲突裁决办法，请开工前必读 [`docs/00_协作规范.md`](docs/00_协作规范.md)。

### 2. 团队四大协作红线

1. **数据库全局只读（Strict Read-Only）**：
   - 严禁在代码或测试中执行 `INSERT`、`UPDATE`、`DELETE`、`ALTER`、`DROP` 等修改指令；
   - 数据库连接池强制启用只读事务（`default_transaction_read_only = on`）。
2. **空间坐标系统一规范**：
   - 空间坐标一律采用 **WGS84（EPSG:4326）**；
   - GeoJSON 坐标格式必须严格遵循 **`[经度 lon, 纬度 lat]`**，严禁颠倒。
3. **接口契约冻结保护**：
   - 前后端字段和接口路径严格遵循《开发任务执行书》与 `docs/01_接口样例.md`；
   - 任何涉及字段重命名、增删必填项的修改，**必须经全组四人共同开会确认**，禁止私自修改。
4. **分支与提交规范**：
   - 严禁直接向 `main` 分支推代码；
   - 个人在 `feature/<姓名缩写>-<功能名>` 开发，验证无误后向 `dev` 分支提交 PR；
   - Commit Message 统一采用标准规范：`feat: / fix: / docs: / refactor:`。

---

## 八、开源协议与数据署名声明

1. **交通 POI 数据合规**：
   - 本项目高校周边交通站点 POI 数据源自 **OpenStreetMap**；
   - 数据受 **ODbL (Open Database License)** 许可协议约束；
   - 在前端地图界面呈现、结果导出或报告撰写中，均须醒目标注：**`© OpenStreetMap contributors`**。
2. **距离测算说明**：
   - 系统所有“周边交通设施距离”均为校区坐标至站点坐标的**直线测地距离**（由 PostGIS `ST_Distance(geom::geography)` 计算得出），非实际城市道路步行或驾车导航路程。
