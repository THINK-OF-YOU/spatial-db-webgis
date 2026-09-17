# 专业 API 对接文档（前端照这份写）

> 适用对象：**前端**。后端实现见 `backend/app/api/majors.py` +
> `backend/app/services/major_service.py`（莫炜钧）。
>
> 本文只讲**新增的三个专业接口**（11 / 12 / 13）。接口 1–10 见
> `docs/01_接口样例.md`。所有报文都是**实测抓的**（`gaokao3`，2026-09-17），
> 不是手写的。
>
> 环境：`export BASE=http://127.0.0.1:8000`

---

## 0. 先看这一段，否则下面全白看

专业数据有**两层，是两个不同的概念**。名字里都带"专业"，但不是一个东西：

| | 叫什么 | 长什么样 | 覆盖多少条录取记录 |
|---|---|---|---|
| 第一层 | **来源招生专业表达** | `计算机科学与技术（创新实验班）`、`工科试验班（信息类）` | **98.62%** |
| 第二层 | **标准专业** | `计算机科学与技术`（教育部专业目录，代码 `080901`） | **37.80%** |

第二层是第一层**归一化**之后的结果，而这一轮只入库了 **Tier 1 精确映射**，
所以六成以上的记录**没有**第二层。

### ⚠️ 由此推出前端最重要的一条纪律

> **未建立标准映射 ≠ 该校没有这个专业。**

一条记录 `std_major` 是 `null`，只说明它的来源专业名没被规则 v1 精确归一，
**专业本身是实打实存在的、分数和位次也是真的**。所以：

- ✅ `std_major` 为 `null` 的行**照常渲染**，标签写「来源专业名，未归一」
- ❌ **不要**写成「无专业」「未知专业」
- ❌ **不要**把这行隐藏掉
- ❌ 按标准专业筛选后条数变少时，**不要**说「该校只有这几个专业」

接口已经按这个原则做了：不加筛选时，两层都会返回，`std_major` 为 `null`
的行**不会被丢掉**（有冒烟测试守着这条）。

---

## 1. 三个接口总览

| # | 接口 | 干什么 | 什么时候调 |
|---|---|---|---|
| 11 | `GET /api/colleges/{school_id}/majors` | 某高校招哪些专业、分数多少 | 用户点开一所高校的「专业」页签 |
| 12 | `GET /api/majors` | 标准专业目录（搜索框用） | 渲染「按标准专业筛选」输入框时 |
| 13 | `GET /api/majors/{major_id}/colleges` | 招这个标准专业的**高校** | 用户选了一个标准专业，想看有哪些学校 |

**典型串联**：详情页（接口 2）→ 看 `data_availability.major_admission` 决定
要不要显示「专业」页签 → 调 11 拉列表；用户想按标准专业筛 → 调 12 拿
`major_id` → 回头调 11 带 `std_major_id`，或调 13 换成看学校。

---

## 2. 接口 11：某高校的招生专业

```
GET /api/colleges/{school_id}/majors
```

### 请求参数

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `school_id` | path `int` | 必填 | 高校 id |
| `source_province` | `string` | 不限 | 生源省，**来源原始口径**（如 `上海`、`内蒙`） |
| `year` | `int` | 不限 | 2000–2100 |
| `category` | `string` | 不限 | 科类/选科，**来源原始口径**（如 `综合`、`物理类`） |
| `batch` | `string` | 不限 | 批次，**来源原始口径**（如 `本科批`、`本科批B段`） |
| `std_major_id` | `int` | 不限 | 按标准专业筛。⚠️ **只覆盖 37.80%**，见 §5 |
| `mapping` | `string` | 不限 | `all` / `mapped` / `unmapped`，其他值 → **422** |
| `q` | `string` | 不限 | 模糊匹配来源专业名**或**标准专业名 |
| `page` | `int` | `1` | ≥1 |
| `page_size` | `int` | `20` | 1–100 |

> 下拉框的值请从 `GET /api/meta/filters` 取真实值，**不要硬编码**。
>
> **专业接口可以复用 `filters` 的下拉项**——实测两个事实表的来源口径完全一致
> （2026-09-17 比对，且双向差集为空）：
>
> | 维度 | `school_admission` | `major_admission` |
> |---|---:|---:|
> | `category` | 17 | 17 |
> | `batch` | 174 | 174 |
> | `source_province` | 30 | 30 |
> | `year` | 3（2023/2024/2025） | 3 |
>
> 所以「投档」和「专业」两个页签可以共用同一套筛选器状态，不用各拉一份元数据。

### 响应信封

```json
{
  "items": [ ... ],
  "total": 4435,
  "page": 1,
  "page_size": 2,
  "warnings": [],
  "display_deduplicated": true,
  "facts_without_major_name": 46
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `total` | `int` | 精确展示合并**之后**的条数（前端分页用它） |
| `display_deduplicated` | `bool` | 是否对**全部展示字段完全一致**的记录做了精确合并。**这只是在做去重，不是数据库改数据**，可以直接忽略 |
| `facts_without_major_name` | `int` | 该校另有几条录取记录**来源根本没给专业名**（全库 22,325 条）。这些行不会出现在 `items` 里——一行没有专业名的记录渲染出来就是一行空白。建议在列表底部提示一句：`另有 46 条录取记录来源未提供专业名` |

`facts_without_major_name` **只按学校统计，不随其他筛选条件变化**。这样同一个
数字不会在不同筛选下忽大忽小。

### `items[]` 元素字段（恰好 14 个）

| 字段 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `raw_major_name` | `string` | 否 | **第一层：来源招生专业表达**。恒有值 |
| `norm_name` | `string` | 是 | 归一化名。`UNRESOLVED` 时可能等于原名或为 `null` |
| `std_status` | `string` | 否 | `MAPPED` / `UNMAPPED` / `UNRESOLVED`，见下 |
| `std_major` | `object \| null` | **是** | **第二层：标准专业**。`null` 不代表没这个专业！ |
| `source_province` | `string` | 是 | 生源省，来源口径 |
| `year` | `int` | 是 | 年份 |
| `category` | `string` | 是 | 科类，来源口径 |
| `batch` | `string` | 是 | 批次，来源口径 |
| `subject_req` | `string` | 是 | 选科要求，来源口径（如 `首选物理，再选化学`） |
| `min_score` | `float` | 是 | 最低分 |
| `max_score` | `float` | 是 | 最高分 |
| `avg_score` | `float` | 是 | 平均分 |
| `min_rank` | `int` | 是 | 最低位次 |
| `admit_count` | `int` | 是 | 录取人数 |

> **缺失一律是 `null`，不是 `0`。** 前端判断用 `x === null`，
> **不要**用 `!x`——`admit_count` 为 `0` 和不适用是两回事。

`std_major` 对象（**只有非 null 时才有**）：

```json
{
  "major_id": 2294,
  "std_code": "080901",
  "std_name": "计算机科学与技术",
  "education_level": "本科"
}
```

### `std_status` 三个取值

| 值 | 含义 | 前端建议 |
|---|---|---|
| `MAPPED` | 已精确归一到标准专业，`std_major` **非 null** | 正常显示标准专业名，可加副标题写来源名 |
| `UNMAPPED` | 来源专业名归一了，但**没能精确对上**标准专业目录 | 显示来源名 + 「未归入标准专业」 |
| `UNRESOLVED` | 来源专业名连归一都没做成 | 显示来源名 + 「未归一」 |

`std_status` 与 `std_major` 的关系是**确定的**：`MAPPED` ⟺ `std_major != null`。
两者不一致就是 bug，见 §6。

### 实测样例

`GET /api/colleges/5334/majors?page_size=3`（四川师范大学）

```json
{
  "items": [
    {
      "raw_major_name": "会计学",
      "norm_name": "会计学",
      "std_status": "UNRESOLVED",
      "std_major": null,
      "source_province": "上海",
      "year": 2025,
      "category": "综合",
      "batch": "本科批",
      "subject_req": "不限",
      "min_score": 488.0,
      "max_score": null,
      "avg_score": 491.0,
      "min_rank": 27683,
      "admit_count": 2
    }
  ],
  "total": 4435,
  "page": 1,
  "page_size": 3,
  "warnings": [],
  "display_deduplicated": true,
  "facts_without_major_name": 46
}
```

注意上面这条：`std_major` 是 `null`，但 `min_score=488`、`min_rank=27683`
都是真的。**这就是那 62% 的样子，必须照常渲染。**

已建立映射的（`GET /api/colleges/5334/majors?std_major_id=2294&page_size=1`）：

```json
{
  "items": [
    {
      "raw_major_name": "计算机科学与技术",
      "norm_name": "计算机科学与技术",
      "std_status": "MAPPED",
      "std_major": {
        "major_id": 2294,
        "std_code": "080901",
        "std_name": "计算机科学与技术",
        "education_level": "本科"
      },
      "source_province": "云南",
      "year": 2025,
      "category": "物理类",
      "batch": "本科批B段",
      "subject_req": "首选物理，再选化学",
      "min_score": 573.0,
      "max_score": null,
      "avg_score": null,
      "min_rank": 20029,
      "admit_count": null
    }
  ],
  "total": 22,
  "warnings": ["按标准专业筛选仅覆盖已建立精确映射的录取记录，未建立映射不代表该校未招该专业"]
}
```

**对照着看**：同一所学校，不加筛选 `total=4435`，按标准专业筛 `total=22`。
差额 4413 条**不是"没有"**，是"规则没归一"。这个对比就是 §0 那条纪律的由来。

---

## 3. 接口 12：标准专业目录

```
GET /api/majors
```

字典表，全表 **1,874 行 / 1,711 个专业名**，**与高校无关**。
用途：做「按标准专业筛选」的搜索框 / 下拉。拿到 `major_id` 再传给接口 11 或 13。

| 参数 | 类型 | 说明 |
|---|---|---|
| `q` | `string` | 模糊匹配**专业名**或**专业代码**（`计算机` 命中 `计算机科学与技术`；`080901` 也命中） |
| `education_level` | `string` | 库里真实取值**只有三个**：`本科`(883) / `专科`(744) / `职业本科`(247) |
| `discipline` | `string` | 学科门类，178 种，如 `计算机类` |
| `category` | `string` | 专业大类，32 种，如 `工学` |
| `page` / `page_size` | `int` | 默认 1 / 20，上限 100 |

响应元素 **7 个字段**：

```json
{
  "major_id": 2294,
  "std_code": "080901",
  "std_name": "计算机科学与技术",
  "education_level": "本科",
  "discipline": "计算机类",
  "category": "工学",
  "catalog_version": "2026"
}
```

> `discipline`（学科门类/专业类）和 `category`（专业大类）**两个字段名字
> 容易搞反**：库里的取值是 `discipline='计算机类'`、`category='工学'`。
> 按库里原值用，别按名字猜。

实测 `GET /api/majors?q=计算机&page_size=3`：

```json
{
  "items": [
    {"major_id": 2294, "std_code": "080901",  "std_name": "计算机科学与技术", "education_level": "本科",     "discipline": "计算机类", "category": "工学",           "catalog_version": "2026"},
    {"major_id": 2302, "std_code": "080909T", "std_name": "电子与计算机工程", "education_level": "本科",     "discipline": "计算机类", "category": "工学",           "catalog_version": "2026"},
    {"major_id": 2895, "std_code": "310201",  "std_name": "计算机应用工程",   "education_level": "职业本科", "discipline": "计算机类", "category": "电子与信息大类", "catalog_version": "2021"}
  ],
  "total": 5,
  "page": 1,
  "page_size": 3,
  "warnings": []
}
```

**注意 `education_level` 有三种**，同一个专业名在本科和职业本科下是**两条不同记录**
（`major_id` 不同）。做下拉时不要把 `职业本科` 漏了。

**`catalog_version` 与 `education_level` 是绑定的**（实测，不是巧合）：

| `catalog_version` | `education_level` | 行数 |
|---|---|---|
| `2026` | 本科 | 883 |
| `2021` | 专科 | 744 |
| `2021` | 职业本科 | 247 |

即本科目录用的是 2026 版，专科/职业本科用的是 2021 版。前端如果要显示
"目录版本"，按 `education_level` 决定即可，不用逐行渲染。

---

## 4. 接口 13：招这个标准专业的高校

```
GET /api/majors/{major_id}/colleges
```

| 参数 | 类型 | 说明 |
|---|---|---|
| `major_id` | path `int` | 来自接口 12。不存在 → **404** |
| `source_province` / `year` / `category` / `batch` | | 同接口 11，全部可选 |
| `page` / `page_size` | `int` | 默认 1 / 20 |

响应比标准信封多一个 `std_major`（把查的是哪个专业回给你，省得前端名字对不上
还看不出来）：

```json
{
  "items": [
    {"school_id": 3719, "national_code": "4132010299", "name": "江苏大学",         "edu_level": "本科", "reg_province": "镇江市", "fact_count": 49},
    {"school_id": 3308, "national_code": "4114014527", "name": "山西工程技术学院", "edu_level": "本科", "reg_province": "阳泉市", "fact_count": 48},
    {"school_id": 5785, "national_code": "4163010743", "name": "青海大学",         "edu_level": "本科", "reg_province": "西宁市", "fact_count": 48}
  ],
  "total": 778,
  "std_major": {
    "major_id": 2294, "std_code": "080901", "std_name": "计算机科学与技术",
    "education_level": "本科", "discipline": "计算机类",
    "category": "工学", "catalog_version": "2026"
  },
  "warnings": ["按标准专业筛选仅覆盖已建立精确映射的录取记录，未建立映射不代表该校未招该专业"]
}
```

- `total` 是**高校数**（去重后的 `school_id`），`items` 里每校一行
- `fact_count` 是该校这个专业下的**录取事实条数**（用来排序的量级参考）。
  **不是招生人数**——招生人数是 `admit_count`，按省/年/批次分行在接口 11 里给
- `reg_province` 里装的是**市名**（`镇江市`），不是省名。这是库里原值，
  按原值用

### ⚠️ 这个接口必须带警告展示

它是纯 Tier 1 查询，**天生只覆盖 37.80%**。查到 778 所**不代表**全国只有
778 所招计算机科学与技术。**不要**把标题写成「开设该专业的全部高校」，
建议写「已归入该标准专业的高校（覆盖部分录取记录）」并把 `warnings` 显示出来。

---

## 5. warnings 怎么处理

**前端只负责展示，不自己编文案。** 把 `warnings[]` 里的字符串原样显示即可
（这是全组约定，见 `docs/00_协作规范.md` §5.4）。

专业接口会出现的两类：

| 文案 | 何时出现 |
|---|---|
| `按标准专业筛选仅覆盖已建立精确映射的录取记录，未建立映射不代表该校未招该专业` | 接口 11 传了 `std_major_id` 时；接口 13 **无条件**出现 |
| `当前科类/批次使用来源数据原始口径` | 传了 `category` 或 `batch` 时（和接口 3/9 同一条） |

> 第一条是 2026-09-17 随专业接口一并**经全组确认**的第 6 类文案，已冻结。
> 前端按上面的约定**原样展示**即可，不要自己改写或省略。
> 若日后文案有变，后端改 `warnings.py` 一个常量，前端不用动。

---

## 6. 错误处理

| 情况 | 返回 |
|---|---|
| `mapping` 传了 `all`/`mapped`/`unmapped` 之外的值 | **422** `{"detail": "mapping 只允许 ['all', 'mapped', 'unmapped']，收到 'bogus'"}` |
| 接口 13 的 `major_id` 不存在 | **404** `{"detail": "未找到 major_id=999999999 的标准专业"}` |
| 接口 11 的 `school_id` 不存在 | **200，空列表**（`total=0`）——**不是 404** |
| `page_size > 100` / `page < 1` | **422** |

> ⚠️ **两个接口口径不同**：专业不存在 → 404；高校不存在 → 空列表。
> 高校不存在请靠**接口 2**（`GET /api/colleges/{id}`）的 404 发现，
> 别指望接口 11 报错。这与已有的 `/admissions` 保持一致。

---

## 7. 详情页要改的一处（重要）

`GET /api/colleges/{school_id}` 的 `data_availability` **从 3 个键变成了 4 个**：

```json
"data_availability": {
  "campus": false,
  "school_admission": true,
  "major_admission": true,
  "major_mapping": false
}
```

| 键 | 含义 | 前端拿它决定什么 |
|---|---|---|
| `school_admission` | 有没有投档录取记录 | 「投档」页签显不显示 |
| `campus` | 有没有带几何的校区 | 地图/周边交通能不能用 |
| **`major_admission`** | 有没有**专业录取事实** | **「专业」页签显不显示** |
| **`major_mapping`** | 有没有**已建立标准映射**的事实 | 「按标准专业筛」能不能用、要不要提前提示覆盖 |

### 为什么要拆成两个

全库 2,952 所高校里 **2,747 所有专业事实，但只有 2,586 所有 Tier 1 映射**。

如果只用 `major_mapping` 一个键，那 161 所「有专业、没映射」的学校会在前端
**被整个藏掉专业视图**——可它们明明有专业。实测例子：

```json
// GET /api/colleges/3877  西交利物浦大学：638 条专业事实，零条映射
"data_availability": {"campus": false, "school_admission": true,
                      "major_admission": true, "major_mapping": false}
```

这所学校 `major_admission=true` → 专业页签**要显示**（`total=596` 条）；
`major_mapping=false` → 按标准专业筛**筛不出东西**，此时应提示用户
「该校专业数据尚未归入标准专业，暂不支持按标准专业筛选」。

### 前端建议写法

```js
// 页签显不显示，只看 major_admission
const showMajorTab = data.data_availability.major_admission

// 页签内部，「按标准专业筛」这个控件能不能用，看 major_mapping
const canFilterByStdMajor = data.data_availability.major_mapping
```

---

## 8. 现在**还没有**的东西，别等

| 东西 | 状态 |
|---|---|
| **专业组** | ❌ 没入库。实测（2026-09-17）：`major_admission.group_id` 全库 **1,617,315 行全是 `NULL`**，`admission_major_group` **0 行**、`group_expr` **0 行**。三个接口**一个专业组字段都不返回**。UI 上先不要做专业组 |
| 专业组相关的筛选 | ❌ 同上 |
| 标准专业的模糊匹配（第二层） | ⚠️ 只有 Tier 1 **精确**映射，没有模糊/人工映射。所以 `std_major` 有 62% 是 `null`，这是**数据现状**不是接口 bug |
| `major` 目录的权威性 | ⚠️ 全表 `status='candidate_baseline'`，即**候选基线**，不是冻结的官方版本。这个字段**不对外返回**（逐行给前端一个内部 QC 标记没意义）。目录版本见 §3 的 `catalog_version` |

---

## 9. 冒烟测试守着的几条（改前端时心里有数）

`backend/smoke_test.py` 里对这三个接口有三十多项断言（全套 96 项），
其中这几条是专门防回归的：

1. **`mapped + unmapped` 恰好等于不筛时的 `total`** —— 证明没有一条记录被丢掉
2. **`mapping=unmapped` 返回的行 `std_major` 是 `null` 但 `raw_major_name` 有值**
3. **按标准专业筛必定带覆盖警告**
4. **`data_availability` 恰好 4 个键**，且 3877 是 `(true, false)`、5334 是 `(true, true)`
5. **接口 11 的元素恰好 14 个字段**，多一个少一个都算失败

跑法（在 `backend/` 下）：`./.venv/Scripts/python.exe smoke_test.py`

---

## 10. 变更记录

| 日期 | 变更 | 影响前端 |
|---|---|---|
| 2026-09-17 | 新增接口 11 / 12 / 13 | 新增专业视图 |
| 2026-09-17 | `data_availability` 3 键 → **4 键**（新增 `major_admission`） | **详情页要改**，见 §7 |
| 2026-09-17 | `warnings` 新增第 6 类文案 | 原样展示即可，见 §5 |

> 专业接口是 2026-09-17 **全组确定**的新增范围，不受《任务执行书》原有条款
> （§4.3 的 `major_mapping: false` 示例、附录 B 第三条对 MajorAdmission 的限制）
> 约束——那些是专业语义链入库**之前**定的。执行书会在下一轮补齐 §4.13–4.15，
> 属于事后追认，不影响本文实现。若补齐后与本文有出入，**以本文为准并回来改契约**，
> 因为本文的报文都是实测的。

---

## 附：30 秒自测

```bash
export BASE=http://127.0.0.1:8000

# 有专业、有映射的学校（四川师范大学）
curl "$BASE/api/colleges/5334/majors?page_size=3"

# 有专业、零映射的学校（西交利物浦大学）—— 专业页签仍要显示
curl "$BASE/api/colleges/3877/majors?page_size=3"

# 只有未归一的那些（应该看到 std_major 全是 null）
curl "$BASE/api/colleges/5334/majors?mapping=unmapped&page_size=3"

# 标准专业搜索
curl "$BASE/api/majors?q=计算机&page_size=3"

# 反查高校（必带警告）
curl "$BASE/api/majors/2294/colleges?page_size=3"
```
