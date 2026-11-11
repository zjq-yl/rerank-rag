# 普通 RAG 与重排 RAG 对比

本项目使用同一份文档和 Chroma 向量索引，对比两条问答链路：

- **普通 RAG**：问题 → BGE 向量检索 Top-K → 生成回答。
- **重排 RAG**：问题 → BGE 向量召回候选 → BGE Reranker 重排 Top-N → 生成回答。

默认普通 RAG 直接取 5 条；重排 RAG 先召回 20 条，再取 5 条。两条链路共用切块、Embedding、向量库和生成模型。

## 目录结构

当前采用 `src` 包布局，命令行入口为 `rerank-rag`：

```text
rerank-rag/
├── src/
│   └── rerank_rag/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── documents.py
│       ├── mineru.py
│       ├── embedding.py
│       ├── vector_store.py
│       ├── rerank.py
│       └── generation.py
├── data/                  # .txt、.md、.docx、.pdf 知识库
│   ├── demo.txt
│   └── faq.md
├── models/                # 自行下载模型，不提交
├── chroma_db/             # 运行时索引，不提交
├── .cache/mineru/         # PDF 解析缓存，不提交
├── .venv/                 # uv 虚拟环境，不提交
├── .env.example           # 配置模板
├── .gitignore
├── .python-version
├── pyproject.toml
├── uv.lock
└── README.md
```

## 用 uv 安装依赖

需要 `uv` 和 Python 3.13 或更新版本。`pyproject.toml` 已列出直接依赖，包括 `chromadb`、`sentence-transformers`、`torch`、`openai`、`python-dotenv`、`python-docx` 和 `requests`。

在仓库根目录运行：

```powershell
uv python install 3.13
uv sync --python 3.13
```

`uv sync` 会创建或更新 `.venv`，下载依赖并更新 `uv.lock`。依赖已写入本仓库，不必重复执行 `uv add`。

Python 包之外，还需自行下载模型权重，将 `BAAI/bge-base-zh-v1.5` 和 `BAAI/bge-reranker-base` 分别放入 `models/bge-base-zh-v1.5/` 和 `models/bge-reranker-base/`。模型目录需包含配置和权重文件。程序使用本地模型，不会自动下载。Embedding 当前使用 CPU；Reranker 有可用 CUDA 时使用 GPU，否则使用 CPU。

复制配置模板：

```powershell
Copy-Item .env.example .env
```

生成答案需要填写 `.env` 中的 `OPENAI_API_KEY`；使用兼容 OpenAI API 的服务时，可填写 `OPENAI_BASE_URL` 和 `OPENAI_CHAT_MODEL`。只用 `--retrieval-only` 比较检索时不需要聊天模型 API Key。模型放在其他路径时，设置 `LOCAL_EMBED_MODEL_PATH`、`LOCAL_RERANK_MODEL_PATH`。

## 文档格式与 MinerU

- `.txt`、`.md`：本地按 UTF-8 读取。
- `.docx`：使用 `python-docx` 在本地提取正文段落和表格文字，按文档顺序写入索引；图片中的文字不会被 OCR。
- `.pdf`：上传到 MinerU 官方在线 API，取得解析后的 Markdown，再写入索引。首次处理 PDF 前，把 MinerU Token 填入根目录 `.env` 的 `MINERU_API_KEY`。PDF 内容会发送给 MinerU，解析可能耗时并消耗账户额度。

PDF 解析结果按文件内容缓存于 `.cache/mineru/`。文件未变化时，重建索引会复用缓存；修改 PDF 后会重新解析。若想强制重新解析全部 PDF，可清空 `.cache/mineru/` 后再次运行 `index`。当前只从 DOCX 提取正文和表格；复杂版式或扫描件建议转为 PDF 后走 MinerU。

## 建立索引

把 `.txt`、`.md`、`.docx` 或 `.pdf` 文档放进 `data/`，然后运行：

```powershell
uv run rerank-rag index
```

这会在 `chroma_db/` 建立或重建索引。修改文档、切块参数或 Embedding 模型后，应重新运行。`index --keep-existing` 会保留集合已有 Chunk，仅在明确需要增量写入时使用。

## 对比检索结果

两条命令使用同一个问题和同一个索引，最终均保留最多 5 条。`--retrieval-only` 会打印排序、来源、分数及文本片段，不调用聊天模型：

```powershell
# 普通 RAG：直接取向量检索前 5 条，不做重排
uv run rerank-rag ask "为什么更换 Embedding 模型后需要重建索引？" --top-k 5 --retrieval-only

# 重排 RAG：召回前 20 条候选，再选前 5 条
uv run rerank-rag ask-rerank "为什么更换 Embedding 模型后需要重建索引？" --candidate-k 20 --rerank-top-n 5 --retrieval-only
```

比较 Chunk ID、顺序和片段内容即可看出差异。`vector_score` 为 `1 - Chroma cosine distance`；`rerank_score` 是重排模型原始分数，两个分数不能直接比较数值。索引不足 20 条时，实际候选数会更少。

## 对比最终回答

配置 API Key 后，去掉 `--retrieval-only`，即可分别生成答案：

```powershell
uv run rerank-rag ask "为什么更换 Embedding 模型后需要重建索引？" --top-k 5
uv run rerank-rag ask-rerank "为什么更换 Embedding 模型后需要重建索引？" --candidate-k 20 --rerank-top-n 5
```

这会发起两次聊天模型请求，可能产生 API 费用。公平对比时保持问题、文档、索引、Embedding 模型和最终结果数一致。示例文档较少时，两条链路的结果可能相同。
