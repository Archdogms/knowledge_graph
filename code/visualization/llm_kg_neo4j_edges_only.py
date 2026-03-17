#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
只导入「边」到已有 LlmEntity 节点（节点已通过 Import 或其它方式导入后使用）

用法: pip install neo4j 后执行
  python llm_kg_neo4j_edges_only.py
  按提示输入 Neo4j 密码。
"""

import os
import json
import getpass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output")
LLM_DIR = os.path.join(OUTPUT_DIR, "llm_extraction")


def main():
    try:
        from neo4j import GraphDatabase
        from neo4j.exceptions import AuthError
    except ImportError:
        print("请先安装: pip install neo4j")
        return

    rel_file = os.environ.get("NEO4J_RELATIONS_FILE", "merged_relations.json")
    rel_path = os.path.join(LLM_DIR, rel_file)
    if not os.path.exists(rel_path):
        print(f"未找到关系文件: {rel_path}（可用 NEO4J_RELATIONS_FILE=merged_relations_corrected.json 指定合规修正后的文件）")
        return
    with open(rel_path, "r", encoding="utf-8") as f:
        relations = json.load(f).get("relations", [])

    uri = "bolt://127.0.0.1:7687"
    database = os.environ.get("NEO4J_DATABASE", "culturegraph")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD") or getpass.getpass("Neo4j 密码: ")
    print(f"  使用数据库: {database}, 用户: {user}")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    # 探测实际节点标签和「名称」属性（Import 可能把 CSV 列名映射成别的）
    try:
        with driver.session(database=database) as session:
            labels = session.run("CALL db.labels() YIELD label RETURN label").data()
    except AuthError:
        print("  认证失败：用户名或密码错误。请确认与 Neo4j Browser 中使用的相同（Neo4j Desktop 里点数据库可查看/重置密码）。")
        return
    except Exception as e:
        print(f"  访问数据库失败: {e}")
        return

    with driver.session(database=database) as session:
        label_list = [x["label"] for x in labels]
        node_label = None
        for lb in label_list:
            if "lm" in lb or "LM" in lb:
                node_label = lb
                break
        if not node_label and label_list:
            node_label = [x for x in label_list if not x.startswith("System")][0] if label_list else "LlmEntity"
        if not node_label:
            node_label = "LlmEntity"

        # 取一个节点看所有属性键；名称多半是字符串且像中文/实体名
        sample = session.run(
            f"MATCH (n:`{node_label}`) RETURN properties(n) AS p LIMIT 1"
        ).single()
        name_key = "name"
        if sample and sample["p"]:
            props = sample["p"]
            keys = list(props.keys())
            if "name" in props:
                name_key = "name"
            else:
                # Import 有时会保留 CSV 列名，或变成小写等；选最可能表示“名字”的键
                for k in ["name", "名称", "label", "id"]:
                    if k in props:
                        name_key = k
                        break
                if name_key not in props and keys:
                    name_key = keys[0]
            print(f"  节点标签: {node_label}, 属性键: {keys}, 用做名称的键: {name_key}")
        else:
            print(f"  节点标签: {node_label}, 未取到样本，默认 name_key=name")

        # 试匹配：关系里常见的「康有为」在库里能否用 name_key 找到
        test_name = "康有为"
        hit = session.run(
            f"MATCH (n:`{node_label}`) WHERE n.`{name_key}` = $name RETURN n LIMIT 1",
            name=test_name,
        ).single()
        if not hit:
            # 可能库里是别的写法，查一个任意节点展示其“名称”值
            any_node = session.run(
                f"MATCH (n:`{node_label}`) RETURN n.`{name_key}` AS val LIMIT 1"
            ).single()
            sample_val = any_node["val"] if any_node else "(无)"
            print(f"  警告: 未找到 name={test_name!r} 的节点。库里该属性示例值: {sample_val!r}")
        else:
            print(f"  试匹配成功: {test_name!r} 可找到节点，开始导入边。")

    def add_rel(tx, r):
        tx.run(
            f"""
            MATCH (a:`{node_label}` {{{name_key}: $src}})
            MATCH (b:`{node_label}` {{{name_key}: $tgt}})
            CREATE (a)-[r:REL]->(b)
            SET r.rel_type = $rel_type, r.confidence = $conf
            """,
            src=r["source"].strip(),
            tgt=r["target"].strip(),
            rel_type=r["relation"],
            conf=float(r.get("confidence", 0.8)),
        )

    with driver.session(database=database) as session:
        n = 0
        err = 0
        for r in relations:
            try:
                session.execute_write(add_rel, r)
                n += 1
                if n % 500 == 0:
                    print(f"  已导入 {n} 条边")
            except Exception as e:
                err += 1
                if err <= 2:
                    print(f"  示例失败: source={r.get('source')!r} target={r.get('target')!r} -> {e}")
        print(f"完成。成功 {n} 条，跳过/失败 {err} 条")
    driver.close()
    print("在 Neo4j 中执行: MATCH (n:LlmEntity)-[r:REL]-(m) RETURN n,r,m LIMIT 300 即可看图")


if __name__ == "__main__":
    main()
