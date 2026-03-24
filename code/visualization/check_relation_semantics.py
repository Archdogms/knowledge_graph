#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查关系语义是否合理（如「活动于」终点应是地点/朝代，不应是人物）。
从 merged_entities.json 与 merged_relations.json 读入，输出异常关系列表。

用法: python check_relation_semantics.py
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output")
LLM_DIR = os.path.join(OUTPUT_DIR, "llm_extraction")


# 关系类型 -> 终点合理的实体类型（若终点是其他类型则视为可疑）
# 同时兼容旧版与新版实体类型。
REL_TARGET_OK = {
    "活动于": ["地名空间", "地名", "文物建筑", "文物遗址", "建筑遗迹", "朝代年号", "历史事件"],  # 活动于某地/某时
    "位于": ["地名空间", "地名"],
    "出生于": ["地名空间", "地名"],
    "发生于": ["地名空间", "地名", "朝代年号", "历史事件"],
    "始建于": ["朝代年号"],
    "记载于": ["典籍文献", "典籍作品"],
    "传承于": ["地名空间", "地名", "宗族姓氏", "人物"],
    "创建修建": ["文物建筑", "文物遗址", "建筑遗迹"],
    "承载文化": ["非遗项目", "非遗技艺", "民俗礼仪", "物产饮食"],
    "盛产": ["物产饮食"],
    "同族": ["人物", "宗族姓氏"],
    "关联人物": ["人物", "文物建筑", "文物遗址", "建筑遗迹", "地名空间", "地名"],
    "著有": ["典籍文献", "典籍作品"],
    "同类": [],  # 任意类型都可能
    "属于时期": ["朝代年号"],
}


def main():
    entities_path = os.path.join(LLM_DIR, "merged_entities.json")
    relations_path = os.path.join(LLM_DIR, "merged_relations.json")
    if not os.path.exists(entities_path) or not os.path.exists(relations_path):
        print("未找到 merged_entities.json 或 merged_relations.json")
        return

    with open(entities_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    name_to_type = {}
    for e in data.get("entities", []):
        name_to_type[e.get("name", "").strip()] = e.get("type", "")

    with open(relations_path, "r", encoding="utf-8") as f:
        rel_data = json.load(f)

    anomalies = []
    for r in rel_data.get("relations", []):
        rel_type = (r.get("relation") or "").strip()
        target_type = name_to_type.get((r.get("target") or "").strip(), "")
        ok_types = REL_TARGET_OK.get(rel_type)
        if ok_types is None:
            continue
        if ok_types and target_type and target_type not in ok_types:
            anomalies.append({
                "source": r.get("source"),
                "target": r.get("target"),
                "relation": rel_type,
                "target_type": target_type,
                "expected": ok_types,
            })

    # 按关系类型汇总
    by_rel = {}
    for a in anomalies:
        k = a["relation"]
        by_rel.setdefault(k, []).append(a)

    print("关系语义异常统计（终点类型不符合预期）")
    print("=" * 60)
    for rel_type in sorted(by_rel.keys(), key=lambda x: -len(by_rel[x])):
        items = by_rel[rel_type]
        print(f"\n【{rel_type}】 共 {len(items)} 条异常")
        print(f"  期望终点类型: {REL_TARGET_OK.get(rel_type, [])}")
        for u in items[:15]:
            print(f"    {u['source']} --[{rel_type}]--> {u['target']} (终点类型: {u['target_type']})")
        if len(items) > 15:
            print(f"    ... 还有 {len(items) - 15} 条")

    print("\n" + "=" * 60)
    print(f"合计异常: {len(anomalies)} 条")
    print("说明: 属 LLM 抽取阶段错误，可在 Neo4j 中按「browser_统计与查看.cypher」第 8 条查询核对并决定是否删除。")


if __name__ == "__main__":
    main()
