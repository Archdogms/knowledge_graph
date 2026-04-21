"""基于 grid_indices_kg.csv 产出两版错位地图 + 1 跳散点图。

输出：
  output/figures/fig1_mismatch_0hop.png
  output/figures/fig1_mismatch_1hop.png
  output/figures/fig2_category_scatter.png  （1 跳口径，与简报口径一致）
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
TAB = ROOT / "output" / "tables"
FIG = ROOT / "output" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 120


def read_cells_kg():
    rows = []
    with (TAB / "grid_indices_kg.csv").open("r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "ix": int(r["ix"]),
                "iy": int(r["iy"]),
                "clng": float(r["clng"]),
                "clat": float(r["clat"]),
                "town": r["town"],
                "anchor_count": int(r["anchor_count"] or 0),
                "anchor_names": r["anchor_names"],
                "poi_count": int(r["poi_count"] or 0),
                "n_entity_0hop": int(r["n_entity_0hop"] or 0),
                "n_entity_1hop": int(r["n_entity_1hop"] or 0),
                "culture_0hop": float(r["culture_0hop"]),
                "culture_1hop": float(r["culture_1hop"]),
                "tourism": float(r["tourism"]),
                "mismatch_0hop": float(r["mismatch_0hop"]),
                "mismatch_1hop": float(r["mismatch_1hop"]),
                "category_0hop": r["category_0hop"],
                "category_1hop": r["category_1hop"],
            })
    return rows


def read_geom():
    towns_path = ROOT / "data/gis/nanhai_towns_real.geojson"
    with towns_path.open("r", encoding="utf-8") as f:
        t = json.load(f)
    towns = [(feat["properties"]["name"], shape(feat["geometry"])) for feat in t["features"]]
    return towns


def plot_polygon(ax, geom, **kwargs):
    if geom.geom_type == "Polygon":
        x, y = geom.exterior.coords.xy
        ax.fill(x, y, **kwargs)
    elif geom.geom_type == "MultiPolygon":
        for g in geom.geoms:
            x, y = g.exterior.coords.xy
            ax.fill(x, y, **kwargs)


def plot_polygon_outline(ax, geom, **kwargs):
    if geom.geom_type == "Polygon":
        x, y = geom.exterior.coords.xy
        ax.plot(x, y, **kwargs)
    elif geom.geom_type == "MultiPolygon":
        for g in geom.geoms:
            x, y = g.exterior.coords.xy
            ax.plot(x, y, **kwargs)


def draw_one(cells, towns, hop: int, out_name: str):
    """hop in {0, 1}。"""
    m_key = f"mismatch_{hop}hop"
    c_key = f"culture_{hop}hop"
    cat_key = f"category_{hop}hop"
    n_ent_key = f"n_entity_{hop}hop"

    fig, ax = plt.subplots(figsize=(11, 10))

    town_union = unary_union([g for _, g in towns])
    plot_polygon(ax, town_union, color="#f3f3f3", edgecolor="none", zorder=1)

    cells_plot = [c for c in cells if c["town"] != "未标注"]

    cmap = LinearSegmentedColormap.from_list(
        "mismatch", ["#1a5fb4", "#74c0fc", "#ffffff", "#ffa8a8", "#c92a2a"], N=256
    )
    vmax = 70
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

    active = [c for c in cells_plot if c[cat_key] != "双低空白"]
    xs = [c["clng"] for c in active]
    ys = [c["clat"] for c in active]
    ms = [c[m_key] for c in active]
    sc = ax.scatter(xs, ys, c=ms, cmap=cmap, norm=norm, marker="s",
                    s=36, alpha=0.9, linewidths=0, zorder=3)

    for name, g in towns:
        plot_polygon_outline(ax, g, color="#444", linewidth=0.9, zorder=4)
    plot_polygon_outline(ax, town_union, color="#111", linewidth=1.6, zorder=5)

    for name, g in towns:
        cx, cy = g.centroid.x, g.centroid.y
        ax.text(cx, cy, name, fontsize=11, color="#111", ha="center", va="center",
                fontweight="bold", zorder=6,
                bbox=dict(boxstyle="round,pad=0.18", facecolor="white",
                          edgecolor="none", alpha=0.75))

    dormant = sorted([c for c in cells_plot if c[cat_key] == "沉睡潜力"],
                     key=lambda x: x[m_key])[:5]
    hollow = sorted([c for c in cells_plot if c[cat_key] == "空心景点"],
                    key=lambda x: -x[m_key])[:5]
    core = [c for c in cells_plot if c[cat_key] == "核心耦合"]

    for c in dormant:
        label = c["anchor_names"].split("|")[0] if c["anchor_names"] else f"{c[n_ent_key]}ent"
        if label:
            ax.annotate(label, (c["clng"], c["clat"]),
                        xytext=(10, 10), textcoords="offset points",
                        fontsize=9, color="#1a5fb4",
                        arrowprops=dict(arrowstyle="-", color="#1a5fb4", lw=0.6),
                        zorder=7)
    for c in hollow:
        label = f"{c['town']}·{c['poi_count']}POI"
        ax.annotate(label, (c["clng"], c["clat"]),
                    xytext=(10, -12), textcoords="offset points",
                    fontsize=9, color="#c92a2a",
                    arrowprops=dict(arrowstyle="-", color="#c92a2a", lw=0.6),
                    zorder=7)
    for c in core:
        ax.scatter([c["clng"]], [c["clat"]], marker="*", s=220,
                   facecolor="#2ca02c", edgecolor="#0c5c18", linewidth=1.2, zorder=8)
        ax.annotate("核心耦合", (c["clng"], c["clat"]),
                    xytext=(12, 12), textcoords="offset points",
                    fontsize=9, color="#0c5c18", fontweight="bold",
                    arrowprops=dict(arrowstyle="-", color="#2ca02c", lw=0.6),
                    zorder=9)

    cbar = plt.colorbar(sc, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label(f"错位值 M = T − C（{hop} 跳口径）", fontsize=11)
    cbar.ax.text(0.5, 1.02, "空心景点\n（旅游热·文化薄）", ha="center", va="bottom",
                 transform=cbar.ax.transAxes, fontsize=9, color="#c92a2a")
    cbar.ax.text(0.5, -0.02, "沉睡潜力\n（文化厚·旅游冷）", ha="center", va="top",
                 transform=cbar.ax.transAxes, fontsize=9, color="#1a5fb4")

    n_dormant = sum(1 for c in cells_plot if c[cat_key] == "沉睡潜力")
    n_hollow = sum(1 for c in cells_plot if c[cat_key] == "空心景点")
    n_core = sum(1 for c in cells_plot if c[cat_key] == "核心耦合")
    title_hop = "0 跳种子实体" if hop == 0 else "1 跳扩展实体"
    ax.set_title(
        f"图 1-{hop}hop  基于知识图谱（{title_hop}）重算的文化—旅游错位地图\n"
        f"区内 {len(cells_plot)} 格，绘点 {len(active)} 格；"
        f"沉睡 {n_dormant}、空心 {n_hollow}、核心耦合 {n_core}",
        fontsize=12, pad=12,
    )
    ax.set_xlabel("经度")
    ax.set_ylabel("纬度")
    ax.set_aspect(1.08)
    ax.grid(True, alpha=0.15)

    plt.tight_layout()
    plt.savefig(FIG / out_name, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [√] {out_name}")


CAT_COLORS = {
    "沉睡潜力": "#1f77b4",
    "空心景点": "#d62728",
    "核心耦合": "#2ca02c",
    "一般地带": "#c7c7c7",
    "双低空白": "#ececec",
}


def draw_scatter_1hop(cells, out_name: str = "fig2_category_scatter.png") -> None:
    """1 跳口径的文化—旅游散点图。风格与原 make_figures.py fig2 一致，仅换为 1 跳数据。"""
    fig, ax = plt.subplots(figsize=(10, 7.5))

    for c in cells:
        if c["category_1hop"] == "双低空白":
            ax.scatter(c["culture_1hop"], c["tourism"],
                       color=CAT_COLORS["双低空白"], s=5, alpha=0.12,
                       linewidths=0, zorder=1)
    for cat in ["一般地带", "核心耦合", "沉睡潜力", "空心景点"]:
        xs = [c["culture_1hop"] for c in cells if c["category_1hop"] == cat]
        ys = [c["tourism"] for c in cells if c["category_1hop"] == cat]
        ax.scatter(xs, ys, color=CAT_COLORS[cat], s=32, alpha=0.65,
                   label=f"{cat} ({len(xs)})", linewidths=0, zorder=3)

    ax.axhline(50, color="#666", linestyle="--", linewidth=0.8, zorder=2)
    ax.axvline(50, color="#666", linestyle="--", linewidth=0.8, zorder=2)
    ax.plot([0, 100], [0, 100], color="#888", linestyle=":", linewidth=0.8, zorder=2)

    dormant = sorted([c for c in cells if c["category_1hop"] == "沉睡潜力"],
                     key=lambda x: x["mismatch_1hop"])[:6]
    hollow = sorted([c for c in cells if c["category_1hop"] == "空心景点"],
                    key=lambda x: -x["mismatch_1hop"])[:5]

    for c in dormant:
        label = c["anchor_names"].split("|")[0][:10] if c["anchor_names"] else c["town"]
        ax.annotate(label, (c["culture_1hop"], c["tourism"]),
                    xytext=(6, -8), textcoords="offset points",
                    fontsize=8.5, color="#1a5fb4")
    for c in hollow:
        ax.annotate(c["town"], (c["culture_1hop"], c["tourism"]),
                    xytext=(-8, 6), textcoords="offset points",
                    fontsize=8.5, color="#c92a2a")

    ax.set_xlim(-3, 100)
    ax.set_ylim(-3, 85)
    ax.set_xlabel("文化厚度 C（典籍提及 + 官方认证综合得分）", fontsize=11)
    ax.set_ylabel("旅游热度 T（POI 数量 + 评分 + 评论综合得分）", fontsize=11)
    ax.set_title(f"图 2  {len(cells):,} 个网格的文化—旅游分布", fontsize=14, pad=12)
    ax.legend(loc="lower right", fontsize=10, framealpha=0.9)
    ax.grid(True, alpha=0.2)

    plt.tight_layout()
    plt.savefig(FIG / out_name, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [√] {out_name}")


def main():
    print("[1/3] 读取 grid_indices_kg.csv ...")
    cells = read_cells_kg()
    print(f"     共 {len(cells)} 格")

    print("[2/3] 读取 7 个 OSM 镇街边界 ...")
    towns = read_geom()

    print("[3/3] 绘制 0 跳 / 1 跳错位地图 + 1 跳散点 ...")
    draw_one(cells, towns, hop=0, out_name="fig1_mismatch_0hop.png")
    draw_one(cells, towns, hop=1, out_name="fig1_mismatch_1hop.png")
    draw_scatter_1hop(cells, out_name="fig2_category_scatter.png")
    print("完成")


if __name__ == "__main__":
    main()
