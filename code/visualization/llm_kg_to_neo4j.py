#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LLM 抽取结果 → Neo4j 导入 + 简易可视化

读取 output/llm_extraction/merged_entities.json 与 merged_relations.json，
生成 Neo4j 可导入的 CSV 与 Cypher，以及浏览器可打开的 HTML 图。

用法:
  python llm_kg_to_neo4j.py
  输出: output/neo4j/ 下 neo4j_llm_nodes.csv, neo4j_llm_edges.csv, neo4j_import_llm.cypher
        output/figures/ 下 knowledge_graph_llm.html（可选）
"""

import os
import csv
import json
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output")
LLM_DIR = os.path.join(OUTPUT_DIR, "llm_extraction")
NEO4J_DIR = os.path.join(OUTPUT_DIR, "neo4j")
FIGURES_DIR = os.path.join(OUTPUT_DIR, "figures")


def _escape_csv(s):
    if s is None:
        return ""
    s = str(s).replace('"', '""')
    if "," in s or "\n" in s or '"' in s:
        return f'"{s}"'
    return s


def load_llm_merged():
    ent_path = os.path.join(LLM_DIR, "merged_entities.json")
    rel_path = os.path.join(LLM_DIR, "merged_relations.json")
    if not os.path.exists(ent_path):
        raise FileNotFoundError(f"请先运行 llm_ner.py 并完成合并，生成 {ent_path}")
    if not os.path.exists(rel_path):
        raise FileNotFoundError(f"缺少 {rel_path}")

    with open(ent_path, "r", encoding="utf-8") as f:
        entities_data = json.load(f)
    with open(rel_path, "r", encoding="utf-8") as f:
        relations_data = json.load(f)

    entities = entities_data.get("entities", [])
    relations = relations_data.get("relations", [])
    return entities, relations


def export_neo4j_csv(entities, relations):
    os.makedirs(NEO4J_DIR, exist_ok=True)

    # 节点 CSV：id 用序号，避免中文/特殊字符在 Neo4j 里当 ID 有问题
    nodes_path = os.path.join(NEO4J_DIR, "neo4j_llm_nodes.csv")
    with open(nodes_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "type", "description", "confidence", "mentions", "is_anchor"])
        for i, e in enumerate(entities):
            name = e.get("name", "").strip()
            if not name:
                continue
            w.writerow([
                i + 1,
                _escape_csv(name),
                _escape_csv(e.get("type", "")),
                _escape_csv((e.get("description") or "")[:200]),
                e.get("confidence", 0),
                e.get("mentions", 0),
                1 if e.get("is_anchor") else 0,
            ])
    print(f"  Neo4j 节点: {nodes_path} ({len(entities)} 条)")

    # 关系 CSV：只保留两端都在实体表中的关系
    name_set = {e.get("name", "").strip() for e in entities if e.get("name", "").strip()}
    edges_path = os.path.join(NEO4J_DIR, "neo4j_llm_edges.csv")
    valid_rels = [r for r in relations if r.get("source") in name_set and r.get("target") in name_set]
    with open(edges_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "target", "relation", "confidence"])
        for r in valid_rels:
            w.writerow([
                _escape_csv(r["source"]),
                _escape_csv(r["target"]),
                _escape_csv(r["relation"]),
                r.get("confidence", 0.8),
            ])
    print(f"  Neo4j 关系: {edges_path} ({len(valid_rels)} 条，已过滤不在节点表中的关系)")

    return nodes_path, edges_path, valid_rels


def export_neo4j_cypher(entities, relations):
    rel_counter = Counter(r["relation"] for r in relations)
    cypher_path = os.path.join(NEO4J_DIR, "neo4j_import_llm.cypher")
    lines = [
        "// ═══ LLM 抽取知识图谱 — Neo4j 导入脚本 ═══",
        "// 1. 将 neo4j_llm_nodes.csv、neo4j_llm_edges.csv 复制到 Neo4j 的 import 目录",
        "// 2. Neo4j Desktop: 数据库 → ⋮ → Open Folder → Import",
        "// 3. 在 Neo4j Browser 中逐段执行下面语句",
        "",
        "// ── Step 1: 约束 ──",
        "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:LLMEntity) REQUIRE n.id IS UNIQUE;",
        "",
        "// ── Step 2: 导入节点 ──",
        "LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_nodes.csv' AS row",
        "CREATE (n:LLMEntity {",
        "  id: toInteger(row.id),",
        "  name: row.name,",
        "  type: row.type,",
        "  description: row.description,",
        "  confidence: toFloat(row.confidence),",
        "  mentions: toInteger(row.mentions),",
        "  is_anchor: toInteger(row.is_anchor) = 1",
        "});",
        "",
        "// 为每种实体类型添加标签（便于按类型查询）",
    ]
    types = sorted(set(e.get("type", "") for e in entities if e.get("type")))
    for t in types:
        safe = t.replace(" ", "_").replace("（", "").replace("）", "")
        lines.append(f'MATCH (n:LLMEntity) WHERE n.type = "{t}" SET n:`{safe}`;')
    lines.extend([
        "",
        "// ── Step 3: 导入关系（无 APOC 时按类型分批）──",
    ])
    for rel_type in rel_counter:
        safe_rel = rel_type.replace(" ", "_")
        lines.append(f"// 关系: {rel_type} ({rel_counter[rel_type]} 条)")
        lines.append("LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row")
        lines.append(f'WITH row WHERE row.relation = "{rel_type}"')
        lines.append("MATCH (a:LLMEntity {name: row.source})")
        lines.append("MATCH (b:LLMEntity {name: row.target})")
        lines.append(f"CREATE (a)-[:`{safe_rel}` {{confidence: toFloat(row.confidence)}}]->(b);")
        lines.append("")
    lines.extend([
        "// ── 查询示例 ──",
        "// 按类型统计节点",
        "MATCH (n:LLMEntity) RETURN n.type AS type, count(*) AS cnt ORDER BY cnt DESC;",
        "",
        "// 查看「康有为」相关关系",
        'MATCH (n:LLMEntity {name: "康有为"})-[r]-(m) RETURN n, r, m LIMIT 50;',
        "",
        "// 查看「西樵山」一度邻居",
        'MATCH (n:LLMEntity {name: "西樵山"})-[r]-(m) RETURN n, r, m;',
    ])
    with open(cypher_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Cypher 脚本: {cypher_path}")
    return cypher_path


def export_pyvis_html(entities, relations, max_nodes=800, max_edges=2000):
    """生成可用浏览器打开的交互式 HTML（pyvis）"""
    try:
        from pyvis.network import Network
    except ImportError:
        print("  跳过 HTML 可视化: 未安装 pyvis，可 pip install pyvis")
        return None

    name_set = {e.get("name", "").strip() for e in entities if e.get("name", "").strip()}
    rels = [r for r in relations if r.get("source") in name_set and r.get("target") in name_set][:max_edges]
    node_ids = set()
    for r in rels:
        node_ids.add(r["source"])
        node_ids.add(r["target"])
    entities_sub = [e for e in entities if e.get("name", "").strip() in node_ids][:max_nodes]
    if not entities_sub:
        entities_sub = entities[:max_nodes]
    name_to_type = {e["name"]: e.get("type", "") for e in entities_sub}

    net = Network(height="700px", width="100%", directed=True, notebook=False)
    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=150)

    for e in entities_sub:
        n = e["name"]
        net.add_node(n, label=n[:8] + "…" if len(n) > 8 else n,
                     title=f"{e.get('type','')}\n{e.get('description','')[:80]}",
                     group=e.get("type", "其他"))
    for r in rels:
        if r["source"] in name_to_type and r["target"] in name_to_type:
            net.add_edge(r["source"], r["target"], title=r.get("relation", ""), label=r.get("relation", "")[:6])

    os.makedirs(FIGURES_DIR, exist_ok=True)
    out_path = os.path.join(FIGURES_DIR, "knowledge_graph_llm.html")
    net.save_graph(out_path)
    print(f"  交互图: {out_path}")
    return out_path


def main():
    print("LLM 实体/关系 → Neo4j 与可视化\n")
    entities, relations = load_llm_merged()
    print(f"实体: {len(entities)} 条，关系: {len(relations)} 条\n")

    export_neo4j_csv(entities, relations)
    export_neo4j_cypher(entities, relations)
    export_pyvis_html(entities, relations)

    print("\n下一步（Neo4j）：")
    print("  1. 打开 Neo4j Desktop，启动一个数据库")
    print("  2. 点击该数据库右侧 [...] -> Open Folder -> Import，打开 import 目录")
    print("  3. 将 output/neo4j/ 下的 neo4j_llm_nodes.csv、neo4j_llm_edges.csv 复制到该 import 目录")
    print("  4. 在 Neo4j Browser 中打开 neo4j_import_llm.cypher，按注释逐段执行")
    print("  5. 执行: MATCH (n:LLMEntity)-[r]-(m) RETURN n,r,m LIMIT 300 即可看图")
    print("\n或直接双击打开 output/figures/knowledge_graph_llm.html 在浏览器中查看简化图。")


if __name__ == "__main__":
    main()
