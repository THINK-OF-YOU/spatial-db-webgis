<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { getCollegeMajors, getStandardMajors } from "../api/majors";
import { getFilterMeta } from "../api/meta";
import type { FilterMeta } from "../types/meta";
import type {
  MajorAdmissionItem,
  MajorMappingFilter,
  MajorStandardStatus,
  StandardMajor,
} from "../types/major";

const props = defineProps<{
  schoolId: number;
  majorMappingAvailable: boolean;
}>();

type FilterDraft = {
  q: string;
  source_province: string;
  year: number | "";
  category: string;
  batch: string;
  mapping: MajorMappingFilter | "";
};

const emptyDraft = (): FilterDraft => ({
  q: "",
  source_province: "",
  year: "",
  category: "",
  batch: "",
  mapping: "",
});

const draft = reactive<FilterDraft>(emptyDraft());
const items = ref<MajorAdmissionItem[]>([]);
const total = ref(0);
const page = ref(1);
const page_size = ref(10);
const warnings = ref<string[]>([]);
const factsWithoutMajorName = ref(0);
const displayDeduplicated = ref(false);
const loading = ref(false);
const error = ref("");
const moreFiltersOpen = ref(false);
const filterMeta = ref<FilterMeta | null>(null);
const metaLoading = ref(false);
const metaError = ref("");

const standardMajorQuery = ref("");
const standardMajorOptions = ref<StandardMajor[]>([]);
const selectedStandardMajor = ref<StandardMajor | null>(null);
const standardMajorLoading = ref(false);
const standardMajorError = ref("");

const pages = computed(() =>
  Math.max(1, Math.ceil(total.value / page_size.value)),
);
const activeFilterCount = computed(
  () =>
    [
      draft.q,
      draft.source_province,
      draft.year,
      draft.category,
      draft.batch,
      draft.mapping,
      selectedStandardMajor.value,
    ].filter(Boolean).length,
);

let dataController: AbortController | undefined;
let metaController: AbortController | undefined;
let standardMajorController: AbortController | undefined;
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
    const data = await getCollegeMajors(
      props.schoolId,
      {
        q: draft.q.trim() || undefined,
        source_province: draft.source_province || undefined,
        year: draft.year === "" ? undefined : draft.year,
        category: draft.category || undefined,
        batch: draft.batch || undefined,
        mapping: draft.mapping || undefined,
        std_major_id: selectedStandardMajor.value?.major_id,
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
    factsWithoutMajorName.value = data.facts_without_major_name;
    displayDeduplicated.value = data.display_deduplicated;
  } catch (cause) {
    if (!current.signal.aborted) {
      error.value =
        cause instanceof Error ? cause.message : "专业录取数据加载失败。";
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
    if (!current.signal.aborted) filterMeta.value = response.data;
  } catch (cause) {
    if (!current.signal.aborted) {
      metaError.value =
        cause instanceof Error ? cause.message : "筛选项加载失败。";
    }
  } finally {
    if (metaController === current) metaLoading.value = false;
  }
}

async function searchStandardMajors() {
  standardMajorController?.abort();
  const current = new AbortController();
  standardMajorController = current;
  standardMajorLoading.value = true;
  standardMajorError.value = "";
  standardMajorOptions.value = [];
  try {
    const data = await getStandardMajors(
      {
        q: standardMajorQuery.value.trim() || undefined,
        page: 1,
        page_size: 8,
      },
      current.signal,
    );
    if (!current.signal.aborted) standardMajorOptions.value = data.items;
  } catch (cause) {
    if (!current.signal.aborted) {
      standardMajorError.value =
        cause instanceof Error ? cause.message : "标准专业查询失败。";
    }
  } finally {
    if (standardMajorController === current)
      standardMajorLoading.value = false;
  }
}

function chooseStandardMajor(major: StandardMajor) {
  selectedStandardMajor.value = major;
  draft.mapping = "mapped";
  standardMajorQuery.value = "";
  standardMajorOptions.value = [];
}

function clearStandardMajor() {
  selectedStandardMajor.value = null;
  standardMajorQuery.value = "";
  standardMajorOptions.value = [];
}

function applyFilters() {
  void load(1);
}

function resetFilters() {
  Object.assign(draft, emptyDraft());
  clearStandardMajor();
  void load(1);
}

function statusText(status: MajorStandardStatus) {
  if (status === "MAPPED") return "已关联标准专业";
  if (status === "UNMAPPED") return "暂未归入标准专业";
  return "来源专业待归一";
}

function factContext(item: MajorAdmissionItem) {
  return [
    item.year === null ? null : `${item.year} 年`,
    item.source_province,
    item.category,
    item.batch,
  ].filter((value): value is string => Boolean(value));
}

function displayNumber(value: number | null) {
  return value === null ? "未提供" : value.toLocaleString("zh-CN");
}

watch(
  () => draft.mapping,
  (mapping) => {
    if (mapping === "unmapped" && selectedStandardMajor.value) {
      clearStandardMajor();
    }
  },
);

watch(
  () => props.schoolId,
  () => {
    Object.assign(draft, emptyDraft());
    clearStandardMajor();
    moreFiltersOpen.value = false;
    void load(1);
    if (!filterMeta.value) void loadFilterMeta();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  dataController?.abort();
  metaController?.abort();
  standardMajorController?.abort();
});
</script>

<template>
  <section class="major-admissions" aria-labelledby="major-admissions-title">
    <div class="major-section-heading">
      <div>
        <span class="eyebrow">ADMISSION MAJORS</span>
        <h3 id="major-admissions-title">专业录取</h3>
        <p>来源招生专业表达与标准专业分层展示。</p>
      </div>
      <span v-if="!loading && !error" class="major-total">
        {{ total.toLocaleString() }} 条
      </span>
    </div>

    <p v-if="!majorMappingAvailable" class="major-availability-note">
      该校有专业录取数据，但暂无已建立的标准专业映射；来源专业与录取事实仍可正常查询。
    </p>

    <form class="major-filter-form" @submit.prevent="applyFilters">
      <div class="major-filter-primary">
        <div class="major-filter-query">
          <label for="major-query">专业名称</label>
          <input
            id="major-query"
            v-model="draft.q"
            type="search"
            placeholder="搜索来源专业或标准专业"
            autocomplete="off"
          />
        </div>
        <div>
          <label for="major-province">生源省</label>
          <select
            v-if="filterMeta"
            id="major-province"
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
            id="major-province"
            v-model="draft.source_province"
            :disabled="metaLoading"
            placeholder="如：湖南"
          />
        </div>
        <div>
          <label for="major-year">年份</label>
          <select v-if="filterMeta" id="major-year" v-model="draft.year">
            <option value="">全部年份</option>
            <option v-for="year in filterMeta.years" :key="year" :value="year">
              {{ year }}
            </option>
          </select>
          <input
            v-else
            id="major-year"
            v-model.number="draft.year"
            :disabled="metaLoading"
            type="number"
            min="2000"
            max="2100"
            placeholder="如：2025"
          />
        </div>
      </div>

      <p v-if="metaError" class="major-filter-hint">
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
          {{ activeFilterCount ? `已选 ${activeFilterCount} 项` : "科类、批次、映射" }}
          {{ moreFiltersOpen ? "收起" : "展开" }}
        </span>
      </button>

      <div v-if="moreFiltersOpen" class="major-filter-more">
        <div>
          <label for="major-category">科类 / 选科</label>
          <select
            v-if="filterMeta"
            id="major-category"
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
            id="major-category"
            v-model="draft.category"
            :disabled="metaLoading"
            placeholder="来源原始口径"
          />
        </div>
        <div>
          <label for="major-batch">录取批次</label>
          <select v-if="filterMeta" id="major-batch" v-model="draft.batch">
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
            id="major-batch"
            v-model="draft.batch"
            :disabled="metaLoading"
            placeholder="来源原始口径"
          />
        </div>
        <div>
          <label for="major-mapping">标准映射状态</label>
          <select id="major-mapping" v-model="draft.mapping">
            <option value="">全部状态</option>
            <option value="mapped">已关联标准专业</option>
            <option value="unmapped">暂无标准映射（含待归一）</option>
          </select>
        </div>

        <div class="standard-major-filter">
          <label for="standard-major-query">指定标准专业</label>
          <div v-if="selectedStandardMajor" class="selected-standard-major">
            <span>
              <strong>{{ selectedStandardMajor.std_name }}</strong>
              {{ selectedStandardMajor.std_code }} · {{ selectedStandardMajor.education_level }}
            </span>
            <button type="button" aria-label="清除标准专业筛选" @click="clearStandardMajor">
              ×
            </button>
          </div>
          <template v-else>
            <div class="standard-major-search">
              <input
                id="standard-major-query"
                v-model="standardMajorQuery"
                type="search"
                placeholder="输入专业名称或代码"
                :disabled="!majorMappingAvailable || standardMajorLoading"
                @keydown.enter.prevent="searchStandardMajors"
              />
              <button
                type="button"
                :disabled="!majorMappingAvailable || standardMajorLoading"
                @click="searchStandardMajors"
              >
                {{ standardMajorLoading ? "查询中" : "查找" }}
              </button>
            </div>
            <p v-if="standardMajorError" class="major-filter-hint error-text">
              {{ standardMajorError }}
            </p>
            <div v-if="standardMajorOptions.length" class="standard-major-options">
              <button
                v-for="major in standardMajorOptions"
                :key="major.major_id"
                type="button"
                @click="chooseStandardMajor(major)"
              >
                <strong>{{ major.std_name }}</strong>
                <span>{{ major.std_code }} · {{ major.education_level }}</span>
              </button>
            </div>
          </template>
          <p class="major-filter-hint">
            标准专业筛选仅检索已建立精确映射的记录，具体覆盖提示以后端返回为准。
          </p>
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

    <p v-for="warning in warnings" :key="warning" class="business-warning">
      {{ warning }}
    </p>

    <div v-if="loading" class="state-message major-state" role="status">
      <span class="loading-ring" />正在加载专业录取…
    </div>
    <div v-else-if="error" class="state-message major-state error" role="alert">
      <h3>专业录取暂不可用</h3>
      <p>{{ error }}</p>
      <button class="secondary" @click="load(requestedPage)">重新加载</button>
    </div>
    <div v-else-if="!items.length" class="state-message major-state" role="status">
      <h3>{{ activeFilterCount ? "没有匹配的专业录取" : "暂无专业录取记录" }}</h3>
      <p v-if="activeFilterCount">请尝试减少筛选条件；未建立标准映射不代表该校未招生。</p>
      <p v-else>该高校当前没有可展示的来源专业录取表达。</p>
      <button v-if="activeFilterCount" class="secondary" @click="resetFilters">
        清空筛选
      </button>
    </div>
    <div v-else class="major-record-list">
      <article
        v-for="(item, index) in items"
        :key="`${page}-${index}-${item.raw_major_name}`"
        class="major-record"
      >
        <div class="major-record-title">
          <div>
            <span class="major-source-label">来源招生专业表达</span>
            <h4>{{ item.raw_major_name }}</h4>
          </div>
          <span class="major-status" :class="item.std_status.toLowerCase()">
            {{ statusText(item.std_status) }}
          </span>
        </div>

        <div v-if="item.std_major" class="standard-major-line">
          <span>标准专业</span>
          <strong>{{ item.std_major.std_name }}</strong>
          <small>
            {{ item.std_major.std_code }} · {{ item.std_major.education_level }}
          </small>
        </div>
        <p v-else class="unmapped-explanation">
          当前未关联标准专业目录；这不影响该条来源专业及录取事实的真实性。
        </p>

        <div class="major-context" aria-label="招生条件">
          <span v-for="part in factContext(item)" :key="part">{{ part }}</span>
          <span v-if="!factContext(item).length">招生条件未提供</span>
        </div>

        <dl class="major-scores">
          <div>
            <dt>最低分</dt>
            <dd>{{ displayNumber(item.min_score) }}</dd>
          </div>
          <div>
            <dt>平均分</dt>
            <dd>{{ displayNumber(item.avg_score) }}</dd>
          </div>
          <div>
            <dt>最高分</dt>
            <dd>{{ displayNumber(item.max_score) }}</dd>
          </div>
          <div>
            <dt>最低位次</dt>
            <dd>{{ displayNumber(item.min_rank) }}</dd>
          </div>
          <div>
            <dt>录取人数</dt>
            <dd>{{ displayNumber(item.admit_count) }}</dd>
          </div>
        </dl>

        <p class="major-subject">
          <span>选科要求</span>{{ item.subject_req || "未提供" }}
        </p>
      </article>
    </div>

    <nav v-if="!loading && !error && items.length" class="major-pagination" aria-label="专业录取分页">
      <button :disabled="page <= 1" @click="load(page - 1)">← 上一页</button>
      <span>{{ page }} / {{ pages }}</span>
      <button :disabled="page >= pages" @click="load(page + 1)">下一页 →</button>
    </nav>

    <div v-if="!loading && !error" class="major-data-notes">
      <p v-if="factsWithoutMajorName > 0">
        另有 {{ factsWithoutMajorName.toLocaleString() }} 条录取记录的来源未提供专业名，未列入本列表。
      </p>
      <p v-if="displayDeduplicated">已合并展示字段完全一致的重复记录。</p>
    </div>
  </section>
</template>
