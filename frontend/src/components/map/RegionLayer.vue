<script setup lang="ts">
import { computed, inject, markRaw, ref, shallowRef, watch } from 'vue'
import { storeToRefs } from 'pinia'
import * as L from 'leaflet'
import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson'
import { MAP_KEY } from './mapContext'
import { useSearchStore } from '../../stores/useSearchStore'
import { loadRegions, type RegionQuery } from './mapData'
import type { RegionFeature, RegionLevel, RegionProps } from './types'

interface RegionTrailItem {
  adcode: string | null
  name: string
  level: RegionLevel | null
}

type RegionCollection = FeatureCollection<Polygon | MultiPolygon, RegionProps>

const ROOT: RegionTrailItem = { adcode: null, name: '全国', level: null }
const LEVEL_TEXT: Record<RegionLevel, string> = {
  province: '省级行政区',
  city: '市级行政区',
  district: '区县级行政区',
}

const mapRef = inject(MAP_KEY)!
const store = useSearchStore()
const { selectedRegions } = storeToRefs(store)

const breadcrumb = ref<RegionTrailItem[]>([ROOT])
const focusedRegion = shallowRef<RegionFeature | null>(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const currentLevel = ref<RegionLevel>('province')
const currentFeatureCount = ref(0)

let layerGroup: L.FeatureGroup | null = null
let requestSerial = 0
let retryOperation: (() => Promise<void>) | null = null
const layerByAdcode = new Map<string, L.Polygon>()
const regionByAdcode = new Map<string, RegionProps>()
const cache = new Map<string, RegionCollection>()

const selectedRegionLabels = computed(() =>
  selectedRegions.value.map((adcode) => ({
    adcode,
    name: regionByAdcode.get(adcode)?.name ?? adcode,
  })),
)

function regionStyle(adcode: string): L.PathOptions {
  const selected = store.selectedRegions.includes(adcode)
  const focused = focusedRegion.value?.properties.adcode === adcode
  if (selected) {
    return {
      color: '#1d4ed8',
      weight: 2.5,
      fillColor: '#3b82f6',
      fillOpacity: 0.24,
      bubblingMouseEvents: false,
    }
  }
  if (focused) {
    return {
      color: '#15803d',
      weight: 2.5,
      fillColor: '#4ade80',
      fillOpacity: 0.18,
      bubblingMouseEvents: false,
    }
  }
  return {
    color: '#7c8a94',
    weight: 1,
    fillColor: '#cbd5e1',
    fillOpacity: 0.05,
    bubblingMouseEvents: false,
  }
}

// GeoJSON [lon, lat] → Leaflet [lat, lng]；Polygon/MultiPolygon 都归一成多环结构。
function toLatLngs(geom: Polygon | MultiPolygon): L.LatLngExpression[][][] {
  const polygons = geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates
  return polygons.map((rings) =>
    rings.map((ring) => ring.map(([lng, lat]) => [lat, lng] as [number, number])),
  )
}

function updateStyles() {
  for (const [adcode, layer] of layerByAdcode) {
    layer.setStyle(regionStyle(adcode))
  }
}

function focusRegion(feature: RegionFeature) {
  focusedRegion.value = feature
  notice.value = ''
  updateStyles()
}

function fitCurrentFeatures(map: L.Map, level: RegionLevel) {
  if (!layerGroup) return
  const bounds = layerGroup.getBounds()
  if (!bounds.isValid()) return
  const maxZoom = level === 'province' ? 4 : level === 'city' ? 7 : 10
  map.fitBounds(bounds, { padding: [24, 24], maxZoom })
}

function renderFeatures(map: L.Map, collection: RegionCollection) {
  layerGroup?.remove()
  layerGroup = markRaw(L.featureGroup()).addTo(map)
  layerByAdcode.clear()
  focusedRegion.value = null

  for (const feature of collection.features) {
    const props = feature.properties
    regionByAdcode.set(props.adcode, props)
    const polygon = markRaw(
      L.polygon(toLatLngs(feature.geometry), {
        ...regionStyle(props.adcode),
        pane: 'regions',
      }),
    )
    polygon.bindTooltip(`${props.name} · 点击查看操作`, { sticky: true })
    polygon.on('mouseover', () => {
      if (focusedRegion.value?.properties.adcode === props.adcode) return
      if (store.selectedRegions.includes(props.adcode)) return
      polygon.setStyle({ weight: 2, fillOpacity: 0.12 })
    })
    polygon.on('mouseout', updateStyles)
    polygon.on('click', () => focusRegion(feature))
    polygon.addTo(layerGroup)
    layerByAdcode.set(props.adcode, polygon)
  }

  currentFeatureCount.value = collection.features.length
  currentLevel.value = collection.features[0]?.properties.level ?? currentLevel.value
  fitCurrentFeatures(map, currentLevel.value)
}

function queryKey(query: RegionQuery) {
  return query.parentAdcode
    ? `parent:${query.parentAdcode}:level:${query.level ?? 'any'}`
    : `level:${query.level ?? 'province'}`
}

async function getRegions(query: RegionQuery) {
  const key = queryKey(query)
  const cached = cache.get(key)
  if (cached) return cached
  const collection = await loadRegions(query)
  cache.set(key, collection)
  return collection
}

async function showRegionLevel(
  query: RegionQuery,
  nextBreadcrumb: RegionTrailItem[],
  emptyMessage: string,
  fallbackQuery?: RegionQuery,
) {
  const map = mapRef.value
  if (!map) return
  const serial = ++requestSerial
  loading.value = true
  error.value = ''
  notice.value = ''
  retryOperation = () => showRegionLevel(query, nextBreadcrumb, emptyMessage, fallbackQuery)
  try {
    let collection = await getRegions(query)
    if (!collection.features.length && fallbackQuery) {
      collection = await getRegions(fallbackQuery)
    }
    if (serial !== requestSerial) return
    if (!collection.features.length) {
      notice.value = emptyMessage
      return
    }
    breadcrumb.value = nextBreadcrumb
    renderFeatures(map, collection)
    retryOperation = null
  } catch (cause) {
    if (serial !== requestSerial) return
    error.value = cause instanceof Error ? cause.message : '行政区数据加载失败。'
  } finally {
    if (serial === requestSerial) loading.value = false
  }
}

function loadRoot() {
  return showRegionLevel({ level: 'province' }, [ROOT], '暂无省级行政区数据。')
}

async function enterFocusedRegion() {
  const feature = focusedRegion.value
  if (!feature || feature.properties.level === 'district') return
  const props = feature.properties
  const nextLevel: RegionLevel = props.level === 'province' ? 'city' : 'district'
  await showRegionLevel(
    { level: nextLevel, parentAdcode: props.adcode },
    [...breadcrumb.value, { adcode: props.adcode, name: props.name, level: props.level }],
    `${props.name}暂无下一级行政区数据，已停留在当前层级。`,
    props.level === 'province' ? { parentAdcode: props.adcode } : undefined,
  )
}

function navigateTo(index: number) {
  if (index < 0 || index >= breadcrumb.value.length - 1) return
  const target = breadcrumb.value[index]
  const nextBreadcrumb = breadcrumb.value.slice(0, index + 1)
  const nextLevel: RegionLevel | null =
    target.level === 'province' ? 'city' : target.level === 'city' ? 'district' : null
  return showRegionLevel(
    target.adcode && nextLevel
      ? { level: nextLevel, parentAdcode: target.adcode }
      : { level: 'province' },
    nextBreadcrumb,
    `${target.name}暂无下一级行政区数据。`,
    target.level === 'province' && target.adcode ? { parentAdcode: target.adcode } : undefined,
  )
}

function isAncestor(ancestorAdcode: string, descendantAdcode: string) {
  const visited = new Set<string>()
  let parent = regionByAdcode.get(descendantAdcode)?.parent_adcode ?? null
  while (parent && !visited.has(parent)) {
    if (parent === ancestorAdcode) return true
    visited.add(parent)
    parent = regionByAdcode.get(parent)?.parent_adcode ?? null
  }
  return false
}

function toggleFocusedSelection() {
  const props = focusedRegion.value?.properties
  if (!props) return
  const current = store.selectedRegions
  if (current.includes(props.adcode)) {
    store.setSelectedRegions(current.filter((adcode) => adcode !== props.adcode))
    notice.value = `${props.name}已移出查询条件。`
    return
  }

  const related = current.find(
    (adcode) => isAncestor(adcode, props.adcode) || isAncestor(props.adcode, adcode),
  )
  if (related) {
    const relatedName = regionByAdcode.get(related)?.name ?? related
    notice.value = `已选择 ${relatedName}，无需同时添加父子区域。`
    return
  }

  store.setSelectedRegions([...current, props.adcode])
  notice.value = `${props.name}已加入查询条件；点击“应用综合筛选”后生效。`
}

function removeSelectedRegion(adcode: string) {
  store.setSelectedRegions(store.selectedRegions.filter((item) => item !== adcode))
  notice.value = '行政区查询条件已移除。'
}

function retryLoad() {
  void retryOperation?.()
}

watch(
  mapRef,
  (map) => {
    if (map) void loadRoot()
  },
  { immediate: true },
)

// selectedRegions 只表示查询条件；变化时仅同步样式，不参与下钻路径。
watch(selectedRegions, updateStyles)
</script>

<template>
  <section class="region-browser" aria-label="行政区浏览与筛选">
    <div class="region-browser-top">
      <nav class="region-breadcrumb" aria-label="行政区层级">
        <template v-for="(item, index) in breadcrumb" :key="item.adcode ?? 'root'">
          <span v-if="index" aria-hidden="true">›</span>
          <button
            type="button"
            :disabled="loading || index === breadcrumb.length - 1"
            @click="navigateTo(index)"
          >
            {{ item.name }}
          </button>
        </template>
      </nav>
      <button
        v-if="breadcrumb.length > 1"
        type="button"
        class="region-back"
        :disabled="loading"
        @click="navigateTo(breadcrumb.length - 2)"
      >
        返回上一级
      </button>
    </div>

    <p v-if="loading" class="region-state">正在加载行政区…</p>
    <div v-else-if="error" class="region-state region-error" role="alert">
      <span>{{ error }}</span>
      <button type="button" @click="retryLoad">重试</button>
    </div>
    <p v-else-if="!currentFeatureCount" class="region-state">当前层级暂无行政区数据。</p>
    <p v-else class="region-level">{{ LEVEL_TEXT[currentLevel] }} · {{ currentFeatureCount }} 个</p>

    <div v-if="focusedRegion" class="region-focus">
      <div>
        <strong>{{ focusedRegion.properties.name }}</strong>
        <span>{{ LEVEL_TEXT[focusedRegion.properties.level] }}</span>
      </div>
      <div class="region-actions">
        <button
          v-if="focusedRegion.properties.level !== 'district'"
          type="button"
          :disabled="loading"
          @click="enterFocusedRegion"
        >
          查看下一级
        </button>
        <button type="button" class="region-select" :disabled="loading" @click="toggleFocusedSelection">
          {{ selectedRegions.includes(focusedRegion.properties.adcode) ? '移出筛选' : '加入筛选' }}
        </button>
      </div>
    </div>

    <p v-if="notice" class="region-notice" role="status">{{ notice }}</p>

    <div v-if="selectedRegionLabels.length" class="selected-regions">
      <span>查询区域</span>
      <button
        v-for="region in selectedRegionLabels"
        :key="region.adcode"
        type="button"
        :title="`移除 ${region.name}`"
        @click="removeSelectedRegion(region.adcode)"
      >
        {{ region.name }} ×
      </button>
    </div>
  </section>
</template>

<style scoped>
.region-browser {
  position: absolute;
  top: 12px;
  left: 54px;
  z-index: 1000;
  width: min(330px, calc(100% - 430px));
  min-width: 250px;
  padding: 9px 10px;
  border: 1px solid #dce2e8;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  color: #263340;
  box-shadow: 0 1px 5px rgba(15, 23, 42, 0.14);
  font-size: 11px;
}
.region-browser-top,
.region-breadcrumb,
.region-actions,
.selected-regions {
  display: flex;
  align-items: center;
  gap: 5px;
}
.region-browser-top {
  justify-content: space-between;
}
.region-breadcrumb {
  min-width: 0;
  overflow: hidden;
}
.region-breadcrumb button,
.region-back,
.region-actions button,
.selected-regions button,
.region-error button {
  border: 0;
  border-radius: 5px;
  background: #eef3f0;
  color: #34564a;
  padding: 4px 6px;
  font: inherit;
  cursor: pointer;
}
.region-breadcrumb button {
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: transparent;
  padding-inline: 2px;
}
.region-breadcrumb button:disabled {
  color: #172c24;
  font-weight: 700;
  cursor: default;
}
.region-back {
  flex: none;
}
.region-level,
.region-state,
.region-notice {
  margin: 7px 0 0;
  color: #738078;
  line-height: 1.5;
}
.region-focus {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e5ebe7;
}
.region-focus strong,
.region-focus span {
  display: block;
}
.region-focus span {
  margin-top: 2px;
  color: #87928c;
  font-size: 10px;
}
.region-actions {
  flex: none;
}
.region-actions .region-select {
  background: #235e50;
  color: #fff;
}
.region-actions button:disabled,
.region-back:disabled,
.region-error button:disabled {
  opacity: 0.5;
  cursor: default;
}
.region-notice {
  padding: 5px 6px;
  border-radius: 5px;
  background: #f5f8f6;
}
.region-error {
  color: #b91c1c;
}
.region-error button {
  margin-left: 5px;
  color: #b91c1c;
}
.selected-regions {
  flex-wrap: wrap;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e5ebe7;
}
.selected-regions > span {
  color: #6b7770;
}
.selected-regions button {
  background: #eaf1ff;
  color: #1d4ed8;
}
</style>
