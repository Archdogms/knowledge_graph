// ═══════════════════════════════════════════════════════════════════════════
// merged_entities.json + merged_relations.json → Neo4j 导图（Cypher 参考）
// ═══════════════════════════════════════════════════════════════════════════
//
// 数据已抽取完毕时，不要再用千问抽；请先把 JSON 导入图数据库，再在 Browser 里跑下面查询。
//
// 【推荐】一键清库 + 导入（与本文档 schema 完全一致）
//   pip install neo4j
//   编辑 code/visualization/neo4j_full_build.py 顶部 URI、USER、PASSWORD、DATABASE
//   python code/visualization/neo4j_full_build.py
//
// 导入后的模型摘要：
//   · 节点：主键 name；属性 ai_label, ai_type, ai_type_code, ai_layer, official_label,
//           official_type, description, confidence, mentions, source_count, is_anchor, color
//   · 附加标签：A1～F3（AI 小类代号，便于 Browser 配色），脚本结束前会去掉 :Entity
//   · 关系「类型」= relation_group 九类之一（如 人物关联、空间关联、文献记载…）
//   · 关系属性：relation_text（具体谓词，如 位于、记载）、evidence、confidence、source_file
//
// 更多示例见：docs/neo4j_cypher_queries.md
//
// 【数据已在库里时】只查库 + 自动生成交互 HTML（浏览器打开即可拖拽看图）：
//   pip install neo4j pyvis
//   CMD: set NEO4J_PASSWORD=你的密码
//   PowerShell: $env:NEO4J_PASSWORD="你的密码"
//   NEO4J_DATABASE=nanhaiknowledgegraph  若用 neo4j_full_build 的库名；默认库可省略
//   python code/visualization/neo4j_query_to_pyvis.py --preset sample
//   python code/visualization/neo4j_query_to_pyvis.py --preset kang -o output/figures/neo4j_kang.html
//   python code/visualization/neo4j_query_to_pyvis.py --cypher "MATCH (a)-[r]->(b) RETURN a,r,b LIMIT 200"
// ═══════════════════════════════════════════════════════════════════════════


// ── 0. Browser 显示上限（大图必调）────────────────────────────────────────
// :config initialNodeDisplay: 10000
// :config maxRows: 25000


// ── 1. 导入后核验（与 merged JSON 总量对照）────────────────────────────────
MATCH (n) RETURN count(n) AS 节点数;
MATCH ()-[r]->() RETURN count(r) AS 关系数;

MATCH (n)
RETURN coalesce(n.ai_type, '(无)') AS AI小类, count(n) AS 数量
ORDER BY 数量 DESC;

MATCH ()-[r]->()
RETURN type(r) AS 关系分组, count(r) AS 数量
ORDER BY 数量 DESC;


// ── 2. 按 relation_text（合并库高频谓词）探查 — 边上属性，不是 type(r) ──────
// merged_relations.json 中高频示例：位于、记载、属于、出生于、兴盛于、始建于、师承、著述 …

MATCH (a)-[r]->(b)
WHERE r.relation_text = '位于'
RETURN a, r, b
LIMIT 200;

MATCH (a)-[r]->(b)
WHERE r.relation_text = '记载'
RETURN a, r, b
LIMIT 200;

MATCH (a)-[r]->(b)
WHERE r.relation_text IN ['属于', '隶属于', '即', '又名']
RETURN a, r, b
LIMIT 200;

MATCH (a)-[r]->(b)
WHERE r.relation_text IN ['出生于', '籍贯为', '聚居于', '居住于', '生活于']
RETURN a, r, b
LIMIT 200;

MATCH (a)-[r]->(b)
WHERE r.relation_text IN ['师承', '师承于', '师从', '传承']
RETURN a, r, b
LIMIT 150;

MATCH (a)-[r]->(b)
WHERE r.relation_text IN ['著述', '著有', '撰写', '主修', '纂修']
RETURN a, r, b
LIMIT 150;

MATCH (a)-[r]->(b)
WHERE r.relation_text IN ['始建于', '兴盛于', '形成于', '刊于', '重修于']
RETURN a, r, b
LIMIT 150;


// ── 3. 按 relation_group（边类型 type(r)）与谓词组合 ─────────────────────────

MATCH (n)-[r:文献记载]->(m)
RETURN n, r, m
LIMIT 200;

MATCH (n)-[r:空间关联]->(m)
WHERE r.relation_text = '位于'
RETURN n, r, m
LIMIT 200;

MATCH (n)-[r:人物关联]->(m)
RETURN n, r, m
LIMIT 200;

MATCH (n)-[r:时序归属]->(m)
RETURN n, r, m
LIMIT 150;


// ── 4. 点名实体邻域（把名称换成你关心的）──────────────────────────────────

MATCH (n) WHERE n.name = '康有为'
OPTIONAL MATCH (n)-[r]-(m)
RETURN n, r, m;

MATCH p = (n)-[*1..2]-(m)
WHERE n.name = '西樵山'
RETURN p
LIMIT 80;

MATCH (n) WHERE n.name = '南海县志'
MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 200;


// ── 5. 统计：谓词分布（验证与 merged relation_stats 一致）──────────────────

MATCH ()-[r]->()
RETURN r.relation_text AS 谓词, count(*) AS 条数
ORDER BY 条数 DESC
LIMIT 50;


// ── 6. 可选：APOC 从 import 目录读 JSON（需插件；大文件注意内存）────────────
// 将 merged_entities.json / merged_relations.json 复制到数据库的 import 文件夹后再执行。
//
// CALL apoc.load.json('file:///merged_entities.json') YIELD value
// UNWIND value.entities AS e
// MERGE (n:Entity {name: e.name})
// SET n.ai_label = e.ai_grade_label,
//     n.ai_type = e.ai_grade_type,
//     n.ai_layer = e.ai_layer,
//     n.official_label = e.official_label,
//     n.official_type = e.official_type,
//     n.description = e.description,
//     n.confidence = e.confidence,
//     n.mentions = e.mentions,
//     n.source_count = e.source_count,
//     n.is_anchor = e.is_anchor;
//
// CALL apoc.load.json('file:///merged_relations.json') YIELD value
// UNWIND value.relations AS rel
// WITH rel, replace(rel.relation_group, '`', '') AS g
// MATCH (a:Entity {name: rel.source})
// MATCH (b:Entity {name: rel.target})
// CALL apoc.create.relationship(a, g,
//   {relation_text: rel.relation_text, evidence: rel.evidence,
//    confidence: rel.confidence, source_file: rel.source_file}, b) YIELD rel AS r
// RETURN count(r);
//
// 说明：APOC 路径与 Python 一键脚本二选一即可；重复导入会造重复边，需先 MATCH 删库或改用 MERGE 策略。
