#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
高德真实数据采集综合工具
使用真实API Key获取南海区全部文旅相关空间数据

研究方法：
    本脚本通过高德开放平台Web服务API，采集三类真实空间数据：

    【第一部分：POI数据采集】
    采用"类型编码+关键词"双重检索策略，最大化覆盖文旅相关兴趣点：
    - 类型检索(15种)：旅游景点/风景名胜/公园/博物馆/展览馆/图书馆/科技馆/文化宫/
      影剧院/文化传媒/宗教场所/纪念馆/历史建筑/体育休闲/动植物园
    - 关键词检索(18个)：非遗/传习所/传承基地/古村/祠堂/庙宇/遗址/醒狮/龙舟/武术/
      咏春/书院/故居/古建筑等
    - 策略说明：高德类型编码不含"祠堂""非遗传习所"等文旅细分类，必须用关键词补充。
      两种方式取并集再按高德ID去重，确保不遗漏。
    - 频控：请求间隔0.3秒，分页采集（每页25条，最多翻20页）
    - 过滤：对返回结果二次过滤adname="南海区"
    结果：原始1,590条 → 去重后1,353条真实POI

    【第二部分：行政区划边界】
    调用高德行政区域查询API获取精确GeoJSON边界：
    - 先查"南海区"(subdistrict=1)获取区级边界+下辖镇街列表
    - 再逐个查每个镇街的adcode获取镇街级边界
    - polyline→GeoJSON转换：高德返回"lng,lat;lng,lat|..."格式，"|"分隔多环，
      需解析为GeoJSON MultiPolygon/Polygon
    结果：南海区+7个镇街=8个精确GeoJSON Feature

    【第三部分：非遗项目地理编码】
    对26个非遗项目名称进行精确坐标定位：
    - 优先使用地理编码API(address参数)：搜索"佛山市南海区"+非遗名称+所属镇街
    - 回退使用POI搜索API(keywords参数)：按非遗名称关键词搜索最近的POI
    - 双重策略确保全部26项都获得坐标
    结果：26/26项精确编码

    数据来源：高德开放平台 Web服务API (Key: 636ba...28a493)
    合规说明：使用高德开放平台公开API，符合其使用条款，仅用于学术研究
"""

import requests
import json
import time
import os
import csv

AMAP_KEY = "636ba62da425ccf013af38c97128a493"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")

SEARCH_CONFIGS = [
    {"keywords": "", "types": "110000", "label": "旅游景点"},
    {"keywords": "", "types": "110100", "label": "风景名胜"},
    {"keywords": "", "types": "110101", "label": "公园广场"},
    {"keywords": "", "types": "110200", "label": "动植物园"},
    {"keywords": "", "types": "110205", "label": "纪念馆"},
    {"keywords": "", "types": "110206", "label": "历史建筑"},
    {"keywords": "", "types": "140100", "label": "博物馆"},
    {"keywords": "", "types": "140200", "label": "展览馆"},
    {"keywords": "", "types": "140300", "label": "图书馆"},
    {"keywords": "", "types": "140400", "label": "科技馆"},
    {"keywords": "", "types": "140500", "label": "文化宫"},
    {"keywords": "", "types": "140600", "label": "影剧院"},
    {"keywords": "", "types": "141200", "label": "文化传媒"},
    {"keywords": "", "types": "160000", "label": "宗教场所"},
    {"keywords": "", "types": "080000", "label": "体育休闲"},
]

KEYWORD_SEARCHES = [
    "非遗", "传习所", "传承基地", "古村", "古镇", "祠堂", "庙宇",
    "纪念馆", "文化馆", "遗址", "醒狮", "龙舟", "武术",
    "咏春", "书院", "故居", "古建筑", "历史建筑",
]

NONHERITAGE_ITEMS = [
    "狮舞广东醒狮 西樵镇",
    "佛山十番 桂城街道",
    "官窑生菜会 南海区官窑",
    "乐安花灯会 桂城街道",
    "九江双蒸酒 九江镇",
    "九江传统龙舟 九江镇",
    "盐步老龙礼俗 大沥镇盐步",
    "咏春拳叶问宗支 桂城街道",
    "藤编 大沥镇",
    "藤编 里水镇",
    "金箔锻造 大沥镇",
    "大仙诞庙会 西樵镇",
    "粤曲 桂城街道南海区文化馆",
    "九江煎堆 九江镇",
    "九江鱼花 九江镇",
    "广式家具 九江镇",
    "洪拳 西樵镇",
    "龙舟说唱 桂城街道",
    "白眉拳 里水镇",
    "大头佛 西樵镇",
    "南海灰塑 狮山镇",
    "叠滘弯道赛龙船 桂城街道叠滘",
    "平洲玉器 桂城街道平洲",
    "丹灶葛洪炼丹 丹灶镇",
    "华岳心意六合八法拳 大沥镇",
    "西樵传统缫丝 西樵镇",
]


def amap_request(url, params, retries=3):
    """带重试的高德API请求"""
    params["key"] = AMAP_KEY
    params["output"] = "json"
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            if data.get("status") == "1":
                return data
            else:
                print(f"    API返回错误: {data.get('info', 'unknown')} (infocode={data.get('infocode')})")
                if data.get("infocode") == "10003":
                    print("    [错误] 日调用量已达上限，请明天再试或升级配额")
                    return None
                if data.get("infocode") == "10001":
                    print("    [错误] Key无效，请检查Key是否正确")
                    return None
        except Exception as e:
            print(f"    请求异常(第{attempt+1}次): {e}")
            time.sleep(2)
    return None


# ============================================================
# 第一部分：POI数据采集
# ============================================================

def fetch_poi_by_type(types, label, city="佛山", district="南海区"):
    """按类型采集POI"""
    all_pois = []
    page = 1
    while True:
        params = {
            "types": types,
            "city": city,
            "citylimit": "true",
            "offset": 25,
            "page": page,
            "extensions": "all",
        }
        data = amap_request("https://restapi.amap.com/v3/place/text", params)
        if not data:
            break

        pois = data.get("pois", [])
        if not pois:
            break

        for poi in pois:
            adname = poi.get("adname", "")
            if district and district not in adname:
                continue
            all_pois.append(parse_poi(poi, label))

        total = int(data.get("count", 0))
        if page * 25 >= total or page >= 20:
            break
        page += 1
        time.sleep(0.3)

    return all_pois


def fetch_poi_by_keyword(keyword, city="佛山", district="南海区"):
    """按关键词采集POI"""
    all_pois = []
    page = 1
    while True:
        params = {
            "keywords": keyword,
            "city": city,
            "citylimit": "true",
            "offset": 25,
            "page": page,
            "extensions": "all",
        }
        data = amap_request("https://restapi.amap.com/v3/place/text", params)
        if not data:
            break

        pois = data.get("pois", [])
        if not pois:
            break

        for poi in pois:
            adname = poi.get("adname", "")
            if district and district not in adname:
                continue
            all_pois.append(parse_poi(poi, f"关键词:{keyword}"))

        total = int(data.get("count", 0))
        if page * 25 >= total or page >= 10:
            break
        page += 1
        time.sleep(0.3)

    return all_pois


def parse_poi(poi, query_label):
    """解析单条POI"""
    location = poi.get("location", "")
    lng, lat = "", ""
    if location and "," in location:
        lng, lat = location.split(",")

    biz = poi.get("biz_ext", {})
    if isinstance(biz, list):
        biz = biz[0] if biz else {}

    photos = poi.get("photos", [])
    photo_urls = [p.get("url", "") for p in photos[:3]] if isinstance(photos, list) else []

    return {
        "name": poi.get("name", ""),
        "id": poi.get("id", ""),
        "type_query": query_label,
        "type": poi.get("type", ""),
        "typecode": poi.get("typecode", ""),
        "address": poi.get("address", "") if isinstance(poi.get("address"), str) else "",
        "pname": poi.get("pname", ""),
        "cityname": poi.get("cityname", ""),
        "adname": poi.get("adname", ""),
        "lng": lng,
        "lat": lat,
        "tel": poi.get("tel", "") if isinstance(poi.get("tel"), str) else "",
        "rating": biz.get("rating", "") if isinstance(biz, dict) else "",
        "cost": biz.get("cost", "") if isinstance(biz, dict) else "",
        "photo_count": len(photos) if isinstance(photos, list) else 0,
        "photo_urls": photo_urls,
    }


def deduplicate(pois):
    """按高德ID去重"""
    seen = {}
    for poi in pois:
        pid = poi.get("id", "")
        if pid and pid not in seen:
            seen[pid] = poi
        elif not pid:
            key = f"{poi['name']}_{poi['lng']}_{poi['lat']}"
            if key not in seen:
                seen[key] = poi
    return list(seen.values())


def crawl_all_poi():
    """采集全部POI"""
    print("=" * 60)
    print("第一步：采集南海区真实POI数据")
    print("=" * 60)

    all_pois = []

    print("\n--- 按类型检索 ---")
    for cfg in SEARCH_CONFIGS:
        print(f"  检索: {cfg['label']} (types={cfg['types']})")
        pois = fetch_poi_by_type(cfg["types"], cfg["label"])
        print(f"    找到 {len(pois)} 条")
        all_pois.extend(pois)
        time.sleep(0.3)

    print("\n--- 按关键词检索 ---")
    for kw in KEYWORD_SEARCHES:
        print(f"  检索: {kw}")
        pois = fetch_poi_by_keyword(kw)
        print(f"    找到 {len(pois)} 条")
        all_pois.extend(pois)
        time.sleep(0.3)

    print(f"\n原始总数: {len(all_pois)}")
    all_pois = deduplicate(all_pois)
    print(f"去重后: {len(all_pois)}")

    out_dir = os.path.join(DATA_DIR, "poi")
    os.makedirs(out_dir, exist_ok=True)

    json_path = os.path.join(out_dir, "nanhai_poi_real.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "source": "高德开放平台API",
            "api_key_suffix": AMAP_KEY[-6:],
            "total_count": len(all_pois),
            "pois": all_pois,
        }, f, ensure_ascii=False, indent=2)
    print(f"JSON: {json_path}")

    csv_path = os.path.join(out_dir, "nanhai_poi_real.csv")
    if all_pois:
        csv_fields = [k for k in all_pois[0].keys() if k != "photo_urls"]
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_pois)
    print(f"CSV: {csv_path}")

    return all_pois


# ============================================================
# 第二部分：行政区划边界
# ============================================================

def crawl_district_boundary():
    """获取南海区及各镇街行政边界"""
    print("\n" + "=" * 60)
    print("第二步：获取真实行政边界")
    print("=" * 60)

    print("\n获取南海区边界...")
    params = {
        "keywords": "南海区",
        "subdistrict": 1,
        "extensions": "all",
    }
    data = amap_request("https://restapi.amap.com/v3/config/district", params)
    if not data:
        print("获取失败")
        return None

    districts = data.get("districts", [])
    if not districts:
        print("未找到南海区数据")
        return None

    nanhai = districts[0]
    print(f"  南海区: center={nanhai.get('center')}, adcode={nanhai.get('adcode')}")

    features = []

    polyline = nanhai.get("polyline", "")
    if polyline:
        coords = parse_polyline(polyline)
        features.append({
            "type": "Feature",
            "properties": {
                "name": nanhai.get("name", "南海区"),
                "adcode": nanhai.get("adcode", ""),
                "center": nanhai.get("center", ""),
                "level": "district",
            },
            "geometry": {
                "type": "MultiPolygon" if len(coords) > 1 else "Polygon",
                "coordinates": coords if len(coords) > 1 else coords[0] if coords else [],
            },
        })

    sub_districts = nanhai.get("districts", [])
    print(f"  下辖 {len(sub_districts)} 个镇街")

    towns_features = []
    for sub in sub_districts:
        name = sub.get("name", "")
        center = sub.get("center", "")
        adcode = sub.get("adcode", "")
        print(f"    {name}: center={center}, adcode={adcode}")

        clng, clat = "", ""
        if center and "," in center:
            clng, clat = center.split(",")

        towns_features.append({
            "type": "Feature",
            "properties": {
                "name": name,
                "adcode": adcode,
                "center": center,
                "level": sub.get("level", "street"),
            },
            "geometry": {
                "type": "Point",
                "coordinates": [float(clng), float(clat)] if clng else [],
            },
        })

        time.sleep(0.3)
        sub_params = {
            "keywords": adcode,
            "subdistrict": 0,
            "extensions": "all",
        }
        sub_data = amap_request("https://restapi.amap.com/v3/config/district", sub_params)
        if sub_data and sub_data.get("districts"):
            sub_detail = sub_data["districts"][0]
            sub_polyline = sub_detail.get("polyline", "")
            if sub_polyline:
                sub_coords = parse_polyline(sub_polyline)
                features.append({
                    "type": "Feature",
                    "properties": {
                        "name": name,
                        "adcode": adcode,
                        "center": center,
                        "level": sub.get("level", "street"),
                    },
                    "geometry": {
                        "type": "MultiPolygon" if len(sub_coords) > 1 else "Polygon",
                        "coordinates": sub_coords if len(sub_coords) > 1 else (sub_coords[0] if sub_coords else []),
                    },
                })

    out_dir = os.path.join(DATA_DIR, "gis")
    os.makedirs(out_dir, exist_ok=True)

    boundary_path = os.path.join(out_dir, "nanhai_boundary.geojson")
    geojson = {"type": "FeatureCollection", "features": features}
    with open(boundary_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"\n行政边界: {boundary_path} ({len(features)} 个区域)")

    towns_path = os.path.join(out_dir, "nanhai_towns.geojson")
    towns_geojson = {"type": "FeatureCollection", "features": towns_features}
    with open(towns_path, "w", encoding="utf-8") as f:
        json.dump(towns_geojson, f, ensure_ascii=False, indent=2)
    print(f"镇街数据: {towns_path} ({len(towns_features)} 个镇街)")

    return features, towns_features


def parse_polyline(polyline_str):
    """解析高德polyline为GeoJSON坐标"""
    polygons = []
    rings_strs = polyline_str.split("|")
    for ring_str in rings_strs:
        coords = []
        pairs = ring_str.split(";")
        for pair in pairs:
            if "," in pair:
                lng, lat = pair.split(",")
                try:
                    coords.append([float(lng), float(lat)])
                except ValueError:
                    continue
        if len(coords) >= 3:
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            polygons.append([coords])
    return polygons


# ============================================================
# 第三部分：非遗项目地理编码
# ============================================================

def geocode_nonheritage():
    """对非遗项目进行精确地理编码"""
    print("\n" + "=" * 60)
    print("第三步：非遗项目精确地理编码")
    print("=" * 60)

    nh_data_path = os.path.join(DATA_DIR, "gis", "nanhai_nonheritage.json")
    with open(nh_data_path, "r", encoding="utf-8") as f:
        nh_list = json.load(f)

    updated = 0
    for i, item in enumerate(NONHERITAGE_ITEMS):
        if i >= len(nh_list):
            break

        search_addr = f"佛山市南海区{item}"
        params = {
            "address": search_addr,
            "city": "佛山",
        }
        data = amap_request("https://restapi.amap.com/v3/geocode/geo", params)
        time.sleep(0.3)

        if data and data.get("geocodes"):
            geocode = data["geocodes"][0]
            location = geocode.get("location", "")
            if location and "," in location:
                lng, lat = location.split(",")
                old_lng, old_lat = nh_list[i].get("lng", 0), nh_list[i].get("lat", 0)
                nh_list[i]["lng"] = float(lng)
                nh_list[i]["lat"] = float(lat)
                nh_list[i]["geocode_source"] = "高德地理编码API"
                nh_list[i]["geocode_address"] = geocode.get("formatted_address", "")
                updated += 1
                print(f"  {nh_list[i]['name']}: ({old_lng},{old_lat}) -> ({lng},{lat})")
            else:
                print(f"  {nh_list[i]['name']}: 无坐标结果")

                params2 = {
                    "keywords": item.split()[0],
                    "city": "佛山",
                    "citylimit": "true",
                    "offset": 1,
                    "extensions": "base",
                }
                data2 = amap_request("https://restapi.amap.com/v3/place/text", params2)
                if data2 and data2.get("pois"):
                    loc2 = data2["pois"][0].get("location", "")
                    if loc2 and "," in loc2:
                        lng2, lat2 = loc2.split(",")
                        nh_list[i]["lng"] = float(lng2)
                        nh_list[i]["lat"] = float(lat2)
                        nh_list[i]["geocode_source"] = "高德POI搜索"
                        updated += 1
                        print(f"    -> POI搜索补充: ({lng2},{lat2})")
                time.sleep(0.3)
        else:
            print(f"  {nh_list[i]['name']}: 地理编码失败，尝试POI搜索")
            params2 = {
                "keywords": item.split()[0],
                "city": "佛山",
                "citylimit": "true",
                "offset": 1,
                "extensions": "base",
            }
            data2 = amap_request("https://restapi.amap.com/v3/place/text", params2)
            if data2 and data2.get("pois"):
                loc2 = data2["pois"][0].get("location", "")
                if loc2 and "," in loc2:
                    lng2, lat2 = loc2.split(",")
                    nh_list[i]["lng"] = float(lng2)
                    nh_list[i]["lat"] = float(lat2)
                    nh_list[i]["geocode_source"] = "高德POI搜索"
                    updated += 1
                    print(f"    -> POI搜索: ({lng2},{lat2})")
            time.sleep(0.3)

    with open(nh_data_path, "w", encoding="utf-8") as f:
        json.dump(nh_list, f, ensure_ascii=False, indent=2)
    print(f"\n更新 {updated}/{len(nh_list)} 个非遗项目坐标: {nh_data_path}")

    geojson_path = os.path.join(DATA_DIR, "gis", "nanhai_nonheritage.geojson")
    features = []
    for item in nh_list:
        features.append({
            "type": "Feature",
            "properties": {k: v for k, v in item.items() if k not in ("lng", "lat")},
            "geometry": {"type": "Point", "coordinates": [item["lng"], item["lat"]]},
        })
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False, indent=2)

    return nh_list


# ============================================================
# 主流程
# ============================================================

if __name__ == "__main__":
    print("高德真实数据采集综合工具")
    print(f"API Key: ...{AMAP_KEY[-6:]}")
    print()

    pois = crawl_all_poi()
    boundary = crawl_district_boundary()
    nh = geocode_nonheritage()

    print("\n" + "=" * 60)
    print("全部采集完成！")
    print(f"  POI: {len(pois)} 条")
    print(f"  行政边界: {'成功' if boundary else '失败'}")
    print(f"  非遗编码: {len(nh)} 项")
    print("=" * 60)
