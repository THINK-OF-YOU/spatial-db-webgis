<script setup lang="ts">
import { computed, inject, markRaw, onBeforeUnmount, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import * as L from 'leaflet'
import { MAP_KEY } from './mapContext'
import { useSearchStore } from '../../stores/useSearchStore'
import { loadCampuses } from './mapData'
import type { CampusStatus } from './types'
import type { MapBounds, ViewportCampusFeature } from '../../types/search'

const mapRef = inject(MAP_KEY)!
const store = useSearchStore()
const { selectedCollege, results, hasSearched } = storeToRefs(store)

const error = ref('')
const loading = ref(false)

// API 状态不变；这里只调整面向用户的低干扰文案。
const STATUS_TEXT: Record<CampusStatus, string> = {
  CONFIRMED: '已核验',
  CANDIDATE: '参考校区点',
}

interface MarkerRec {
  marker: L.CircleMarker
  schoolId: number
  status: CampusStatus
}

let layerGroup: L.LayerGroup | null = null
let selectHighlight: L.LayerGroup | null = null
const records: MarkerRec[] = []
const bySchool = new Map<number, L.CircleMarker[]>()
let requestController: AbortController | null = null
let requestVersion = 0
let lastSuccessfulBbox = ''
let activeBbox = ''

function styleFor(status: CampusStatus): L.CircleMarkerOptions {
  return status === 'CONFIRMED'
    ? { radius: 7, color: '#ffffff', weight: 2, fillColor: '#2e7d32', fillOpacity: 0.95, bubblingMouseEvents: false }
    : { radius: 7, color: '#f59e0b', weight: 2, fillColor: '#f59e0b', fillOpacity: 0.25, bubblingMouseEvents: false }
}

function renderFeatures(m: L.Map, features: ViewportCampusFeature[]) {
  if (!layerGroup) layerGroup = markRaw(L.layerGroup()).addTo(m)
  else layerGroup.clearLayers()
  if (!selectHighlight) selectHighlight = markRaw(L.layerGroup()).addTo(m)
  else selectHighlight.clearLayers()
  records.length = 0
  bySchool.clear()
  for (const f of features) {
    const p = f.properties
    const [lng, lat] = f.geometry.coordinates
    const marker = markRaw(L.circleMarker([lat, lng], styleFor(p.verify_status)))
    marker.bindTooltip(`${p.school_name} · ${p.campus_name}（${STATUS_TEXT[p.verify_status]}）`)
    marker.on('click', () => store.setSelectedCollege({ school_id: p.school_id }))
    marker.addTo(layerGroup)
    records.push({ marker, schoolId: p.school_id, status: p.verify_status })
    const arr = bySchool.get(p.school_id) ?? []
    arr.push(marker)
    bySchool.set(p.school_id, arr)
  }
  updateSelection()
  updateResults()
}

function currentBounds(m: L.Map): MapBounds {
  const bounds = m.getBounds()
  return {
    west: Number(bounds.getWest().toFixed(6)),
    south: Number(bounds.getSouth().toFixed(6)),
    east: Number(bounds.getEast().toFixed(6)),
    north: Number(bounds.getNorth().toFixed(6)),
  }
}

function bboxKey(bounds: MapBounds) {
  return `${bounds.west},${bounds.south},${bounds.east},${bounds.north}`
}

async function refresh(m: L.Map, force = false) {
  const bounds = currentBounds(m)
  const key = bboxKey(bounds)
  store.setMapBounds(bounds)
  if (!force && (key === lastSuccessfulBbox || key === activeBbox)) return

  requestController?.abort()
  const controller = new AbortController()
  requestController = controller
  const version = ++requestVersion
  activeBbox = key
  loading.value = true

  try {
    const fc = await loadCampuses(bounds, controller.signal)
    if (controller.signal.aborted || version !== requestVersion) return
    // 地图和高校列表只在同一次最新请求成功后，一起切换到同一批视野数据。
    renderFeatures(m, fc.features)
    store.setViewportCampuses(fc.features)
    lastSuccessfulBbox = key
    error.value = ''
  } catch (cause) {
    if (controller.signal.aborted || version !== requestVersion) return
    error.value = '当前视野校区加载失败，已保留上一次结果。'
    console.warn(cause)
  } finally {
    if (version === requestVersion) {
      activeBbox = ''
      loading.value = false
    }
  }
}

function retry() {
  const m = mapRef.value
  if (m) void refresh(m, true)
}

watch(
  mapRef,
  (m, _previous, onCleanup) => {
    if (!m) return
    const onMoveEnd = () => void refresh(m)
    m.on('moveend', onMoveEnd)
    void refresh(m)
    onCleanup(() => m.off('moveend', onMoveEnd))
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  requestController?.abort()
})

// 列表/地图选中 → 地图定位并高亮；无 Campus 则不动、不报错（契约 §8.2）
function updateSelection() {
  const c = selectedCollege.value
  const m = mapRef.value
  if (!m || !selectHighlight) return
  selectHighlight.clearLayers()
  if (!c) return
  const markers = bySchool.get(c.school_id)
  if (!markers || markers.length === 0) return
  const bounds = L.latLngBounds(markers.map((mk) => mk.getLatLng()))
  m.fitBounds(bounds.pad(0.4), { maxZoom: 12 })
  markers.forEach((mk) =>
    markRaw(
      L.circleMarker(mk.getLatLng(), {
        pane: 'marker',
        radius: 12,
        color: '#1d4ed8',
        weight: 2,
        fill: false,
        interactive: false,
      }),
    ).addTo(selectHighlight!),
  )
}
watch(selectedCollege, updateSelection)

// 表达综合查询结果的空间部分：即使结果为 0，也要把全部非结果校区弱化。
const resultIds = computed(() => new Set<number>(results.value.map((r) => r.school_id)))
function updateResults() {
  const ids = resultIds.value
  const active = hasSearched.value
  for (const rec of records) {
    const dim = active && !ids.has(rec.schoolId)
    const base = styleFor(rec.status)
    rec.marker.setStyle(
      dim
        ? {
            ...base,
            color: '#cbd5e1',
            opacity: 0.25,
            fillOpacity: 0.06,
            weight: 1,
          }
        : { ...base, opacity: 1, fillOpacity: base.fillOpacity, weight: 2 },
    )
  }
}
watch([resultIds, hasSearched], updateResults)
</script>

<template>
  <div v-if="loading" class="layer-status">正在更新当前视野校区…</div>
  <div v-else-if="error" class="layer-status layer-error">
    <span>{{ error }}</span>
    <button type="button" @click="retry">重试</button>
  </div>
</template>

<style scoped>
.layer-status {
  position: absolute;
  left: 12px;
  top: 12px;
  z-index: 1000;
  background: rgba(255, 255, 255, 0.92);
  color: #52645a;
  padding: 6px 10px;
  border: 1px solid #dce5df;
  border-radius: 6px;
  font-size: 12px;
}
.layer-error {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
}
.layer-error button {
  border: 0;
  background: transparent;
  color: inherit;
  text-decoration: underline;
}
</style>
