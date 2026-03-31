#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import math
import os
import shutil

import shapefile


ROOT = r"c:\Users\ms\Desktop\mid\knowledge_graph"
SRC_DIR = os.path.join(ROOT, "data", "gis")
OUT_DIR = os.path.join(ROOT, "output", "gis")
WGS84_WKT = (
    'GEOGCS["WGS 84",DATUM["WGS_1984",'
    'SPHEROID["WGS 84",6378137,298.257223563]],'
    'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
)


def safe_text(value, max_len=200):
    if value is None:
        return ""
    return str(value)[:max_len]


def write_sidecars(shp_base):
    with open(shp_base + ".prj", "w", encoding="ascii") as f:
        f.write(WGS84_WKT)
    with open(shp_base + ".cpg", "w", encoding="ascii") as f:
        f.write("UTF-8")


def geojson_to_shp(src_path, shp_base):
    data = json.load(open(src_path, "r", encoding="utf-8"))
    features = data.get("features", [])

    geom_type = None
    for feat in features:
        g = (feat.get("geometry") or {}).get("type")
        if g in ("Point", "MultiPoint", "Polygon", "MultiPolygon"):
            geom_type = g
            break

    if geom_type in ("Point", "MultiPoint"):
        writer = shapefile.Writer(shp_base, shapeType=shapefile.POINT, encoding="utf-8")
        writer.field("name", "C", 100)
        writer.field("adcode", "C", 20)
        writer.field("level", "C", 30)
        writer.field("town", "C", 40)
        writer.field("category", "C", 60)
        writer.field("source", "C", 40)
        count = 0

        for feat in features:
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            g_type = geom.get("type")
            coords = geom.get("coordinates") or []
            points = []
            if g_type == "Point" and len(coords) >= 2:
                points = [coords]
            elif g_type == "MultiPoint":
                points = [p for p in coords if isinstance(p, list) and len(p) >= 2]

            for pt in points:
                try:
                    x, y = float(pt[0]), float(pt[1])
                except Exception:
                    continue
                writer.point(x, y)
                writer.record(
                    safe_text(props.get("name"), 100),
                    safe_text(props.get("adcode"), 20),
                    safe_text(props.get("level"), 30),
                    safe_text(props.get("town"), 40),
                    safe_text(props.get("category"), 60),
                    safe_text(props.get("source"), 40),
                )
                count += 1

        writer.close()
        write_sidecars(shp_base)
        return count

    writer = shapefile.Writer(shp_base, shapeType=shapefile.POLYGON, encoding="utf-8")
    writer.field("name", "C", 100)
    writer.field("adcode", "C", 20)
    writer.field("level", "C", 30)
    writer.field("center", "C", 40)
    count = 0

    for feat in features:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        g_type = geom.get("type")
        coords = geom.get("coordinates") or []
        parts = []

        if g_type == "Polygon":
            for ring in coords:
                if not ring:
                    continue
                r = list(ring)
                if r[0] != r[-1]:
                    r.append(r[0])
                if len(r) >= 4:
                    parts.append(r)
        elif g_type == "MultiPolygon":
            for poly in coords:
                for ring in poly:
                    if not ring:
                        continue
                    r = list(ring)
                    if r[0] != r[-1]:
                        r.append(r[0])
                    if len(r) >= 4:
                        parts.append(r)

        if not parts:
            continue

        writer.poly(parts)
        writer.record(
            safe_text(props.get("name"), 100),
            safe_text(props.get("adcode"), 20),
            safe_text(props.get("level"), 30),
            safe_text(props.get("center"), 40),
        )
        count += 1

    writer.close()
    write_sidecars(shp_base)
    return count


def _town_centers_from_geojson(path: str) -> dict[str, tuple[float, float]]:
    if not os.path.isfile(path):
        return {}
    data = json.load(open(path, "r", encoding="utf-8"))
    out: dict[str, tuple[float, float]] = {}
    for f in data.get("features") or []:
        p = f.get("properties") or {}
        geom = f.get("geometry") or {}
        name = p.get("name")
        if not name or geom.get("type") != "Point":
            continue
        c = geom.get("coordinates") or []
        if len(c) < 2:
            continue
        try:
            out[str(name)] = (float(c[0]), float(c[1]))
        except (TypeError, ValueError):
            continue
    return out


def _district_center_from_boundary_geojson(path: str) -> tuple[float, float] | None:
    if not os.path.isfile(path):
        return None
    data = json.load(open(path, "r", encoding="utf-8"))
    for f in data.get("features") or []:
        p = f.get("properties") or {}
        if str(p.get("level", "")).lower() != "district":
            continue
        raw = p.get("center") or ""
        if "," not in raw:
            continue
        a, b = raw.split(",", 1)
        try:
            return float(a.strip()), float(b.strip())
        except ValueError:
            continue
    return None


def _spiral_offset(base_x: float, base_y: float, town_key: str, idx: int) -> tuple[float, float]:
    ang = 2 * math.pi * (idx % 24) / 24.0 + idx * 0.07
    r = 0.00055 * math.sqrt((idx // 24) + 1)
    return base_x + r * math.cos(ang), base_y + r * math.sin(ang)


def json_points_to_shp(src_path, shp_base):
    payload = json.load(open(src_path, "r", encoding="utf-8"))
    if isinstance(payload, dict):
        if "features" in payload:
            records = [(f.get("properties") or {}) for f in payload["features"]]
        elif "pois" in payload:
            records = payload["pois"]
        elif "items" in payload:
            # 如 nanhai_nonheritage_full90.json：名录在 items，多数无 lng/lat
            records = payload["items"]
        else:
            records = []
    elif isinstance(payload, list):
        records = payload
    else:
        records = []

    gis_dir = os.path.dirname(src_path)
    town_centers = _town_centers_from_geojson(
        os.path.join(gis_dir, "nanhai_towns.geojson")
    )
    district_ctr = _district_center_from_boundary_geojson(
        os.path.join(gis_dir, "nanhai_boundary.geojson")
    )
    per_town: dict[str, int] = {}

    writer = shapefile.Writer(shp_base, shapeType=shapefile.POINT, encoding="utf-8")
    writer.field("name", "C", 120)
    writer.field("town", "C", 40)
    writer.field("category", "C", 60)
    writer.field("level", "C", 20)
    writer.field("source", "C", 40)

    count = 0
    for item in records:
        if not isinstance(item, dict):
            continue
        x = y = None
        src_note = ""
        try:
            lx = item.get("lng")
            ly = item.get("lat")
            if lx not in (None, "") and ly not in (None, ""):
                x = float(lx)
                y = float(ly)
        except (TypeError, ValueError):
            x = y = None

        if x is None:
            town = str(item.get("town") or "").strip()
            base = town_centers.get(town)
            if base is None and town in ("南海区",):
                base = district_ctr
            if base is None:
                continue
            i = per_town.get(town, 0)
            per_town[town] = i + 1
            x, y = _spiral_offset(base[0], base[1], town, i)
            src_note = "镇街中心近似"
        else:
            src_note = safe_text(item.get("source"), 40) or "geocoded"

        writer.point(x, y)
        writer.record(
            safe_text(item.get("name"), 120),
            safe_text(item.get("town"), 40),
            safe_text(item.get("category"), 60),
            safe_text(item.get("level"), 20),
            safe_text(src_note, 40),
        )
        count += 1

    writer.close()
    write_sidecars(shp_base)
    return count


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    copied = []
    converted = []

    for fn in os.listdir(SRC_DIR):
        src = os.path.join(SRC_DIR, fn)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(OUT_DIR, fn)
        shutil.copy2(src, dst)
        copied.append(fn)

    for fn in copied:
        src = os.path.join(SRC_DIR, fn)
        stem = os.path.splitext(fn)[0]
        shp_base = os.path.join(OUT_DIR, stem)

        if fn.lower().endswith(".geojson"):
            n = geojson_to_shp(src, shp_base)
            converted.append((fn, stem + ".shp", n))
        elif fn.lower().endswith(".json"):
            n = json_points_to_shp(src, shp_base)
            converted.append((fn, stem + ".shp", n))

    print(f"copied: {len(copied)} files")
    for src_name, shp_name, count in converted:
        print(f"{src_name} -> {shp_name} ({count} features)")


if __name__ == "__main__":
    main()
