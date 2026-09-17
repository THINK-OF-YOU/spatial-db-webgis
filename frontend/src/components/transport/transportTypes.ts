/**
 * /api/colleges/{school_id}/transport 的契约类型。
 *
 * 契约见《任务执行书》§4.11，字段逐字一致、全部 snake_case，不做二次映射。
 * 后端 Owner：莫炜钧（API 10）。本文件是前端侧的类型镜像，配合 Mock 先行。
 */

/** 交通设施 mode：来源口径，取值限于库内真实值。 */
export type TransportMode = 'rail' | 'metro' | 'airport' | 'rail_halt'

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
  metro: '地铁站',
  rail: '火车站',
  airport: '机场',
  rail_halt: '铁路停靠站',
}

/** 分组展示顺序（不是排序，只决定面板里分组的先后）。 */
export const MODE_ORDER: TransportMode[] = ['metro', 'rail', 'airport', 'rail_halt']
