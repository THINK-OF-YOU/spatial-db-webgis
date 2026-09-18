export interface FilterMeta {
  years: number[];
  source_provinces: string[];
  edu_levels: string[];
  categories: string[];
  batches: string[];
}

export interface FilterMetaResponse {
  data: FilterMeta;
  warnings: string[];
}

/** SchoolAdmission 中至少有一条有效 min_rank 的真实考试上下文。 */
export interface CandidateProfileContext {
  source_province: string;
  year: number;
  category: string;
  batch: string | null;
}

export interface CandidateProfileContextsResponse {
  data: {
    contexts: CandidateProfileContext[];
  };
  warnings: string[];
}

export interface ScoreRangeContext {
  source_province: string;
  year: number;
  category: string;
  valid_score_count: number;
  ambiguous_score_count: number;
  min_score: number;
  max_score: number;
}

export interface ScoreRangeContextsResponse {
  data: {
    contexts: ScoreRangeContext[];
  };
  warnings: string[];
}

export type ScoreResolutionStatus =
  | "resolved"
  | "ambiguous"
  | "not_found"
  | "unsupported_context";

export interface ScoreResolution {
  source_province: string;
  year: number;
  category: string;
  score: number;
  status: ScoreResolutionStatus;
  resolved_rank: number | null;
  matching_row_count: number;
  distinct_rank_count: number;
}

export interface ScoreResolutionResponse {
  data: ScoreResolution;
  warnings: string[];
}
