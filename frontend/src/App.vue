<script setup lang="ts">
import { computed, provide } from 'vue'
import { storeToRefs } from 'pinia'
import SearchView from './views/SearchView.vue'
import MapView from './components/map/MapView.vue'
import { useSearchStore } from './stores/useSearchStore'
import { TRANSPORT_KEY } from './components/transport/transportContext'
import { useTransport } from './components/transport/useTransport'

const store = useSearchStore()
const { selectedCollege } = storeToRefs(store)
const transportSchoolId = computed(() => selectedCollege.value?.school_id ?? null)

// selectedCollege 的局部空间详情状态：Panel 与 Leaflet Layer 共用同一响应。
provide(TRANSPORT_KEY, useTransport(transportSchoolId))
</script>

<template>
  <SearchView>
    <template #map>
      <MapView />
    </template>
  </SearchView>
</template>
