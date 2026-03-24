#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
POI 数据清洗流水线 — 基于 Ollama 本地大模型（多线程并发版）

功能：
  1. 纠正 POI 分类（category）
  2. 打上「文旅相关」标签（is_cultural_tourism）
  3. 断点续跑：每批次处理后实时存盘，中断后恢复自动跳过已完成批次
  4. 多线程并发调用 Ollama，最大化 CPU/GPU 利用率

用法：
  python llm_poi_clean.py                          # 断点续跑（默认4线程）
  python llm_poi_clean.py --threads 8              # 8线程并发
  python llm_poi_clean.py --reset                  # 清空旧进度，从头开始
  python llm_poi_clean.py --merge-only             # 仅合并已有结果，输出最终 CSV
  python llm_poi_clean.py --batch-size 25          # 自定义批次大小
"""

import os
import sys
import re
import json
import time
import argparse
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from tqdm import tqdm
except ImportError:
    print("请安装 tqdm: pip install tqdm")
    sys.exit(1)

import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ════════════════════ 路径配置 ════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(BASE_DIR, "..", "..")
INPUT_CSV = os.path.join(PROJECT_DIR, "output", "tables", "poi_cleaned.csv")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output", "poi_llm_clean")
PROGRESS_PATH = os.path.join(OUTPUT_DIR, "progress.json")
LOG_PATH = os.path.join(OUTPUT_DIR, "clean_log.log")
OUTPUT_CSV = os.path.join(PROJECT_DIR, "output", "tables", "poi_llm_cleaned.csv")

# ════════════════════ 可变配置（通过命令行参数修改） ════════════════════

CFG = {
    "ollama_url": "http://localhost:11434/api/chat",
    "model": "qwen2.5:7b",
    "batch_size": 20,
    "num_threads": 4,
}

_progress_lock = threading.Lock()
_log_lock = threading.Lock()

# ════════════════════ 分类体系 ════════════════════

VALID_CATEGORIES = [
    "人文古迹", "宗教场所", "自然景观", "公园绿地",
    "文化场馆", "非遗体验", "教育研学", "休闲娱乐",
    "体育运动", "特色街区", "红色文化", "餐饮住宿",
    "商业服务", "其他",
]
CATEGORY_SET = set(VALID_CATEGORIES)

# ════════════════════ Prompt 模板 ════════════════════

SYSTEM_PROMPT = """\
# 角色
你是佛山市南海区文化旅游数据治理专家，精通南海区文旅资源分类与文化遗产价值评估。

# 任务
对给定的一批 POI（兴趣点）数据进行两项判定：
1. **纠正分类**：根据 POI 名称、原始类型、地址，将其归入最合适的类别。
2. **文旅相关性打标**：判断该 POI 是否与南海区文化旅游场景相关。

# 分类体系（共14类，必须严格归入其中之一）

| 类别 | 定义 | 典型示例 |
|------|------|----------|
| 人文古迹 | 祠堂、宗祠、公祠、故居、纪念馆、碑刻、古塔、古桥、牌坊、书院、古村落遗存 | 康有为故居、陈氏宗祠、奎光楼、松塘村 |
| 宗教场所 | 寺庙、道观、教堂、清真寺 | 南海观音寺、宝峰寺、云泉仙馆 |
| 自然景观 | 山川、河流、湖泊、自然风光、风景名胜 | 西樵山、千灯湖、听音湖 |
| 公园绿地 | 城市公园、广场、花园、绿道、社区公园 | 大沥公园、桂城公园、文化广场 |
| 文化场馆 | 博物馆、图书馆、美术馆、文化馆、展览馆、文化宫 | 南海博物馆、康有为博物馆 |
| 非遗体验 | 非遗体验馆、传习所、传统工艺作坊、非遗相关店铺 | 黄飞鸿狮艺武术馆、醒狮传习所 |
| 教育研学 | 学校、科教场所、研学基地 | 石门中学、南海中学 |
| 休闲娱乐 | 影院、KTV、游乐场、农庄、主题乐园、度假区 | 南海影剧院、长鹿旅游休博园 |
| 体育运动 | 体育馆、运动场、武术馆、健身房、球场 | 南海体育中心、咏春拳馆 |
| 特色街区 | 文创园、商业步行街、特色小镇、工业遗产园 | 粤港澳文化创意产业园 |
| 红色文化 | 革命旧址、纪念碑、红色教育基地 | 中共南海县委旧址 |
| 餐饮住宿 | 酒店、民宿、餐厅（有文化或地方特色的归此类） | 西樵山大饼老店、九江双蒸博物馆餐厅 |
| 商业服务 | 纯商业设施、充电宝、停车场、写字楼、普通店铺 | 充电宝租借点、停车场、服装店 |
| 其他 | 以上类别均不适合 | 居民楼门牌、路口名 |

# 分类优先级规则
1. 祠堂（宗祠/公祠/大宗祠/家祠）→ **人文古迹**（不是宗教场所！）
2. 寺/庙/道观/教堂/清真寺 → **宗教场所**
3. 名称含"公园""广场" → **公园绿地**
4. 革命旧址/红色景区 → **红色文化**
5. 纪念馆/故居/书院/牌坊/古塔/古桥/遗址 → **人文古迹**
6. 博物馆/图书馆/美术馆/展览馆/文化馆/文化宫 → **文化场馆**
7. 武术馆/体育馆/健身/运动/球场 → **体育运动**
8. 充电宝/停车场/门牌/路口/公交站/写字楼/服装店 → **商业服务**

# 文旅相关性判定标准
「文旅相关」= 该 POI 对南海区的文化旅游有价值，游客/研究者/文化爱好者可能会前往。
- ✅ 文旅相关：祠堂、古迹、寺庙、博物馆、公园景区、非遗场馆、红色旧址、文化名人故居、特色文化街区、有历史文化的建筑等
- ✅ 文旅相关：承载地方文化记忆的场所（即使是小型社区公园也算，因为可能承载龙舟等民俗活动）
- ❌ 非文旅相关：充电宝、停车场、普通商铺、写字楼、普通餐厅、培训机构、门牌号、路口等纯商业/交通/生活设施

# 输出格式
严格输出JSON数组，不要输出其他内容。每项包含3个字段：

```json
[
  {"idx": 0, "corrected_category": "人文古迹", "is_cultural_tourism": true},
  {"idx": 1, "corrected_category": "商业服务", "is_cultural_tourism": false}
]
```

- idx: 输入列表中的序号（从0开始）
- corrected_category: 纠正后的类别（必须是14类之一）
- is_cultural_tourism: 是否文旅相关（true/false）\
"""


def build_user_prompt(batch_items):
    lines = ["以下是一批南海区 POI 数据，请逐条判定分类和文旅相关性：\n"]
    for i, item in enumerate(batch_items):
        lines.append(
            f"[{i}] 名称: {item['name']} | "
            f"原始分类: {item['category']} | "
            f"原始类型: {item['original_type']} | "
            f"地址: {item.get('address', '')} | "
            f"镇街: {item['town']}"
        )
    return "\n".join(lines)


# ════════════════════ Ollama 调用 ════════════════════

def call_ollama(system_prompt, user_prompt, temperature=0.15, max_retries=3):
    payload = {
        "model": CFG["model"],
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
            resp = requests.post(CFG["ollama_url"], json=payload, timeout=300)
            if resp.status_code == 200:
                msg = resp.json().get("message", {})
                return msg.get("content", "")
            else:
                print(f"  [T{threading.current_thread().name}] Ollama HTTP {resp.status_code}, 重试 {attempt+1}/{max_retries}")
                time.sleep(3)
        except requests.exceptions.ConnectionError:
            print(f"  [T{threading.current_thread().name}] Ollama 连接失败, 重试 {attempt+1}/{max_retries}")
            time.sleep(5)
        except requests.exceptions.Timeout:
            print(f"  [T{threading.current_thread().name}] Ollama 超时, 重试 {attempt+1}/{max_retries}")
            time.sleep(5)
    return None


def parse_json_response(text):
    if not text:
        return []
    text = text.strip()

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


# ════════════════════ 进度管理（线程安全） ════════════════════

def load_progress():
    if os.path.exists(PROGRESS_PATH):
        try:
            with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "results" in data:
                return data
        except (json.JSONDecodeError, ValueError):
            print("  警告: progress.json 损坏，已重置")
    return {
        "model": CFG["model"],
        "batch_size": CFG["batch_size"],
        "total_rows": 0,
        "completed_batches": [],
        "results": {},
        "stats": {"processed": 0, "cultural_tourism": 0, "category_changes": 0},
        "last_update": "",
        "status": "idle",
    }


def save_progress(progress):
    with _progress_lock:
        progress["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tmp = PROGRESS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
        os.replace(tmp, PROGRESS_PATH)


def append_log(batch_id, count, ct_count, cat_changes, elapsed):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tid = threading.current_thread().name
    line = (
        f"{ts} | {tid} | batch={batch_id} | processed={count} | "
        f"cultural_tourism={ct_count} | cat_changes={cat_changes} | "
        f"elapsed={elapsed:.1f}s"
    )
    with _log_lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# ════════════════════ 批次处理 ════════════════════

def process_batch(batch_items, batch_id, progress):
    user_prompt = build_user_prompt(batch_items)
    response = call_ollama(SYSTEM_PROMPT, user_prompt)
    parsed = parse_json_response(response)

    batch_results = {}
    ct_count = 0
    cat_changes = 0

    result_map = {}
    for item in parsed:
        if isinstance(item, dict) and "idx" in item:
            result_map[item["idx"]] = item

    for i, poi in enumerate(batch_items):
        row_idx = str(poi["_row_idx"])
        if i in result_map:
            r = result_map[i]
            cat = r.get("corrected_category", poi["category"])
            if cat not in CATEGORY_SET:
                cat = poi["category"]
            is_ct = bool(r.get("is_cultural_tourism", False))
        else:
            cat = poi["category"]
            is_ct = False

        if cat != poi["category"]:
            cat_changes += 1
        if is_ct:
            ct_count += 1

        batch_results[row_idx] = {
            "corrected_category": cat,
            "is_cultural_tourism": is_ct,
        }

    with _progress_lock:
        progress["results"].update(batch_results)
        progress["completed_batches"].append(batch_id)
        progress["stats"]["processed"] += len(batch_items)
        progress["stats"]["cultural_tourism"] += ct_count
        progress["stats"]["category_changes"] += cat_changes

    save_progress(progress)
    return len(batch_items), ct_count, cat_changes


# ════════════════════ 主流程（多线程） ════════════════════

def run_cleaning():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    batch_size = CFG["batch_size"]
    num_threads = CFG["num_threads"]

    print(f"读取数据: {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV)
    total = len(df)
    print(f"总计 {total} 条 POI\n")

    progress = load_progress()
    progress["total_rows"] = total
    progress["batch_size"] = batch_size
    completed_batches = set(progress.get("completed_batches", []))

    batches = []
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_id = f"batch_{start:06d}"
        batch_items = []
        for idx in range(start, end):
            row = df.iloc[idx]
            batch_items.append({
                "_row_idx": idx,
                "name": str(row["name"]),
                "category": str(row["category"]),
                "original_type": str(row.get("original_type", "")),
                "address": str(row.get("address", "")),
                "town": str(row.get("town", "")),
            })
        batches.append((batch_id, batch_items))

    pending = [(bid, items) for bid, items in batches if bid not in completed_batches]
    done_count = len(batches) - len(pending)

    print(f"{'='*60}")
    print(f"POI 数据清洗 — LLM 分类纠正 + 文旅打标（多线程）")
    print(f"模型: {CFG['model']} | 批次大小: {batch_size} | 并发线程: {num_threads}")
    print(f"总批次: {len(batches)} | 已完成: {done_count} | 待处理: {len(pending)}")
    print(f"已处理 POI: {progress['stats']['processed']}")
    print(f"{'='*60}\n")

    if not pending:
        print("所有批次已完成，无需继续处理。")
        return

    progress["status"] = "running"
    save_progress(progress)

    bar = tqdm(total=len(pending), desc="清洗进度", ncols=110)

    def _worker(batch_id, batch_items):
        t0 = time.time()
        count, ct_count, cat_changes = process_batch(batch_items, batch_id, progress)
        elapsed = time.time() - t0
        append_log(batch_id, count, ct_count, cat_changes, elapsed)
        return count, ct_count, cat_changes, elapsed

    with ThreadPoolExecutor(max_workers=num_threads, thread_name_prefix="W") as pool:
        futures = {
            pool.submit(_worker, bid, items): bid
            for bid, items in pending
        }
        for fut in as_completed(futures):
            bid = futures[fut]
            try:
                count, ct_count, cat_changes, elapsed = fut.result()
                bar.update(1)
                bar.set_postfix(
                    已处理=progress["stats"]["processed"],
                    文旅=progress["stats"]["cultural_tourism"],
                    改分类=progress["stats"]["category_changes"],
                    耗时=f"{elapsed:.1f}s",
                )
            except Exception as e:
                print(f"\n  批次 {bid} 异常: {e}")
                bar.update(1)

    bar.close()

    progress["status"] = "completed"
    save_progress(progress)

    print(f"\n{'='*60}")
    print(f"清洗完成！")
    print(f"  处理: {progress['stats']['processed']} 条")
    print(f"  文旅相关: {progress['stats']['cultural_tourism']} 条")
    print(f"  分类纠正: {progress['stats']['category_changes']} 条")
    print(f"{'='*60}")


def merge_results():
    print(f"\n合并结果到 {OUTPUT_CSV} ...")

    progress = load_progress()
    results = progress.get("results", {})

    if not results:
        print("错误: 没有找到清洗结果，请先运行清洗。")
        return

    df = pd.read_csv(INPUT_CSV)
    print(f"原始数据: {len(df)} 条")
    print(f"清洗结果: {len(results)} 条")

    corrected_cats = []
    is_ct_flags = []
    original_cats = []

    for idx in range(len(df)):
        key = str(idx)
        if key in results:
            r = results[key]
            corrected_cats.append(r["corrected_category"])
            is_ct_flags.append(r["is_cultural_tourism"])
        else:
            corrected_cats.append(df.iloc[idx]["category"])
            is_ct_flags.append(False)
        original_cats.append(df.iloc[idx]["category"])

    df["original_category"] = original_cats
    df["category"] = corrected_cats
    df["is_cultural_tourism"] = is_ct_flags

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n输出文件: {OUTPUT_CSV}")

    print(f"\n=== 纠正后分类分布 ===")
    print(df["category"].value_counts().to_string())

    changed = sum(1 for a, b in zip(original_cats, corrected_cats) if a != b)
    ct_total = sum(is_ct_flags)
    print(f"\n分类变更: {changed} 条 ({changed/len(df)*100:.1f}%)")
    print(f"文旅相关: {ct_total} 条 ({ct_total/len(df)*100:.1f}%)")

    cat_migration = {}
    for orig, new in zip(original_cats, corrected_cats):
        if orig != new:
            key = f"{orig} → {new}"
            cat_migration[key] = cat_migration.get(key, 0) + 1
    if cat_migration:
        print(f"\n=== 分类迁移 TOP 20 ===")
        for k, v in sorted(cat_migration.items(), key=lambda x: -x[1])[:20]:
            print(f"  {k}: {v} 条")

    return df


def reset_progress():
    if os.path.exists(PROGRESS_PATH):
        os.remove(PROGRESS_PATH)
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)
    print("已清空清洗进度。")


# ════════════════════ 入口 ════════════════════

def main():
    parser = argparse.ArgumentParser(description="POI 数据清洗 — LLM 分类纠正 + 文旅打标")
    parser.add_argument("--reset", action="store_true", help="清空进度，从头开始")
    parser.add_argument("--merge-only", action="store_true", help="仅合并已有结果输出CSV")
    parser.add_argument("--batch-size", type=int, default=20, help="每批 POI 数量 (默认: 20)")
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama 模型 (默认: qwen2.5:7b)")
    parser.add_argument("--threads", type=int, default=4, help="并发线程数 (默认: 4)")
    args = parser.parse_args()

    CFG["model"] = args.model
    CFG["batch_size"] = args.batch_size
    CFG["num_threads"] = args.threads

    if args.reset:
        reset_progress()

    if args.merge_only:
        merge_results()
        return

    run_cleaning()
    merge_results()


if __name__ == "__main__":
    main()
