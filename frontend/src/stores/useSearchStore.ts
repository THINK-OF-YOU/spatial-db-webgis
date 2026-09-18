import { defineStore } from 'pinia'
import type {
  DrawnGeometry,
  MapBounds,
  CompareCollegeSnapshot,
  ReferencePoint,
  SearchState,
  SelectedCollegeType,
  ViewportCampusFeature,
} from '../types'

export const useSearchStore = defineStore('search', {
  state: (): SearchState => ({
    filters: {},
    // 全页面唯一业务结果源，由业务页面统一查询后更新；地图仅消费。
    results: [],
    selectedCollege: null,
    compareCollegeIds: [],
    compareColleges: [],
    referencePoint: null,
    radiusKm: null,
    selectedRegions: [],
    drawnGeometry: null,
    mapBounds: null,
    viewportCampuses: [],
    campusStatus: false,
    loading: false,
    hasSearched: false,
    candidateProfile: {
      source_province: '',
      year: null,
      category: '',
      input_mode: 'rank',
      rank: null,
      score: null,
      resolved_rank: null,
      resolution_status: 'idle',
      batch: '',
    },
    candidateProfileEnabled: false,
    // 真实数据抽样：湖南 2024 物理类、位次 20000 时命中约 129 所。
    rankWindow: { ahead: 3000, behind: 8000 },
    warnings: [],
  }),
  getters: {
    candidateEffectiveRank(state): number | null {
      if (state.candidateProfile.input_mode === 'rank') {
        return state.candidateProfile.rank
      }
      return state.candidateProfile.resolution_status === 'resolved'
        ? state.candidateProfile.resolved_rank
        : null
    },
  },
  actions: {
    setSelectedCollege(college: SelectedCollegeType | null) {
      if (this.selectedCollege?.school_id === college?.school_id) return
      this.selectedCollege = college === null ? null : { school_id: college.school_id }
    },
    addCompareCollege(college: CompareCollegeSnapshot): 'added' | 'duplicate' | 'limit' {
      if (this.compareCollegeIds.includes(college.school_id)) return 'duplicate'
      if (this.compareColleges.length >= 4) return 'limit'
      this.compareColleges.push({
        ...college,
        reference_admission: college.reference_admission
          ? { ...college.reference_admission }
          : undefined,
      })
      this.compareCollegeIds.push(college.school_id)
      return 'added'
    },
    removeCompareCollege(schoolId: number) {
      this.compareColleges = this.compareColleges.filter(
        (college) => college.school_id !== schoolId,
      )
      this.compareCollegeIds = this.compareCollegeIds.filter((id) => id !== schoolId)
    },
    toggleCompareCollege(
      college: CompareCollegeSnapshot,
    ): 'added' | 'removed' | 'duplicate' | 'limit' {
      if (this.compareCollegeIds.includes(college.school_id)) {
        this.removeCompareCollege(college.school_id)
        return 'removed'
      }
      return this.addCompareCollege(college)
    },
    clearCompareColleges() {
      this.compareColleges = []
      this.compareCollegeIds = []
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
    setMapBounds(bounds: MapBounds | null) {
      this.mapBounds = bounds === null ? null : { ...bounds }
    },
    setViewportCampuses(campuses: ViewportCampusFeature[]) {
      this.viewportCampuses = [...campuses]
    },
    setHasSearched(hasSearched: boolean) {
      this.hasSearched = hasSearched
    },
    setCandidateSourceProvince(sourceProvince: string) {
      this.candidateProfile.source_province = sourceProvince
      this.candidateProfile.year = null
      this.candidateProfile.category = ''
      this.candidateProfile.batch = ''
      this.invalidateCandidateScoreResolution()
    },
    setCandidateYear(year: number | null) {
      this.candidateProfile.year = year
      this.candidateProfile.category = ''
      this.candidateProfile.batch = ''
      this.invalidateCandidateScoreResolution()
    },
    setCandidateCategory(category: string) {
      this.candidateProfile.category = category
      this.candidateProfile.batch = ''
      this.invalidateCandidateScoreResolution()
    },
    setCandidateBatch(batch: string) {
      this.candidateProfile.batch = batch
    },
    setCandidateInputMode(inputMode: 'rank' | 'score') {
      this.candidateProfile.input_mode = inputMode
    },
    setCandidateScore(score: number | null) {
      this.candidateProfile.score = score
      this.invalidateCandidateScoreResolution()
    },
    setCandidateScoreResolution(
      status: SearchState['candidateProfile']['resolution_status'],
      resolvedRank: number | null = null,
    ) {
      this.candidateProfile.resolution_status = status
      this.candidateProfile.resolved_rank = status === 'resolved' ? resolvedRank : null
    },
    invalidateCandidateScoreResolution() {
      this.candidateProfile.resolved_rank = null
      this.candidateProfile.resolution_status = 'idle'
    },
    resetCandidateProfile() {
      this.candidateProfile = {
        source_province: '',
        year: null,
        category: '',
        input_mode: 'rank',
        rank: null,
        score: null,
        resolved_rank: null,
        resolution_status: 'idle',
        batch: '',
      }
      this.candidateProfileEnabled = false
      this.rankWindow = { ahead: 3000, behind: 8000 }
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
