import type { Polygon } from 'geojson'

/** 轻量选中状态；school_id 沿用执行书中的数值 ID。 */
export interface SelectedCollegeType {
  school_id: number
}

/** WGS84 / EPSG:4326，经度 lon、纬度 lat。 */
export interface ReferencePoint {
  lon: number
  lat: number
}

/** 只存普通 JSON，不能存 Leaflet LatLngBounds 实例。 */
export interface MapBounds {
  west: number
  south: number
  east: number
  north: number
}

export type DrawnGeometry = Polygon

/** 本轮空占位，业务筛选接入时按确认的契约增加 snake_case 字段。 */
export type SearchFilters = Record<string, never>

/** 仅定义结果身份下限，不代表完整 API 响应 DTO。 */
export type SearchResult = SelectedCollegeType

export interface SearchState {
  filters: SearchFilters
  results: SearchResult[]
  selectedCollege: SelectedCollegeType | null
  compareCollegeIds: number[]
  referencePoint: ReferencePoint | null
  radiusKm: number | null
  /** 行政区 adcode；不代表 /api/search 的 regions 请求结构。 */
  selectedRegions: string[]
  /** 标准 GeoJSON Polygon，坐标顺序 [longitude, latitude]。 */
  drawnGeometry: DrawnGeometry | null
  mapBounds: MapBounds | null
  /** false: 仅 CONFIRMED；true: CONFIRMED + CANDIDATE。 */
  campusStatus: boolean
  loading: boolean
  /** 仅后端业务提示；网络、HTTP、解析错误由对应组件处理。 */
  warnings: string[]
}
