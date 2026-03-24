#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
景点评论数据采集与管理工具
生成南海区主要文旅景点的评论示例数据，用于体验度分析

实际使用时可通过以下方式补充真实数据：
1. 手动从大众点评/携程/马蜂窝复制评论到CSV
2. 使用半自动化工具辅助采集（注意合规）
"""

import json
import os
import csv
import random
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "data", "reviews")

SCENIC_SPOTS = [
    {"name": "西樵山风景名胜区", "id": "B02F3080HH", "category": "自然景观"},
    {"name": "南海博物馆", "id": "B02F308001", "category": "文化场馆"},
    {"name": "南海影视城", "id": "B02F308002", "category": "人文景点"},
    {"name": "黄飞鸿纪念馆", "id": "B02F308003", "category": "纪念馆"},
    {"name": "康有为故居", "id": "B02F308004", "category": "名人故居"},
    {"name": "南海观音寺", "id": "B02F308005", "category": "宗教场所"},
    {"name": "松塘古村", "id": "B02F308006", "category": "古村落"},
    {"name": "千灯湖公园", "id": "B02F308009", "category": "公园"},
    {"name": "里水梦里水乡", "id": "B02F308023", "category": "水乡"},
    {"name": "九江双蒸博物馆", "id": "B02F308017", "category": "博物馆"},
    {"name": "烟桥古村", "id": "B02F308007", "category": "古村落"},
    {"name": "仙岗古村", "id": "B02F308032", "category": "古村落"},
    {"name": "平洲玉器街", "id": "B02F308028", "category": "特色街区"},
    {"name": "宝峰寺", "id": "B02F308020", "category": "宗教场所"},
    {"name": "贤鲁岛", "id": "B02F308024", "category": "自然景观"},
]

REVIEW_TEMPLATES = {
    "自然景观": {
        "positive": [
            "山清水秀，空气非常好，适合周末爬山。",
            "风景很美，绿化好，适合拍照打卡。",
            "登顶后视野开阔，俯瞰南海全景，非常壮观。",
            "天然氧吧，带小朋友来很合适，有很多游玩设施。",
            "历史文化底蕴深厚，石器遗址值得一看。",
        ],
        "neutral": [
            "景区面积大，全部走完需要一天时间。",
            "门票价格还行，景点较多但部分在维修。",
            "人不算太多，就是停车不太方便。",
        ],
        "negative": [
            "台阶太多，爬得比较累，建议穿运动鞋。",
            "夏天蚊虫较多，要做好防蚊措施。",
        ],
    },
    "文化场馆": {
        "positive": [
            "展品丰富，了解了很多南海的历史文化。",
            "免费参观，展览策划得很用心。",
            "讲解员很专业，孩子学到了不少知识。",
            "建筑设计很现代，内部空间舒适。",
        ],
        "neutral": [
            "面积不大，一个小时左右就能看完。",
            "展品以图文为主，互动体验较少。",
        ],
        "negative": [
            "部分展厅在装修，内容不够完整。",
        ],
    },
    "古村落": {
        "positive": [
            "古建筑保存完好，青砖灰瓦很有岭南特色。",
            "很安静的小村庄，适合慢慢逛，感受历史韵味。",
            "祠堂建筑很有特点，雕刻精美。",
            "村里的老人很热情，会讲很多村庄的故事。",
            "拍照很出片，古色古香的感觉。",
        ],
        "neutral": [
            "商业化程度不高，配套设施一般。",
            "路不太好找，建议导航到村口。",
        ],
        "negative": [
            "部分老房子已经破败，希望能加强修缮保护。",
            "没什么餐饮配套，建议自带水和干粮。",
        ],
    },
    "公园": {
        "positive": [
            "灯光很美，特别是晚上来，千灯湖名不虚传。",
            "跑步散步的好地方，绿化做得很好。",
            "周末带家人来很放松，有大片草坪。",
        ],
        "neutral": [
            "夏天比较热，建议傍晚来。",
        ],
        "negative": [
            "周末人很多，停车位不够。",
        ],
    },
    "宗教场所": {
        "positive": [
            "香火很旺，寺庙建筑宏伟庄严。",
            "很有灵气的地方，环境清幽。",
            "素斋很好吃，值得一试。",
        ],
        "neutral": [
            "来拜拜的人很多，节假日要排队。",
        ],
        "negative": [
            "香油钱要求有点高，商业化气息较重。",
        ],
    },
}

DEFAULT_TEMPLATES = {
    "positive": [
        "值得一来的地方，了解了不少当地文化。",
        "环境不错，管理也挺好的。",
        "很有特色，推荐朋友来看看。",
        "文化氛围浓厚，增长了不少见识。",
    ],
    "neutral": [
        "一般般，可以顺路来看看。",
        "规模不大，半小时就够了。",
    ],
    "negative": [
        "交通不太方便，找了很久。",
        "内容比较单一，看完有点无聊。",
    ],
}


def generate_reviews_for_spot(spot, count=20):
    """为单个景点生成模拟评论"""
    category = spot["category"]
    templates = REVIEW_TEMPLATES.get(category, DEFAULT_TEMPLATES)

    reviews = []
    base_date = datetime(2024, 1, 1)

    for i in range(count):
        rand = random.random()
        if rand < 0.55:
            sentiment = "positive"
            rating = random.choice([4, 4, 4, 5, 5, 5])
        elif rand < 0.85:
            sentiment = "neutral"
            rating = random.choice([3, 3, 4])
        else:
            sentiment = "negative"
            rating = random.choice([1, 2, 2, 3])

        pool = templates.get(sentiment, DEFAULT_TEMPLATES[sentiment])
        text = random.choice(pool)

        review_date = base_date + timedelta(days=random.randint(0, 700))

        reviews.append({
            "spot_name": spot["name"],
            "spot_id": spot["id"],
            "spot_category": category,
            "rating": rating,
            "sentiment": sentiment,
            "review_text": text,
            "review_date": review_date.strftime("%Y-%m-%d"),
            "source": random.choice(["大众点评", "携程", "马蜂窝", "高德"]),
        })

    return reviews


def generate_all_reviews():
    """生成所有景点的评论数据"""
    print("=" * 60)
    print("景点评论数据生成")
    print("=" * 60)

    random.seed(42)
    all_reviews = []

    for spot in SCENIC_SPOTS:
        count = random.randint(15, 30)
        reviews = generate_reviews_for_spot(spot, count)
        all_reviews.extend(reviews)
        avg_rating = sum(r["rating"] for r in reviews) / len(reviews)
        pos_pct = sum(1 for r in reviews if r["sentiment"] == "positive") / len(reviews) * 100
        print(f"  {spot['name']}: {len(reviews)} 条评论, 平均评分 {avg_rating:.1f}, 好评率 {pos_pct:.0f}%")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    json_path = os.path.join(OUTPUT_DIR, "nanhai_reviews.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "note": "示例评论数据，用于体验度分析流程验证。实际研究中应替换为真实采集数据。",
            "total_count": len(all_reviews),
            "spots_count": len(SCENIC_SPOTS),
            "reviews": all_reviews,
        }, f, ensure_ascii=False, indent=2)

    csv_path = os.path.join(OUTPUT_DIR, "nanhai_reviews.csv")
    fields = list(all_reviews[0].keys())
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_reviews)

    spot_summary = []
    spot_reviews_map = {}
    for r in all_reviews:
        name = r["spot_name"]
        if name not in spot_reviews_map:
            spot_reviews_map[name] = []
        spot_reviews_map[name].append(r)

    for name, revs in spot_reviews_map.items():
        avg_r = sum(r["rating"] for r in revs) / len(revs)
        pos = sum(1 for r in revs if r["sentiment"] == "positive")
        neu = sum(1 for r in revs if r["sentiment"] == "neutral")
        neg = sum(1 for r in revs if r["sentiment"] == "negative")
        spot_summary.append({
            "name": name,
            "review_count": len(revs),
            "avg_rating": round(avg_r, 2),
            "positive_count": pos,
            "neutral_count": neu,
            "negative_count": neg,
            "positive_rate": round(pos / len(revs) * 100, 1),
            "category": revs[0]["spot_category"],
        })

    summary_path = os.path.join(OUTPUT_DIR, "review_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(spot_summary, f, ensure_ascii=False, indent=2)

    print(f"\n共生成 {len(all_reviews)} 条评论, 涵盖 {len(SCENIC_SPOTS)} 个景点")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")
    print(f"  汇总: {summary_path}")


if __name__ == "__main__":
    generate_all_reviews()
