#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接通过 Neo4j 驱动导入 LLM 实体/关系（无需把 CSV 放到 import 目录）

先安装: pip install neo4j
Neo4j Desktop 里数据库启动后，默认 bolt://localhost:7687，密码为你创建数据库时设的。

用法:
  python llm_kg_neo4j_direct.py
  python llm_kg_neo4j_direct.py --uri bolt://127.0.0.1:7687 --password 你的密码
"""

import os
import json
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output")
LLM_DIR = os.path.join(OUTPUT_DIR, "llm_extraction")


def load_llm_merged():
    ent_path = os.path.join(LLM_DIR, "merged_entities.json")
    rel_path = os.path.join(LLM_DIR, "merged_relations.json")
    with open(ent_path, "r", encoding="utf-8") as f:
        entities = json.load(f).get("entities", [])
    with open(rel_path, "r", encoding="utf-8") as f:
        relations = json.load(f).get("relations", [])
    return entities, relations


def run(uri="bolt://127.0.0.1:7687", user="neo4j", password=None):
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("请先安装: pip install neo4j")
        return

    if not password:
        import getpass
        password = getpass.getpass("Neo4j 密码: ")

    entities, relations = load_llm_merged()
    name_set = {e.get("name", "").strip() for e in entities if e.get("name", "").strip()}
    relations = [r for r in relations if r.get("source") in name_set and r.get("target") in name_set]

    driver = GraphDatabase.driver(uri, auth=(user, password))

    def add_entity(tx, e, i):
        tx.run(
            """
            MERGE (n:LLMEntity {id: $id})
            SET n.name = $name, n.type = $type, n.description = $desc,
                n.confidence = $conf, n.mentions = $mentions, n.is_anchor = $anchor
            """,
            id=i + 1,
            name=e.get("name", "").strip(),
            type=e.get("type", ""),
            desc=(e.get("description") or "")[:500],
            conf=float(e.get("confidence", 0.8)),
            mentions=int(e.get("mentions", 0)),
            anchor=bool(e.get("is_anchor")),
        )

    def add_relation(tx, r):
        tx.run(
            """
            MATCH (a:LLMEntity {name: $src})
            MATCH (b:LLMEntity {name: $tgt})
            CREATE (a)-[r:REL]->(b)
            SET r.rel_type = $rel_type, r.confidence = $conf
            """,
            src=r["source"],
            tgt=r["target"],
            rel_type=r["relation"],
            conf=float(r.get("confidence", 0.8)),
        )

    with driver.session() as session:
        print("创建约束...")
        session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:LLMEntity) REQUIRE n.id IS UNIQUE;")
        print("导入节点...")
        for i, e in enumerate(entities):
            if not e.get("name", "").strip():
                continue
            session.execute_write(add_entity, e, i)
            if (i + 1) % 500 == 0:
                print(f"  已导入 {i + 1} 个节点")
        print("导入关系...")
        for j, r in enumerate(relations):
            session.execute_write(add_relation, r)
            if (j + 1) % 500 == 0:
                print(f"  已导入 {j + 1} 条关系")

    driver.close()
    print("完成。在 Neo4j Query 中执行: MATCH (n:LLMEntity)-[r]-(m) RETURN n,r,m LIMIT 300")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="bolt://127.0.0.1:7687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password", default=None)
    args = parser.parse_args()
    run(uri=args.uri, user=args.user, password=args.password)
