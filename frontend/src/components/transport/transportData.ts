import type {
  TransportItem,
  TransportMode,
  TransportQuery,
  TransportResponse,
} from './transportTypes'

/**
 * transport 数据访问层。
 *
 * Mock 先行：USE_MOCK = true 时读本地 mock；后端（莫炜钧 API 10）就绪后
 * 改成 false 即切真实 /api，字段不变、组件不重写。
 *
 * 注意：这里的 mock 只服务于前端开发，字段必须与 Contract 逐字一致，
 * 不因 mock 方便而扩展正式接口字段（前端工作契约 §13）。
 */
const USE_MOCK = true
const API_BASE = '/api'

// 覆盖不足 warning。文案取《任务执行书》§4.12 示例「部分高校周边缺少交通设施数据」。
// 注意：它还没并入 backend/app/warnings.py（协作规范 §5.4 只冻结了 3 条），
//       联调时提醒莫炜钧把这条加进后端 warnings 常量，前端只展示不自行编造。
const WARN_NO_COVERAGE = '部分高校周边缺少交通设施数据'

// ── mock 数据 ────────────────────────────────────────────────────────
// key: school_id。站点名用 OSM 原名 name；name_zh 有意留 null 以演示缺失态。
// distance_km 为到最近 Campus 的直线距离，按升序排列。
// 覆盖不全：没有数据的学校（如 school_id 9）走「查不到 → warning」分支，
// 绝不渲染成“该高校周边没有交通站点”。
const MOCK: Record<number, TransportItem[]> = {
  // 北京大学 校本部（116.3103, 39.9928）
  1: [
    { poi_id: 41207, mode: 'metro', name: '北京大学东门', name_zh: '北京大学东门', lon: 116.3158, lat: 39.9879, distance_km: 0.6, campus_id: 1, campus_name: '校本部' },
    { poi_id: 41208, mode: 'metro', name: '中关村', name_zh: null, lon: 116.317, lat: 39.984, distance_km: 1.1, campus_id: 1, campus_name: '校本部' },
    { poi_id: 41209, mode: 'metro', name: '海淀黄庄', name_zh: null, lon: 116.318, lat: 39.976, distance_km: 1.9, campus_id: 1, campus_name: '校本部' },
    { poi_id: 41550, mode: 'rail_halt', name: '清华园', name_zh: null, lon: 116.32, lat: 39.996, distance_km: 0.9, campus_id: 1, campus_name: '校本部' },
  ],
  // 清华大学 校本部（116.3266, 39.999）
  2: [
    { poi_id: 41300, mode: 'metro', name: '清华东路西口', name_zh: null, lon: 116.332, lat: 39.998, distance_km: 0.5, campus_id: 2, campus_name: '校本部' },
    { poi_id: 41301, mode: 'metro', name: '五道口', name_zh: '五道口', lon: 116.337, lat: 39.992, distance_km: 1.1, campus_id: 2, campus_name: '校本部' },
    { poi_id: 41551, mode: 'rail_halt', name: '清华园', name_zh: null, lon: 116.32, lat: 39.996, distance_km: 0.7, campus_id: 2, campus_name: '校本部' },
  ],
  // 武汉大学 文理学部（114.356, 30.5365）
  3: [
    { poi_id: 42001, mode: 'metro', name: '街道口', name_zh: '街道口', lon: 114.356, lat: 30.536, distance_km: 0.1, campus_id: 3, campus_name: '文理学部' },
    { poi_id: 42002, mode: 'metro', name: '广埠屯', name_zh: null, lon: 114.363, lat: 30.528, distance_km: 1.1, campus_id: 3, campus_name: '文理学部' },
    { poi_id: 42003, mode: 'metro', name: '洪山广场', name_zh: null, lon: 114.343, lat: 30.547, distance_km: 1.6, campus_id: 3, campus_name: '文理学部' },
    { poi_id: 42100, mode: 'rail', name: '武昌', name_zh: '武昌站', lon: 114.316, lat: 30.531, distance_km: 3.9, campus_id: 3, campus_name: '文理学部' },
    { poi_id: 42101, mode: 'rail', name: '汉口', name_zh: null, lon: 114.251, lat: 30.621, distance_km: 13.5, campus_id: 3, campus_name: '文理学部' },
  ],
  // 浙江大学 紫金港校区（120.0838, 30.3018）
  4: [
    { poi_id: 43001, mode: 'metro', name: '浙大紫金港', name_zh: '浙大紫金港', lon: 120.079, lat: 30.306, distance_km: 0.6, campus_id: 4, campus_name: '紫金港校区' },
    { poi_id: 43002, mode: 'metro', name: '三坝', name_zh: null, lon: 120.071, lat: 30.312, distance_km: 1.7, campus_id: 4, campus_name: '紫金港校区' },
  ],
  // 四川大学 望江校区（104.08, 30.63）—— 故意留空，演示覆盖不足 warning
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

/** 收敛 radiusKm / limit 到契约边界（默认 3 / 20，上限 20 / 200）。 */
function clampQuery(q: TransportQuery): { radiusKm: number; limit: number; modes?: TransportMode[] } {
  const radiusKm = Math.min(Math.max(q.radiusKm ?? 3, 0), 20)
  const limit = Math.min(Math.max(q.limit ?? 20, 1), 200)
  const modes = q.modes && q.modes.length ? q.modes : undefined
  return { radiusKm, limit, modes }
}

/**
 * /api/colleges/{school_id}/transport：该校周边交通站点。
 * 返回按 distance_km 升序、最多 limit 条；查不到站点时带覆盖不足 warning。
 */
export async function loadTransport(
  schoolId: number,
  query: TransportQuery = {},
): Promise<TransportResponse> {
  const { radiusKm, limit, modes } = clampQuery(query)

  if (USE_MOCK) {
    const all = MOCK[schoolId] ?? []
    const items = all
      .filter((t) => !modes || modes.includes(t.mode))
      .filter((t) => t.distance_km <= radiusKm)
      .sort((a, b) => a.distance_km - b.distance_km)
      .slice(0, limit)
    // 覆盖不齐：查不到站点时用 warning 说明，不能显示成“周边没有站点”。
    const warnings = items.length === 0 ? [WARN_NO_COVERAGE] : []
    return { items, total: items.length, warnings }
  }

  const qs = new URLSearchParams({ radius_km: String(radiusKm), limit: String(limit) })
  modes?.forEach((m) => qs.append('mode', m))
  return get<TransportResponse>(`/colleges/${schoolId}/transport?${qs.toString()}`)
}
