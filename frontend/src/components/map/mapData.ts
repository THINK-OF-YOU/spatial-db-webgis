import campusesRaw from '../../mocks/campuses.geojson?raw'
import { request } from '../../api/http'
import regionsRaw from '../../mocks/regions.geojson?raw'
import type { FeatureCollection, MultiPolygon, Point, Polygon } from 'geojson'
import type {
  CampusProps,
  CampusStatus,
  NearbyResponse,
  RegionProps,
  RegionLevel,
  WithinResponse,
} from './types'

/**
 * 地图数据访问层。
 *
 * Mock 先行：USE_MOCK = true 时读本地 GeoJSON / 本地计算；后端在搭档机上，
 * 联调时改成 false 即切真实 /api（字段不变，组件不重写）。
 */
const USE_MOCK = false

// 冻结 warning 文案（与后端 warnings.py 一致，见协作规范 §5.4）
const WARN_CANDIDATE = '本次空间查询包含候选校区'

const campusesFC = JSON.parse(campusesRaw) as FeatureCollection<Point, CampusProps>
const regionsFC = JSON.parse(regionsRaw) as FeatureCollection<Polygon | MultiPolygon, RegionProps>

async function get<T>(path: string): Promise<T> {
  return request<T>(path)
}

async function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

/** /api/map/campuses：浏览态同时返回 CONFIRMED 与 CANDIDATE。 */
export async function loadCampuses(): Promise<FeatureCollection<Point, CampusProps>> {
  if (USE_MOCK) return campusesFC
  return get<FeatureCollection<Point, CampusProps>>('/map/campuses')
}

export interface RegionQuery {
  level?: RegionLevel
  parentAdcode?: string
  simplify?: number
}

/** /api/map/regions：支持省级入口与 parent_adcode 真实下钻。 */
export async function loadRegions(
  query: RegionQuery = {},
): Promise<FeatureCollection<Polygon | MultiPolygon, RegionProps>> {
  const level = query.level ?? (query.parentAdcode ? undefined : 'province')
  if (USE_MOCK) {
    const features = regionsFC.features.filter((feature) => {
      if (query.parentAdcode) return feature.properties.parent_adcode === query.parentAdcode
      return !level || feature.properties.level === level
    })
    return { type: 'FeatureCollection', features }
  }
  const params = new URLSearchParams({ simplify: String(query.simplify ?? 0.01) })
  if (level) params.set('level', level)
  if (query.parentAdcode) params.set('parent_adcode', query.parentAdcode)
  return get<FeatureCollection<Polygon | MultiPolygon, RegionProps>>(
    `/map/regions?${params.toString()}`,
  )
}

/** /api/spatial/nearby：参考点 + 半径。默认只用 CONFIRMED（契约 §3.3）。 */
export async function nearby(
  lon: number,
  lat: number,
  radiusKm: number,
  verifyStatus?: CampusStatus[],
): Promise<NearbyResponse> {
  const statuses = verifyStatus && verifyStatus.length ? verifyStatus : (['CONFIRMED'] as CampusStatus[])
  if (USE_MOCK) {
    const items = campusesFC.features
      .filter((f) => statuses.includes(f.properties.verify_status))
      .map((f) => {
        const [clon, clat] = f.geometry.coordinates
        const d = haversineKm(lon, lat, clon, clat)
        return { f, d }
      })
      .filter((x) => x.d <= radiusKm)
      .sort((a, b) => a.d - b.d)
      .map(({ f, d }) => ({
        school_id: f.properties.school_id,
        school_name: f.properties.school_name,
        campus_id: f.properties.campus_id,
        campus_name: f.properties.campus_name,
        verify_status: f.properties.verify_status,
        distance_km: round2(d),
      }))
    return { items, warnings: statuses.includes('CANDIDATE') ? [WARN_CANDIDATE] : [] }
  }
  const qs = new URLSearchParams({ lon: String(lon), lat: String(lat), radius_km: String(radiusKm) })
  statuses.forEach((s) => qs.append('verify_status', s))
  return get<NearbyResponse>(`/spatial/nearby?${qs.toString()}`)
}

/** /api/spatial/within：GeoJSON Polygon 内的校区。 */
export async function within(
  geometry: Polygon | MultiPolygon,
  verifyStatus?: CampusStatus[],
): Promise<WithinResponse> {
  const statuses = verifyStatus && verifyStatus.length ? verifyStatus : (['CONFIRMED'] as CampusStatus[])
  if (USE_MOCK) {
    const polys = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates
    const items = campusesFC.features
      .filter((f) => statuses.includes(f.properties.verify_status))
      .filter((f) => {
        const [clon, clat] = f.geometry.coordinates
        return polys.some((rings) => pointInPolygon(clon, clat, rings))
      })
      .map((f) => {
        const [lon, lat] = f.geometry.coordinates
        return {
          school_id: f.properties.school_id,
          school_name: f.properties.school_name,
          campus_id: f.properties.campus_id,
          campus_name: f.properties.campus_name,
          verify_status: f.properties.verify_status,
          lon,
          lat,
        }
      })
    return { items, total: items.length, warnings: statuses.includes('CANDIDATE') ? [WARN_CANDIDATE] : [] }
  }
  return post<WithinResponse>('/spatial/within', { geometry, verify_status: statuses })
}

function round2(n: number): number {
  return Math.round(n * 100) / 100
}

function toRad(deg: number): number {
  return (deg * Math.PI) / 180
}

function haversineKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const R = 6371
  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(lon2 - lon1)
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

/** 射线法点在多边形内判断（rings: 一个多边形的环数组，环元素为 [lon, lat]）。 */
function pointInPolygon(lon: number, lat: number, rings: number[][][]): boolean {
  const ring = rings[0]
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    const intersects = (yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi
    if (intersects) inside = !inside
  }
  return inside
}
