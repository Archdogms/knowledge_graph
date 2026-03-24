# 基于多元大数据的佛山市南海区文旅融合调研

## 项目结构

```
knowledge_graph/
├── docs/                          # 研究文档
│   ├── 研究开题.md              # 开题报告
│   ├── 中期检查报告.md          # 中期检查报告
│   ├── 研究方法论报告.md        # 方法论说明
│   ├── 分类体系.md              # 分类体系说明
│   └── neo4j_query.md           # Neo4j查询示例
│
├── code/                          # 代码
│   ├── collection/              # 数据采集
│   │   ├── amap_real_data.py    # 高德POI采集
│   │   ├── ocr_books_parallel.py# OCR并行处理
│   │   └── review_crawler_real.py # 评论爬取
│   ├── processing/              # 数据处理
│   │   ├── llm_ner.py           # LLM实体抽取
│   │   └── poi_cleaner.py       # POI数据清洗
│   ├── analysis/                # 数据分析
│   │   ├── culture_genealogy.py # 文化谱系构建
│   │   ├── scenic_genealogy.py  # 景点谱系构建
│   │   ├── coupling_analysis.py # 耦合分析
│   │   └── spatial_analysis.py  # 空间分析
│   └── visualization/           # 可视化
│       ├── knowledge_graph.py   # 知识图谱构建
│       └── llm_kg_to_neo4j.py   # Neo4j导出
│
├── data/                          # 数据
│   ├── corpus/                  # 典籍文本（53个MD文件）
│   ├── entities/                # LLM抽取结果
│   │   ├── entities.json        # 合并实体 (7,354个)
│   │   ├── relations.json       # 合并关系 (9,885条)
│   │   ├── by_source/           # 按文本源分类的实体
│   │   └── relations_by_source/ # 按文本源分类的关系
│   ├── poi/                     # POI数据
│   │   ├── poi_cleaned.json     # 标准化POI (13,113条)
│   │   ├── poi_shapefile.json   # Shapefile原始数据
│   │   └── poi_amap.json        # 高德API数据
│   ├── reviews/                 # 评论数据 (16,391条)
│   ├── gis/                     # 地理数据
│   └── anchors/                 # 文化锚点和谱系
│       ├── cultural_anchors.json  # 文化载体锚点 (165条)
│       ├── culture_taxonomy.json  # 文化分类 (8类97条目)
│       └── culture_genealogy_tree.json # 文化谱系树
│
├── output/                        # 输出结果
│   ├── figures/                 # 可视化 (HTML+图片)
│   ├── tables/                  # 导出表格 (CSV)
│   ├── neo4j/                   # Neo4j导入文件
│   └── analysis/                # 分析结果 (JSON)
│       ├── scenic_genealogy_tree.json  # 景点谱系树
│       ├── scenic_town_tree.json       # 镇街分布树
│       └── coupling_results.json       # 耦合分析结果
│
├── books/                         # PDF原始书籍 (36本)
├── lib/                           # 前端库
└── README.md
```

## 数据规模

| 数据类型 | 数量 | 说明 |
|---------|------|------|
| 典籍文本 | 53个 | 级540万字符 |
| LLM实体 | 7,354个 | 9类型 |
| LLM关系 | 9,885条 | 15类型 |
| POI景点 | 13,113条 | 11类分类 |
| 用户评论 | 16,391条 | 4平台 |
| 文化锚点 | 165条 | 政府普查级 |
| 非遗项目 | 37项 | 精确编码 |