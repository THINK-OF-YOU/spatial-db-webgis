/**
 * /api/colleges/{school_id}/transport 的契约类型。
 *
 * 字段逐字镜像真实 API，全部保持 snake_case，不做二次映射。
 */

/** 交通设施 mode：来源口径，取值限于库内真实值。 */
export type TransportMode = 'rail' | 'metro' | 'airport' | 'rail_halt'

/** 当前桌面端提供的查询半径。API 本身仍支持 (0, 20] km。 */
export type TransportRadius = 1 | 3 | 5

/** 单个交通站点（§4.11 字段）。 */
export interface TransportItem {
  poi_id: number
  mode: TransportMode
  /** 站点名以 OSM 原名 name 为准。 */
  name: string
  /** name_zh 大量缺失，缺失时返回 null；不得用 name 填充、不得推算。 */
  name_zh: string | null
  lon: number
  lat: number
  /** 到最近 Campus 的米制测地距离（对外返回 km）。 */
  distance_km: number
  campus_id: number
  campus_name: string
}

/**
 * transport 响应。§4.11 示例为 { items, total, warnings } ——
 * 没有 page / page_size（它不是分页列表，用 limit 控制条数）。
 */
export interface TransportResponse {
  items: TransportItem[]
  total: number
  warnings: string[]
}

export type TransportSummaryMode = Exclude<TransportMode, 'rail_halt'>

export interface TransportSummaryResponse {
  school_id: number
  items: Record<TransportSummaryMode, TransportItem | null>
  warnings: string[]
}

/** 前端调用 loadTransport 时的可选参数，映射 §4.11 的可选 query。 */
export interface TransportQuery {
  /** 默认 3，上限 20。 */
  radiusKm?: number
  /** 可重复；取值限于 rail / metro / airport / rail_halt。不传 = 全部。 */
  modes?: TransportMode[]
  /** 默认 20，上限 200。 */
  limit?: number
}

/** mode 展示文案。仅前端展示用，非契约字段，后端不返回。 */
export const MODE_LABELS: Record<TransportMode, string> = {
  metro: '地铁',
  rail: '铁路站',
  airport: '机场',
  rail_halt: '铁路停靠站',
}

/** 分组展示顺序（不是排序，只决定面板里分组的先后）。 */
export const MODE_ORDER: TransportMode[] = ['metro', 'rail', 'airport', 'rail_halt']

export const RADIUS_OPTIONS: TransportRadius[] = [1, 3, 5]
