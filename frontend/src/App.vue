<script setup lang="ts">
import SearchView from './views/SearchView.vue'
import MapView from './components/map/MapView.vue'
</script>

<template>
  <SearchView>
    <template #map>
      <MapView />
    </template>
  </SearchView>
</template>
