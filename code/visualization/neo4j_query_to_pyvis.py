#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
已导入 Neo4j 的数据 → 执行 Cypher → 自动生成交互式 HTML 图（无需再导 JSON）

依赖:
  pip install neo4j pyvis

连接（优先环境变量，其次命令行）:
  NEO4J_URI       默认 bolt://127.0.0.1:7687
  NEO4J_USER      默认 neo4j
  NEO4J_PASSWORD  必填之一；不设则用命令行 --password 或交互输入
  NEO4J_DATABASE  多库时指定，如 nanhaiknowledgegraph；不设则用 neo4j

示例:
  python code/visualization/neo4j_query_to_pyvis.py --preset sample
  python code/visualization/neo4j_query_to_pyvis.py --preset kang
  python code/visualization/neo4j_query_to_pyvis.py --preset renwu_cc --style neo4j -o output/figures/kg_neo4j_like.html
  python code/visualization/neo4j_query_to_pyvis.py --cypher "MATCH (a)-[r]->(b) WHERE r.relation_text='位于' RETURN a,r,b LIMIT 250"
  python code/visualization/neo4j_query_to_pyvis.py --cypher-file cypher/neo4j_merged_graph.cypher --limit 0
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", ".."))
DEFAULT_OUT = os.path.join(ROOT_DIR, "output", "figures", "neo4j_from_db.html")

# 内置常用子图（与 neo4j_full_build 导入结果一致：边上 relation_text，类型名= relation_group）
PRESETS: dict[str, str] = {
    "sample": """
        MATCH (a)-[r]->(b)
        RETURN a, r, b
        LIMIT 350
        """.strip(),
    "located": """
        MATCH (a)-[r]->(b)
        WHERE r.relation_text = '位于'
        RETURN a, r, b
        LIMIT 300
        """.strip(),
    "recorded": """
        MATCH (a)-[r:文献记载]->(b)
        RETURN a, r, b
        LIMIT 250
        """.strip(),
    "kang": """
        MATCH p = (n)-[*1..2]-(m)
        WHERE n.name = '康有为'
        RETURN p
        LIMIT 120
        """.strip(),
    "xiqiao": """
        MATCH p = (n)-[*1..2]-(m)
        WHERE n.name = '西樵山'
        RETURN p
        LIMIT 120
        """.strip(),
    "zhi": """
        MATCH (a)-[r]->(b)
        WHERE r.relation_text IN ['位于','记载','属于','出生于','著述','著有','始建于','兴盛于']
        RETURN a, r, b
        LIMIT 400
        """.strip(),
    "renwu_cc": """
        MATCH (a)-[r:人物关联]->(b)
        WHERE a.ai_type_code IN ['C1','C2','C3'] AND b.ai_type_code IN ['C1','C2','C3']
        RETURN a, r, b
        LIMIT 320
        """.strip(),
}


def _env_uri() -> str:
    return os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687").strip()


def _env_user() -> str:
    return os.environ.get("NEO4J_USER", "neo4j").strip()


def _env_password(cli_pw: str | None) -> str:
    p = (cli_pw or os.environ.get("NEO4J_PASSWORD") or "").strip()
    if p:
        return p
    import getpass

    return getpass.getpass("Neo4j 密码: ").strip()


def _env_database(cli_db: str | None) -> str | None:
    d = (cli_db or os.environ.get("NEO4J_DATABASE") or "").strip()
    return d if d else None


def _extract_first_cypher_block(text: str) -> str | None:
    """从 .cypher 文件中取第一段非注释连续行作为查询（简单场景）。"""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        if s.upper().startswith("CALL ") and "apoc." in s.lower():
            return None
        lines.append(line)
        if s.endswith(";"):
            break
    q = "\n".join(lines).strip()
    if q.endswith(";"):
        q = q[:-1].strip()
    return q if lines else None


def _node_label(node) -> str:
    try:
        labs = list(node.labels)
        return labs[0] if labs else "Node"
    except Exception:
        return "Node"


def _darken_hex(fill_hex: str, factor: float = 0.62) -> str:
    """与 neo4j grass 类似：填充色加深作描边。"""
    h = (fill_hex or "").lstrip("#")
    if len(h) != 6:
        return "#37474F"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _props_tooltip(props: dict, max_items: int = 18) -> str:
    parts = []
    for i, (k, v) in enumerate(props.items()):
        if i >= max_items:
            parts.append("…")
            break
        s = str(v)
        if len(s) > 200:
            s = s[:197] + "…"
        parts.append(f"{k}: {s}")
    return "<br>".join(html.escape(x) for x in parts)


def subgraph_from_neo4j_graph(graph) -> tuple[dict, list]:
    """neo4j.graph.Graph → ({element_id: node}, [(s,e,rel), ...])"""
    nodes: dict = {}
    edges: list = []
    if graph is None:
        return nodes, edges
    for node in graph.nodes:
        nodes[node.element_id] = node
    for rel in graph.relationships:
        try:
            s = rel.start_node.element_id
            e = rel.end_node.element_id
        except Exception:
            continue
        nodes.setdefault(s, rel.start_node)
        nodes.setdefault(e, rel.end_node)
        edges.append((s, e, rel))
    return nodes, edges


def subgraph_from_records(records: list) -> tuple[dict, list]:
    """消费完 Result 后，从 record 里抠 Node / Relationship / Path（graph() 不可用时的兜底）。"""
    from neo4j.graph import Node, Path, Relationship

    nodes: dict = {}
    edges: list = []

    def take_node(n: Node) -> None:
        nodes[n.element_id] = n

    def take_rel(r: Relationship) -> None:
        try:
            take_node(r.start_node)
            take_node(r.end_node)
            edges.append((r.start_node.element_id, r.end_node.element_id, r))
        except Exception:
            pass

    for rec in records:
        for val in rec.values():
            if isinstance(val, Node):
                take_node(val)
            elif isinstance(val, Relationship):
                take_rel(val)
            elif isinstance(val, Path):
                for n in val.nodes:
                    take_node(n)
                for r in val.relationships:
                    take_rel(r)
    return nodes, edges


def build_pyvis(
    nodes: dict,
    edges: list,
    out_path: str,
    height: str = "820px",
    style: str = "default",
) -> str:
    try:
        from pyvis.network import Network
    except ImportError:
        print("请先安装: pip install pyvis", file=sys.stderr)
        sys.exit(1)

    neo4j_like = style.strip().lower() in ("neo4j", "browser", "neo4j-like")

    if neo4j_like:
        net = Network(
            height=height or "920px",
            width="100%",
            directed=True,
            notebook=False,
            cdn_resources="remote",
            bgcolor="#e8ecf1",
            font_color="#ffffff",
        )
        net.barnes_hut(
            gravity=-8200,
            central_gravity=0.26,
            spring_length=175,
            spring_strength=0.042,
            damping=0.53,
        )
        try:
            net.options.edges.smooth.type = "continuous"
            net.options.edges.color.inherit = False
        except Exception:
            pass
    else:
        net = Network(
            height=height,
            width="100%",
            directed=True,
            notebook=False,
            cdn_resources="remote",
        )
        net.barnes_hut(
            gravity=-12000,
            central_gravity=0.35,
            spring_length=140,
            spring_strength=0.001,
            damping=0.5,
        )

    for eid, node in nodes.items():
        props = dict(node)
        name = props.get("name") or eid
        lbl = name if len(str(name)) <= 14 else str(name)[:13] + "…"
        color = props.get("color")
        tip = _props_tooltip(props) + f"<br>labels: {':'.join(node.labels)}"
        kw: dict = {"label": lbl, "title": tip}
        if neo4j_like:
            vd = props.get("viz_diameter")
            try:
                size = float(vd) * 0.42 if vd is not None else 22.0
            except (TypeError, ValueError):
                size = 22.0
            size = max(14.0, min(38.0, size))
            kw["size"] = size
            kw["font"] = {"size": 13, "color": "#ffffff", "face": "arial"}
            kw["borderWidth"] = 2
            kw["shadow"] = True
            if color:
                c = str(color).lstrip("#")
                if re.fullmatch(r"[0-9A-Fa-f]{6}", c):
                    hx = "#" + c
                    kw["color"] = {
                        "background": hx,
                        "border": _darken_hex(hx),
                        "highlight": {"background": hx, "border": "#ffffff"},
                    }
            else:
                kw["color"] = {
                    "background": "#78909c",
                    "border": "#455a64",
                    "highlight": {"background": "#90a4ae", "border": "#ffffff"},
                }
        elif color:
            c = str(color).lstrip("#")
            if re.fullmatch(r"[0-9A-Fa-f]{6}", c):
                kw["color"] = "#" + c
        net.add_node(eid, **kw)

    seen_edge: set[tuple] = set()
    for s, e, rel in edges:
        key = (s, e, getattr(rel, "element_id", id(rel)))
        if key in seen_edge:
            continue
        seen_edge.add(key)
        props = dict(rel)
        rtype = rel.type if hasattr(rel, "type") else ""
        verb = (props.get("relation_text") or "")[:10]
        lab = verb or (str(rtype)[:8] if rtype else "→")
        ev = str(props.get("evidence", ""))[:160]
        tip = html.escape(f"type: {rtype}\nrelation_text: {props.get('relation_text','')}\n{ev}")
        if neo4j_like:
            net.add_edge(
                s,
                e,
                label=lab,
                title=tip,
                arrows="to",
                color="#9aa3af",
                width=1.05,
                smooth={"type": "continuous", "roundness": 0.45},
            )
        else:
            net.add_edge(s, e, label=lab, title=tip, arrows="to")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    net.write_html(out_path, open_browser=False)
    return out_path


def run_query_to_html(
    cypher: str,
    out_path: str,
    uri: str,
    user: str,
    password: str,
    database: str | None,
    style: str = "default",
) -> None:
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("请先安装: pip install neo4j", file=sys.stderr)
        sys.exit(1)

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        if database:
            session_ctx = driver.session(database=database)
        else:
            session_ctx = driver.session()

        with session_ctx as session:
            result = session.run(cypher)
            graph = result.graph()
            records = list(result)
            nodes, edges = subgraph_from_neo4j_graph(graph)
            if not nodes and records:
                nodes, edges = subgraph_from_records(records)
    finally:
        driver.close()

    if not nodes:
        print("查询未返回任何节点。请检查：库名是否正确、Cypher 是否含 (n)-[r]-(m) 或路径 p。", file=sys.stderr)
        sys.exit(2)

    path = build_pyvis(nodes, edges, out_path, style=style)
    print(f"已写出: {path}")
    print(f"  节点 {len(nodes)} 个，边 {len(edges)} 条（去重前记录数供参考）")


def main() -> None:
    parser = argparse.ArgumentParser(description="Neo4j 已有数据 → Cypher → Pyvis HTML")
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()), help="内置子图查询")
    parser.add_argument("--cypher", type=str, help="自定义一条 Cypher（建议 RETURN 节点与关系或路径）")
    parser.add_argument(
        "--cypher-file",
        type=str,
        help="从文件读取第一段可执行 Cypher（跳过 // 与 APOC 段则失败并需改用 --cypher）",
    )
    parser.add_argument("-o", "--out", default=DEFAULT_OUT, help=f"输出 HTML，默认 {DEFAULT_OUT}")
    parser.add_argument(
        "--style",
        choices=("default", "neo4j"),
        default="default",
        help="neo4j=浅灰底+白字+描边+平滑边，观感接近 Neo4j Browser（力导向仍由 vis.js 计算）",
    )
    parser.add_argument("--uri", default=None, help="覆盖 NEO4J_URI")
    parser.add_argument("--user", default=None, help="覆盖 NEO4J_USER")
    parser.add_argument("--password", default=None, help="覆盖 NEO4J_PASSWORD")
    parser.add_argument("--database", default=None, help="覆盖 NEO4J_DATABASE（多库必填）")
    args = parser.parse_args()

    uri = (args.uri or _env_uri()).strip()
    user = (args.user or _env_user()).strip()
    password = (args.password or os.environ.get("NEO4J_PASSWORD") or "").strip()
    if not password:
        try:
            import neo4j_full_build as _nfb

            if getattr(_nfb, "PASSWORD", None):
                password = str(_nfb.PASSWORD).strip()
        except ImportError:
            pass
    if not password:
        password = _env_password(None)
    database = _env_database(args.database)
    if not database:
        try:
            import neo4j_full_build as _nfb2

            if getattr(_nfb2, "DATABASE", None):
                database = str(_nfb2.DATABASE).strip()
        except ImportError:
            pass

    cypher: str | None = None
    if args.preset:
        cypher = PRESETS[args.preset]
    elif args.cypher:
        cypher = args.cypher.strip()
    elif args.cypher_file:
        p = os.path.normpath(args.cypher_file)
        if not os.path.isfile(p):
            print(f"文件不存在: {p}", file=sys.stderr)
            sys.exit(1)
        with open(p, "r", encoding="utf-8") as f:
            raw = f.read()
        cypher = _extract_first_cypher_block(raw)
        if not cypher:
            print(
                "未能从该文件自动截取单条 Cypher；请用 --cypher 直接传查询，或编辑文件把目标查询放在文件最前且非注释。",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        parser.print_help()
        print("\n必须指定 --preset、--cypher 或 --cypher-file 之一。", file=sys.stderr)
        sys.exit(1)

    run_query_to_html(cypher, args.out, uri, user, password, database, style=args.style)


if __name__ == "__main__":
    main()
