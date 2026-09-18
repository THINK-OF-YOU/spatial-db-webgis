<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { loadTransportSummary } from './transportData'
import type {
  TransportItem,
  TransportSummaryMode,
  TransportSummaryResponse,
} from './transportTypes'

const props = defineProps<{ schoolId: number }>()

const MODE_LABELS: Record<TransportSummaryMode, string> = {
  metro: '最近地铁',
  rail: '最近铁路站',
  airport: '最近机场',
}
const MODE_ORDER: TransportSummaryMode[] = ['metro', 'rail', 'airport']
const NO_CAMPUS_WARNING = '该校暂无可用校区数据，无法进行周边查询'

const response = ref<TransportSummaryResponse | null>(null)
const loading = ref(false)
const error = ref('')
let controller: AbortController | null = null
let requestVersion = 0

const noCampus = computed(() =>
  response.value?.warnings.includes(NO_CAMPUS_WARNING) ?? false,
)
const rows = computed(() =>
  MODE_ORDER.map((mode) => ({ mode, item: response.value?.items[mode] ?? null })),
)

function displayName(item: TransportItem) {
  return item.name_zh?.trim() || item.name
}

async function load() {
  controller?.abort()
  const version = ++requestVersion
  response.value = null
  error.value = ''
  loading.value = true
  const current = new AbortController()
  controller = current

  try {
    const data = await loadTransportSummary(props.schoolId, current.signal)
    if (current.signal.aborted || version !== requestVersion) return
    response.value = data
  } catch (cause) {
    if (current.signal.aborted || version !== requestVersion) return
    error.value =
      cause instanceof Error ? cause.message : '最近交通设施摘要加载失败，请稍后重试。'
  } finally {
    if (version === requestVersion) loading.value = false
  }
}

watch(() => props.schoolId, () => void load(), { immediate: true })
onBeforeUnmount(() => {
  controller?.abort()
  requestVersion += 1
})
</script>

<template>
  <section class="transport-summary" aria-labelledby="transport-summary-heading">
    <div class="transport-summary-heading">
      <div>
        <span>POSTGIS · OSM</span>
        <h3 id="transport-summary-heading">最近交通设施</h3>
      </div>
      <small>测地直线距离</small>
    </div>

    <div v-if="loading" class="transport-summary-state" role="status">
      正在查询最近交通设施…
    </div>
    <div v-else-if="error" class="transport-summary-state error" role="alert">
      <span>{{ error }}</span>
      <button type="button" @click="load">重试</button>
    </div>
    <div v-else-if="noCampus" class="transport-summary-state unavailable">
      <strong>暂无可用校区坐标</strong>
      <span>缺少空间基准，当前无法判断最近交通设施。</span>
    </div>
    <dl v-else-if="response" class="transport-summary-grid">
      <div v-for="row in rows" :key="row.mode" :class="`mode-${row.mode}`">
        <dt>{{ MODE_LABELS[row.mode] }}</dt>
        <dd v-if="row.item">
          <strong>{{ displayName(row.item) }}</strong>
          <span>{{ row.item.distance_km.toFixed(2) }} km</span>
          <small>最近校区：{{ row.item.campus_name }}</small>
        </dd>
        <dd v-else class="missing">
          <strong>暂无记录</strong>
          <small>当前数据与限定查询范围内暂无对应交通设施记录</small>
        </dd>
      </div>
    </dl>

    <p class="transport-summary-note">
      距离为 Campus 与交通设施坐标之间的测地直线距离，不代表步行、驾车或通勤距离。数据 © OpenStreetMap contributors（ODbL）。
    </p>
  </section>
</template>

<style scoped>
.transport-summary {
  margin-top: 20px;
  padding: 15px;
  border: 1px solid #dfe8e1;
  border-radius: 9px;
  background: #f9fbf9;
  color: #31483b;
}
.transport-summary-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.transport-summary-heading span {
  color: #829087;
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1.2px;
}
.transport-summary-heading h3 {
  margin: 3px 0 0;
  font-size: 15px;
}
.transport-summary-heading small {
  color: #7f8e85;
  font-size: 9px;
}
.transport-summary-grid {
  display: grid;
  gap: 7px;
  margin: 0;
}
.transport-summary-grid > div {
  display: grid;
  grid-template-columns: 82px minmax(0, 1fr);
  gap: 10px;
  padding: 8px 9px;
  border: 1px solid #e3eae5;
  border-left: 3px solid #718b7a;
  border-radius: 6px;
  background: #fff;
}
.transport-summary-grid > .mode-metro { border-left-color: #2563eb; }
.transport-summary-grid > .mode-rail { border-left-color: #7c3aed; }
.transport-summary-grid > .mode-airport { border-left-color: #dc2626; }
.transport-summary-grid dt {
  color: #65786d;
  font-size: 10px;
  font-weight: 650;
}
.transport-summary-grid dd {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2px 8px;
  min-width: 0;
  margin: 0;
}
.transport-summary-grid dd strong {
  overflow: hidden;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.transport-summary-grid dd span {
  color: #2f6650;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.transport-summary-grid dd small {
  grid-column: 1 / -1;
  color: #8a9790;
  font-size: 9px;
}
.transport-summary-grid dd.missing {
  display: block;
}
.transport-summary-grid dd.missing strong,
.transport-summary-grid dd.missing small {
  display: block;
  color: #929d97;
  white-space: normal;
}
.transport-summary-state {
  display: grid;
  gap: 6px;
  padding: 12px;
  border-radius: 6px;
  background: #f1f5f2;
  color: #687970;
  font-size: 11px;
}
.transport-summary-state.error {
  background: #fff5f3;
  color: #9b4d42;
}
.transport-summary-state.unavailable {
  background: #fff9e9;
  color: #806a37;
}
.transport-summary-state button {
  justify-self: start;
  padding: 4px 8px;
}
.transport-summary-note {
  margin: 10px 0 0;
  color: #8d9992;
  font-size: 9px;
  line-height: 1.55;
}
</style>
