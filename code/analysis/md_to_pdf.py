#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import textwrap
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def clean_md_line(line: str) -> str:
    s = line.rstrip("\n")
    s = re.sub(r"^#{1,6}\s*", "", s)
    s = re.sub(r"^\s*-\s*", "• ", s)
    s = s.replace("`", "")
    s = s.replace("**", "")
    s = s.replace("|", " ")
    return s.strip()


def wrap_line(line: str, width: int = 48):
    if not line:
        return [""]
    return textwrap.wrap(line, width=width, break_long_words=False, break_on_hyphens=False)


def export_md_to_pdf(md_path: str, pdf_path: str):
    font_path = r"C:\Windows\Fonts\msyh.ttc"
    font_name = "MSYH"
    pdfmetrics.registerFont(TTFont(font_name, font_path))

    with open(md_path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    lines = []
    for raw in raw_lines:
        cleaned = clean_md_line(raw)
        if cleaned == "":
            lines.append("")
        else:
            lines.extend(wrap_line(cleaned))

    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    left = 50
    top = height - 60
    bottom = 50
    line_h = 20

    y = top
    c.setFont(font_name, 12)

    for ln in lines:
        if y < bottom:
            c.showPage()
            c.setFont(font_name, 12)
            y = top
        c.drawString(left, y, ln)
        y -= line_h

    c.save()


if __name__ == "__main__":
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    md_file = os.path.join(root, "docs", "tasks", "4.13_成果简报.md")
    pdf_file = os.path.join(root, "docs", "tasks", "4.13_成果简报.pdf")
    export_md_to_pdf(md_file, pdf_file)
    print(pdf_file)
