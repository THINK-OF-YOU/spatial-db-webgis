/** 与 College API 的 snake_case 字段直接对应，不含招生查询。 */
export interface College {
  school_id: number;
  national_code: string | null;
  name: string;
  edu_level: string | null;
  reg_province: string | null;
  has_campus: boolean;
  has_admission: boolean;
}

export interface CollegeFilters {
  q?: string;
  edu_level?: string;
  reg_province?: string;
}

export interface CollegeQuery extends CollegeFilters {
  page: number;
  page_size: number;
}

export interface CollegePage {
  items: College[];
  total: number;
  page: number;
  page_size: number;
  warnings: string[];
}

export interface CollegeDetail {
  college: College;
  campuses: {
    campus_id: number;
    campus_name: string | null;
    address: string | null;
    verify_status: "CONFIRMED" | "CANDIDATE";
    lon: number | null;
    lat: number | null;
  }[];
  data_availability: {
    campus: boolean;
    school_admission: boolean;
    enrollment_plan: boolean;
    major_mapping: boolean;
  };
}
