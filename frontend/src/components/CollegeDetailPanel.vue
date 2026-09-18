<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { getCollege } from "../api/colleges";
import type { CollegeDetail } from "../types/college";
import { useSearchStore } from "../stores/useSearchStore";
import CollegeAdmissions from "./CollegeAdmissions.vue";
import CollegeMajorAdmissions from "./CollegeMajorAdmissions.vue";
import TransportPanel from "./transport/TransportPanel.vue";
import TransportSummary from "./transport/TransportSummary.vue";

const store = useSearchStore();
const { selectedCollege } = storeToRefs(store);
const detail = ref<CollegeDetail | null>(null);
const loading = ref(false);
const error = ref("");
const panel = ref<HTMLElement | null>(null);
const activeTab = ref<"overview" | "admissions" | "majors">("overview");
let controller: AbortController | undefined;
let returnFocus: HTMLElement | null = null;
async function load(school_id: number) {
  controller?.abort();
  const current = new AbortController();
  controller = current;
  detail.value = null;
  error.value = "";
  loading.value = true;
  try {
    const data = await getCollege(school_id, current.signal);
    if (!current.signal.aborted) detail.value = data;
  } catch (cause) {
    if (!current.signal.aborted)
      error.value = cause instanceof Error ? cause.message : "详情加载失败。";
  } finally {
    if (controller === current) loading.value = false;
  }
}
watch(
  () => selectedCollege.value?.school_id,
  async (id, previous) => {
    if (id === undefined) {
      controller?.abort();
      detail.value = null;
      activeTab.value = "overview";
      return;
    }
    activeTab.value = "overview";
    if (previous === undefined)
      returnFocus =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
    void load(id);
    await nextTick();
    panel.value?.focus();
  },
  { immediate: true },
);
function close() {
  store.setSelectedCollege(null);
  if (returnFocus?.isConnected) returnFocus.focus();
}
onBeforeUnmount(() => controller?.abort());
</script>

<template>
  <aside
    v-if="selectedCollege"
    ref="panel"
    class="detail-panel"
    tabindex="-1"
    role="region"
    aria-label="高校详情"
    :aria-busy="loading"
    @keydown.esc.stop="close"
  >
    <div class="detail-top">
      <div class="detail-title">
        <h2 v-if="detail">{{ detail.college.name }}</h2>
        <span v-if="detail?.college.edu_level" class="detail-level">
          {{ detail.college.edu_level }}
        </span>
        <span v-else class="detail-loading-title">正在载入…</span>
      </div>
      <button class="close-button" aria-label="关闭高校详情" @click="close">×</button>
    </div>
    <div v-if="loading" class="state-message" role="status">
      <span class="loading-ring" />正在加载高校详情…
    </div>
    <div v-else-if="error" class="state-message error" role="alert">
      <h3>详情暂不可用</h3>
      <p>{{ error }}</p>
      <button class="secondary" @click="load(selectedCollege.school_id)">
        重试详情
      </button>
    </div>
    <template v-else-if="detail">
      <nav class="detail-tabs" aria-label="高校详情内容">
        <button
          type="button"
          :class="{ active: activeTab === 'overview' }"
          :aria-selected="activeTab === 'overview'"
          @click="activeTab = 'overview'"
        >
          高校概览
        </button>
        <button
          type="button"
          :class="{ active: activeTab === 'admissions' }"
          :aria-selected="activeTab === 'admissions'"
          :disabled="!detail.data_availability.school_admission"
          :title="
            detail.data_availability.school_admission
              ? '查看历史投档'
              : '该校暂无历史投档数据'
          "
          @click="activeTab = 'admissions'"
        >
          历史投档
          <span v-if="!detail.data_availability.school_admission">暂无数据</span>
        </button>
        <button
          type="button"
          :class="{ active: activeTab === 'majors' }"
          :aria-selected="activeTab === 'majors'"
          :disabled="!detail.data_availability.major_admission"
          :title="
            detail.data_availability.major_admission
              ? '查看专业录取'
              : '该校暂无来源专业录取数据'
          "
          @click="activeTab = 'majors'"
        >
          专业录取
          <span v-if="!detail.data_availability.major_admission">暂无数据</span>
        </button>
      </nav>

      <div class="detail-body">
        <template v-if="activeTab === 'overview'">
          <TransportSummary :school-id="detail.college.school_id" />
          <section class="campus-section">
            <div class="section-title">
              <h3>校区信息</h3>
              <span>{{ detail.campuses.length }} 个点位</span>
            </div>
            <div v-if="!detail.campuses.length" class="no-campus">
              <h4>暂无可信校区数据</h4>
              <p>高校信息仍可正常浏览，地图不会定位到该校。</p>
            </div>
            <article
              v-for="campus in detail.campuses"
              :key="campus.campus_id"
              class="campus-card"
            >
              <span
                v-if="campus.verify_status === 'CONFIRMED'"
                class="status-tag confirmed"
                >已核验</span
              >
              <h4>{{ campus.campus_name || "校区名称未提供" }}</h4>
              <p>{{ campus.address || "地址未提供" }}</p>
              <p class="coordinates">
                经度 {{ campus.lon?.toFixed(5) ?? "未提供" }} · 纬度
                {{ campus.lat?.toFixed(5) ?? "未提供" }}
              </p>
            </article>
          </section>
          <TransportPanel />
          <p class="detail-note">
            校区坐标主要用于空间查询参考，部分点位尚未完成人工核验。
          </p>
        </template>
        <CollegeAdmissions
          v-else-if="activeTab === 'admissions'"
          :school-id="detail.college.school_id"
        />
        <CollegeMajorAdmissions
          v-else-if="activeTab === 'majors'"
          :school-id="detail.college.school_id"
          :major-mapping-available="detail.data_availability.major_mapping"
        />
      </div>
    </template>
  </aside>
</template>
