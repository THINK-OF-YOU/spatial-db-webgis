import type { Feature, Point, Polygon } from 'geojson'
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

export type ViewportCampusStatus = 'CONFIRMED' | 'CANDIDATE'

/** 当前地图 BBOX 返回的纯 GeoJSON Campus；只用于展示层，不是业务查询结果。 */
export interface ViewportCampusProps {
  campus_id: number
  school_id: number
  school_name: string
  campus_name: string
  verify_status: ViewportCampusStatus
}

export type ViewportCampusFeature = Feature<Point, ViewportCampusProps>

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
  /** 仅 CandidateProfile 位次模式返回的每校代表历史投档事实。 */
  reference_admission?: ReferenceAdmission
}

/**
 * 当前一次搜索上下文中加入比较栏的轻量事实快照。
 *
 * 它刻意复用 SearchResult 的字段，而不是保存完整 CollegeDetail；这样翻页
 * 或地图视野更新后，比较仍然使用加入当时的同口径结果，不会重新挑选历史事实。
 */
export type CompareCollegeSnapshot = SearchResult

/** 当前一次 CandidateProfile 综合查询实际提交给比较附属接口的招生上下文。 */
export interface CompareAdmissionContext {
  source_province: string
  year: number
  category: string
  batch: string | null
  candidate_rank: number
}

export interface ReferenceAdmission {
  admission_id: number
  unit_id: number
  unit_name: string
  source_province: string
  year: number
  category: string | null
  batch: string | null
  min_score: number | null
  min_rank: number
  /** historical_min_rank - candidate_rank。 */
  rank_gap: number
}

export interface CandidateProfileState {
  source_province: string
  year: number | null
  category: string
  input_mode: 'rank' | 'score'
  /** 位次模式下由用户直接填写。 */
  rank: number | null
  /** 分数模式下由用户填写；只做整数精确匹配。 */
  score: number | null
  /** 分数解析成功后的一分一段累计人数。 */
  resolved_rank: number | null
  resolution_status:
    | 'idle'
    | 'loading'
    | 'resolved'
    | 'ambiguous'
    | 'not_found'
    | 'unsupported_context'
    | 'error'
  batch: string
}

/** 运行时查询窗口，不属于 CandidateProfile 固有字段。 */
export interface RankWindowState {
  ahead: number
  behind: number
}

export interface AdmissionSearchCondition {
  source_province?: string
  year?: number
  category?: string
  batch?: string
  rank?: number
  rank_ahead?: number
  rank_behind?: number
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

export type TransportSearchMode = 'metro' | 'rail' | 'airport'

export interface TransportSearchCondition {
  mode: TransportSearchMode
  max_distance_km: number
}

/** 与 backend/app/api/search.py 的 SearchRequest 逐字段对应。 */
export interface SearchRequest {
  admission?: AdmissionSearchCondition
  college?: CollegeSearchCondition
  regions: string[]
  spatial?: SpatialSearchCondition
  /** 交通条件全部绑定同一个 Campus，并按数组顺序做 AND。 */
  transport?: TransportSearchCondition[]
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
  compareColleges: CompareCollegeSnapshot[]
  referencePoint: ReferencePoint | null
  radiusKm: number | null
  /** 行政区 adcode；直接对应 /api/search 的 regions。 */
  selectedRegions: string[]
  /** 标准 GeoJSON Polygon，坐标顺序 [longitude, latitude]。 */
  drawnGeometry: DrawnGeometry | null
  mapBounds: MapBounds | null
  /** 当前地图视野内的 Campus；由同一次 BBOX 请求共同驱动地图与高校列表。 */
  viewportCampuses: ViewportCampusFeature[]
  /** false: 仅 CONFIRMED；true: CONFIRMED + CANDIDATE。 */
  campusStatus: boolean
  loading: boolean
  /** 最近一次成功加载是否来自 POST /api/search；用于区分未查询与 0 结果。 */
  hasSearched: boolean
  /** source_province/year/category/batch 的唯一招生上下文来源。 */
  candidateProfile: CandidateProfileState
  /** 是否启用必须得到 effective_rank 的 CandidateProfile 模式。 */
  candidateProfileEnabled: boolean
  /** 本次怎么看历史事实；与 CandidateProfile 身份语义分离。 */
  rankWindow: RankWindowState
  /** 仅后端业务提示；网络、HTTP、解析错误由对应组件处理。 */
  warnings: string[]
}
