"""根据网格化结果产出 5 张核心图，用于论文正文与汇报。

输入：
  output/tables/grid_indices.csv
  output/tables/grid_town_summary.csv
  output/tables/grid_overview.json
  data/gis/nanhai_boundary.geojson
  data/gis/nanhai_towns_voronoi_approx.geojson

输出：
  output/figures/fig1_mismatch_map.png      错位热力地图（核心图）
  output/figures/fig2_category_scatter.png  文化—旅游散点图（按分层着色）
  output/figures/fig3_town_bar.png          7 镇街对比柱状图
  output/figures/fig4_density_overlay.png   文化 vs 旅游 双核密度叠加
  output/figures/fig5_jiujiang_zoom.png     九江镇专题放大图
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
import numpy as np
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
TAB = ROOT / "output" / "tables"
FIG = ROOT / "output" / "figures"
FIG.mkdir(parents=True, exist_ok=True)


plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 120


GRID_DEG = 0.0045


CAT_COLORS = {
    "沉睡潜力": "#1f77b4",
    "空心景点": "#d62728",
    "核心耦合": "#2ca02c",
    "一般地带": "#c7c7c7",
    "双低空白": "#ececec",
}


def read_cells():
    rows = []
    with (TAB / "grid_indices.csv").open("r", encoding="utf-8-sig") as f:
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
                "culture": float(r["culture"]),
                "tourism": float(r["tourism"]),
                "mismatch": float(r["mismatch"]),
                "category": r["category"],
            })
    return rows


def read_towns():
    rows = []
    with (TAB / "grid_town_summary.csv").open("r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["town"] in ("未标注", ""):
                continue
            rows.append({
                "town": r["town"],
                "grid_count": int(r["grid_count"]),
                "anchor_total": int(r["anchor_total"]),
                "poi_total": int(r["poi_total"]),
                "culture_mean": float(r["culture_mean"]),
                "tourism_mean": float(r["tourism_mean"]),
                "mismatch_mean": float(r["mismatch_mean"]),
                "n_dormant": int(r["n_dormant"]),
                "n_hollow": int(r["n_hollow"]),
                "n_core": int(r["n_core"]),
            })
    return rows


def read_geom():
    """读取南海区外边界 + 7 个镇街真实 OSM 边界。"""
    with (ROOT / "data/gis/nanhai_boundary.geojson").open("r", encoding="utf-8") as f:
        b = json.load(f)
    towns_path = ROOT / "data/gis/nanhai_towns_real.geojson"
    with towns_path.open("r", encoding="utf-8") as f:
        t = json.load(f)
    boundary = [shape(feat["geometry"]) for feat in b["features"]]
    towns = [(feat["properties"]["name"], shape(feat["geometry"])) for feat in t["features"]]
    return boundary, towns


def plot_polygon(ax, geom, **kwargs):
    """matplotlib 只认 numpy array，shapely 多边形需要展开绘制。"""
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


def fig1_mismatch_map(cells, boundary, towns):
    """
    绘图口径：以 OSM 7 个镇街的 union 作为整体轮廓，同一套几何既负责
    底色填充也负责镇界分割。只绘制 town != "未标注" 的网格，
    避免底色 / 网格 / 轮廓三者边缘对不上。
    """
    fig, ax = plt.subplots(figsize=(11, 10))

    town_union = unary_union([g for _, g in towns])
    plot_polygon(ax, town_union, color="#f3f3f3", edgecolor="none", zorder=1)

    cells_plot = [c for c in cells if c["town"] != "未标注"]

    cmap = LinearSegmentedColormap.from_list(
        "mismatch", ["#1a5fb4", "#74c0fc", "#ffffff", "#ffa8a8", "#c92a2a"], N=256
    )
    vmax = 70
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

    active = [c for c in cells_plot if c["category"] != "双低空白"]
    xs = [c["clng"] for c in active]
    ys = [c["clat"] for c in active]
    ms = [c["mismatch"] for c in active]
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

    dormant = sorted([c for c in cells_plot if c["category"] == "沉睡潜力"],
                      key=lambda x: x["mismatch"])[:5]
    hollow = sorted([c for c in cells_plot if c["category"] == "空心景点"],
                     key=lambda x: -x["mismatch"])[:5]

    for c in dormant:
        label = c["anchor_names"].split("|")[0] if c["anchor_names"] else ""
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

    cbar = plt.colorbar(sc, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label("错位值 M  =  旅游热度 − 文化厚度", fontsize=11)
    cbar.ax.text(0.5, 1.02, "空心景点\n（旅游热·文化薄）", ha="center", va="bottom",
                 transform=cbar.ax.transAxes, fontsize=9, color="#c92a2a")
    cbar.ax.text(0.5, -0.02, "沉睡潜力\n（文化厚·旅游冷）", ha="center", va="top",
                 transform=cbar.ax.transAxes, fontsize=9, color="#1a5fb4")

    ax.set_title(
        f"图 1  南海区文化—旅游错位地图（500m 网格，共 {len(cells_plot)} 格，"
        f"仅绘制非双低空白 {len(active)} 格）",
        fontsize=13, pad=12,
    )
    ax.set_xlabel("经度")
    ax.set_ylabel("纬度")
    ax.set_aspect(1.08)
    ax.grid(True, alpha=0.15)

    plt.tight_layout()
    plt.savefig(FIG / "fig1_mismatch_map.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  [√] fig1_mismatch_map.png")


def fig2_category_scatter(cells):
    fig, ax = plt.subplots(figsize=(10, 7.5))

    for c in cells:
        if c["category"] == "双低空白":
            ax.scatter(c["culture"], c["tourism"], color=CAT_COLORS[c["category"]],
                        s=5, alpha=0.12, linewidths=0, zorder=1)
    for cat in ["一般地带", "核心耦合", "沉睡潜力", "空心景点"]:
        xs = [c["culture"] for c in cells if c["category"] == cat]
        ys = [c["tourism"] for c in cells if c["category"] == cat]
        ax.scatter(xs, ys, color=CAT_COLORS[cat], s=32, alpha=0.65,
                    label=f"{cat} ({len(xs)})", linewidths=0, zorder=3)

    ax.axhline(50, color="#666", linestyle="--", linewidth=0.8, zorder=2)
    ax.axvline(50, color="#666", linestyle="--", linewidth=0.8, zorder=2)
    ax.plot([0, 100], [0, 100], color="#888", linestyle=":", linewidth=0.8, zorder=2)

    ax.text(75, 25, "空心景点区\n旅游 < 文化 反之", fontsize=9, color="#888",
             ha="center", alpha=0)
    ax.text(15, 85, "沉睡潜力区上方\n（此图中文化横轴、旅游纵轴）", fontsize=9,
             color="#888", ha="center", alpha=0)

    dormant = sorted([c for c in cells if c["category"] == "沉睡潜力"],
                      key=lambda x: x["mismatch"])[:6]
    hollow = sorted([c for c in cells if c["category"] == "空心景点"],
                     key=lambda x: -x["mismatch"])[:5]

    for c in dormant:
        label = c["anchor_names"].split("|")[0][:10] if c["anchor_names"] else c["town"]
        ax.annotate(label, (c["culture"], c["tourism"]),
                    xytext=(6, -8), textcoords="offset points",
                    fontsize=8.5, color="#1a5fb4")
    for c in hollow:
        label = f"{c['town']}"
        ax.annotate(label, (c["culture"], c["tourism"]),
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
    plt.savefig(FIG / "fig2_category_scatter.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  [√] fig2_category_scatter.png")


def fig3_town_bar(towns):
    towns_sorted = sorted(towns, key=lambda x: -x["culture_mean"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    names = [t["town"] for t in towns_sorted]
    c_means = [t["culture_mean"] for t in towns_sorted]
    t_means = [t["tourism_mean"] for t in towns_sorted]

    x = np.arange(len(names))
    w = 0.38
    ax1.bar(x - w / 2, c_means, w, label="文化厚度 C", color="#4c72b0")
    ax1.bar(x + w / 2, t_means, w, label="旅游热度 T", color="#dd8452")
    ax1.set_xticks(x)
    ax1.set_xticklabels(names, fontsize=10)
    ax1.set_ylabel("平均值（0–100）", fontsize=11)
    ax1.set_title("（a）7 个镇街的文化—旅游均值对比", fontsize=12)
    ax1.legend(loc="upper right")
    ax1.grid(True, axis="y", alpha=0.3)

    for i, (c, t) in enumerate(zip(c_means, t_means)):
        ax1.text(i - w / 2, c + 0.3, f"{c:.1f}", ha="center", fontsize=9)
        ax1.text(i + w / 2, t + 0.3, f"{t:.1f}", ha="center", fontsize=9)

    d = [t["n_dormant"] for t in towns_sorted]
    h = [t["n_hollow"] for t in towns_sorted]
    c = [t["n_core"] for t in towns_sorted]
    ax2.barh(x, d, color=CAT_COLORS["沉睡潜力"], label="沉睡潜力格数")
    ax2.barh(x, [-v for v in h], color=CAT_COLORS["空心景点"], label="空心景点格数")
    ax2.scatter(c, x, color=CAT_COLORS["核心耦合"], s=80,
                marker="*", zorder=3, label="核心耦合格数")
    ax2.axvline(0, color="#333", linewidth=0.8)
    ax2.set_yticks(x)
    ax2.set_yticklabels(names, fontsize=10)
    ax2.invert_yaxis()
    ax2.set_xlabel("网格数（左为沉睡, 右为空心）", fontsize=11)
    ax2.set_title("（b）7 个镇街的错位类型计数", fontsize=12)
    ax2.legend(loc="lower right", fontsize=9)
    ax2.grid(True, axis="x", alpha=0.3)

    for i, v in enumerate(d):
        if v > 0:
            ax2.text(v + 0.3, i, str(v), va="center", fontsize=9,
                    color=CAT_COLORS["沉睡潜力"])
    for i, v in enumerate(h):
        if v > 0:
            ax2.text(-v - 0.3, i, str(v), va="center", ha="right",
                    fontsize=9, color=CAT_COLORS["空心景点"])

    fig.suptitle("图 3  南海七镇街对比：谁有文化、谁有游客、谁错位", fontsize=14, y=1.01)
    plt.tight_layout()
    plt.savefig(FIG / "fig3_town_bar.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  [√] fig3_town_bar.png")


def fig4_density_overlay(cells, boundary, towns):
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    minx, miny = min(c["clng"] for c in cells), min(c["clat"] for c in cells)
    maxx, maxy = max(c["clng"] for c in cells), max(c["clat"] for c in cells)
    res = 120
    xs = np.linspace(minx, maxx, res)
    ys = np.linspace(miny, maxy, res)
    XX, YY = np.meshgrid(xs, ys)

    c_heat = np.zeros_like(XX)
    t_heat = np.zeros_like(XX)

    sigma = 2.5 * GRID_DEG

    for c in cells:
        if c["culture"] == 0 and c["tourism"] == 0:
            continue
        dx2 = (XX - c["clng"]) ** 2
        dy2 = (YY - c["clat"]) ** 2
        k = np.exp(-(dx2 + dy2) / (2 * sigma ** 2))
        c_heat += k * c["culture"]
        t_heat += k * c["tourism"]

    if c_heat.max() > 0:
        c_heat /= c_heat.max()
    if t_heat.max() > 0:
        t_heat /= t_heat.max()

    for ax, data, cmap, title in [
        (axes[0], c_heat, "Blues", "（a）文化厚度核密度"),
        (axes[1], t_heat, "Oranges", "（b）旅游热度核密度"),
    ]:
        for g in boundary:
            plot_polygon(ax, g, color="#fafafa", edgecolor="#666", linewidth=0.8, zorder=1)
        im = ax.contourf(XX, YY, data, levels=15, cmap=cmap, alpha=0.85, zorder=2)
        for name, g in towns:
            plot_polygon_outline(ax, g, color="#333", linewidth=1.0, zorder=3)
            cx, cy = g.centroid.x, g.centroid.y
            ax.text(cx, cy, name, fontsize=9, color="#111",
                    ha="center", va="center", zorder=4,
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                              edgecolor="none", alpha=0.7))
        ax.set_title(title, fontsize=12)
        ax.set_xlabel("经度")
        ax.set_ylabel("纬度")
        ax.set_aspect(1.08)
        plt.colorbar(im, ax=ax, shrink=0.75)

    fig.suptitle("图 4  南海区文化与旅游的空间分布：叠加看重合与错位", fontsize=14, y=1.01)
    plt.tight_layout()
    plt.savefig(FIG / "fig4_density_overlay.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  [√] fig4_density_overlay.png")


def fig5_jiujiang(cells, towns):
    jj = None
    for name, g in towns:
        if name == "九江镇":
            jj = g
            break
    if jj is None:
        print("  [!] 未找到九江镇边界，跳过图 5")
        return

    fig, ax = plt.subplots(figsize=(10, 9))

    plot_polygon(ax, jj, color="#fafafa", edgecolor="#222", linewidth=1.4, zorder=1)

    jj_cells = [c for c in cells if c["town"] == "九江镇"]

    cat_order = ["双低空白", "一般地带", "核心耦合", "沉睡潜力", "空心景点"]
    size_map = {"沉睡潜力": 48, "空心景点": 48, "核心耦合": 48,
                "一般地带": 32, "双低空白": 32}
    alpha_map = {"沉睡潜力": 0.9, "空心景点": 0.9, "核心耦合": 0.9,
                 "一般地带": 0.55, "双低空白": 0.55}

    for cat in cat_order:
        sub = [c for c in jj_cells if c["category"] == cat]
        if not sub:
            continue
        ax.scatter([c["clng"] for c in sub], [c["clat"] for c in sub],
                   color=CAT_COLORS[cat], s=size_map[cat],
                   alpha=alpha_map[cat], marker="s", linewidths=0, zorder=3)

    plot_polygon_outline(ax, jj, color="#222", linewidth=1.6, zorder=4)

    for c in jj_cells:
        if c["category"] == "沉睡潜力" and c["anchor_names"]:
            label = c["anchor_names"].split("|")[0]
            ax.annotate(label, (c["clng"], c["clat"]),
                        xytext=(6, 6), textcoords="offset points",
                        fontsize=9, color="#1a5fb4", zorder=5)
        elif c["category"] == "空心景点":
            label = f"{c['poi_count']} POI"
            ax.annotate(label, (c["clng"], c["clat"]),
                        xytext=(6, -10), textcoords="offset points",
                        fontsize=9, color="#c92a2a", zorder=5)

    n_dormant = sum(1 for c in jj_cells if c["category"] == "沉睡潜力")
    n_hollow = sum(1 for c in jj_cells if c["category"] == "空心景点")
    anchor_total = sum(c["anchor_count"] for c in jj_cells)
    poi_total = sum(c["poi_count"] for c in jj_cells)

    text = (f"九江镇统计（真实 OSM 行政边界）\n"
            f"  网格数: {len(jj_cells)}\n"
            f"  文化载体: {anchor_total} 条\n"
            f"  POI: {poi_total} 个\n"
            f"  沉睡潜力格: {n_dormant}\n"
            f"  空心景点格: {n_hollow}")
    ax.text(0.02, 0.98, text, transform=ax.transAxes, fontsize=10,
             va="top", ha="left",
             bbox=dict(boxstyle="round,pad=0.5", facecolor="white",
                       edgecolor="#888", alpha=0.9))

    handles = [
        mpatches.Patch(color=CAT_COLORS["沉睡潜力"], label="沉睡潜力"),
        mpatches.Patch(color=CAT_COLORS["空心景点"], label="空心景点"),
        mpatches.Patch(color=CAT_COLORS["核心耦合"], label="核心耦合"),
        mpatches.Patch(color=CAT_COLORS["一般地带"], label="一般地带"),
        mpatches.Patch(color=CAT_COLORS["双低空白"], label="双低空白"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=10)

    minx, miny, maxx, maxy = jj.bounds
    dx, dy = (maxx - minx) * 0.04, (maxy - miny) * 0.04
    ax.set_xlim(minx - dx, maxx + dx)
    ax.set_ylim(miny - dy, maxy + dy)

    ax.set_title("图 5  九江镇专题：真实行政边界 + 500m 网格错位分布",
                 fontsize=13, pad=10)
    ax.set_xlabel("经度")
    ax.set_ylabel("纬度")
    ax.set_aspect(1.08)
    ax.grid(True, alpha=0.2)

    plt.tight_layout()
    plt.savefig(FIG / "fig5_jiujiang_zoom.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  [√] fig5_jiujiang_zoom.png")


def main():
    print("[1/2] 读取网格结果 ...")
    cells = read_cells()
    towns_sum = read_towns()
    boundary, towns = read_geom()
    print(f"     网格 {len(cells)} 个，镇街 {len(towns_sum)} 个")

    print("[2/2] 生成五张核心图 ...")
    fig1_mismatch_map(cells, boundary, towns)
    fig2_category_scatter(cells)
    fig3_town_bar(towns_sum)
    fig4_density_overlay(cells, boundary, towns)
    fig5_jiujiang(cells, towns)

    print(f"\n所有图已生成至 {FIG}")


if __name__ == "__main__":
    main()
