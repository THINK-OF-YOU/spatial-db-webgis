export interface SchoolAdmissionItem {
  source_province: string | null;
  year: number | null;
  category: string | null;
  batch: string | null;
  subject_req: string | null;
  min_score: number | null;
  min_rank: number | null;
  control_score: number | null;
  score_diff: number | null;
  admit_count: number | null;
}

export interface CollegeAdmissionsQuery {
  source_province?: string;
  year?: number;
  category?: string;
  batch?: string;
  page: number;
  page_size: number;
}

export interface CollegeAdmissionsPage {
  items: SchoolAdmissionItem[];
  total: number;
  page: number;
  page_size: number;
  warnings: string[];
  display_deduplicated: boolean;
}

export type AdmissionSummaryYearStatus =
  | "reference_available"
  | "rank_unavailable"
  | "no_record";

export interface AdmissionSummaryQuery {
  source_province: string;
  main_year: number;
  category: string;
  candidate_rank: number;
  batch?: string;
}

export interface AdmissionSummaryReference {
  admission_id: number;
  unit_id: number;
  unit_name: string;
  batch: string | null;
  min_score: number | null;
  min_rank: number;
  /** historical_min_rank - candidate_rank。 */
  rank_gap: number;
}

export interface AdmissionSummaryYear {
  year: number;
  status: AdmissionSummaryYearStatus;
  /** 严格上下文下的原始 SchoolAdmission 行数，不是明细展示去重数。 */
  record_count: number;
  reference_admission: AdmissionSummaryReference | null;
}

export interface CollegeAdmissionSummary {
  school_id: number;
  context: {
    source_province: string;
    main_year: number;
    category: string;
    batch: string | null;
    candidate_rank: number;
  };
  years: AdmissionSummaryYear[];
}
