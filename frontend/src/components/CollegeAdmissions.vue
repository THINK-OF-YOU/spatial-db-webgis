<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import {
  getCollegeAdmissions,
  getCollegeAdmissionSummary,
} from "../api/admissions";
import { getFilterMeta } from "../api/meta";
import { useSearchStore } from "../stores/useSearchStore";
import type {
  CollegeAdmissionSummary,
  SchoolAdmissionItem,
} from "../types/admission";
import type { FilterMeta } from "../types/meta";

const props = defineProps<{
  schoolId: number;
}>();

const store = useSearchStore();
const { candidateProfile, candidateProfileEnabled, candidateEffectiveRank } =
  storeToRefs(store);

type FilterDraft = {
  source_province: string;
  year: number | "";
  category: string;
  batch: string;
};

const emptyDraft = (): FilterDraft => ({
  source_province: "",
  year: "",
  category: "",
  batch: "",
});

const draft = reactive<FilterDraft>(emptyDraft());
const items = ref<SchoolAdmissionItem[]>([]);
const total = ref(0);
const page = ref(1);
const page_size = ref(10);
const warnings = ref<string[]>([]);
const displayDeduplicated = ref(false);
const loading = ref(false);
const error = ref("");
const moreFiltersOpen = ref(false);
const filterMeta = ref<FilterMeta | null>(null);
const metaWarnings = ref<string[]>([]);
const metaLoading = ref(false);
const metaError = ref("");
const summary = ref<CollegeAdmissionSummary | null>(null);
const summaryLoading = ref(false);
const summaryError = ref("");
const showFullRecords = ref(false);

const candidateProfileActive = computed(() => {
  const rank = candidateEffectiveRank.value;
  return (
    candidateProfileEnabled.value &&
    Boolean(candidateProfile.value.source_province) &&
    candidateProfile.value.year !== null &&
    Boolean(candidateProfile.value.category) &&
    rank !== null &&
    Number.isInteger(rank) &&
    rank > 0
  );
});
const candidateProfileSignature = computed(() =>
  candidateProfileActive.value
    ? JSON.stringify([
        props.schoolId,
        candidateProfile.value.source_province,
        candidateProfile.value.year,
        candidateProfile.value.category,
        candidateProfile.value.batch,
        candidateProfile.value.input_mode,
        candidateProfile.value.score,
        candidateEffectiveRank.value,
      ])
    : "",
);

const pages = computed(() =>
  Math.max(1, Math.ceil(total.value / page_size.value)),
);
const activeFilterCount = computed(
  () =>
    [draft.source_province, draft.year, draft.category, draft.batch].filter(
      Boolean,
    ).length,
);
const visibleWarnings = computed(() =>
  [
    ...new Set([
      ...warnings.value,
      ...(moreFiltersOpen.value ? metaWarnings.value : []),
    ]),
  ],
);

let dataController: AbortController | undefined;
let metaController: AbortController | undefined;
let summaryController: AbortController | undefined;
let requestedPage = 1;

async function loadSummary() {
  summaryController?.abort();
  summary.value = null;
  summaryError.value = "";
  if (!candidateProfileActive.value) {
    summaryLoading.value = false;
    return;
  }

  const rank = candidateEffectiveRank.value;
  const mainYear = candidateProfile.value.year;
  if (rank === null || mainYear === null) return;

  const current = new AbortController();
  summaryController = current;
  summaryLoading.value = true;
  try {
    const data = await getCollegeAdmissionSummary(
      props.schoolId,
      {
        source_province: candidateProfile.value.source_province,
        main_year: mainYear,
        category: candidateProfile.value.category,
        candidate_rank: rank,
        batch: candidateProfile.value.batch || undefined,
      },
      current.signal,
    );
    if (!current.signal.aborted) summary.value = data;
  } catch (cause) {
    if (!current.signal.aborted) {
      summaryError.value =
        cause instanceof Error ? cause.message : "多年度历史参考加载失败。";
    }
  } finally {
    if (summaryController === current) summaryLoading.value = false;
  }
}

async function load(nextPage = 1) {
  requestedPage = nextPage;
  dataController?.abort();
  const current = new AbortController();
  dataController = current;
  loading.value = true;
  error.value = "";
  items.value = [];
  warnings.value = [];

  try {
    const data = await getCollegeAdmissions(
      props.schoolId,
      {
        source_province: draft.source_province || undefined,
        year: draft.year === "" ? undefined : draft.year,
        category: draft.category || undefined,
        batch: draft.batch || undefined,
        page: nextPage,
        page_size: page_size.value,
      },
      current.signal,
    );
    if (current.signal.aborted) return;
    items.value = data.items;
    total.value = data.total;
    page.value = data.page;
    page_size.value = data.page_size;
    warnings.value = [...new Set(data.warnings)];
    displayDeduplicated.value = data.display_deduplicated;
  } catch (cause) {
    if (!current.signal.aborted) {
      error.value =
        cause instanceof Error ? cause.message : "历史投档数据加载失败。";
    }
  } finally {
    if (dataController === current) loading.value = false;
  }
}

async function loadFilterMeta() {
  metaController?.abort();
  const current = new AbortController();
  metaController = current;
  metaLoading.value = true;
  metaError.value = "";
  try {
    const response = await getFilterMeta(current.signal);
    if (current.signal.aborted) return;
    filterMeta.value = response.data;
    metaWarnings.value = [...new Set(response.warnings)];
  } catch (cause) {
    if (!current.signal.aborted) {
      metaError.value =
        cause instanceof Error ? cause.message : "筛选项加载失败。";
    }
  } finally {
    if (metaController === current) metaLoading.value = false;
  }
}

function applyFilters() {
  void load(1);
}

function resetFilters() {
  Object.assign(draft, emptyDraft());
  void load(1);
}

function displayNumber(value: number | null) {
  return value === null ? "未提供" : value.toLocaleString("zh-CN");
}

function displayAdmitCount(value: number | null) {
  if (value === null) return "未提供";
  if (value === 0) return "0（来源值）";
  return value.toLocaleString("zh-CN");
}

function displayRankGap(rankGap: number) {
  if (rankGap === 0) return "与当前参考位次相同";
  return rankGap > 0
    ? `历史最低位次比当前靠后 ${rankGap.toLocaleString("zh-CN")} 位`
    : `历史最低位次比当前靠前 ${Math.abs(rankGap).toLocaleString("zh-CN")} 位`;
}

function recordKey(item: SchoolAdmissionItem, index: number) {
  return [
    page.value,
    index,
    item.source_province,
    item.year,
    item.category,
    item.batch,
    item.subject_req,
  ].join("-");
}

watch(
  () => props.schoolId,
  () => {
    Object.assign(draft, emptyDraft());
    moreFiltersOpen.value = false;
    void load(1);
    if (!filterMeta.value) void loadFilterMeta();
  },
  { immediate: true },
);

watch(
  candidateProfileSignature,
  (signature, previous) => {
    summaryController?.abort();
    summary.value = null;
    summaryError.value = "";
    showFullRecords.value = false;
    if (signature && signature !== previous) void loadSummary();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  dataController?.abort();
  metaController?.abort();
  summaryController?.abort();
});
</script>

<template>
  <section class="college-admissions" aria-labelledby="college-admissions-title">
    <div class="major-section-heading">
      <div>
        <span class="eyebrow">HISTORICAL ADMISSIONS</span>
        <h3 id="college-admissions-title">历史投档</h3>
        <p>按来源条件查看该校历年投档分数与位次。</p>
      </div>
      <span v-if="!candidateProfileActive && !loading && !error" class="major-total">
        {{ total.toLocaleString() }} 条
      </span>
    </div>

    <section
      v-if="candidateProfileActive"
      class="admission-summary"
      aria-labelledby="admission-summary-title"
    >
      <div class="admission-summary-context">
        <div>
          <span class="eyebrow">CANDIDATE PROFILE · MULTI-YEAR</span>
          <h4 id="admission-summary-title">学校级多年度历史参考</h4>
        </div>
        <strong>
          参考位次 {{ candidateEffectiveRank?.toLocaleString("zh-CN") }}
        </strong>
      </div>
      <p class="admission-summary-profile">
        {{ candidateProfile.source_province }} · 主参考年份
        {{ candidateProfile.year }} · {{ candidateProfile.category }} ·
        {{ candidateProfile.batch || "全部批次" }}
        <template v-if="candidateProfile.input_mode === 'score'">
          · {{ candidateProfile.score }} 分解析所得
        </template>
      </p>
      <p class="admission-summary-note">
        各年份均与同一个当前参考位次比较；科类与批次严格使用来源原始口径，不做跨年映射。
      </p>

      <div v-if="summaryLoading" class="state-message major-state" role="status">
        <span class="loading-ring" />正在整理多年度历史参考…
      </div>
      <div v-else-if="summaryError" class="state-message major-state error" role="alert">
        <h3>多年度历史参考暂不可用</h3>
        <p>{{ summaryError }}</p>
        <button class="secondary" @click="loadSummary">重新加载</button>
      </div>
      <div
        v-else-if="summary && !summary.years.length"
        class="state-message major-state"
        role="status"
      >
        <h3>暂无可比较年份</h3>
        <p>当前生源省与科类在主参考年份之前没有可用历史年份。</p>
      </div>
      <div v-else-if="summary" class="admission-summary-years">
        <article
          v-for="entry in summary.years"
          :key="entry.year"
          class="admission-summary-year"
          :class="entry.status"
        >
          <div class="admission-summary-year-head">
            <div>
              <strong>{{ entry.year }} 年</strong>
              <span>{{ entry.record_count.toLocaleString("zh-CN") }} 条真实记录</span>
            </div>
            <span class="admission-summary-status">
              {{
                entry.status === "reference_available"
                  ? "可比较"
                  : entry.status === "rank_unavailable"
                    ? "位次缺失"
                    : "无匹配记录"
              }}
            </span>
          </div>

          <template v-if="entry.reference_admission">
            <dl class="admission-summary-metrics">
              <div>
                <dt>历史最低位次</dt>
                <dd>
                  {{ entry.reference_admission.min_rank.toLocaleString("zh-CN") }}
                </dd>
              </div>
              <div>
                <dt>历史最低分</dt>
                <dd>{{ displayNumber(entry.reference_admission.min_score) }}</dd>
              </div>
            </dl>
            <p class="admission-summary-gap">
              {{ displayRankGap(entry.reference_admission.rank_gap) }}
            </p>
            <p class="admission-summary-source">
              {{ entry.reference_admission.unit_name }} ·
              {{ entry.reference_admission.batch || "批次未提供" }}
            </p>
          </template>
          <p v-else-if="entry.status === 'rank_unavailable'" class="admission-summary-empty">
            有历史投档记录，但当前缺少可用于位次比较的历史最低位次。
          </p>
          <p v-else class="admission-summary-empty">
            当前考试口径下无匹配投档记录。
          </p>
        </article>
      </div>
    </section>

    <form
      v-if="!candidateProfileActive"
      class="major-filter-form"
      @submit.prevent="applyFilters"
    >
      <div class="admission-filter-primary">
        <div>
          <label for="admission-province">生源省</label>
          <select
            v-if="filterMeta"
            id="admission-province"
            v-model="draft.source_province"
          >
            <option value="">全部生源省</option>
            <option
              v-for="province in filterMeta.source_provinces"
              :key="province"
              :value="province"
            >
              {{ province }}
            </option>
          </select>
          <input
            v-else
            id="admission-province"
            v-model="draft.source_province"
            :disabled="metaLoading"
            placeholder="如：湖南"
          />
        </div>
        <div>
          <label for="admission-year">年份</label>
          <select v-if="filterMeta" id="admission-year" v-model="draft.year">
            <option value="">全部年份</option>
            <option v-for="year in filterMeta.years" :key="year" :value="year">
              {{ year }}
            </option>
          </select>
          <input
            v-else
            id="admission-year"
            v-model.number="draft.year"
            :disabled="metaLoading"
            type="number"
            min="2000"
            max="2100"
            placeholder="如：2025"
          />
        </div>
      </div>

      <p v-if="metaError" class="major-filter-hint error-text">
        筛选项未能加载，可直接输入条件。
      </p>

      <button
        type="button"
        class="major-more-toggle"
        :aria-expanded="moreFiltersOpen"
        @click="moreFiltersOpen = !moreFiltersOpen"
      >
        <span>更多筛选</span>
        <span>
          {{ activeFilterCount ? `已选 ${activeFilterCount} 项` : "科类、批次" }}
          {{ moreFiltersOpen ? "收起" : "展开" }}
        </span>
      </button>

      <div v-if="moreFiltersOpen" class="admission-filter-more">
        <div>
          <label for="admission-category">科类 / 选科</label>
          <select
            v-if="filterMeta"
            id="admission-category"
            v-model="draft.category"
          >
            <option value="">全部科类</option>
            <option
              v-for="category in filterMeta.categories"
              :key="category"
              :value="category"
            >
              {{ category }}
            </option>
          </select>
          <input
            v-else
            id="admission-category"
            v-model="draft.category"
            :disabled="metaLoading"
            placeholder="来源原始口径"
          />
        </div>
        <div>
          <label for="admission-batch">录取批次</label>
          <select v-if="filterMeta" id="admission-batch" v-model="draft.batch">
            <option value="">全部批次</option>
            <option
              v-for="batch in filterMeta.batches"
              :key="batch"
              :value="batch"
            >
              {{ batch }}
            </option>
          </select>
          <input
            v-else
            id="admission-batch"
            v-model="draft.batch"
            :disabled="metaLoading"
            placeholder="来源原始口径"
          />
        </div>
      </div>

      <div class="major-filter-actions">
        <button class="primary" type="submit" :disabled="loading">
          应用筛选 <span aria-hidden="true">→</span>
        </button>
        <button type="button" class="quiet" :disabled="loading" @click="resetFilters">
          清空条件
        </button>
      </div>
    </form>

    <button
      v-if="candidateProfileActive"
      type="button"
      class="admission-full-toggle"
      :aria-expanded="showFullRecords"
      @click="showFullRecords = !showFullRecords"
    >
      <span>完整历史投档明细</span>
      <span>{{ showFullRecords ? "收起" : "展开查看" }}</span>
    </button>

    <div
      v-if="!candidateProfileActive || showFullRecords"
      class="admission-full-records"
    >
    <div class="major-result-toolbar">
      <span>{{ !loading && !error ? `第 ${page} / ${pages} 页` : "查询结果" }}</span>
      <label>
        每页
        <select v-model.number="page_size" :disabled="loading" @change="load(1)">
          <option :value="10">10</option>
          <option :value="20">20</option>
          <option :value="50">50</option>
        </select>
      </label>
    </div>

    <p v-for="warning in visibleWarnings" :key="warning" class="business-warning">
      {{ warning }}
    </p>

    <div v-if="loading" class="state-message major-state" role="status">
      <span class="loading-ring" />正在加载历史投档…
    </div>
    <div v-else-if="error" class="state-message major-state error" role="alert">
      <h3>历史投档暂不可用</h3>
      <p>{{ error }}</p>
      <button class="secondary" @click="load(requestedPage)">重新加载</button>
    </div>
    <div v-else-if="!items.length" class="state-message major-state" role="status">
      <h3>{{ activeFilterCount ? "没有匹配的投档记录" : "暂无历史投档记录" }}</h3>
      <p v-if="activeFilterCount">请尝试减少筛选条件或更换生源省、年份。</p>
      <p v-else>该高校当前没有可展示的历史投档数据。</p>
      <button v-if="activeFilterCount" class="secondary" @click="resetFilters">
        清空筛选
      </button>
    </div>
    <div v-else class="admission-record-list">
      <article
        v-for="(item, index) in items"
        :key="recordKey(item, index)"
        class="admission-record"
      >
        <div class="admission-record-heading">
          <div>
            <span>{{ item.source_province || "生源省未提供" }}</span>
            <h4>{{ item.year === null ? "年份未提供" : `${item.year} 年` }}</h4>
          </div>
          <div class="admission-vocabulary">
            <strong>{{ item.category || "科类未提供" }}</strong>
            <span>{{ item.batch || "批次未提供" }}</span>
          </div>
        </div>

        <dl class="admission-key-metrics">
          <div>
            <dt>最低分</dt>
            <dd>{{ displayNumber(item.min_score) }}</dd>
          </div>
          <div>
            <dt>最低位次</dt>
            <dd>{{ displayNumber(item.min_rank) }}</dd>
          </div>
        </dl>

        <dl class="admission-more-metrics">
          <div>
            <dt>控制线</dt>
            <dd>{{ displayNumber(item.control_score) }}</dd>
          </div>
          <div>
            <dt>线差</dt>
            <dd>{{ displayNumber(item.score_diff) }}</dd>
          </div>
          <div>
            <dt>录取人数（来源）</dt>
            <dd>{{ displayAdmitCount(item.admit_count) }}</dd>
          </div>
        </dl>

        <p class="major-subject">
          <span>选科要求</span>{{ item.subject_req || "未提供" }}
        </p>
      </article>
    </div>

    <nav
      v-if="!loading && !error && items.length"
      class="major-pagination"
      aria-label="历史投档分页"
    >
      <button :disabled="page <= 1" @click="load(page - 1)">← 上一页</button>
      <span>{{ page }} / {{ pages }}</span>
      <button :disabled="page >= pages" @click="load(page + 1)">下一页 →</button>
    </nav>

    <div v-if="!loading && !error" class="major-data-notes">
      <p>科类与批次沿用来源数据原始口径，不代表全国统一分类。</p>
      <p>录取人数按来源原值展示；0 不解释为“未公布”或“录取 0 人”。</p>
      <p v-if="displayDeduplicated">已合并展示字段完全一致的重复记录。</p>
    </div>
    </div>
  </section>
</template>
