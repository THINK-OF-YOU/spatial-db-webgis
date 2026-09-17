import type {
  CollegeMajorPage,
  CollegeMajorQuery,
  StandardMajorPage,
  StandardMajorQuery,
} from "../types/major";
import { request } from "./http";

function buildQuery(query: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return params.toString();
}

export function getCollegeMajors(
  school_id: number,
  query: CollegeMajorQuery,
  signal?: AbortSignal,
) {
  const params = buildQuery({ ...query });
  return request<CollegeMajorPage>(
    `/colleges/${school_id}/majors?${params}`,
    { signal },
  );
}

export function getStandardMajors(
  query: StandardMajorQuery,
  signal?: AbortSignal,
) {
  const params = buildQuery({ ...query });
  return request<StandardMajorPage>(`/majors?${params}`, { signal });
}
