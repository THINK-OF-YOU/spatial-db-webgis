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
