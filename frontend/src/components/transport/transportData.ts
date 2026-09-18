import { request } from '../../api/http'
import type {
  TransportMode,
  TransportQuery,
  TransportResponse,
  TransportSummaryResponse,
} from './transportTypes'

/**
 * 真实 Transport API 数据访问层。
 *
 * 列表和地图不在这里各自请求；App 级局部 controller 只调用一次本函数，
 * 再把同一个 TransportResponse 分发给 Panel 与 Leaflet Layer。
 */
export async function loadTransport(
  schoolId: number,
  query: TransportQuery = {},
  signal?: AbortSignal,
): Promise<TransportResponse> {
  const radiusKm = Math.min(Math.max(query.radiusKm ?? 3, 0.01), 20)
  const limit = Math.min(Math.max(query.limit ?? 20, 1), 200)
  const modes: TransportMode[] | undefined = query.modes?.length
    ? [...new Set(query.modes)]
    : undefined

  const params = new URLSearchParams({
    radius_km: String(radiusKm),
    limit: String(limit),
  })
  modes?.forEach((mode) => params.append('mode', mode))

  return request<TransportResponse>(
    `/colleges/${schoolId}/transport?${params.toString()}`,
    { signal },
  )
}

/** 每种主要交通类型各自独立求最近点，不能由 V1 列表的前 N 条推导。 */
export function loadTransportSummary(
  schoolId: number,
  signal?: AbortSignal,
): Promise<TransportSummaryResponse> {
  return request<TransportSummaryResponse>(
    `/colleges/${schoolId}/transport/summary`,
    { signal },
  )
}
