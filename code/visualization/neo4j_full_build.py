#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Neo4j 南海知识图谱一键构建
读取 qwen_extraction 的 merged_entities / merged_relations → 按 AI小类 分标签分色 → 关系按 relation_group 分类型

节点颜色 n.color 与 neo4j_style.grass 按 merged_entities.ai_type_stats 实体条数降序分档：
  前 5 红 → 次 5 蓝 → 5 橙 → 5 紫 → 5 青 → 最低 3 绿；每档内色相拉宽便于区分。
  频次排名还写入 n.freq_rank、n.viz_diameter；grass 中按排名加大节点直径与描边（越高频越大、越粗）。
仅改样式不重导全量: neo4j_apply_frequency_colors.py
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

DEFAULT_COLOR = "#546E7A"

# 全量 AI 小类（与 merged / 抽取 schema 一致）
ALL_AI_GRADE_TYPES: tuple[str, ...] = (
    "A1 表演艺术类非遗",
    "A2 传统技艺类非遗",
    "A3 民俗节庆类非遗",
    "A4 信俗礼仪类非遗",
    "A5 传统体育游艺类非遗",
    "A6 饮食酿造类非遗及文化物产",
    "B1 古建筑类",
    "B2 宗教建筑类",
    "B3 纪念性建筑与名人故居类",
    "B4 古遗址与生产遗存类",
    "B5 石刻碑记类",
    "B6 古村落与聚落遗产类",
    "C1 历史文化人物",
    "C2 非遗传承人及技艺人物",
    "C3 文物营建与守护人物",
    "C4 宗族姓氏与地方社群",
    "D1 山川水系空间",
    "D2 镇街圩市空间",
    "D3 历史街区与传统片区",
    "D4 传承场所与活动场地",
    "E1 地方志类",
    "E2 族谱家乘类",
    "E3 碑记题咏类",
    "E4 文集著述类",
    "E5 口述史与地方记忆材料",
    "F1 朝代年号类",
    "F2 历史事件类",
    "F3 发展阶段类",
)

# 各大类独立色系；元组顺序对应小类编号 1、2、3…（A1 取 [0]，A6 取 [5]）
_MAJOR_PALETTES: dict[str, tuple[str, ...]] = {
    "A": ("#B71C1C", "#C62828", "#D32F2F", "#E53935", "#8B0000", "#BF360C"),  # 非遗·红
    "B": ("#E65100", "#EF6C00", "#F57C00", "#D84315", "#BF360C", "#A1887F"),  # 物质·橙/褐
    "C": ("#0D47A1", "#1565C0", "#1976D2", "#1E88E5"),  # 传承主体·蓝
    "D": ("#1B5E20", "#2E7D32", "#388E3C", "#43A047"),  # 文化空间·绿
    "E": ("#4A148C", "#6A1B9A", "#7B1FA2", "#8E24AA", "#38006B"),  # 文献·紫
    "F": ("#006064", "#00838F", "#0097A7"),  # 时序·青
}

AI_MAJOR_LABEL: dict[str, str] = {
    "A": "A 非遗文化体系",
    "B": "B 物质文化遗产体系",
    "C": "C 传承主体体系",
    "D": "D 文化空间体系",
    "E": "E 文献记忆体系",
    "F": "F 历史时序体系",
}


def ai_type_to_label(ai_type: str) -> str:
    """'A1 表演艺术类非遗' → 'A1'"""
    return ai_type.split()[0] if ai_type else "OTHER"


def _grass_border_color(fill_hex: str) -> str:
    """填充色加深约 35% 作为描边，提高节点轮廓对比度。"""
    h = (fill_hex or "").lstrip("#")
    if len(h) != 6:
        return fill_hex or "#37474F"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = max(0, min(255, int(r * 0.62)))
    g = max(0, min(255, int(g * 0.62)))
    b = max(0, min(255, int(b * 0.62)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _type_code_major_index(ai_type: str) -> tuple[str, int]:
    """'A1 表演艺术类非遗' → ('A', 0)；'F3 …' → ('F', 2)。"""
    parts = (ai_type or "").strip().split()
    if not parts:
        return "", -1
    code = parts[0]
    if len(code) < 2 or not code[0].isalpha() or not code[1].isdigit():
        return "", -1
    major = code[0].upper()
    idx = int(code[1]) - 1
    return major, idx


def build_ai_type_colors_by_major() -> dict[str, str]:
    """按大类固定色系 + 小类序号取同系深浅档（备用，非默认导入）。"""
    out: dict[str, str] = {}
    for ai_type in ALL_AI_GRADE_TYPES:
        major, idx = _type_code_major_index(ai_type)
        variants = _MAJOR_PALETTES.get(major)
        if not variants or idx < 0 or idx >= len(variants):
            out[ai_type] = DEFAULT_COLOR
            continue
        out[ai_type] = variants[idx]
    return out


# 频次分档：每档 5 色刻意拉大色相/明度差，避免「一片糊蓝」
_PALETTE_FREQ_RED = ("#5D0014", "#E53935", "#FF7043", "#B71C1C", "#880E4F")
_PALETTE_FREQ_BLUE = ("#0A1647", "#1565C0", "#0277BD", "#283593", "#006064")
_PALETTE_FREQ_ORANGE = ("#E65100", "#F9A825", "#BF360C", "#4E342E", "#FF3D00")
_PALETTE_FREQ_PURPLE = ("#311B92", "#C2185B", "#6A1B9A", "#7C4DFF", "#4A148C")
_PALETTE_FREQ_CYAN = ("#004D40", "#00ACC1", "#00838F", "#455A64", "#0097A7")
_PALETTE_FREQ_GREEN = ("#00C853", "#1B5E20", "#33691E")


def build_frequency_style_maps(
    ai_type_stats: dict,
) -> tuple[dict[str, str], dict[str, int], dict[str, int]]:
    """
    返回 (color, freq_rank 从 1 起, viz_diameter 像素)。
    排名越靠前节点越大、描边越粗（在 grass 里按 rank 写死），颜色对比更强。
    """
    stats = ai_type_stats or {}
    ordered = sorted(ALL_AI_GRADE_TYPES, key=lambda t: (-int(stats.get(t, 0)), t))
    n = len(ordered)
    bands = (
        _PALETTE_FREQ_RED,
        _PALETTE_FREQ_BLUE,
        _PALETTE_FREQ_ORANGE,
        _PALETTE_FREQ_PURPLE,
        _PALETTE_FREQ_CYAN,
        _PALETTE_FREQ_GREEN,
    )
    colors: dict[str, str] = {}
    ranks: dict[str, int] = {}
    diameters: dict[str, int] = {}
    i = 0
    for band in bands:
        for hex_c in band:
            if i >= n:
                break
            t = ordered[i]
            colors[t] = hex_c
            ranks[t] = i + 1
            diameters[t] = _viz_diameter_for_rank(i + 1, n)
            i += 1
    while i < n:
        t = ordered[i]
        colors[t] = DEFAULT_COLOR
        ranks[t] = i + 1
        diameters[t] = _viz_diameter_for_rank(i + 1, n)
        i += 1
    return colors, ranks, diameters


def _viz_diameter_for_rank(rank: int, n_types: int) -> int:
    """1=最大 52px，最后≈22px，中间线性。"""
    if n_types <= 1:
        return 40
    lo, hi = 22, 52
    return int(round(hi - (rank - 1) * (hi - lo) / (n_types - 1)))


def _grass_diameter_for_grass_rank(rank: int) -> int:
    """Browser 按标签写死的直径；未知档位用中等大小。"""
    n = len(ALL_AI_GRADE_TYPES)
    if rank < 1 or rank > n + 5:
        return 32
    return _viz_diameter_for_rank(rank, n)


def _grass_border_width_for_grass_rank(rank: int) -> int:
    if rank < 1 or rank > len(ALL_AI_GRADE_TYPES) + 5:
        return 2
    if rank <= 5:
        return 4
    if rank <= 10:
        return 3
    if rank <= 20:
        return 2
    return 1


def build_ai_type_colors_from_stats(ai_type_stats: dict) -> dict[str, str]:
    """仅颜色 dict（兼容旧调用）；新逻辑请用 build_frequency_style_maps。"""
    c, _, _ = build_frequency_style_maps(ai_type_stats)
    return c


def write_neo4j_grass_file(
    palette: dict[str, str],
    grass_path: str,
    rank_by_type: dict[str, int] | None = None,
) -> None:
    """写入 Browser 用 .grass；若提供 rank_by_type，则按排名设直径与 border-width。"""
    grass_lines = [
        "/* 频次分档+强对比色; 排名高=更大节点+更粗描边 | 与 n.color / n.freq_rank / n.viz_diameter 同步 */\n",
        "node {\n  font-size: 12px;\n  caption: '{name}';\n  text-color-internal: #FFFFFF;\n}\n",
    ]
    for ai_type in ALL_AI_GRADE_TYPES:
        color = palette.get(ai_type, DEFAULT_COLOR)
        bd = _grass_border_color(color)
        r = (rank_by_type or {}).get(ai_type, 99)
        dia = _grass_diameter_for_grass_rank(r)
        bw = _grass_border_width_for_grass_rank(r)
        safe_label = ai_type.replace("`", "")
        grass_lines.append(
            f"node.`{safe_label}` {{\n"
            f"  color: {color};\n"
            f"  border-color: {bd};\n"
            f"  border-width: {bw}px;\n"
            f"  diameter: {dia}px;\n"
            f"  caption: '{{name}}';\n"
            f"}}\n"
        )
    grass_lines.append(
        "relationship {\n  color: #78909C;\n  shaft-width: 2px;\n  font-size: 10px;\n  caption: '{relation_text}';\n}\n"
    )
    with open(grass_path, "w", encoding="utf-8") as f:
        f.write("".join(grass_lines))


# AI小类代号 → 全称（供外部脚本使用）
CODE_TO_FULL = {t.split()[0]: t for t in ALL_AI_GRADE_TYPES}


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

    name_to_types: dict[str, set[str]] = {}
    for e in entities:
        nm = (e.get("name") or "").strip()
        at = (e.get("ai_grade_type") or "").strip()
        if nm and at:
            name_to_types.setdefault(nm, set()).add(at)
    multi_type = sum(1 for ts in name_to_types.values() if len(ts) > 1)
    print(f"  唯一实体名: {len(name_to_types)} | 跨类同名实体: {multi_type}")

    stats = ent_data.get("ai_type_stats") or {}
    palette, rank_by_type, diam_by_type = build_frequency_style_maps(stats)
    print("  配色: 按 ai_type_stats 频次降序 — 红→蓝→橙→紫→青→绿；强对比色 + 排名→节点大小/描边（grass）")

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
    n_types = len(ALL_AI_GRADE_TYPES)
    with driver.session(database=DATABASE) as s:
        for i in range(0, len(entities), BATCH_SIZE):
            batch = entities[i : i + BATCH_SIZE]
            params = []
            for e in batch:
                ai_type = (e.get("ai_grade_type") or "").strip()
                fr = rank_by_type.get(ai_type)
                if fr is None:
                    fr = n_types
                    vd = _viz_diameter_for_rank(n_types, n_types)
                else:
                    vd = diam_by_type.get(ai_type, _viz_diameter_for_rank(fr, n_types))
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
                    "color":          palette.get(ai_type, DEFAULT_COLOR),
                    "freq_rank":      int(fr),
                    "viz_diameter":   int(vd),
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
                    n.color          = row.color,
                    n.freq_rank      = row.freq_rank,
                    n.viz_diameter   = row.viz_diameter
            """, batch=params)
            total_nodes += len(batch)
            if (i // BATCH_SIZE + 1) % 4 == 0 or i + BATCH_SIZE >= len(entities):
                print(f"  节点: {total_nodes}/{len(entities)}")
    print(f"  done: {total_nodes}\n")

    # ═══ 4. 给节点添加 AI小类中文标签 (按 name_to_types 赋多标签) ═══
    print("[4/7] 添加AI小类中文标签 (用于 Browser 分类显示)...")
    total_label_assignments = 0
    with driver.session(database=DATABASE) as s:
        for ai_type in ALL_AI_GRADE_TYPES:
            color = palette.get(ai_type, DEFAULT_COLOR)
            names_with_type = [n for n, ts in name_to_types.items() if ai_type in ts]
            if not names_with_type:
                continue
            safe_label = ai_type.replace("`", "")
            for j in range(0, len(names_with_type), BATCH_SIZE):
                batch_names = names_with_type[j : j + BATCH_SIZE]
                s.run(
                    f"UNWIND $names AS nm MATCH (n:Entity {{name: nm}}) SET n:`{safe_label}` RETURN count(n)",
                    names=batch_names,
                )
            total_label_assignments += len(names_with_type)
            print(f"  {color}  {ai_type}: {len(names_with_type)}")
    print(f"  done. 标签赋值合计: {total_label_assignments} (含跨类重复)\n")

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
    print(f"  MATCH (n:`C1 历史文化人物`)-[r]->(m) RETURN n, r, m LIMIT 100")
    print(f"  MATCH (n:`A1 表演艺术类非遗`)-[r]->(m) RETURN n, r, m LIMIT 100")
    print(f"\n按关系分组查看:")
    print(f"  MATCH (n)-[r:人物关联]->(m) RETURN n, r, m LIMIT 100")
    print(f"  MATCH (n)-[r:空间关联]->(m) RETURN n, r, m LIMIT 100")

    # ═══ 生成 GRASS 样式文件 (可导入 Browser) ═══
    grass_path = os.path.join(EXTRACTION_DIR, "neo4j_style.grass")
    write_neo4j_grass_file(palette, grass_path, rank_by_type)
    print(f"\nGRASS 样式文件已生成: {grass_path}")
    print("  在 Browser 中: 点击左上角齿轮 → 拖入该文件 即可应用自定义颜色\n")


if __name__ == "__main__":
    main()
