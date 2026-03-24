#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
古籍OCR结果整合工具
将散落的OCR页面文本合并为完整的结构化文档

研究方法：
    本脚本解决的问题是：看典古籍平台的OCR输出以"单页"为单位存储（每页一个txt+json），
    无法直接用于跨页的NLP分析（实体共现、主题模型等都需要连续文本）。
    
    处理逻辑：
    1. 从文件名提取页码数字（如 "401_换行.txt" → 页码401），按数字排序确保顺序正确
    2. 合并为两种格式：
       - 带页码标记版：插入"--- 第N页 ---"分隔符，用于分析结果溯源到原始页面
       - 连续文本版：去除分隔符，用于NLP处理
    3. 生成页码-字符偏移索引：记录每页在全文中的位置，支持后续从实体定位到原始页面
    4. 同步整理开题阶段已有的22份文化典籍MD文件，统一命名和存放路径
    5. 生成文本统计报告（文件名、字符数、行数、中文字符数）
    
    数据来源：
    - 古籍识别/b4b47661.../：看典古籍平台OCR产出的458页南海县志（含_换行.txt和.json两种格式）
    - 开题阶段/文化典籍/：22份Z-Library获取的文化典籍OCR文本（.md格式）
    
    输出结果：
    - 南海县志_OCR全文.txt：375,453字符（含页码标记）
    - 南海县志_OCR连续文本.txt：30,984行纯文本
    - 南海县志_页码索引.json：458页的字符偏移索引
    - 开题阶段典籍/：22份统一命名的典籍文本
    - 文本统计报告.json：所有文本的字符/行数统计，总计3,271,537个中文字符
"""

import os
import json
import glob
import re
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
OCR_DIR = os.path.join(PROJECT_ROOT, "古籍识别", "b4b47661-7006-426c-9e3e-0e2cca73fbdf")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "典籍文本")
CULTURE_DIR = os.path.join(PROJECT_ROOT, "开题阶段", "文化典籍")


def consolidate_ocr_pages():
    """合并所有OCR换行文本为完整文档"""
    print("=" * 60)
    print("古籍OCR结果整合")
    print("=" * 60)

    txt_files = glob.glob(os.path.join(OCR_DIR, "*_换行.txt"))
    if not txt_files:
        print("未找到OCR文本文件")
        return

    def get_page_num(filepath):
        basename = os.path.basename(filepath)
        num_str = basename.replace("_换行.txt", "")
        try:
            return int(num_str)
        except ValueError:
            return 0

    txt_files.sort(key=get_page_num)
    print(f"找到 {len(txt_files)} 页OCR文本 (页码 {get_page_num(txt_files[0])}-{get_page_num(txt_files[-1])})")

    full_text_lines = []
    page_index = []
    char_offset = 0

    for filepath in txt_files:
        page_num = get_page_num(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            continue

        page_index.append({
            "page": page_num,
            "char_offset": char_offset,
            "char_length": len(content),
            "line_count": content.count("\n") + 1,
        })

        full_text_lines.append(f"\n\n--- 第{page_num}页 ---\n\n")
        full_text_lines.append(content)
        char_offset += len(content) + len(f"\n\n--- 第{page_num}页 ---\n\n")

    full_text = "".join(full_text_lines)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_path = os.path.join(OUTPUT_DIR, "南海县志_OCR全文.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    print(f"全文已保存: {output_path} ({len(full_text)} 字符)")

    continuous_text = []
    for filepath in txt_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            lines = content.split("\n")
            continuous_text.extend(lines)

    clean_path = os.path.join(OUTPUT_DIR, "南海县志_OCR连续文本.txt")
    with open(clean_path, "w", encoding="utf-8") as f:
        f.write("\n".join(continuous_text))
    print(f"连续文本已保存: {clean_path} ({len(continuous_text)} 行)")

    index_path = os.path.join(OUTPUT_DIR, "南海县志_页码索引.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_pages": len(page_index),
            "total_chars": len(full_text),
            "source": "古籍识别OCR",
            "pages": page_index,
        }, f, ensure_ascii=False, indent=2)
    print(f"页码索引已保存: {index_path}")

    return full_text


def copy_existing_texts():
    """复制开题阶段已有的文化典籍MD文件"""
    print("\n" + "=" * 60)
    print("整理已有文化典籍文本")
    print("=" * 60)

    if not os.path.exists(CULTURE_DIR):
        print(f"未找到文化典籍目录: {CULTURE_DIR}")
        return

    md_files = glob.glob(os.path.join(CULTURE_DIR, "*.md"))
    print(f"找到 {len(md_files)} 个典籍MD文件")

    dest_dir = os.path.join(OUTPUT_DIR, "开题阶段典籍")
    os.makedirs(dest_dir, exist_ok=True)

    name_map = {
        "南海古村": "南海龙狮南海衣冠南海古村_南海古村篇",
        "南海龙狮篇": "南海龙狮南海衣冠南海古村_南海龙狮篇",
        "南海衣冠": "南海龙狮南海衣冠南海古村_南海衣冠篇",
        "佛山祖庙": "佛山祖庙",
        "佛山市志 上": "佛山市志_上",
        "佛山市志 下": "佛山市志_下",
        "南海县志": "南海县志",
        "南海市文化艺术志": "南海市文化艺术志",
        "西樵山旅游": "南海市西樵山旅游度假区志",
        "南海美食篇": "南海美食_南海美食篇",
        "南海特产篇": "南海美食_南海特产篇",
        "南海传说": "南海美食_南海传说篇",
        "佛山文史": "佛山文史资料",
        "佛山历史人物": "佛山历史人物录",
        "岭南文化": "岭南文化知识书系_佛山祖庙",
        "中枢与象征": "中枢与象征_佛山祖庙",
        "中国旅行": "中国旅行_广州佛山",
        "南海书画": "南海非遗_南海书画篇",
        "邹伯奇": "南海文史资料_邹伯奇",
        "狮舞岭南": "狮舞岭南龙腾南海",
        "佛山市博物馆": "佛山市博物馆藏绘画",
    }

    copied = 0
    for md_file in md_files:
        basename = os.path.basename(md_file)
        short_name = basename
        for key, val in name_map.items():
            if key in basename:
                short_name = val + ".md"
                break
        else:
            short_name = re.sub(r'\s*\(.*?\)', '', basename).strip()
            short_name = re.sub(r'\s+', '_', short_name)

        dest_path = os.path.join(dest_dir, short_name)
        shutil.copy2(md_file, dest_path)
        copied += 1

    print(f"已复制 {copied} 个文件到 {dest_dir}")


def generate_text_stats():
    """生成所有典籍文本的统计信息"""
    print("\n" + "=" * 60)
    print("生成文本统计报告")
    print("=" * 60)

    stats = []

    for root, dirs, files in os.walk(OUTPUT_DIR):
        for fname in files:
            if fname.endswith((".txt", ".md")):
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                stats.append({
                    "file": os.path.relpath(fpath, OUTPUT_DIR),
                    "chars": len(content),
                    "lines": content.count("\n") + 1,
                    "cjk_chars": len(re.findall(r'[\u4e00-\u9fff]', content)),
                })

    stats.sort(key=lambda x: x["cjk_chars"], reverse=True)

    report_path = os.path.join(OUTPUT_DIR, "文本统计报告.json")
    total_cjk = sum(s["cjk_chars"] for s in stats)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_files": len(stats),
            "total_cjk_chars": total_cjk,
            "files": stats,
        }, f, ensure_ascii=False, indent=2)
    print(f"统计报告已保存: {report_path}")
    print(f"共 {len(stats)} 个文件, 总计 {total_cjk} 个中文字符")


if __name__ == "__main__":
    consolidate_ocr_pages()
    copy_existing_texts()
    generate_text_stats()
    print("\n全部完成！")
