"""把本次工作简报 md 渲染为 HTML：把相对图片路径改为 file:/// 绝对 URI。"""
from __future__ import annotations
import re
from pathlib import Path
import markdown

ROOT = Path(__file__).resolve().parents[2]
MD = ROOT / "docs" / "tasks" / "20260421.md"
HTML = MD.with_suffix(".html")

CSS = """
@page{size:A4;margin:14mm 14mm;}
body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;line-height:1.55;padding:0;margin:0;color:#222;font-size:12.5px;}
h1{font-size:18px;margin:0 0 10px;text-align:center;}
h2{font-size:15px;margin:10px 0 4px;page-break-after:avoid;}
h3{font-size:13px;margin:8px 0 4px;page-break-after:avoid;}
p{margin:4px 0;}
ul,ol{margin:4px 0 6px;padding-left:20px;}
li{margin:1px 0;}
img{max-width:100%;height:auto;page-break-inside:avoid;margin:4px 0;display:block;}
figure{margin:0;}
figcaption{text-align:center;font-size:11px;color:#555;margin-top:2px;}
.row{display:flex;gap:8px;align-items:flex-start;page-break-inside:avoid;}
.row>figure{flex:1;min-width:0;}
.row>figure>img{width:100%;max-height:none;}
table{border-collapse:collapse;width:auto;font-size:11.5px;margin:4px 0;page-break-inside:avoid;}
th,td{border:1px solid #999;padding:3px 9px;vertical-align:top;}
pre,code{font-family:Consolas,monospace;white-space:pre-wrap;word-break:break-word;}
h2+p,h2+ul,h2+ol,h3+p,h3+ul,h3+ol{margin-top:0;}
"""


def abs_img(match: re.Match) -> str:
    alt, src = match.group(1), match.group(2)
    if src.startswith(("http://", "https://", "file://", "data:")):
        return match.group(0)
    p = (MD.parent / src).resolve()
    uri = "file:///" + p.as_posix()
    return f"![{alt}]({uri})"


def abs_html_img(match: re.Match) -> str:
    before, src, after = match.group(1), match.group(2), match.group(3)
    if src.startswith(("http://", "https://", "file://", "data:")):
        return match.group(0)
    p = (MD.parent / src).resolve()
    uri = "file:///" + p.as_posix()
    return f'<img {before}src="{uri}"{after}>'


def main() -> None:
    md = MD.read_text(encoding="utf-8")
    md = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", abs_img, md)
    md = re.sub(r'<img ([^>]*?)src="([^"]+)"([^>]*?)>', abs_html_img, md)
    body = markdown.markdown(md, extensions=["tables", "fenced_code", "toc", "nl2br", "md_in_html"])
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        + CSS
        + "</style></head><body>"
        + body
        + "</body></html>"
    )
    HTML.write_text(html, encoding="utf-8")
    print(f"wrote {HTML} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
