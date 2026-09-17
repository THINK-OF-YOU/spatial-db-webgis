<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { getCollegeAdmissions } from "../api/admissions";
import { getFilterMeta } from "../api/meta";
import type { SchoolAdmissionItem } from "../types/admission";
import type { FilterMeta } from "../types/meta";

const props = defineProps<{
  schoolId: number;
}>();

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
let requestedPage = 1;

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

onBeforeUnmount(() => {
  dataController?.abort();
  metaController?.abort();
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
      <span v-if="!loading && !error" class="major-total">
        {{ total.toLocaleString() }} 条
      </span>
    </div>

    <form class="major-filter-form" @submit.prevent="applyFilters">
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
  </section>
</template>
