import { defineStore } from 'pinia'
import type { DrawnGeometry, ReferencePoint, SearchState, SelectedCollegeType } from '../types'

export const useSearchStore = defineStore('search', {
  state: (): SearchState => ({
    filters: {},
    // 全页面唯一业务结果源，由业务页面统一查询后更新；地图仅消费。
    results: [],
    selectedCollege: null,
    compareCollegeIds: [],
    referencePoint: null,
    radiusKm: null,
    selectedRegions: [],
    drawnGeometry: null,
    mapBounds: null,
    campusStatus: false,
    loading: false,
    warnings: [],
  }),
  actions: {
    setSelectedCollege(college: SelectedCollegeType | null) {
      if (this.selectedCollege?.school_id === college?.school_id) return
      this.selectedCollege = college === null ? null : { school_id: college.school_id }
    },
    setReferencePoint(point: ReferencePoint | null) {
      this.referencePoint = point === null ? null : { lon: point.lon, lat: point.lat }
    },
    setRadiusKm(radiusKm: number | null) {
      this.radiusKm = radiusKm
    },
    setSelectedRegions(adcodes: string[]) {
      this.selectedRegions = [...adcodes]
    },
    setDrawnGeometry(geometry: DrawnGeometry | null) {
      this.drawnGeometry = geometry
    },
    clearSpatialFilters() {
      this.referencePoint = null
      this.radiusKm = null
      this.drawnGeometry = null
      this.selectedRegions = []
      // 地图组件自行响应状态，清除 Marker / Circle / Polygon / 行政区高亮。
    },
  },
})
