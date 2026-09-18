<script setup lang="ts">
import type { CompareCollegeSnapshot } from '../types'

defineProps<{
  colleges: CompareCollegeSnapshot[]
  notice?: string
}>()

const emit = defineEmits<{
  remove: [schoolId: number]
  clear: []
  start: []
}>()
</script>

<template>
  <aside v-if="colleges.length" class="compare-tray" aria-label="高校横向比较栏">
    <div class="compare-tray-copy">
      <span class="eyebrow">FACT COMPARISON</span>
      <strong>已选 {{ colleges.length }} / 4 所</strong>
      <p>只并排展示当前搜索得到的真实事实。</p>
    </div>
    <div class="compare-tray-items">
      <span v-for="college in colleges" :key="college.school_id" class="compare-chip">
        <span :title="college.name">{{ college.name }}</span>
        <button
          type="button"
          :aria-label="`移除${college.name}`"
          @click="emit('remove', college.school_id)"
        >
          ×
        </button>
      </span>
    </div>
    <div class="compare-tray-actions">
      <button type="button" class="quiet" @click="emit('clear')">清空</button>
      <button
        type="button"
        class="compare-start"
        :disabled="colleges.length < 2"
        :title="colleges.length < 2 ? '至少选择 2 所高校' : '打开高校横向比较'"
        @click="emit('start')"
      >
        开始比较
      </button>
    </div>
    <p v-if="notice" class="compare-tray-notice" role="status">{{ notice }}</p>
    <p v-else-if="colleges.length < 2" class="compare-tray-hint">
      再选择 {{ 2 - colleges.length }} 所高校后即可开始比较。
    </p>
  </aside>
</template>

<style scoped>
.compare-tray {
  display: grid;
  grid-template-columns: minmax(145px, 0.75fr) minmax(0, 2fr) auto;
  align-items: center;
  gap: 12px;
  margin: 0 12px 10px;
  padding: 11px 13px;
  border: 1px solid #b9d7c3;
  border-radius: 9px;
  background: #f1f8f3;
  box-shadow: 0 5px 16px rgb(35 94 80 / 8%);
}
.compare-tray-copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.compare-tray-copy .eyebrow {
  color: #5c8170;
  font-size: 8px;
}
.compare-tray-copy strong {
  color: #285e4b;
  font-size: 12px;
}
.compare-tray-copy p,
.compare-tray-hint,
.compare-tray-notice {
  margin: 0;
  color: #6d8175;
  font-size: 9px;
  line-height: 1.45;
}
.compare-tray-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}
.compare-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 190px;
  padding: 5px 7px 5px 9px;
  border: 1px solid #c9dfd0;
  border-radius: 999px;
  background: #fff;
  color: #3e6252;
  font-size: 10px;
}
.compare-chip > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.compare-chip button {
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #7a9586;
  line-height: 1;
}
.compare-chip button:hover {
  background: #eaf4ed;
  color: #285e4b;
}
.compare-tray-actions {
  display: flex;
  align-items: center;
  gap: 7px;
  white-space: nowrap;
}
.compare-tray-actions .quiet {
  padding: 7px;
}
.compare-start {
  min-height: 30px;
  padding: 7px 11px;
  border: 1px solid #235e50;
  border-radius: 6px;
  background: #235e50;
  color: #fff;
  font-size: 10px;
}
.compare-start:hover:not(:disabled) {
  background: #174638;
}
.compare-tray-notice {
  grid-column: 2 / -1;
  color: #876b32;
}

@media (max-width: 1380px) {
  .compare-tray {
    grid-template-columns: minmax(130px, 0.7fr) minmax(0, 1.8fr);
  }
  .compare-tray-actions {
    grid-column: 2;
    justify-content: flex-end;
  }
}
</style>
