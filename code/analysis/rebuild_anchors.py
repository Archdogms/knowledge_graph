"""重建 cultural_anchors.json：镇街回填 + 91 项非遗全量并入 + 非遗空间合理展开。

两个老问题：
  1. 原 anchors 的 98 条 town 为 "nan/未知"。
  2. 91 项非遗只进了 36 条；即便是带坐标的 26 条，也有多个项目共享同一个"登记地址"坐标。

修复：
  A. 镇街归属：先从 address/name 做关键字匹配，失败再用 (lng,lat) 做点在面内。
  B. 非遗落位：
     - 先尝试根据项目名里的村/街关键词做**点名落位**（叠滘→叠滘水乡、
       乐安→乐安社区、西联村→西联、平洲→平洲玉器街、万石→万石社区等）。
     - 对 `nanhai_nonheritage.json` 里的坐标做**共享检测**：任何坐标被 ≥2 个
       项目共用，都视为"登记地址/保护中心"，不再当真实坐标，走镇域内采样。
     - 剩余的按"**镇街多边形内均匀随机采样**"落位（拒绝采样），保证每条非遗
       都落在自己所属镇街范围内、且相互分散。
  C. 主桥梁（不可移动文物/文化景观/历史名村/圩市街区）保留原始坐标不动，
     仅修正坏的 town 字段。
"""
from __future__ import annotations

import json
import random
import shutil
from collections import Counter
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

ANCHOR_PATH = DATA / "anchors" / "cultural_anchors.json"
NH_COORD_PATH = DATA / "gis" / "nanhai_nonheritage.json"
NH_FULL_PATH = DATA / "gis" / "nanhai_nonheritage_full90.json"
TOWNS_GEO = DATA / "gis" / "nanhai_towns_real.geojson"

TOWN_KEYWORDS = [
    "西樵镇", "九江镇", "丹灶镇", "狮山镇", "桂城街道", "大沥镇", "里水镇",
]
TOWN_ALIAS = {
    "平洲": "桂城街道", "盐步": "大沥镇", "黄岐": "大沥镇",
    "罗村": "狮山镇", "小塘": "狮山镇", "官窑": "狮山镇",
    "金沙": "丹灶镇", "和顺": "里水镇",
}

# 名字里出现这些关键词 → 落到对应大致坐标（区内已知社区/地标粗略位置）
NAMED_SPOT = {
    "叠滘": (113.172, 23.028),      # 桂城叠滘社区
    "乐安": (113.120, 23.030),      # 桂城乐安社区
    "平洲": (113.180, 23.015),      # 桂城平洲
    "西联": (113.149, 23.060),      # 桂城西联
    "赤山": (113.163, 23.065),      # 桂城赤山
    "万石": (113.130, 23.050),      # 桂城万石
    "狮中": (113.146, 23.055),      # 桂城狮中
    "石石肯": (113.153, 23.060),    # 桂城石石肯
    "官窑": (113.046, 23.167),      # 狮山官窑
    "罗村": (113.089, 23.106),      # 狮山罗村
    "小塘": (112.985, 23.147),      # 狮山小塘
    "和顺": (113.067, 23.205),      # 里水和顺
    "盐步": (113.120, 23.098),      # 大沥盐步
    "黄岐": (113.179, 23.122),      # 大沥黄岐
    "九江": (112.999, 22.857),      # 九江镇中心
    "丹灶": (112.895, 23.037),      # 丹灶镇中心
    "西樵": (112.946, 22.946),      # 西樵镇中心
    "松塘": (112.947, 22.968),
    "仙岗": (112.888, 23.042),
}


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def derive_town_from_text(text: str) -> str | None:
    if not text:
        return None
    for kw in TOWN_KEYWORDS:
        if kw in text:
            return kw
    for alias, full in TOWN_ALIAS.items():
        if alias in text:
            return full
    return None


def build_town_lookup():
    fc = load_json(TOWNS_GEO)
    geoms, names = [], []
    for f in fc["features"]:
        geoms.append(shape(f["geometry"]))
        names.append(f["properties"].get("name", "未知"))
    tree = STRtree(geoms)

    def which(lng, lat):
        try:
            p = Point(float(lng), float(lat))
        except Exception:
            return None
        for idx in tree.query(p):
            g = geoms[int(idx)]
            if g.contains(p):
                return names[int(idx)]
        return None

    by_name = {n: g for g, n in zip(geoms, names)}
    centroids = {n: (g.representative_point().x, g.representative_point().y) for g, n in zip(geoms, names)}
    return which, by_name, centroids


def is_bad_town(t) -> bool:
    if t is None:
        return True
    s = str(t)
    if s.lower() == "nan" or s in ("", "未知", "None"):
        return True
    try:
        import math
        if isinstance(t, float) and math.isnan(t):
            return True
    except Exception:
        pass
    if s not in TOWN_KEYWORDS:
        return True
    return False


def sample_in_polygon(poly, rng: random.Random, max_tries: int = 500) -> tuple[float, float]:
    """多边形内均匀采样：基于 bbox 的拒绝采样。"""
    minx, miny, maxx, maxy = poly.bounds
    for _ in range(max_tries):
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        if poly.contains(Point(x, y)):
            return round(x, 6), round(y, 6)
    c = poly.representative_point()
    return round(c.x, 6), round(c.y, 6)


def detect_named_spot(name: str) -> tuple[float, float] | None:
    """若项目名里含 NAMED_SPOT 关键字，返回锚定坐标。"""
    if not name:
        return None
    for kw, pt in NAMED_SPOT.items():
        if kw in name:
            return pt
    return None


def main() -> None:
    print("[1/5] 读取原始数据 ...")
    raw = load_json(ANCHOR_PATH)
    anchors = raw["anchors"]
    print(f"     原 anchors = {len(anchors)}")

    backup = ANCHOR_PATH.with_suffix(".bak.json")
    if not backup.exists():
        shutil.copy2(ANCHOR_PATH, backup)
        print(f"     已备份原文件 -> {backup.name}")

    which_town, polys_by_name, centroids = build_town_lookup()

    print("[2/5] 修复镇街归属 ...")
    fixed_addr = fixed_geo = kept = 0
    for a in anchors:
        if not is_bad_town(a.get("town")):
            continue
        t = derive_town_from_text(a.get("address") or "")
        if not t:
            t = derive_town_from_text(a.get("name") or "")
        if t:
            a["town"] = t
            a["town_fix_source"] = "address"
            fixed_addr += 1
            continue
        t = which_town(a.get("lng"), a.get("lat"))
        if t:
            a["town"] = t
            a["town_fix_source"] = "geometry"
            fixed_geo += 1
            continue
        kept += 1
    print(f"     地址修正 {fixed_addr}；空间修正 {fixed_geo}；保留未修 {kept}")

    print("[3/5] 并入完整 91 项非遗并做合理落位 ...")
    nh26_raw = load_json(NH_COORD_PATH)
    nh91_raw = load_json(NH_FULL_PATH)
    nh26 = nh26_raw if isinstance(nh26_raw, list) else nh26_raw.get("items", [])
    nh91 = nh91_raw if isinstance(nh91_raw, list) else nh91_raw.get("items", [])

    # 检测聚簇坐标：被 ≥2 个项目共用的"真实地址"视为登记地址，弃用
    coord_count: Counter = Counter()
    for x in nh26:
        if x.get("lng") and x.get("lat"):
            coord_count[(round(float(x["lng"]), 5), round(float(x["lat"]), 5))] += 1
    shared = {k for k, v in coord_count.items() if v >= 2}
    if shared:
        print(f"     发现 {len(shared)} 个共用坐标（登记地址），共涉及 "
              f"{sum(coord_count[k] for k in shared)} 条非遗 → 改为镇域随机落位")

    def real_coord(name: str) -> tuple[float, float] | None:
        for x in nh26:
            if x.get("name") == name and x.get("lng") and x.get("lat"):
                k = (round(float(x["lng"]), 5), round(float(x["lat"]), 5))
                if k in shared:
                    return None  # 共享坐标弃用
                return float(x["lng"]), float(x["lat"])
        return None

    non_nh_anchors = [a for a in anchors if a.get("anchor_type") != "非遗项目"]
    removed = len(anchors) - len(non_nh_anchors)
    print(f"     移除原 '非遗项目' anchors: {removed}")

    rng = random.Random(42)
    new_nh: list[dict] = []
    src_stats: Counter = Counter()
    for i, item in enumerate(nh91):
        name = item["name"]
        town = item.get("town") or "未知"
        if town == "南海区":
            town = "桂城街道"
        level = item.get("level") or ""
        cat = item.get("category") or ""
        rec = {
            "name": name,
            "anchor_type": "非遗项目",
            "sub_type": cat,
            "era": "",
            "protection_level": f"{level}非物质文化遗产代表性项目" if level else "非物质文化遗产",
            "address": f"南海区{town}",
            "town": town,
            "id": f"NH_{i+1:04d}",
        }

        lnglat = real_coord(name)
        src = "geocoded"
        if lnglat is None:
            spot = detect_named_spot(name)
            if spot is not None:
                # 名字点名落位，±250 m 抖动避免完全同格
                jx = rng.uniform(-0.0025, 0.0025)
                jy = rng.uniform(-0.0025, 0.0025)
                lnglat = (spot[0] + jx, spot[1] + jy)
                src = "name_hint"
        if lnglat is None:
            poly = polys_by_name.get(town)
            if poly is None:
                poly = polys_by_name.get("桂城街道")
            lnglat = sample_in_polygon(poly, rng)
            src = "polygon_sample"

        rec["lng"] = round(lnglat[0], 6)
        rec["lat"] = round(lnglat[1], 6)
        rec["coord_source"] = src
        src_stats[src] += 1
        new_nh.append(rec)
    print(f"     非遗落位: {dict(src_stats)}")

    merged_anchors = non_nh_anchors + new_nh

    print("[4/5] 汇总统计 ...")
    type_stats = Counter(a.get("anchor_type") or "?" for a in merged_anchors)
    town_stats = Counter(a.get("town") or "未知" for a in merged_anchors)
    print("     type_stats:", dict(type_stats))
    print("     town_stats:")
    for k, v in town_stats.most_common():
        print(f"        {k}: {v}")

    print("[5/5] 写回 cultural_anchors.json ...")
    out = {
        "total": len(merged_anchors),
        "type_stats": dict(type_stats),
        "town_stats": dict(town_stats),
        "anchors": merged_anchors,
        "notes": [
            "2026-04-21 rebuild v2: 修复 98 条镇街归属；合并 91 项非遗；",
            "非遗落位三档：name_hint（名字含村/街地标）→ geocoded（真实且非共享地址）→ polygon_sample（镇域多边形内均匀采样）。",
            "原共享登记地址坐标全部弃用，改为镇域随机采样。",
        ],
    }
    ANCHOR_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"     已写入 {ANCHOR_PATH}（备份在 {backup.name}）")


if __name__ == "__main__":
    main()
