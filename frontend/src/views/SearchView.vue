<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from "vue";
import { storeToRefs } from "pinia";
import { getColleges } from "../api/colleges";
import { useSearchStore } from "../stores/useSearchStore";
import CollegeDetailPanel from "../components/CollegeDetailPanel.vue";

const store = useSearchStore();
const { results, loading, warnings, selectedCollege } = storeToRefs(store);
const draft = reactive({
  q: store.filters.q ?? "",
  edu_level: store.filters.edu_level ?? "",
  reg_province: store.filters.reg_province ?? "",
});
const page = ref(1);
const page_size = ref(20);
const total = ref(0);
const error = ref("");
const hasLoaded = ref(false);
const list = ref<HTMLElement | null>(null);
const pages = computed(() =>
  Math.max(1, Math.ceil(total.value / page_size.value)),
);
const hasSpatial = computed(
  () =>
    !!(
      store.referencePoint ||
      store.drawnGeometry ||
      store.selectedRegions.length
    ),
);
const applied = computed(
  () => Object.values(store.filters).filter(Boolean).join(" / ") || "全部高校",
);
let controller: AbortController | undefined;
let requestedPage = 1;

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
    const data = await getColleges(
      { ...store.filters, page: nextPage, page_size: page_size.value },
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
function search() {
  store.filters = {
    q: draft.q.trim(),
    edu_level: draft.edu_level,
    reg_province: draft.reg_province.trim(),
  };
  void load();
}
function reset() {
  Object.assign(draft, { q: "", edu_level: "", reg_province: "" });
  search();
}
onBeforeUnmount(() => {
  controller?.abort();
  loading.value = false;
});
void load();
</script>

<template>
  <div class="search-page">
    <header class="top-bar">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">学</span>
        <div>
          <h1>高校空间查询</h1>
          <p>从一所高校，探索更多可能</p>
        </div>
      </div>
      <div class="top-meta">
        <span>全国高校 · 数据浏览</span><span class="version">V1</span>
      </div>
    </header>
    <main class="workspace">
      <section class="directory" aria-label="高校查询">
        <div class="directory-intro">
          <span class="eyebrow">COLLEGE EXPLORER</span>
          <h2>寻找你的下一站</h2>
          <p>按名称、层次与登记地区查找高校。</p>
        </div>
        <form class="search-form" @submit.prevent="search">
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
              <label for="edu-level">办学层次</label
              ><select id="edu-level" v-model="draft.edu_level">
                <option value="">全部层次</option>
                <option>本科</option>
                <option>高职（专科）</option>
              </select>
            </div>
            <div>
              <label for="region">登记地区</label
              ><input
                id="region"
                v-model="draft.reg_province"
                placeholder="如：武汉市"
                aria-describedby="region-hint"
              />
            </div>
          </div>
          <p id="region-hint" class="field-hint">
            登记地区按原始名称精确匹配，与地图选区不同。
          </p>
          <div class="form-actions">
            <button class="primary" type="submit">
              查询高校 <span aria-hidden="true">→</span></button
            ><button type="button" class="quiet" @click="reset">重置</button>
          </div>
        </form>
        <div class="results-heading">
          <div>
            <h3>
              高校结果
              <span v-if="hasLoaded">{{ total.toLocaleString() }}</span>
            </h3>
            <p>{{ applied }}</p>
          </div>
          <label class="page-size"
            >每页<select
              v-model.number="page_size"
              aria-label="每页条数"
              :disabled="loading"
              @change="load()"
            >
              <option :value="20">20</option>
              <option :value="50">50</option>
            </select></label
          >
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
            <p>试试更短的关键词，或取消层次、登记地区条件。</p>
            <button class="secondary" @click="reset">查看全部高校</button>
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
              <span class="college-card-top"
                ><span class="college-monogram" aria-hidden="true">{{
                  college.name.slice(0, 1)
                }}</span
                ><span class="college-identity"
                  ><strong>{{ college.name }}</strong
                  ><span
                    >{{ college.reg_province || "登记地区未提供" }}<i>·</i
                    >{{ college.edu_level || "层次未提供" }}</span
                  ></span
                ><span class="card-arrow" aria-hidden="true">↗</span></span
              >
              <span class="college-card-bottom"
                ><span>院校代码 {{ college.national_code || "未提供" }}</span
                ><span
                  :class="college.has_campus ? 'campus-available' : 'muted'"
                  >{{
                    college.has_campus ? "有校区数据" : "暂无可信校区数据"
                  }}</span
                ></span
              >
            </button>
          </template>
        </div>
        <nav class="pagination" aria-label="高校列表分页">
          <button
            :disabled="loading || !!error || page <= 1"
            aria-label="上一页"
            @click="load(page - 1)"
          >
            ←</button
          ><span>{{ hasLoaded ? `${page} / ${pages} 页` : "—" }}</span
          ><button
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
            <h2>在地图上认识高校</h2>
          </div>
          <span class="map-caption">WGS84 · 校区空间分布</span>
        </div>
        <div class="map-host"><slot name="map" /></div>
        <div class="map-footnote">
          <span
            >地图展示有坐标的校区；没有校区数据的高校仍保留在查询结果中。</span
          ><span v-if="hasSpatial" class="spatial-note"
            >已记录空间条件 · 本轮高校查询不应用空间筛选</span
          ><span v-else>点击校区点查看高校详情</span>
        </div>
        <CollegeDetailPanel />
      </section>
    </main>
  </div>
</template>
