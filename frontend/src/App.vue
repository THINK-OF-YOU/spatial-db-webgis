<script setup lang="ts">
import SearchView from './views/SearchView.vue'

// MapView 就绪后在此添加 import MapView from './components/map/MapView.vue'，
// 将下方改为 <SearchView><template #map><MapView /></template></SearchView>。
// MapView 与业务 UI 共用 useSearchStore，不触发主查询、不覆盖 results。
</script>

<template>
  <SearchView />
</template>
