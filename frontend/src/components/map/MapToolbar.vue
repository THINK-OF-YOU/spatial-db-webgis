<script setup lang="ts">
import type { DrawMode } from './types'

defineProps<{ mode: DrawMode; regionOpen: boolean }>()
const emit = defineEmits<{
  'update:mode': [mode: DrawMode]
  'update:regionOpen': [open: boolean]
  clear: []
}>()

const items: { key: DrawMode; label: string; title: string }[] = [
  { key: 'browse', label: '浏览', title: '浏览模式（点击校区 / 行政区）' },
  { key: 'point', label: '参考点', title: '点击地图设置空间查询参考点' },
  { key: 'rect', label: '矩形', title: '拖拽绘制矩形范围' },
  { key: 'polygon', label: '多边形', title: '点击绘制多边形，双击完成' },
]
</script>

<template>
  <div class="map-toolbar">
    <button
      v-for="it in items.slice(0, 1)"
      :key="it.key"
      type="button"
      :class="{ active: mode === it.key }"
      :title="it.title"
      @click="emit('update:mode', it.key)"
    >
      {{ it.label }}
    </button>
    <button
      type="button"
      :class="{ active: regionOpen }"
      title="打开或关闭行政区选择器"
      :aria-pressed="regionOpen"
      @click="emit('update:regionOpen', !regionOpen)"
    >
      行政区
    </button>
    <button
      v-for="it in items.slice(1)"
      :key="it.key"
      type="button"
      :class="{ active: mode === it.key }"
      :title="it.title"
      @click="emit('update:mode', it.key)"
    >
      {{ it.label }}
    </button>
    <button type="button" class="clear" title="清除空间条件（行政区 / 参考点 / 半径 / 绘制）" @click="emit('clear')">
      清除空间
    </button>
  </div>
</template>

<style scoped>
.map-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 1000;
  display: flex;
  gap: 6px;
  background: white;
  border: 1px solid #dce2e8;
  border-radius: 8px;
  padding: 6px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
}
.map-toolbar button {
  border: 1px solid transparent;
  background: #f3f5f7;
  color: #263340;
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 12px;
  cursor: pointer;
}
.map-toolbar button.active {
  background: #1d4ed8;
  color: white;
  border-color: #1d4ed8;
}
.map-toolbar button.clear {
  color: #b91c1c;
}
</style>
