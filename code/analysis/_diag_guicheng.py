"""诊断：桂城为什么不在核心耦合。打印关键阈值与桂城格子的 C/T 值分位。"""
import csv

rows = list(csv.DictReader(open("output/tables/grid_indices_kg.csv", encoding="utf-8-sig")))
c0 = sorted(float(r["culture_0hop"]) for r in rows)
c1 = sorted(float(r["culture_1hop"]) for r in rows)
t = sorted(float(r["tourism"]) for r in rows)


def pct(xs, q):
    return xs[int(q * len(xs))]


print(f"全区 grid 数 = {len(rows)}")
print(f"culture_0hop 中位 {pct(c0,.5):.3f}，P75 {pct(c0,.75):.3f}，P90 {pct(c0,.9):.3f}")
print(f"culture_1hop 中位 {pct(c1,.5):.3f}，P75 {pct(c1,.75):.3f}，P90 {pct(c1,.9):.3f}")
print(f"tourism      中位 {pct(t,.5):.3f}，P75 {pct(t,.75):.3f}，P90 {pct(t,.9):.3f}")

gc = [r for r in rows if r["town"] == "桂城街道"]
print(f"\n桂城格数 = {len(gc)}")
print(
    "桂城 category_0hop:",
    {k: sum(1 for x in gc if x["category_0hop"] == k) for k in set(r["category_0hop"] for r in gc)},
)
print(
    "桂城 category_1hop:",
    {k: sum(1 for x in gc if x["category_1hop"] == k) for k in set(r["category_1hop"] for r in gc)},
)

gc_t_hi = [r for r in gc if float(r["tourism"]) >= pct(t, 0.75)]
print(f"\n桂城 T>=P75（高旅游）格 = {len(gc_t_hi)}")
for r in gc_t_hi[:10]:
    print(
        f"  C0={float(r['culture_0hop']):.2f}  C1={float(r['culture_1hop']):.2f}  "
        f"T={float(r['tourism']):.2f}  cat0={r['category_0hop']}  cat1={r['category_1hop']}  "
        f"anchor={r['anchor_count']}"
    )

gc_sorted = sorted(gc, key=lambda r: float(r["culture_1hop"]), reverse=True)
print("\n桂城 C1 前 5：")
for r in gc_sorted[:5]:
    print(
        f"  C0={float(r['culture_0hop']):.2f}  C1={float(r['culture_1hop']):.2f}  "
        f"T={float(r['tourism']):.2f}  cat0={r['category_0hop']}  cat1={r['category_1hop']}  "
        f"anchor={r['anchor_count']}  names={r['anchor_names'][:60]}"
    )
