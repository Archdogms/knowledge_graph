#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
辅助补充数据解析工具
将 shapefile（文化点、POI）和 xlsx（评论）统一解析为项目标准 JSON 格式

数据来源：
    1. wenhuadian/ — 南海三镇官方文化资源普查（2019年）：
       不可移动文物(80)、非遗(37)、文化景观(20)、名镇名村传统村落(16)、
       圩市街区(18)、名村(1)
    2. poi/ — 佛山市全量 POI shapefile（2022/2024两期，72万+条）
    3. 携程去哪儿马蜂窝评价/ — 三平台旅游评论数据（1.5万+条）

输出：
    - cultural_anchors.json：文化载体资源锚点表（172条）
    - nanhai_culture_poi.json：南海区文旅相关 POI（从shapefile中筛选）
    - merged_reviews.json：合并后的多平台评论数据
"""

import os
import sys
import json
import re
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

try:
    import geopandas as gpd
    import pandas as pd
    HAS_GEO = True
except ImportError:
    HAS_GEO = False
    print("[警告] 未安装 geopandas/pandas，无法解析 shapefile/xlsx")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUPP_DIR = os.path.join(BASE_DIR, "..", "..", "辅助补充数据")
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
DB_DIR = os.path.join(DATA_DIR, "database")
REVIEW_DIR = os.path.join(DATA_DIR, "reviews")


# ── 镇街名标准化 ──
TOWN_NORM = {
    "西樵": "西樵镇", "九江": "九江镇", "丹灶": "丹灶镇",
    "狮山": "狮山镇", "大沥": "大沥镇", "里水": "里水镇",
    "桂城": "桂城街道",
}


def norm_town(raw):
    if not raw:
        return ""
    raw = str(raw).strip().replace("\n", "")
    for k, v in TOWN_NORM.items():
        if k in raw:
            return v
    return raw


# ═══════════════════════════════════════════
#  Part 1: 文化载体锚点表
# ═══════════════════════════════════════════

def parse_immovable_relics():
    """不可移动文物 shapefile → 锚点列表"""
    fp = os.path.join(SUPP_DIR, "wenhuadian", "不可移动文物.shp")
    if not os.path.exists(fp):
        return []
    gdf = gpd.read_file(fp)
    anchors = []
    for _, r in gdf.iterrows():
        geom = r.geometry
        lng = geom.x if geom and geom.geom_type == "Point" else 0
        lat = geom.y if geom and geom.geom_type == "Point" else 0
        anchors.append({
            "name": str(r.get("名称", "")).strip(),
            "anchor_type": "不可移动文物",
            "sub_type": str(r.get("类别", "")).strip(),
            "era": str(r.get("年代", "")).strip(),
            "protection_level": str(r.get("保护级", "")).strip(),
            "address": str(r.get("地址", "")).strip(),
            "town": norm_town(r.get("镇（街", "")),
            "lng": round(lng, 6),
            "lat": round(lat, 6),
        })
    return anchors


def parse_nonheritage_shp():
    """非遗 shapefile → 锚点列表"""
    fp = os.path.join(SUPP_DIR, "wenhuadian", "非遗.shp")
    if not os.path.exists(fp):
        return []
    gdf = gpd.read_file(fp)
    anchors = []
    for _, r in gdf.iterrows():
        geom = r.geometry
        lng = geom.x if geom and geom.geom_type == "Point" else 0
        lat = geom.y if geom and geom.geom_type == "Point" else 0
        if lng < 1:
            lng, lat = 0, 0
        anchors.append({
            "name": str(r.get("名称", "")).strip(),
            "anchor_type": "非遗项目",
            "sub_type": str(r.get("类型", "")).strip(),
            "era": "",
            "protection_level": str(r.get("级别", "")).strip(),
            "address": "",
            "town": norm_town(r.get("乡镇", "")),
            "lng": round(lng, 6),
            "lat": round(lat, 6),
        })
    return anchors


def parse_cultural_landscape():
    """文化景观 shapefile → 锚点列表"""
    fp = os.path.join(SUPP_DIR, "wenhuadian", "文化景观.shp")
    if not os.path.exists(fp):
        return []
    gdf = gpd.read_file(fp)
    anchors = []
    for _, r in gdf.iterrows():
        geom = r.geometry
        lng = geom.x if geom and geom.geom_type == "Point" else 0
        lat = geom.y if geom and geom.geom_type == "Point" else 0
        if lng < 1:
            lng, lat = 0, 0
        anchors.append({
            "name": str(r.get("名称", "")).strip(),
            "anchor_type": "文化景观",
            "sub_type": "",
            "era": "",
            "protection_level": "",
            "address": "",
            "town": norm_town(r.get("所属镇", "")),
            "lng": round(lng, 6),
            "lat": round(lat, 6),
        })
    return anchors


def parse_villages():
    """名镇名村传统村落 + 名村 → 锚点列表"""
    anchors = []
    for shp_name in ["名镇名村传统村落", "名村"]:
        fp = os.path.join(SUPP_DIR, "wenhuadian", f"{shp_name}.shp")
        if not os.path.exists(fp):
            continue
        gdf = gpd.read_file(fp)
        for _, r in gdf.iterrows():
            geom = r.geometry
            lng = geom.x if geom and geom.geom_type == "Point" else 0
            lat = geom.y if geom and geom.geom_type == "Point" else 0
            anchors.append({
                "name": str(r.get("名称", "")).strip(),
                "anchor_type": "历史文化名村",
                "sub_type": str(r.get("类别", "")).strip(),
                "era": "",
                "protection_level": str(r.get("类别", "")).strip(),
                "address": "",
                "town": norm_town(r.get("标注", "")),
                "lng": round(lng, 6),
                "lat": round(lat, 6),
            })
    return anchors


def parse_market_streets():
    """圩市街区 → 锚点列表"""
    fp = os.path.join(SUPP_DIR, "wenhuadian", "圩市街区.shp")
    if not os.path.exists(fp):
        return []
    gdf = gpd.read_file(fp)
    anchors = []
    for _, r in gdf.iterrows():
        geom = r.geometry
        lng = geom.x if geom and geom.geom_type == "Point" else 0
        lat = geom.y if geom and geom.geom_type == "Point" else 0
        anchors.append({
            "name": str(r.get("名称", "")).strip(),
            "anchor_type": "圩市街区",
            "sub_type": "",
            "era": "",
            "protection_level": "",
            "address": "",
            "town": norm_town(r.get("所属镇", "")),
            "lng": round(lng, 6),
            "lat": round(lat, 6),
        })
    return anchors


def build_cultural_anchors():
    """汇总全部文化载体锚点"""
    all_anchors = []
    parsers = [
        ("不可移动文物", parse_immovable_relics),
        ("非遗项目", parse_nonheritage_shp),
        ("文化景观", parse_cultural_landscape),
        ("历史文化名村", parse_villages),
        ("圩市街区", parse_market_streets),
    ]

    for label, fn in parsers:
        items = fn()
        print(f"  {label}: {len(items)} 条")
        all_anchors.extend(items)

    seen = set()
    deduped = []
    for a in all_anchors:
        key = a["name"]
        if key and key not in seen:
            seen.add(key)
            a["id"] = f"ANC_{len(deduped)+1:04d}"
            deduped.append(a)

    type_stats = Counter(a["anchor_type"] for a in deduped)
    town_stats = Counter(a["town"] for a in deduped if a["town"])

    os.makedirs(DB_DIR, exist_ok=True)
    out_path = os.path.join(DB_DIR, "cultural_anchors.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(deduped),
            "type_stats": dict(type_stats.most_common()),
            "town_stats": dict(town_stats.most_common()),
            "anchors": deduped,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  文化载体锚点: {out_path} ({len(deduped)} 条)")
    for t, c in type_stats.most_common():
        print(f"    {t}: {c}")
    return deduped


# ═══════════════════════════════════════════
#  Part 2: Shapefile POI → 文旅 POI
# ═══════════════════════════════════════════

CULTURE_POI_TYPECODES = {
    "110": "风景名胜",
    "1101": "风景名胜",
    "1102": "人文古迹",
    "1103": "公园绿地",
    "1104": "宗教场所",
    "1105": "文化场馆",
}

CULTURE_POI_NAME_KEYWORDS = [
    "祠堂", "宗祠", "书院", "故居", "纪念馆", "纪念堂", "博物馆", "遗址",
    "古村", "古建筑", "庙", "寺", "庵", "观", "宫", "祠", "塔", "桥",
    "牌坊", "炮楼", "碉楼", "醒狮", "龙舟", "武术", "非遗", "文化",
    "影视城", "景区", "公园", "广场",
]


def parse_shapefile_poi():
    """从 shapefile 中筛选南海区文旅 POI"""
    poi_dir = os.path.join(SUPP_DIR, "poi")
    if not os.path.exists(poi_dir):
        return []

    fp_2024 = os.path.join(poi_dir, "2024_10", "佛山市.shp")
    fp_2022 = os.path.join(poi_dir, "2022_10", "佛山市.shp")
    fp = fp_2024 if os.path.exists(fp_2024) else fp_2022
    if not os.path.exists(fp):
        return []

    print(f"  加载 POI shapefile: {fp}")
    gdf = gpd.read_file(fp)
    nanhai = gdf[gdf["adname"] == "南海区"].copy()
    print(f"  南海区 POI: {len(nanhai)} / 总 {len(gdf)}")

    culture_pois = []
    for _, r in nanhai.iterrows():
        tc = str(r.get("typecode", ""))
        name = str(r.get("name", ""))
        is_culture = False

        for prefix in CULTURE_POI_TYPECODES:
            if tc.startswith(prefix):
                is_culture = True
                break

        if not is_culture:
            for kw in CULTURE_POI_NAME_KEYWORDS:
                if kw in name:
                    is_culture = True
                    break

        if not is_culture:
            continue

        geom = r.geometry
        lng = round(geom.x, 6) if geom and geom.geom_type == "Point" else 0
        lat = round(geom.y, 6) if geom and geom.geom_type == "Point" else 0

        culture_pois.append({
            "id": str(r.get("poiid", "")),
            "name": name.strip(),
            "address": str(r.get("address", "")).strip(),
            "type": str(r.get("type", "")).strip(),
            "typecode": tc,
            "lng": lng,
            "lat": lat,
            "town": str(r.get("business_a", "")).strip(),
            "source": "shapefile_2024",
        })

    out_path = os.path.join(DATA_DIR, "poi", "nanhai_culture_poi_shp.json")
    os.makedirs(os.path.join(DATA_DIR, "poi"), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(culture_pois),
            "source": "佛山市POI shapefile 2024_10",
            "filter": "南海区 + 文旅相关typecode/名称关键词",
            "pois": culture_pois,
        }, f, ensure_ascii=False, indent=2)

    print(f"  文旅 POI (shapefile): {out_path} ({len(culture_pois)} 条)")
    return culture_pois


# ═══════════════════════════════════════════
#  Part 3: 评论 xlsx → 合并评论
# ═══════════════════════════════════════════

def parse_review_xlsx():
    """解析三平台评论 xlsx 并合并"""
    xlsx_dir = os.path.join(SUPP_DIR, "携程去哪儿马蜂窝评价")
    if not os.path.exists(xlsx_dir):
        return []

    all_reviews = []

    for f in os.listdir(xlsx_dir):
        if not f.endswith(".xlsx"):
            continue
        fp = os.path.join(xlsx_dir, f)
        df = pd.read_excel(fp)

        if "景点名称" in df.columns:
            # 马蜂窝格式
            for _, row in df.iterrows():
                text = str(row.get("标题", "")).strip()
                if not text or text == "nan":
                    continue
                all_reviews.append({
                    "platform": "马蜂窝",
                    "spot_name": str(row.get("景点名称", "")).strip(),
                    "user": str(row.get("名称", "")).strip(),
                    "text": text,
                    "time": str(row.get("时间", "")),
                    "source_note": str(row.get("from", "")),
                })

        elif "标题2" in df.columns and "文本" in df.columns:
            # 去哪儿格式
            for _, row in df.iterrows():
                text = str(row.get("文本", "")).strip()
                spot = str(row.get("标题2", "")).strip()
                if not text or text == "nan" or not spot or spot == "nan":
                    continue
                text_clean = re.sub(r'\s+', ' ', text)[:2000]
                all_reviews.append({
                    "platform": "去哪儿",
                    "spot_name": spot,
                    "user": str(row.get("评论7", "")).strip(),
                    "text": text_clean,
                    "time": "",
                    "source_note": str(row.get("标题链接", "")),
                })

        elif "关键词" in df.columns or "评论4" in df.columns:
            # 携程格式
            for _, row in df.iterrows():
                title = str(row.get("标题", "")).strip()
                review_field = str(row.get("字段1", "")).strip()
                if title == "nan":
                    title = ""
                if review_field == "nan":
                    review_field = ""
                spot_name = title
                text = review_field if review_field else title
                if not text:
                    continue
                comment_count = str(row.get("评论4", ""))
                all_reviews.append({
                    "platform": "携程",
                    "spot_name": spot_name,
                    "user": "",
                    "text": text[:2000],
                    "time": "",
                    "source_note": str(row.get("标题链接", "")),
                    "comment_count": comment_count,
                })

    platform_stats = Counter(r["platform"] for r in all_reviews)
    spot_stats = Counter(r["spot_name"] for r in all_reviews)

    os.makedirs(REVIEW_DIR, exist_ok=True)
    out_path = os.path.join(REVIEW_DIR, "merged_reviews_supp.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(all_reviews),
            "platform_stats": dict(platform_stats.most_common()),
            "top_spots": dict(spot_stats.most_common(30)),
            "reviews": all_reviews,
        }, f, ensure_ascii=False, indent=2)

    print(f"  合并评论: {out_path} ({len(all_reviews)} 条)")
    for p, c in platform_stats.most_common():
        print(f"    {p}: {c}")
    return all_reviews


# ═══════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════

def main():
    if not HAS_GEO:
        print("请先安装: pip install geopandas pandas openpyxl")
        return

    print("=" * 60)
    print("辅助补充数据解析")
    print("=" * 60)

    print("\n--- Part 1: 文化载体锚点 ---")
    anchors = build_cultural_anchors()

    print("\n--- Part 2: Shapefile POI ---")
    culture_pois = parse_shapefile_poi()

    print("\n--- Part 3: 评论数据 ---")
    reviews = parse_review_xlsx()

    print("\n" + "=" * 60)
    print("汇总:")
    print(f"  文化锚点: {len(anchors)} 条")
    print(f"  文旅POI(shapefile): {len(culture_pois)} 条")
    print(f"  评论数据: {len(reviews)} 条")
    print("=" * 60)


if __name__ == "__main__":
    main()
