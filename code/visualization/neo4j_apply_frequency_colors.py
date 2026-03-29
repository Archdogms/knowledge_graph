#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
按 merged_entities.ai_type_stats 频次分档配色，写入 Neo4j n.color，并生成 neo4j_style.grass。

规则（与 neo4j_full_build 一致）:
  实体条数降序 — 前 5 红、次 5 蓝、再 5 橙、5 紫、5 青、最后 3 绿（最低频）。

用法:
  pip install neo4j
  set NEO4J_PASSWORD=你的密码
  set NEO4J_DATABASE=nanhaiknowledgegraph   （与库名一致；可选）
  python code/visualization/neo4j_apply_frequency_colors.py

仅更新样式文件、不连库:
  python code/visualization/neo4j_apply_frequency_colors.py --grass-only
"""

from __future__ import annotations

import argparse
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 延迟导入，便于 --help 在未装 neo4j 时仍可用
def _import_nf():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "neo4j_full_build", os.path.join(BASE_DIR, "neo4j_full_build.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    parser = argparse.ArgumentParser(description="频次分档配色 → Neo4j n.color + neo4j_style.grass")
    parser.add_argument("--grass-only", action="store_true", help="只写 .grass 与 palette JSON，不连数据库")
    parser.add_argument("--uri", default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--database", default=None)
    args = parser.parse_args()

    nf = _import_nf()
    entities_path = os.path.join(nf.EXTRACTION_DIR, "merged_entities.json")
    if not os.path.isfile(entities_path):
        print(f"缺少: {entities_path}", file=sys.stderr)
        sys.exit(1)

    with open(entities_path, "r", encoding="utf-8") as f:
        ent_data = json.load(f)
    stats = ent_data.get("ai_type_stats") or {}
    palette, rank_by_type, diam_by_type = nf.build_frequency_style_maps(stats)

    grass_path = os.path.join(nf.EXTRACTION_DIR, "neo4j_style.grass")
    nf.write_neo4j_grass_file(palette, grass_path, rank_by_type)
    print(f"已写入: {grass_path}")

    palette_path = os.path.join(nf.EXTRACTION_DIR, "neo4j_frequency_rank_palette.json")
    ordered = sorted(
        nf.ALL_AI_GRADE_TYPES,
        key=lambda t: (-int(stats.get(t, 0)), t),
    )
    dump = {
        "rule": "降序条数: 5红 + 5蓝 + 5橙 + 5紫 + 5青 + 3绿(最低频)；强对比色 + freq_rank/viz_diameter",
        "by_frequency_rank": [
            {
                "rank": i + 1,
                "ai_type": t,
                "count": int(stats.get(t, 0)),
                "color": palette[t],
                "viz_diameter_px": diam_by_type.get(t),
            }
            for i, t in enumerate(ordered)
        ],
    }
    with open(palette_path, "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=2)
    print(f"已写入: {palette_path}")

    if args.grass_only:
        print("(--grass-only) 已跳过数据库。")
        return

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("未安装 neo4j，跳过写库。可: pip install neo4j", file=sys.stderr)
        return

    uri = (args.uri or os.environ.get("NEO4J_URI") or nf.URI).strip()
    user = (args.user or os.environ.get("NEO4J_USER") or nf.USER).strip()
    password = (args.password or os.environ.get("NEO4J_PASSWORD") or nf.PASSWORD or "").strip()
    if not password:
        import getpass

        password = getpass.getpass("Neo4j 密码: ").strip()
    database = (args.database or os.environ.get("NEO4J_DATABASE") or nf.DATABASE or "").strip()

    n_t = len(nf.ALL_AI_GRADE_TYPES)
    rows = []
    for t in nf.ALL_AI_GRADE_TYPES:
        fr = rank_by_type.get(t, n_t)
        rows.append(
            {
                "ai_type": t,
                "color": palette.get(t, nf.DEFAULT_COLOR),
                "freq_rank": int(fr),
                "viz_diameter": int(diam_by_type.get(t, nf._viz_diameter_for_rank(fr, n_t))),
            }
        )
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        if database:
            session = driver.session(database=database)
        else:
            session = driver.session()
        with session as s:
            s.run(
                """
                UNWIND $rows AS row
                MATCH (n) WHERE n.ai_type = row.ai_type
                SET n.color = row.color,
                    n.freq_rank = row.freq_rank,
                    n.viz_diameter = row.viz_diameter
                """,
                rows=rows,
            )
            n = s.run(
                "MATCH (n) WHERE n.color IS NOT NULL RETURN count(n) AS c"
            ).single()["c"]
        print(f"已更新 Neo4j 中带 color 的节点数: {n}（按 ai_type 批量 SET）")
        print(f"连接: {uri}  库: {database or '(默认)'}")
    except Exception as e:
        print(f"写库失败（.grass 已生成）: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
