# CandidateProfile V2.1 学校级多年度历史参考覆盖率审计

审计日期：2026-09-17  
数据库：`gaokao3`（`127.0.0.1:5432`）  
执行约束：数据库连接 `transaction_read_only=on`；无 INSERT / UPDATE / DELETE / DDL；无业务代码修改。  
固定口径：`main_year = 2025`，全部批次，不做 province/category/batch 映射。

## 1. 口径与方法

### 1.1 Comparable Years

严格复用 CandidateProfile V2.1 当前后端语义：

```text
相同 source_province
+ 相同 category
+ year IS NOT NULL
+ year <= 2025
→ 全库 DISTINCT year
```

Comparable Years 来自全库考试上下文，不来自单个 College。

### 1.2 年度状态

- `reference_available`：该校、该严格上下文、该年存在至少一条 `SchoolAdmission.min_rank IS NOT NULL`。
- `rank_unavailable`：该年存在真实 SchoolAdmission，但所有 `min_rank` 均为 NULL。
- `no_record`：该 Comparable Year 下该校没有严格上下文记录。

### 1.3 School-Context 分母

报告给出两套互补口径：

1. **全量产品口径（主结论）**：2,952 个 College × 155 个真实考试上下文，共 **457,560** 个 School-Context。该口径对应用户可选择任意 College 和任意数据库真实上下文时的产品覆盖面。
2. **Observed 口径（补充）**：只保留 `year <= 2025` 内至少存在过一条 SchoolAdmission 的 College × context，共 **91,425** 个。该口径用于观察“已有该校该上下文数据”后的多年连续性。

两套口径都没有删除 Comparable Years 中的 `no_record` 年份。全量口径是本报告对“真实产品覆盖率”的主回答。

## 2. Context-Level 审计

共有 **155** 个严格 `source_province + category` 上下文。

| Comparable Years 数 | 上下文数 | 占 155 个上下文 |
|---:|---:|---:|
| 1 年 | 83 | 53.5484% |
| 2 年 | 48 | 30.9677% |
| 3 年及以上 | 24 | 15.4839% |

当前数据中“3 年及以上”实际均为 3 年。83 个单年上下文又分为：仅 2023 年 42 个、仅 2024 年 12 个、仅 2025 年 29 个。

29 个仅有 2025 的上下文覆盖 85,608 个全量 College-Context；其中 8,931 个为 observed 组合，8,901 个有 1 年 reference，30 个为 0 年 reference。高体量示例包括：

- 内蒙 / 物理类：`[2025]`，1,387 个 observed School-Context。
- 内蒙 / 历史类：`[2025]`，1,206 个。
- 河南 / 物理类：`[2025]`，595 个。
- 云南 / 物理类：`[2025]`，583 个。
- 四川 / 物理类：`[2025]`，567 个。
- 江西 / 物理类：`[2025]`，563 个。
- 四川 / 历史类：`[2025]`，487 个。

完整 155 个上下文见 `v2_1_context_coverage.csv`。

## 3. 全国 School-Level 核心统计

### 3.1 全量产品口径（457,560）

| reference_available 年数 | School-Context 数 | 占比 |
|---:|---:|---:|
| >= 3 年 | 11,584 | 2.5317% |
| = 2 年 | 27,582 | 6.0281% |
| = 1 年 | 42,063 | 9.1929% |
| = 0 年 | 376,331 | 82.2474% |

- **真正 >=2 年 reference_available：39,166 / 457,560 = 8.5598%。**
- **真正只有 1 年 reference_available：42,063 / 457,560 = 9.1929%。**
- 平均 `comparable_year_count`：**1.6194**。
- 平均 `reference_available_year_count`：**0.2884**。

### 3.2 Observed 补充口径（91,425）

| reference_available 年数 | Observed School-Context 数 | 占比 |
|---:|---:|---:|
| >= 3 年 | 11,584 | 12.6705% |
| = 2 年 | 27,582 | 30.1690% |
| = 1 年 | 42,063 | 46.0082% |
| = 0 年 | 10,196 | 11.1523% |

- 至少 2 年：**42.8395%**。
- 平均 Comparable Years：**1.9564**。
- 平均 reference_available 年数：**1.4436**。

全量与 observed 的非零分档数量相同；差异来自全量口径额外纳入了 **366,135** 个在该 College-Context 下从未出现 SchoolAdmission 的组合。

## 4. “只有 1 年”成因量化

42,063 个只有 1 年 reference 的 School-Context 可互斥拆分为：

| 主要成因 | 数量 | 占“只有 1 年”的比例 | 定义 |
|---|---:|---:|---|
| A. Context 本身只有 1 个 Comparable Year | 24,806 | 58.9734% | 没有第二个可比较年份 |
| B. Context 有多年，但具体学校其他年份无记录 | 14,083 | 33.4807% | `comparable_year_count > 1` 且其他缺失年全为 `no_record` |
| C. Context 有多年，且至少一个年份 min_rank 全缺失 | 3,174 | 7.5458% | 至少出现一个 `rank_unavailable`；可同时伴随 `no_record` |

在 B/C 对应的多年度单参考组合中，共有 24,452 个“未形成 reference”的年份槽位：

- `no_record`：20,676，**84.5575%**。
- `rank_unavailable`：3,776，**15.4425%**。

结论：单年度退化首先由上下文本身只有一个年份造成，其次是学校历史记录不连续；`min_rank` 缺失是较小但仍可量化的第三因素。

## 5. 省份 / 科类差异

### 5.1 最适合展示三年度能力的上下文

下表均为 Comparable Years `[2023, 2024, 2025]`。全量占比以 2,952 个 College 为分母，Observed 占比只以该上下文出现过事实的学校为分母。

| Context | >=3 年数量 | 全量 >=3 年占比 | Observed >=3 年占比 |
|---|---:|---:|---:|
| 山东 / 综合 | 1,682 | 56.9783% | 83.2673% |
| 重庆 / 物理类 | 1,405 | 47.5949% | 87.3213% |
| 浙江 / 综合 | 1,391 | 47.1206% | 86.1300% |
| 辽宁 / 物理类 | 1,202 | 40.7182% | 86.8497% |
| 重庆 / 历史类 | 1,109 | 37.5678% | 77.5524% |
| 江苏 / 物理类 | 950 | 32.1816% | 66.2483% |

这些上下文最能稳定展示 V2.1 的 3 年卡片能力。

### 5.2 至少两年度覆盖较好的上下文

| Context | Comparable Years | >=2 年数量 | 全量 >=2 年占比 | Observed >=2 年占比 |
|---|---|---:|---:|---:|
| 贵州 / 物理类 | `[2024, 2025]` | 1,876 | 63.5501% | 92.9173% |
| 四川 / 理科 | `[2023, 2024]` | 1,871 | 63.3808% | 93.1773% |
| 山东 / 综合 | `[2023, 2024, 2025]` | 1,854 | 62.8049% | 91.7822% |
| 河北 / 物理类 | `[2023, 2025]` | 1,819 | 61.6192% | 85.1991% |
| 四川 / 文科 | `[2023, 2024]` | 1,728 | 58.5366% | 90.7563% |
| 浙江 / 综合 | `[2023, 2024, 2025]` | 1,504 | 50.9485% | 93.1269% |

### 5.3 虽有 3 年，但学校多数只有 1 年 reference 的上下文

以下比例使用 observed 分母，避免全无事实的学校干扰“历史连续性”判断：

| Context | Observed 数 | >=2 年数及占比 | =1 年数及占比 | =0 年数 |
|---|---:|---:|---:|---:|
| 广东 / 历史类 | 901 | 55（6.1043%） | 546（60.5993%） | 300 |
| 天津 / 综合 | 934 | 401（42.9336%） | 524（56.1028%） | 9 |
| 福建 / 历史类 | 1,319 | 613（46.4746%） | 633（47.9909%） | 73 |
| 福建 / 物理类 | 1,493 | 755（50.5693%） | 695（46.5506%） | 43 |
| 海南 / 综合 | 1,015 | 556（54.7783%） | 453（44.6305%） | 6 |

广东 / 历史类是最明显的“上下文有 3 年，但学校层面普遍无法形成多年参考”样例。

## 6. 四川 / 2025 / 物理类为何通常只有 2025

真实数据严格值为：

| 四川 category 原值 | DISTINCT years | 记录数 | 学校数 | min_rank 非空数 |
|---|---|---:|---:|---:|
| 物理类 | `[2025]` | 1,124 | 567 | 1,123 |
| 历史类 | `[2025]` | 666 | 487 | 666 |
| 理科 | `[2023, 2024]` | 8,367 | 2,008 | 8,360 |
| 文科 | `[2023, 2024]` | 6,863 | 1,904 | 6,861 |

因此，四川 / 物理类的全库 Comparable Years 本身只有 `[2025]`。2023、2024 的相关旧口径事实存放在严格不同的 `理科` 值下。V2.1 明确规定 `理科 ≠ 物理类`，所以不能跨制度拼接；这不是代表事实选择失败，也不是前端漏展示，而是严格上下文的真实年份集合只有 2025。

## 7. 人工前端验证样例

示例代表事实仅为前端核验使用，统一采用测试 `candidate_rank = 20,000`。代表事实按当前 V2.1 规则选择：`ABS(min_rank - 20000) → min_rank → school_admission.id`。该测试 rank 不参与覆盖率统计。

### 7.1 >=3 年 reference_available

- `school_id=5216`，海南医科大学，海南 / 综合。
- Comparable Years：`[2023, 2024, 2025]`。

| 年份 | status | record_count | representative min_rank |
|---:|---|---:|---:|
| 2025 | reference_available | 12 | 20,421 |
| 2024 | reference_available | 34 | 17,552 |
| 2023 | reference_available | 6 | 10,740 |

### 7.2 恰好 2 年 reference_available

- `school_id=5008`，广东食品药品职业学院，广东 / 历史类。
- Comparable Years：`[2023, 2024, 2025]`。

| 年份 | status | record_count | representative min_rank |
|---:|---|---:|---:|
| 2025 | reference_available | 1 | 51,997 |
| 2024 | reference_available | 1 | 68,261 |
| 2023 | rank_unavailable | 57 | — |

### 7.3 只有 1 年 reference_available

- `school_id=5334`，四川师范大学，四川 / 物理类。
- Comparable Years：`[2025]`。

| 年份 | status | record_count | representative min_rank |
|---:|---|---:|---:|
| 2025 | reference_available | 15 | 14,292 |

### 7.4 reference_available + rank_unavailable 混合状态

- `school_id=4495`，华北水利水电大学，新疆 / 理科。
- Comparable Years：`[2023, 2024, 2025]`。

| 年份 | status | record_count | representative min_rank |
|---:|---|---:|---:|
| 2025 | reference_available | 4 | 18,404 |
| 2024 | rank_unavailable | 2 | — |
| 2023 | rank_unavailable | 2 | — |

### 7.5 reference_available + no_record 补充样例

- `school_id=5654`，陕西师范大学，海南 / 综合。
- Comparable Years：`[2023, 2024, 2025]`。

| 年份 | status | record_count | representative min_rank |
|---:|---|---:|---:|
| 2025 | no_record | 0 | — |
| 2024 | reference_available | 12 | 11,844 |
| 2023 | no_record | 0 | — |

## 8. 产品价值结论

1. 全国全量产品口径下，真正具备 >=2 年 reference 的比例是 **8.5598%**；在已出现过该校该上下文事实的 observed 口径下是 **42.8395%**。
2. 全国全量产品口径下，真正只有 1 年 reference 的比例是 **9.1929%**；observed 口径下是 **46.0082%**。
3. 在“只有 1 年”的组合中，58.9734% 因上下文本身只有一个 Comparable Year，33.4807% 因学校在其他年份无记录，7.5458% 涉及 `min_rank` 全缺失。
4. 四川 / 物理类经常只能看到 2025，是因为严格原值下 Comparable Years 就是 `[2025]`；2023、2024 是不同 category 原值 `理科`，本轮禁止映射。
5. 山东 / 综合、重庆 / 物理类、浙江 / 综合、辽宁 / 物理类、重庆 / 历史类最适合展示 3 年能力；贵州 / 物理类、四川 / 理科等适合展示稳定的 2 年能力。
6. 数据支持的判断是：**V2.1 只在部分省份/科类有明显价值**。它不是全国均匀的多年度能力；但也不能简单概括为所有已观测场景都退化成单年度，因为 observed 组合中仍有 42.8395% 具备至少 2 年 reference。全量产品表面更严峻：82.2474% 的任意 College × context 组合为 0 年 reference。

## 9. 输出与可复现性

- `QA/v2_1_context_coverage.csv`：155 个 context，包含全量与 observed 分母下的分档统计。
- `QA/v2_1_school_context_coverage.csv`：457,560 个全量 College-Context，包含 Comparable Years、三类年度计数和 `observed_context` 标记。
- CSV 使用 UTF-8 BOM，便于 Windows/Excel 直接打开。
- 统计使用一次性内联只读 Python/SQL；未在仓库中保留临时脚本。
-  eligible SchoolAdmission 数为 229,675；符合条件的 `school_admission → school_unit` 孤儿数为 0。

最终状态：`CANDIDATE_PROFILE_V2_1_COVERAGE_AUDIT_COMPLETE`
