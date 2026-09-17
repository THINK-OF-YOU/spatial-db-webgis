# 前端 · Vue 3 + Leaflet

高校志愿填报空间查询原型 V1 的 PC 单页前端。

- **业务 UI**（布局 / 筛选 / 列表 / Drawer / 对比 / 导出）：范传智
- **GIS 地图**（Leaflet / Campus / AdminRegion / 参考点 / 半径 / 绘制）：高天恒

两者通过唯一的 `useSearchStore` 共享状态，不各自维护第二套状态。

---

## 技术栈

| 项 | 值 |
|---|---|
| 框架 | Vue 3.5 + Pinia 4 |
| 地图 | Leaflet 1.9.4 |
| 语言 | TypeScript（严格模式） |
| 构建 | Vite 8 |

底图使用 **Esri World Street Map**（WGS84 / Web Mercator，无 GCJ02 偏移，需联网）。

---

## 目录结构

```
src/
├── App.vue                    根组件（把 MapView 接入 SearchView 的 #map 插槽）
├── main.ts
├── style.css
├── views/
│   └── SearchView.vue         College 搜索、筛选、结果、分页（范传智）
├── stores/
│   └── useSearchStore.ts      全页面唯一共享状态（范传智主维护）
├── types/                     共享类型
├── api/                       http.ts 公共请求；colleges.ts 真实高校接口
├── components/
│   ├── CollegeDetailPanel.vue 高校详情侧栏，响应 selectedCollege
│   └── map/                   地图 GIS 模块（高天恒）
│       ├── MapView.vue        地图初始化 / 参考点 / 半径圆 / 矩形与多边形绘制
│       ├── CampusLayer.vue    校区点渲染与点击、选中定位高亮、结果淡化
│       ├── RegionLayer.vue    行政区面渲染 / 高亮 / 选择
│       ├── MapToolbar.vue     浏览 / 参考点 / 矩形 / 多边形 / 清除空间
│       ├── MapLegend.vue      图例（CONFIRMED / CANDIDATE）
│       ├── mapData.ts         地图数据访问层（Mock / 真实 API 切换）
│       ├── mapContext.ts      地图实例注入键
│       └── types.ts           地图接口类型
└── mocks/
    ├── campuses.geojson       校区 Mock（字段对齐契约 §4.6）
    └── regions.geojson        行政区 Mock（字段对齐契约 §4.7）
```

---

## 启动

```bash
cd frontend
npm install
npm run dev          # 开发服务器 http://localhost:5173
```

其他脚本：

```bash
npm run type-check   # vue-tsc + tsc 类型检查
npm run build        # 类型检查 + 生产打包
npm run preview      # 预览打包产物
```

---

## Mock 与真实后端切换

地图数据统一走 `components/map/mapData.ts`，组件不直接发请求：

```ts
const USE_MOCK = false  // M1 默认真实数据；仅 GIS 独立开发可改为 true
```

- College 列表和详情始终使用真实 FastAPI，不回退 Mock。
- Vite 开发与预览的 `/api` 默认代理到 `http://127.0.0.1:8000`。远程后端可在本地环境设置 `API_TARGET` 后重启 Vite；不提交 `.env` 或凭据。
- 生产静态部署需由 Web 服务器反向代理 `/api`，Vite 配置不会写入生产包。
- 地图浏览请求复用 `api/http.ts`；行政区使用现有 `simplify=0.01` 参数降低传输量。
- 切换只改数据源，组件字段不变（契约 §13）。

`nearby` / `within` 也已封装（默认只用 `CONFIRMED`，可传 `verify_status` 覆盖），
用于独立验证与调试，不写入主业务 `results`（契约 §15）。

---

## 地图模块交互

| 操作 | 效果 |
|---|---|
| 工具栏「参考点」+ 点击地图 | 设置 `referencePoint`（并给默认半径 300km），画参考点标记 + 半径圆 |
| 工具栏「矩形」+ 拖拽 | 画矩形 → 转 GeoJSON Polygon 写入 `drawnGeometry` |
| 工具栏「多边形」+ 点击顶点 + 双击闭合 | 画多边形 → 转 GeoJSON Polygon 写入 `drawnGeometry` |
| 点击行政区面 | 增删 `selectedRegions` 的 adcode，并高亮 |
| 点击校区点 | `setSelectedCollege`，业务 UI 打开 Drawer |
| 列表选中学校 | 地图定位并高亮该校区（无 Campus 则不动、不报错） |
| 「清除空间」 | `clearSpatialFilters`，同步清参考点/圆/绘制/行政区高亮 |

---

## 共享状态约定（严格遵守）

- 地图**只产生空间条件**，写入 `referencePoint / radiusKm / selectedRegions / drawnGeometry`，
  **不覆盖 `results`、不自动请求 `/api/search`**。
- 地图读取 `selectedCollege`（定位高亮）、`results`（淡化非结果学校）。
- Leaflet 实例（`L.Map / L.Marker / L.Layer` 等）全部 `markRaw`，**不进 Pinia**，保留在组件内。
- 坐标：GeoJSON 固定 `[lon, lat]`；进入 Leaflet 才转 `[lat, lng]`，不交换经纬度。
- `CONFIRMED` = 已核验校区；`CANDIDATE` 文案固定「候选校区点，尚未完成实体级人工核验」。

---

## M1 业务交互与边界

- 查询按钮 / Enter 将草稿条件写入 `filters`，发送 `GET /api/colleges` 的 `q / edu_level / reg_province / page / page_size`。新查询回到第一页；分页只使用已应用的条件。
- `reg_province` 显示为“登记地区”，按原值精确筛选；不是空间选区。
- `results` 只存当前页的真实高校，是唯一主业务结果源；后端 `warnings` 去重展示。网络/HTTP/解析错误单独显示并提供重试。
- 选中列表或校区都通过 `selectedCollege.school_id` 请求真实详情。详情保留在侧栏局部状态，不把详情或 Leaflet 实例放进 Store。
- 新请求取消旧请求，避免快速切换时旧响应覆盖新结果；15 秒超时；详情支持关闭、Esc 与返回焦点。
- 既有地图空间工具保留，但 M1 高校查询不使用空间条件、不请求 `/api/search`、招生接口或附近/范围接口。
- GIS 小范围整合：真实数据开关、公共请求复用、异步图层完成后同步选中/结果；补建既有 `marker` pane，并防止绘制模式的图层点击拦截。未重写 GIS 算法。

## 本轮验证（2026-09-17）

- `npm run type-check`、`npm run build`。
- 本机 `gaokao3` 真实后端：2,952 所高校、432 个校区；列表、名称搜索、层次/登记地区组合筛选、分页、真实详情。
- 浏览器验证 CONFIRMED / CANDIDATE / 无 Campus、加载、空结果、HTTP 错误与重试。故障状态通过浏览器请求拦截验证，正常流程全部使用真实 API。
- 地图→详情、列表→定位高亮、参考点/半径、矩形、多边形、行政区、清除空间；地图操作不覆盖业务 results。
- 浏览器控制台无未捕获异常；未请求 M2/M4 业务接口。底图依赖 Esri 网络服务。
