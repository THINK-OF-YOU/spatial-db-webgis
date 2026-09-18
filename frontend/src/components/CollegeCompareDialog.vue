<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { getCollegeAdmissionSummary } from '../api/admissions'
import { getCollegeMajors } from '../api/majors'
import { getCollegeTierLabels } from '../data/collegeTiers'
import type { CollegeAdmissionSummary } from '../types/admission'
import type { CollegeMajorPage } from '../types/major'
import type { CompareAdmissionContext, CompareCollegeSnapshot } from '../types'
import { loadTransportSummary } from './transport/transportData'
import type {
  TransportItem,
  TransportSummaryMode,
  TransportSummaryResponse,
} from './transport/transportTypes'

const props = defineProps<{
  open: boolean
  colleges: CompareCollegeSnapshot[]
  admissionContext: CompareAdmissionContext | null
}>()

const emit = defineEmits<{ close: [] }>()

type ResourceState<T> =
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; message: string }

const transportStates = ref<Record<number, ResourceState<TransportSummaryResponse>>>({})
const admissionStates = ref<Record<number, ResourceState<CollegeAdmissionSummary>>>({})
const majorStates = ref<Record<number, ResourceState<CollegeMajorPage>>>({})
const controller = ref<AbortController | null>(null)
let requestVersion = 0

const hasDistance = computed(() =>
  props.colleges.some((college) => college.distance_km != null),
)
const gridStyle = computed(() => ({
  '--compare-columns': String(Math.max(props.colleges.length, 1)),
}))
const transportModes: { key: TransportSummaryMode; label: string }[] = [
  { key: 'metro', label: '最近地铁' },
  { key: 'rail', label: '最近铁路站' },
  { key: 'airport', label: '最近机场' },
]

const contextSummary = computed(() => {
  const context = props.admissionContext
  if (!context) return ''
  return [
    `生源省：${context.source_province}`,
    `年份：${context.year}`,
    `科类：${context.category}`,
    `批次：${context.batch || '全部批次'}`,
    `参考位次：${context.candidate_rank.toLocaleString('zh-CN')}`,
  ].join(' · ')
})

const admissionYears = computed(() => {
  const years = new Set<number>()
  for (const state of Object.values(admissionStates.value)) {
    if (state.status !== 'success') continue
    for (const entry of state.data.years) years.add(entry.year)
  }
  return [...years].sort((left, right) => right - left)
})
const admissionLoading = computed(() =>
  props.colleges.some((college) => admissionStates.value[college.school_id]?.status === 'loading'),
)
const admissionError = computed(() =>
  props.colleges.some((college) => admissionStates.value[college.school_id]?.status === 'error'),
)

function displayName(item: TransportItem) {
  return item.name_zh?.trim() || item.name
}

function formatNumber(value: number | null | undefined) {
  return value == null ? '未提供' : value.toLocaleString('zh-CN')
}

function formatDistance(value: number | null | undefined) {
  return value == null ? '当前结果未返回' : `${value.toFixed(2)} km`
}

function formatRankGap(value: number | null | undefined) {
  return value == null ? '未提供' : formatNumber(value)
}

function admissionStatusText(status: string) {
  if (status === 'reference_available') return '可比较'
  if (status === 'rank_unavailable') return '位次不可用'
  return '暂无同口径记录'
}

function getTransportState(schoolId: number) {
  return transportStates.value[schoolId]
}

function getTransportItem(schoolId: number, mode: TransportSummaryMode) {
  const state = getTransportState(schoolId)
  return state?.status === 'success' ? state.data.items[mode] : null
}

function isNoCampus(schoolId: number) {
  const state = getTransportState(schoolId)
  return (
    state?.status === 'success' &&
    state.data.warnings.includes('该校暂无可用校区数据，无法进行周边查询')
  )
}

function getAdmissionState(schoolId: number) {
  return admissionStates.value[schoolId]
}

function getAdmissionYear(schoolId: number, year: number) {
  const state = getAdmissionState(schoolId)
  if (state?.status !== 'success') return null
  return state.data.years.find((entry) => entry.year === year) ?? null
}

function getMajorState(schoolId: number) {
  return majorStates.value[schoolId]
}

function getMajorItems(schoolId: number) {
  const state = getMajorState(schoolId)
  return state?.status === 'success' ? state.data.items.slice(0, 3) : []
}

function isCurrent(current: AbortController, version: number) {
  return !current.signal.aborted && version === requestVersion
}

function setTransportState(schoolId: number, state: ResourceState<TransportSummaryResponse>) {
  transportStates.value = { ...transportStates.value, [schoolId]: state }
}

function setAdmissionState(schoolId: number, state: ResourceState<CollegeAdmissionSummary>) {
  admissionStates.value = { ...admissionStates.value, [schoolId]: state }
}

function setMajorState(schoolId: number, state: ResourceState<CollegeMajorPage>) {
  majorStates.value = { ...majorStates.value, [schoolId]: state }
}

async function loadTransport(
  schoolId: number,
  current: AbortController,
  version: number,
) {
  try {
    const data = await loadTransportSummary(schoolId, current.signal)
    if (isCurrent(current, version)) setTransportState(schoolId, { status: 'success', data })
  } catch (cause) {
    if (!isCurrent(current, version)) return
    setTransportState(schoolId, {
      status: 'error',
      message: cause instanceof Error ? cause.message : '交通摘要加载失败',
    })
  }
}

async function loadAdmission(
  schoolId: number,
  context: CompareAdmissionContext,
  current: AbortController,
  version: number,
) {
  try {
    const data = await getCollegeAdmissionSummary(
      schoolId,
      {
        source_province: context.source_province,
        main_year: context.year,
        category: context.category,
        candidate_rank: context.candidate_rank,
        batch: context.batch || undefined,
      },
      current.signal,
    )
    if (isCurrent(current, version)) setAdmissionState(schoolId, { status: 'success', data })
  } catch (cause) {
    if (!isCurrent(current, version)) return
    setAdmissionState(schoolId, {
      status: 'error',
      message: cause instanceof Error ? cause.message : '学校历史参考加载失败',
    })
  }
}

async function loadMajors(
  schoolId: number,
  context: CompareAdmissionContext,
  current: AbortController,
  version: number,
) {
  try {
    const data = await getCollegeMajors(
      schoolId,
      {
        source_province: context.source_province,
        year: context.year,
        category: context.category,
        batch: context.batch || undefined,
        candidate_rank: context.candidate_rank,
        page: 1,
        page_size: 3,
      },
      current.signal,
    )
    if (isCurrent(current, version)) setMajorState(schoolId, { status: 'success', data })
  } catch (cause) {
    if (!isCurrent(current, version)) return
    setMajorState(schoolId, {
      status: 'error',
      message: cause instanceof Error ? cause.message : '专业录取参考加载失败',
    })
  }
}

async function loadDialogData() {
  controller.value?.abort()
  const version = ++requestVersion
  const current = new AbortController()
  controller.value = current
  transportStates.value = {}
  admissionStates.value = {}
  majorStates.value = {}

  for (const college of props.colleges) {
    setTransportState(college.school_id, { status: 'loading' })
    if (props.admissionContext) {
      setAdmissionState(college.school_id, { status: 'loading' })
      setMajorState(college.school_id, { status: 'loading' })
    }
  }

  await Promise.all(
    props.colleges.map(async (college) => {
      const tasks: Promise<void>[] = [loadTransport(college.school_id, current, version)]
      if (props.admissionContext) {
        tasks.push(
          loadAdmission(college.school_id, props.admissionContext, current, version),
          loadMajors(college.school_id, props.admissionContext, current, version),
        )
      }
      await Promise.all(tasks)
    }),
  )
}

function stopRequests() {
  requestVersion += 1
  controller.value?.abort()
}

function close() {
  emit('close')
}

watch(
  () =>
    JSON.stringify({
      open: props.open,
      school_ids: props.colleges.map((college) => college.school_id),
      context: props.admissionContext,
    }),
  () => {
    if (props.open) void loadDialogData()
    else stopRequests()
  },
  { immediate: true },
)

onBeforeUnmount(stopRequests)
</script>

<template>
  <div
    v-if="open"
    class="compare-overlay"
    role="presentation"
    @click.self="close"
    @keydown.esc="close"
  >
    <section
      class="compare-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="college-compare-title"
    >
      <header class="compare-dialog-header">
        <div>
          <span class="eyebrow">COLLEGE FACT COMPARISON</span>
          <h2 id="college-compare-title">高校横向比较</h2>
          <p>以下内容均来自当前搜索结果及现有招生、交通接口，仅并排呈现客观事实。</p>
        </div>
        <button type="button" class="compare-dialog-close" aria-label="关闭高校横向比较" @click="close">
          ×
        </button>
      </header>

      <div class="compare-dialog-scroll">
        <p v-if="admissionContext && contextSummary" class="compare-context">
          当前考生画像上下文：{{ contextSummary }}
        </p>

        <section class="compare-section" aria-labelledby="compare-overview-heading">
          <div class="compare-section-heading">
            <h3 id="compare-overview-heading">院校概况</h3>
            <span>College 当前事实</span>
          </div>
          <div class="compare-grid" :style="gridStyle" role="table">
            <div class="compare-cell compare-label" role="columnheader">比较项</div>
            <div
              v-for="college in colleges"
              :key="`overview-head-${college.school_id}`"
              class="compare-cell compare-college-head"
              role="columnheader"
            >
              <strong>{{ college.name }}</strong>
              <small>{{ college.school_id }}</small>
            </div>

            <div class="compare-cell compare-label" role="rowheader">院校层次</div>
            <div v-for="college in colleges" :key="`level-${college.school_id}`" class="compare-cell" role="cell">
              {{ college.edu_level || '未提供' }}
            </div>
            <div class="compare-cell compare-label" role="rowheader">院校标签</div>
            <div v-for="college in colleges" :key="`tier-${college.school_id}`" class="compare-cell" role="cell">
              {{ getCollegeTierLabels(college.school_id).join(' / ') || '未标注' }}
            </div>
            <div class="compare-cell compare-label" role="rowheader">登记地区</div>
            <div v-for="college in colleges" :key="`region-${college.school_id}`" class="compare-cell" role="cell">
              {{ college.reg_province || '未提供' }}
            </div>
            <div class="compare-cell compare-label" role="rowheader">院校代码</div>
            <div v-for="college in colleges" :key="`code-${college.school_id}`" class="compare-cell" role="cell">
              {{ college.national_code || '未提供' }}
            </div>
            <div class="compare-cell compare-label" role="rowheader">校区空间数据</div>
            <div v-for="college in colleges" :key="`campus-${college.school_id}`" class="compare-cell" role="cell">
              {{ college.has_campus ? '已有校区空间数据' : '暂无可用校区空间数据' }}
            </div>
          </div>
        </section>

        <section v-if="admissionContext" class="compare-section" aria-labelledby="compare-history-heading">
          <div class="compare-section-heading">
            <h3 id="compare-history-heading">学校历史参考</h3>
            <span>同一招生上下文 · 多年度事实</span>
          </div>
          <p v-if="admissionYears.length === 0 && admissionLoading" class="compare-empty-note">
            正在加载当前招生口径的多年度历史参考…
          </p>
          <p v-else-if="admissionYears.length === 0 && admissionError" class="compare-empty-note">
            学校历史参考加载失败；不影响其它比较事实继续展示。
          </p>
          <p v-else-if="admissionYears.length === 0" class="compare-empty-note">
            当前生源省与科类下暂无可比较年份。
          </p>
          <div v-else class="compare-grid" :style="gridStyle" role="table">
            <div class="compare-cell compare-label" role="columnheader">比较项</div>
            <div
              v-for="college in colleges"
              :key="`history-head-${college.school_id}`"
              class="compare-cell compare-college-head"
              role="columnheader"
            >
              {{ college.name }}
            </div>
            <template v-for="year in admissionYears" :key="`history-year-${year}`">
              <div class="compare-cell compare-label" role="rowheader">{{ year }} 年</div>
              <div
                v-for="college in colleges"
                :key="`${year}-${college.school_id}`"
                class="compare-cell history-cell"
                role="cell"
              >
                <span v-if="getAdmissionState(college.school_id)?.status === 'loading'">正在加载…</span>
                <span v-else-if="getAdmissionState(college.school_id)?.status === 'error'" class="compare-error">
                  历史参考加载失败
                </span>
                <template v-else-if="getAdmissionYear(college.school_id, year)">
                  <strong :class="`history-status ${getAdmissionYear(college.school_id, year)!.status}`">
                    {{ admissionStatusText(getAdmissionYear(college.school_id, year)!.status) }}
                  </strong>
                  <template v-if="getAdmissionYear(college.school_id, year)!.reference_admission">
                    <span>最低位次：{{ formatNumber(getAdmissionYear(college.school_id, year)!.reference_admission!.min_rank) }}</span>
                    <span>最低分：{{ formatNumber(getAdmissionYear(college.school_id, year)!.reference_admission!.min_score) }}</span>
                    <span>位次差：{{ formatRankGap(getAdmissionYear(college.school_id, year)!.reference_admission!.rank_gap) }}</span>
                  </template>
                  <span v-else-if="getAdmissionYear(college.school_id, year)!.status === 'rank_unavailable'">
                    有招生记录，但位次不可用
                  </span>
                  <span v-else>暂无同口径记录</span>
                  <small>真实记录 {{ getAdmissionYear(college.school_id, year)!.record_count.toLocaleString('zh-CN') }} 条</small>
                </template>
                <span v-else class="compare-muted">暂无同口径记录</span>
              </div>
            </template>
          </div>
        </section>

        <section v-if="admissionContext" class="compare-section" aria-labelledby="compare-major-heading">
          <div class="compare-section-heading">
            <h3 id="compare-major-heading">专业录取参考</h3>
            <span>每校按现有 Major API 顺序取最多 3 条</span>
          </div>
          <p class="compare-section-note">
            来源专业表达是主要名称；标准专业仅在真实映射存在时作为辅助信息。各高校的 Top 3 独立展示，不进行跨校专业对齐。
          </p>
          <div class="major-compare-grid" :style="gridStyle">
            <article v-for="college in colleges" :key="`majors-${college.school_id}`" class="major-compare-column">
              <header>
                <strong>{{ college.name }}</strong>
                <small>当前参考位次 {{ admissionContext.candidate_rank.toLocaleString('zh-CN') }}</small>
              </header>
              <div v-if="getMajorState(college.school_id)?.status === 'loading'" class="compare-resource-state">
                正在加载专业录取参考…
              </div>
              <div v-else-if="getMajorState(college.school_id)?.status === 'error'" class="compare-resource-state compare-error">
                专业参考加载失败
              </div>
              <div v-else-if="!getMajorItems(college.school_id).length" class="compare-resource-state compare-muted">
                当前招生口径下暂无专业录取参考
              </div>
              <ol v-else class="major-compare-list">
                <li
                  v-for="(item, index) in getMajorItems(college.school_id)"
                  :key="`${college.school_id}-${item.expr_id ?? item.raw_major_name}-${index}`"
                  class="major-compare-item"
                >
                  <div class="major-compare-item-title">
                    <strong>{{ item.raw_major_name }}</strong>
                    <small>参考 {{ index + 1 }}</small>
                  </div>
                  <p v-if="item.std_major" class="major-compare-standard">
                    标准专业：{{ item.std_major.std_name }}
                  </p>
                  <dl>
                    <div>
                      <dt>最低位次</dt>
                      <dd>{{ formatNumber(item.min_rank) }}</dd>
                    </div>
                    <div>
                      <dt>最低分</dt>
                      <dd>{{ formatNumber(item.min_score) }}</dd>
                    </div>
                    <div>
                      <dt>位次差</dt>
                      <dd>{{ formatRankGap(item.professional_rank_gap) }}</dd>
                    </div>
                  </dl>
                  <p class="major-compare-year">{{ item.year ?? '年份未提供' }} · 来源表达事实</p>
                </li>
              </ol>
            </article>
          </div>
        </section>

        <p v-else class="compare-gated-note">
          启用考生画像后，可比较同口径多年度学校历史与专业录取参考。
        </p>

        <section v-if="hasDistance" class="compare-section" aria-labelledby="compare-distance-heading">
          <div class="compare-section-heading">
            <h3 id="compare-distance-heading">距当前参考点</h3>
            <span>复用搜索结果 distance_km</span>
          </div>
          <div class="compare-grid" :style="gridStyle" role="table">
            <div class="compare-cell compare-label" role="columnheader">比较项</div>
            <div v-for="college in colleges" :key="`distance-head-${college.school_id}`" class="compare-cell compare-college-head" role="columnheader">
              {{ college.name }}
            </div>
            <div class="compare-cell compare-label" role="rowheader">测地直线距离</div>
            <div v-for="college in colleges" :key="`distance-${college.school_id}`" class="compare-cell compare-value" role="cell">
              {{ formatDistance(college.distance_km) }}
            </div>
          </div>
        </section>

        <section class="compare-section" aria-labelledby="compare-transport-heading">
          <div class="compare-section-heading">
            <h3 id="compare-transport-heading">最近交通事实</h3>
            <span>每所高校独立请求</span>
          </div>
          <div class="compare-grid" :style="gridStyle" role="table">
            <div class="compare-cell compare-label" role="columnheader">比较项</div>
            <div v-for="college in colleges" :key="`transport-head-${college.school_id}`" class="compare-cell compare-college-head" role="columnheader">
              {{ college.name }}
            </div>
            <template v-for="mode in transportModes" :key="mode.key">
              <div class="compare-cell compare-label" role="rowheader">{{ mode.label }}</div>
              <div v-for="college in colleges" :key="`${mode.key}-${college.school_id}`" class="compare-cell transport-cell" role="cell">
                <span v-if="getTransportState(college.school_id)?.status === 'loading'">正在加载…</span>
                <span v-else-if="getTransportState(college.school_id)?.status === 'error'" class="compare-error">交通摘要加载失败</span>
                <span v-else-if="isNoCampus(college.school_id)" class="compare-muted">暂无可用校区空间数据</span>
                <template v-else-if="getTransportItem(college.school_id, mode.key)">
                  <strong>{{ displayName(getTransportItem(college.school_id, mode.key)!) }}</strong>
                  <small>{{ getTransportItem(college.school_id, mode.key)!.distance_km.toFixed(2) }} km</small>
                </template>
                <span v-else class="compare-muted">暂无记录</span>
              </div>
            </template>
          </div>
          <p class="compare-footnote">
            交通距离为校区与交通设施之间的测地直线距离，不代表步行、驾车或通勤距离。数据 © OpenStreetMap contributors（ODbL）。
          </p>
        </section>
      </div>
    </section>
  </div>
</template>

<style scoped>
.compare-overlay {
  position: fixed;
  z-index: 1200;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 28px;
  background: rgb(26 45 38 / 42%);
}
.compare-dialog {
  display: flex;
  flex-direction: column;
  width: min(1240px, 100%);
  max-height: min(88vh, 860px);
  overflow: hidden;
  border: 1px solid #cbded1;
  border-radius: 13px;
  background: #f7faf8;
  box-shadow: 0 24px 70px rgb(22 54 42 / 24%);
}
.compare-dialog-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 21px 25px 17px;
  border-bottom: 1px solid #dce8df;
  background: #fff;
}
.compare-dialog-header .eyebrow {
  color: #668676;
  font-size: 8px;
}
.compare-dialog-header h2 {
  margin-top: 5px;
  color: #26483a;
  font-size: 21px;
}
.compare-dialog-header p {
  margin-top: 6px;
  color: #7a8b81;
  font-size: 10px;
}
.compare-dialog-close {
  flex: none;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid #d8e5dc;
  border-radius: 50%;
  background: #f7faf8;
  color: #6f8578;
  font-size: 21px;
  line-height: 1;
}
.compare-dialog-close:hover {
  border-color: #99bbaa;
  background: #edf6ef;
}
.compare-dialog-scroll {
  overflow: auto;
  padding: 17px 25px 26px;
}
.compare-context {
  margin-bottom: 14px;
  padding: 9px 11px;
  border: 1px solid #d5e7da;
  border-radius: 7px;
  background: #f0f8f2;
  color: #476c58;
  font-size: 10px;
}
.compare-section {
  margin-top: 16px;
}
.compare-section:first-of-type {
  margin-top: 0;
}
.compare-section-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.compare-section-heading h3 {
  color: #315746;
  font-size: 13px;
}
.compare-section-heading span {
  color: #8a9a90;
  font-size: 9px;
}
.compare-grid {
  display: grid;
  grid-template-columns: 145px repeat(var(--compare-columns), minmax(178px, 1fr));
  min-width: max-content;
  border-top: 1px solid #dce7df;
  border-left: 1px solid #dce7df;
  background: #fff;
}
.compare-cell {
  min-height: 38px;
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-right: 1px solid #dce7df;
  border-bottom: 1px solid #dce7df;
  color: #496355;
  font-size: 10px;
  line-height: 1.45;
}
.compare-label {
  color: #74867b;
  background: #f4f8f5;
  font-weight: 650;
}
.compare-college-head {
  display: grid;
  align-content: center;
  gap: 2px;
  background: #eef7f0;
  color: #2f654f;
}
.compare-college-head strong {
  font-size: 11px;
}
.compare-college-head small {
  color: #85978b;
  font-size: 9px;
}
.compare-value {
  color: #3c6b56;
  font-variant-numeric: tabular-nums;
}
.history-cell {
  display: grid;
  align-content: center;
  gap: 2px;
}
.history-cell strong {
  font-size: 10px;
}
.history-cell span,
.history-cell small {
  color: #65786d;
  font-size: 9px;
}
.history-cell small {
  color: #8a9990;
}
.history-status.reference_available {
  color: #397763;
}
.history-status.rank_unavailable {
  color: #876b32;
}
.history-status.no_record {
  color: #87958c;
}
.compare-section-note {
  margin: 0 0 9px;
  color: #7f9086;
  font-size: 9px;
  line-height: 1.55;
}
.major-compare-grid {
  display: grid;
  grid-template-columns: repeat(var(--compare-columns), minmax(210px, 1fr));
  gap: 9px;
  min-width: max-content;
}
.major-compare-column {
  min-width: 210px;
  border: 1px solid #dce7df;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}
.major-compare-column > header {
  display: grid;
  gap: 3px;
  padding: 10px 11px;
  border-bottom: 1px solid #dce7df;
  background: #eef7f0;
  color: #2f654f;
}
.major-compare-column > header strong {
  font-size: 11px;
}
.major-compare-column > header small {
  color: #7d9183;
  font-size: 9px;
}
.compare-resource-state {
  padding: 14px 11px;
  color: #788a7f;
  font-size: 10px;
  line-height: 1.55;
}
.major-compare-list {
  display: grid;
  gap: 7px;
  margin: 0;
  padding: 9px;
  list-style: none;
}
.major-compare-item {
  padding: 9px;
  border: 1px solid #e1eae3;
  border-radius: 6px;
  background: #fbfdfb;
}
.major-compare-item-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}
.major-compare-item-title strong {
  color: #3b604d;
  font-size: 10px;
  line-height: 1.45;
}
.major-compare-item-title small {
  flex: none;
  color: #8a9990;
  font-size: 8px;
}
.major-compare-standard {
  margin-top: 5px;
  color: #6d8175;
  font-size: 9px;
  line-height: 1.45;
}
.major-compare-item dl {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 5px;
  margin: 8px 0 0;
}
.major-compare-item dl div {
  min-width: 0;
}
.major-compare-item dt {
  color: #8a9990;
  font-size: 8px;
}
.major-compare-item dd {
  margin: 2px 0 0;
  color: #456b57;
  font-size: 9px;
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}
.major-compare-year {
  margin-top: 7px;
  color: #99a59e;
  font-size: 8px;
}
.compare-gated-note {
  margin-top: 16px;
  padding: 9px 11px;
  border: 1px solid #e0e8e2;
  border-radius: 6px;
  background: #f5f8f5;
  color: #788a7f;
  font-size: 10px;
}
.transport-cell {
  display: grid;
  align-content: center;
  gap: 2px;
}
.transport-cell strong {
  overflow: hidden;
  color: #3c5f4e;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.transport-cell small {
  color: #397763;
  font-size: 9px;
  font-variant-numeric: tabular-nums;
}
.compare-muted {
  color: #929f97;
}
.compare-error {
  color: #a05247;
}
.compare-empty-note,
.compare-footnote {
  margin: 0;
  padding: 9px 11px;
  border-radius: 6px;
  background: #f2f6f3;
  color: #788a7f;
  font-size: 10px;
  line-height: 1.55;
}
.compare-footnote {
  margin-top: 9px;
  padding: 0;
  background: transparent;
  color: #8a9990;
  font-size: 9px;
}

@media (max-width: 900px) {
  .compare-overlay {
    padding: 12px;
  }
  .compare-dialog-header,
  .compare-dialog-scroll {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
