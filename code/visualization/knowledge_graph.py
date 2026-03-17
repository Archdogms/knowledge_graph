#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
南海区文旅知识图谱构建与可视化（文化载体锚定版）

核心理念：
    "以文物古迹、历史建筑、非遗表演等实体为锚点，
     向上对应文化典籍中的历史记载，
     向下对应现实中的景点产品，
     是连接文化传承与旅游开发的实体中介层。"

三层结构：
    ┌─────────────────────────────────────────────────┐
    │  上层：典籍文化层                                │
    │  NER提取的文化实体（人物/朝代/事件/文化要素）    │
    │  → 连接关系："典籍记载"、"关联人物"               │
    ├─────────────────────────────────────────────────┤
    │  中间层：文化载体锚点层（核心）                   │
    │  不可移动文物(80) + 非遗(36) + 文化景观(19)      │
    │  + 名村(12) + 圩市街区(18) = 165条锚点           │
    │  → 连接关系："文化承载"、"传承于"、"位于"          │
    ├─────────────────────────────────────────────────┤
    │  下层：旅游产品层                                │
    │  POI景点 + 镇街节点                              │
    │  → 连接关系："对应景点"、"位于镇街"               │
    └─────────────────────────────────────────────────┘

节点选取策略：
    - 文化锚点：全部165条（核心层，全量保留）
    - 文化实体：TOP100（按权重排序，去除"其他"后的纯文化实体）
    - POI景点：与锚点有空间关联的TOP80（500m范围内）
    - 非遗项目：全量（从nonheritage.json）
    - 镇街：7个

关系构建（10类语义关系）：
    1. 典籍记载：NER实体 ↔ 锚点（锚点名称在典籍中与实体共现）
    2. 关联人物：人物实体 → 以其命名的锚点/POI
    3. 文化承载：POI → 关联的非遗项目
    4. 对应景点：锚点 → 空间匹配的POI
    5. 传承于：非遗 → 所在镇街
    6. 位于：锚点/POI → 所属镇街
    7. 同时代：相同朝代的锚点之间
    8. 同门类：相同文化大类的锚点/非遗之间
    9. 共现关联：NER共现关系（两端均为文化实体）
    10. 文化关联：文化要素实体 → 对应非遗项目
"""

import os
import json
import math

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
DB_DIR = os.path.join(DATA_DIR, "database")
GIS_DIR = os.path.join(DATA_DIR, "gis")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output")

TYPE_COLORS = {
    "不可移动文物": "#E74C3C",
    "非遗项目":     "#F39C12",
    "文化景观":     "#1ABC9C",
    "历史文化名村": "#8E44AD",
    "圩市街区":     "#D35400",
    "人物":         "#FF6B6B",
    "地点":         "#4ECDC4",
    "朝代":         "#98D8C8",
    "文化要素":     "#F7DC6F",
    "事件":         "#FFA07A",
    "建筑":         "#45B7D1",
    "景点":         "#2ECC71",
    "镇街":         "#3498DB",
}


def load_all_data():
    """加载全部数据源"""
    with open(os.path.join(DB_DIR, "cultural_anchors.json"), "r", encoding="utf-8") as f:
        anchors = json.load(f).get("anchors", [])

    with open(os.path.join(DB_DIR, "culture_entities.json"), "r", encoding="utf-8") as f:
        entities_data = json.load(f)

    with open(os.path.join(DB_DIR, "culture_relations.json"), "r", encoding="utf-8") as f:
        relations_data = json.load(f)

    with open(os.path.join(DB_DIR, "poi_cleaned.json"), "r", encoding="utf-8") as f:
        poi_data = json.load(f)

    nonheritage = []
    nh_path = os.path.join(GIS_DIR, "nanhai_nonheritage.json")
    if os.path.exists(nh_path):
        with open(nh_path, "r", encoding="utf-8") as f:
            nonheritage = json.load(f)

    taxonomy = {}
    tax_path = os.path.join(DB_DIR, "culture_taxonomy.json")
    if os.path.exists(tax_path):
        with open(tax_path, "r", encoding="utf-8") as f:
            taxonomy = json.load(f)

    return anchors, entities_data, relations_data, poi_data, nonheritage, taxonomy


def build_anchored_graph(anchors, entities_data, relations_data, poi_data, nonheritage, taxonomy):
    """构建以文化载体为锚点的三层知识图谱"""
    nodes = {}
    edges = []
    edge_set = set()

    def add_edge(src, tgt, relation, weight=1.0):
        key = tuple(sorted([src, tgt])) + (relation,)
        if key not in edge_set and src in nodes and tgt in nodes:
            edges.append({"source": src, "target": tgt, "relation": relation, "weight": weight})
            edge_set.add(key)

    # ═══ 中间层：文化载体锚点（全量165条）═══
    for a in anchors:
        name = a["name"]
        atype = a["anchor_type"]
        era_info = f"，{a['era']}" if a.get("era") else ""
        level_info = f"，{a['protection_level']}" if a.get("protection_level") else ""
        town_info = a.get("town", "")

        intro = f"【{atype}】{name}{era_info}{level_info}"
        if town_info:
            intro += f"，位于{town_info}"
        intro += "。"

        size = 22
        if "全国" in a.get("protection_level", ""):
            size = 30
        elif "省级" in a.get("protection_level", ""):
            size = 26
        elif "市级" in a.get("protection_level", ""):
            size = 22

        nodes[name] = {
            "id": a["id"],
            "type": atype,
            "layer": "anchor",
            "size": size,
            "weight": 80,
            "intro": intro,
            "town": town_info,
        }

    # ═══ 上层：典籍文化实体（TOP100）═══
    top_entities = sorted(
        entities_data["entities"],
        key=lambda x: x["weight"],
        reverse=True
    )[:100]

    for e in top_entities:
        name = e["name"]
        if name in nodes:
            continue
        intro = f"【{e['type']}】在典籍中出现{e['mentions']}次，来自{e.get('source_count', 1)}个文本源。"
        if e.get("is_anchor"):
            intro += " [文化锚点]"
        nodes[name] = {
            "id": e["id"],
            "type": e["type"],
            "layer": "culture",
            "size": min(35, max(10, 8 + math.sqrt(e["mentions"]) * 1.2)),
            "weight": e["weight"],
            "intro": intro,
        }

    # ═══ 下层：POI景点（优先有文化锚点关联的）═══
    pois_with_anchor = [p for p in poi_data["pois"] if p.get("has_cultural_anchor")]
    pois_without = [p for p in poi_data["pois"] if not p.get("has_cultural_anchor")]
    selected_pois = pois_with_anchor[:80] + pois_without[:20]

    for poi in selected_pois:
        name = poi["name"]
        if name in nodes:
            continue
        addr = (poi.get("address") or "")[:30]
        intro = f"【{poi.get('category', '景点')}】位于{poi.get('town', '')}"
        if addr:
            intro += f"，{addr}"
        ca = poi.get("cultural_anchors", [])
        if ca:
            intro += f"。关联文化载体: {', '.join(ca[:3])}"
        intro += "。"
        nodes[name] = {
            "id": f"POI_{poi['id']}" if poi.get('id') else f"POI_{name}",
            "type": "景点",
            "layer": "tourism",
            "size": 14,
            "weight": poi.get("rating", 3) * 10,
            "intro": intro,
        }

    # ═══ 非遗项目（全量）═══
    for nh in nonheritage:
        name = nh["name"]
        if name not in nodes:
            intro = f"【{nh.get('level', '')}非遗】{nh.get('category', '')}，传承于{nh.get('town', '')}。"
            nodes[name] = {
                "id": f"NH_{name}",
                "type": "非遗项目",
                "layer": "anchor",
                "size": 20 if nh.get("level") in ("国家级", "省级") else 14,
                "weight": {"国家级": 100, "省级": 70, "市级": 50, "区级": 30}.get(nh.get("level", ""), 20),
                "intro": intro,
            }

    # ═══ 镇街节点 ═══
    towns = ["桂城街道", "西樵镇", "九江镇", "丹灶镇", "狮山镇", "大沥镇", "里水镇"]
    for town in towns:
        if town not in nodes:
            nodes[town] = {
                "id": f"TOWN_{town}",
                "type": "镇街",
                "layer": "tourism",
                "size": 28,
                "weight": 90,
                "intro": f"南海区七镇街之一，文旅资源分布的重要空间单元。",
            }

    # ═══════════════════════════════════════════
    #  关系构建
    # ═══════════════════════════════════════════

    # 1. 锚点 → 镇街
    for a in anchors:
        town = a.get("town", "")
        if town and town in nodes and a["name"] in nodes:
            add_edge(a["name"], town, "位于", 1.5)

    # 2. 锚点 → 空间匹配的POI
    for poi in selected_pois:
        name = poi["name"]
        if name not in nodes:
            continue
        for anchor_name in poi.get("cultural_anchors", []):
            if anchor_name in nodes:
                add_edge(anchor_name, name, "对应景点", 2.0)

    # 3. POI → 镇街
    for poi in selected_pois:
        town = poi.get("town", "")
        if town in nodes and poi["name"] in nodes:
            add_edge(poi["name"], town, "位于", 1.0)

    # 4. NER共现关系
    for r in relations_data["relations"]:
        src, tgt = r["source_name"], r["target_name"]
        if src in nodes and tgt in nodes:
            add_edge(src, tgt, "共现关联", min(r["co_occurrence"] / 5.0, 3.0))

    # 5. 典籍记载：NER实体 ↔ 锚点名称的文本共现
    anchor_name_set = {a["name"] for a in anchors}
    entity_name_set = {e["name"] for e in top_entities}
    for r in relations_data["relations"]:
        src, tgt = r["source_name"], r["target_name"]
        if src in anchor_name_set and tgt in entity_name_set and src in nodes and tgt in nodes:
            add_edge(src, tgt, "典籍记载", 2.5)
        elif tgt in anchor_name_set and src in entity_name_set and src in nodes and tgt in nodes:
            add_edge(tgt, src, "典籍记载", 2.5)

    # 6. 人物实体 → 关联锚点/POI
    for e in top_entities:
        if e["type"] != "人物":
            continue
        ename = e["name"]
        if ename not in nodes:
            continue
        for a in anchors:
            if ename in a["name"] and a["name"] in nodes:
                add_edge(ename, a["name"], "关联人物", 2.0)
        for poi in selected_pois:
            if ename in poi["name"] and poi["name"] in nodes:
                add_edge(ename, poi["name"], "关联人物", 1.5)

    # 7. POI → 非遗
    for poi in selected_pois:
        pname = poi["name"]
        if pname not in nodes:
            continue
        for nh_name in poi.get("nonheritage_match", []):
            for nh in nonheritage:
                if nh_name in nh["name"] and nh["name"] in nodes:
                    add_edge(pname, nh["name"], "文化承载", 2.0)
                    break

    # 8. 非遗 → 镇街
    for nh in nonheritage:
        town = nh.get("town", "")
        if town in nodes and nh["name"] in nodes:
            add_edge(nh["name"], town, "传承于", 1.5)

    # 9. 文化要素实体 → 非遗
    for e in top_entities:
        if e["type"] != "文化要素":
            continue
        ename = e["name"]
        if ename not in nodes:
            continue
        for nh in nonheritage:
            if ename in nh["name"] or nh["name"] in ename:
                if nh["name"] in nodes:
                    add_edge(ename, nh["name"], "文化关联", 2.0)

    # 10. 同时代锚点关联
    era_groups = {}
    for a in anchors:
        era = a.get("era", "")
        if not era:
            continue
        for period in ["清", "明", "宋", "元", "唐", "民国"]:
            if period in era:
                era_groups.setdefault(period, []).append(a["name"])
                break
    for period, names in era_groups.items():
        if len(names) < 2:
            continue
        for i in range(min(len(names), 8)):
            for j in range(i + 1, min(len(names), 8)):
                if names[i] in nodes and names[j] in nodes:
                    add_edge(names[i], names[j], "同时代", 0.5)

    # 11. taxonomy → 非遗
    if taxonomy:
        for cat_name, cat_info in taxonomy.items():
            for sub_name, sub_info in cat_info.get("subcategories", {}).items():
                for item in sub_info.get("items", []):
                    for nh in nonheritage:
                        if item in nh["name"] or nh["name"] in item:
                            for a in anchors:
                                if nh["name"] in a["name"] or a["name"] in nh["name"]:
                                    if a["name"] in nodes and nh["name"] in nodes:
                                        add_edge(a["name"], nh["name"], "同门类", 1.0)

    return nodes, edges


def export_graph_json(nodes, edges, output_path):
    """导出为JSON格式"""
    nodes_list = []
    for name, info in nodes.items():
        nodes_list.append({
            "id": info["id"],
            "label": name,
            "type": info["type"],
            "layer": info.get("layer", ""),
            "size": info["size"],
            "color": TYPE_COLORS.get(info["type"], "#888"),
            "weight": info["weight"],
            "intro": info.get("intro", ""),
        })

    edges_list = []
    for e in edges:
        edges_list.append({
            "source": e["source"],
            "target": e["target"],
            "relation": e["relation"],
            "weight": round(e["weight"], 2),
        })

    from collections import Counter
    type_dist = dict(Counter(n["type"] for n in nodes_list))
    layer_dist = dict(Counter(n["layer"] for n in nodes_list))
    rel_dist = dict(Counter(e["relation"] for e in edges_list))

    graph = {
        "nodes": nodes_list,
        "edges": edges_list,
        "statistics": {
            "node_count": len(nodes_list),
            "edge_count": len(edges_list),
            "type_distribution": type_dist,
            "layer_distribution": layer_dist,
            "relation_distribution": rel_dist,
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    return graph


def build_graph_html(graph):
    """生成知识图谱交互式HTML（文化锚定版）"""
    nodes_js = json.dumps(graph["nodes"], ensure_ascii=False)
    edges_js = json.dumps(graph["edges"], ensure_ascii=False)

    legend_html = ""
    for type_name, color in TYPE_COLORS.items():
        count = graph["statistics"]["type_distribution"].get(type_name, 0)
        if count > 0:
            legend_html += f'<span style="color:{color}">&#9679;</span> {type_name}({count}) &nbsp;'

    stats = graph["statistics"]
    layer_info = " | ".join(f"{k}:{v}" for k, v in stats.get("layer_distribution", {}).items())

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>南海区文旅知识图谱（文化载体锚定版）</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <style>
        body {{ margin: 0; padding: 0; background: #0a0a1a; }}
        #chart {{ width: 100vw; height: 100vh; }}
        .info {{ position: absolute; top: 10px; left: 20px; color: #ddd; font-family: "Microsoft YaHei"; z-index: 10; }}
        .info h2 {{ margin: 0; font-size: 18px; color: #E74C3C; }}
        .info .legend {{ font-size: 11px; margin-top: 5px; line-height: 1.8; max-width: 600px; }}
        .info .stats {{ font-size: 11px; color: #888; margin-top: 3px; }}
        .card-tip {{ max-width: 320px; padding: 12px 14px; background: rgba(20,25,45,0.96); border: 1px solid #444; border-radius: 10px; box-shadow: 0 6px 20px rgba(0,0,0,0.5); }}
        .card-tip .title {{ font-size: 15px; font-weight: bold; color: #E74C3C; margin-bottom: 6px; border-bottom: 1px solid #333; padding-bottom: 8px; }}
        .card-tip .tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; color: #fff; margin-bottom: 8px; margin-right: 4px; }}
        .card-tip .tag-anchor {{ background: #C0392B; }}
        .card-tip .tag-culture {{ background: #2980B9; }}
        .card-tip .tag-tourism {{ background: #27AE60; }}
        .card-tip .intro {{ font-size: 12px; line-height: 1.6; color: #bbb; }}
        .card-tip .layer {{ font-size: 11px; color: #666; margin-top: 6px; font-style: italic; }}
    </style>
</head>
<body>
    <div class="info">
        <h2>南海区文旅知识图谱（文化载体锚定版）</h2>
        <div class="legend">{legend_html}</div>
        <div class="stats">节点: {stats['node_count']} | 关系: {stats['edge_count']} | {layer_info} | 悬停节点查看介绍卡</div>
    </div>
    <div id="chart"></div>
    <script>
        var chart = echarts.init(document.getElementById('chart'));
        var rawNodes = {nodes_js};
        var rawEdges = {edges_js};

        var nodeMap = {{}};
        rawNodes.forEach(function(n) {{ nodeMap[n.label] = n; }});

        var layerTag = {{'anchor': ['锚点层', 'tag-anchor'], 'culture': ['典籍层', 'tag-culture'], 'tourism': ['旅游层', 'tag-tourism']}};

        var nodes = rawNodes.map(function(n) {{
            return {{
                name: n.label, symbolSize: n.size,
                itemStyle: {{ color: n.color, borderColor: '#222', borderWidth: 1 }},
                label: {{ show: n.size > 16, fontSize: Math.max(9, n.size / 2.8), color: '#ddd', fontFamily: 'Microsoft YaHei' }},
                category: n.type
            }};
        }});

        var edges = rawEdges.map(function(e) {{
            return {{
                source: e.source, target: e.target,
                relation: e.relation || '',
                lineStyle: {{ width: Math.max(0.5, e.weight * 0.8), color: '#444', opacity: 0.5, curveness: 0.2 }},
                label: {{ show: false }}
            }};
        }});

        var categories = {json.dumps([{"name": t} for t in TYPE_COLORS.keys()], ensure_ascii=False)};

        function getCardHtml(name, isNode) {{
            var n = nodeMap[name];
            if (!n) return '<b>' + name + '</b>';
            var intro = n.intro || '';
            var lt = layerTag[n.layer] || ['', ''];
            return '<div class="card-tip">' +
                '<div class="title">' + name + '</div>' +
                '<span class="tag" style="background:' + n.color + '">' + n.type + '</span>' +
                (lt[0] ? '<span class="tag ' + lt[1] + '">' + lt[0] + '</span>' : '') +
                '<div class="intro">' + intro + '</div>' +
                (isNode ? '<div class="layer">三层结构: 典籍文化层 ⇄ 文化载体锚点层 ⇄ 旅游产品层</div>' : '') +
                '</div>';
        }}

        var option = {{
            tooltip: {{
                trigger: 'item', confine: true,
                backgroundColor: 'transparent', borderWidth: 0, padding: 0,
                formatter: function(p) {{
                    if (p.dataType === 'node') return getCardHtml(p.name, true);
                    var rel = (p.data && p.data.relation) ? p.data.relation : '';
                    return '<div class="card-tip"><div style="text-align:center;color:#aaa;font-size:12px">' +
                        '<b>' + p.data.source + '</b>' +
                        '<br/><span style="color:#E74C3C">— ' + rel + ' —</span><br/>' +
                        '<b>' + p.data.target + '</b></div></div>';
                }}
            }},
            series: [{{
                type: 'graph', layout: 'force', roam: true, draggable: true,
                categories: categories,
                data: nodes, links: edges,
                force: {{ repulsion: 250, edgeLength: [50, 200], gravity: 0.06, layoutAnimation: true }},
                emphasis: {{ focus: 'adjacency', lineStyle: {{ width: 3 }} }}
            }}]
        }};
        chart.setOption(option);
        window.addEventListener('resize', function() {{ chart.resize(); }});
    </script>
</body>
</html>"""
    return html


def build_pyvis_graph(graph, output_path):
    """
    用 pyvis (vis.js) 生成可直接打开的交互式知识图谱HTML。
    支持：多重关系、边标签、节点介绍卡、物理仿真、搜索。
    """
    from pyvis.network import Network

    net = Network(
        height="100vh", width="100%",
        bgcolor="#0a0a1a", font_color="#ddd",
        directed=True, notebook=False,
        cdn_resources="remote",
    )

    RELATION_COLORS = {
        "典籍记载": "#E74C3C",
        "关联人物": "#FF6B6B",
        "文化承载": "#F39C12",
        "对应景点": "#2ECC71",
        "传承于":   "#8E44AD",
        "位于":     "#3498DB",
        "同时代":   "#98D8C8",
        "同门类":   "#D35400",
        "共现关联": "#555555",
        "文化关联": "#F7DC6F",
    }

    LAYER_LABEL = {"anchor": "文化载体锚点层", "culture": "典籍文化层", "tourism": "旅游产品层"}

    for n in graph["nodes"]:
        title_html = (
            f"<div style='max-width:300px;font-family:Microsoft YaHei,sans-serif;'>"
            f"<b style='font-size:14px;color:{n['color']}'>{n['label']}</b><br/>"
            f"<span style='background:{n['color']};color:#fff;padding:1px 6px;border-radius:3px;font-size:11px'>{n['type']}</span>"
            f"&nbsp;<span style='background:#333;color:#aaa;padding:1px 6px;border-radius:3px;font-size:11px'>"
            f"{LAYER_LABEL.get(n.get('layer',''), '')}</span><br/><br/>"
            f"<span style='font-size:12px;color:#bbb'>{n.get('intro','')}</span></div>"
        )
        shape = "dot"
        if n.get("layer") == "anchor":
            shape = "diamond"
        elif n.get("layer") == "culture":
            shape = "triangle"

        net.add_node(
            n["label"],
            label=n["label"],
            title=title_html,
            color=n["color"],
            size=n["size"] * 1.2,
            shape=shape,
            font={"size": max(8, n["size"] // 2), "color": "#ccc", "face": "Microsoft YaHei"},
            borderWidth=1,
            borderWidthSelected=3,
        )

    for e in graph["edges"]:
        rel = e["relation"]
        edge_color = RELATION_COLORS.get(rel, "#555")
        net.add_edge(
            e["source"], e["target"],
            title=f"{e['source']}  —[ {rel} ]—  {e['target']}",
            label=rel,
            color={"color": edge_color, "opacity": 0.6, "highlight": edge_color},
            width=max(0.5, e.get("weight", 1) * 0.8),
            font={"size": 8, "color": "#666", "strokeWidth": 0, "face": "Microsoft YaHei"},
            smooth={"type": "curvedCCW", "roundness": 0.2},
            arrows={"to": {"enabled": True, "scaleFactor": 0.4}},
        )

    net.set_options(json.dumps({
        "physics": {
            "enabled": True,
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
                "gravitationalConstant": -80,
                "centralGravity": 0.008,
                "springLength": 120,
                "springConstant": 0.04,
                "damping": 0.5,
                "avoidOverlap": 0.3,
            },
            "stabilization": {"iterations": 200, "fit": True},
        },
        "interaction": {
            "hover": True,
            "tooltipDelay": 100,
            "multiselect": True,
            "navigationButtons": True,
            "keyboard": True,
        },
        "edges": {
            "smooth": {"type": "curvedCCW", "roundness": 0.15},
            "font": {"size": 0, "color": "#666"},
        },
        "nodes": {
            "font": {"face": "Microsoft YaHei"},
        },
    }))

    net.save_graph(output_path)

    stats = graph["statistics"]
    legend_items = []
    for t, color in TYPE_COLORS.items():
        cnt = stats["type_distribution"].get(t, 0)
        if cnt > 0:
            legend_items.append(
                f'<span style="display:inline-block;width:10px;height:10px;'
                f'background:{color};border-radius:50%;margin-right:4px"></span>'
                f'{t}({cnt})'
            )
    legend_html = "&nbsp;&nbsp;".join(legend_items)

    rel_items = []
    for r, cnt in sorted(stats["relation_distribution"].items(), key=lambda x: -x[1]):
        rc = RELATION_COLORS.get(r, "#555")
        rel_items.append(
            f'<span style="color:{rc}">━━</span> {r}({cnt})'
        )
    rel_legend = "&nbsp;&nbsp;".join(rel_items)

    layer_info = " | ".join(f"{k}: {v}" for k, v in stats.get("layer_distribution", {}).items())

    shapes_legend = (
        '<span style="color:#E74C3C">◆</span> 锚点层 &nbsp;'
        '<span style="color:#4ECDC4">▲</span> 典籍层 &nbsp;'
        '<span style="color:#2ECC71">●</span> 旅游层'
    )

    search_js = """
    <script>
    (function(){
      var searchBox = document.getElementById('kg-search');
      if (!searchBox) return;
      searchBox.addEventListener('input', function() {
        var q = this.value.trim().toLowerCase();
        if (!q) {
          network.fit();
          return;
        }
        var matching = [];
        nodes.forEach(function(n) {
          if (n.label && n.label.toLowerCase().indexOf(q) >= 0) matching.push(n.id);
        });
        if (matching.length > 0) {
          network.selectNodes(matching);
          network.focus(matching[0], {scale: 1.2, animation: true});
        }
      });

      // 切换边标签显示
      var edgeLabelsOn = false;
      var toggleBtn = document.getElementById('kg-toggle-edge');
      if (toggleBtn) {
        toggleBtn.addEventListener('click', function() {
          edgeLabelsOn = !edgeLabelsOn;
          var newSize = edgeLabelsOn ? 9 : 0;
          network.setOptions({edges: {font: {size: newSize}}});
          this.textContent = edgeLabelsOn ? '隐藏关系标签' : '显示关系标签';
        });
      }

      // 稳定后关闭物理引擎以提高交互流畅性
      network.once('stabilized', function() {
        network.setOptions({physics: {enabled: false}});
      });
    })();
    </script>
    """

    overlay_html = f"""
    <div id="kg-panel" style="position:fixed;top:10px;left:10px;z-index:9999;font-family:'Microsoft YaHei',sans-serif;
        background:rgba(10,10,26,0.92);border:1px solid #333;border-radius:10px;padding:14px 18px;max-width:700px;
        box-shadow:0 8px 30px rgba(0,0,0,0.6);color:#ddd;">
      <h2 style="margin:0 0 6px 0;font-size:16px;color:#E74C3C;">南海区文旅知识图谱（交互版）</h2>
      <div style="font-size:11px;line-height:1.8;">{legend_html}</div>
      <div style="font-size:11px;line-height:1.8;margin-top:4px;">{rel_legend}</div>
      <div style="font-size:11px;color:#888;margin-top:4px;">
        节点 {stats['node_count']} | 关系 {stats['edge_count']} | {layer_info} | 形状: {shapes_legend}
      </div>
      <div style="margin-top:8px;display:flex;gap:8px;align-items:center;">
        <input id="kg-search" type="text" placeholder="搜索节点..." style="flex:1;padding:5px 10px;background:#1a1a2e;
          border:1px solid #444;border-radius:6px;color:#eee;font-size:12px;outline:none;" />
        <button id="kg-toggle-edge" style="padding:5px 12px;background:#2c3e50;color:#ddd;border:none;
          border-radius:6px;cursor:pointer;font-size:11px;white-space:nowrap;">显示关系标签</button>
      </div>
      <div style="font-size:10px;color:#555;margin-top:6px;">
        提示: 鼠标悬停查看介绍卡 | 滚轮缩放 | 拖拽移动 | 双击聚焦 | 搜索定位节点
      </div>
    </div>
    {search_js}
    """

    with open(output_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    html_content = html_content.replace("</body>", f"{overlay_html}\n</body>")
    html_content = html_content.replace(
        "<body>",
        '<body style="margin:0;padding:0;overflow:hidden;background:#0a0a1a;">'
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"  pyvis 交互式图谱: {output_path}")
    print(f"  节点 {stats['node_count']} | 关系 {stats['edge_count']}")
    print(f"  直接用浏览器打开即可查看和交互！")

    return output_path


def export_neo4j(graph, output_dir):
    """
    导出 Neo4j 兼容的文件：
    1. neo4j_nodes.csv — 节点表（Neo4j LOAD CSV 可直接导入）
    2. neo4j_edges.csv — 关系表（支持同一对实体的多种关系）
    3. neo4j_import.cypher — Cypher 导入脚本
    """
    import csv

    neo4j_dir = os.path.join(output_dir, "neo4j")
    os.makedirs(neo4j_dir, exist_ok=True)

    # ── 节点 CSV ──
    nodes_path = os.path.join(neo4j_dir, "neo4j_nodes.csv")
    with open(nodes_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "type", "layer", "intro", "weight"])
        for n in graph["nodes"]:
            writer.writerow([n["id"], n["label"], n["type"], n.get("layer", ""),
                             n.get("intro", ""), n.get("weight", 0)])
    print(f"  Neo4j 节点: {nodes_path} ({len(graph['nodes'])} 条)")

    # ── 关系 CSV（同一对实体可以有多行/多种关系）──
    edges_path = os.path.join(neo4j_dir, "neo4j_edges.csv")
    with open(edges_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "target", "relation", "weight"])
        for e in graph["edges"]:
            writer.writerow([e["source"], e["target"], e["relation"], e.get("weight", 1)])
    print(f"  Neo4j 关系: {edges_path} ({len(graph['edges'])} 条)")

    # 统计多重关系
    from collections import defaultdict
    pair_rels = defaultdict(list)
    for e in graph["edges"]:
        pair = tuple(sorted([e["source"], e["target"]]))
        pair_rels[pair].append(e["relation"])
    multi = sum(1 for v in pair_rels.values() if len(v) > 1)
    print(f"  其中 {multi} 对实体存在多重关系")

    # ── Cypher 导入脚本 ──
    cypher_path = os.path.join(neo4j_dir, "neo4j_import.cypher")
    lines = []
    lines.append("// ═══ 南海区文旅知识图谱 — Neo4j 导入脚本 ═══")
    lines.append("// 用法: 在 Neo4j Browser 中逐段执行，或用 neo4j-admin import")
    lines.append("")
    lines.append("// ── Step 1: 创建约束 ──")
    lines.append("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;")
    lines.append("")
    lines.append("// ── Step 2: 导入节点 ──")
    lines.append("// 方式A: LOAD CSV (需把 neo4j_nodes.csv 放到 Neo4j import 目录)")
    lines.append("LOAD CSV WITH HEADERS FROM 'file:///neo4j_nodes.csv' AS row")
    lines.append("CREATE (n:Entity {")
    lines.append("  id: row.id, name: row.name, type: row.type,")
    lines.append("  layer: row.layer, intro: row.intro, weight: toFloat(row.weight)")
    lines.append("});")
    lines.append("")
    lines.append("// 为每种类型添加标签")
    for t in set(n["type"] for n in graph["nodes"]):
        safe_label = t.replace("（", "").replace("）", "").replace(" ", "")
        lines.append(f'MATCH (n:Entity) WHERE n.type = "{t}" SET n:{safe_label};')
    lines.append("")
    lines.append("// ── Step 3: 导入关系 ──")
    lines.append("// 方式A: LOAD CSV")
    lines.append("LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row")
    lines.append("MATCH (a:Entity {name: row.source})")
    lines.append("MATCH (b:Entity {name: row.target})")
    lines.append("CALL apoc.create.relationship(a, row.relation, {weight: toFloat(row.weight)}, b) YIELD rel")
    lines.append("RETURN count(rel);")
    lines.append("")
    lines.append("// ── Step 3 备选 (无 APOC 插件时): 为每种关系类型单独创建 ──")
    from collections import Counter
    rel_types = Counter(e["relation"] for e in graph["edges"])
    for rel_type in rel_types:
        safe_rel = rel_type.replace(" ", "_")
        lines.append(f'// 关系类型: {rel_type} ({rel_types[rel_type]} 条)')
        lines.append(f"LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row")
        lines.append(f'WITH row WHERE row.relation = "{rel_type}"')
        lines.append(f"MATCH (a:Entity {{name: row.source}})")
        lines.append(f"MATCH (b:Entity {{name: row.target}})")
        lines.append(f"CREATE (a)-[:`{safe_rel}` {{weight: toFloat(row.weight)}}]->(b);")
        lines.append("")

    lines.append("// ── Step 4: 查询示例 ──")
    lines.append("// 查看所有节点类型统计")
    lines.append("MATCH (n:Entity) RETURN n.type, count(*) ORDER BY count(*) DESC;")
    lines.append("")
    lines.append("// 查看某个锚点的所有关系")
    lines.append('MATCH (n:Entity {name: "云泉仙馆"})-[r]-(m) RETURN n, r, m;')
    lines.append("")
    lines.append("// 查看两个实体间的所有关系")
    lines.append('MATCH (a:Entity {name: "九江双蒸酒酿制技艺"})-[r]-(b:Entity {name: "九江镇"}) RETURN a, r, b;')
    lines.append("")
    lines.append("// 查找文化载体锚点的关联景点")
    lines.append("MATCH (a:Entity {layer: 'anchor'})-[r:`对应景点`]->(p:Entity {layer: 'tourism'}) RETURN a.name, p.name LIMIT 20;")

    with open(cypher_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Cypher脚本: {cypher_path}")

    # ── 方式B: 直接生成 Cypher CREATE 语句（不依赖CSV，可直接粘贴执行）──
    cypher_direct_path = os.path.join(neo4j_dir, "neo4j_create_all.cypher")
    direct_lines = []
    direct_lines.append("// ═══ 直接创建全部节点和关系（无需CSV文件）═══")
    direct_lines.append("// 在 Neo4j Browser 中分批执行")
    direct_lines.append("")
    direct_lines.append("// ── 节点 ──")
    for n in graph["nodes"]:
        name_esc = n["label"].replace('"', '\\"')
        intro_esc = n.get("intro", "").replace('"', '\\"').replace("\n", " ")
        t = n["type"]
        layer = n.get("layer", "")
        safe_label = t.replace("（", "").replace("）", "").replace(" ", "")
        direct_lines.append(
            f'CREATE (:`{safe_label}`:Entity {{id: "{n["id"]}", name: "{name_esc}", '
            f'type: "{t}", layer: "{layer}", '
            f'intro: "{intro_esc}", weight: {n.get("weight", 0)}}});'
        )

    direct_lines.append("")
    direct_lines.append("// ── 关系 ──")
    for e in graph["edges"]:
        src_esc = e["source"].replace('"', '\\"')
        tgt_esc = e["target"].replace('"', '\\"')
        rel = e["relation"].replace(" ", "_")
        w = e.get("weight", 1)
        direct_lines.append(
            f'MATCH (a:Entity {{name: "{src_esc}"}}), (b:Entity {{name: "{tgt_esc}"}}) '
            f'CREATE (a)-[:`{rel}` {{weight: {w}}}]->(b);'
        )

    with open(cypher_direct_path, "w", encoding="utf-8") as f:
        f.write("\n".join(direct_lines))
    print(f"  Cypher直接创建: {cypher_direct_path}")

    return neo4j_dir


def main():
    print("=" * 60)
    print("南海区文旅知识图谱（文化载体锚定版）")
    print("=" * 60)

    anchors, entities_data, relations_data, poi_data, nonheritage, taxonomy = load_all_data()
    print(f"文化锚点: {len(anchors)}")
    print(f"文化实体: {entities_data['total']}, 关系: {relations_data['total']}")
    print(f"景点: {len(poi_data['pois'])}, 非遗: {len(nonheritage)}")

    print("\n--- 构建锚定图谱 ---")
    nodes, edges = build_anchored_graph(anchors, entities_data, relations_data, poi_data, nonheritage, taxonomy)
    print(f"节点: {len(nodes)}, 关系: {len(edges)}")

    os.makedirs(os.path.join(OUTPUT_DIR, "figures"), exist_ok=True)

    json_path = os.path.join(DB_DIR, "expanded_knowledge_graph.json")
    graph = export_graph_json(nodes, edges, json_path)
    print(f"图谱JSON: {json_path}")

    html = build_graph_html(graph)
    html_path = os.path.join(OUTPUT_DIR, "figures", "knowledge_graph.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"可视化HTML: {html_path}")

    print("\n--- pyvis 交互式知识图谱 ---")
    pyvis_path = os.path.join(OUTPUT_DIR, "figures", "knowledge_graph_interactive.html")
    build_pyvis_graph(graph, pyvis_path)

    print("\n--- Neo4j 导出 ---")
    neo4j_dir = export_neo4j(graph, OUTPUT_DIR)

    print(f"\n节点类型分布:")
    for t, c in sorted(graph["statistics"]["type_distribution"].items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")
    print(f"\n层级分布:")
    for l, c in graph["statistics"]["layer_distribution"].items():
        print(f"  {l}: {c}")
    print(f"\n关系类型分布:")
    for r, c in sorted(graph["statistics"]["relation_distribution"].items(), key=lambda x: -x[1]):
        print(f"  {r}: {c}")

    print("\n完成！")


if __name__ == "__main__":
    main()
