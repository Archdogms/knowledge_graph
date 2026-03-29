#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 Neo4j 按 Cypher 拉子图，导出高分辨率 PNG / SVG（matplotlib + networkx）。

不依赖 Neo4j Browser；可调 --dpi、画布尺寸。
若要与 Neo4j 里力导向观感接近，请用 neo4j_query_to_pyvis.py --style neo4j 生 HTML，
可选 neo4j_pyvis_screenshot.py 截高清 PNG。

示例:
  python code/visualization/neo4j_export_subgraph_png.py
  python code/visualization/neo4j_export_subgraph_png.py --dpi 400 --width 28 --height 21
  python code/visualization/neo4j_export_subgraph_png.py --cypher "MATCH (a)-[r]->(b) RETURN a,r,b LIMIT 200"

依赖: pip install neo4j networkx matplotlib numpy
"""

from __future__ import annotations

import argparse
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", ".."))
DEFAULT_OUT_DIR = os.path.join(ROOT_DIR, "output", "figures")

# 复用 neo4j_query_to_pyvis 的解析与连接习惯
sys.path.insert(0, BASE_DIR)
from neo4j_query_to_pyvis import (  # noqa: E402
    subgraph_from_neo4j_graph,
    subgraph_from_records,
    _env_database,
    _env_password,
    _env_uri,
    _env_user,
)

try:
    import neo4j_full_build as nfb
except ImportError:
    nfb = None

DEFAULT_CYPHER = """
MATCH (a)-[r:人物关联]->(b)
WHERE a.ai_type_code IN ['C1','C2','C3'] AND b.ai_type_code IN ['C1','C2','C3']
RETURN a, r, b
LIMIT 280
""".strip()


def _hex_color(props: dict) -> str:
    c = props.get("color")
    if not c:
        return "#64748b"
    s = str(c).strip()
    if s.startswith("#") and len(s) == 7:
        return s
    return "#64748b"


def export_png_svg(
    cypher: str,
    out_png: str,
    out_svg: str | None,
    uri: str,
    user: str,
    password: str,
    database: str | None,
    dpi: float,
    width_in: float,
    height_in: float,
    font_size: float,
    node_size: float,
) -> None:
    import numpy as np
    import networkx as nx
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("请先安装: pip install neo4j", file=sys.stderr)
        sys.exit(1)

    print("Neo4j 查询中…", flush=True)
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        ctx = driver.session(database=database) if database else driver.session()
        with ctx as session:
            result = session.run(cypher)
            graph = result.graph()
            records = list(result)
            nodes, edges = subgraph_from_neo4j_graph(graph)
            if not nodes and records:
                nodes, edges = subgraph_from_records(records)
    finally:
        driver.close()

    if not nodes:
        print("查询未返回节点，未生成图片。", file=sys.stderr)
        sys.exit(2)

    G = nx.DiGraph()
    labels: dict = {}
    for eid, node in nodes.items():
        G.add_node(eid)
        props = dict(node)
        name = props.get("name") or str(eid)
        sn = str(name)
        labels[eid] = sn if len(sn) <= 12 else sn[:11] + "…"

    seen: set[tuple] = set()
    for s, e, rel in edges:
        key = (s, e, getattr(rel, "element_id", id(rel)))
        if key in seen:
            continue
        seen.add(key)
        G.add_edge(s, e)

    order = list(G.nodes())
    colors = [_hex_color(dict(nodes[eid])) for eid in order]

    print(f"布局 {len(G)} 个节点…", flush=True)
    n = max(len(G), 1)
    k = 2.8 / (n ** 0.5)
    it = 28 if n > 180 else 72
    pos = nx.spring_layout(G, seed=42, k=k, iterations=it)

    # 输出像素 ≈ width_in * dpi × height_in * dpi（由 savefig 的 dpi 决定）
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")

    nx.draw_networkx_edges(
        G,
        pos,
        ax=ax,
        edge_color="#94a3b8",
        arrows=True,
        arrowsize=14,
        width=0.55,
        alpha=0.88,
        connectionstyle="arc3,rad=0.06",
    )
    nx.draw_networkx_nodes(
        G,
        pos,
        ax=ax,
        nodelist=order,
        node_color=colors,
        node_size=node_size,
        alpha=0.95,
        linewidths=0.6,
        edgecolors="#1e293b",
    )
    nx.draw_networkx_labels(
        G,
        pos,
        labels,
        ax=ax,
        font_size=font_size,
        font_family="Microsoft YaHei",
    )
    ax.axis("off")
    ax.margins(0.14)
    plt.tight_layout()

    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    print("写入 PNG…", flush=True)
    fig.savefig(
        out_png,
        dpi=dpi,
        bbox_inches="tight",
        facecolor="#f8fafc",
        pad_inches=0.25,
    )
    if out_svg:
        print("写入 SVG（节点多时会较慢）…", flush=True)
        fig.savefig(
            out_svg,
            format="svg",
            bbox_inches="tight",
            facecolor="#f8fafc",
            pad_inches=0.25,
        )
    plt.close(fig)

    print(f"已导出 PNG: {out_png}  （dpi={dpi}, 画布约 {width_in}\"×{height_in}\"）")
    if out_svg:
        print(f"已导出 SVG: {out_svg}")
    print(f"  节点 {len(nodes)}，有向边 {G.number_of_edges()}")


def main() -> None:
    p = argparse.ArgumentParser(description="Neo4j 子图 → 高清 PNG/SVG")
    p.add_argument("--cypher", default=None, help="Cypher；默认人物关联+C1C2C3+LIMIT 500")
    p.add_argument("-o", "--out", default=None, help="输出 PNG 路径")
    p.add_argument("--svg", default=None, help="同时写 SVG 路径（矢量，可无损缩放）")
    p.add_argument("--dpi", type=float, default=300.0, help="PNG 输出 dpi，默认 300")
    p.add_argument("--width", type=float, default=14.0, help="图宽（英寸），默认 14")
    p.add_argument("--height", type=float, default=10.5, help="图高（英寸），默认 10.5")
    p.add_argument("--font-size", type=float, default=7.0, help="节点名字号")
    p.add_argument("--node-size", type=float, default=180.0, help="节点圆点面积参数（matplotlib）")
    p.add_argument("--uri", default=None)
    p.add_argument("--user", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--database", default=None)
    args = p.parse_args()

    uri = (args.uri or _env_uri()).strip()
    user = (args.user or _env_user()).strip()
    pw = (args.password or os.environ.get("NEO4J_PASSWORD") or "").strip()
    if not pw and nfb is not None and getattr(nfb, "PASSWORD", None):
        pw = str(nfb.PASSWORD).strip()
    if not pw:
        pw = _env_password(None)
    db = _env_database(args.database)
    if not db and nfb is not None and getattr(nfb, "DATABASE", None):
        db = str(nfb.DATABASE).strip()

    cypher = (args.cypher or DEFAULT_CYPHER).strip()
    out_png = args.out or os.path.join(
        DEFAULT_OUT_DIR, "neo4j_人物关联_C1C2C3_300dpi.png"
    )
    out_svg = args.svg

    export_png_svg(
        cypher,
        out_png,
        out_svg,
        uri,
        user,
        pw,
        db,
        dpi=args.dpi,
        width_in=args.width,
        height_in=args.height,
        font_size=args.font_size,
        node_size=args.node_size,
    )


if __name__ == "__main__":
    main()
