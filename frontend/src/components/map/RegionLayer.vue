<script setup lang="ts">
import { inject, markRaw, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import * as L from 'leaflet'
import type { MultiPolygon, Polygon } from 'geojson'
import { MAP_KEY } from './mapContext'
import { useSearchStore } from '../../stores/useSearchStore'
import { loadRegions } from './mapData'

const mapRef = inject(MAP_KEY)!
const store = useSearchStore()
const { selectedRegions } = storeToRefs(store)

const error = ref('')

let layerGroup: L.LayerGroup | null = null
const layerByAdcode = new Map<string, L.Polygon>()

function regionStyle(active: boolean): L.PathOptions {
  return active
    ? { color: '#1d4ed8', weight: 2, fillColor: '#3b82f6', fillOpacity: 0.25, bubblingMouseEvents: false }
    : { color: '#94a3b8', weight: 1, fillColor: '#cbd5e1', fillOpacity: 0.06, bubblingMouseEvents: false }
}

// GeoJSON [lon, lat] → Leaflet [lat, lng]；Polygon/MultiPolygon 都归一成多环结构
function toLatLngs(geom: Polygon | MultiPolygon): L.LatLngExpression[][][] {
  const polys = geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates
  return polys.map((rings) =>
    rings.map((ring) => ring.map(([lng, lat]) => [lat, lng] as [number, number])),
  )
}

async function render(m: L.Map) {
  if (layerGroup) layerGroup.remove()
  layerGroup = markRaw(L.layerGroup()).addTo(m)
  layerByAdcode.clear()
  try {
    const fc = await loadRegions()
    const active = new Set(store.selectedRegions)
    for (const f of fc.features) {
      const { adcode, name } = f.properties
      const poly = markRaw(
        L.polygon(toLatLngs(f.geometry), { ...regionStyle(active.has(adcode)), pane: 'regions' }),
      )
      poly.bindTooltip(name)
      poly.on('click', () => toggleRegion(adcode))
      poly.addTo(layerGroup!)
      layerByAdcode.set(adcode, poly)
    }
  } catch (e) {
    error.value = '行政区图层加载失败'
    console.warn(e)
  }
}

watch(mapRef, (m) => {
  if (m) render(m)
}, { immediate: true })

function toggleRegion(adcode: string) {
  const cur = store.selectedRegions
  const next = cur.includes(adcode) ? cur.filter((a) => a !== adcode) : [...cur, adcode]
  store.setSelectedRegions(next)
}

// selectedRegions 变化（含 reset 清空）时同步高亮
watch(selectedRegions, (list) => {
  const set = new Set(list)
  for (const [adcode, layer] of layerByAdcode) {
    layer.setStyle(regionStyle(set.has(adcode)))
  }
})
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
