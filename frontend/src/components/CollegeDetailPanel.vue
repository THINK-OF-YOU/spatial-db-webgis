<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { getCollege } from "../api/colleges";
import type { CollegeDetail } from "../types/college";
import { useSearchStore } from "../stores/useSearchStore";
import CollegeMajorAdmissions from "./CollegeMajorAdmissions.vue";

const store = useSearchStore();
const { selectedCollege } = storeToRefs(store);
const detail = ref<CollegeDetail | null>(null);
const loading = ref(false);
const error = ref("");
const panel = ref<HTMLElement | null>(null);
const activeTab = ref<"overview" | "majors">("overview");
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
    :class="{ 'major-mode': activeTab === 'majors' }"
    tabindex="-1"
    role="region"
    aria-label="高校详情"
    :aria-busy="loading"
    @keydown.esc.stop="close"
  >
    <div class="detail-top">
      <span class="eyebrow">高校详情</span
      ><button class="close-button" aria-label="关闭高校详情" @click="close">
        ×
      </button>
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
      <div class="detail-hero">
        <span class="detail-emblem" aria-hidden="true">{{
          detail.college.name.slice(0, 1)
        }}</span>
        <h2>{{ detail.college.name }}</h2>
        <p>{{ detail.college.edu_level || "办学层次未提供" }}</p>
      </div>
      <dl class="college-facts">
        <div>
          <dt>登记地区</dt>
          <dd>{{ detail.college.reg_province || "未提供" }}</dd>
        </div>
        <div>
          <dt>院校代码</dt>
          <dd>{{ detail.college.national_code || "未提供" }}</dd>
        </div>
      </dl>
      <nav class="detail-tabs" aria-label="高校详情内容">
        <button
          :class="{ active: activeTab === 'overview' }"
          :aria-selected="activeTab === 'overview'"
          @click="activeTab = 'overview'"
        >
          高校概览
        </button>
        <button
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

      <template v-if="activeTab === 'overview'">
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
              class="status-tag"
              :class="
                campus.verify_status === 'CONFIRMED' ? 'confirmed' : 'candidate'
              "
              >{{
                campus.verify_status === "CONFIRMED"
                  ? "已核验校区"
                  : "候选校区点，尚未完成实体级人工核验"
              }}</span
            >
            <h4>{{ campus.campus_name || "校区名称未提供" }}</h4>
            <p>{{ campus.address || "地址未提供" }}</p>
            <p class="coordinates">
              经度 {{ campus.lon?.toFixed(5) ?? "未提供" }} · 纬度
              {{ campus.lat?.toFixed(5) ?? "未提供" }}
            </p>
          </article>
        </section>
        <p class="detail-note">
          校区点位不代表学校全部办学地点。候选点仅供参考，请注意核验状态。
        </p>
      </template>
      <CollegeMajorAdmissions
        v-else
        :school-id="detail.college.school_id"
        :major-mapping-available="detail.data_availability.major_mapping"
      />
    </template>
  </aside>
</template>
