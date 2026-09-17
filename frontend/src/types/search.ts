import type { Polygon } from 'geojson'
import type { CollegeFilters } from './college'

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

/** M1 使用 College 列表接口的已确认筛选字段。 */
export type SearchFilters = CollegeFilters

/** GET /colleges 与 POST /search 可共同写入的高校结果最小结构。 */
export interface SearchResult {
  school_id: number
  national_code: string | null
  name: string
  edu_level: string | null
  reg_province: string | null
  has_campus: boolean
  /** 仅 GET /colleges 返回。 */
  has_admission?: boolean
  /** 仅 POST /search 在提供参考点时可能返回。 */
  distance_km?: number | null
}

export interface AdmissionSearchCondition {
  source_province?: string
  year?: number
  category?: string
  batch?: string
}

export interface CollegeSearchCondition {
  edu_level?: string
}

export interface SpatialSearchCondition {
  reference_point?: ReferencePoint
  radius_km?: number
  include_candidate_campus: boolean
  geometry?: DrawnGeometry
}

/** 与 backend/app/api/search.py 的 SearchRequest 逐字段对应。 */
export interface SearchRequest {
  admission?: AdmissionSearchCondition
  college?: CollegeSearchCondition
  regions: string[]
  spatial?: SpatialSearchCondition
  page: number
  page_size: number
}

export interface SearchResponse {
  items: SearchResult[]
  total: number
  page: number
  page_size: number
  warnings: string[]
}

export interface SearchState {
  filters: SearchFilters
  results: SearchResult[]
  selectedCollege: SelectedCollegeType | null
  compareCollegeIds: number[]
  referencePoint: ReferencePoint | null
  radiusKm: number | null
  /** 行政区 adcode；直接对应 /api/search 的 regions。 */
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
