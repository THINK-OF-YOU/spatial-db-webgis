import type {
  AdmissionSummaryQuery,
  CollegeAdmissionSummary,
  CollegeAdmissionsPage,
  CollegeAdmissionsQuery,
} from "../types/admission";
import { request } from "./http";

export function getCollegeAdmissions(
  school_id: number,
  query: CollegeAdmissionsQuery,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return request<CollegeAdmissionsPage>(
    `/colleges/${school_id}/admissions?${params.toString()}`,
    { signal },
  );
}

export function getCollegeAdmissionSummary(
  school_id: number,
  query: AdmissionSummaryQuery,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return request<CollegeAdmissionSummary>(
    `/colleges/${school_id}/admissions/summary?${params.toString()}`,
    { signal },
  );
}
