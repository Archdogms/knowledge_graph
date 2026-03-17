#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复遗漏的5本典籍 + 删除废数据 + 更新统计
"""

import os
import re
import shutil
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SRC_DIR = os.path.join(os.path.dirname(BASE_DIR), "开题阶段", "文化典籍")
DST_DIR = os.path.join(BASE_DIR, "data", "典籍文本", "开题阶段典籍")

MISSING_MAPPINGS = {
    "南海龙狮篇": "南海龙狮南海衣冠南海古村_南海龙狮篇.md",
    "南海衣冠": "南海龙狮南海衣冠南海古村_南海衣冠篇.md",
    "岭南文化知识书系": "岭南文化知识书系_佛山祖庙.md",
    "中枢与象征": "中枢与象征_佛山祖庙.md",
    "南海美食南海特产南海传说 (中共": "南海美食南海特产南海传说_合辑.md",
}

TRASH_FILES = [
    os.path.join(DST_DIR, "南海县志.md"),
    os.path.join(DST_DIR, "狮舞岭南龙腾南海.md"),
]


def fix_missing():
    print("=" * 60)
    print("修复遗漏典籍 + 清理废数据")
    print("=" * 60)

    print("\n--- 补充遗漏的5本典籍 ---")
    added = 0
    for fname in os.listdir(SRC_DIR):
        if not fname.endswith(".md"):
            continue
        for keyword, target_name in MISSING_MAPPINGS.items():
            if keyword in fname:
                src = os.path.join(SRC_DIR, fname)
                dst = os.path.join(DST_DIR, target_name)
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                    sz = os.path.getsize(dst)
                    print(f"  + {target_name} ({sz:,} bytes)")
                    added += 1
                else:
                    print(f"  = {target_name} (already exists)")
                break
    print(f"补充了 {added} 本")

    print("\n--- 删除废数据 ---")
    for path in TRASH_FILES:
        if os.path.exists(path):
            os.remove(path)
            print(f"  - 删除: {os.path.basename(path)}")
        else:
            print(f"  = 不存在: {os.path.basename(path)}")

    print("\n--- 更新文本统计 ---")
    text_dir = os.path.dirname(DST_DIR)
    stats = []
    for root, dirs, files in os.walk(text_dir):
        for fname in files:
            if fname.endswith((".txt", ".md")) and fname != "文本统计报告.json":
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                cjk = len(re.findall(r'[\u4e00-\u9fff]', content))
                stats.append({
                    "file": os.path.relpath(fpath, text_dir),
                    "chars": len(content),
                    "lines": content.count("\n") + 1,
                    "cjk_chars": cjk,
                })

    stats.sort(key=lambda x: x["cjk_chars"], reverse=True)
    total_cjk = sum(s["cjk_chars"] for s in stats)

    report_path = os.path.join(text_dir, "文本统计报告.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_files": len(stats),
            "total_cjk_chars": total_cjk,
            "files": stats,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n更新后: {len(stats)} 个文件, {total_cjk:,} 个中文字符")
    print(f"统计报告: {report_path}")

    print("\n--- 当前典籍清单 ---")
    for s in stats:
        quality = "优" if s["cjk_chars"] > 50000 else ("良" if s["cjk_chars"] > 10000 else ("中" if s["cjk_chars"] > 3000 else "差"))
        print(f"  [{quality}] {s['file']}: {s['cjk_chars']:>8,} 中文字符")


if __name__ == "__main__":
    fix_missing()
