#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知识图谱论文级可视化

生成：
  1. 知识图谱全景图 (PNG/SVG)
  2. 核心节点子图 (PNG/SVG)
  3. 实体/关系类型分布图 (PNG/SVG)
  4. LLM vs 规则抽取对比表
  5. 优化版交互式HTML (pyvis)

输出到 output/knowledge_graph/
"""

import os
import json
import math
from collections import Counter, defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 中文字体设置
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
DB_DIR = os.path.join(DATA_DIR, "database")
LLM_DIR = os.path.join(BASE_DIR, "..", "..", "output", "llm_extraction")
KG_OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output", "knowledge_graph")

TYPE_COLORS = {
    "人物":     "#FF6B6B",
    "建筑":     "#45B7D1",
    "地点":     "#4ECDC4",
    "朝代":     "#98D8C8",
    "文化要素": "#F7DC6F",
    "事件":     "#FFA07A",
    "不可移动文物": "#E74C3C",
    "非遗项目":     "#F39C12",
    "文化景观":     "#1ABC9C",
    "历史文化名村": "#8E44AD",
    "圩市街区":     "#D35400",
    "景点":     "#2ECC71",
    "镇街":     "#3498DB",
}

RELATION_COLORS = {
    "典籍记载": "#E74C3C",
    "创建修建": "#C0392B",
    "关联人物": "#FF6B6B",
    "文化承载": "#F39C12",
    "对应景点": "#2ECC71",
    "传承于":   "#8E44AD",
    "位于":     "#3498DB",
    "同时代":   "#98D8C8",
    "同门类":   "#D35400",
    "发生于":   "#FFA07A",
    "共现关联": "#888888",
}


def load_data():
    """加载LLM抽取的合并数据（如果有），否则加载现有数据"""
    entities = None
    relations = None

    llm_ent = os.path.join(LLM_DIR, "merged_entities.json")
    llm_rel = os.path.join(LLM_DIR, "merged_relations.json")

    if os.path.exists(llm_ent):
        with open(llm_ent, "r", encoding="utf-8") as f:
            entities = json.load(f)
        print(f"LLM实体: {entities['total']} 条")

    if os.path.exists(llm_rel):
        with open(llm_rel, "r", encoding="utf-8") as f:
            relations = json.load(f)
        print(f"LLM关系: {relations['total']} 条")

    # 回退到现有数据
    if entities is None:
        with open(os.path.join(DB_DIR, "culture_entities.json"), "r", encoding="utf-8") as f:
            entities = json.load(f)
        print(f"规则实体: {entities['total']} 条")

    if relations is None:
        with open(os.path.join(DB_DIR, "culture_relations.json"), "r", encoding="utf-8") as f:
            relations = json.load(f)
        print(f"规则关系: {relations['total']} 条")

    # 文化锚点
    anchors = []
    anchor_path = os.path.join(DB_DIR, "cultural_anchors.json")
    if os.path.exists(anchor_path):
        with open(anchor_path, "r", encoding="utf-8") as f:
            anchors = json.load(f).get("anchors", [])

    return entities, relations, anchors


def plot_entity_distribution(entities, output_dir):
    """实体类型分布图"""
    type_stats = entities.get("type_stats", {})
    if not type_stats:
        type_stats = dict(Counter(e["type"] for e in entities.get("entities", [])))

    labels = list(type_stats.keys())
    values = list(type_stats.values())
    colors = [TYPE_COLORS.get(l, "#888") for l in labels]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # 饼图
    wedges, texts, autotexts = ax1.pie(
        values, labels=labels, colors=colors,
        autopct='%1.1f%%', startangle=90,
        textprops={'fontsize': 10}
    )
    ax1.set_title('文化实体类型分布', fontsize=14, fontweight='bold')

    # 柱状图
    bars = ax2.barh(labels, values, color=colors, edgecolor='#333', linewidth=0.5)
    ax2.set_xlabel('数量', fontsize=12)
    ax2.set_title('文化实体数量统计', fontsize=14, fontweight='bold')
    for bar, val in zip(bars, values):
        ax2.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                 str(val), ha='left', va='center', fontsize=10)

    plt.tight_layout()

    for fmt in ['png', 'svg']:
        path = os.path.join(output_dir, f'entity_distribution.{fmt}')
        fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  实体分布图: entity_distribution.png/svg")


def plot_relation_distribution(relations, output_dir):
    """关系类型分布图"""
    if "relation_stats" in relations:
        rel_stats = relations["relation_stats"]
    else:
        rel_stats = dict(Counter(r.get("relation", "未知") for r in relations.get("relations", [])))

    labels = list(rel_stats.keys())
    values = list(rel_stats.values())
    colors = [RELATION_COLORS.get(l, "#888") for l in labels]

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(labels, values, color=colors, edgecolor='#333', linewidth=0.5)
    ax.set_ylabel('数量', fontsize=12)
    ax.set_title('知识图谱关系类型分布', fontsize=14, fontweight='bold')
    ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=10)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                str(val), ha='center', va='bottom', fontsize=9)

    plt.tight_layout()

    for fmt in ['png', 'svg']:
        path = os.path.join(output_dir, f'relation_distribution.{fmt}')
        fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  关系分布图: relation_distribution.png/svg")


def plot_kg_overview(entities, relations, anchors, output_dir):
    """知识图谱三层结构全景图（简化版，用 networkx 布局）"""
    try:
        import networkx as nx
    except ImportError:
        print("  跳过全景图（需要 networkx）")
        return

    G = nx.Graph()

    anchor_names = {a["name"] for a in anchors}
    ent_list = entities.get("entities", [])

    # 选取核心节点
    top_entities = sorted(ent_list, key=lambda x: x.get("mentions", x.get("weight", 0)), reverse=True)[:60]

    for e in top_entities:
        G.add_node(e["name"], type=e["type"], layer="culture",
                   size=min(300, max(50, e.get("mentions", 5) * 5)))

    for a in anchors[:50]:
        if a["name"] not in G:
            G.add_node(a["name"], type=a["anchor_type"], layer="anchor", size=200)

    rel_list = relations.get("relations", [])
    for r in rel_list:
        src = r.get("source", r.get("source_name", ""))
        tgt = r.get("target", r.get("target_name", ""))
        if src in G and tgt in G:
            G.add_edge(src, tgt, relation=r.get("relation", "关联"))

    if len(G.nodes) < 3:
        print("  节点不足，跳过全景图")
        return

    fig, ax = plt.subplots(figsize=(16, 12))
    pos = nx.spring_layout(G, k=2.5, iterations=80, seed=42)

    for node in G.nodes():
        data = G.nodes[node]
        color = TYPE_COLORS.get(data.get("type", ""), "#888")
        size = data.get("size", 100)
        ax.scatter(pos[node][0], pos[node][1], c=color, s=size, alpha=0.8,
                   edgecolors='#333', linewidths=0.5, zorder=3)

    for u, v in G.edges():
        ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                color='#aaa', alpha=0.3, linewidth=0.5, zorder=1)

    for node in G.nodes():
        data = G.nodes[node]
        if data.get("size", 0) > 120 or node in anchor_names:
            ax.annotate(node, pos[node], fontsize=7, ha='center', va='bottom',
                       color='#333', zorder=4)

    ax.set_title('南海区文旅知识图谱全景', fontsize=16, fontweight='bold')
    ax.axis('off')

    # 图例
    legend_items = []
    for t, c in TYPE_COLORS.items():
        count = sum(1 for n in G.nodes() if G.nodes[n].get("type") == t)
        if count > 0:
            legend_items.append(plt.scatter([], [], c=c, s=80, label=f'{t} ({count})'))
    if legend_items:
        ax.legend(handles=legend_items, loc='upper left', fontsize=8, framealpha=0.9)

    plt.tight_layout()
    for fmt in ['png', 'svg']:
        path = os.path.join(output_dir, f'kg_overview.{fmt}')
        fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  全景图: kg_overview.png/svg")


def plot_subgraph(entities, relations, center_name, output_dir):
    """以核心节点为中心的子图"""
    try:
        import networkx as nx
    except ImportError:
        return

    ent_names = {e["name"]: e for e in entities.get("entities", [])}
    if center_name not in ent_names:
        return

    G = nx.Graph()
    G.add_node(center_name)

    rel_list = relations.get("relations", [])
    neighbors = set()
    edge_data = []
    for r in rel_list:
        src = r.get("source", r.get("source_name", ""))
        tgt = r.get("target", r.get("target_name", ""))
        if src == center_name:
            neighbors.add(tgt)
            edge_data.append((src, tgt, r.get("relation", "")))
        elif tgt == center_name:
            neighbors.add(src)
            edge_data.append((src, tgt, r.get("relation", "")))

    for n in neighbors:
        info = ent_names.get(n, {})
        G.add_node(n, type=info.get("type", ""))
    for src, tgt, rel in edge_data:
        if src in G and tgt in G:
            G.add_edge(src, tgt, relation=rel)

    if len(G.nodes) < 2:
        return

    fig, ax = plt.subplots(figsize=(10, 8))
    pos = nx.spring_layout(G, k=2, seed=42)

    for node in G.nodes():
        info = ent_names.get(node, {})
        color = TYPE_COLORS.get(info.get("type", ""), "#888")
        size = 500 if node == center_name else 200
        ax.scatter(pos[node][0], pos[node][1], c=color, s=size, alpha=0.8,
                   edgecolors='#333', linewidths=1, zorder=3)
        ax.annotate(node, pos[node], fontsize=8, ha='center', va='bottom', zorder=4)

    for u, v, data in G.edges(data=True):
        ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                color='#666', alpha=0.5, linewidth=1, zorder=1)
        mid = ((pos[u][0]+pos[v][0])/2, (pos[u][1]+pos[v][1])/2)
        ax.annotate(data.get("relation", ""), mid, fontsize=6, ha='center',
                   color='#E74C3C', alpha=0.8, zorder=2)

    ax.set_title(f'"{center_name}" 关联网络', fontsize=14, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()

    safe_name = center_name.replace("/", "_").replace("\\", "_")
    for fmt in ['png', 'svg']:
        path = os.path.join(output_dir, f'subgraph_{safe_name}.{fmt}')
        fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  子图: subgraph_{safe_name}.png/svg")


def generate_statistics(entities, relations, anchors, output_dir):
    """生成知识图谱统计JSON"""
    ent_list = entities.get("entities", [])
    rel_list = relations.get("relations", [])

    stats = {
        "entity_count": len(ent_list),
        "relation_count": len(rel_list),
        "anchor_count": len(anchors),
        "entity_types": dict(Counter(e["type"] for e in ent_list)),
        "relation_types": dict(Counter(r.get("relation", "未知") for r in rel_list)),
        "top_entities": [
            {"name": e["name"], "type": e["type"], "mentions": e.get("mentions", 0)}
            for e in sorted(ent_list, key=lambda x: x.get("mentions", 0), reverse=True)[:20]
        ],
        "extraction_method": entities.get("extracted_by", "jieba+rules"),
    }

    path = os.path.join(output_dir, "kg_statistics.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  统计: kg_statistics.json")


def main():
    os.makedirs(KG_OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("知识图谱论文级可视化")
    print("=" * 60)

    entities, relations, anchors = load_data()

    print("\n--- 生成图表 ---")
    plot_entity_distribution(entities, KG_OUTPUT_DIR)
    plot_relation_distribution(relations, KG_OUTPUT_DIR)
    plot_kg_overview(entities, relations, anchors, KG_OUTPUT_DIR)

    core_nodes = ["西樵山", "康有为", "黄飞鸿", "九江双蒸"]
    for name in core_nodes:
        plot_subgraph(entities, relations, name, KG_OUTPUT_DIR)

    generate_statistics(entities, relations, anchors, KG_OUTPUT_DIR)

    print(f"\n输出目录: {KG_OUTPUT_DIR}")
    print("完成！")


if __name__ == "__main__":
    main()
