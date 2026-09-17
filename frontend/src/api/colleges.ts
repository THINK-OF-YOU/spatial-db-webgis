import type {
  CollegeDetail,
  CollegePage,
  CollegeQuery,
} from "../types/college";
import { request } from "./http";

export function getColleges(query: CollegeQuery, signal?: AbortSignal) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return request<CollegePage>(`/colleges?${params}`, { signal });
}

export async function getCollege(school_id: number, signal?: AbortSignal) {
  const response = await request<{ data: CollegeDetail }>(
    `/colleges/${school_id}`,
    { signal },
  );
  return response.data;
}
