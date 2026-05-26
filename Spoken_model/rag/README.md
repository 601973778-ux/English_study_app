# Spoken_model RAG 知识库

情景口语 RAG 检索库：将 `Book1_p1_p370.md` 等语料解析为统一 chunk，建立本地 TF-IDF 索引，供口语对话 / 评估时检索例句与对话轮次。

## 技术方案

| 层级 | 选型 | 说明 |
|------|------|------|
| 语料格式 | 统一 `chunks.jsonl` | 每行一条 chunk，字段固定（schema 契约） |
| 解析 | `book1_md` / `deepseek_scenario_md` | Book1 按 Topic 分块；DeepSeek 场景 MD 按表格对话/句型分块 |
| 向量检索（当前） | **TF-IDF + 余弦相似度** | 纯 Python，**无需 API Key、无需 GPU**，中英 query 均可试 |
| 向量检索（可选升级） | fastembed + bge 系列 | 见 `requirements-rag.txt`，替换/并行索引即可 |
| 存储 | `corpus/chunks.jsonl` + `index/tfidf_index.json` | 单机 JSON，与 `app/server.py` 同仓库易部署 |
| 过滤 | metadata：`scenario_tags` / `chunk_type` / `topic_id` | 检索前先硬过滤，再算相似度 |

### 数据流

```
Book1_p1_p370.md
    → parse_book1_md.py（分块 + 元数据）
    → corpus/chunks.jsonl
    → build_tfidf_index（离线建索引）
    → index/tfidf_index.json + manifest.json
    → retriever.retrieve(query) → Top-K chunks
```

### Chunk 类型

- `useful_expression` — 常用表达（英中句对）
- `dialogue_turn` — 对话单轮（含 speaker）
- `vocabulary` — Words Storm 词汇

### 后续语料

**不必**复用 Book1 的 MD 解析规则；只需产出 **相同 schema 的 JSONL**，再跑索引构建（或增量 append + rebuild）。

## 构建知识库

在仓库根目录执行（默认按 `config/corpus_manifest.json` 合并 Book1 + DeepSeek 场景语料）：

```bash
python -m Spoken_model.rag.build_kb
```

仅构建单个 Book1 文件（旧行为）：

```bash
python -m Spoken_model.rag.build_kb --input Spoken_model/Communication_Data/Book1_p1_p370.md
```

指定源文件与测试检索：

```bash
python -m Spoken_model.rag.build_kb --input Spoken_model/Communication_Data/Book1_p1_p370.md --query "点餐 主菜 I'd like"
```

## 代码中使用

```python
from Spoken_model.rag.retrieval.retriever import SpokenRagRetriever

rag = SpokenRagRetriever()
hits = rag.retrieve(
    "请用英语点主菜",
    top_k=5,
    scenario_tags=["restaurant", "ordering"],
    chunk_types=["useful_expression", "dialogue_turn"],
)
```

## 目录结构

```
Spoken_model/rag/
  config/corpus_manifest.json      # 语料清单
  config/topic_scenario_tags.json  # topic → 情景标签（可扩展）
  ingest/parse_book1_md.py         # Book1 解析器
  ingest/parse_deepseek_scenario_md.py  # DeepSeek 餐厅场景 MD
  corpus/chunks.jsonl              # 构建产物
  index/manifest.json              # 索引版本信息
  index/tfidf_index.json           # TF-IDF 索引
  build_kb.py                      # 一键构建 CLI
  retrieval/retriever.py           # 在线检索入口
```

## 与口语对话模块的关系

- **固定题面**（`turns.json` 中文题目）仍由开发者主控；
- RAG 仅提供 **参考例句 / 对话范例**，注入 LLM prompt 或评估模板；
- 每 10 次用户发言后的 **cycle 评估** 可对每轮 query 检索 `useful_expression`。
