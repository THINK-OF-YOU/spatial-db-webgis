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
