# 南海知识图谱 — Neo4j Cypher 查询示例

> 数据库: `nanhaiknowledgegraph`
>
> 节点标签: `A1` ~ `F3`（AI小类代号，移除了 Entity 公共标签以便 Browser 自动分色）
>
> 关系类型: `人物关联` / `空间关联` / `时序归属` / `文献记载` / `传承延续` / `从属分类` / `社群组织` / `营建创造` / `文化表征`

---

## 零、全图查看

> Neo4j Browser 默认最多显示 1000 行，需先调大限制：

```
:config initialNodeDisplay: 10000
:config maxRows: 25000
```

```cypher
// 全部节点 + 关系
MATCH (n)-[r]->(m) RETURN n, r, m

// 含孤立节点的完整图
MATCH (n) OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m
```

> 8000+ 节点全量渲染较慢，建议按 AI大类 分批查看：
```cypher
// 只看非遗 (A类) 相关子图
MATCH (n)-[r]->(m) WHERE n.ai_label = 'A 非遗文化体系' RETURN n, r, m

// 只看传承主体 (C类) 相关子图
MATCH (n)-[r]->(m) WHERE n.ai_label = 'C 传承主体体系' RETURN n, r, m
```

---

## 一、全局总览

```cypher
// 节点总数
MATCH (n) RETURN count(n) AS 节点总数

// 关系总数
MATCH ()-[r]->() RETURN count(r) AS 关系总数

// AI小类分布
MATCH (n)
RETURN n.ai_type AS AI小类, count(n) AS 数量
ORDER BY 数量 DESC

// 关系分组分布
MATCH ()-[r]->()
RETURN type(r) AS 关系分组, count(r) AS 数量
ORDER BY 数量 DESC

// AI大类分布
MATCH (n)
RETURN n.ai_label AS AI大类, count(n) AS 数量
ORDER BY 数量 DESC
```

---

## 二、按 AI小类 查看（颜色区分）

```cypher
// 查看所有历史文化人物 (C1，蓝色)
MATCH (n:C1)-[r]->(m) RETURN n, r, m LIMIT 200

// 查看所有表演艺术类非遗 (A1，红色)
MATCH (n:A1)-[r]->(m) RETURN n, r, m LIMIT 200

// 查看所有古建筑 (B1，棕色)
MATCH (n:B1)-[r]->(m) RETURN n, r, m LIMIT 200

// 查看所有镇街圩市空间 (D2，绿色)
MATCH (n:D2)-[r]->(m) RETURN n, r, m LIMIT 200

// 查看所有地方志 (E1，紫色)
MATCH (n:E1)-[r]->(m) RETURN n, r, m LIMIT 200

// 查看所有朝代年号 (F1，青色)
MATCH (n:F1)-[r]->(m) RETURN n, r, m LIMIT 200
```

---

## 2.5、人物-人物关系

```cypher
// 历史文化人物 (C1) 之间的所有关系
MATCH (a:C1)-[r]->(b:C1) RETURN a, r, b

// 所有人物类 (C1+C2+C3) 之间的关系
MATCH (a)-[r]->(b)
WHERE a.ai_type_code IN ['C1','C2','C3'] AND b.ai_type_code IN ['C1','C2','C3']
RETURN a, r, b

// 仅看人物关联分组
MATCH (a)-[r:人物关联]->(b)
WHERE a.ai_type_code IN ['C1','C2','C3'] AND b.ai_type_code IN ['C1','C2','C3']
RETURN a, r, b
```

---

## 三、按关系分组查看

```cypher
// 人物关联 — 谁和谁有什么人物关系
MATCH (a)-[r:人物关联]->(b)
RETURN a.name AS 源, r.relation_text AS 关系, b.name AS 目标, r.evidence AS 依据
LIMIT 100

// 空间关联 — 实体的地理空间关系
MATCH (a)-[r:空间关联]->(b)
RETURN a.name, r.relation_text, b.name
LIMIT 100

// 时序归属 — 实体的时间脉络
MATCH (a)-[r:时序归属]->(b)
RETURN a.name, r.relation_text, b.name
LIMIT 100

// 传承延续 — 非遗/技艺的传承链
MATCH (a)-[r:传承延续]->(b)
RETURN a.name, r.relation_text, b.name
LIMIT 100

// 文献记载 — 文献与实体的记录关系
MATCH (a)-[r:文献记载]->(b)
RETURN a.name, r.relation_text, b.name
LIMIT 100

// 营建创造 — 谁建造/创作了什么
MATCH (a)-[r:营建创造]->(b)
RETURN a.name, r.relation_text, b.name
LIMIT 100
```

---

## 四、跨类查看（交叉探索）

```cypher
// 人物 (C1) 与 非遗项目 (A1~A6) 之间的所有关系
MATCH (p:C1)-[r]->(a)
WHERE a.ai_type_code IN ['A1','A2','A3','A4','A5','A6']
RETURN p.name AS 人物, type(r) AS 关系分组, r.relation_text AS 关系, a.name AS 非遗项目
LIMIT 200

// 古建筑 (B1) 位于哪些镇街 (D2)
MATCH (b:B1)-[r:空间关联]->(d:D2)
RETURN b.name AS 古建筑, r.relation_text AS 关系, d.name AS 镇街
LIMIT 100

// 文献 (E类) 记载了哪些人物 (C1)
MATCH (e)-[r:文献记载]->(c:C1)
WHERE e.ai_label = 'E 文献记忆体系'
RETURN e.name AS 文献, r.relation_text AS 关系, c.name AS 人物
LIMIT 100

// 某朝代 (F1) 下有哪些实体
MATCH (n)-[r:时序归属]->(f:F1)
WHERE f.name CONTAINS '清'
RETURN n.name AS 实体, n.ai_type AS 类型, r.relation_text AS 关系, f.name AS 朝代
LIMIT 200
```

---

## 五、指定实体深度探索

```cypher
// 某实体的一跳邻居（以"醒狮"为例）
MATCH (n {name: '醒狮'})-[r]-(m)
RETURN n, r, m

// 某实体的二跳子图
MATCH path = (n {name: '醒狮'})-[*1..2]-(m)
RETURN path LIMIT 300

// 查看某人物的所有关系
MATCH (p {name: '康有为'})-[r]-(m)
RETURN p.name, type(r) AS 关系分组, r.relation_text AS 关系, m.name AS 关联实体, m.ai_type AS 对方类型
ORDER BY type(r)

// 两个实体之间的最短路径
MATCH path = shortestPath((a {name: '西樵山'})-[*..6]-(b {name: '南海县'}))
RETURN path
```

---

## 六、统计与排行

```cypher
// 度数最高的节点 TOP 20（连接最多的实体）
MATCH (n)
WITH n, size([(n)-[]-() | 1]) AS degree
RETURN n.name AS 实体, n.ai_type AS AI小类, degree AS 度数
ORDER BY degree DESC
LIMIT 20

// 被提及次数最多的实体 TOP 20
MATCH (n)
RETURN n.name AS 实体, n.ai_type AS AI小类, n.mentions AS 提及次数
ORDER BY n.mentions DESC
LIMIT 20

// 跨源引用最多的实体（出现在最多文献中）
MATCH (n)
RETURN n.name, n.ai_type, n.source_count AS 跨源数
ORDER BY n.source_count DESC
LIMIT 20

// 高置信度关系 TOP 50
MATCH (a)-[r]->(b)
WHERE r.confidence >= 0.95
RETURN a.name, r.relation_text, b.name, type(r) AS 关系分组, r.confidence
ORDER BY r.confidence DESC
LIMIT 50

// 各 AI大类 的平均度数
MATCH (n)
WITH n.ai_label AS 大类, n, size([(n)-[]-() | 1]) AS deg
RETURN 大类, count(n) AS 节点数, avg(deg) AS 平均度数, max(deg) AS 最大度数
ORDER BY 平均度数 DESC
```

---

## 七、官方分类视角

```cypher
// 按官方大类统计
MATCH (n)
WHERE n.official_label <> ''
RETURN n.official_label AS 官方大类, count(n) AS 数量
ORDER BY 数量 DESC

// 按官方小类统计
MATCH (n)
WHERE n.official_type <> ''
RETURN n.official_type AS 官方小类, count(n) AS 数量
ORDER BY 数量 DESC

// 查看某官方类别下的实体 (例：不可移动文物)
MATCH (n)-[r]->(m)
WHERE n.official_label = '不可移动文物'
RETURN n.name, n.official_type, r.relation_text, m.name
LIMIT 100

// AI分类 vs 官方分类交叉表
MATCH (n)
WHERE n.official_label <> ''
RETURN n.ai_label AS AI大类, n.official_label AS 官方大类, count(n) AS 数量
ORDER BY 数量 DESC
```

---

## 八、AI三层体系视角

```cypher
// 文化本体层 (A 非遗 + B 物质遗产)
MATCH (n)-[r]->(m)
WHERE n.ai_layer = '文化本体层'
RETURN n, r, m LIMIT 200

// 传承承载层 (C 传承主体 + D 文化空间)
MATCH (n)-[r]->(m)
WHERE n.ai_layer = '传承承载层'
RETURN n, r, m LIMIT 200

// 认知支撑层 (E 文献记忆 + F 历史时序)
MATCH (n)-[r]->(m)
WHERE n.ai_layer = '认知支撑层'
RETURN n, r, m LIMIT 200
```

---

## 九、子图导出与分析

```cypher
// 导出某个社区/区域相关的完整子图 (以"西樵"为例)
MATCH (n)-[r]->(m)
WHERE n.name CONTAINS '西樵' OR m.name CONTAINS '西樵'
RETURN n, r, m

// 找出孤立节点（没有任何关系的实体）
MATCH (n)
WHERE NOT (n)--()
RETURN n.name, n.ai_type, n.description
LIMIT 50

// 找出桥接节点（连接不同AI大类的实体）
MATCH (a)-[r1]->(bridge)-[r2]->(b)
WHERE a.ai_label <> b.ai_label
  AND a.ai_label <> bridge.ai_label
  AND bridge.ai_label <> b.ai_label
RETURN bridge.name AS 桥接实体, bridge.ai_type,
       a.ai_label AS 左侧大类, b.ai_label AS 右侧大类,
       count(*) AS 桥接次数
ORDER BY 桥接次数 DESC
LIMIT 20
```

---

## 十、Browser 可视化配色

在 Neo4j Browser 中执行以下命令手动设置颜色（也可导入生成的 `neo4j_style.grass` 文件）：

```
:style reset
```

| 标签 | AI小类 | 颜色 |
|------|--------|------|
| A1 | 表演艺术类非遗 | `#E74C3C` |
| A2 | 传统技艺类非遗 | `#E67E22` |
| A3 | 民俗节庆类非遗 | `#F39C12` |
| A4 | 信俗礼仪类非遗 | `#D35400` |
| A5 | 传统体育游艺类非遗 | `#C0392B` |
| A6 | 饮食酿造类非遗及文化物产 | `#F1C40F` |
| B1 | 古建筑类 | `#D4A76A` |
| B2 | 宗教建筑类 | `#B8860B` |
| B3 | 纪念性建筑与名人故居类 | `#CD853F` |
| B4 | 古遗址与生产遗存类 | `#8B6914` |
| B5 | 石刻碑记类 | `#A0522D` |
| B6 | 古村落与聚落遗产类 | `#DEB887` |
| C1 | 历史文化人物 | `#3498DB` |
| C2 | 非遗传承人及技艺人物 | `#2980B9` |
| C3 | 文物营建与守护人物 | `#2471A3` |
| C4 | 宗族姓氏与地方社群 | `#5DADE2` |
| D1 | 山川水系空间 | `#27AE60` |
| D2 | 镇街圩市空间 | `#2ECC71` |
| D3 | 历史街区与传统片区 | `#1ABC9C` |
| D4 | 传承场所与活动场地 | `#16A085` |
| E1 | 地方志类 | `#8E44AD` |
| E2 | 族谱家乘类 | `#9B59B6` |
| E3 | 碑记题咏类 | `#7D3C98` |
| E4 | 文集著述类 | `#A569BD` |
| E5 | 口述史与地方记忆材料 | `#BB8FCE` |
| F1 | 朝代年号类 | `#5499C7` |
| F2 | 历史事件类 | `#48C9B0` |
| F3 | 发展阶段类 | `#76D7C4` |
