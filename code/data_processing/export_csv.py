#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将所有JSON结果数据导出为CSV表格，便于查看和论文引用
"""

import json
import csv
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
BASE = os.path.join(_BASE_DIR, "data")
OUT = os.path.join(_BASE_DIR, "output", "tables")


def export_reviews():
    """导出评论数据为CSV"""
    with open(os.path.join(BASE, "reviews", "nanhai_reviews_real.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = data["reviews"]
    path = os.path.join(BASE, "reviews", "nanhai_reviews_real.csv")
    fields = ["spot_name", "rating", "review_text", "review_date", "source", "sentiment"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"评论CSV: {path} ({len(rows)}条)")


def export_review_summary():
    """导出评论汇总为CSV"""
    with open(os.path.join(BASE, "reviews", "review_summary_real.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    path = os.path.join(BASE, "reviews", "review_summary_real.csv")
    fields = ["name", "total_count", "text_review_count", "avg_rating",
              "positive_count", "neutral_count", "negative_count", "positive_rate", "sources"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in data:
            row["sources"] = ";".join(row.get("sources", []))
            w.writerow(row)
    print(f"评论汇总CSV: {path} ({len(data)}条)")


def export_poi():
    """导出清洗后POI为CSV"""
    with open(os.path.join(BASE, "database", "poi_cleaned.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = data["pois"]
    path = os.path.join(BASE, "poi", "nanhai_poi_real.csv")
    fields = ["id", "name", "category", "original_type", "address", "town",
              "lng", "lat", "rating", "has_nonheritage", "nonheritage_match", "query_type"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            row["nonheritage_match"] = ";".join(row.get("nonheritage_match", []))
            w.writerow(row)
    print(f"POI CSV: {path} ({len(rows)}条)")


def export_entities():
    """导出文化实体为CSV"""
    with open(os.path.join(BASE, "database", "culture_entities.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = data["entities"]
    path = os.path.join(OUT, "culture_entities.csv")
    fields = ["id", "name", "type", "mentions", "confidence", "source_count", "weight", "sources"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            row["sources"] = ";".join(row.get("sources", []))
            w.writerow(row)
    print(f"实体CSV: {path} ({len(rows)}条)")


def export_experience():
    """导出体验度评分为CSV"""
    with open(os.path.join(OUT, "experience_scores.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    path = os.path.join(OUT, "experience_scores.csv")
    fields = ["name", "category", "town", "rating", "has_nonheritage",
              "total_score", "level", "score_rating", "score_review",
              "score_positive", "score_culture", "score_photos"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(data)
    print(f"体验度CSV: {path} ({len(data)}条)")


def export_coupling():
    """导出耦合分析为CSV"""
    with open(os.path.join(BASE, "database", "coupling_results.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for item in data["strong_coupling"]:
        rows.append({"status": "强耦合", "culture": item["culture_element"],
                      "scenic": item["scenic_spot"], "match_type": item["match_type"],
                      "notes": item["notes"]})
    for item in data["misalignment"]:
        rows.append({"status": "错位", "culture": item["culture_element"],
                      "scenic": item["scenic_spot"], "match_type": item["match_type"],
                      "notes": item["notes"]})
    for item in data["missing_A"]:
        rows.append({"status": "缺失A(文化未转化)", "culture": item["culture_element"],
                      "scenic": "", "match_type": item.get("level", ""),
                      "notes": item["reason"]})
    for item in data["missing_B"]:
        rows.append({"status": "缺失B(有形无魂)", "culture": "",
                      "scenic": item["scenic_spot"], "match_type": item.get("category", ""),
                      "notes": item["reason"]})

    path = os.path.join(OUT, "coupling_analysis.csv")
    fields = ["status", "culture", "scenic", "match_type", "notes"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"耦合CSV: {path} ({len(rows)}条)")


def export_spatial():
    """导出镇街空间统计为CSV"""
    with open(os.path.join(OUT, "spatial_analysis_results.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for town, stats in data["town_stats"].items():
        rows.append({
            "town": town,
            "poi_count": stats["poi_count"],
            "nh_count": stats["nh_count"],
            "total_resources": stats["total_resources"],
            "culture_density": stats["culture_density"],
            "tourism_density": stats["tourism_density"],
        })
    rows.sort(key=lambda x: -x["total_resources"])

    path = os.path.join(OUT, "spatial_town_stats.csv")
    fields = ["town", "poi_count", "nh_count", "total_resources", "culture_density", "tourism_density"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"镇街统计CSV: {path} ({len(rows)}条)")


def export_nonheritage():
    """导出非遗数据为CSV"""
    with open(os.path.join(BASE, "gis", "nanhai_nonheritage.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    path = os.path.join(OUT, "nonheritage.csv")
    fields = ["name", "level", "town", "lng", "lat", "category", "geocode_source", "geocode_address"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(data)
    print(f"非遗CSV: {path} ({len(data)}条)")


if __name__ == "__main__":
    print("=" * 50)
    print("导出所有结果数据为CSV表格")
    print("=" * 50)
    os.makedirs(OUT, exist_ok=True)
    export_reviews()
    export_review_summary()
    export_poi()
    export_entities()
    export_experience()
    export_coupling()
    export_spatial()
    export_nonheritage()
    print("\n全部完成！")
