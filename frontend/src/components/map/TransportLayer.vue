<script setup lang="ts">
import { inject, markRaw, onBeforeUnmount, watch } from 'vue'
import * as L from 'leaflet'
import { TRANSPORT_KEY } from '../transport/transportContext'
import { MODE_LABELS } from '../transport/transportTypes'
import type { TransportItem, TransportMode } from '../transport/transportTypes'
import { MAP_KEY } from './mapContext'

const mapRef = inject(MAP_KEY)!
const transport = inject(TRANSPORT_KEY)!

const { items } = transport
let layerGroup: L.LayerGroup | null = null

const MODE_STYLE: Record<TransportMode, L.CircleMarkerOptions> = {
  metro: { radius: 6, color: '#ffffff', weight: 2, fillColor: '#2563eb', fillOpacity: 0.95 },
  rail: { radius: 7, color: '#ffffff', weight: 2, fillColor: '#7c3aed', fillOpacity: 0.95 },
  rail_halt: { radius: 6, color: '#ffffff', weight: 2, fillColor: '#d97706', fillOpacity: 0.95 },
  airport: { radius: 8, color: '#ffffff', weight: 2, fillColor: '#dc2626', fillOpacity: 0.95 },
}

function textLine(className: string, text: string) {
  const line = document.createElement('div')
  line.className = className
  line.textContent = text
  return line
}

function popupContent(item: TransportItem) {
  const root = document.createElement('div')
  root.className = 'transport-popup'
  root.append(textLine('transport-popup-title', item.name))
  if (item.name_zh && item.name_zh !== item.name) {
    root.append(textLine('transport-popup-secondary', item.name_zh))
  }
  root.append(
    textLine('transport-popup-meta', `${MODE_LABELS[item.mode]} · ${item.distance_km.toFixed(2)} km`),
    textLine('transport-popup-campus', `最近校区：${item.campus_name}`),
  )
  return root
}

function tooltipContent(item: TransportItem) {
  const root = document.createElement('span')
  root.textContent = `${item.name} · ${item.distance_km.toFixed(2)} km`
  return root
}

function render() {
  const map = mapRef.value
  if (!map) return
  if (!layerGroup) layerGroup = markRaw(L.layerGroup()).addTo(map)
  else layerGroup.clearLayers()

  for (const item of items.value) {
    const marker = markRaw(
      L.circleMarker([item.lat, item.lon], {
        ...MODE_STYLE[item.mode],
        pane: 'transport',
        bubblingMouseEvents: false,
      }),
    )
    marker.bindTooltip(tooltipContent(item), { direction: 'top', offset: [0, -5] })
    marker.bindPopup(popupContent(item), { maxWidth: 260 })
    marker.addTo(layerGroup)
  }
}

watch([mapRef, items], render, { immediate: true })

onBeforeUnmount(() => {
  if (layerGroup && mapRef.value) mapRef.value.removeLayer(layerGroup)
  layerGroup = null
})
</script>

<template></template>

<style>
.transport-popup {
  min-width: 165px;
  color: #26372e;
  line-height: 1.45;
}
.transport-popup-title {
  font-size: 13px;
  font-weight: 700;
}
.transport-popup-secondary,
.transport-popup-campus {
  color: #78877f;
  font-size: 11px;
}
.transport-popup-meta {
  margin-top: 5px;
  color: #3f6d54;
  font-size: 11px;
  font-weight: 650;
}
</style>
