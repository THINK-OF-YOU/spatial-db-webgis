<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useSearchStore } from '../stores/useSearchStore'

const { results } = storeToRefs(useSearchStore())
</script>

<template>
  <div class="search-page">
    <header class="top-bar">
      <h1>高校志愿填报空间查询原型</h1>
      <span>V1 · 公共底座</span>
    </header>
    <main class="workspace">
      <aside class="panel filters-panel" aria-labelledby="filters-title">
        <h2 id="filters-title">筛选条件</h2>
        <p>筛选区占位</p>
      </aside>
      <section class="panel map-panel" aria-label="地图区域">
        <!-- 接入组件需填满父容器；地图实例由 MapView 内部维护。 -->
        <div class="map-host">
          <slot name="map">
            <div class="map-placeholder">
              <h2>地图区域</h2>
              <p>MapView 接入位置</p>
            </div>
          </slot>
        </div>
      </section>
      <section class="panel results-panel" aria-labelledby="results-title">
        <h2 id="results-title">高校结果</h2>
        <p>结果列表占位 · 当前结果 {{ results.length }} 所</p>
      </section>
    </main>
  </div>
</template>
