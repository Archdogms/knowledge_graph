#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
南海文史资料PDF批量文本提取
从books目录的36本PDF中筛选30本文旅相关的，提取文本并整合到典籍数据库

研究方法：
    使用PyMuPDF(fitz)提取PDF中的文本层。南海文史资料PDF多为扫描件，
    部分Z-Library版本可能嵌入了OCR文字层。对每本PDF：
    1. 逐页提取文本 → 合并为全文
    2. 统计中文字符数 → 若>500则视为有效提取
    3. 有效文本保存到典籍目录
    4. 无法提取的记录到待OCR清单
    
    排除5本涉政/已处理的PDF：
    - 第4辑（华侨爱国爱乡统战）
    - 第7辑（抗日战争纪念）
    - 第9辑（冯乃超左翼文学/政治）
    - 第32辑（民主党派史料）
    - 第35辑（邹伯奇，已处理过）
"""

import os
import re
import json
import fitz  # PyMuPDF

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
BOOKS_DIR = os.path.join(BASE_DIR, "books")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "典籍文本", "南海文史资料")
STATS_PATH = os.path.join(BASE_DIR, "data", "典籍文本", "文本统计报告.json")

EXCLUDE_VOLUMES = {"第4辑", "第7辑", "第9辑", "第32辑", "第35辑"}


def extract_volume_number(filename):
    """从文件名提取辑号"""
    m = re.search(r'第(\d+)辑', filename)
    if m:
        return int(m.group(1))
    return 0


def extract_short_title(filename):
    """从文件名提取简短标题"""
    m = re.match(r'南海文史资料\s+第(\d+)辑\s*(.+?)\s*\(', filename)
    if m:
        vol = m.group(1)
        subtitle = m.group(2).strip()
        if subtitle:
            return f"第{vol}辑_{subtitle}"
        return f"第{vol}辑"
    m = re.match(r'南海文史资料\s+第(\d+)辑', filename)
    if m:
        return f"第{m.group(1)}辑"
    return filename[:30]


def should_exclude(filename):
    """判断是否在排除列表"""
    for vol in EXCLUDE_VOLUMES:
        if vol in filename:
            return True
    return False


def extract_text_from_pdf(pdf_path):
    """从PDF提取全部文本"""
    try:
        doc = fitz.open(pdf_path)
        all_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text and text.strip():
                all_text.append(text.strip())
        doc.close()
        return "\n\n".join(all_text)
    except Exception as e:
        print(f"    提取失败: {e}")
        return ""


def count_cjk(text):
    """统计中文字符数"""
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def main():
    print("=" * 60)
    print("南海文史资料PDF批量文本提取")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pdf_files = sorted(
        [f for f in os.listdir(BOOKS_DIR) if f.endswith(".pdf")],
        key=extract_volume_number
    )
    print(f"共找到 {len(pdf_files)} 个PDF文件")

    results = {"success": [], "failed": [], "excluded": []}

    for fname in pdf_files:
        vol_num = extract_volume_number(fname)
        short_title = extract_short_title(fname)

        if should_exclude(fname):
            print(f"  [跳过] {short_title} (排除列表)")
            results["excluded"].append({"file": fname, "title": short_title, "reason": "涉政/已处理"})
            continue

        print(f"  [处理] {short_title}...", end="", flush=True)
        pdf_path = os.path.join(BOOKS_DIR, fname)
        text = extract_text_from_pdf(pdf_path)
        cjk_count = count_cjk(text)

        if cjk_count > 500:
            out_name = f"南海文史资料_{short_title}.txt"
            out_path = os.path.join(OUTPUT_DIR, out_name)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f" {cjk_count:,} 中文字符")
            results["success"].append({
                "file": fname,
                "title": short_title,
                "output": out_name,
                "chars": len(text),
                "cjk_chars": cjk_count,
                "lines": text.count("\n") + 1,
            })
        else:
            print(f" 仅 {cjk_count} 字符 (扫描件无OCR层)")
            results["failed"].append({
                "file": fname,
                "title": short_title,
                "cjk_chars": cjk_count,
                "reason": "扫描PDF无嵌入OCR文字层",
            })

    print(f"\n{'='*60}")
    print(f"提取结果汇总:")
    print(f"  成功提取: {len(results['success'])} 本")
    print(f"  无法提取(需OCR): {len(results['failed'])} 本")
    print(f"  已排除: {len(results['excluded'])} 本")

    total_cjk = sum(r["cjk_chars"] for r in results["success"])
    print(f"  新增中文字符: {total_cjk:,}")

    if results["success"]:
        print(f"\n成功提取的文本:")
        for r in results["success"]:
            print(f"  {r['title']}: {r['cjk_chars']:>8,} 字符")

    if results["failed"]:
        print(f"\n无法提取(扫描件，需手动OCR):")
        for r in results["failed"]:
            print(f"  {r['title']}")

    report_path = os.path.join(OUTPUT_DIR, "提取报告.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n提取报告: {report_path}")

    print(f"\n--- 更新全局文本统计 ---")
    update_global_stats()

    print("\n完成！")


def update_global_stats():
    """更新全局文本统计报告"""
    text_dir = os.path.dirname(OUTPUT_DIR)
    stats = []
    for root, dirs, files in os.walk(text_dir):
        for fname in files:
            if fname.endswith((".txt", ".md")) and "统计" not in fname and "报告" not in fname:
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                cjk = count_cjk(content)
                if cjk > 100:
                    stats.append({
                        "file": os.path.relpath(fpath, text_dir),
                        "chars": len(content),
                        "lines": content.count("\n") + 1,
                        "cjk_chars": cjk,
                    })

    stats.sort(key=lambda x: x["cjk_chars"], reverse=True)
    total_cjk = sum(s["cjk_chars"] for s in stats)

    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "total_files": len(stats),
            "total_cjk_chars": total_cjk,
            "files": stats,
        }, f, ensure_ascii=False, indent=2)
    print(f"全局统计: {len(stats)} 个文件, {total_cjk:,} 个中文字符")


if __name__ == "__main__":
    main()
