import type { FilterMetaResponse } from "../types/meta";
import { request } from "./http";

export function getFilterMeta(signal?: AbortSignal) {
  return request<FilterMetaResponse>("/meta/filters", { signal });
}
