import type {
  CandidateProfileContextsResponse,
  FilterMetaResponse,
  ScoreRangeContextsResponse,
  ScoreResolutionResponse,
} from "../types/meta";
import { request } from "./http";

export function getFilterMeta(signal?: AbortSignal) {
  return request<FilterMetaResponse>("/meta/filters", { signal });
}

export function getCandidateProfileContexts(signal?: AbortSignal) {
  return request<CandidateProfileContextsResponse>(
    "/meta/candidate-profile-contexts",
    { signal },
  );
}

export function getScoreRangeContexts(signal?: AbortSignal) {
  return request<ScoreRangeContextsResponse>("/meta/score-range-contexts", {
    signal,
  });
}

export function resolveScoreRank(
  params: {
    source_province: string;
    year: number;
    category: string;
    score: number;
  },
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({
    source_province: params.source_province,
    year: String(params.year),
    category: params.category,
    score: String(params.score),
  });
  return request<ScoreResolutionResponse>(
    `/meta/score-range/resolve?${query.toString()}`,
    { signal },
  );
}
