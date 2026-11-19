# 本地文档 RAG 问答

本项目从本地文档构建 Chroma 向量索引，根据问题检索相关内容，并调用聊天模型生成带来源引用的回答。支持两种查询方式：

- `ask`：直接使用 BGE 向量检索结果生成回答。
- `ask-rerank`：先召回候选片段，再用 BGE Reranker 排序后生成回答。

两种查询方式共用文档、切块、Embedding、向量库和生成模型。默认直接检索返回 5 条；启用重排时先召回 20 条候选，再保留 5 条。

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
│       ├── generation.py
│       ├── web.py
│       └── static/         # 本地网页 HTML、CSS、JavaScript
├── data/                  # 本地知识库，不提交到 Git
├── models/                # 自行下载模型，不提交
├── chroma_db/             # 运行时索引，不提交
├── .cache/mineru/         # PDF 解析缓存，不提交
├── .venv/                 # uv 虚拟环境，不提交
├── .env.example           # 配置模板
├── data-manifest.example.json  # 文档登记模板
├── .gitignore
├── .python-version
├── docs/implementation-plan.md  # 企业版实施清单
├── pyproject.toml
├── uv.lock
└── README.md
```

## 用 uv 安装依赖

需要 `uv` 和 Python 3.13 或更新版本。`pyproject.toml` 已列出直接依赖，包括 `chromadb`、`sentence-transformers`、`torch`、`openai`、`python-dotenv`、`docling` 和 `requests`。

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

生成答案需要填写 `.env` 中的 `OPENAI_API_KEY`；使用兼容 OpenAI API 的服务时，可填写 `OPENAI_BASE_URL` 和 `OPENAI_CHAT_MODEL`。只查看检索结果时可以使用 `--retrieval-only`，此时不需要聊天模型 API Key。模型放在其他路径时，设置 `LOCAL_EMBED_MODEL_PATH`、`LOCAL_RERANK_MODEL_PATH`。

### 数据外发开关

默认禁止两类数据传输：`RAG_ALLOW_MINERU_UPLOAD=false` 禁止上传原始 PDF/PPT 到 MinerU，`RAG_ALLOW_LLM_CONTEXT_TRANSFER=false` 禁止把检索片段发送到聊天模型。首次解析未缓存的 PDF、需要 MinerU 备用解析的 PPT，或生成回答时，程序会提示设置对应开关。只有确认文档或片段可以交给该服务处理后，才在 `.env` 中把对应值改为 `true`。即使使用本地聊天模型，也需显式开启片段传输开关；仅检索不受影响。

这些开关只阻止默认调用，**不提供脱敏、审批或权限控制**。当前项目不应直接处理真实企业机密文档。企业版增量见 [实施清单](docs/implementation-plan.md)。

## 支持的文档格式

- `.txt`、`.md`：本地按 UTF-8 读取。
- `.docx`（Word）、`.xlsx`（Excel）：使用 Docling 在本地解析并导出 Markdown。
- `.pptx`、`.ppt`（PowerPoint）：先使用 Docling；如果解析失败或没有提取到文字，再将原文件交给 MinerU。Docling 处理旧版 `.ppt` 通常需要 LibreOffice，备用解析需要配置 `MINERU_API_KEY`。
- `.html`、`.htm`、`.csv`、`.epub`、`.odt`、`.ods`、`.odp`：同样由 Docling 在本地解析。
- `.pdf`：继续上传到 MinerU 官方在线 API，取得解析后的 Markdown。首次处理 PDF 前，把 MinerU Token 填入根目录 `.env` 的 `MINERU_API_KEY`。PDF 内容会发送给 MinerU，解析可能耗时并消耗账户额度。

MinerU 的 PDF/PPT 解析结果按文件内容缓存于 `.cache/mineru/`。文件未变化时，重建索引会复用缓存；文件修改后会重新解析。若想强制重新解析全部缓存文档，可清空 `.cache/mineru/` 后再次运行 `index`。旧版 `.doc`、`.xls` 不在当前支持列表中，可先转成 `.docx`、`.xlsx`。Docling 能保留更多文档结构，但检索质量仍受文档内容和切块方式影响。

## 建立索引

先在仓库根目录创建 `data/`，把上述格式的文档放进去。每个文档都要在 `data/manifest.json` 中登记，路径相对于 `data/`；可从模板开始：

```powershell
Copy-Item data-manifest.example.json data/manifest.json
```

模板中的 `example.md` 只是示例，需改成实际文件名；子目录使用 `/` 分隔，例如 `policies/leave.docx`。每条记录必须填写唯一的 `document_id`、负责人 `owner`、密级 `classification`（`public`、`internal`、`confidential`、`top_secret`）和布尔值 `approved`。只有人工确认可入库后才把 `approved` 设为 `true`。未登记、登记了不存在的文件、未获批准或绝密文档，都会在**解析任何文件前**终止本次建索引。修改或删除文档时也要同步更新登记文件。

`data/` 和其中的 `manifest.json` 都被 Git 忽略。这里的 `approved` 只是本地人工登记值，目前没有审批工作流或身份校验，不能作为企业正式审批凭据。该检查只对新建索引生效，已有 Chroma 索引不会自动撤回历史片段；清理历史内容需要先核对登记，再运行普通 `index` 重建，不能使用 `--keep-existing`。

登记完成后运行：

```powershell
uv run rerank-rag index
```

这会在 `chroma_db/` 建立或重建索引。修改文档、切块参数或 Embedding 模型后，应重新运行。`index --keep-existing` 会保留集合已有 Chunk，仅在明确需要增量写入时使用。

## 本地网页

建立索引后，在仓库根目录启动网页：

```powershell
uv run rerank-rag web
```

浏览器访问 `http://127.0.0.1:8765`。在网页中输入问题，可选择是否启用重排或仅查看检索片段。生成回答需要配置 `OPENAI_API_KEY`；仅检索不需要聊天模型 API Key。停止服务可在终端按 `Ctrl+C`。默认只监听本机；如果端口被占用，可用 `uv run rerank-rag web --port 8766` 更换。

## 检索文档

`--retrieval-only` 会打印命中的片段、来源和分数，不调用聊天模型。把示例问题换成与你放入 `data/` 的文档相关的问题：

```powershell
# 直接使用向量检索结果
uv run rerank-rag ask "你的问题" --top-k 5 --retrieval-only

# 召回候选后重排
uv run rerank-rag ask-rerank "你的问题" --candidate-k 20 --rerank-top-n 5 --retrieval-only
```

`vector_score` 为 `1 - Chroma cosine distance`；`rerank_score` 是重排模型原始分数，两者不能直接比较数值。索引不足 20 条时，实际候选数会更少。

## 生成回答

配置聊天模型 API Key 后，直接提问即可生成回答：

```powershell
uv run rerank-rag ask "你的问题" --top-k 5
uv run rerank-rag ask-rerank "你的问题" --candidate-k 20 --rerank-top-n 5
```

每次生成回答都会调用聊天模型，可能产生 API 费用。
