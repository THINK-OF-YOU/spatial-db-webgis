import type { InjectionKey, ShallowRef } from 'vue'
import type * as L from 'leaflet'

/** Leaflet 地图实例注入键。MapView 提供，CampusLayer / RegionLayer 注入消费。 */
export const MAP_KEY: InjectionKey<ShallowRef<L.Map | null>> = Symbol('leaflet-map')
