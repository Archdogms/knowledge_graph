#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键构建 Neo4j 图数据库：清库 → 导节点 → 导边 → 加类型标签 → 设颜色属性。
"""

import os
import json
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LLM_DIR = os.path.join(BASE_DIR, "..", "..", "output", "llm_extraction")

URI = "bolt://127.0.0.1:7687"
USER = "neo4j"
PASSWORD = "ms781125"
DATABASE = "culturegraph"

TYPE_COLORS = {
    "人物": "#4A90D9",
    "地名": "#7ED787",
    "建筑遗迹": "#F5A623",
    "典籍作品": "#BD10E0",
    "非遗技艺": "#D0021B",
    "朝代年号": "#50E3C2",
    "历史事件": "#B8E986",
    "物产饮食": "#F8E71C",
    "宗族姓氏": "#9013FE",
}


def main():
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("请先安装: pip install neo4j")
        sys.exit(1)

    entities_path = os.path.join(LLM_DIR, "merged_entities.json")
    relations_path = os.path.join(LLM_DIR, "merged_relations.json")
    for p in [entities_path, relations_path]:
        if not os.path.exists(p):
            print(f"缺少文件: {p}")
            sys.exit(1)

    with open(entities_path, "r", encoding="utf-8") as f:
        ent_data = json.load(f)
    entities = ent_data.get("entities", [])

    with open(relations_path, "r", encoding="utf-8") as f:
        rel_data = json.load(f)
    relations = rel_data.get("relations", [])

    print(f"实体: {len(entities)} 条 | 关系: {len(relations)} 条")
    print(f"连接: {URI}  数据库: {DATABASE}  用户: {USER}")

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

    # ═══ 1. 清库 ═══
    print("\n[1/5] 清空数据库...")
    with driver.session(database=DATABASE) as s:
        s.run("MATCH (n) DETACH DELETE n")
    print("  已清空。")

    # ═══ 2. 创建约束 ═══
    print("[2/5] 创建唯一约束...")
    with driver.session(database=DATABASE) as s:
        try:
            s.run("CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (n:Entity) REQUIRE n.name IS UNIQUE")
            print("  约束已创建。")
        except Exception as e:
            print(f"  约束创建跳过: {e}")

    # ═══ 3. 导入节点（批量） ═══
    print("[3/5] 导入节点...")
    batch_size = 500
    total_nodes = 0
    with driver.session(database=DATABASE) as s:
        for i in range(0, len(entities), batch_size):
            batch = entities[i : i + batch_size]
            params = []
            for e in batch:
                params.append({
                    "name": (e.get("name") or "").strip(),
                    "type": (e.get("type") or "").strip(),
                    "description": (e.get("description") or "").strip(),
                    "confidence": float(e.get("confidence", 0)),
                    "mentions": int(e.get("mentions", 0)),
                    "is_anchor": bool(e.get("is_anchor", False)),
                    "color": TYPE_COLORS.get((e.get("type") or "").strip(), "#A5ABB6"),
                })
            s.run(
                """
                UNWIND $batch AS row
                MERGE (n:Entity {name: row.name})
                SET n.type = row.type,
                    n.description = row.description,
                    n.confidence = row.confidence,
                    n.mentions = row.mentions,
                    n.is_anchor = row.is_anchor,
                    n.color = row.color
                """,
                batch=params,
            )
            total_nodes += len(batch)
            print(f"  节点: {total_nodes}/{len(entities)}")
    print(f"  节点导入完成: {total_nodes} 个。")

    # ═══ 4. 给节点加类型标签（人物、地名 等）═══
    print("[4/5] 给节点添加类型标签（用于颜色区分）...")
    with driver.session(database=DATABASE) as s:
        for typ in TYPE_COLORS:
            result = s.run(
                f'MATCH (n:Entity) WHERE n.type = $t SET n:`{typ}` RETURN count(n) AS cnt',
                t=typ,
            )
            cnt = result.single()["cnt"]
            print(f"  {typ}: {cnt} 个节点")
    print("  类型标签添加完成。")

    # ═══ 5. 导入关系（批量） ═══
    print("[5/5] 导入关系...")
    total_edges = 0
    skipped = 0
    with driver.session(database=DATABASE) as s:
        for i in range(0, len(relations), batch_size):
            batch = relations[i : i + batch_size]
            params = []
            for r in batch:
                params.append({
                    "src": (r.get("source") or "").strip(),
                    "tgt": (r.get("target") or "").strip(),
                    "rel_type": (r.get("relation") or "").strip(),
                    "confidence": float(r.get("confidence", 0.8)),
                    "evidence": (r.get("evidence") or "")[:100],
                    "source_file": (r.get("source_file") or ""),
                })
            result = s.run(
                """
                UNWIND $batch AS row
                MATCH (a:Entity {name: row.src})
                MATCH (b:Entity {name: row.tgt})
                CREATE (a)-[r:REL]->(b)
                SET r.rel_type = row.rel_type,
                    r.confidence = row.confidence,
                    r.evidence = row.evidence,
                    r.source_file = row.source_file
                RETURN count(r) AS cnt
                """,
                batch=params,
            )
            cnt = result.single()["cnt"]
            total_edges += cnt
            skipped += len(batch) - cnt
            if (i // batch_size + 1) % 4 == 0 or i + batch_size >= len(relations):
                print(f"  关系: {total_edges} 条（跳过 {skipped}）")
    print(f"  关系导入完成: {total_edges} 条，跳过 {skipped} 条。")

    # ═══ 最终统计 ═══
    print("\n═══ 验证 ═══")
    with driver.session(database=DATABASE) as s:
        node_count = s.run("MATCH (n:Entity) RETURN count(n) AS c").single()["c"]
        edge_count = s.run("MATCH ()-[r:REL]->() RETURN count(r) AS c").single()["c"]
        type_dist = s.run("MATCH (n:Entity) RETURN n.type AS t, count(n) AS c ORDER BY c DESC").data()
        rel_dist = s.run("MATCH ()-[r:REL]->() RETURN r.rel_type AS t, count(r) AS c ORDER BY c DESC").data()

    print(f"节点总数: {node_count}")
    print(f"关系总数: {edge_count}")
    print("\n实体类型分布:")
    for row in type_dist:
        color = TYPE_COLORS.get(row["t"], "")
        print(f"  {row['t']}: {row['c']} 个  {color}")
    print("\n关系类型分布:")
    for row in rel_dist:
        print(f"  {row['t']}: {row['c']} 条")

    driver.close()
    print("\n构建完成！")
    print("在 Neo4j 客户端中查看图：")
    print("  MATCH (n:Entity)-[r:REL]->(m) RETURN n,r,m LIMIT 300")


if __name__ == "__main__":
    main()
