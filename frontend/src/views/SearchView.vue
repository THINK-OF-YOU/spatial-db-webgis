<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from "vue";
import { storeToRefs } from "pinia";
import { getColleges } from "../api/colleges";
import { getFilterMeta } from "../api/meta";
import { searchColleges } from "../api/search";
import { useSearchStore } from "../stores/useSearchStore";
import type { CollegeFilters } from "../types/college";
import type { FilterMeta } from "../types/meta";
import type {
  AdmissionSearchCondition,
  SearchRequest,
  SpatialSearchCondition,
} from "../types/search";
import CollegeDetailPanel from "../components/CollegeDetailPanel.vue";

type IntegratedRequest = Omit<SearchRequest, "page" | "page_size">;
type ActiveQuery =
  | { kind: "directory"; filters: CollegeFilters; summary: string }
  | { kind: "integrated"; request: IntegratedRequest; summary: string };

const emptyMeta: FilterMeta = {
  years: [],
  source_provinces: [],
  edu_levels: [],
  categories: [],
  batches: [],
};

const store = useSearchStore();
const {
  results,
  loading,
  warnings,
  selectedCollege,
  referencePoint,
  radiusKm,
  selectedRegions,
  drawnGeometry,
  campusStatus,
} = storeToRefs(store);

const draft = reactive({
  q: store.filters.q ?? "",
  edu_level: store.filters.edu_level ?? "",
  reg_province: store.filters.reg_province ?? "",
});
const admissionDraft = reactive<{
  source_province: string;
  year: number | "";
  category: string;
  batch: string;
}>({ source_province: "", year: "", category: "", batch: "" });

const filterMeta = ref<FilterMeta>(emptyMeta);
const metaWarnings = ref<string[]>([]);
const metaLoading = ref(false);
const metaError = ref("");
const page = ref(1);
const page_size = ref(20);
const total = ref(0);
const error = ref("");
const formError = ref("");
const modeNotice = ref("");
const hasLoaded = ref(false);
const list = ref<HTMLElement | null>(null);
const activeQuery = ref<ActiveQuery>({
  kind: "directory",
  filters: { ...store.filters },
  summary: "全部高校",
});

const pages = computed(() =>
  Math.max(1, Math.ceil(total.value / page_size.value)),
);
const hasAdmissionConditions = computed(() =>
  Boolean(
    admissionDraft.source_province ||
      admissionDraft.year ||
      admissionDraft.category ||
      admissionDraft.batch,
  ),
);
const hasSpatialConditions = computed(() =>
  Boolean(
    referencePoint.value ||
      drawnGeometry.value ||
      selectedRegions.value.length,
  ),
);
const hasComprehensiveConditions = computed(
  () => hasAdmissionConditions.value || hasSpatialConditions.value,
);
const hasDirectoryExclusiveConditions = computed(() =>
  Boolean(draft.q.trim() || draft.reg_province.trim()),
);
const comprehensiveConditionCount = computed(() => {
  let count = 0;
  if (admissionDraft.source_province) count += 1;
  if (admissionDraft.year) count += 1;
  if (admissionDraft.category) count += 1;
  if (admissionDraft.batch) count += 1;
  if (selectedRegions.value.length) count += 1;
  if (referencePoint.value) count += 1;
  if (drawnGeometry.value) count += 1;
  return count;
});
const incompatibleDraft = computed(
  () =>
    hasDirectoryExclusiveConditions.value && hasComprehensiveConditions.value,
);
const submitLabel = computed(() =>
  hasDirectoryExclusiveConditions.value || !hasComprehensiveConditions.value
    ? "查询高校目录"
    : "应用综合筛选",
);
const queryModeLabel = computed(() =>
  activeQuery.value.kind === "integrated" ? "综合查询" : "目录查询",
);
const applied = computed(() => activeQuery.value.summary);
const emptyHint = computed(() =>
  activeQuery.value.kind === "integrated"
    ? "当前招生与空间条件没有共同匹配的高校，可减少条件后重试。"
    : "试试更短的关键词，或取消层次、登记地区条件。",
);

let controller: AbortController | undefined;
let metaController: AbortController | undefined;
let requestedPage = 1;

function compactAdmission(): AdmissionSearchCondition | undefined {
  const condition: AdmissionSearchCondition = {};
  if (admissionDraft.source_province)
    condition.source_province = admissionDraft.source_province;
  if (admissionDraft.year) condition.year = admissionDraft.year;
  if (admissionDraft.category) condition.category = admissionDraft.category;
  if (admissionDraft.batch) condition.batch = admissionDraft.batch;
  return Object.keys(condition).length ? condition : undefined;
}

function compactSpatial(): SpatialSearchCondition | undefined {
  if (!referencePoint.value && !drawnGeometry.value) return undefined;
  const condition: SpatialSearchCondition = {
    include_candidate_campus: campusStatus.value,
  };
  if (referencePoint.value) {
    condition.reference_point = { ...referencePoint.value };
    if (radiusKm.value !== null) condition.radius_km = radiusKm.value;
  }
  if (drawnGeometry.value) condition.geometry = drawnGeometry.value;
  return condition;
}

function describeDirectory(filters: CollegeFilters) {
  const parts = [
    filters.q ? `名称：${filters.q}` : "",
    filters.edu_level ? `层次：${filters.edu_level}` : "",
    filters.reg_province ? `登记地区：${filters.reg_province}` : "",
  ].filter(Boolean);
  return parts.join(" / ") || "全部高校";
}

function describeIntegrated(request: IntegratedRequest) {
  const parts = [
    request.college?.edu_level ? `层次：${request.college.edu_level}` : "",
    request.admission?.source_province
      ? `生源省：${request.admission.source_province}`
      : "",
    request.admission?.year ? `年份：${request.admission.year}` : "",
    request.admission?.category ? `科类：${request.admission.category}` : "",
    request.admission?.batch ? `批次：${request.admission.batch}` : "",
    request.regions.length ? `目标行政区：${request.regions.length} 个` : "",
    request.spatial?.reference_point
      ? `参考点半径：${request.spatial.radius_km ?? "未设"} km`
      : "",
    request.spatial?.geometry ? "已绘制 Polygon" : "",
    request.spatial?.include_candidate_campus ? "包含候选校区" : "",
  ].filter(Boolean);
  return parts.join(" / ") || "全部高校";
}

function validateIntegratedDraft() {
  if (
    referencePoint.value &&
    (radiusKm.value === null ||
      radiusKm.value <= 0 ||
      radiusKm.value > 2000)
  ) {
    formError.value = "设置参考点后，请输入 0～2000 km 范围内的查询半径。";
    return false;
  }
  formError.value = "";
  return true;
}

async function load(nextPage = 1) {
  requestedPage = nextPage;
  controller?.abort();
  const current = new AbortController();
  controller = current;
  loading.value = true;
  error.value = "";
  results.value = [];
  warnings.value = [];
  hasLoaded.value = false;
  try {
    const query = activeQuery.value;
    const data =
      query.kind === "directory"
        ? await getColleges(
            {
              ...query.filters,
              page: nextPage,
              page_size: page_size.value,
            },
            current.signal,
          )
        : await searchColleges(
            {
              ...query.request,
              page: nextPage,
              page_size: page_size.value,
            },
            current.signal,
          );
    if (current.signal.aborted) return;
    results.value = data.items;
    warnings.value = [...new Set(data.warnings)];
    total.value = data.total;
    page.value = data.page;
    page_size.value = data.page_size;
    hasLoaded.value = true;
    list.value?.scrollTo({ top: 0 });
  } catch (cause) {
    if (!current.signal.aborted)
      error.value =
        cause instanceof Error ? cause.message : "查询失败，请重试。";
  } finally {
    if (controller === current) loading.value = false;
  }
}

function submitSearch() {
  formError.value = "";
  if (
    !hasDirectoryExclusiveConditions.value &&
    hasComprehensiveConditions.value &&
    !validateIntegratedDraft()
  )
    return;
  const directoryFilters: CollegeFilters = {
    q: draft.q.trim(),
    edu_level: draft.edu_level,
    reg_province: draft.reg_province.trim(),
  };
  store.filters = { ...directoryFilters };

  if (hasDirectoryExclusiveConditions.value) {
    activeQuery.value = {
      kind: "directory",
      filters: directoryFilters,
      summary: describeDirectory(directoryFilters),
    };
    modeNotice.value = hasComprehensiveConditions.value
      ? "高校名称和登记地区仅由高校目录接口支持。本次明确执行目录查询，招生与空间条件未被提交；清除名称和登记地区后可应用综合筛选。"
      : "当前使用高校目录查询；高校名称与登记地区均会参与筛选。";
  } else if (hasComprehensiveConditions.value) {
    const request: IntegratedRequest = {
      admission: compactAdmission(),
      college: draft.edu_level ? { edu_level: draft.edu_level } : undefined,
      regions: [...selectedRegions.value],
      spatial: compactSpatial(),
    };
    activeQuery.value = {
      kind: "integrated",
      request,
      summary: describeIntegrated(request),
    };
    modeNotice.value =
      "招生与空间条件已合并为一次综合查询，列表与地图共享同一份结果。";
  } else {
    activeQuery.value = {
      kind: "directory",
      filters: directoryFilters,
      summary: describeDirectory(directoryFilters),
    };
    modeNotice.value = "当前使用高校目录查询。";
  }
  void load(1);
}

function clearAll() {
  Object.assign(draft, { q: "", edu_level: "", reg_province: "" });
  Object.assign(admissionDraft, {
    source_province: "",
    year: "",
    category: "",
    batch: "",
  });
  store.clearSpatialFilters();
  campusStatus.value = false;
  formError.value = "";
  modeNotice.value = "";
  submitSearch();
}

function onRadiusInput(event: Event) {
  const value = (event.target as HTMLInputElement).value;
  store.setRadiusKm(value === "" ? null : Number(value));
}

async function loadMeta() {
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
    if (!current.signal.aborted)
      metaError.value =
        cause instanceof Error ? cause.message : "筛选项加载失败。";
  } finally {
    if (metaController === current) metaLoading.value = false;
  }
}

onBeforeUnmount(() => {
  controller?.abort();
  metaController?.abort();
  loading.value = false;
});
void loadMeta();
void load();
</script>

<template>
  <div class="search-page">
    <header class="top-bar">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">学</span>
        <div>
          <h1>高校空间查询</h1>
          <p>招生条件与空间范围，一次完成筛选</p>
        </div>
      </div>
      <div class="top-meta">
        <span>全国高校 · 综合查询</span><span class="version">V1</span>
      </div>
    </header>
    <main class="workspace">
      <section class="directory" aria-label="高校查询">
        <div class="directory-intro">
          <span class="eyebrow">COLLEGE EXPLORER</span>
          <h2>寻找你的下一站</h2>
          <p>目录条件与招生、空间条件按真实接口协同查询。</p>
        </div>
        <form class="search-form" @submit.prevent="submitSearch">
          <div class="filter-section">
            <div class="filter-section-title">
              <strong>高校条件</strong><span>目录与综合查询共用办学层次</span>
            </div>
            <label for="college-query">高校名称</label>
            <input
              id="college-query"
              v-model="draft.q"
              type="search"
              placeholder="输入高校名称或关键词"
              autocomplete="off"
            />
            <div class="filter-row">
              <div>
                <label for="edu-level">办学层次</label>
                <select id="edu-level" v-model="draft.edu_level">
                  <option value="">全部层次</option>
                  <option
                    v-for="level in filterMeta.edu_levels"
                    :key="level"
                    :value="level"
                  >
                    {{ level }}
                  </option>
                </select>
              </div>
              <div>
                <label for="region">登记地区</label>
                <input
                  id="region"
                  v-model="draft.reg_province"
                  placeholder="如：武汉市"
                  aria-describedby="region-hint"
                />
              </div>
            </div>
            <p id="region-hint" class="field-hint">
              登记地区按原始名称精确匹配，与地图目标行政区不同。
            </p>
          </div>

          <details class="integrated-filters">
            <summary>
              <span>招生与空间条件</span>
              <span v-if="comprehensiveConditionCount" class="condition-count">
                {{ comprehensiveConditionCount }} 项
              </span>
              <span v-else class="summary-hint">按需展开</span>
            </summary>
            <div class="integrated-filter-body">
              <div class="filter-section-title">
                <strong>招生条件</strong><span>筛选符合历史投档条件的高校</span>
              </div>
              <div class="filter-grid">
                <div>
                  <label for="source-province">生源省</label>
                  <select
                    id="source-province"
                    v-model="admissionDraft.source_province"
                    :disabled="metaLoading"
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
                </div>
                <div>
                  <label for="admission-year">年份</label>
                  <select
                    id="admission-year"
                    v-model.number="admissionDraft.year"
                    :disabled="metaLoading"
                  >
                    <option value="">全部年份</option>
                    <option
                      v-for="year in filterMeta.years"
                      :key="year"
                      :value="year"
                    >
                      {{ year }}
                    </option>
                  </select>
                </div>
                <div>
                  <label for="admission-category">科类</label>
                  <select
                    id="admission-category"
                    v-model="admissionDraft.category"
                    :disabled="metaLoading"
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
                </div>
                <div>
                  <label for="admission-batch">批次</label>
                  <select
                    id="admission-batch"
                    v-model="admissionDraft.batch"
                    :disabled="metaLoading"
                  >
                    <option value="">全部批次</option>
                    <option
                      v-for="batch in filterMeta.batches"
                      :key="batch"
                      :value="batch"
                    >
                      {{ batch }}
                    </option>
                  </select>
                </div>
              </div>
              <p v-if="metaLoading" class="field-hint">正在加载真实筛选项…</p>
              <p v-else-if="metaError" class="inline-error">
                {{ metaError }}
                <button type="button" @click="loadMeta">重试</button>
              </p>
              <p
                v-for="warning in metaWarnings"
                :key="warning"
                class="field-hint"
              >
                {{ warning }}
              </p>

              <div class="filter-section-title spatial-title">
                <strong>空间条件</strong><span>在地图上选区、选点或绘制</span>
              </div>
              <div class="spatial-summary">
                <span :class="{ active: selectedRegions.length }">
                  行政区 {{ selectedRegions.length ? `${selectedRegions.length} 个` : "未选" }}
                </span>
                <span :class="{ active: referencePoint }">
                  参考点 {{ referencePoint ? "已设置" : "未设置" }}
                </span>
                <span :class="{ active: drawnGeometry }">
                  Polygon {{ drawnGeometry ? "已绘制" : "未绘制" }}
                </span>
              </div>
              <div class="radius-control">
                <label for="radius-km">参考点半径（km）</label>
                <input
                  id="radius-km"
                  type="number"
                  min="0.1"
                  max="2000"
                  step="10"
                  :value="radiusKm ?? ''"
                  :disabled="!referencePoint"
                  placeholder="先在地图设置参考点"
                  @input="onRadiusInput"
                />
              </div>
              <label class="candidate-toggle">
                <input v-model="campusStatus" type="checkbox" />
                <span>
                  <strong>允许候选校区参与空间查询</strong>
                  <small>候选校区点尚未完成实体级人工核验</small>
                </span>
              </label>
            </div>
          </details>

          <p v-if="incompatibleDraft" class="compatibility-note">
            名称或登记地区存在时，将明确执行目录查询；招生与空间条件不会被静默提交或丢弃。
          </p>
          <p v-if="formError" class="inline-error" role="alert">
            {{ formError }}
          </p>
          <p v-if="modeNotice" class="query-notice">{{ modeNotice }}</p>
          <div class="form-actions">
            <button class="primary" type="submit" :disabled="loading">
              {{ submitLabel }} <span aria-hidden="true">→</span>
            </button>
            <button type="button" class="quiet" :disabled="loading" @click="clearAll">
              清除全部
            </button>
          </div>
        </form>
        <div class="results-heading">
          <div>
            <h3>
              高校结果
              <span v-if="hasLoaded">{{ total.toLocaleString() }}</span>
              <em>{{ queryModeLabel }}</em>
            </h3>
            <p :title="applied">{{ applied }}</p>
          </div>
          <label class="page-size">
            每页
            <select
              v-model.number="page_size"
              aria-label="每页条数"
              :disabled="loading"
              @change="load(1)"
            >
              <option :value="20">20</option>
              <option :value="50">50</option>
            </select>
          </label>
        </div>
        <div ref="list" class="college-list" :aria-busy="loading">
          <p v-for="warning in warnings" :key="warning" class="business-warning">
            {{ warning }}
          </p>
          <div v-if="loading" class="state-message" role="status">
            <span class="loading-ring" />正在查找高校…
          </div>
          <div v-else-if="error" class="state-message error" role="alert">
            <h3>暂时未能获取高校</h3>
            <p>{{ error }}</p>
            <button class="secondary" @click="load(requestedPage)">
              重新加载
            </button>
          </div>
          <div v-else-if="!results.length" class="state-message" role="status">
            <h3>没有找到匹配的高校</h3>
            <p>{{ emptyHint }}</p>
            <button class="secondary" @click="clearAll">清除全部条件</button>
          </div>
          <template v-else>
            <button
              v-for="college in results"
              :key="college.school_id"
              class="college-card"
              :class="{
                selected: selectedCollege?.school_id === college.school_id,
              }"
              :aria-pressed="selectedCollege?.school_id === college.school_id"
              @click="store.setSelectedCollege(college)"
            >
              <span class="college-card-top">
                <span class="college-monogram" aria-hidden="true">{{
                  college.name.slice(0, 1)
                }}</span>
                <span class="college-identity">
                  <strong>{{ college.name }}</strong>
                  <span>
                    {{ college.reg_province || "登记地区未提供" }}<i>·</i>{{
                      college.edu_level || "层次未提供"
                    }}
                  </span>
                </span>
                <span class="card-arrow" aria-hidden="true">↗</span>
              </span>
              <span class="college-card-bottom">
                <span>院校代码 {{ college.national_code || "未提供" }}</span>
                <span v-if="college.distance_km != null" class="distance-value">
                  {{ college.distance_km.toFixed(2) }} km
                </span>
                <span :class="college.has_campus ? 'campus-available' : 'muted'">
                  {{ college.has_campus ? "有校区数据" : "暂无可信校区数据" }}
                </span>
              </span>
            </button>
          </template>
        </div>
        <nav class="pagination" aria-label="高校列表分页">
          <button
            :disabled="loading || !!error || page <= 1"
            aria-label="上一页"
            @click="load(page - 1)"
          >
            ←
          </button>
          <span>{{ hasLoaded ? `${page} / ${pages} 页` : "—" }}</span>
          <button
            :disabled="loading || !!error || !hasLoaded || page >= pages"
            aria-label="下一页"
            @click="load(page + 1)"
          >
            →
          </button>
        </nav>
      </section>
      <section class="map-panel" aria-label="高校空间分布">
        <div class="map-heading">
          <div>
            <span class="eyebrow">SPATIAL VIEW</span>
            <h2>在地图上组合空间条件</h2>
          </div>
          <span class="map-caption">WGS84 · 校区空间分布</span>
        </div>
        <div class="map-host"><slot name="map" /></div>
        <div class="map-footnote">
          <span>地图展示有坐标的校区；没有校区数据的高校仍可参与非空间查询。</span>
          <span v-if="hasSpatialConditions" class="spatial-note">
            {{
              hasDirectoryExclusiveConditions
                ? "空间条件已记录；清除名称和登记地区后可应用综合筛选"
                : "空间条件已记录，点击“应用综合筛选”后提交后端"
            }}
          </span>
          <span v-else>点击校区点查看高校详情</span>
        </div>
        <CollegeDetailPanel />
      </section>
    </main>
  </div>
</template>
