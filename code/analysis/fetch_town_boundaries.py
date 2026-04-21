"""从 OpenStreetMap Nominatim 拉取南海区 7 个镇街的真实行政边界，保存到
data/gis/nanhai_towns_real.geojson。替代此前基于 7 个质心生成的 Voronoi 近似。

Nominatim 公共服务限制约 1 request/s，脚本内置间隔。需要联网。
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "gis" / "nanhai_towns_real.geojson"

UA = "nanhai-kg-research/1.0 (academic use)"

TOWN_QUERIES = [
    ("西樵镇", "西樵镇 佛山市 南海区"),
    ("九江镇", "九江镇 佛山市 南海区"),
    ("狮山镇", "狮山镇 佛山市 南海区"),
    ("大沥镇", "大沥镇 佛山市"),
    ("桂城街道", "桂城街道 佛山市"),
    ("丹灶镇", "丹灶镇 佛山市"),
    ("里水镇", "里水镇 佛山市"),
]


def fetch_one(query: str) -> dict:
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "polygon_geojson": 1,
        "limit": 1,
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if not data:
        raise RuntimeError(f"no result for: {query}")
    return data[0]


def main() -> None:
    features = []
    for cn, q in TOWN_QUERIES:
        print(f"  拉取 {cn} ...")
        r = fetch_one(q)
        features.append({
            "type": "Feature",
            "properties": {
                "name": cn,
                "osm_id": r.get("osm_id"),
                "source": "OSM Nominatim",
                "display_name": r.get("display_name"),
            },
            "geometry": r["geojson"],
        })
        time.sleep(1.2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features},
                  f, ensure_ascii=False)
    print(f"\n已写入 {OUT}（{len(features)} 个镇街）")


if __name__ == "__main__":
    main()
