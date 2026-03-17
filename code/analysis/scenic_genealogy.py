#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
景点谱系树构建工具
基于POI数据和评论分析，按类型/体验度/区位构建景点层级结构

研究方法：
    景点谱系反映文旅市场的"需求侧"现状，与文化谱系（"供给侧"）形成对照。
    
    体验度评估模型（六维加权评分）：
    ┌──────────────┬──────┬──────────────────────────┬──────────────┐
    │ 维度         │ 权重 │ 计算方法                 │ 满分条件     │
    ├──────────────┼──────┼──────────────────────────┼──────────────┤
    │ 平台评分     │ 30%  │ avg_rating/5.0×100       │ 评分5.0      │
    │ 好评率       │ 20%  │ 正面评论占比             │ 100%好评     │
    │ 文化深度     │ 20%  │ has_nh×30+nh_cnt×15+典籍 │ 关联非遗+典籍│
    │ 评论活跃度   │ 15%  │ count/20×100             │ 20+条评论    │
    │ 历史积淀     │ 10%  │ 典籍文本中提及次数       │ 高频提及     │
    │ 照片丰富度   │  5%  │ photos/15×100            │ 15+张照片    │
    └──────────────┴──────┴──────────────────────────┴──────────────┘
    
    权重设计理由：
    - 平台评分30%（最高权重）：代表游客实际体验的综合评价
    - 好评率20%：比评分更能反映口碑一致性
    - 文化深度20%：体现"文旅融合"研究视角
    - 历史积淀10%：典籍文本中被提及的频次，体现文化底蕴
    
    分级标准：≥60=高, ≥40=中, <40=低
    
    输出：
    - scenic_genealogy_tree.json：按 类别→体验度→景点 的三层树
    - scenic_town_tree.json：按 镇街→类别→景点 的三层树
    - experience_scores.json：所有景点的五维评分明细
"""

import os
import json
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
DB_DIR = os.path.join(DATA_DIR, "database")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output")


def load_data():
    """加载清洗后的POI和评论数据（含补充多平台评论）"""
    poi_path = os.path.join(DB_DIR, "poi_cleaned.json")
    with open(poi_path, "r", encoding="utf-8") as f:
        poi_data = json.load(f)

    review_summary = {}

    real_review_path = os.path.join(DATA_DIR, "reviews", "review_summary_real.json")
    fallback_path = os.path.join(DATA_DIR, "reviews", "review_summary.json")
    review_path = real_review_path if os.path.exists(real_review_path) else fallback_path
    if os.path.exists(review_path):
        with open(review_path, "r", encoding="utf-8") as f:
            reviews = json.load(f)
        for r in reviews:
            review_summary[r["name"]] = r
        print(f"[原始评论] {len(review_summary)} 条")

    supp_path = os.path.join(DATA_DIR, "reviews", "merged_reviews_supp.json")
    if os.path.exists(supp_path):
        with open(supp_path, "r", encoding="utf-8") as f:
            supp_data = json.load(f)
        from collections import Counter
        spot_reviews = defaultdict(list)
        for r in supp_data.get("reviews", []):
            spot = r.get("spot_name", "").strip()
            if spot:
                spot_reviews[spot].append(r.get("text", ""))

        supp_added = 0
        for spot, texts in spot_reviews.items():
            if spot in review_summary:
                review_summary[spot]["review_count"] = review_summary[spot].get("review_count", 0) + len(texts)
            else:
                review_summary[spot] = {
                    "name": spot,
                    "review_count": len(texts),
                    "avg_rating": 4.0,
                    "positive_rate": 70,
                }
                supp_added += 1
        print(f"[补充评论] 覆盖 {len(spot_reviews)} 景点, 新增 {supp_added} 个")

    print(f"[评论汇总] 共 {len(review_summary)} 个景点有评论数据")
    return poi_data["pois"], review_summary


def load_culture_entities():
    """加载文化实体库，用于典籍提及度评估"""
    entity_path = os.path.join(DB_DIR, "culture_entities.json")
    if not os.path.exists(entity_path):
        return {}
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    name_mentions = {}
    for e in data.get("entities", []):
        name_mentions[e["name"]] = e["mentions"]
    return name_mentions

CULTURE_MENTIONS = None

def get_culture_mention_score(poi_name):
    """计算景点在典籍中的被提及程度"""
    global CULTURE_MENTIONS
    if CULTURE_MENTIONS is None:
        CULTURE_MENTIONS = load_culture_entities()

    keywords = [poi_name]
    short = poi_name.replace("南海", "").replace("佛山", "").replace("区", "").replace("镇", "")
    if len(short) >= 2 and short != poi_name:
        keywords.append(short)

    total = 0
    for kw in keywords:
        for name, mentions in CULTURE_MENTIONS.items():
            if kw in name or name in kw:
                total += mentions
                break
    return min(total / 50.0, 1.0) * 100

def calculate_experience_score(poi, review_info):
    """计算单个景点的体验度综合得分（六维模型）"""
    rating = poi.get("rating", 0)
    if not rating:
        rating = 3.0

    review_count = review_info.get("review_count", 0) if review_info else 0
    positive_rate = review_info.get("positive_rate", 50) if review_info else 50
    avg_rating = review_info.get("avg_rating", rating) if review_info else rating

    has_nh = 1 if poi.get("has_nonheritage", False) else 0
    nh_count = len(poi.get("nonheritage_match", []))

    w_rating = 0.30
    w_review = 0.15
    w_positive = 0.20
    w_culture = 0.20
    w_history = 0.10
    w_photos = 0.05

    score_rating = min(avg_rating / 5.0, 1.0) * 100
    score_review = min(review_count / 20.0, 1.0) * 100
    score_positive = positive_rate
    score_culture = min((has_nh * 30 + nh_count * 15), 100)
    score_history = get_culture_mention_score(poi.get("name", ""))
    photo_count = poi.get("photos", 0) if isinstance(poi.get("photos"), int) else 0
    score_photos = min(photo_count / 15.0, 1.0) * 100

    total = (
        w_rating * score_rating +
        w_review * score_review +
        w_positive * score_positive +
        w_culture * score_culture +
        w_history * score_history +
        w_photos * score_photos
    )

    if total >= 60:
        level = "高"
    elif total >= 40:
        level = "中"
    else:
        level = "低"

    return {
        "total_score": round(total, 1),
        "level": level,
        "score_rating": round(score_rating, 1),
        "score_review": round(score_review, 1),
        "score_positive": round(score_positive, 1),
        "score_culture": round(score_culture, 1),
        "score_history": round(score_history, 1),
        "score_photos": round(score_photos, 1),
    }


def build_scenic_tree(pois, review_summary):
    """构建景点谱系树"""
    tree = {
        "name": "南海区景点谱系",
        "children": [],
    }

    by_category = defaultdict(list)
    for poi in pois:
        cat = poi.get("category", "其他")
        review_info = review_summary.get(poi["name"])
        exp = calculate_experience_score(poi, review_info)
        poi["experience"] = exp
        by_category[cat].append(poi)

    for cat_name, cat_pois in sorted(by_category.items()):
        cat_node = {
            "name": cat_name,
            "value": f"{len(cat_pois)}个景点",
            "children": [],
        }

        by_level = defaultdict(list)
        for poi in cat_pois:
            level = poi["experience"]["level"]
            by_level[level].append(poi)

        for level in ["高", "中", "低"]:
            if level not in by_level:
                continue
            level_node = {
                "name": f"体验度:{level}",
                "children": [],
            }
            for poi in sorted(by_level[level], key=lambda x: x["experience"]["total_score"], reverse=True):
                poi_node = {
                    "name": poi["name"],
                    "value": f"得分:{poi['experience']['total_score']} | {poi['town']}",
                }
                level_node["children"].append(poi_node)
            cat_node["children"].append(level_node)

        tree["children"].append(cat_node)

    return tree


def build_town_tree(pois):
    """按镇街构建景点分布树"""
    tree = {
        "name": "南海区景点分布（按镇街）",
        "children": [],
    }

    by_town = defaultdict(list)
    for poi in pois:
        town = poi.get("town", "未知")
        by_town[town].append(poi)

    for town, town_pois in sorted(by_town.items(), key=lambda x: -len(x[1])):
        town_node = {
            "name": f"{town} ({len(town_pois)}个)",
            "children": [],
        }
        by_cat = defaultdict(list)
        for poi in town_pois:
            by_cat[poi["category"]].append(poi)

        for cat, cat_pois in sorted(by_cat.items()):
            cat_node = {
                "name": cat,
                "children": [{"name": p["name"], "value": 1} for p in cat_pois],
            }
            town_node["children"].append(cat_node)

        tree["children"].append(town_node)

    return tree


def build_echarts_html(tree_data, title):
    """生成ECharts可视化HTML"""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <style>
        body {{ margin: 0; padding: 0; background: #16213e; }}
        #chart {{ width: 100vw; height: 100vh; }}
        .title {{ position: absolute; top: 10px; left: 20px; color: #e0e0e0; font-size: 20px; font-family: "Microsoft YaHei"; z-index: 10; }}
        .subtitle {{ position: absolute; top: 40px; left: 20px; color: #888; font-size: 13px; font-family: "Microsoft YaHei"; z-index: 10; }}
    </style>
</head>
<body>
    <div class="title">{title}</div>
    <div class="subtitle">基于POI数据与评论分析 | 按类型/体验度/区位</div>
    <div id="chart"></div>
    <script>
        var chart = echarts.init(document.getElementById('chart'));
        var data = {json.dumps(tree_data, ensure_ascii=False)};
        var option = {{
            tooltip: {{ trigger: 'item', triggerOn: 'mousemove' }},
            series: [{{
                type: 'tree',
                data: [data],
                top: '5%', left: '10%', bottom: '5%', right: '25%',
                symbolSize: 10,
                orient: 'LR',
                label: {{
                    position: 'left', verticalAlign: 'middle', align: 'right',
                    fontSize: 12, fontFamily: 'Microsoft YaHei', color: '#ddd'
                }},
                leaves: {{
                    label: {{ position: 'right', verticalAlign: 'middle', align: 'left', fontSize: 11, color: '#aaa' }}
                }},
                lineStyle: {{ color: '#4a6fa5', width: 1.5, curveness: 0.5 }},
                expandAndCollapse: true,
                initialTreeDepth: 2,
                animationDuration: 550,
                animationDurationUpdate: 750
            }}]
        }};
        chart.setOption(option);
        window.addEventListener('resize', function() {{ chart.resize(); }});
    </script>
</body>
</html>"""
    return html


def main():
    print("=" * 60)
    print("南海区景点谱系树构建")
    print("=" * 60)

    pois, review_summary = load_data()
    print(f"加载 {len(pois)} 个POI, {len(review_summary)} 个评论汇总")

    scenic_tree = build_scenic_tree(pois, review_summary)
    tree_path = os.path.join(DB_DIR, "scenic_genealogy_tree.json")
    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(scenic_tree, f, ensure_ascii=False, indent=2)
    print(f"景点谱系树: {tree_path}")

    town_tree = build_town_tree(pois)
    town_path = os.path.join(DB_DIR, "scenic_town_tree.json")
    with open(town_path, "w", encoding="utf-8") as f:
        json.dump(town_tree, f, ensure_ascii=False, indent=2)
    print(f"镇街分布树: {town_path}")

    os.makedirs(os.path.join(OUTPUT_DIR, "figures"), exist_ok=True)

    html1 = build_echarts_html(scenic_tree, "南海区景点谱系树（按类型/体验度）")
    html1_path = os.path.join(OUTPUT_DIR, "figures", "scenic_genealogy_tree.html")
    with open(html1_path, "w", encoding="utf-8") as f:
        f.write(html1)
    print(f"可视化(类型): {html1_path}")

    html2 = build_echarts_html(town_tree, "南海区景点分布（按镇街）")
    html2_path = os.path.join(OUTPUT_DIR, "figures", "scenic_town_tree.html")
    with open(html2_path, "w", encoding="utf-8") as f:
        f.write(html2)
    print(f"可视化(镇街): {html2_path}")

    exp_data = []
    for poi in pois:
        if "experience" in poi:
            exp_data.append({
                "name": poi["name"],
                "category": poi["category"],
                "town": poi["town"],
                "rating": poi["rating"],
                "has_nonheritage": poi["has_nonheritage"],
                **poi["experience"],
            })
    exp_data.sort(key=lambda x: x["total_score"], reverse=True)

    exp_path = os.path.join(OUTPUT_DIR, "tables", "experience_scores.json")
    os.makedirs(os.path.join(OUTPUT_DIR, "tables"), exist_ok=True)
    with open(exp_path, "w", encoding="utf-8") as f:
        json.dump(exp_data, f, ensure_ascii=False, indent=2)
    print(f"体验度评分: {exp_path}")

    high = sum(1 for e in exp_data if e["level"] == "高")
    mid = sum(1 for e in exp_data if e["level"] == "中")
    low = sum(1 for e in exp_data if e["level"] == "低")
    print(f"\n体验度分级: 高={high}, 中={mid}, 低={low}")


if __name__ == "__main__":
    main()
