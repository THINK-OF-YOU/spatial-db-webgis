import { onScopeDispose, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { loadTransport } from './transportData'
import { MODE_ORDER } from './transportTypes'
import type {
  TransportItem,
  TransportMode,
  TransportRadius,
} from './transportTypes'

export interface TransportController {
  items: Ref<TransportItem[]>
  total: Ref<number>
  warnings: Ref<string[]>
  loading: Ref<boolean>
  error: Ref<string>
  radiusKm: Ref<TransportRadius>
  modes: Ref<TransportMode[]>
  setRadius: (radius: TransportRadius) => void
  toggleMode: (mode: TransportMode) => void
  selectAllModes: () => void
  retry: () => void
}

/**
 * selectedCollege 对应的局部 Transport 状态。
 *
 * 由 App 创建一次并通过 provide/inject 给详情 Panel 和地图 Layer，共享同一个
 * 响应；不进入 Pinia，也不建立第二套高校业务结果源。
 */
export function useTransport(
  schoolId: Readonly<Ref<number | null>>,
): TransportController {
  const items = ref<TransportItem[]>([])
  const total = ref(0)
  const warnings = ref<string[]>([])
  const loading = ref(false)
  const error = ref('')
  const radiusKm = ref<TransportRadius>(3)
  const modes = ref<TransportMode[]>([...MODE_ORDER])

  let controller: AbortController | null = null
  let requestVersion = 0

  function clearResponse() {
    items.value = []
    total.value = 0
    warnings.value = []
    error.value = ''
  }

  async function refresh() {
    controller?.abort()
    const version = ++requestVersion
    clearResponse()

    const currentSchoolId = schoolId.value
    if (currentSchoolId === null) {
      controller = null
      loading.value = false
      return
    }

    const current = new AbortController()
    controller = current
    loading.value = true

    try {
      const selectedModes =
        modes.value.length === MODE_ORDER.length ? undefined : [...modes.value]
      const response = await loadTransport(
        currentSchoolId,
        {
          radiusKm: radiusKm.value,
          modes: selectedModes,
          limit: 200,
        },
        current.signal,
      )
      if (current.signal.aborted || version !== requestVersion) return
      items.value = response.items
      total.value = response.total
      warnings.value = [...new Set(response.warnings ?? [])]
    } catch (cause) {
      if (current.signal.aborted || version !== requestVersion) return
      error.value =
        cause instanceof Error ? cause.message : '周边交通数据加载失败，请稍后重试。'
    } finally {
      if (version === requestVersion) loading.value = false
    }
  }

  function setRadius(radius: TransportRadius) {
    if (radiusKm.value !== radius) radiusKm.value = radius
  }

  function toggleMode(mode: TransportMode) {
    const selected = modes.value.includes(mode)
    if (selected && modes.value.length === 1) return
    modes.value = selected
      ? modes.value.filter((item) => item !== mode)
      : MODE_ORDER.filter((item) => item === mode || modes.value.includes(item))
  }

  function selectAllModes() {
    modes.value = [...MODE_ORDER]
  }

  watch(
    [schoolId, radiusKm, () => modes.value.join(',')],
    () => void refresh(),
    { immediate: true },
  )

  onScopeDispose(() => {
    controller?.abort()
    requestVersion += 1
  })

  return {
    items,
    total,
    warnings,
    loading,
    error,
    radiusKm,
    modes,
    setRadius,
    toggleMode,
    selectAllModes,
    retry: () => void refresh(),
  }
}
