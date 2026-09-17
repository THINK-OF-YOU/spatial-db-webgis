<script setup lang="ts">
import { computed, inject, markRaw, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import * as L from 'leaflet'
import { MAP_KEY } from './mapContext'
import { useSearchStore } from '../../stores/useSearchStore'
import { loadCampuses } from './mapData'
import type { CampusStatus } from './types'

const mapRef = inject(MAP_KEY)!
const store = useSearchStore()
const { selectedCollege, results } = storeToRefs(store)

const error = ref('')

// 冻结文案（协作规范 §5.4）
const STATUS_TEXT: Record<CampusStatus, string> = {
  CONFIRMED: '已核验校区',
  CANDIDATE: '候选校区点，尚未完成实体级人工核验',
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

function styleFor(status: CampusStatus): L.CircleMarkerOptions {
  return status === 'CONFIRMED'
    ? { radius: 7, color: '#ffffff', weight: 2, fillColor: '#2e7d32', fillOpacity: 0.95, bubblingMouseEvents: false }
    : { radius: 7, color: '#f59e0b', weight: 2, fillColor: '#f59e0b', fillOpacity: 0.25, bubblingMouseEvents: false }
}

async function render(m: L.Map) {
  if (layerGroup) layerGroup.remove()
  if (selectHighlight) selectHighlight.remove()
  layerGroup = markRaw(L.layerGroup()).addTo(m)
  selectHighlight = markRaw(L.layerGroup()).addTo(m)
  records.length = 0
  bySchool.clear()
  try {
    const fc = await loadCampuses()
    for (const f of fc.features) {
      const p = f.properties
      const [lng, lat] = f.geometry.coordinates
      const marker = markRaw(L.circleMarker([lat, lng], styleFor(p.verify_status)))
      marker.bindTooltip(`${p.school_name} · ${p.campus_name}（${STATUS_TEXT[p.verify_status]}）`)
      marker.on('click', () => store.setSelectedCollege({ school_id: p.school_id }))
      marker.addTo(layerGroup!)
      records.push({ marker, schoolId: p.school_id, status: p.verify_status })
      const arr = bySchool.get(p.school_id) ?? []
      arr.push(marker)
      bySchool.set(p.school_id, arr)
    }
    updateSelection()
    updateResults()
  } catch (e) {
    error.value = '校区图层加载失败'
    console.warn(e)
  }
}

watch(mapRef, (m) => {
  if (m) render(m)
}, { immediate: true })

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

// 表达业务结果的空间部分：查询结果存在时，非结果学校校区淡化（契约 §5 规则3）
const resultIds = computed(() => new Set<number>(results.value.map((r) => r.school_id)))
function updateResults() {
  const ids = resultIds.value
  const active = ids.size > 0
  for (const rec of records) {
    const dim = active && !ids.has(rec.schoolId)
    const base = styleFor(rec.status)
    rec.marker.setStyle({ ...base, fillOpacity: dim ? (base.fillOpacity ?? 1) * 0.2 : base.fillOpacity })
  }
}
watch(resultIds, updateResults)
</script>

<template>
  <div v-if="error" class="layer-error">{{ error }}</div>
</template>

<style scoped>
.layer-error {
  position: absolute;
  left: 12px;
  top: 12px;
  z-index: 1000;
  background: #fef2f2;
  color: #b91c1c;
  padding: 6px 10px;
  border: 1px solid #fecaca;
  border-radius: 6px;
  font-size: 12px;
}
</style>
