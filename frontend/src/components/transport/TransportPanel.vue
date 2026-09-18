<script setup lang="ts">
import { computed, inject } from 'vue'
import { TRANSPORT_KEY } from './transportContext'
import { MODE_LABELS, MODE_ORDER, RADIUS_OPTIONS } from './transportTypes'
import type { TransportMode } from './transportTypes'

const transport = inject(TRANSPORT_KEY)
if (!transport) throw new Error('TransportPanel requires TRANSPORT_KEY')

const {
  items,
  total,
  warnings,
  loading,
  error,
  radiusKm,
  modes,
  setRadius,
  toggleMode,
  selectAllModes,
  retry,
} = transport

const NO_CAMPUS_WARNING = '该校暂无可用校区数据，无法进行周边查询'
const noCampus = computed(() => warnings.value.includes(NO_CAMPUS_WARNING))
const allModesSelected = computed(() => modes.value.length === MODE_ORDER.length)

function isSelected(mode: TransportMode) {
  return modes.value.includes(mode)
}

function modeClass(mode: TransportMode) {
  return `mode-${mode.replace('_', '-')}`
}
</script>

<template>
  <section class="transport-section" aria-labelledby="transport-heading">
    <div class="transport-heading-row">
      <div>
        <span class="transport-kicker">POSTGIS · REAL POI</span>
        <h3 id="transport-heading">周边交通设施</h3>
      </div>
      <span v-if="!loading && !error" class="transport-count">
        已加载 {{ total }} 个点位
      </span>
    </div>
    <p class="transport-intro">距离按交通设施到最近校区的直线测地距离计算。</p>

    <div class="transport-controls">
      <fieldset>
        <legend>查询半径</legend>
        <div class="transport-segments">
          <button
            v-for="radius in RADIUS_OPTIONS"
            :key="radius"
            type="button"
            :class="{ active: radiusKm === radius }"
            :aria-pressed="radiusKm === radius"
            @click="setRadius(radius)"
          >
            {{ radius }} km
          </button>
        </div>
      </fieldset>

      <fieldset>
        <legend>交通类型</legend>
        <div class="transport-mode-controls">
          <button
            type="button"
            class="mode-all"
            :class="{ active: allModesSelected }"
            :aria-pressed="allModesSelected"
            @click="selectAllModes"
          >
            全部
          </button>
          <button
            v-for="mode in MODE_ORDER"
            :key="mode"
            type="button"
            class="mode-filter"
            :class="[{ active: isSelected(mode) }, modeClass(mode)]"
            :aria-pressed="isSelected(mode)"
            :disabled="isSelected(mode) && modes.length === 1"
            @click="toggleMode(mode)"
          >
            <span aria-hidden="true" />{{ MODE_LABELS[mode] }}
          </button>
        </div>
      </fieldset>
    </div>

    <div v-if="loading" class="transport-state" role="status">
      <span class="transport-loader" aria-hidden="true" />
      正在查询真实交通设施…
    </div>
    <div v-else-if="error" class="transport-state error" role="alert">
      <strong>交通数据暂不可用</strong>
      <span>{{ error }}</span>
      <button type="button" @click="retry">重新加载</button>
    </div>
    <div v-else-if="noCampus" class="transport-state unavailable">
      <strong>暂无可用校区数据</strong>
      <span>暂时无法进行周边交通查询。</span>
      <small v-for="warning in warnings" :key="warning">{{ warning }}</small>
    </div>
    <div v-else-if="items.length === 0" class="transport-state empty">
      <strong>当前查询范围内暂无交通设施数据</strong>
      <span>这表示数据库当前未检索到 POI，不代表现实中不存在交通设施。</span>
      <small v-for="warning in warnings" :key="warning">{{ warning }}</small>
    </div>

    <template v-else>
      <ul class="transport-list" aria-label="周边交通设施列表">
        <li v-for="item in items" :key="item.poi_id" class="transport-item">
          <span class="transport-mode-dot" :class="modeClass(item.mode)" aria-hidden="true" />
          <span class="transport-item-main">
            <strong>{{ item.name }}</strong>
            <span v-if="item.name_zh && item.name_zh !== item.name">{{ item.name_zh }}</span>
            <small>{{ MODE_LABELS[item.mode] }} · 最近校区：{{ item.campus_name }}</small>
          </span>
          <em>{{ item.distance_km.toFixed(2) }} km</em>
        </li>
      </ul>
      <div v-if="warnings.length" class="transport-warnings" role="status">
        <p v-for="warning in warnings" :key="warning">{{ warning }}</p>
      </div>
    </template>

    <p class="transport-attribution">交通设施数据 © OpenStreetMap contributors（ODbL）</p>
  </section>
</template>

<style scoped>
.transport-section {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid #e3ebe5;
  color: #27382f;
}
.transport-heading-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.transport-kicker {
  color: #7b8f83;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1.45px;
}
.transport-heading-row h3 {
  margin: 4px 0 0;
  font-size: 16px;
}
.transport-count {
  padding: 4px 8px;
  border: 1px solid #d7e4db;
  border-radius: 999px;
  background: #f5f9f6;
  color: #4d6d5b;
  font-size: 11px;
  white-space: nowrap;
}
.transport-intro {
  margin: 6px 0 14px;
  color: #77877e;
  font-size: 11px;
  line-height: 1.55;
}
.transport-controls {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
}
.transport-controls fieldset {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}
.transport-controls legend {
  margin-bottom: 6px;
  color: #607369;
  font-size: 11px;
  font-weight: 650;
}
.transport-segments,
.transport-mode-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.transport-segments button,
.transport-mode-controls button {
  min-height: 29px;
  padding: 5px 10px;
  border: 1px solid #d8e2db;
  border-radius: 6px;
  background: #fff;
  color: #5e7066;
  font-size: 11px;
}
.transport-segments button.active,
.transport-mode-controls button.active {
  border-color: #6f9b80;
  background: #edf5ef;
  color: #2f6347;
}
.transport-mode-controls button:disabled {
  cursor: default;
}
.mode-filter {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.mode-filter > span,
.transport-mode-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #a7b2ab;
  flex: none;
}
.mode-filter:not(.active) > span {
  background: #cbd3ce !important;
}
.mode-metro > span,
.transport-mode-dot.mode-metro {
  background: #2563eb;
}
.mode-rail > span,
.transport-mode-dot.mode-rail {
  background: #7c3aed;
}
.mode-rail-halt > span,
.transport-mode-dot.mode-rail-halt {
  background: #d97706;
}
.mode-airport > span,
.transport-mode-dot.mode-airport {
  background: #dc2626;
}
.transport-state {
  display: grid;
  justify-items: start;
  gap: 5px;
  padding: 14px;
  border: 1px solid #e0e7e2;
  border-radius: 8px;
  background: #f8faf8;
  color: #66766d;
  font-size: 12px;
  line-height: 1.5;
}
.transport-state strong {
  color: #344c3f;
}
.transport-state.error {
  border-color: #efc9c4;
  background: #fff6f5;
  color: #9c5043;
}
.transport-state.error button {
  margin-top: 3px;
  padding: 5px 9px;
  border: 1px solid #d8a8a1;
  border-radius: 5px;
  background: #fff;
  color: inherit;
}
.transport-state.unavailable,
.transport-state.empty {
  border-color: #eadbb7;
  background: #fffbef;
  color: #7f6a38;
}
.transport-state small {
  color: inherit;
  opacity: 0.86;
}
.transport-loader {
  width: 18px;
  height: 18px;
  border: 2px solid #dce8df;
  border-top-color: #438061;
  border-radius: 50%;
  animation: transport-spin 0.8s linear infinite;
}
@keyframes transport-spin {
  to { transform: rotate(360deg); }
}
.transport-list {
  max-height: 300px;
  overflow: auto;
  margin: 0;
  padding: 0 4px 0 0;
  list-style: none;
  scrollbar-width: thin;
}
.transport-item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  align-items: start;
  gap: 8px;
  padding: 9px 0;
  border-top: 1px solid #edf1ee;
}
.transport-item:first-child {
  border-top: 0;
}
.transport-mode-dot {
  margin-top: 5px;
}
.transport-item-main {
  display: grid;
  min-width: 0;
  gap: 2px;
}
.transport-item-main strong {
  overflow: hidden;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.transport-item-main > span,
.transport-item-main small {
  overflow: hidden;
  color: #7b8981;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.transport-item em {
  color: #3d6a52;
  font-size: 11px;
  font-style: normal;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.transport-warnings {
  margin-top: 9px;
  padding: 8px 10px;
  border: 1px solid #eadbb7;
  border-radius: 6px;
  background: #fffbef;
  color: #7f6a38;
  font-size: 10px;
}
.transport-warnings p {
  margin: 0;
}
.transport-attribution {
  margin: 10px 0 0;
  color: #98a29c;
  font-size: 9px;
}
</style>
