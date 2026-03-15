# 南海区文史 LLM 实体/关系抽取（Colab 用）

从南海区典籍语料中抽取文化实体与关系，供知识图谱构建。本地用 Ollama，Colab 需自建或对接大模型 API。

## 目录

- `llm_ner.py`：抽取脚本（实体 + 关系，断点续跑）
- `data/corpus/`：语料（53 篇 .md + corpus_index.json）
- `data/database/cultural_anchors.json`：文化锚点（用于实体过滤）
- 运行后结果在 `output/llm_extraction/`

## 本地运行（Ollama）

```bash
pip install -r requirements.txt
# 先拉模型: ollama pull qwen3:8b
python llm_ner.py --demo    # 试跑 3 篇
python llm_ner.py --reset   # 全量重跑
python llm_ner.py           # 断点续跑
```

## Colab 运行

1. 把本仓库 clone 到 Colab（或上传 ZIP 解压）。
2. Colab 里没有 Ollama，需二选一：
   - **方案 A**：在 Colab 里装 Ollama（需 GPU 运行时），再 `!ollama pull qwen3:8b`，然后 `!python llm_ner.py --demo`。
   - **方案 B**：改 `llm_ner.py` 里的 `call_ollama()`，改为请求 Colab 可访问的 API（如 OpenAI 兼容接口、或自己部署的推理服务），并设置对应 `OLLAMA_CHAT_URL` / API Key。
3. 安装依赖：`!pip install -r requirements.txt`
4. 在仓库根目录执行：`!python llm_ner.py --demo` 或 `!python llm_ner.py --reset`

脚本会自动识别 `data/` 在仓库根目录，无需改路径。
