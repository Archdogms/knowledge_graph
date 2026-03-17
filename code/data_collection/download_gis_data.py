#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GIS空间底图数据准备工具
生成南海区行政边界GeoJSON和空间分析所需的基础数据

实际使用中可通过以下方式获取更精确的数据：
1. 自然资源部标准地图: http://bzdt.ch.mnr.gov.cn/
2. OpenStreetMap: https://download.geofabrik.de/asia/china.html
3. 高德行政区查询API
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "data", "gis")


def generate_nanhai_boundary():
    """
    生成南海区行政边界GeoJSON（简化版）
    实际使用时应替换为自然资源部或OSM的精确数据
    """
    boundary = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": "南海区",
                    "adcode": "440605",
                    "city": "佛山市",
                    "province": "广东省",
                    "level": "district",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [112.89, 22.72], [113.00, 22.72], [113.10, 22.75],
                        [113.20, 22.85], [113.22, 22.95], [113.22, 23.05],
                        [113.20, 23.12], [113.18, 23.16], [113.10, 23.18],
                        [113.00, 23.15], [112.92, 23.10], [112.88, 23.00],
                        [112.87, 22.90], [112.88, 22.80], [112.89, 22.72],
                    ]],
                },
            }
        ],
    }
    return boundary


def generate_towns_data():
    """生成南海区各镇街数据"""
    towns = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "桂城街道", "area_km2": 84.16, "type": "街道"},
                "geometry": {"type": "Point", "coordinates": [113.148, 23.030]},
            },
            {
                "type": "Feature",
                "properties": {"name": "西樵镇", "area_km2": 176.63, "type": "镇"},
                "geometry": {"type": "Point", "coordinates": [112.960, 22.935]},
            },
            {
                "type": "Feature",
                "properties": {"name": "九江镇", "area_km2": 94.75, "type": "镇"},
                "geometry": {"type": "Point", "coordinates": [113.025, 22.790]},
            },
            {
                "type": "Feature",
                "properties": {"name": "丹灶镇", "area_km2": 143.48, "type": "镇"},
                "geometry": {"type": "Point", "coordinates": [113.010, 23.015]},
            },
            {
                "type": "Feature",
                "properties": {"name": "狮山镇", "area_km2": 330.60, "type": "镇"},
                "geometry": {"type": "Point", "coordinates": [113.080, 23.080]},
            },
            {
                "type": "Feature",
                "properties": {"name": "大沥镇", "area_km2": 95.90, "type": "镇"},
                "geometry": {"type": "Point", "coordinates": [113.090, 23.065]},
            },
            {
                "type": "Feature",
                "properties": {"name": "里水镇", "area_km2": 148.28, "type": "镇"},
                "geometry": {"type": "Point", "coordinates": [113.135, 23.120]},
            },
        ],
    }
    return towns


def generate_nanhai_nonheritage():
    """生成南海区非遗项目空间数据"""
    nonheritage = [
        {"name": "狮舞（广东醒狮）", "level": "国家级", "town": "西樵镇", "lng": 112.955, "lat": 22.936, "category": "传统舞蹈"},
        {"name": "十番音乐（佛山十番）", "level": "国家级", "town": "桂城街道", "lng": 113.160, "lat": 23.020, "category": "传统音乐"},
        {"name": "官窑生菜会", "level": "省级", "town": "狮山镇", "lng": 113.038, "lat": 23.102, "category": "民俗"},
        {"name": "灯会（乐安花灯会）", "level": "省级", "town": "桂城街道", "lng": 113.145, "lat": 23.040, "category": "民俗"},
        {"name": "九江双蒸酒酿制技艺", "level": "省级", "town": "九江镇", "lng": 113.028, "lat": 22.793, "category": "传统技艺"},
        {"name": "赛龙舟（九江传统龙舟）", "level": "省级", "town": "九江镇", "lng": 113.030, "lat": 22.795, "category": "传统体育"},
        {"name": "端午节（盐步老龙礼俗）", "level": "省级", "town": "大沥镇", "lng": 113.142, "lat": 23.069, "category": "民俗"},
        {"name": "咏春拳（叶问宗支）", "level": "省级", "town": "桂城街道", "lng": 113.150, "lat": 23.025, "category": "传统体育"},
        {"name": "藤编（大沥）", "level": "省级", "town": "大沥镇", "lng": 113.085, "lat": 23.065, "category": "传统技艺"},
        {"name": "藤编（里水）", "level": "省级", "town": "里水镇", "lng": 113.130, "lat": 23.115, "category": "传统技艺"},
        {"name": "金箔锻造技艺", "level": "省级", "town": "大沥镇", "lng": 113.085, "lat": 23.065, "category": "传统技艺"},
        {"name": "庙会（大仙诞庙会）", "level": "省级", "town": "西樵镇", "lng": 112.960, "lat": 22.938, "category": "民俗"},
        {"name": "粤曲", "level": "省级", "town": "桂城街道", "lng": 113.148, "lat": 23.030, "category": "传统音乐"},
        {"name": "糕点制作技艺（九江煎堆）", "level": "省级", "town": "九江镇", "lng": 113.025, "lat": 22.790, "category": "传统技艺"},
        {"name": "九江鱼花生产习俗", "level": "省级", "town": "九江镇", "lng": 113.025, "lat": 22.785, "category": "民俗"},
        {"name": "广式家具制作技艺", "level": "省级", "town": "九江镇", "lng": 113.030, "lat": 22.788, "category": "传统技艺"},
        {"name": "洪拳（南海洪拳）", "level": "省级", "town": "西樵镇", "lng": 112.958, "lat": 22.935, "category": "传统体育"},
        {"name": "龙舟说唱", "level": "市级", "town": "桂城街道", "lng": 113.153, "lat": 23.029, "category": "传统音乐"},
        {"name": "白眉拳", "level": "市级", "town": "里水镇", "lng": 113.132, "lat": 23.118, "category": "传统体育"},
        {"name": "大头佛", "level": "市级", "town": "西樵镇", "lng": 112.962, "lat": 22.940, "category": "传统舞蹈"},
        {"name": "南海灰塑", "level": "市级", "town": "狮山镇", "lng": 113.115, "lat": 23.072, "category": "传统美术"},
        {"name": "叠滘弯道赛龙船", "level": "市级", "town": "桂城街道", "lng": 113.124, "lat": 23.043, "category": "传统体育"},
        {"name": "平洲传统玉器制作技艺", "level": "市级", "town": "桂城街道", "lng": 113.190, "lat": 23.005, "category": "传统技艺"},
        {"name": "丹灶葛洪炼丹传说", "level": "市级", "town": "丹灶镇", "lng": 113.015, "lat": 23.018, "category": "民间文学"},
        {"name": "华岳心意六合八法拳", "level": "市级", "town": "大沥镇", "lng": 113.092, "lat": 23.068, "category": "传统体育"},
        {"name": "西樵传统缫丝技艺", "level": "市级", "town": "西樵镇", "lng": 112.958, "lat": 22.932, "category": "传统技艺"},
    ]

    geojson = {
        "type": "FeatureCollection",
        "features": [],
    }
    for item in nonheritage:
        geojson["features"].append({
            "type": "Feature",
            "properties": {
                "name": item["name"],
                "level": item["level"],
                "town": item["town"],
                "category": item["category"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [item["lng"], item["lat"]],
            },
        })

    return geojson, nonheritage


def main():
    print("=" * 60)
    print("南海区GIS空间底图数据准备")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    boundary = generate_nanhai_boundary()
    path = os.path.join(OUTPUT_DIR, "nanhai_boundary.geojson")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(boundary, f, ensure_ascii=False, indent=2)
    print(f"行政边界: {path}")

    towns = generate_towns_data()
    path = os.path.join(OUTPUT_DIR, "nanhai_towns.geojson")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(towns, f, ensure_ascii=False, indent=2)
    print(f"镇街数据: {path} ({len(towns['features'])} 个镇街)")

    geojson, raw_list = generate_nanhai_nonheritage()
    path = os.path.join(OUTPUT_DIR, "nanhai_nonheritage.geojson")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"非遗数据: {path} ({len(raw_list)} 个项目)")

    json_path = os.path.join(OUTPUT_DIR, "nanhai_nonheritage.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(raw_list, f, ensure_ascii=False, indent=2)

    print("\nGIS数据准备完成！")
    print("注意: 行政边界为简化版，实际研究中请替换为自然资源部标准数据。")


if __name__ == "__main__":
    main()
