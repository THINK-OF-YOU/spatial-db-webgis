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
  admit_count: number | null;
}

export interface CollegeMajorQuery {
  source_province?: string;
  year?: number;
  category?: string;
  batch?: string;
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
