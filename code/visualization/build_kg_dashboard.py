#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
根据 merged_entities.json 与 merged_relations.json 生成「知识图谱看板」HTML。
可直接用浏览器打开，查看实体类型频次、关系类型频次、属性分布与子图预览。

用法:
  python build_kg_dashboard.py
  生成: ../../output/visualization/kg_dashboard.html
  用浏览器打开该 HTML 即可。
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output")
LLM_DIR = os.path.join(OUTPUT_DIR, "llm_extraction")
VIS_DIR = os.path.join(OUTPUT_DIR, "visualization")
DASHBOARD_PATH = os.path.join(VIS_DIR, "kg_dashboard.html")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    entities_path = os.path.join(LLM_DIR, "merged_entities.json")
    relations_path = os.path.join(LLM_DIR, "merged_relations.json")
    if not os.path.exists(entities_path) or not os.path.exists(relations_path):
        print("未找到 merged_entities.json 或 merged_relations.json，请先完成 LLM 抽取。")
        return

    data = load_json(entities_path)
    rel_data = load_json(relations_path)

    type_stats = data.get("type_stats", {})
    relation_stats = rel_data.get("relation_stats", {})
    total_entities = data.get("total", 0)
    total_relations = rel_data.get("total", 0)
    entities = data.get("entities", [])[:2000]  # 用于图与表格的样本
    relations = rel_data.get("relations", [])[:1500]  # 子图边样本

    # 用于前端的 JSON（转义后嵌入 HTML）
    type_labels = list(type_stats.keys())
    type_values = list(type_stats.values())
    rel_labels = list(relation_stats.keys())
    rel_values = list(relation_stats.values())

    # 实体样本：id, name, type, description, confidence, mentions
    entities_flat = [
        {
            "name": e.get("name", ""),
            "type": e.get("type", ""),
            "description": (e.get("description") or "")[:80],
            "confidence": e.get("confidence"),
            "mentions": e.get("mentions"),
        }
        for e in entities
    ]

    # 关系样本：source, target, relation, confidence
    relations_flat = [
        {
            "source": r.get("source", ""),
            "target": r.get("target", ""),
            "relation": r.get("relation", ""),
            "confidence": r.get("confidence"),
        }
        for r in relations
    ]

    os.makedirs(VIS_DIR, exist_ok=True)

    # 频次表格：纯 HTML，不依赖 JS，file:// 下也能看到
    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    entity_rows = "".join(
        '<tr><td>{}</td><td>{}</td></tr>'.format(esc(k), v) for k, v in sorted(type_stats.items(), key=lambda x: -x[1])
    )
    relation_rows = "".join(
        '<tr><td>{}</td><td>{}</td></tr>'.format(esc(k), v) for k, v in sorted(relation_stats.items(), key=lambda x: -x[1])
    )
    entity_sample_rows = "".join(
        '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
            esc(e.get("name", "")),
            esc(e.get("type", "")),
            esc((e.get("description") or "")[:80]),
            e.get("confidence") if e.get("confidence") is not None else "",
            e.get("mentions") if e.get("mentions") is not None else "",
        )
        for e in entities[:500]
    )

    # 前端用数据：放进独立 JSON 块，避免 </script> 等破坏页面
    payload = {
        "typeLabels": type_labels,
        "typeValues": type_values,
        "relLabels": rel_labels,
        "relValues": rel_values,
        "entitiesSample": entities_flat,
        "relationsSample": relations_flat,
    }
    data_script = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>知识图谱看板 - 实体/关系频次与属性</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    :root { --bg: #0f1419; --card: #1a2332; --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff; --border: #30363d; }
    * { box-sizing: border-box; }
    body { font-family: "Segoe UI", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 16px; }
    h1 { font-size: 1.5rem; margin: 0 0 16px 0; color: var(--text); }
    h2 { font-size: 1.1rem; margin: 16px 0 8px 0; color: var(--accent); }
    .row { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; min-width: 280px; }
    .card.wide { flex: 1; min-width: 360px; }
    .card.graph { flex: 1; min-width: 400px; height: 420px; }
    .card.props { max-height: 400px; overflow: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }
    th { color: var(--muted); font-weight: 600; }
    .meta { color: var(--muted); font-size: 12px; margin-bottom: 12px; }
    #graph { width: 100%; height: 100%; min-height: 360px; }
    #detail { font-size: 12px; white-space: pre-wrap; word-break: break-all; }
    .section-title { margin-top: 24px; }
    .chart-wrap { min-height: 220px; }
  </style>
</head>
<body>
  <h1>知识图谱看板 · 实体与关系频次 / 属性</h1>
  <p class="meta">实体总数: """ + str(total_entities) + """ · 关系总数: """ + str(total_relations) + """（下表与图为抽样）</p>

  <div class="row">
    <div class="card wide">
      <h2>实体类型频次</h2>
      <div class="chart-wrap"><canvas id="chartEntity" height="220"></canvas></div>
      <table><thead><tr><th>实体类型</th><th>数量</th></tr></thead><tbody>""" + entity_rows + """</tbody></table>
    </div>
    <div class="card wide">
      <h2>关系类型频次</h2>
      <div class="chart-wrap"><canvas id="chartRelation" height="220"></canvas></div>
      <table><thead><tr><th>关系类型</th><th>数量</th></tr></thead><tbody>""" + relation_rows + """</tbody></table>
    </div>
  </div>

  <div class="row section-title">
    <div class="card graph">
      <h2>子图预览（点击节点/边可看属性）</h2>
      <div id="graph"></div>
    </div>
    <div class="card props">
      <h2>当前选中 · 属性</h2>
      <pre id="detail">点击图中节点或边查看属性</pre>
    </div>
  </div>

  <div class="row section-title">
    <div class="card wide">
      <h2>实体样本（名称 / 类型 / 描述片段 / 置信度 / 提及次数）</h2>
      <div style="max-height: 320px; overflow: auto;">
        <table>
          <thead><tr><th>名称</th><th>类型</th><th>描述</th><th>置信度</th><th>提及</th></tr></thead>
          <tbody id="entityTable">""" + entity_sample_rows + """</tbody>
        </table>
      </div>
    </div>
  </div>

  <script type="application/json" id="dashboardData">""" + data_script + """</script>
  <script>
    function run() {
      var el = document.getElementById("dashboardData");
      if (!el) return;
      var payload;
      try { payload = JSON.parse(el.textContent); } catch (e) { return; }
      var typeLabels = payload.typeLabels || [], typeValues = payload.typeValues || [];
      var relLabels = payload.relLabels || [], relValues = payload.relValues || [];
      var entitiesSample = payload.entitiesSample || [], relationsSample = payload.relationsSample || [];

      if (typeof Chart !== "undefined") {
        try {
          new Chart(document.getElementById("chartEntity"), {
            type: "bar",
            data: { labels: typeLabels, datasets: [{ label: "数量", data: typeValues, backgroundColor: "rgba(88, 166, 255, 0.7)" }] },
            options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } }
          });
          new Chart(document.getElementById("chartRelation"), {
            type: "bar",
            data: { labels: relLabels, datasets: [{ label: "数量", data: relValues, backgroundColor: "rgba(126, 231, 135, 0.7)" }] },
            options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } }
          });
        } catch (e) {}
      }

      if (typeof vis !== "undefined" && relationsSample.length) {
        try {
          var typeColor = {
            "人物": "#4A90D9",
            "宗族姓氏": "#9013FE",
            "地名空间": "#7ED787",
            "地名": "#7ED787",
            "文物建筑": "#F5A623",
            "文物遗址": "#FF8C42",
            "建筑遗迹": "#F5A623",
            "典籍文献": "#BD10E0",
            "典籍作品": "#BD10E0",
            "非遗项目": "#D0021B",
            "非遗技艺": "#D0021B",
            "民俗礼仪": "#FF5C8A",
            "朝代年号": "#50E3C2",
            "历史事件": "#B8E986",
            "物产饮食": "#F8E71C"
          };
          var nameSet = {};
          relationsSample.forEach(function(r) { nameSet[r.source] = 1; nameSet[r.target] = 1; });
          var nameList = Object.keys(nameSet);
          var nodeMap = {};
          var nodes = new vis.DataSet(nameList.map(function(name, i) {
            nodeMap[name] = i;
            var e = entitiesSample.filter(function(x) { return x.name === name; })[0] || {};
            var typ = e.type || "";
            var color = typeColor[typ] || "#A5ABB6";
            return { id: i, label: name.length > 8 ? name.slice(0, 8) + "…" : name, title: name + (typ ? " (" + typ + ")" : ""), color: color };
          }));
          var edges = new vis.DataSet(relationsSample.map(function(r, i) {
            var sid = nodeMap[r.source], tid = nodeMap[r.target];
            if (sid == null || tid == null) return null;
            return { id: i, from: sid, to: tid, label: (r.relation || "").slice(0, 6), title: "关系: " + (r.relation || "") + " 置信度: " + (r.confidence != null ? r.confidence : ""), relation: r.relation, confidence: r.confidence, sourceName: r.source, targetName: r.target };
          }).filter(Boolean));
          var container = document.getElementById("graph");
          var detail = document.getElementById("detail");
          var net = new vis.Network(container, { nodes: nodes, edges: edges }, { nodes: { shape: "dot", font: { size: 10 } }, edges: { arrows: "to", font: { size: 9, align: "middle" } }, physics: { enabled: true, barnesHut: { avoidOverlap: 0.2 } });
          net.on("click", function(params) {
            if (params.nodes.length) {
              var name = nameList[params.nodes[0]];
              var e = entitiesSample.filter(function(x) { return x.name === name; })[0] || {};
              detail.textContent = "节点: " + name + "\\n类型: " + (e.type || "") + "\\n描述: " + (e.description || "") + "\\n置信度: " + (e.confidence != null ? e.confidence : "") + "\\n提及: " + (e.mentions != null ? e.mentions : "");
            } else if (params.edges.length) {
              var edge = edges.get(params.edges[0]);
              if (edge) detail.textContent = "边: " + (edge.sourceName || nameList[edge.from]) + " --[" + (edge.relation || edge.label) + "]--> " + (edge.targetName || nameList[edge.to]) + "\\n置信度: " + (edge.confidence != null ? edge.confidence : "");
            }
          });
        } catch (e) {}
      }
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run); else run();
  </script>
</body>
</html>"""

    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print("已生成:", os.path.abspath(DASHBOARD_PATH))
    print("用浏览器打开该文件即可查看实体/关系频次与属性。")
    if not os.path.isabs(DASHBOARD_PATH):
        print("或: file:///" + os.path.abspath(DASHBOARD_PATH).replace("\\", "/"))


if __name__ == "__main__":
    main()
