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
│   └── SearchView.vue         业务页面骨架（范传智）
├── stores/
│   └── useSearchStore.ts      全页面唯一共享状态（范传智主维护）
├── types/                     共享类型
├── api/                       接口封装（范传智，待建）
├── components/
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
const USE_MOCK = true   // true：读本地 GeoJSON；false：请求 /api
```

- 后端在搭档机上，本机开发时 `USE_MOCK = true` 即可独立跑通地图。
- 联调时改成 `false`，并在 `vite.config.ts` 加 `/api` 代理指向后端机（如 `http://<后端机IP>:8000`）。
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

## 给范传智的协调事项

1. `package.json` 已新增 `leaflet` 与 `@types/leaflet`（`package.json` 归范传智，走 PR 时请确认）。
2. `api/` 目录目前为空；地图用了 `components/map/mapData.ts` 做数据层，联调时可并进 `api/map`。
3. 联调真实后端时需在 `vite.config.ts` 加 `/api` 代理（见上）。
