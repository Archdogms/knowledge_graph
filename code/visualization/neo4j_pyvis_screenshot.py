#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
对 neo4j_query_to_pyvis 生成的本地 HTML 截图（接近你在 Neo4j Browser 里看到的力导向效果）。

依赖:
  pip install playwright
  playwright install chromium

示例:
  python code/visualization/neo4j_query_to_pyvis.py --preset renwu_cc --style neo4j -o output/figures/kg_neo4j_like.html
  python code/visualization/neo4j_pyvis_screenshot.py output/figures/kg_neo4j_like.html -o output/figures/kg_neo4j_like.png --wait 16000 --scale 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Pyvis HTML → 高清 PNG（Chromium 无头截图）")
    ap.add_argument("html", help="本地 .html 绝对或相对路径")
    ap.add_argument("-o", "--out", required=True, help="输出 PNG 路径")
    ap.add_argument("--wait", type=int, default=14000, help="打开后再等待毫秒数，让力导向趋于稳定")
    ap.add_argument("--width", type=int, default=1920, help="视口宽")
    ap.add_argument("--height", type=int, default=1080, help="视口高")
    ap.add_argument("--scale", type=float, default=2.0, help="device_scale_factor，越大越清晰")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("请先: pip install playwright && playwright install chromium", file=sys.stderr)
        sys.exit(1)

    path = Path(args.html).resolve()
    if not path.is_file():
        print(f"文件不存在: {path}", file=sys.stderr)
        sys.exit(2)

    url = path.as_uri()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=args.scale,
        )
        page.goto(url, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(args.wait)
        page.screenshot(path=str(out), full_page=False)
        browser.close()

    print(f"已截图: {out.resolve()}")


if __name__ == "__main__":
    main()
