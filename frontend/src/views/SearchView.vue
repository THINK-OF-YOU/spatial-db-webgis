<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { getColleges } from "../api/colleges";
import {
  getCandidateProfileContexts,
  getFilterMeta,
  getScoreRangeContexts,
  resolveScoreRank,
} from "../api/meta";
import { searchColleges } from "../api/search";
import { useSearchStore } from "../stores/useSearchStore";
import {
  getCollegeTierGroup,
  getCollegeTierLabels,
  type CollegeTierGroup,
} from "../data/collegeTiers";
import type { CollegeFilters } from "../types/college";
import type {
  CandidateProfileContext,
  FilterMeta,
  ScoreRangeContext,
} from "../types/meta";
import type {
  AdmissionSearchCondition,
  CompareAdmissionContext,
  SearchRequest,
  SearchResult,
  SpatialSearchCondition,
  TransportSearchCondition,
  TransportSearchMode,
} from "../types/search";
import CollegeDetailPanel from "../components/CollegeDetailPanel.vue";
import CompareTray from "../components/CompareTray.vue";
import CollegeCompareDialog from "../components/CollegeCompareDialog.vue";

type IntegratedRequest = Omit<SearchRequest, "page" | "page_size">;
type ActiveQuery =
  | { kind: "directory"; filters: CollegeFilters; summary: string }
  | { kind: "integrated"; request: IntegratedRequest; summary: string };
type QueryGroupKey = "college" | "candidate" | "spatial" | "transport";

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
  compareColleges,
  referencePoint,
  radiusKm,
  selectedRegions,
  drawnGeometry,
  campusStatus,
  hasSearched,
  viewportCampuses,
  candidateProfile,
  candidateProfileEnabled,
  candidateEffectiveRank,
  rankWindow,
} = storeToRefs(store);

const draft = reactive({
  q: store.filters.q ?? "",
  edu_level: store.filters.edu_level ?? "",
  reg_province: store.filters.reg_province ?? "",
});
const filterMeta = ref<FilterMeta>(emptyMeta);
const metaWarnings = ref<string[]>([]);
const metaLoading = ref(false);
const metaError = ref("");
const candidateContexts = ref<CandidateProfileContext[]>([]);
const candidateContextWarnings = ref<string[]>([]);
const candidateContextLoading = ref(false);
const candidateContextError = ref("");
const scoreRangeContexts = ref<ScoreRangeContext[]>([]);
const scoreMetadataLoading = ref(false);
const scoreMetadataError = ref("");
const scoreResolveError = ref("");
const page = ref(1);
const page_size = ref(20);
const total = ref(0);
const error = ref("");
const formError = ref("");
const modeNotice = ref("");
const compareNotice = ref("");
const compareDialogOpen = ref(false);
const hasLoaded = ref(false);
const sidebarCollapsed = ref(false);
const hasSubmittedSearch = ref(false);
const queryGroups = reactive<Record<QueryGroupKey, boolean>>({
  college: true,
  candidate: true,
  spatial: true,
  transport: false,
});
const directoryContent = ref<HTMLElement | null>(null);
const activeQuery = ref<ActiveQuery>({
  kind: "directory",
  filters: { ...store.filters },
  summary: "全部高校",
});

const TRANSPORT_MODE_LABELS: Record<TransportSearchMode, string> = {
  metro: "地铁",
  rail: "铁路站",
  airport: "机场",
};
const TRANSPORT_DISTANCE_OPTIONS: Record<TransportSearchMode, number[]> = {
  metro: [1, 2, 3],
  rail: [3, 5, 10],
  airport: [20, 30, 50],
};
const TRANSPORT_DEFAULT_DISTANCE: Record<TransportSearchMode, number> = {
  metro: 2,
  rail: 5,
  airport: 30,
};
const TRANSPORT_MODES: TransportSearchMode[] = ["metro", "rail", "airport"];
interface TransportDraftCondition {
  enabled: boolean;
  max_distance_km: number;
}
const transportEnabled = ref(false);
const transportConditions = reactive<Record<TransportSearchMode, TransportDraftCondition>>({
  metro: { enabled: false, max_distance_km: TRANSPORT_DEFAULT_DISTANCE.metro },
  rail: { enabled: false, max_distance_km: TRANSPORT_DEFAULT_DISTANCE.rail },
  airport: { enabled: false, max_distance_km: TRANSPORT_DEFAULT_DISTANCE.airport },
});
const selectedTransportModes = computed(() =>
  TRANSPORT_MODES.filter((mode) => transportConditions[mode].enabled),
);

const viewportSchoolIds = computed(
  () => new Set(viewportCampuses.value.map((campus) => campus.properties.school_id)),
);
const viewportColleges = computed<SearchResult[]>(() => {
  const colleges = new Map<number, SearchResult>();
  for (const campus of viewportCampuses.value) {
    const { school_id, school_name } = campus.properties;
    if (colleges.has(school_id)) continue;
    colleges.set(school_id, {
      school_id,
      national_code: null,
      name: school_name,
      edu_level: null,
      reg_province: null,
      has_campus: true,
    });
  }
  return [...colleges.values()];
});
const hasAppliedDirectoryFilters = computed(() => {
  const query = activeQuery.value;
  if (query.kind !== "directory") return false;
  return Boolean(query.filters.q || query.filters.edu_level || query.filters.reg_province);
});
const usesBusinessResults = computed(() =>
  activeQuery.value.kind === "integrated"
    ? hasSearched.value
    : hasAppliedDirectoryFilters.value,
);
const isPureViewportMode = computed(
  () => activeQuery.value.kind === "directory" && !hasAppliedDirectoryFilters.value,
);
const displayedColleges = computed<SearchResult[]>(() => {
  if (isPureViewportMode.value) return viewportColleges.value;
  if (!usesBusinessResults.value) return [];
  return results.value.filter((college) => viewportSchoolIds.value.has(college.school_id));
});

const GROUP_ORDER: { key: CollegeTierGroup; label: string }[] = [
  { key: "985", label: "985 高校" },
  { key: "211", label: "211 高校" },
  { key: "double-first-class", label: "双一流高校" },
  { key: "other", label: "其他高校" },
];

const groupedColleges = computed(() =>
  GROUP_ORDER.map((group) => ({
    ...group,
    colleges: displayedColleges.value
      .filter((college) => getCollegeTierGroup(college.school_id) === group.key)
      .sort((left, right) => {
        const leftGap = Math.abs(left.reference_admission?.rank_gap ?? Number.POSITIVE_INFINITY);
        const rightGap = Math.abs(right.reference_admission?.rank_gap ?? Number.POSITIVE_INFINITY);
        return leftGap - rightGap || left.school_id - right.school_id;
      }),
  })),
);
const visibleCollegeGroups = computed(() =>
  groupedColleges.value.filter((group) => group.colleges.length),
);
const expandedGroups = ref<Record<CollegeTierGroup, boolean>>({
  "985": false,
  "211": false,
  "double-first-class": false,
  other: false,
});
let lastGroupSignature = "";

watch(
  visibleCollegeGroups,
  (groups) => {
    const signature = groups
      .map((group) => `${group.key}:${group.colleges.map((college) => college.school_id).join(",")}`)
      .join("|");
    if (signature === lastGroupSignature) return;
    lastGroupSignature = signature;
    const first = groups[0]?.key;
    expandedGroups.value = {
      "985": first === "985",
      "211": first === "211",
      "double-first-class": first === "double-first-class",
      other: first === "other",
    };
  },
  { immediate: true },
);

watch(selectedCollege, (college) => {
  if (!college) return;
  if (
    candidateProfileEnabled.value &&
    hasSearched.value &&
    !results.value.some((item) => item.school_id === college.school_id)
  ) {
    store.setSelectedCollege(null);
    return;
  }
  const group = getCollegeTierGroup(college.school_id);
  if (visibleCollegeGroups.value.some((item) => item.key === group)) {
    expandedGroups.value[group] = true;
  }
});

watch(
  () => [
    candidateProfileEnabled.value,
    candidateProfile.value.source_province,
    candidateProfile.value.year,
    candidateProfile.value.category,
    candidateProfile.value.batch,
    candidateProfile.value.input_mode,
    candidateProfile.value.rank,
    candidateProfile.value.score,
    candidateProfile.value.resolved_rank,
    candidateProfile.value.resolution_status,
  ],
  (current, previous) => {
    if (!previous || current.every((value, index) => value === previous[index])) return;
    // 画像变化时关闭仍绑定旧查询上下文的详情，避免学校结果和专业事实串线。
    if (selectedCollege.value) store.setSelectedCollege(null);
    controller?.abort();
    loading.value = false;
    store.setHasSearched(false);
    results.value = [];
    warnings.value = [];
    total.value = 0;
    hasLoaded.value = false;
  },
);

function toggleGroup(group: CollegeTierGroup) {
  expandedGroups.value[group] = !expandedGroups.value[group];
}

function syncQueryGroup(group: QueryGroupKey, event: Event) {
  queryGroups[group] = (event.currentTarget as HTMLDetailsElement).open;
}

function collapseQueryGroups() {
  for (const group of Object.keys(queryGroups) as QueryGroupKey[]) {
    queryGroups[group] = false;
  }
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
}

const pages = computed(() =>
  Math.max(1, Math.ceil(total.value / page_size.value)),
);
const hasAdmissionConditions = computed(() =>
  Boolean(
    candidateProfile.value.source_province ||
      candidateProfile.value.year ||
      candidateProfile.value.category ||
      candidateProfile.value.batch ||
      candidateProfileEnabled.value,
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
  () =>
    hasAdmissionConditions.value ||
    hasSpatialConditions.value ||
    transportEnabled.value,
);
const hasDirectoryExclusiveConditions = computed(() =>
  Boolean(draft.q.trim() || draft.reg_province.trim()),
);
const comprehensiveConditionCount = computed(() => {
  let count = 0;
  if (candidateProfile.value.source_province) count += 1;
  if (candidateProfile.value.year) count += 1;
  if (candidateProfile.value.category) count += 1;
  if (candidateProfile.value.batch) count += 1;
  if (candidateProfileEnabled.value && candidateEffectiveRank.value) count += 1;
  if (selectedRegions.value.length) count += 1;
  if (referencePoint.value) count += 1;
  if (drawnGeometry.value) count += 1;
  if (transportEnabled.value) count += 1;
  return count;
});
const directoryConditionCount = computed(
  () => [draft.q.trim(), draft.edu_level, draft.reg_province.trim()].filter(Boolean).length,
);
const candidateGroupSummary = computed(() => {
  const profile = candidateProfile.value;
  const parts = [profile.source_province, profile.year, profile.category, profile.batch].filter(
    (value) => value !== "" && value !== null && value !== undefined,
  );
  if (candidateProfileEnabled.value && candidateEffectiveRank.value !== null) {
    parts.push(`位次 ${candidateEffectiveRank.value.toLocaleString("zh-CN")}`);
  }
  return parts.length ? parts.join(" · ") : "未设置";
});
const spatialGroupSummary = computed(() => {
  const count =
    selectedRegions.value.length +
    (referencePoint.value ? 1 : 0) +
    (drawnGeometry.value ? 1 : 0) +
    (campusStatus.value ? 1 : 0);
  return count ? `${count} 项已设置` : "未设置";
});
const transportGroupSummary = computed(() => {
  if (!transportEnabled.value) return "未启用";
  return selectedTransportModes.value.length
    ? `${selectedTransportModes.value.length} 项 AND 条件`
    : "已启用，待选择";
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
  isPureViewportMode.value
    ? "地图视野"
    : activeQuery.value.kind === "integrated"
      ? "综合查询"
      : "目录查询",
);
const compareAdmissionContext = computed<CompareAdmissionContext | null>(() => {
  if (activeQuery.value.kind !== "integrated") return null;
  const admission = activeQuery.value.request.admission;
  if (
    !admission?.source_province ||
    admission.year === undefined ||
    !admission.category ||
    admission.rank === undefined
  )
    return null;
  return {
    source_province: admission.source_province,
    year: admission.year,
    category: admission.category,
    batch: admission.batch ?? null,
    candidate_rank: admission.rank,
  };
});
const applied = computed(() => activeQuery.value.summary);
const emptyHint = computed(() =>
  isPureViewportMode.value
    ? "当前地图视野内暂无 Campus，可平移或缩放地图后重试。"
    : activeQuery.value.kind === "integrated"
    ? activeQuery.value.request.admission?.rank != null
      ? "当前历史位次参考范围和空间条件下暂无高校结果，可尝试扩大位次参考范围或调整空间条件。"
      : "当前招生与空间条件没有共同匹配的高校，可减少条件后重试。"
    : "试试更短的关键词，或取消层次、登记地区条件。",
);
const listDescription = computed(() => {
  if (isPureViewportMode.value) return "列表随地图视野稳定后更新";
  const queryTotal = hasLoaded.value ? ` · 查询共 ${total.value.toLocaleString()} 所` : "";
  return `${applied.value}${queryTotal}`;
});
const rankLower = computed(() => {
  const rank = candidateEffectiveRank.value;
  return rank === null ? null : Math.max(1, rank - rankWindow.value.ahead);
});
const rankUpper = computed(() => {
  const rank = candidateEffectiveRank.value;
  return rank === null ? null : rank + rankWindow.value.behind;
});
const activeScoreRangeContext = computed(() => {
  const { source_province, year, category } = candidateProfile.value;
  if (!source_province || year === null || !category) return null;
  return (
    scoreRangeContexts.value.find(
      (context) =>
        context.source_province === source_province &&
        context.year === year &&
        context.category === category,
    ) ?? null
  );
});
const scoreModeAvailable = computed(
  () => (activeScoreRangeContext.value?.valid_score_count ?? 0) > 0,
);
const scoreResolutionMessage = computed(() => {
  const profile = candidateProfile.value;
  const status = profile.resolution_status;
  if (status === "loading") return "正在按一分一段数据解析参考位次…";
  if (status === "resolved" && profile.resolved_rank !== null) {
    return `按 ${profile.source_province} / ${profile.year} / ${profile.category} / ${profile.score} 分的一分一段累计人数，参考位次约 ${profile.resolved_rank.toLocaleString("zh-CN")}。`;
  }
  if (status === "ambiguous")
    return "同一分数存在多个不同累计人数，无法安全确定参考位次，请改填位次。";
  if (status === "not_found")
    return "当前上下文没有该精确分数的一分一段记录，不会使用邻近分数估算。";
  if (status === "unsupported_context")
    return "当前考试上下文缺少可用于分数换算的可靠一分一段数据，请直接填写位次。";
  if (status === "error") return "分数解析暂时失败，可以重试或切换到位次模式。";
  return "";
});
const candidateSourceProvinceOptions = computed(() =>
  [...new Set(candidateContexts.value.map((context) => context.source_province))]
    .sort((left, right) => left.localeCompare(right, "zh-CN")),
);
const candidateYearOptions = computed(() => {
  const province = candidateProfile.value.source_province;
  if (!province) return [];
  return [
    ...new Set(
      candidateContexts.value
        .filter((context) => context.source_province === province)
        .map((context) => context.year),
    ),
  ].sort((left, right) => right - left);
});
const candidateCategoryOptions = computed(() => {
  const { source_province, year } = candidateProfile.value;
  if (!source_province || year === null) return [];
  return [
    ...new Set(
      candidateContexts.value
        .filter(
          (context) =>
            context.source_province === source_province && context.year === year,
        )
        .map((context) => context.category),
    ),
  ].sort((left, right) => left.localeCompare(right, "zh-CN"));
});
const candidateBatchOptions = computed(() => {
  const { source_province, year, category } = candidateProfile.value;
  if (!source_province || year === null || !category) return [];
  return [
    ...new Set(
      candidateContexts.value
        .filter(
          (context) =>
            context.source_province === source_province &&
            context.year === year &&
            context.category === category &&
            context.batch !== null &&
            context.batch !== "",
        )
        .map((context) => context.batch as string),
    ),
  ].sort((left, right) => left.localeCompare(right, "zh-CN"));
});
const combinedMetaWarnings = computed(() =>
  [...new Set([...metaWarnings.value, ...candidateContextWarnings.value])],
);

let controller: AbortController | undefined;
let metaController: AbortController | undefined;
let candidateContextController: AbortController | undefined;
let scoreMetadataController: AbortController | undefined;
let scoreResolverController: AbortController | undefined;
let requestedPage = 1;

function autoSelectCandidateCategory() {
  if (candidateCategoryOptions.value.length === 1) {
    store.setCandidateCategory(candidateCategoryOptions.value[0]);
  }
}

function autoSelectCandidateYear() {
  if (candidateYearOptions.value.length === 1) {
    store.setCandidateYear(candidateYearOptions.value[0]);
    autoSelectCandidateCategory();
  }
}

function reconcileCandidateProfile() {
  const profile = candidateProfile.value;
  if (!profile.source_province) {
    if (profile.year !== null || profile.category || profile.batch) {
      store.setCandidateSourceProvince("");
    }
    return;
  }
  if (!candidateSourceProvinceOptions.value.includes(profile.source_province)) {
    store.setCandidateSourceProvince("");
    return;
  }
  if (profile.year === null) {
    autoSelectCandidateYear();
    return;
  }
  if (!candidateYearOptions.value.includes(profile.year)) {
    store.setCandidateYear(null);
    autoSelectCandidateYear();
    return;
  }
  if (!profile.category) {
    autoSelectCandidateCategory();
    return;
  }
  if (!candidateCategoryOptions.value.includes(profile.category)) {
    store.setCandidateCategory("");
    autoSelectCandidateCategory();
    return;
  }
  if (profile.batch && !candidateBatchOptions.value.includes(profile.batch)) {
    store.setCandidateBatch("");
  }
}

function isCandidateContextSelectionValid() {
  const profile = candidateProfile.value;
  if (!profile.source_province) {
    return profile.year === null && !profile.category && !profile.batch;
  }
  if (!candidateSourceProvinceOptions.value.includes(profile.source_province)) return false;
  if (profile.year === null) return !profile.category && !profile.batch;
  if (!candidateYearOptions.value.includes(profile.year)) return false;
  if (!profile.category) return !profile.batch;
  if (!candidateCategoryOptions.value.includes(profile.category)) return false;
  return !profile.batch || candidateBatchOptions.value.includes(profile.batch);
}

function compactAdmission(): AdmissionSearchCondition | undefined {
  const condition: AdmissionSearchCondition = {};
  const profile = candidateProfile.value;
  if (profile.source_province) condition.source_province = profile.source_province;
  if (profile.year !== null) condition.year = profile.year;
  if (profile.category) condition.category = profile.category;
  if (profile.batch) condition.batch = profile.batch;
  if (candidateProfileEnabled.value && candidateEffectiveRank.value !== null) {
    condition.rank = candidateEffectiveRank.value;
    condition.rank_ahead = rankWindow.value.ahead;
    condition.rank_behind = rankWindow.value.behind;
  }
  return Object.keys(condition).length ? condition : undefined;
}

function compactSpatial(): SpatialSearchCondition | undefined {
  if (
    !referencePoint.value &&
    !drawnGeometry.value &&
    !selectedRegions.value.length
  )
    return undefined;
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

function compactTransport(): TransportSearchCondition[] | undefined {
  if (!transportEnabled.value) return undefined;
  const conditions = selectedTransportModes.value.map((mode) => ({
    mode,
    max_distance_km: transportConditions[mode].max_distance_km,
  }));
  return conditions.length ? conditions : undefined;
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
    request.admission?.rank
      ? candidateProfile.value.input_mode === "score"
        ? `分数解析参考位次：${request.admission.rank}`
        : `考生位次：${request.admission.rank}`
      : "",
    request.admission?.rank
      ? `历史位次：${Math.max(
          1,
          request.admission.rank - (request.admission.rank_ahead ?? 3000),
        )}～${request.admission.rank + (request.admission.rank_behind ?? 8000)}`
      : "",
    request.regions.length ? `目标行政区：${request.regions.length} 个` : "",
    request.spatial?.reference_point
      ? `参考点半径：${request.spatial.radius_km ?? "未设"} km`
      : "",
    request.spatial?.geometry ? "已绘制 Polygon" : "",
    request.spatial?.include_candidate_campus ? "包含参考校区点" : "",
    request.transport?.length
      ? `交通：${request.transport
          .map((condition) => `${TRANSPORT_MODE_LABELS[condition.mode]} ≤ ${condition.max_distance_km} km`)
          .join(" + ")}`
      : "",
  ].filter(Boolean);
  return parts.join(" / ") || "全部高校";
}

function isCompared(schoolId: number) {
  return compareColleges.value.some((college) => college.school_id === schoolId);
}

function toggleCompare(college: SearchResult) {
  const result = store.toggleCompareCollege(college);
  if (result === "added") {
    compareNotice.value = "已加入比较栏；翻页或打开详情不会丢失该快照。";
  } else if (result === "removed") {
    compareNotice.value = "已从比较栏移除。";
  } else if (result === "limit") {
    compareNotice.value = "最多同时比较 4 所高校，请先移除一所再加入。";
  }
}

function removeCompare(schoolId: number) {
  store.removeCompareCollege(schoolId);
  compareNotice.value = "已从比较栏移除。";
  if (compareColleges.value.length < 2) compareDialogOpen.value = false;
}

function clearCompare() {
  store.clearCompareColleges();
  compareNotice.value = "比较栏已清空。";
  compareDialogOpen.value = false;
}

function openCompare() {
  if (compareColleges.value.length < 2) {
    compareNotice.value = "至少选择 2 所高校后才能开始比较。";
    return;
  }
  compareNotice.value = "";
  compareDialogOpen.value = true;
}

function validateIntegratedDraft() {
  if (hasAdmissionConditions.value) {
    if (candidateContextLoading.value) {
      formError.value = "可用考试上下文仍在加载，请稍后再试。";
      return false;
    }
    if (candidateContextError.value || !candidateContexts.value.length) {
      formError.value = "考试上下文暂时无法加载，请重试后再提交。";
      return false;
    }
    if (!isCandidateContextSelectionValid()) {
      formError.value = "当前考试上下文已不可用，请按生源省、年份、科类顺序重新选择。";
      return false;
    }
  }
  if (candidateProfileEnabled.value) {
    const profile = candidateProfile.value;
    if (!profile.source_province || profile.year === null || !profile.category) {
      formError.value = "启用位次画像后，生源省、年份和科类均为必填。";
      return false;
    }
    if (profile.input_mode === "rank") {
      if (profile.rank === null || !Number.isInteger(profile.rank) || profile.rank <= 0) {
        formError.value = "考生位次必须是大于 0 的整数。";
        return false;
      }
    } else {
      if (scoreMetadataLoading.value) {
        formError.value = "分数数据上下文仍在加载，请稍后再试。";
        return false;
      }
      if (scoreMetadataError.value || !scoreModeAvailable.value) {
        formError.value =
          "当前考试上下文缺少可用于分数换算的可靠一分一段数据，请直接填写位次。";
        return false;
      }
      if (profile.score === null || !Number.isInteger(profile.score) || profile.score < 0) {
        formError.value = "考生分数必须是大于或等于 0 的整数。";
        return false;
      }
      if (
        profile.resolution_status !== "resolved" ||
        profile.resolved_rank === null ||
        !Number.isInteger(profile.resolved_rank) ||
        profile.resolved_rank <= 0
      ) {
        formError.value = "当前分数尚未得到可靠参考位次，请先解析或改填位次。";
        return false;
      }
    }
    if (
      !Number.isInteger(rankWindow.value.ahead) ||
      rankWindow.value.ahead < 0 ||
      !Number.isInteger(rankWindow.value.behind) ||
      rankWindow.value.behind < 0
    ) {
      formError.value = "向前、向后位次范围必须是大于或等于 0 的整数。";
      return false;
    }
  }
  const radius = radiusKm.value;
  if (
    referencePoint.value &&
    (radius === null ||
      !Number.isInteger(radius) ||
      radius < 10 ||
      radius > 2000 ||
      radius % 10 !== 0)
  ) {
    formError.value = "设置参考点后，请输入 10～2000 km 且为 10 的倍数。";
    return false;
  }
  if (transportEnabled.value) {
    if (!selectedTransportModes.value.length) {
      formError.value = "请至少选择一种交通设施，或关闭交通筛选。";
      return false;
    }
    const invalidMode = selectedTransportModes.value.find(
      (mode) =>
        !TRANSPORT_DISTANCE_OPTIONS[mode].includes(
          transportConditions[mode].max_distance_km,
        ),
    );
    if (invalidMode) {
      formError.value = `请选择${TRANSPORT_MODE_LABELS[invalidMode]}提供的有效最大距离。`;
      return false;
    }
  }
  formError.value = "";
  return true;
}

function displayWarning(warning: string) {
  return warning === "本次空间查询包含候选校区"
    ? "本次空间查询使用了尚未完成最终人工核验的参考校区点"
    : warning;
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
    store.setHasSearched(query.kind === "integrated");
    if (hasSubmittedSearch.value) collapseQueryGroups();
    directoryContent.value?.scrollTo({ top: 0, behavior: "auto" });
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
  // 一次真正的新业务查询建立新的上下文；翻页走 load()，不会触发这里。
  store.clearCompareColleges();
  hasSubmittedSearch.value = true;
  compareNotice.value = "";
  compareDialogOpen.value = false;
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
      transport: compactTransport(),
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
  store.resetCandidateProfile();
  store.clearSpatialFilters();
  campusStatus.value = false;
  transportEnabled.value = false;
  for (const mode of TRANSPORT_MODES) {
    transportConditions[mode].enabled = false;
    transportConditions[mode].max_distance_km = TRANSPORT_DEFAULT_DISTANCE[mode];
  }
  formError.value = "";
  modeNotice.value = "";
  submitSearch();
}

function onRadiusInput(event: Event) {
  const value = (event.target as HTMLInputElement).value;
  store.setRadiusKm(value === "" ? null : Number(value));
}

function setTransportEnabled(enabled: boolean) {
  transportEnabled.value = enabled;
  if (enabled && !selectedTransportModes.value.length) {
    transportConditions.metro.enabled = true;
  }
  if (!enabled) {
    for (const mode of TRANSPORT_MODES) transportConditions[mode].enabled = false;
  }
}

function toggleTransportMode(mode: TransportSearchMode) {
  transportConditions[mode].enabled = !transportConditions[mode].enabled;
  if (transportConditions[mode].enabled) {
    transportEnabled.value = true;
  } else if (!selectedTransportModes.value.length) {
    transportEnabled.value = false;
  }
}

function setTransportDistance(mode: TransportSearchMode, distance: number) {
  transportConditions[mode].max_distance_km = distance;
}

function onRankInput(event: Event) {
  const value = (event.target as HTMLInputElement).value;
  candidateProfile.value.rank = value === "" ? null : Number(value);
}

function onCandidateInputModeChange(event: Event) {
  store.setCandidateInputMode(
    (event.target as HTMLInputElement).value as "rank" | "score",
  );
  formError.value = "";
}

function onScoreInput(event: Event) {
  scoreResolverController?.abort();
  scoreResolveError.value = "";
  const value = (event.target as HTMLInputElement).value;
  store.setCandidateScore(value === "" ? null : Number(value));
}

async function resolveCandidateScore() {
  const profile = candidateProfile.value;
  scoreResolveError.value = "";
  if (!profile.source_province || profile.year === null || !profile.category) {
    store.setCandidateScoreResolution("unsupported_context");
    return;
  }
  if (!scoreModeAvailable.value) {
    store.setCandidateScoreResolution("unsupported_context");
    return;
  }
  if (profile.score === null || !Number.isInteger(profile.score) || profile.score < 0) {
    scoreResolveError.value = "请输入大于或等于 0 的整数分数。";
    store.setCandidateScoreResolution("error");
    return;
  }

  scoreResolverController?.abort();
  const current = new AbortController();
  scoreResolverController = current;
  store.setCandidateScoreResolution("loading");
  try {
    const response = await resolveScoreRank(
      {
        source_province: profile.source_province,
        year: profile.year,
        category: profile.category,
        score: profile.score,
      },
      current.signal,
    );
    if (current.signal.aborted) return;
    store.setCandidateScoreResolution(
      response.data.status,
      response.data.resolved_rank,
    );
  } catch (cause) {
    if (current.signal.aborted) return;
    scoreResolveError.value =
      cause instanceof Error ? cause.message : "分数解析失败，请重试。";
    store.setCandidateScoreResolution("error");
  }
}

function onRankWindowInput(field: "ahead" | "behind", event: Event) {
  const value = (event.target as HTMLInputElement).value;
  rankWindow.value[field] = value === "" ? Number.NaN : Number(value);
}

function onCandidateSourceProvinceChange(event: Event) {
  scoreResolverController?.abort();
  scoreResolveError.value = "";
  store.setCandidateSourceProvince((event.target as HTMLSelectElement).value);
  autoSelectCandidateYear();
}

function onCandidateYearChange(event: Event) {
  scoreResolverController?.abort();
  scoreResolveError.value = "";
  const value = (event.target as HTMLSelectElement).value;
  store.setCandidateYear(value === "" ? null : Number(value));
  autoSelectCandidateCategory();
}

function onCandidateCategoryChange(event: Event) {
  scoreResolverController?.abort();
  scoreResolveError.value = "";
  store.setCandidateCategory((event.target as HTMLSelectElement).value);
}

function onCandidateBatchChange(event: Event) {
  store.setCandidateBatch((event.target as HTMLSelectElement).value);
}

function formatRank(value: number | null | undefined) {
  return value == null ? "—" : value.toLocaleString("zh-CN");
}

function describeRankGap(gap: number) {
  if (gap === 0) return "与你当前位次相同";
  return gap > 0
    ? `历史最低位次比你当前位次靠后 ${gap.toLocaleString("zh-CN")} 位`
    : `历史最低位次比你当前位次靠前 ${Math.abs(gap).toLocaleString("zh-CN")} 位`;
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

async function loadCandidateContexts() {
  candidateContextController?.abort();
  const current = new AbortController();
  candidateContextController = current;
  candidateContextLoading.value = true;
  candidateContextError.value = "";
  candidateContexts.value = [];
  try {
    const response = await getCandidateProfileContexts(current.signal);
    if (current.signal.aborted) return;
    candidateContexts.value = response.data.contexts;
    candidateContextWarnings.value = [...new Set(response.warnings)];
    reconcileCandidateProfile();
  } catch (cause) {
    if (!current.signal.aborted) {
      candidateContextWarnings.value = [];
      candidateContextError.value =
        cause instanceof Error ? cause.message : "考试上下文加载失败。";
    }
  } finally {
    if (candidateContextController === current) candidateContextLoading.value = false;
  }
}

async function loadScoreRangeContexts() {
  scoreMetadataController?.abort();
  const current = new AbortController();
  scoreMetadataController = current;
  scoreMetadataLoading.value = true;
  scoreMetadataError.value = "";
  scoreRangeContexts.value = [];
  try {
    const response = await getScoreRangeContexts(current.signal);
    if (current.signal.aborted) return;
    scoreRangeContexts.value = response.data.contexts;
  } catch (cause) {
    if (!current.signal.aborted) {
      scoreMetadataError.value =
        cause instanceof Error ? cause.message : "分数数据上下文加载失败。";
    }
  } finally {
    if (scoreMetadataController === current) scoreMetadataLoading.value = false;
  }
}

onBeforeUnmount(() => {
  controller?.abort();
  metaController?.abort();
  candidateContextController?.abort();
  scoreMetadataController?.abort();
  scoreResolverController?.abort();
  loading.value = false;
  compareDialogOpen.value = false;
});
void loadMeta();
void loadCandidateContexts();
void loadScoreRangeContexts();
void load();
</script>

<template>
  <div class="search-page">
    <main class="workspace" :class="{ 'sidebar-is-collapsed': sidebarCollapsed }">
      <section class="map-panel" aria-label="高校空间分布">
        <div class="map-host"><slot name="map" /></div>
        <div class="map-footnote">
          <span>校区坐标用于空间查询参考，部分点位尚未完成人工核验；无校区数据的高校仍可参与非空间查询。</span>
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

      <section
        class="directory"
        :class="{ 'is-collapsed': sidebarCollapsed }"
        aria-label="高校查询"
      >
        <button
          v-if="sidebarCollapsed"
          type="button"
          class="sidebar-reopen"
          aria-label="展开查询侧栏"
          :aria-expanded="!sidebarCollapsed"
          @click="toggleSidebar"
        >
          <span aria-hidden="true">›</span>
          <strong>展开查询</strong>
        </button>
        <div
          ref="directoryContent"
          v-show="!sidebarCollapsed"
          class="directory-content"
        >
          <div class="directory-intro">
            <div class="directory-intro-main">
              <span class="brand-mark" aria-hidden="true">学</span>
              <div>
                <span class="eyebrow">COLLEGE EXPLORER</span>
                <h1>寻找你的下一站</h1>
              </div>
            </div>
            <button
              type="button"
              class="sidebar-collapse"
              aria-label="折叠查询侧栏"
              title="折叠查询侧栏"
              :aria-expanded="!sidebarCollapsed"
              @click="toggleSidebar"
            >
              <span aria-hidden="true">‹</span>
            </button>
            <p>招生、空间与地图结果共享同一套查询状态。</p>
          </div>
          <form class="search-form" @submit.prevent="submitSearch">
          <details
            class="query-group"
            :open="queryGroups.college"
            @toggle="syncQueryGroup('college', $event)"
          >
            <summary class="query-group-summary">
              <span>
                <strong>高校条件</strong>
                <small>名称、办学层次、登记地区</small>
              </span>
              <span class="query-group-meta">
                {{ directoryConditionCount ? `${directoryConditionCount} 项` : "未设置" }}
                <span class="query-group-chevron" aria-hidden="true">⌄</span>
              </span>
            </summary>
            <div class="query-group-body">
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
          </details>

          <div class="integrated-entry">
            <strong>招生与空间条件</strong>
            <span>{{ comprehensiveConditionCount ? `${comprehensiveConditionCount} 项已设置` : "按需展开下方分组" }}</span>
          </div>

          <details
            class="query-group"
            :open="queryGroups.candidate"
            @toggle="syncQueryGroup('candidate', $event)"
          >
            <summary class="query-group-summary">
              <span>
                <strong>考生画像与招生上下文</strong>
                <small>生源省、年份、科类与位次</small>
              </span>
              <span class="query-group-meta">
                {{ candidateGroupSummary }}
                <span class="query-group-chevron" aria-hidden="true">⌄</span>
              </span>
            </summary>
            <div class="query-group-body">
              <label class="profile-toggle">
                <input v-model="candidateProfileEnabled" type="checkbox" />
                <span>
                  <strong>启用考生画像</strong>
                  <small>位次可直接填写，也可由可靠一分一段数据辅助解析；不代表录取预测</small>
                </span>
              </label>
              <div class="filter-grid">
                <div>
                  <label for="source-province">
                    生源省<span v-if="candidateProfileEnabled" class="required-mark">必填</span>
                  </label>
                  <select
                    id="source-province"
                    :value="candidateProfile.source_province"
                    :disabled="candidateContextLoading || !!candidateContextError"
                    @change="onCandidateSourceProvinceChange"
                  >
                    <option value="">全部生源省</option>
                    <option
                      v-for="province in candidateSourceProvinceOptions"
                      :key="province"
                      :value="province"
                    >
                      {{ province }}
                    </option>
                  </select>
                </div>
                <div>
                  <label for="admission-year">
                    年份<span v-if="candidateProfileEnabled" class="required-mark">必填</span>
                  </label>
                  <select
                    id="admission-year"
                    :value="candidateProfile.year ?? ''"
                    :disabled="
                      candidateContextLoading ||
                      !!candidateContextError ||
                      !candidateProfile.source_province
                    "
                    @change="onCandidateYearChange"
                  >
                    <option value="">全部年份</option>
                    <option
                      v-for="year in candidateYearOptions"
                      :key="year"
                      :value="year"
                    >
                      {{ year }}
                    </option>
                  </select>
                </div>
                <div>
                  <label for="admission-category">
                    科类 / 选科<span v-if="candidateProfileEnabled" class="required-mark">必填</span>
                  </label>
                  <select
                    id="admission-category"
                    :value="candidateProfile.category"
                    :disabled="
                      candidateContextLoading ||
                      !!candidateContextError ||
                      candidateProfile.year === null
                    "
                    @change="onCandidateCategoryChange"
                  >
                    <option value="">全部科类</option>
                    <option
                      v-for="category in candidateCategoryOptions"
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
                    :value="candidateProfile.batch"
                    :disabled="
                      candidateContextLoading ||
                      !!candidateContextError ||
                      !candidateProfile.category
                    "
                    @change="onCandidateBatchChange"
                  >
                    <option value="">全部批次</option>
                    <option
                      v-for="batch in candidateBatchOptions"
                      :key="batch"
                      :value="batch"
                    >
                      {{ batch }}
                    </option>
                  </select>
                </div>
              </div>
              <div v-if="candidateProfileEnabled" class="rank-profile-panel">
                <fieldset class="profile-input-mode">
                  <legend>我掌握的信息</legend>
                  <label>
                    <input
                      type="radio"
                      name="candidate-input-mode"
                      value="rank"
                      :checked="candidateProfile.input_mode === 'rank'"
                      @change="onCandidateInputModeChange"
                    />
                    <span>我知道位次</span>
                  </label>
                  <label :class="{ disabled: !scoreModeAvailable }">
                    <input
                      type="radio"
                      name="candidate-input-mode"
                      value="score"
                      :checked="candidateProfile.input_mode === 'score'"
                      :disabled="scoreMetadataLoading || !!scoreMetadataError || !scoreModeAvailable"
                      @change="onCandidateInputModeChange"
                    />
                    <span>我只知道分数</span>
                  </label>
                </fieldset>

                <p v-if="scoreMetadataLoading" class="field-hint">
                  正在核对当前上下文的分数解析能力…
                </p>
                <p v-else-if="scoreMetadataError" class="inline-error">
                  分数解析能力暂时无法加载，位次模式仍可正常使用。
                  <button type="button" @click="loadScoreRangeContexts">重试</button>
                </p>
                <p
                  v-else-if="
                    candidateProfile.source_province &&
                    candidateProfile.year !== null &&
                    candidateProfile.category &&
                    !scoreModeAvailable
                  "
                  class="field-hint"
                >
                  当前考试上下文缺少可用于分数换算的可靠一分一段数据，请直接填写位次。
                </p>

                <div v-if="candidateProfile.input_mode === 'rank'" class="rank-input-row">
                  <div>
                    <label for="candidate-rank">
                      考生位次<span class="required-mark">必填</span>
                    </label>
                    <input
                      id="candidate-rank"
                      type="number"
                      min="1"
                      step="1"
                      inputmode="numeric"
                      :value="candidateProfile.rank ?? ''"
                      placeholder="如：20000"
                      @input="onRankInput"
                    />
                  </div>
                  <div class="rank-range-preview" aria-live="polite">
                    <span>当前历史参考区间</span>
                    <strong v-if="rankLower !== null && rankUpper !== null">
                      {{ formatRank(rankLower) }} ～ {{ formatRank(rankUpper) }}
                    </strong>
                    <strong v-else>填写位次后计算</strong>
                  </div>
                </div>

                <div v-else class="score-resolution-panel">
                  <div class="score-input-row">
                    <div>
                      <label for="candidate-score">
                        考生分数<span class="required-mark">必填</span>
                      </label>
                      <input
                        id="candidate-score"
                        type="number"
                        min="0"
                        step="1"
                        inputmode="numeric"
                        :value="candidateProfile.score ?? ''"
                        :disabled="!scoreModeAvailable"
                        placeholder="输入整数分数"
                        @input="onScoreInput"
                      />
                    </div>
                    <button
                      type="button"
                      class="secondary score-resolve-button"
                      :disabled="
                        !scoreModeAvailable ||
                        candidateProfile.resolution_status === 'loading' ||
                        candidateProfile.score === null
                      "
                      @click="resolveCandidateScore"
                    >
                      {{ candidateProfile.resolution_status === "loading" ? "解析中" : "解析参考位次" }}
                    </button>
                  </div>
                  <p v-if="activeScoreRangeContext" class="field-hint">
                    当前一分一段可用分数：{{ activeScoreRangeContext.min_score }}～{{ activeScoreRangeContext.max_score }}；仅精确匹配，不使用邻近分数估算。
                  </p>
                  <p v-else-if="scoreMetadataLoading" class="field-hint">
                    正在加载分数数据上下文…
                  </p>
                  <p v-else class="inline-error">
                    当前考试上下文缺少可用于分数换算的可靠一分一段数据，请直接填写位次。
                    <button v-if="scoreMetadataError" type="button" @click="loadScoreRangeContexts">重试</button>
                  </p>
                  <p
                    v-if="scoreResolutionMessage"
                    class="score-resolution-message"
                    :class="candidateProfile.resolution_status"
                    aria-live="polite"
                  >
                    {{ scoreResolutionMessage }}
                  </p>
                  <p v-if="scoreResolveError" class="inline-error">{{ scoreResolveError }}</p>
                  <div class="rank-range-preview score-rank-preview" aria-live="polite">
                    <span>当前历史参考区间</span>
                    <strong v-if="rankLower !== null && rankUpper !== null">
                      {{ formatRank(rankLower) }} ～ {{ formatRank(rankUpper) }}
                    </strong>
                    <strong v-else>成功解析参考位次后计算</strong>
                  </div>
                </div>
                <div class="rank-window-grid">
                  <div>
                    <label for="rank-ahead">向前查看（位）</label>
                    <input
                      id="rank-ahead"
                      type="number"
                      min="0"
                      step="1"
                      :value="Number.isNaN(rankWindow.ahead) ? '' : rankWindow.ahead"
                      @input="onRankWindowInput('ahead', $event)"
                    />
                    <small>排名数字更小、位置更靠前</small>
                  </div>
                  <div>
                    <label for="rank-behind">向后查看（位）</label>
                    <input
                      id="rank-behind"
                      type="number"
                      min="0"
                      step="1"
                      :value="Number.isNaN(rankWindow.behind) ? '' : rankWindow.behind"
                      @input="onRankWindowInput('behind', $event)"
                    />
                    <small>排名数字更大、位置更靠后</small>
                  </div>
                </div>
                <p class="field-hint">
                  默认向前 3,000 位、向后 8,000 位，仅用于限定要查看的历史事实范围。
                </p>
              </div>
              <p class="field-hint">
                生源省、年份、科类与批次按有效历史最低位次记录逐级提供。
              </p>
              <p v-if="candidateContextLoading" class="field-hint">
                正在加载可用考试上下文…
              </p>
              <p v-else-if="candidateContextError" class="inline-error">
                考试上下文暂时无法加载：{{ candidateContextError }}
                <button type="button" @click="loadCandidateContexts">重试</button>
              </p>
              <p v-if="metaLoading" class="field-hint">正在加载高校筛选项…</p>
              <p v-else-if="metaError" class="inline-error">
                {{ metaError }}
                <button type="button" @click="loadMeta">重试</button>
              </p>
              <p
                v-for="warning in combinedMetaWarnings"
                :key="warning"
                class="field-hint"
              >
                {{ warning }}
              </p>

            </div>
          </details>

          <details
            class="query-group"
            :open="queryGroups.spatial"
            @toggle="syncQueryGroup('spatial', $event)"
          >
            <summary class="query-group-summary">
              <span>
                <strong>空间条件</strong>
                <small>行政区、参考点、绘制范围与校区口径</small>
              </span>
              <span class="query-group-meta">
                {{ spatialGroupSummary }}
                <span class="query-group-chevron" aria-hidden="true">⌄</span>
              </span>
            </summary>
            <div class="query-group-body">
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
                  min="10"
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
                  <strong>允许参考校区点参与空间查询</strong>
                  <small>部分点位尚未完成人工核验</small>
                </span>
              </label>

            </div>
          </details>

          <details
            class="query-group"
            :open="queryGroups.transport"
            @toggle="syncQueryGroup('transport', $event)"
          >
            <summary class="query-group-summary">
              <span>
                <strong>交通条件</strong>
                <small>地铁、铁路站与机场距离</small>
              </span>
              <span class="query-group-meta">
                {{ transportGroupSummary }}
                <span class="query-group-chevron" aria-hidden="true">⌄</span>
              </span>
            </summary>
            <div class="query-group-body">
              <section class="transport-filter-section" aria-labelledby="transport-filter-title">
                <div class="filter-section-title">
                  <strong id="transport-filter-title">交通空间条件</strong>
                  <span>可组合选择，所有条件同时满足</span>
                </div>
                <label class="transport-filter-toggle">
                  <input
                    :checked="transportEnabled"
                    type="checkbox"
                    @change="setTransportEnabled(($event.target as HTMLInputElement).checked)"
                  />
                  <span>
                    <strong>启用交通设施筛选</strong>
                    <small>默认关闭；启用后仅保留同一校区同时满足所选条件的高校</small>
                  </span>
                </label>
                <div v-if="transportEnabled" class="transport-filter-body">
                  <div class="transport-condition-list">
                    <label
                      v-for="mode in TRANSPORT_MODES"
                      :key="mode"
                      class="transport-condition"
                      :class="{ active: transportConditions[mode].enabled }"
                    >
                      <span class="transport-condition-main">
                        <input
                          :checked="transportConditions[mode].enabled"
                          type="checkbox"
                          @change="toggleTransportMode(mode)"
                        />
                        <span>
                          <strong>{{ TRANSPORT_MODE_LABELS[mode] }}</strong>
                          <small>{{ transportConditions[mode].enabled ? "加入 AND 条件" : "未选择" }}</small>
                        </span>
                      </span>
                      <select
                        :value="transportConditions[mode].max_distance_km"
                        :disabled="!transportConditions[mode].enabled"
                        :aria-label="`${TRANSPORT_MODE_LABELS[mode]}最大距离`"
                        @change="setTransportDistance(mode, Number(($event.target as HTMLSelectElement).value))"
                      >
                        <option
                          v-for="distance in TRANSPORT_DISTANCE_OPTIONS[mode]"
                          :key="distance"
                          :value="distance"
                        >
                          ≤ {{ distance }} km
                        </option>
                      </select>
                    </label>
                  </div>
                  <p class="transport-and-hint">
                    已选择 {{ selectedTransportModes.length }} 项；选择多项时按 AND 处理，必须由同一个 Campus 同时满足。
                  </p>
                  <p class="transport-candidate-notice">
                    交通筛选会使用已核验与候选校区坐标；候选点尚未完成最终人工核验，结果将同步显示业务提示。
                  </p>
                  <p class="field-hint">
                    距离为 Campus 与交通设施坐标之间的测地直线距离，不代表步行、驾车或通勤距离。交通数据 © OpenStreetMap contributors（ODbL）。
                  </p>
                </div>
              </section>
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
              当前视野高校
              <span>{{ displayedColleges.length.toLocaleString() }}</span>
              <em>{{ queryModeLabel }}</em>
            </h3>
            <p :title="listDescription">{{ listDescription }}</p>
          </div>
          <label v-if="usesBusinessResults" class="page-size">
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
        <CompareTray
          :colleges="compareColleges"
          :notice="compareNotice"
          @remove="removeCompare"
          @clear="clearCompare"
          @start="openCompare"
        />
        <div class="college-list" :aria-busy="loading">
          <p v-for="warning in warnings" :key="warning" class="business-warning">
            {{ displayWarning(warning) }}
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
          <div v-else-if="!displayedColleges.length" class="state-message" role="status">
            <h3>没有找到匹配的高校</h3>
            <p>{{ emptyHint }}</p>
            <button class="secondary" @click="clearAll">清除全部条件</button>
          </div>
          <template v-else>
            <div class="college-groups">
              <section
                v-for="group in visibleCollegeGroups"
                :key="group.key"
                class="college-group"
              >
                <button
                  type="button"
                  class="college-group-toggle"
                  :aria-expanded="expandedGroups[group.key]"
                  @click="toggleGroup(group.key)"
                >
                  <span>
                    <strong>{{ group.label }}</strong>
                    <small>{{ group.colleges.length }} 所</small>
                  </span>
                  <span
                    class="group-chevron"
                    :class="{ expanded: expandedGroups[group.key] }"
                    aria-hidden="true"
                  >
                    ⌄
                  </span>
                </button>
                <div v-if="expandedGroups[group.key]" class="college-group-list">
                  <article
                    v-for="college in group.colleges"
                    :key="college.school_id"
                    class="college-card"
                    :class="{
                      selected: selectedCollege?.school_id === college.school_id,
                    }"
                    :aria-pressed="selectedCollege?.school_id === college.school_id"
                    role="button"
                    tabindex="0"
                    @click="store.setSelectedCollege(college)"
                    @keydown.enter="store.setSelectedCollege(college)"
                    @keydown.space.prevent="store.setSelectedCollege(college)"
                  >
                    <span class="college-card-top">
                      <span class="college-monogram" aria-hidden="true">{{
                        college.name.slice(0, 1)
                      }}</span>
                      <span class="college-identity">
                        <strong>{{ college.name }}</strong>
                        <span
                          v-if="getCollegeTierLabels(college.school_id).length"
                          class="tier-tags"
                        >
                          <span
                            v-for="label in getCollegeTierLabels(college.school_id)"
                            :key="label"
                            class="tier-tag"
                          >
                            {{ label }}
                          </span>
                        </span>
                        <span v-if="isPureViewportMode">当前地图视野内 · Campus 浏览数据</span>
                        <span v-else>
                          {{ college.reg_province || "登记地区未提供" }}<i>·</i>{{
                            college.edu_level || "层次未提供"
                          }}
                        </span>
                      </span>
                      <span class="card-actions">
                        <button
                          type="button"
                          class="compare-toggle"
                          :class="{ active: isCompared(college.school_id) }"
                          :aria-pressed="isCompared(college.school_id)"
                          @click.stop="toggleCompare(college)"
                        >
                          {{ isCompared(college.school_id) ? "已加入" : "加入对比" }}
                        </button>
                        <span class="card-arrow" aria-hidden="true">↗</span>
                      </span>
                    </span>
                    <span class="college-card-bottom">
                      <span v-if="!isPureViewportMode">
                        院校代码 {{ college.national_code || "未提供" }}
                      </span>
                      <span v-else>点击高校可定位并高亮校区</span>
                      <span v-if="college.distance_km != null" class="distance-value">
                        {{ college.distance_km.toFixed(2) }} km
                      </span>
                      <span :class="college.has_campus ? 'campus-available' : 'muted'">
                        {{ college.has_campus ? "有校区数据" : "暂无可信校区数据" }}
                      </span>
                    </span>
                    <span
                      v-if="college.reference_admission"
                      class="rank-reference"
                    >
                      <span class="rank-reference-heading">
                        <strong>
                          历史最低位次
                          {{ formatRank(college.reference_admission.min_rank) }}
                        </strong>
                        <em>{{ college.reference_admission.year }} 年历史参考</em>
                      </span>
                      <span>{{ describeRankGap(college.reference_admission.rank_gap) }}</span>
                      <span>
                        {{ college.reference_admission.source_province }} ·
                        {{ college.reference_admission.category || "科类未提供" }} ·
                        {{ college.reference_admission.batch || "批次未提供" }} ·
                        最低分 {{ formatRank(college.reference_admission.min_score) }}
                      </span>
                    </span>
                  </article>
                </div>
              </section>
            </div>
          </template>
        </div>
        <nav v-if="usesBusinessResults" class="pagination" aria-label="高校列表分页">
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
        </div>
      </section>
    </main>
    <CollegeCompareDialog
      :open="compareDialogOpen"
      :colleges="compareColleges"
      :admission-context="compareAdmissionContext"
      @close="compareDialogOpen = false"
    />
  </div>
</template>
