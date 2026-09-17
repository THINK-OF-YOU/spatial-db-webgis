import type { SearchRequest, SearchResponse } from "../types/search";
import { request } from "./http";

export function searchColleges(body: SearchRequest, signal?: AbortSignal) {
  return request<SearchResponse>("/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}
