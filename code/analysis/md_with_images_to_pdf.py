#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import textwrap
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
FONT_NAME = "MSYH"

PAGE_W, PAGE_H = A4
LEFT = 50
RIGHT = 50
TOP = PAGE_H - 50
BOTTOM = 55
CONTENT_W = PAGE_W - LEFT - RIGHT


def char_width(text, font_size):
    w = 0
    for ch in text:
        if ord(ch) > 0x2E7F:
            w += font_size
        else:
            w += font_size * 0.55
    return w


def wrap_text(text, font_size, max_w):
    lines = []
    buf = ""
    for ch in text:
        buf += ch
        if char_width(buf, font_size) > max_w:
            lines.append(buf[:-1])
            buf = ch
    if buf:
        lines.append(buf)
    return lines


def clean_md(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    return text.replace("`", "")


def parse_md(md_path):
    items = []
    with open(md_path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    i = 0
    while i < len(raw_lines):
        line = raw_lines[i].rstrip("\n")
        stripped = line.strip()

        if not stripped:
            items.append(("blank", ""))
            i += 1
            continue

        img = re.match(r"!\[.*?\]\((.*?)\)", stripped)
        if img:
            items.append(("image", img.group(1)))
            i += 1
            continue

        if stripped.startswith("# "):
            items.append(("h1", clean_md(stripped[2:])))
            i += 1
            continue
        if stripped.startswith("## "):
            items.append(("h2", clean_md(stripped[3:])))
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(raw_lines):
            table_lines = []
            while i < len(raw_lines) and raw_lines[i].strip().startswith("|"):
                table_lines.append(raw_lines[i].strip())
                i += 1
            header = [c.strip() for c in table_lines[0].split("|")[1:-1]]
            rows = []
            for tl in table_lines[2:]:
                rows.append([clean_md(c.strip()) for c in tl.split("|")[1:-1]])
            items.append(("table", (header, rows)))
            continue

        if stripped.startswith("- "):
            items.append(("bullet", clean_md(stripped[2:])))
            i += 1
            continue
        if stripped.startswith("> "):
            items.append(("quote", clean_md(stripped[2:])))
            i += 1
            continue

        items.append(("text", clean_md(stripped)))
        i += 1

    return items


def draw_table(c, header, rows, x, y, font_name):
    n_cols = len(header)
    col_w = CONTENT_W / n_cols
    row_h = 20
    fs = 9

    c.setFont(font_name, fs)
    c.setFillGray(0.9)
    c.rect(x, y - row_h, CONTENT_W, row_h, fill=True, stroke=False)
    c.setFillGray(0)
    for ci, h in enumerate(header):
        c.drawString(x + ci * col_w + 4, y - row_h + 5, h)
    y -= row_h

    for row in rows:
        c.setStrokeGray(0.8)
        c.line(x, y, x + CONTENT_W, y)
        for ci, cell in enumerate(row):
            c.drawString(x + ci * col_w + 4, y - row_h + 5, cell[:int(col_w / (fs * 0.55))])
        y -= row_h

    return y - 6


def main(md_path, pdf_path):
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
    items = parse_md(md_path)
    md_dir = os.path.dirname(md_path)

    c = canvas.Canvas(pdf_path, pagesize=A4)
    y = TOP

    def ensure_space(need):
        nonlocal y
        if y - need < BOTTOM:
            c.showPage()
            y = TOP

    for kind, val in items:
        if kind == "blank":
            y -= 8
            continue

        if kind == "h1":
            ensure_space(36)
            c.setFont(FONT_NAME, 17)
            c.drawString(LEFT, y, val)
            y -= 30
            continue

        if kind == "h2":
            ensure_space(28)
            c.setFont(FONT_NAME, 13)
            c.drawString(LEFT, y, val)
            y -= 22
            continue

        if kind in ("text", "bullet", "quote"):
            fs = 10.5
            indent = 0
            prefix = ""
            if kind == "bullet":
                prefix = "· "
                indent = 10
            elif kind == "quote":
                prefix = ""
                fs = 10
            full = prefix + val
            wrapped = wrap_text(full, fs, CONTENT_W - indent)
            for wl in wrapped:
                ensure_space(18)
                c.setFont(FONT_NAME, fs)
                if kind == "quote":
                    c.setFillGray(0.35)
                else:
                    c.setFillGray(0)
                c.drawString(LEFT + indent, y, wl)
                c.setFillGray(0)
                y -= 16
            y -= 2
            continue

        if kind == "table":
            header, rows = val
            need = (len(rows) + 2) * 20
            ensure_space(min(need, 200))
            y = draw_table(c, header, rows, LEFT, y, FONT_NAME)
            continue

        if kind == "image":
            img_path = os.path.normpath(os.path.join(md_dir, val))
            if not os.path.exists(img_path):
                ensure_space(18)
                c.setFont(FONT_NAME, 10)
                c.drawString(LEFT, y, f"[图片缺失] {val}")
                y -= 16
                continue

            img = ImageReader(img_path)
            iw, ih = img.getSize()
            max_h = 300
            scale = min(CONTENT_W / iw, max_h / ih)
            dw = iw * scale
            dh = ih * scale

            ensure_space(dh + 12)
            c.drawImage(img_path, LEFT, y - dh, width=dw, height=dh,
                        preserveAspectRatio=True, mask="auto")
            y -= (dh + 12)

    c.save()
    size_kb = os.path.getsize(pdf_path) / 1024
    print(f"PDF saved: {pdf_path} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        md_file = sys.argv[1]
        pdf_file = sys.argv[2]
    else:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        md_file = os.path.join(root, "docs", "tasks", "4.13_成果图文简报.md")
        pdf_file = os.path.join(root, "docs", "tasks", "4.13_成果图文简报.pdf")
    main(md_file, pdf_file)
