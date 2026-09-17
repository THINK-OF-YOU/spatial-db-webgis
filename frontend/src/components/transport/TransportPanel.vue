<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { loadTransport } from './transportData'
import { MODE_LABELS, MODE_ORDER } from './transportTypes'
import type { TransportItem, TransportMode } from './transportTypes'

/**
 * 高校周边交通站点展示组件。
 *
 * 正式位置在范传智的详情 Drawer（任务书 §3.4 / 附录 D）。本组件保持自包含、
 * 只依赖 schoolId 一个 prop，方便直接嵌入 Drawer，不改 Drawer 的字段结构。
 *
 * 关键规则（§4.11 / 附录 D）：
 * - 站点名以 OSM 原名 name 为准；name_zh 缺失时不显示中文名、不翻译、不兜底。
 * - 查不到站点时显示后端 warnings 的覆盖不足说明，绝不写成“该高校周边没有交通站点”。
 * - 界面固定标注 ODbL 署名。
 */

const props = defineProps<{ schoolId: number | null }>()

const items = ref<TransportItem[]>([])
const warnings = ref<string[]>([])
const loading = ref(false)
const error = ref('')

// 同一 school_id 不重复请求（契约 §8 联动时避免反复触发）
let lastSchoolId: number | null = null

async function refresh() {
  const id = props.schoolId
  if (id === null || id === lastSchoolId) return
  lastSchoolId = id
  loading.value = true
  error.value = ''
  items.value = []
  warnings.value = []
  try {
    const resp = await loadTransport(id)
    items.value = resp.items
    warnings.value = [...new Set(resp.warnings ?? [])]
  } catch (e) {
    error.value = '交通站点加载失败'
    console.warn(e)
  } finally {
    loading.value = false
  }
}

watch(() => props.schoolId, refresh, { immediate: true })

// 按 mode 分组，分组顺序固定（地铁/火车/机场/铁路停靠站）
const grouped = computed<{ mode: TransportMode; label: string; list: TransportItem[] }[]>(() => {
  return MODE_ORDER.map((mode) => ({
    mode,
    label: MODE_LABELS[mode],
    list: items.value.filter((t) => t.mode === mode),
  })).filter((g) => g.list.length > 0)
})
</script>

<template>
  <div class="transport-panel" v-if="schoolId !== null">
    <h3 class="title">周边交通站点</h3>

    <p v-if="loading" class="hint">加载中…</p>
    <p v-else-if="error" class="hint error">{{ error }}</p>

    <!-- 覆盖不足：宁可说“数据覆盖不足”，也不说“周边没有站点”（§4.11） -->
    <div v-else-if="warnings.length" class="warn" role="status">
      <span v-for="w in warnings" :key="w">{{ w }}</span>
    </div>

    <p v-else-if="items.length === 0" class="hint">该范围内未检索到交通站点</p>

    <template v-else>
      <div v-for="g in grouped" :key="g.mode" class="mode-group">
        <div class="mode-label">{{ g.label }}</div>
        <ul class="poi-list">
          <li v-for="t in g.list" :key="t.poi_id" class="poi-item">
            <span class="name">{{ t.name }}</span>
            <span v-if="t.name_zh" class="name-zh">{{ t.name_zh }}</span>
            <span class="meta">{{ t.campus_name }} · {{ t.distance_km.toFixed(2) }} km</span>
          </li>
        </ul>
      </div>
    </template>

    <p class="attribution">交通设施数据 © OpenStreetMap contributors（ODbL）</p>
  </div>
</template>

<style scoped>
.transport-panel {
  position: absolute;
  right: 12px;
  bottom: 24px;
  z-index: 1000;
  width: 264px;
  max-height: 320px;
  overflow: auto;
  background: white;
  border: 1px solid #dce2e8;
  border-radius: 8px;
  padding: 10px 12px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.14);
  font-size: 12px;
  color: #263340;
}
.title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
}
.hint {
  margin: 6px 0;
  color: #6b7785;
}
.hint.error {
  color: #b91c1c;
}
.warn {
  margin: 6px 0;
  padding: 6px 8px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 6px;
  color: #92400e;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.mode-group {
  margin-top: 8px;
}
.mode-label {
  color: #6b7785;
  font-weight: 600;
  margin-bottom: 4px;
}
.poi-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.poi-item {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px;
  padding: 4px 0;
  border-top: 1px solid #f0f3f6;
}
.poi-item:first-child {
  border-top: none;
}
.name {
  font-weight: 600;
}
.name-zh {
  color: #6b7785;
}
.meta {
  margin-left: auto;
  color: #8a97a5;
  white-space: nowrap;
}
.attribution {
  margin: 8px 0 0;
  padding-top: 6px;
  border-top: 1px solid #f0f3f6;
  color: #9aa5b1;
  font-size: 11px;
}
</style>
