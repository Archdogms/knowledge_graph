#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Neo4j 南海知识图谱一键构建
读取 qwen_extraction 的 merged_entities / merged_relations → 按 AI小类 分标签分色 → 关系按 relation_group 分类型
"""

import os
import json
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXTRACTION_DIR = os.path.join(BASE_DIR, "..", "..", "output", "qwen_extraction")

URI = "bolt://127.0.0.1:7687"
USER = "neo4j"
PASSWORD = "ms781125"
DATABASE = "nanhaiknowledgegraph"

BATCH_SIZE = 500

# ────────────────────────── AI小类颜色表 (31 种) ──────────────────────────
AI_TYPE_COLORS = {
    "A1 表演艺术类非遗":           "#E74C3C",
    "A2 传统技艺类非遗":           "#E67E22",
    "A3 民俗节庆类非遗":           "#F39C12",
    "A4 信俗礼仪类非遗":           "#D35400",
    "A5 传统体育游艺类非遗":       "#C0392B",
    "A6 饮食酿造类非遗及文化物产": "#F1C40F",
    "B1 古建筑类":                 "#D4A76A",
    "B2 宗教建筑类":               "#B8860B",
    "B3 纪念性建筑与名人故居类":   "#CD853F",
    "B4 古遗址与生产遗存类":       "#8B6914",
    "B5 石刻碑记类":               "#A0522D",
    "B6 古村落与聚落遗产类":       "#DEB887",
    "C1 历史文化人物":             "#3498DB",
    "C2 非遗传承人及技艺人物":     "#2980B9",
    "C3 文物营建与守护人物":       "#2471A3",
    "C4 宗族姓氏与地方社群":       "#5DADE2",
    "D1 山川水系空间":             "#27AE60",
    "D2 镇街圩市空间":             "#2ECC71",
    "D3 历史街区与传统片区":       "#1ABC9C",
    "D4 传承场所与活动场地":       "#16A085",
    "E1 地方志类":                 "#8E44AD",
    "E2 族谱家乘类":               "#9B59B6",
    "E3 碑记题咏类":               "#7D3C98",
    "E4 文集著述类":               "#A569BD",
    "E5 口述史与地方记忆材料":     "#BB8FCE",
    "F1 朝代年号类":               "#5499C7",
    "F2 历史事件类":               "#48C9B0",
    "F3 发展阶段类":               "#76D7C4",
}

DEFAULT_COLOR = "#A5ABB6"

# AI小类代号 → 全称 映射 (自动从 AI_TYPE_COLORS 生成)
CODE_TO_FULL = {}
for _full_name in AI_TYPE_COLORS:
    _code = _full_name.split()[0]
    CODE_TO_FULL[_code] = _full_name


def ai_type_to_label(ai_type: str) -> str:
    """'A1 表演艺术类非遗' → 'A1'"""
    return ai_type.split()[0] if ai_type else "OTHER"


def main():
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("请先安装: pip install neo4j")
        sys.exit(1)

    entities_path = os.path.join(EXTRACTION_DIR, "merged_entities.json")
    relations_path = os.path.join(EXTRACTION_DIR, "merged_relations.json")
    for p in [entities_path, relations_path]:
        if not os.path.exists(p):
            print(f"缺少文件: {p}")
            sys.exit(1)

    print("加载数据...")
    t0 = time.time()
    with open(entities_path, "r", encoding="utf-8") as f:
        ent_data = json.load(f)
    entities = ent_data.get("entities", [])

    with open(relations_path, "r", encoding="utf-8") as f:
        rel_data = json.load(f)
    relations = rel_data.get("relations", [])
    print(f"  实体: {len(entities)} | 关系: {len(relations)} | 耗时: {time.time()-t0:.1f}s")

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    print(f"连接: {URI}  数据库: {DATABASE}\n")

    # ═══ 1. 清库 ═══
    print("[1/7] 清空数据库...")
    with driver.session(database=DATABASE) as s:
        s.run("MATCH (n) DETACH DELETE n")
    print("  done.\n")

    # ═══ 2. 约束 + 索引 ═══
    print("[2/7] 创建约束和索引...")
    with driver.session(database=DATABASE) as s:
        for stmt in [
            "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (n:Entity) REQUIRE n.name IS UNIQUE",
            "CREATE INDEX idx_ai_type IF NOT EXISTS FOR (n:Entity) ON (n.ai_type)",
            "CREATE INDEX idx_ai_label IF NOT EXISTS FOR (n:Entity) ON (n.ai_label)",
            "CREATE INDEX idx_official_label IF NOT EXISTS FOR (n:Entity) ON (n.official_label)",
        ]:
            try:
                s.run(stmt)
            except Exception as e:
                print(f"  跳过: {e}")
    print("  done.\n")

    # ═══ 3. 导入节点 (带 Entity 公共标签) ═══
    print("[3/7] 导入节点...")
    total_nodes = 0
    with driver.session(database=DATABASE) as s:
        for i in range(0, len(entities), BATCH_SIZE):
            batch = entities[i : i + BATCH_SIZE]
            params = []
            for e in batch:
                ai_type = (e.get("ai_grade_type") or "").strip()
                params.append({
                    "name":           (e.get("name") or "").strip(),
                    "ai_label":       (e.get("ai_grade_label") or "").strip(),
                    "ai_type":        ai_type,
                    "ai_type_code":   ai_type_to_label(ai_type),
                    "ai_layer":       (e.get("ai_layer") or "").strip(),
                    "official_label": (e.get("official_label") or "").strip(),
                    "official_type":  (e.get("official_type") or "").strip(),
                    "description":    (e.get("description") or "").strip(),
                    "confidence":     float(e.get("confidence", 0)),
                    "mentions":       int(e.get("mentions", 0)),
                    "source_count":   int(e.get("source_count", 0)),
                    "is_anchor":      bool(e.get("is_anchor", False)),
                    "color":          AI_TYPE_COLORS.get(ai_type, DEFAULT_COLOR),
                })
            s.run("""
                UNWIND $batch AS row
                MERGE (n:Entity {name: row.name})
                SET n.ai_label       = row.ai_label,
                    n.ai_type        = row.ai_type,
                    n.ai_type_code   = row.ai_type_code,
                    n.ai_layer       = row.ai_layer,
                    n.official_label = row.official_label,
                    n.official_type  = row.official_type,
                    n.description    = row.description,
                    n.confidence     = row.confidence,
                    n.mentions       = row.mentions,
                    n.source_count   = row.source_count,
                    n.is_anchor      = row.is_anchor,
                    n.color          = row.color
            """, batch=params)
            total_nodes += len(batch)
            if (i // BATCH_SIZE + 1) % 4 == 0 or i + BATCH_SIZE >= len(entities):
                print(f"  节点: {total_nodes}/{len(entities)}")
    print(f"  done: {total_nodes}\n")

    # ═══ 4. 给节点添加 AI小类代号标签 (A1, B1, ..., F3) ═══
    print("[4/7] 添加AI小类标签 (用于 Browser 颜色区分)...")
    with driver.session(database=DATABASE) as s:
        for ai_type, color in AI_TYPE_COLORS.items():
            code = ai_type_to_label(ai_type)
            result = s.run(
                f"MATCH (n:Entity) WHERE n.ai_type = $t SET n:`{code}` RETURN count(n) AS cnt",
                t=ai_type,
            )
            cnt = result.single()["cnt"]
            if cnt > 0:
                print(f"  :{code}  {color}  {ai_type}: {cnt}")
    print("  done.\n")

    # ═══ 5. 导入关系 (按 relation_group 分类型) ═══
    print("[5/7] 导入关系...")
    groups = {}
    for r in relations:
        g = (r.get("relation_group") or "RELATED").strip()
        groups.setdefault(g, []).append(r)

    total_edges = 0
    total_skipped = 0
    for group_name, rels in sorted(groups.items(), key=lambda x: -len(x[1])):
        safe_type = group_name.replace("`", "")
        group_edges = 0
        with driver.session(database=DATABASE) as s:
            for i in range(0, len(rels), BATCH_SIZE):
                batch = rels[i : i + BATCH_SIZE]
                params = [{
                    "src":           (r.get("source") or "").strip(),
                    "tgt":           (r.get("target") or "").strip(),
                    "relation_text": (r.get("relation_text") or "").strip(),
                    "confidence":    float(r.get("confidence", 0.8)),
                    "evidence":      (r.get("evidence") or "")[:300],
                    "source_file":   (r.get("source_file") or ""),
                } for r in batch]
                result = s.run(f"""
                    UNWIND $batch AS row
                    MATCH (a:Entity {{name: row.src}})
                    MATCH (b:Entity {{name: row.tgt}})
                    CREATE (a)-[r:`{safe_type}`]->(b)
                    SET r.relation_text = row.relation_text,
                        r.confidence    = row.confidence,
                        r.evidence      = row.evidence,
                        r.source_file   = row.source_file
                    RETURN count(r) AS cnt
                """, batch=params)
                cnt = result.single()["cnt"]
                group_edges += cnt
                total_skipped += len(batch) - cnt
        total_edges += group_edges
        print(f"  [{group_name}]: {group_edges} 条")
    print(f"  done: {total_edges} 条 (跳过 {total_skipped} 条，因端点不存在)\n")

    # ═══ 6. 移除 Entity 公共标签 → Browser 按 A1/B1/... 自动分色 ═══
    print("[6/7] 移除 Entity 标签 → Browser 按AI小类自动分色...")
    with driver.session(database=DATABASE) as s:
        cnt = s.run("MATCH (n:Entity) REMOVE n:Entity RETURN count(n) AS c").single()["c"]
    print(f"  处理 {cnt} 个节点\n")

    # ═══ 7. 最终验证 ═══
    print("[7/7] 验证统计")
    print("═" * 55)
    with driver.session(database=DATABASE) as s:
        nc = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        ec = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]

        type_dist = s.run("""
            MATCH (n)
            RETURN n.ai_type AS ai_type, n.color AS color, count(n) AS cnt
            ORDER BY cnt DESC
        """).data()

        rel_dist = s.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS rel_group, count(r) AS cnt
            ORDER BY cnt DESC
        """).data()

    print(f"  节点: {nc}  |  关系: {ec}")
    print(f"\n  AI小类分布:")
    for row in type_dist:
        bar = "█" * max(1, row["cnt"] // 100)
        print(f"    {row['color'] or '       '}  {row['ai_type']}: {row['cnt']}  {bar}")
    print(f"\n  关系分组分布:")
    for row in rel_dist:
        print(f"    {row['rel_group']}: {row['cnt']}")

    elapsed = time.time() - t0
    driver.close()

    print(f"\n{'═' * 55}")
    print(f"构建完成！耗时 {elapsed:.1f}s")
    print(f"\n在 Neo4j Browser 中查看:")
    print(f"  MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 300")
    print(f"\n按AI小类查看:")
    print(f"  MATCH (n:A1)-[r]->(m) RETURN n, r, m LIMIT 100")
    print(f"  MATCH (n:C1)-[r]->(m) RETURN n, r, m LIMIT 100")
    print(f"\n按关系分组查看:")
    print(f"  MATCH (n)-[r:人物关联]->(m) RETURN n, r, m LIMIT 100")
    print(f"  MATCH (n)-[r:空间关联]->(m) RETURN n, r, m LIMIT 100")

    # ═══ 生成 GRASS 样式文件 (可导入 Browser) ═══
    grass_path = os.path.join(EXTRACTION_DIR, "neo4j_style.grass")
    grass_lines = ["node {\n  diameter: 40px;\n  font-size: 12px;\n  caption: '{name}';\n}\n"]
    for ai_type, color in AI_TYPE_COLORS.items():
        code = ai_type_to_label(ai_type)
        grass_lines.append(f"node.{code} {{\n  color: {color};\n  border-color: {color};\n  caption: '{{name}}';\n}}\n")
    grass_lines.append("relationship {\n  font-size: 10px;\n  caption: '{relation_text}';\n}\n")
    with open(grass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(grass_lines))
    print(f"\nGRASS 样式文件已生成: {grass_path}")
    print("  在 Browser 中: 点击左上角齿轮 → 拖入该文件 即可应用自定义颜色\n")


if __name__ == "__main__":
    main()
