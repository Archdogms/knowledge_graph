#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
高德镇街级 polyline 常为空；用区级 adcode 二次查询会得到与全区相同的几何。
本脚本：南海区行政面 + 各镇街中心点 → Voronoi 剖分并裁剪到区界内，
得到「可制图、各镇街互斥」的面数据。

重要：这是几何近似，仅用于可视化 / 镇街尺度制图，不可替代官方行政区划界线。
"""

from __future__ import annotations

import os
import shutil

import geopandas as gpd
from shapely.validation import make_valid

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DATA_GIS = os.path.join(ROOT, "data", "gis")
OUT_GIS = os.path.join(ROOT, "output", "gis")
# 南海区适宜用 WGS84 UTM 49N 做平面 Voronoi，减轻经纬度畸变
WORK_CRS = "EPSG:32649"


def load_district_polygon(boundary_path: str):
    gdf = gpd.read_file(boundary_path)
    gdf = gdf.to_crs(4326)
    if "level" in gdf.columns:
        row = gdf[gdf["level"].astype(str).str.lower() == "district"]
        if len(row) == 1:
            return row.geometry.iloc[0]
    return gdf.union_all()


def main():
    boundary_fp = os.path.join(DATA_GIS, "nanhai_boundary.geojson")
    towns_fp = os.path.join(DATA_GIS, "nanhai_towns.geojson")
    if not os.path.isfile(boundary_fp) or not os.path.isfile(towns_fp):
        raise SystemExit(f"缺少输入: {boundary_fp} 或 {towns_fp}")

    district_geom = make_valid(load_district_polygon(boundary_fp))

    towns = gpd.read_file(towns_fp).to_crs(4326)
    if len(towns) < 2:
        raise SystemExit("镇街中心点不足 2 个，无法做 Voronoi")

    towns_r = towns.copy().reset_index(drop=True)
    district_proj = (
        gpd.GeoSeries([district_geom], crs=4326).to_crs(WORK_CRS).iloc[0]
    )
    district_proj = make_valid(district_proj)
    # 在投影坐标下取质心，再做点剖分（避免在 WGS84 上对 Polygon 求 centroid 的告警）
    centroids_proj = towns_r.to_crs(WORK_CRS).geometry.centroid
    pts_proj = gpd.GeoDataFrame(
        towns_r.drop(columns=["geometry"]), geometry=centroids_proj, crs=WORK_CRS
    )

    try:
        vor = pts_proj.geometry.voronoi_polygons(extend_to=district_proj.envelope)
    except TypeError:
        vor = pts_proj.geometry.voronoi_polygons()

    named_rows = []
    for i in range(len(pts_proj)):
        r = towns_r.iloc[i]
        cell = vor.iloc[i]
        poly_proj = make_valid(cell.intersection(district_proj))
        if poly_proj.is_empty:
            continue
        poly4326 = gpd.GeoSeries([poly_proj], crs=WORK_CRS).to_crs(4326).iloc[0]
        named_rows.append(
            {
                "name": r.get("name", ""),
                "adcode": str(r.get("adcode", "")),
                "level": str(r.get("level", "street")),
                "boundary_type": "Voronoi近似(镇街中心点裁剪至区界，非官方界线)",
                "geometry": poly4326,
            }
        )

    out_gdf = gpd.GeoDataFrame(named_rows, crs=4326)
    os.makedirs(DATA_GIS, exist_ok=True)
    os.makedirs(OUT_GIS, exist_ok=True)

    stem = "nanhai_towns_voronoi_approx"
    geo_path = os.path.join(OUT_GIS, f"{stem}.geojson")
    out_gdf.to_file(geo_path, driver="GeoJSON", encoding="utf-8")
    shutil.copy2(geo_path, os.path.join(DATA_GIS, f"{stem}.geojson"))

    # 必须带 .shp；若曾误生成同名目录，会与 OGR 写入冲突并报 WinError 5
    shp_path = os.path.join(OUT_GIS, f"{stem}.shp")
    out_gdf.to_file(shp_path, driver="ESRI Shapefile", encoding="utf-8")

    print(f"Wrote {geo_path}")
    print(f"Wrote {shp_path} (+ .shx/.dbf/.prj 等)")
    print(f"Also copied geojson -> data/gis/{stem}.geojson")


if __name__ == "__main__":
    main()
