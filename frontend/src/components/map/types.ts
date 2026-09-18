import type { Feature, MultiPolygon, Polygon } from 'geojson'
import type {
  ViewportCampusFeature,
  ViewportCampusProps,
  ViewportCampusStatus,
} from '../../types/search'

/** 校区核验状态，契约冻结：CONFIRMED=已核验，CANDIDATE=候选。 */
export type CampusStatus = ViewportCampusStatus

/** /api/map/campuses 的 feature properties（契约 §4.6）。 */
export type CampusProps = ViewportCampusProps

export type CampusFeature = ViewportCampusFeature

/** /api/map/regions 的 feature properties（契约 §4.7）。 */
export type RegionLevel = 'province' | 'city' | 'district'

export interface RegionProps {
  adcode: string
  name: string
  level: RegionLevel
  parent_adcode: string | null
  children_num: number
}

export type RegionFeature = Feature<Polygon | MultiPolygon, RegionProps>

/** /api/spatial/nearby 的 item（契约 §4.8）。 */
export interface NearbyItem {
  school_id: number
  school_name: string
  campus_id: number
  campus_name: string
  verify_status: CampusStatus
  distance_km: number
}

export interface NearbyResponse {
  items: NearbyItem[]
  warnings: string[]
}

/** /api/spatial/within 的 item（契约 §4.9）。 */
export interface WithinItem {
  school_id: number
  school_name: string
  campus_id: number
  campus_name: string
  verify_status: CampusStatus
  lon: number
  lat: number
}

export interface WithinResponse {
  items: WithinItem[]
  total: number
  warnings: string[]
}

/** 地图交互模式。 */
export type DrawMode = 'browse' | 'point' | 'rect' | 'polygon'
