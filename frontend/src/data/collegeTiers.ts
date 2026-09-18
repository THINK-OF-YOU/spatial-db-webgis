/**
 * 高校重点层级展示参考数据。
 *
 * 只用于当前已显示高校的 UI 分组与标签，不参与查询、空间筛选或结果生成。
 * 关联键固定为本项目 college.school_id；未收录学校安全归入 other。
 *
 * 名单来源：
 * - 教育部《“985工程”学校名单》（39 所）
 * - 教育部《“211工程”学校名单》（按当前 college 实体拆分校区后 115 个名称）
 * - 国家留学网公布的教育部等三部委第二轮“双一流”建设高校名单（147 所）
 * - https://www.moe.gov.cn/srcsite/A22/s7065/200612/t20061206_128833.html
 * - https://www.moe.gov.cn/srcsite/A22/s7065/200512/t20051223_82762.html
 * - https://origin-www.csc.edu.cn/article/2363
 *
 * 名单名称先与当前 college.std_name 做精确匹配；上海体育学院更名为上海体育大学
 * 的记录按教育部 2023 年更名函对应同一 school_id；更名依据：
 * https://www.moe.gov.cn/srcsite/A03/s181/202306/t20230616_1064609.html。
 * 未能对应的军事院校不强行写入。
 */
export interface CollegeTierMeta {
  is985: boolean
  is211: boolean
  isDoubleFirstClass: boolean
}

export type CollegeTierGroup = "985" | "211" | "double-first-class" | "other"

export const collegeTiers: Readonly<Record<number, CollegeTierMeta>> = {
  2959: { is985: true, is211: true, isDoubleFirstClass: true },
  2960: { is985: true, is211: true, isDoubleFirstClass: true },
  2961: { is985: true, is211: true, isDoubleFirstClass: true },
  2962: { is985: false, is211: true, isDoubleFirstClass: true },
  2963: { is985: false, is211: true, isDoubleFirstClass: true },
  2964: { is985: true, is211: true, isDoubleFirstClass: true },
  2965: { is985: true, is211: true, isDoubleFirstClass: true },
  2966: { is985: false, is211: true, isDoubleFirstClass: true },
  2968: { is985: false, is211: true, isDoubleFirstClass: true },
  2971: { is985: false, is211: true, isDoubleFirstClass: true },
  2976: { is985: true, is211: true, isDoubleFirstClass: true },
  2978: { is985: false, is211: true, isDoubleFirstClass: true },
  2979: { is985: false, is211: false, isDoubleFirstClass: true },
  2981: { is985: false, is211: true, isDoubleFirstClass: true },
  2982: { is985: true, is211: true, isDoubleFirstClass: true },
  2983: { is985: false, is211: false, isDoubleFirstClass: true },
  2985: { is985: false, is211: true, isDoubleFirstClass: true },
  2988: { is985: false, is211: true, isDoubleFirstClass: true },
  2989: { is985: false, is211: true, isDoubleFirstClass: true },
  2990: { is985: false, is211: true, isDoubleFirstClass: true },
  2994: { is985: false, is211: false, isDoubleFirstClass: true },
  2995: { is985: false, is211: false, isDoubleFirstClass: true },
  2997: { is985: false, is211: true, isDoubleFirstClass: true },
  2998: { is985: false, is211: true, isDoubleFirstClass: true },
  2999: { is985: false, is211: false, isDoubleFirstClass: true },
  3000: { is985: false, is211: false, isDoubleFirstClass: true },
  3001: { is985: false, is211: false, isDoubleFirstClass: true },
  3005: { is985: true, is211: true, isDoubleFirstClass: true },
  3006: { is985: false, is211: true, isDoubleFirstClass: true },
  3007: { is985: false, is211: true, isDoubleFirstClass: true },
  3015: { is985: false, is211: true, isDoubleFirstClass: true },
  3016: { is985: false, is211: true, isDoubleFirstClass: true },
  3017: { is985: false, is211: true, isDoubleFirstClass: true },
  3049: { is985: false, is211: false, isDoubleFirstClass: true },
  3052: { is985: true, is211: true, isDoubleFirstClass: true },
  3053: { is985: true, is211: true, isDoubleFirstClass: true },
  3055: { is985: false, is211: false, isDoubleFirstClass: true },
  3059: { is985: false, is211: true, isDoubleFirstClass: true },
  3060: { is985: false, is211: false, isDoubleFirstClass: true },
  3111: { is985: false, is211: true, isDoubleFirstClass: true },
  3239: { is985: false, is211: false, isDoubleFirstClass: true },
  3242: { is985: false, is211: true, isDoubleFirstClass: true },
  3321: { is985: false, is211: true, isDoubleFirstClass: true },
  3375: { is985: false, is211: true, isDoubleFirstClass: true },
  3376: { is985: true, is211: true, isDoubleFirstClass: true },
  3380: { is985: true, is211: true, isDoubleFirstClass: true },
  3386: { is985: false, is211: true, isDoubleFirstClass: true },
  3489: { is985: true, is211: true, isDoubleFirstClass: true },
  3490: { is985: false, is211: true, isDoubleFirstClass: true },
  3498: { is985: false, is211: true, isDoubleFirstClass: true },
  3557: { is985: true, is211: true, isDoubleFirstClass: true },
  3559: { is985: false, is211: true, isDoubleFirstClass: true },
  3564: { is985: false, is211: true, isDoubleFirstClass: true },
  3565: { is985: false, is211: true, isDoubleFirstClass: true },
  3637: { is985: true, is211: true, isDoubleFirstClass: true },
  3638: { is985: true, is211: true, isDoubleFirstClass: true },
  3639: { is985: true, is211: true, isDoubleFirstClass: true },
  3640: { is985: false, is211: true, isDoubleFirstClass: true },
  3643: { is985: false, is211: true, isDoubleFirstClass: true },
  3647: { is985: false, is211: false, isDoubleFirstClass: true },
  3648: { is985: false, is211: false, isDoubleFirstClass: true },
  3649: { is985: true, is211: true, isDoubleFirstClass: true },
  3651: { is985: false, is211: true, isDoubleFirstClass: true },
  3652: { is985: false, is211: true, isDoubleFirstClass: true },
  3657: { is985: false, is211: false, isDoubleFirstClass: true },
  3658: { is985: false, is211: false, isDoubleFirstClass: true },
  3660: { is985: false, is211: true, isDoubleFirstClass: true },
  3698: { is985: false, is211: false, isDoubleFirstClass: true },
  3706: { is985: true, is211: true, isDoubleFirstClass: true },
  3707: { is985: false, is211: true, isDoubleFirstClass: true },
  3708: { is985: true, is211: true, isDoubleFirstClass: true },
  3709: { is985: false, is211: true, isDoubleFirstClass: true },
  3710: { is985: false, is211: true, isDoubleFirstClass: true },
  3712: { is985: false, is211: true, isDoubleFirstClass: true },
  3715: { is985: false, is211: false, isDoubleFirstClass: true },
  3716: { is985: false, is211: true, isDoubleFirstClass: true },
  3717: { is985: false, is211: true, isDoubleFirstClass: true },
  3718: { is985: false, is211: false, isDoubleFirstClass: true },
  3720: { is985: false, is211: false, isDoubleFirstClass: true },
  3723: { is985: false, is211: true, isDoubleFirstClass: true },
  3724: { is985: false, is211: false, isDoubleFirstClass: true },
  3726: { is985: false, is211: false, isDoubleFirstClass: true },
  3727: { is985: false, is211: true, isDoubleFirstClass: true },
  3728: { is985: false, is211: true, isDoubleFirstClass: true },
  3879: { is985: true, is211: true, isDoubleFirstClass: true },
  3896: { is985: false, is211: false, isDoubleFirstClass: true },
  3907: { is985: false, is211: false, isDoubleFirstClass: true },
  3990: { is985: false, is211: true, isDoubleFirstClass: true },
  3991: { is985: true, is211: true, isDoubleFirstClass: true },
  3992: { is985: false, is211: true, isDoubleFirstClass: true },
  4116: { is985: true, is211: true, isDoubleFirstClass: true },
  4118: { is985: false, is211: true, isDoubleFirstClass: true },
  4206: { is985: false, is211: true, isDoubleFirstClass: true },
  4324: { is985: true, is211: true, isDoubleFirstClass: true },
  4325: { is985: true, is211: true, isDoubleFirstClass: true },
  4327: { is985: false, is211: true, isDoubleFirstClass: true },
  4496: { is985: false, is211: true, isDoubleFirstClass: true },
  4507: { is985: false, is211: false, isDoubleFirstClass: true },
  4675: { is985: true, is211: true, isDoubleFirstClass: true },
  4676: { is985: true, is211: true, isDoubleFirstClass: true },
  4680: { is985: false, is211: true, isDoubleFirstClass: true },
  4683: { is985: false, is211: true, isDoubleFirstClass: true },
  4685: { is985: false, is211: true, isDoubleFirstClass: true },
  4687: { is985: false, is211: true, isDoubleFirstClass: true },
  4694: { is985: false, is211: true, isDoubleFirstClass: true },
  4809: { is985: false, is211: false, isDoubleFirstClass: true },
  4811: { is985: true, is211: true, isDoubleFirstClass: true },
  4812: { is985: true, is211: true, isDoubleFirstClass: true },
  4818: { is985: false, is211: true, isDoubleFirstClass: true },
  4955: { is985: true, is211: true, isDoubleFirstClass: true },
  4956: { is985: false, is211: true, isDoubleFirstClass: true },
  4958: { is985: true, is211: true, isDoubleFirstClass: true },
  4959: { is985: false, is211: false, isDoubleFirstClass: true },
  4961: { is985: false, is211: false, isDoubleFirstClass: true },
  4963: { is985: false, is211: false, isDoubleFirstClass: true },
  4965: { is985: false, is211: true, isDoubleFirstClass: true },
  5084: { is985: false, is211: false, isDoubleFirstClass: true },
  5122: { is985: false, is211: true, isDoubleFirstClass: true },
  5213: { is985: false, is211: true, isDoubleFirstClass: true },
  5242: { is985: true, is211: true, isDoubleFirstClass: true },
  5246: { is985: false, is211: true, isDoubleFirstClass: true },
  5319: { is985: true, is211: true, isDoubleFirstClass: true },
  5320: { is985: false, is211: true, isDoubleFirstClass: true },
  5321: { is985: true, is211: true, isDoubleFirstClass: true },
  5322: { is985: false, is211: false, isDoubleFirstClass: true },
  5323: { is985: false, is211: false, isDoubleFirstClass: true },
  5329: { is985: false, is211: true, isDoubleFirstClass: true },
  5332: { is985: false, is211: false, isDoubleFirstClass: true },
  5342: { is985: false, is211: true, isDoubleFirstClass: true },
  5462: { is985: false, is211: true, isDoubleFirstClass: true },
  5541: { is985: false, is211: true, isDoubleFirstClass: true },
  5634: { is985: false, is211: true, isDoubleFirstClass: true },
  5640: { is985: false, is211: true, isDoubleFirstClass: true },
  5641: { is985: true, is211: true, isDoubleFirstClass: true },
  5642: { is985: true, is211: true, isDoubleFirstClass: true },
  5644: { is985: false, is211: true, isDoubleFirstClass: true },
  5651: { is985: false, is211: true, isDoubleFirstClass: true },
  5652: { is985: true, is211: true, isDoubleFirstClass: true },
  5654: { is985: false, is211: true, isDoubleFirstClass: true },
  5737: { is985: true, is211: true, isDoubleFirstClass: true },
  5785: { is985: false, is211: true, isDoubleFirstClass: true },
  5798: { is985: false, is211: true, isDoubleFirstClass: true },
  5822: { is985: false, is211: true, isDoubleFirstClass: true },
  5825: { is985: false, is211: true, isDoubleFirstClass: true },
}

const EMPTY_META: CollegeTierMeta = Object.freeze({
  is985: false,
  is211: false,
  isDoubleFirstClass: false,
})

export function getCollegeTierMeta(schoolId: number): CollegeTierMeta {
  return collegeTiers[schoolId] ?? EMPTY_META
}

export function getCollegeTierGroup(schoolId: number): CollegeTierGroup {
  const meta = getCollegeTierMeta(schoolId)
  if (meta.is985) return "985"
  if (meta.is211) return "211"
  if (meta.isDoubleFirstClass) return "double-first-class"
  return "other"
}

export function getCollegeTierLabels(schoolId: number): string[] {
  const meta = getCollegeTierMeta(schoolId)
  return [
    meta.is985 ? "985" : "",
    meta.is211 ? "211" : "",
    meta.isDoubleFirstClass ? "双一流" : "",
  ].filter(Boolean)
}
