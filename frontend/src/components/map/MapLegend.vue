<script setup lang="ts"></script>

<template>
  <div class="map-legend">
    <div class="item"><span class="dot confirmed"></span><span>已核验校区</span></div>
    <div class="item"><span class="dot candidate"></span><span>候选校区点，尚未完成实体级人工核验</span></div>
  </div>
</template>

<style scoped>
.map-legend {
  position: absolute;
  bottom: 24px;
  left: 12px;
  z-index: 1000;
  background: white;
  border: 1px solid #dce2e8;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: #263340;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
}
.item {
  display: flex;
  align-items: center;
  gap: 8px;
  line-height: 20px;
}
.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex: none;
}
.dot.confirmed {
  background: #2e7d32;
  border: 2px solid #ffffff;
  box-shadow: 0 0 0 1px #2e7d32;
}
.dot.candidate {
  background: rgba(245, 158, 11, 0.3);
  border: 2px solid #f59e0b;
}
</style>
