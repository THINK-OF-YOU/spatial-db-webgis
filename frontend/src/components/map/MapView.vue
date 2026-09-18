<script setup lang="ts">
import { markRaw, onBeforeUnmount, onMounted, provide, ref, shallowRef, watch } from 'vue'
import { storeToRefs } from 'pinia'
import * as L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Polygon } from 'geojson'
import { useSearchStore } from '../../stores/useSearchStore'
import { MAP_KEY } from './mapContext'
import type { DrawMode } from './types'
import CampusLayer from './CampusLayer.vue'
import RegionLayer from './RegionLayer.vue'
import MapToolbar from './MapToolbar.vue'
import MapLegend from './MapLegend.vue'
import TransportLayer from './TransportLayer.vue'

const store = useSearchStore()
const { referencePoint, radiusKm, drawnGeometry, selectedCollege } = storeToRefs(store)

const el = ref<HTMLDivElement | null>(null)
const map = shallowRef<L.Map | null>(null)
const mode = ref<DrawMode>('browse')
const regionOpen = ref(false)

// Leaflet 实例一律 markRaw，避免被 Vue 响应式代理（契约 §4：不得入 Pinia，保留在地图组件内）。
const referenceGroup = markRaw(L.layerGroup())
const drawnLayer = markRaw(L.layerGroup())
const tempVertexLayer = markRaw(L.layerGroup())

// 临时绘制状态（矩形 / 多边形）
let drawStart: L.LatLng | null = null
let tempRect: L.Rectangle | null = null
let polyPoints: L.LatLng[] = []
let tempPolyline: L.Polyline | null = null
let resizeObserver: ResizeObserver | null = null

function invalidateMapSize() {
  map.value?.invalidateSize({ pan: false, animate: false })
}

provide(MAP_KEY, map)

onMounted(() => {
  if (!el.value) return
  const m = markRaw(L.map(el.value, { center: [35.0, 104.0], zoom: 4, zoomControl: false }))
  // 行政区放独立 pane（低于 overlayPane 400），校区点永远压在上面
  m.createPane('regions').style.zIndex = '380'
  // 交通 POI 高于普通 Campus 点，低于选中高校与参考点高亮。
  m.createPane('transport').style.zIndex = '430'
  // 既有参考点和选中光环使用此 pane；必须在渲染前创建。
  m.createPane('marker').style.zIndex = '450'
  markRaw(
    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
      {
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, HERE, Garmin, FAO, NOAA, USGS',
        maxZoom: 19,
      },
    ),
  ).addTo(m)
  drawnLayer.addTo(m)
  referenceGroup.addTo(m)
  tempVertexLayer.addTo(m)
  map.value = m
  bindInteractions(m)
  // MapView 现在作为主画布被浮动侧栏覆盖；监听容器与窗口变化，避免折叠/恢复后 Leaflet 保留旧尺寸。
  resizeObserver = new ResizeObserver(() => {
    requestAnimationFrame(invalidateMapSize)
  })
  resizeObserver.observe(el.value)
  window.addEventListener('resize', invalidateMapSize)
  renderReference()
  renderDrawn()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('resize', invalidateMapSize)
  map.value?.remove()
  map.value = null
})

function bindInteractions(m: L.Map) {
  m.on('click', (e: L.LeafletMouseEvent) => {
    if (mode.value === 'point') placeReference(e)
    else if (mode.value === 'polygon') addPolyPoint(e)
  })
  m.on('dblclick', () => {
    if (mode.value === 'polygon') finishPoly()
  })
  m.on('mousedown', (e: L.LeafletMouseEvent) => {
    if (mode.value === 'rect') beginRect(e)
  })
  m.on('mousemove', (e: L.LeafletMouseEvent) => {
    if (mode.value === 'rect') updateRect(e)
  })
  m.on('mouseup', (e: L.LeafletMouseEvent) => {
    if (mode.value === 'rect') endRect(e)
  })
}

// 进入/离开绘制模式时，切换地图拖拽与双击缩放，并清理临时图层
watch(mode, (md) => {
  const m = map.value
  if (!m) return
  if (md === 'rect') {
    m.dragging.disable()
    m.doubleClickZoom.disable()
  } else if (md === 'polygon') {
    m.dragging.enable()
    m.doubleClickZoom.disable()
  } else {
    m.dragging.enable()
    m.doubleClickZoom.enable()
  }
  if (md !== 'rect') {
    if (tempRect) {
      tempRect.remove()
      tempRect = null
    }
    drawStart = null
  }
  if (md !== 'polygon') clearPolyTemp()
})

// ── 参考点 + 半径圆 ────────────────────────────────────────────────
function placeReference(e: L.LeafletMouseEvent) {
  const { lat, lng } = e.latlng
  store.setReferencePoint({ lon: lng, lat })
  if (store.radiusKm === null) store.setRadiusKm(300)
  mode.value = 'browse'
}

function renderReference() {
  referenceGroup.clearLayers()
  const m = map.value
  const rp = referencePoint.value
  if (!m || !rp) return
  const latlng = L.latLng(rp.lat, rp.lon)
  markRaw(
    L.circleMarker(latlng, {
      pane: 'marker',
      radius: 6,
      color: '#b91c1c',
      weight: 2,
      fillColor: '#ef4444',
      fillOpacity: 0.95,
      bubblingMouseEvents: false,
    }).bindTooltip('参考点'),
  ).addTo(referenceGroup)
  const r = radiusKm.value
  if (r) {
    markRaw(
      L.circle(latlng, {
        radius: r * 1000,
        color: '#1d4ed8',
        weight: 1,
        fillColor: '#3b82f6',
        fillOpacity: 0.08,
        interactive: false,
      }),
    ).addTo(referenceGroup)
  }
}

watch([referencePoint, radiusKm], renderReference)

// ── 矩形 / 多边形绘制 → GeoJSON Polygon → drawnGeometry ─────────────
function beginRect(e: L.LeafletMouseEvent) {
  const m = map.value
  if (!m) return
  drawStart = e.latlng
  if (tempRect) tempRect.remove()
  tempRect = markRaw(
    L.rectangle(L.latLngBounds(e.latlng, e.latlng), {
      color: '#1d4ed8',
      weight: 2,
      dashArray: '6 4',
      fill: false,
    }),
  ).addTo(m)
}

function updateRect(e: L.LeafletMouseEvent) {
  if (!tempRect || !drawStart) return
  tempRect.setBounds(L.latLngBounds(drawStart, e.latlng))
}

function endRect(e: L.LeafletMouseEvent) {
  if (!tempRect || !drawStart) return
  const bounds = L.latLngBounds(drawStart, e.latlng)
  tempRect.remove()
  tempRect = null
  drawStart = null
  store.setDrawnGeometry(boundsToPolygon(bounds))
  mode.value = 'browse'
}

function boundsToPolygon(b: L.LatLngBounds): Polygon {
  const sw = b.getSouthWest()
  const se = b.getSouthEast()
  const ne = b.getNorthEast()
  const nw = b.getNorthWest()
  return {
    type: 'Polygon',
    coordinates: [
      [
        [sw.lng, sw.lat],
        [se.lng, se.lat],
        [ne.lng, ne.lat],
        [nw.lng, nw.lat],
        [sw.lng, sw.lat],
      ],
    ],
  }
}

function addPolyPoint(e: L.LeafletMouseEvent) {
  polyPoints.push(e.latlng)
  drawPolyTemp()
}

function drawPolyTemp() {
  const m = map.value
  if (!m) return
  if (!tempPolyline) {
    tempPolyline = markRaw(
      L.polyline(polyPoints, { color: '#1d4ed8', weight: 2, dashArray: '6 4' }),
    ).addTo(m)
  } else {
    tempPolyline.setLatLngs(polyPoints)
  }
  tempVertexLayer.clearLayers()
  polyPoints.forEach((p) =>
    markRaw(
      L.circleMarker(p, {
        radius: 3,
        color: '#1d4ed8',
        fillColor: '#1d4ed8',
        fillOpacity: 1,
        interactive: false,
      }),
    ).addTo(tempVertexLayer),
  )
}

function finishPoly() {
  // dblclick 前会先触发两次 click，把重复顶点去掉
  const pts = dedupeConsecutive(polyPoints)
  if (pts.length >= 3) {
    const ring: [number, number][] = pts.map((p) => [p.lng, p.lat])
    ring.push([ring[0][0], ring[0][1]])
    store.setDrawnGeometry({ type: 'Polygon', coordinates: [ring] })
  }
  clearPolyTemp()
  mode.value = 'browse'
}

function dedupeConsecutive(pts: L.LatLng[]): L.LatLng[] {
  const out: L.LatLng[] = []
  for (const p of pts) {
    const last = out[out.length - 1]
    if (last && last.lat === p.lat && last.lng === p.lng) continue
    out.push(p)
  }
  return out
}

function clearPolyTemp() {
  if (tempPolyline) {
    tempPolyline.remove()
    tempPolyline = null
  }
  tempVertexLayer.clearLayers()
  polyPoints = []
}

function renderDrawn() {
  drawnLayer.clearLayers()
  const m = map.value
  const g = drawnGeometry.value
  if (!m || !g) return
  const latlngs: [number, number][][] = g.coordinates.map((ring) =>
    ring.map((pos) => [pos[1], pos[0]] as [number, number]),
  )
  markRaw(
    L.polygon(latlngs, {
      color: '#7c3aed',
      weight: 2,
      fillColor: '#a78bfa',
      fillOpacity: 0.15,
      interactive: false,
    }),
  ).addTo(drawnLayer)
}

watch(drawnGeometry, renderDrawn)

// 两个大型地图浮层不长期叠放：列表或 Campus 选择高校时，
// 行政区面板自动收起；反向打开行政区时先关闭高校详情。
watch(selectedCollege, (college) => {
  if (college) regionOpen.value = false
})

function setRegionOpen(open: boolean) {
  if (open) {
    mode.value = 'browse'
    if (selectedCollege.value) store.setSelectedCollege(null)
  }
  regionOpen.value = open
}

function onClearSpatial() {
  mode.value = 'browse'
  store.clearSpatialFilters()
}
</script>

<template>
  <div class="map-root">
    <div ref="el" class="map-canvas" :class="`mode-${mode}`"></div>
    <MapToolbar
      v-model:mode="mode"
      :region-open="regionOpen"
      @update:region-open="setRegionOpen"
      @clear="onClearSpatial"
    />
    <MapLegend />
    <CampusLayer />
    <TransportLayer />
    <RegionLayer :open="regionOpen" @open="setRegionOpen(true)" @close="setRegionOpen(false)" />
  </div>
</template>

<style scoped>
.map-root {
  position: relative;
  width: 100%;
  height: 100%;
}
.map-canvas {
  width: 100%;
  height: 100%;
}
.mode-rect,
.mode-polygon,
.mode-point {
  cursor: crosshair;
}
/* 选点/绘制时让输入到达地图，避免行政区与校区点击拦截工具操作。 */
.mode-point :deep(.leaflet-interactive),
.mode-rect :deep(.leaflet-interactive),
.mode-polygon :deep(.leaflet-interactive) {
  pointer-events: none;
}
</style>
