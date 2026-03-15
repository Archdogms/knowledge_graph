#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LLM 智能实体/关系抽取流水线 v2

使用 Ollama + Qwen3.5 本地大模型，从典籍文本中抽取文化实体和语义关系。

特性：
  - 9 类实体 + 15 类关系，覆盖南海区文旅融合研究全域
  - 同一对实体支持多种关系（多重关系），每条关系附原文依据
  - 断点续跑: 每片段实时存盘，断电重启后自动跳过已完成片段
  - 双层进度条: 文件级 + 片段级（tqdm）
  - --reset 清空全部旧结果重新开始
  - --demo  先跑3篇×2000字预览效果

用法：
  python llm_ner.py --demo             # DEMO 预览
  python llm_ner.py --reset            # 清空旧结果，全量重跑
  python llm_ner.py                    # 断点续跑
  python llm_ner.py --merge-only       # 仅合并已有结果
"""

import os
import re
import json
import time
import shutil
import argparse
import hashlib
from datetime import datetime
from collections import Counter, defaultdict

try:
    from tqdm import tqdm
except ImportError:
    print("请安装 tqdm: pip install tqdm")
    exit(1)

import requests

# ════════════════════ 路径配置 ════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Colab/单包: data、output 在仓库根下; 原项目: 在 ../../data, ../../output
_DATA_ROOT = os.path.join(BASE_DIR, "data")
_OUTPUT_ROOT = os.path.join(BASE_DIR, "output")
if os.path.isdir(_DATA_ROOT):
    DATA_DIR = _DATA_ROOT
    OUTPUT_DIR = os.path.join(_OUTPUT_ROOT, "llm_extraction")
else:
    DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
    OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output", "llm_extraction")
CORPUS_DIR = os.path.join(DATA_DIR, "corpus")
DB_DIR = os.path.join(DATA_DIR, "database")
ENTITY_DIR = os.path.join(OUTPUT_DIR, "entities")
RELATION_DIR = os.path.join(OUTPUT_DIR, "relations")
PROGRESS_PATH = os.path.join(OUTPUT_DIR, "progress.json")
LOG_PATH = os.path.join(OUTPUT_DIR, "extraction_log.log")

# ════════════════════ Ollama 配置 ════════════════════

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
#MODEL_NAME = "qwen3.5:9b"
MODEL_NAME = "qwen3:8b"
#MODEL_NAME = "qwen2.5:7b"
CHUNK_SIZE = 500   # 500~600 更稳，800 易慢/超时
CHUNK_OVERLAP = 50

def _update_config(model=None, chunk_size=None):
    global MODEL_NAME, CHUNK_SIZE
    if model:
        MODEL_NAME = model
    if chunk_size:
        CHUNK_SIZE = chunk_size

# ════════════════════ 文化锚点 ════════════════════

ANCHOR_NAMES = set()

def load_anchors():
    global ANCHOR_NAMES
    anchor_path = os.path.join(DB_DIR, "cultural_anchors.json")
    if os.path.exists(anchor_path):
        with open(anchor_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ANCHOR_NAMES = {a["name"] for a in data.get("anchors", [])}
    print(f"文化锚点: {len(ANCHOR_NAMES)} 条")

# ════════════════════ 实体/关系类型定义 ════════════════════

VALID_ENTITY_TYPES = {
    "人物", "建筑遗迹", "地名", "朝代年号",
    "非遗技艺", "历史事件", "典籍作品", "物产饮食", "宗族姓氏",
}

VALID_RELATION_TYPES = {
    "创建修建", "出生于", "活动于", "著有", "位于",
    "始建于", "承载文化", "传承于", "记载于", "属于时期",
    "发生于", "盛产", "关联人物", "同族", "同类",
}

# ════════════════════ Prompt 模板 ════════════════════

ENTITY_SYSTEM_PROMPT = """\
# 角色
你是佛山市南海区文化遗产与旅游研究领域的资深专家，精通岭南文化、南海地方志、非物质文化遗产。

# 任务
从给定的南海区文史资料文本中，精确提取与南海区文化、历史、旅游相关的实体。

# 实体类型定义（共9类，必须严格归入其中之一）

| 类型 | 定义 | 正确示例 | 错误示例（不提取） |
|------|------|----------|-------------------|
| 人物 | 与南海/佛山相关的历史人物、文化名人、工匠、官员、文学家、武术家 | 康有为、陈启沅、黄飞鸿、朱次琦、詹天佑、邹伯奇 | 现代普通人名、机构名称 |
| 建筑遗迹 | 祠堂、庙宇、塔、桥、故居、书院、亭阁、遗址、碑刻等传统建筑或遗迹 | 云泉仙馆、绮亭陈公祠、奎光楼、宝峰寺、康有为故居 | 现代商场、写字楼 |
| 地名 | 南海区内的村落、山川、水系、街区、镇街、圩市等地理实体 | 西樵山、九江镇、官窑、松塘村、桑园围、千灯湖 | "中国""广东""佛山市"等过大地名 |
| 朝代年号 | 朝代名称、具体年号或历史时期 | 清代、明万历、民国、宋嘉定、光绪三十年 | 纯公元纪年如"1898年" |
| 非遗技艺 | 非物质文化遗产项目、民俗活动、传统技艺、艺术形式、民间信仰仪式 | 龙舟说唱、醒狮、粤剧、九江双蒸酿制技艺、十番音乐、生菜会、灰塑 | "文化""传统"等泛词 |
| 历史事件 | 有明确时间或地点的具体历史事件 | 公车上书、戊戌变法、康有为上书、南海县设立 | "社会变革"等笼统描述 |
| 典籍作品 | 文中提及的书籍、诗文、志书、碑文、族谱等文献 | 《南海县志》、《大德南海志》、《康南海自编年谱》 | 现代论文 |
| 物产饮食 | 南海区特色物产、名优食品、农副产品 | 九江双蒸酒、西樵大饼、大顶苦瓜、南海鱼花、藤编制品 | 普通食物如"米饭" |
| 宗族姓氏 | 文中提及的具有地方文化意义的宗族、家族、堂号 | 九江关氏、松塘区氏、烟桥何氏、简村陈氏 | 单纯姓氏如"陈" |

# 排除规则（严格执行）
- 排除现代人名、现代机构名
- 排除纯数字、标点符号、单字实体
- 排除过于泛化的词汇（如"经济""发展""社会""地方""历史"）
- 排除与南海区文化/历史/旅游无直接关联的普通名词
- 实体名称长度：2~15个汉字

# 输出格式
严格输出JSON数组，不要输出任何其他内容。每个实体包含4个字段：

```json
[
  {"name":"康有为","type":"人物","description":"清末维新变法领袖，南海丹灶人","confidence":0.95},
  {"name":"云泉仙馆","type":"建筑遗迹","description":"西樵山清代道观，省级文保单位","confidence":0.90}
]
```

若文本中无可提取的实体，返回 `[]`。\
"""

RELATION_SYSTEM_PROMPT = """\
# 角色
你是佛山市南海区文旅知识图谱构建专家，负责从文本中判定实体之间的语义关系。

# 任务
根据提供的实体列表和原文片段，判断实体之间存在的所有关系。
注意：同一对实体之间可以存在多种关系，请全部列出。

# 关系类型定义（共15类，必须严格归入其中之一）

| 关系类型 | 方向 | 含义 | 示例 |
|---------|------|------|------|
| 创建修建 | 人物 → 建筑遗迹 | 人物主持创建、修建、重修、捐建某建筑 | 康有为→康有为故居 |
| 出生于 | 人物 → 地名 | 人物的出生地/籍贯 | 康有为→丹灶镇 |
| 活动于 | 人物 → 地名/建筑遗迹 | 人物在此地讲学、活动、居住、任职 | 朱次琦→九江礼山草堂 |
| 著有 | 人物 → 典籍作品 | 人物撰写/编著某文献 | 康有为→《新学伪经考》 |
| 位于 | 建筑遗迹/地名 → 地名 | 空间归属，A位于B | 松塘村→西樵镇 |
| 始建于 | 建筑遗迹 → 朝代年号 | 建筑的始建年代 | 云泉仙馆→清乾隆 |
| 承载文化 | 地名/建筑遗迹 → 非遗技艺 | 某地是某文化活动的载体或举办地 | 九江镇→龙舟说唱 |
| 传承于 | 非遗技艺 → 地名 | 某技艺/民俗在某地流传传承 | 醒狮→大沥镇 |
| 记载于 | 实体 → 典籍作品 | 某实体在某文献中有记载 | 西樵山→《南海县志》 |
| 属于时期 | 实体 → 朝代年号 | 实体所属的朝代/时期 | 陈启沅→清代 |
| 发生于 | 历史事件 → 地名/朝代年号 | 事件发生的地点或时间 | 戊戌变法→光绪二十四年 |
| 盛产 | 地名 → 物产饮食 | 某地以某种特产闻名 | 九江镇→九江双蒸酒 |
| 关联人物 | 人物 ↔ 建筑遗迹/地名 | 以人物命名、人物祖居等关联 | 黄飞鸿→黄飞鸿纪念馆 |
| 同族 | 人物 ↔ 宗族姓氏 | 人物属于某宗族 | 康有为→南海康氏 |
| 同类 | 实体 ↔ 实体 | 同一文化门类、同一类型 | 醒狮↔龙舟（民俗类） |

# 核心规则
1. 同一对实体之间可能存在多种关系 —— 例如"康有为"与"丹灶镇"既有"出生于"也有"活动于"的关系，请分两条输出。
2. 每条关系必须附带 evidence（从原文中引用的依据片段，≤40字）。
3. 关系的 source 和 target 必须是实体列表中的名称（完全一致）。
4. confidence 范围 0.0~1.0，只输出你有把握的关系（≥0.7）。

# 输出格式
严格输出JSON数组，不要输出任何其他内容：

```json
[
  {"source":"康有为","target":"丹灶镇","relation":"出生于","evidence":"康有为，南海丹灶苏村人","confidence":0.95},
  {"source":"康有为","target":"丹灶镇","relation":"活动于","evidence":"康有为少时在丹灶读书","confidence":0.85}
]
```

若无可确定的关系，返回 `[]`。\
"""

# ════════════════════ Ollama 调用 ════════════════════

def call_ollama(system_prompt, user_prompt, temperature=0.3, max_retries=3):
    """通过 Ollama Chat API 调用本地模型"""
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.85,
            "repeat_penalty": 1.05,
            "num_predict": 4096,
        },
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=180)
            if resp.status_code == 200:
                msg = resp.json().get("message", {})
                return msg.get("content", "")
            else:
                print(f"  Ollama HTTP {resp.status_code}, 重试 {attempt+1}/{max_retries}")
                time.sleep(2)
        except requests.exceptions.ConnectionError:
            print(f"  Ollama 连接失败, 重试 {attempt+1}/{max_retries}")
            time.sleep(5)
        except requests.exceptions.Timeout:
            print(f"  Ollama 超时, 重试 {attempt+1}/{max_retries}")
            time.sleep(3)

    return None


def parse_json_response(text):
    """从LLM响应中提取JSON数组（兼容多种输出格式）"""
    if not text:
        return []

    text = text.strip()

    # Qwen3.5 思考模式：跳过 <think>...</think> 块
    think_end = text.rfind("</think>")
    if think_end != -1:
        text = text[think_end + len("</think>"):].strip()

    if text.startswith("["):
        try:
            end = text.rfind("]") + 1
            return json.loads(text[:end])
        except json.JSONDecodeError:
            pass

    m = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return []


# ════════════════════ 文本分片 ════════════════════

def split_text_to_chunks(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    if text.startswith("---"):
        end_fm = text.find("---", 3)
        if end_fm != -1:
            text = text[end_fm + 3:].strip()

    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。、；：""''（）《》—…·！？\s]', '', text)

    chunks = []
    pos = 0
    while pos < len(text):
        end = min(pos + chunk_size, len(text))
        chunk = text[pos:end]
        if len(chunk.strip()) > 50:
            chunks.append(chunk.strip())
        pos += chunk_size - overlap

    return chunks


# ════════════════════ 实体抽取 ════════════════════

def validate_entity(e):
    if not isinstance(e, dict):
        return False
    name = e.get("name", "").strip()
    etype = e.get("type", "").strip()
    conf = e.get("confidence", 0)

    if not name or not etype:
        return False
    if etype not in VALID_ENTITY_TYPES:
        return False
    if len(name) < 2 or len(name) > 15:
        return False
    if not isinstance(conf, (int, float)) or conf < 0.5:
        return False
    if name in ANCHOR_NAMES:
        return True
    if conf < 0.7:
        return False
    return True


def extract_entities_from_chunk(chunk_text, file_title=""):
    user_prompt = (
        f"以下是佛山市南海区文史资料《{file_title}》的一段文本。"
        f"请严格按照规则提取其中的文化相关实体。\n\n"
        f"【文本】\n{chunk_text}"
    )
    response = call_ollama(ENTITY_SYSTEM_PROMPT, user_prompt)
    raw_entities = parse_json_response(response)

    valid = []
    for e in raw_entities:
        if validate_entity(e):
            e["name"] = e["name"].strip()
            e["type"] = e["type"].strip()
            e["is_anchor"] = e["name"] in ANCHOR_NAMES
            e["source_file"] = file_title
            valid.append(e)

    return valid, response


# ════════════════════ 关系抽取 ════════════════════

def validate_relation(r, known_entities):
    if not isinstance(r, dict):
        return False
    src = r.get("source", "").strip()
    tgt = r.get("target", "").strip()
    rel = r.get("relation", "").strip()
    evidence = r.get("evidence", "")
    conf = r.get("confidence", 0)

    if not src or not tgt or not rel:
        return False
    if src == tgt:
        return False
    if rel not in VALID_RELATION_TYPES:
        return False
    if not evidence:
        return False
    if not isinstance(conf, (int, float)) or conf < 0.6:
        return False
    if src not in known_entities or tgt not in known_entities:
        return False
    return True


def extract_relations_from_chunk(chunk_text, entities_in_chunk, file_title=""):
    if len(entities_in_chunk) < 2:
        return [], ""

    entity_list_str = "\n".join(
        f"  - {e['name']}（{e['type']}）：{e.get('description', '')}"
        for e in entities_in_chunk[:30]
    )

    user_prompt = (
        f"以下是佛山市南海区文史资料《{file_title}》的一段文本及从中提取的实体。\n"
        f"请判断实体之间的所有关系（同一对实体可有多种关系）。\n\n"
        f"【实体列表】\n{entity_list_str}\n\n"
        f"【原文片段】\n{chunk_text}"
    )

    response = call_ollama(RELATION_SYSTEM_PROMPT, user_prompt)
    raw_relations = parse_json_response(response)

    known = {e["name"] for e in entities_in_chunk}
    valid = []
    for r in raw_relations:
        if validate_relation(r, known):
            r["source"] = r["source"].strip()
            r["target"] = r["target"].strip()
            r["relation"] = r["relation"].strip()
            r["source_file"] = file_title
            valid.append(r)

    return valid, response


# ════════════════════ 进度管理 ════════════════════

def load_progress():
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "task": "extraction",
        "model": MODEL_NAME,
        "total_files": 0,
        "completed_files": [],
        "file_chunk_progress": {},
        "stats": {"entities": 0, "relations": 0},
        "last_update": "",
        "status": "idle",
    }


def save_progress(progress):
    progress["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    progress["model"] = MODEL_NAME
    tmp = PROGRESS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PROGRESS_PATH)


def append_log(file, chunk, ent_count, rel_count, elapsed):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | model={MODEL_NAME} | file={file} | chunk={chunk} | entities={ent_count} | relations={rel_count} | elapsed={elapsed}s"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ════════════════════ 文件级结果管理 ════════════════════

def load_file_entities(filename):
    path = os.path.join(ENTITY_DIR, filename.replace(".md", ".json"))
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"chunks": {}}


def save_file_entities(filename, data):
    path = os.path.join(ENTITY_DIR, filename.replace(".md", ".json"))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_file_relations(filename):
    path = os.path.join(RELATION_DIR, filename.replace(".md", ".json"))
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"chunks": {}}


def save_file_relations(filename, data):
    path = os.path.join(RELATION_DIR, filename.replace(".md", ".json"))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ════════════════════ 重置 ════════════════════

def reset_all():
    """清空全部旧结果，从头开始"""
    for d in [ENTITY_DIR, RELATION_DIR]:
        if os.path.isdir(d):
            shutil.rmtree(d)
    for f in [PROGRESS_PATH, LOG_PATH,
              os.path.join(OUTPUT_DIR, "merged_entities.json"),
              os.path.join(OUTPUT_DIR, "merged_relations.json"),
              os.path.join(OUTPUT_DIR, "demo_report.md")]:
        if os.path.exists(f):
            os.remove(f)
    print("已清空全部旧抽取结果。")


# ════════════════════ 主流程 ════════════════════

def get_corpus_files(demo=False):
    index_path = os.path.join(CORPUS_DIR, "corpus_index.json")
    if not os.path.exists(index_path):
        print("错误: corpus_index.json 不存在，请先运行 prepare_corpus.py")
        return []

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    files = index["files"]

    if demo:
        demo_targets = ["南海县志_OCR连续文本", "南海龙狮", "西樵山专辑"]
        demo_files = []
        for f_info in files:
            for target in demo_targets:
                if target in f_info["title"]:
                    demo_files.append(f_info)
                    break
            if len(demo_files) >= 3:
                break
        return demo_files or files[:3]

    return files


def process_file(file_info, progress, demo=False):
    filename = file_info["filename"]
    title = file_info["title"]
    filepath = os.path.join(CORPUS_DIR, filename)

    if not os.path.exists(filepath):
        print(f"  文件不存在: {filepath}")
        return 0, 0

    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    if demo:
        text = text[:2000]

    chunks = split_text_to_chunks(text)
    if not chunks:
        return 0, 0

    ent_data = load_file_entities(filename)
    rel_data = load_file_relations(filename)
    completed_chunks = set(ent_data.get("chunks", {}).keys())

    file_entities_count = 0
    file_relations_count = 0

    chunk_bar = tqdm(
        enumerate(chunks), total=len(chunks),
        desc=f"  片段", leave=False, ncols=100,
        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
    )

    for chunk_idx, chunk_text in chunk_bar:
        chunk_key = f"chunk_{chunk_idx:04d}"

        if chunk_key in completed_chunks:
            file_entities_count += len(ent_data["chunks"][chunk_key].get("entities", []))
            file_relations_count += len(rel_data.get("chunks", {}).get(chunk_key, {}).get("relations", []))
            continue

        t0 = time.time()

        entities, _ = extract_entities_from_chunk(chunk_text, title)
        file_entities_count += len(entities)

        ent_data.setdefault("chunks", {})[chunk_key] = {
            "entities": entities,
            "chunk_text_hash": hashlib.md5(chunk_text.encode()).hexdigest()[:8],
        }
        save_file_entities(filename, ent_data)

        relations, _ = extract_relations_from_chunk(chunk_text, entities, title)
        file_relations_count += len(relations)

        rel_data.setdefault("chunks", {})[chunk_key] = {
            "relations": relations,
        }
        save_file_relations(filename, rel_data)

        elapsed = time.time() - t0

        append_log(filename, chunk_key, len(entities), len(relations), round(elapsed, 1))

        progress["file_chunk_progress"][filename] = chunk_idx + 1
        progress["stats"]["entities"] += len(entities)
        progress["stats"]["relations"] += len(relations)
        save_progress(progress)

        chunk_bar.set_postfix(E=file_entities_count, R=file_relations_count)

    return file_entities_count, file_relations_count


def run_extraction(demo=False):
    for d in [OUTPUT_DIR, ENTITY_DIR, RELATION_DIR]:
        os.makedirs(d, exist_ok=True)

    load_anchors()
    files = get_corpus_files(demo=demo)
    if not files:
        return 0, 0

    progress = load_progress()
    completed_files = set(progress.get("completed_files", []))

    mode_str = "DEMO (3篇×2000字)" if demo else f"全量 ({len(files)}篇)"
    print(f"\n{'='*60}")
    print(f"LLM 实体/关系抽取 v2 — {mode_str}")
    print(f"模型: {MODEL_NAME}")
    print(f"实体类型: {len(VALID_ENTITY_TYPES)}类 | 关系类型: {len(VALID_RELATION_TYPES)}类")
    print(f"片段大小: {CHUNK_SIZE}字 | 已完成文件: {len(completed_files)}")
    print(f"{'='*60}\n")

    progress["total_files"] = len(files)
    progress["status"] = "running"
    save_progress(progress)

    total_ent = 0
    total_rel = 0

    file_bar = tqdm(files, desc="文件进度", ncols=100)

    for file_info in file_bar:
        filename = file_info["filename"]
        title = file_info["title"]

        if filename in completed_files and not demo:
            ent_data = load_file_entities(filename)
            for cv in ent_data.get("chunks", {}).values():
                total_ent += len(cv.get("entities", []))
            file_bar.set_postfix(E=total_ent, R=total_rel)
            continue

        file_bar.set_description(f"处理: {title[:25]}")

        ent_count, rel_count = process_file(file_info, progress, demo=demo)
        total_ent += ent_count
        total_rel += rel_count

        if not demo:
            completed_files.add(filename)
            progress["completed_files"] = list(completed_files)
            save_progress(progress)

        file_bar.set_postfix(E=total_ent, R=total_rel)

    progress["status"] = "completed"
    save_progress(progress)

    print(f"\n{'='*60}")
    print(f"抽取完成！实体: {total_ent}, 关系: {total_rel}")
    print(f"结果目录: {OUTPUT_DIR}")
    print(f"{'='*60}")

    return total_ent, total_rel


# ════════════════════ 合并与去重 ════════════════════

def merge_results():
    print("\n合并实体...")

    entity_counter = Counter()
    entity_info = {}
    entity_sources = defaultdict(set)

    for fname in sorted(os.listdir(ENTITY_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(ENTITY_DIR, fname), "r", encoding="utf-8") as f:
            data = json.load(f)
        for chunk_data in data.get("chunks", {}).values():
            for e in chunk_data.get("entities", []):
                name = e["name"]
                entity_counter[name] += 1
                entity_sources[name].add(e.get("source_file", fname))
                if name not in entity_info or e.get("confidence", 0) > entity_info[name].get("confidence", 0):
                    entity_info[name] = e

    merged = []
    for name, count in entity_counter.most_common():
        info = entity_info[name]
        is_anchor = name in ANCHOR_NAMES
        if count >= 2 or is_anchor:
            merged.append({
                "name": name,
                "type": info["type"],
                "description": info.get("description", ""),
                "confidence": round(info.get("confidence", 0.8), 2),
                "mentions": count,
                "source_count": len(entity_sources[name]),
                "is_anchor": is_anchor,
            })

    type_stats = dict(Counter(e["type"] for e in merged))
    output = {
        "total": len(merged),
        "type_stats": type_stats,
        "extracted_by": f"LLM ({MODEL_NAME})",
        "entity_types": sorted(VALID_ENTITY_TYPES),
        "merged_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "entities": merged,
    }

    path = os.path.join(OUTPUT_DIR, "merged_entities.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"合并实体: {len(merged)} 条 → {path}")
    print(f"类型分布: {type_stats}")

    # ── 合并关系（保留多重关系） ──
    print("\n合并关系...")
    merged_rels = []
    seen_keys = set()

    for fname in sorted(os.listdir(RELATION_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(RELATION_DIR, fname), "r", encoding="utf-8") as f:
            data = json.load(f)
        for chunk_data in data.get("chunks", {}).values():
            for r in chunk_data.get("relations", []):
                # 同一对实体+同一关系类型 视为同一条（去重）
                key = (r["source"], r["target"], r["relation"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    merged_rels.append(r)

    merged_names = {e["name"] for e in merged}
    final_rels = [
        r for r in merged_rels
        if r["source"] in merged_names and r["target"] in merged_names
    ]

    # 统计多重关系
    pair_rels = defaultdict(list)
    for r in final_rels:
        pair = tuple(sorted([r["source"], r["target"]]))
        pair_rels[pair].append(r["relation"])
    multi_count = sum(1 for v in pair_rels.values() if len(v) > 1)

    rel_stats = dict(Counter(r["relation"] for r in final_rels))
    rel_output = {
        "total": len(final_rels),
        "multi_relation_pairs": multi_count,
        "relation_stats": rel_stats,
        "relation_types": sorted(VALID_RELATION_TYPES),
        "extracted_by": f"LLM ({MODEL_NAME})",
        "merged_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "relations": final_rels,
    }

    path = os.path.join(OUTPUT_DIR, "merged_relations.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rel_output, f, ensure_ascii=False, indent=2)
    print(f"合并关系: {len(final_rels)} 条 → {path}")
    print(f"其中 {multi_count} 对实体存在多重关系")
    print(f"关系分布: {rel_stats}")

    return merged, final_rels


# ════════════════════ DEMO 报告 ════════════════════

def generate_demo_report():
    report_lines = [
        "# LLM 实体/关系抽取 DEMO 报告 (v2)\n",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        f"模型: {MODEL_NAME}\n",
        f"实体类型: {len(VALID_ENTITY_TYPES)}类 — {', '.join(sorted(VALID_ENTITY_TYPES))}\n",
        f"关系类型: {len(VALID_RELATION_TYPES)}类 — {', '.join(sorted(VALID_RELATION_TYPES))}\n",
        "---\n",
    ]

    for fname in sorted(os.listdir(ENTITY_DIR)):
        if not fname.endswith(".json"):
            continue
        title = fname.replace(".json", "")
        ent_path = os.path.join(ENTITY_DIR, fname)
        rel_path = os.path.join(RELATION_DIR, fname)

        with open(ent_path, "r", encoding="utf-8") as f:
            ent_data = json.load(f)
        rel_data = {}
        if os.path.exists(rel_path):
            with open(rel_path, "r", encoding="utf-8") as f:
                rel_data = json.load(f)

        report_lines.append(f"\n## {title}\n")

        all_ents = []
        for cv in ent_data.get("chunks", {}).values():
            all_ents.extend(cv.get("entities", []))

        report_lines.append(f"\n### 抽取实体 ({len(all_ents)} 个)\n")
        report_lines.append("| 名称 | 类型 | 描述 | 置信度 | 锚点 |")
        report_lines.append("|------|------|------|--------|------|")
        seen = set()
        for e in all_ents:
            if e["name"] not in seen:
                seen.add(e["name"])
                anchor = "Y" if e.get("is_anchor") else ""
                desc = e.get("description", "")[:40]
                report_lines.append(
                    f"| {e['name']} | {e['type']} | {desc} | {e.get('confidence', '')} | {anchor} |"
                )

        all_rels = []
        for cv in rel_data.get("chunks", {}).values():
            all_rels.extend(cv.get("relations", []))

        report_lines.append(f"\n### 抽取关系 ({len(all_rels)} 条)\n")
        report_lines.append("| 源实体 | 关系类型 | 目标实体 | 原文依据 | 置信度 |")
        report_lines.append("|--------|----------|----------|----------|--------|")
        for r in all_rels:
            ev = r.get("evidence", "")[:40]
            report_lines.append(
                f"| {r['source']} | {r['relation']} | {r['target']} | {ev} | {r.get('confidence', '')} |"
            )

    report_path = os.path.join(OUTPUT_DIR, "demo_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"\nDEMO 报告: {report_path}")
    return report_path


# ════════════════════ 入口 ════════════════════

def main():
    parser = argparse.ArgumentParser(description="LLM 智能实体/关系抽取 v2")
    parser.add_argument("--demo", action="store_true", help="DEMO: 只跑3篇×2000字")
    parser.add_argument("--merge-only", action="store_true", help="仅合并已有结果")
    parser.add_argument("--reset", action="store_true", help="清空全部旧结果，从头重跑")
    parser.add_argument("--model", default=MODEL_NAME, help=f"Ollama模型 (默认: {MODEL_NAME})")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help=f"片段大小 (默认: {CHUNK_SIZE})")
    args = parser.parse_args()

    _update_config(args.model, args.chunk_size)

    if args.reset:
        reset_all()

    if args.merge_only:
        load_anchors()
        merge_results()
        return

    total_ent, total_rel = run_extraction(demo=args.demo)

    if args.demo:
        generate_demo_report()
        print("\n请查看 demo_report.md 确认抽取效果。")
        print("效果满意后运行: python llm_ner.py --reset")
    else:
        merge_results()
        print("\n全量抽取和合并已完成！")


if __name__ == "__main__":
    main()
