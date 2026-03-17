# 毕设中期阶段 - 基于多元大数据的佛山市南海区文旅融合调研

## 项目结构

```
中期阶段/
├── 研究开题.md                     # 开题报告（原有）
├── 中期检查报告.md                  # 中期检查报告
├── README.md                       # 本文件
│
├── data/                           # 数据文件
│   ├── 典籍文本/                   # OCR结构化文本
│   │   ├── 南海县志_OCR全文.txt    # 458页OCR合并文本
│   │   ├── 南海县志_OCR连续文本.txt # 去除页码标记的连续文本
│   │   ├── 南海县志_页码索引.json   # 页码-字符位置索引
│   │   ├── 文本统计报告.json       # 所有文本统计
│   │   └── 开题阶段典籍/           # 22个典籍MD文件
│   │
│   ├── poi/                        # 高德POI数据
│   │   ├── nanhai_poi_sample.json  # POI数据（JSON）
│   │   └── nanhai_poi_sample.csv   # POI数据（CSV）
│   │
│   ├── reviews/                    # 评论数据
│   │   ├── nanhai_reviews.json     # 354条评论
│   │   ├── nanhai_reviews.csv      # CSV格式
│   │   └── review_summary.json     # 景点评论汇总
│   │
│   ├── gis/                        # 空间底图数据
│   │   ├── nanhai_boundary.geojson # 南海区行政边界
│   │   ├── nanhai_towns.geojson    # 7个镇街点位
│   │   ├── nanhai_nonheritage.geojson # 26个非遗项目空间分布
│   │   └── nanhai_nonheritage.json # 非遗项目列表
│   │
│   └── database/                   # 结构化数据库
│       ├── culture_entities.json   # 2413个文化实体
│       ├── culture_relations.json  # 5000条共现关系
│       ├── poi_cleaned.json        # 41条清洗后POI
│       ├── culture_taxonomy.json   # 文化分类原始数据
│       ├── culture_genealogy_tree.json # 文化谱系树
│       ├── scenic_genealogy_tree.json  # 景点谱系树
│       ├── scenic_town_tree.json       # 镇街分布树
│       ├── coupling_results.json       # 耦合分析结果
│       └── expanded_knowledge_graph.json # 扩展知识图谱
│
├── code/                           # 代码文件
│   ├── data_collection/            # 数据采集
│   │   ├── consolidate_ocr.py      # OCR整合工具
│   │   ├── amap_poi_crawler.py     # 高德POI采集
│   │   ├── review_collector.py     # 评论数据采集
│   │   └── download_gis_data.py    # GIS数据准备
│   │
│   ├── data_processing/            # 数据处理
│   │   ├── text_ner.py             # NER实体抽取
│   │   └── poi_cleaner.py          # POI数据清洗
│   │
│   ├── analysis/                   # 核心分析
│   │   ├── culture_genealogy.py    # 文化谱系构建
│   │   ├── scenic_genealogy.py     # 景点谱系构建（含体验度评估）
│   │   ├── coupling_analysis.py    # 双谱系耦合分析
│   │   └── spatial_analysis.py     # 空间分析
│   │
│   └── visualization/              # 可视化
│       └── knowledge_graph.py      # 知识图谱扩展与可视化
│
└── output/                         # 分析结果输出
    ├── figures/                    # 可视化文件
    │   ├── culture_genealogy_tree.html  # 文化谱系树
    │   ├── scenic_genealogy_tree.html   # 景点谱系树
    │   ├── scenic_town_tree.html        # 镇街分布树
    │   ├── knowledge_graph.html         # 知识图谱
    │   ├── coupling_analysis.html       # 耦合分析
    │   └── spatial_analysis.html        # 空间分析
    │
    └── tables/                     # 统计表格
        ├── culture_genealogy_stats.json  # 谱系统计
        ├── experience_scores.json        # 体验度评分
        ├── coupling_summary.json         # 耦合分析摘要
        └── spatial_analysis_results.json # 空间分析结果
```

## 运行说明

### 环境依赖

```bash
pip install jieba requests
```

### 执行顺序

```bash
# 1. 数据采集
python code/data_collection/consolidate_ocr.py
python code/data_collection/amap_poi_crawler.py
python code/data_collection/review_collector.py
python code/data_collection/download_gis_data.py

# 2. 数据处理
python code/data_processing/text_ner.py
python code/data_processing/poi_cleaner.py

# 3. 核心分析
python code/analysis/culture_genealogy.py
python code/analysis/scenic_genealogy.py
python code/analysis/coupling_analysis.py
python code/analysis/spatial_analysis.py

# 4. 可视化
python code/visualization/knowledge_graph.py
```

### 查看可视化

用浏览器打开 `output/figures/` 下的HTML文件即可查看交互式可视化。

## 技术栈

- Python 3.x
- jieba（中文分词）
- ECharts 5（可视化）
- 高德开放平台API（POI检索）

## 后续工作

1. 配置高德API Key获取完整POI数据
2. 替换模拟评论为真实采集数据
3. 完善可达性分析（等时圈）
4. 撰写论文正文
5. 设计文旅体验提升方案
