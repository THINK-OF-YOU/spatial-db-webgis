export type MajorMappingFilter = "all" | "mapped" | "unmapped";
export type MajorStandardStatus = "MAPPED" | "UNMAPPED" | "UNRESOLVED";

export interface StandardMajor {
  major_id: number;
  std_code: string;
  std_name: string;
  education_level: string;
  discipline: string | null;
  category: string | null;
  catalog_version: string | null;
}

export interface MajorAdmissionItem {
  /** CandidateProfile 模式下的来源招生专业表达身份。 */
  expr_id?: number;
  /** CandidateProfile 模式下选中的代表 MajorAdmission。 */
  representative_admission_id?: number;
  unit_id?: number;
  unit_name?: string;
  group_id?: number | null;
  raw_major_name: string;
  norm_name: string | null;
  std_status: MajorStandardStatus;
  std_major: StandardMajor | null;
  source_province: string | null;
  year: number | null;
  category: string | null;
  batch: string | null;
  subject_req: string | null;
  min_score: number | null;
  max_score: number | null;
  avg_score: number | null;
  min_rank: number | null;
  /** professional min_rank - candidate rank；无历史位次时为 null。 */
  professional_rank_gap?: number | null;
  admit_count: number | null;
}

export interface CollegeMajorQuery {
  source_province?: string;
  year?: number;
  category?: string;
  batch?: string;
  candidate_rank?: number;
  std_major_id?: number;
  mapping?: MajorMappingFilter;
  q?: string;
  page: number;
  page_size: number;
}

export interface CollegeMajorPage {
  items: MajorAdmissionItem[];
  total: number;
  page: number;
  page_size: number;
  warnings: string[];
  display_deduplicated: boolean;
  facts_without_major_name: number;
  candidate_profile_applied: boolean;
  candidate_profile: {
    source_province: string;
    year: number;
    category: string;
    batch: string | null;
    rank: number;
  } | null;
}

export interface StandardMajorQuery {
  q?: string;
  education_level?: string;
  discipline?: string;
  category?: string;
  page: number;
  page_size: number;
}

export interface StandardMajorPage {
  items: StandardMajor[];
  total: number;
  page: number;
  page_size: number;
  warnings: string[];
}
