# 辅助补充数据、POI 与评论数据 — 位置与流程

你之前提供的**辅助数据文档/文件夹**对应本项目的 **「辅助补充数据」** 目录，用于解析出 POI 和评论等。下面是数据放哪里、脚本怎么跑、结果在哪。

---

## 一、原始辅助数据放在哪（你提供的）

**目录：** `中期阶段/辅助补充数据/`  
（该目录未上传 GitHub，在 `.gitignore` 中排除。）

建议的**子目录结构**（与解析脚本一致）：

```
辅助补充数据/
├── wenhuadian/           # 南海三镇文化资源普查（2019）
│   ├── 不可移动文物.shp
│   ├── 非遗.shp
│   ├── 文化景观.shp
│   ├── 名镇名村传统村落.shp
│   ├── 圩市街区.shp
│   └── …
├── poi/                  # 佛山市全量 POI shapefile
│   ├── 2024_10/佛山市.shp   # 或 2022_10/佛山市.shp
│   └── …
└── 携程去哪儿马蜂窝评价/   # 三平台旅游评论
    ├── xxx.xlsx          # 马蜂窝/去哪儿/携程格式
    └── …
```

脚本会从上述路径读取，并输出到 `data/` 下（见下一节）。

---

## 二、解析脚本（辅助数据 → 项目标准格式）

**脚本：** `code/data_collection/parse_supplementary_data.py`

**作用：**

1. **Part 1** 文化载体锚点：读 `辅助补充数据/wenhuadian/*.shp` → 写 `data/database/cultural_anchors.json`
2. **Part 2** POI：读 `辅助补充数据/poi/` 下 shapefile → 写 `data/poi/nanhai_culture_poi_shp.json`
3. **Part 3** 评论：读 `辅助补充数据/携程去哪儿马蜂窝评价/*.xlsx` → 写 `data/reviews/merged_reviews_supp.json`

**运行前：** 需安装 `geopandas pandas openpyxl`。  
**运行：** 在项目根或 `code/data_collection` 下执行  
`python parse_supplementary_data.py`

---

## 三、POI 数据最终在哪、怎么来的

| 文件 | 位置 | 说明 |
|------|------|------|
| 高德 API 爬取 | `data/poi/nanhai_poi_real.json` | 高德 Place API，约 1,353 条 |
| Shapefile 解析结果 | `data/poi/nanhai_culture_poi_shp.json` | 由 **辅助补充数据/poi/** 经 `parse_supplementary_data.py` 生成 |
| 百度 API 爬取 | `data/poi/nanhai_poi_baidu.json` | 百度 Place API，含评分/评论数 |
| **融合清洗结果（最终用的）** | **`data/database/poi_cleaned.json`** | 由 `poi_cleaner.py` 融合上述三源后输出 |

**POI 清洗脚本：** `code/data_processing/poi_cleaner.py`  
读取：`data/poi/nanhai_poi_real.json`、`nanhai_culture_poi_shp.json`、`nanhai_poi_baidu.json`  
输出：`data/database/poi_cleaned.json`

---

## 四、评论数据最终在哪、怎么来的

| 文件 | 位置 | 说明 |
|------|------|------|
| **辅助数据解析出的合并评论** | **`data/reviews/merged_reviews_supp.json`** | 由 **辅助补充数据/携程去哪儿马蜂窝评价/*.xlsx** 经 `parse_supplementary_data.py` 生成 |
| 原始/其他评论 | `data/reviews/nanhai_reviews_real.csv`、`review_summary_real.json` 等 | 爬虫或其它脚本产出，供分析用 |

景点层级、体验度分析（`scenic_genealogy.py`）会加载 `poi_cleaned.json` 和评论汇总（含 `merged_reviews_supp.json` 的补充评论）。

---

## 五、POI 与评论的「表格」导出（便于查看和论文引用）

运行 **`python code/data_processing/export_csv.py`** 后会产生：

| 表格 | 路径 | 说明 |
|------|------|------|
| **POI 最终结果表** | **`output/tables/poi_cleaned.csv`** | 清洗后的 POI 全量表格（id/name/category/town/address/lng/lat/rating/source/非遗关联/文化锚点等） |
| 评论明细表（具体评论文本） | `output/tables/reviews_detail.csv` | 来自 **辅助数据** 携程/去哪儿/马蜂窝 xlsx 解析，每行一条评论（platform, spot_name, user, text, time） |
| 评论汇总（多平台合并） | `output/tables/review_summary_merged.csv` | 按景点汇总，**sources 含 高德/携程/去哪儿/马蜂窝**，总条数、有正文条数、评分等 |

之前若只看到「高德和携程」，是因为 **`review_summary_real`** 来自爬虫 `review_crawler_real.py`，只接了高德（评分）和携程（部分评论）；**去哪儿、马蜂窝** 的评论在你提供的辅助数据 xlsx 里，解析后是 `merged_reviews_supp.json`，现已参与合并并导出为上述表格。

---

## 六、为什么评论里没有「具体评论」、为什么只有高德和携程？

- **没有具体评论**：  
  - 高德 API 只返回**评分**，没有用户评论文本，所以 `nanhai_reviews_real` 里很多是「高德评分: 4.3」这类占位。  
  - **具体评论文本**在辅助数据的 **携程/去哪儿/马蜂窝 xlsx** 里，解析后保存在 `data/reviews/merged_reviews_supp.json`。  
  - 现已用 **`export_csv.py`** 把其中每条评论导出为 **`output/tables/reviews_detail.csv`**（含 platform, spot_name, user, text, time），可直接打开看每条评论。

- **只有高德和携程**：  
  - `review_summary_real.json` 是爬虫脚本 `review_crawler_real.py` 生成的，该脚本只请求了**高德**和**携程**，没有爬去哪儿/马蜂窝。  
  - 去哪儿、马蜂窝的数据来自你提供的**辅助数据 xlsx**，解析后进入 `merged_reviews_supp.json`。  
  - 现已增加 **合并汇总**：`export_csv.py` 会生成 `review_summary_merged.json` 与 **`output/tables/review_summary_merged.csv`**，按景点合并高德+携程+去哪儿+马蜂窝，sources 列会列出各平台。

---

## 七、总结

- **你提供的辅助数据文档/文件夹** → 放在 **`中期阶段/辅助补充数据/`**，按上面的 `wenhuadian/`、`poi/`、`携程去哪儿马蜂窝评价/` 结构放置。
- **解析一次**：运行 `parse_supplementary_data.py`，得到  
  `data/database/cultural_anchors.json`、  
  `data/poi/nanhai_culture_poi_shp.json`、  
  `data/reviews/merged_reviews_supp.json`。
- **POI 最终**：`data/database/poi_cleaned.json`；**POI 表格**：运行 `export_csv.py` 后得到 **`output/tables/poi_cleaned.csv`**。
- **评论**：具体评论文本在 `merged_reviews_supp.json`，导出为 **`output/tables/reviews_detail.csv`**；按景点合并多平台（高德/携程/去哪儿/马蜂窝）的汇总表为 **`output/tables/review_summary_merged.csv`**。
