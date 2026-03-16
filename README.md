# SuperPaperAgent / 论文智能管理助手

SuperPaperAgent 是一个面向研究者的本地论文库管理与 AI 辅助阅读工具，支持导入 Zotero/其他来源的 CSV、PDF 切片、向量嵌入、AI 摘要与聊天检索等流程。

---

## 中文说明

### 功能概览

- 论文库：导入/浏览/筛选论文元信息，查看详情。
- 切片 Pipeline：从 PDF 提取文本并切分为 chunks，支持跳过已完成切片与停止任务。
- 向量嵌入 Pipeline：对 chunks 生成 embeddings 写入向量库，支持模型配置、跳过已嵌入内容与停止任务，并显示完成进度。
- AI 摘要 Pipeline：为论文生成多种形式的 AI 摘要/标签，支持跳过已摘要与停止任务。
- AI Chat：基于论文内容对话，支持多会话管理（新建/切换/删除/本地持久化）与工具调用提醒。
- 搜索：支持中文检索，并支持按标题/摘要/AI 总结等细粒度检索（灰度/持续完善中）。

### 环境依赖

- Python 3.9+（推荐使用虚拟环境）
- Node.js 18+ / npm
- 可访问的 LLM/Embedding 服务（本地或远程均可）

### 快速开始（推荐）

根目录提供启动脚本 `start_app.sh`，会自动：
1) 检测并创建 `.venv` 虚拟环境；2) 安装后端依赖；3) 安装前端依赖；4) 启动前后端并自动注入 API 地址。

```bash
./start_app.sh
```

指定端口：

```bash
# 后端端口 前端端口
./start_app.sh 9000 5100
```

默认地址：
- 后端：`http://localhost:8000`
- 前端：`http://localhost:5173`

### 手动启动（可选）

后端：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```bash
cd frontend
npm install
# 指定后端地址（可选）
VITE_API_BASE="http://127.0.0.1:8000" npm run dev -- --host 127.0.0.1 --port 5173
```

### 导入论文库

请在前端的 **Management / Import CSV** 面板中上传 CSV 完成导入（不建议使用命令行脚本导入，以避免字段/编码不一致导致的问题）。

目前仅对 **Zotero 默认导出 CSV** 做过完整测试；下面列出的字段也来自 Zotero 导出的默认表头。若你使用其他文献管理工具导出 CSV，请尽量对齐这些字段名称与含义。

CSV 需与 Zotero 导出结构兼容，表头为英文列名，常用字段如下（除 `Key` 外均可为空）：

- `Key`：条目唯一标识（必填，用于去重）
- `Item Type`：条目类型（如 `journalArticle`、`conferencePaper` 等，用于判断是否为论文）
- `Title`：标题
- `Author`：作者（Zotero 导出为单列字符串）
- `Publication Title`：期刊/会议名称
- `Publication Year`：年份
- `DOI`
- `Url`
- `Abstract Note`：摘要
- `Date`：出版日期（字符串）
- `Date Added`：加入库时间
- `Date Modified`：修改时间
- `Manual Tags`：手动标签
- `Automatic Tags`：自动标签
- `Extra`：额外信息
- `Notes`：笔记
- `File Attachments`：PDF/附件路径，多个以 `;` 分隔

建议使用 UTF‑8 编码（Zotero 默认导出即兼容）。导入完成后在 Papers 页面查看。

### 运行 Pipeline

在前端 Management/Pipeline 面板中可一键触发：

1. **PDF 切片**  
   - 自动统计需要处理/已跳过/失败数量  
   - 支持“跳过已切片 PDF”和“停止切片”

2. **向量嵌入**  
   - 支持在 Settings 中配置 Embedding API（见下文）  
   - 支持“跳过已嵌入 chunks”和“停止嵌入”  
   - 统计窗口显示向量库完成进度（embedded/total）

3. **AI 摘要/标签**  
   - 支持“跳过已摘要论文”（不勾选则重新生成）  
   - 支持停止摘要  
   - 统计窗口显示摘要完成进度

### Settings 配置

在前端 Settings 页填写并保存（写入后端数据库）：

**LLM（用于 Chat / 摘要）**
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_API_KEY`

**Embedding（用于向量嵌入）**
- `EMBED_BASE_URL`
- `EMBED_MODEL`
- `EMBED_API_KEY`
- `EMBED_COLLECTION`（向量库 collection 名称，默认已给出）

### 项目状态（灰度/实验性）

当前项目处于灰度功能阶段：
- 包含 Chat、中文检索、细粒度检索、Pipeline 组合流等在内的功能仍在快速迭代，可能存在意想不到的 bug 或边界情况。
- 欢迎提交 Issue/PR，一起完善体验与稳定性。

**RAG 说明**
- 当前默认聊天主路径为“规划器 + RAG 工具”：
  - 模型先分析用户需求并输出 `<tool_call>...</tool_call>`；
  - 再决定是否调用 `rag_search`（向量召回 -> 可切换重排 -> 带引用生成）；
  - 如不需要检索，可跳过数据库搜索直接给出简短回复。
- 当触发工具调用时，前端聊天区会显示工具调用提示；流式接口会返回 `tool_call` 事件。
- 已支持全库问答与单论文过滤问答、引用校验与自动修复、重启后任务恢复与评测门禁。

### RAG 新能力（本地）

- `POST /chat` 支持 `scope=library|paper`（默认 `library`），并支持 `paper_id` 过滤。
- 支持 `candidate_k`、`final_k`、`rerank`、`require_citations` 参数。
- 响应新增 `citations`（可追溯 chunk 引用）与 `retrieval_meta`（检索与时延元数据）。
- `retrieval_meta` 新增工具调用字段（如 `tool_call_invoked/tool_call_reason/tool_call_query/tool_call_scope`）用于审计本轮是否触发检索。
- 流式 `POST /chat`（`stream=true`）新增 `tool_call` SSE 事件，事件顺序通常为：`tool_call -> delta... -> final -> done`。
- 旧参数 `use_embeddings/send_full_text/max_chunks/top_k` 仍兼容一个版本周期；当使用旧参数时，`retrieval_meta` 会返回弃用提示（计划在 **2026-06-30** 后移除）。

### Pipeline 任务持久化与恢复

- 新增任务接口：
  - `GET /pipeline/jobs`
  - `GET /pipeline/jobs/{job_id}`
  - `POST /pipeline/jobs/{job_id}/resume`
- 任务状态持久化到数据库，服务重启后会将运行中任务标记为 `interrupted`，可从历史任务恢复。

### 质量评测与门禁

- 评测脚本：`backend/scripts/evaluate_rag.py`
- 默认评测集：`backend/eval/rag_eval_cases.json`
- 规模化评测集生成：`backend/scripts/generate_eval_cases.py`
- 基线报告目录：`backend/eval/reports/`
- 端到端冒烟脚本：`backend/scripts/smoke_rag_pipeline.py`

```bash
# 1) 基于本地论文库生成评测集（按论文抽样）
./.venv/bin/python backend/scripts/generate_eval_cases.py \
  --paper-cases 96 \
  --output backend/eval/rag_eval_cases_baseline_1500.json

# 2) 运行评测并产出基线报告
TS=$(date +%Y%m%d-%H%M%S)
./.venv/bin/python backend/scripts/evaluate_rag.py \
  --api-base http://127.0.0.1:8000 \
  --cases backend/eval/rag_eval_cases_baseline_1500.json \
  --workers 3 \
  --output backend/eval/reports/rag-baseline-${TS}.json \
  --report backend/eval/reports/rag-baseline-${TS}.md \
  --no-fail

# 3) 端到端冒烟（含中断恢复 + chat 引用检查）
./.venv/bin/python backend/scripts/smoke_rag_pipeline.py \
  --api-base http://127.0.0.1:8000 \
  --process-limit 50 \
  --embed-limit 500 \
  --summarize-limit 100 \
  --interrupt-stage embed_chunks
```

- 本地发布门禁（后端编译/测试 + 前端测试/构建 + 评测）：

```bash
./.venv/bin/python backend/scripts/release_gate.py --api-base http://127.0.0.1:8000
```

`release_gate.py` 默认行为：
- 优先使用 `backend/eval/rag_eval_cases_baseline_1500.json`（不存在时回退到 `backend/eval/rag_eval_cases.json`）。
- 每次评测自动写入 `backend/eval/reports/rag-baseline-<timestamp>.{json,md}`。
- 自动与上一份基线 JSON 报告对比，若出现指标回退则阻断发布。
- 默认执行前端 `test:run` 与 `build` 检查。

可选参数示例：

```bash
# 跳过“与上一份报告对比”
./.venv/bin/python backend/scripts/release_gate.py --skip-regression-check

# 跳过前端检查（仅用于本地临时排障）
./.venv/bin/python backend/scripts/release_gate.py --skip-frontend

# 指定评测集与并发参数
./.venv/bin/python backend/scripts/release_gate.py \
  --cases backend/eval/rag_eval_cases_baseline_1500.json \
  --eval-workers 3 \
  --eval-timeout 180
```

### 常见问题

- **后端启动报 `sqlmodel/uvicorn` 未找到**：请确保使用 `.venv` 中的 Python；推荐直接运行 `./start_app.sh`。
- **前后端无法互联**：确认后端 host 使用 `localhost/127.0.0.1`，并与前端 `VITE_API_BASE` 一致。
- **聊天历史看起来“丢了”**：当前聊天采用“多会话本地持久化”，请在 Chat 页顶部 `Session` 下拉框切换历史会话；`New Session` 会开启全新上下文。

---

## English Guide

### What It Is

SuperPaperAgent is a local paper library manager with AI-assisted reading. It supports importing Zotero-like CSV libraries, PDF chunking, vector embedding, AI summaries/tags, and paper-centric chat & search.

### Key Features

- Paper library: import/browse/filter metadata, view details.
- PDF Chunking pipeline: extract & split PDFs into chunks, with skip-existing and stop controls.
- Embedding pipeline: generate embeddings for chunks into a vector store, with model settings, skip-existing and stop, plus completion stats.
- AI Summary pipeline: generate multi-form summaries/tags, with skip-existing and stop, plus progress stats.
- AI Chat: converse over your papers with multi-session management (new/switch/delete/local persistence) and tool-call notices.
- Search: supports Chinese queries and fine-grained scopes (title/abstract/AI summaries), still evolving.

### Requirements

- Python 3.9+
- Node.js 18+ / npm
- Reachable LLM and Embedding endpoints (local or remote)

### Quick Start (recommended)

Use the root script `start_app.sh`. It will:
1) create `.venv` if missing, 2) install backend deps, 3) install frontend deps, 4) start both apps and wire API base automatically.

```bash
./start_app.sh
```

Custom ports:

```bash
./start_app.sh 9000 5100
```

Defaults:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

### Manual Start (optional)

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm install
VITE_API_BASE="http://127.0.0.1:8000" npm run dev -- --host 127.0.0.1 --port 5173
```

### Import Your Library

Please upload your CSV from the frontend **Management / Import CSV** panel.  
We do not recommend importing via CLI scripts to avoid header/encoding mismatches.

So far we have only fully tested **CSV exports from Zotero with default headers**. The field list below matches Zotero’s default columns. If you export CSV from other tools, please align your headers/semantics to these names as much as possible.

The CSV must follow Zotero‑compatible headers (English column names). Common fields are:

- `Key` (required): unique item id used for deduplication
- `Item Type`: item type (e.g., `journalArticle`, `conferencePaper`)
- `Title`
- `Author`
- `Publication Title`
- `Publication Year`
- `DOI`
- `Url`
- `Abstract Note`
- `Date`
- `Date Added`
- `Date Modified`
- `Manual Tags`
- `Automatic Tags`
- `Extra`
- `Notes`
- `File Attachments`: PDF/attachment paths, separated by `;`

UTF‑8 encoding is recommended (Zotero export is compatible by default). After importing, check the Papers page.

### Run Pipelines

On the Management/Pipeline panel you can trigger:

1. **PDF Chunking**  
   - shows to-process / skipped / failed counts  
   - supports “skip existing chunks” and “stop”

2. **Embeddings**  
   - configure embedding service in Settings  
   - supports “skip existing embeddings” and “stop”  
   - stats window shows vector store completion (embedded/total)

3. **AI Summaries/Tags**  
   - supports “skip existing summaries” (unchecked = re-generate)  
   - supports stop  
   - stats window shows summary completion

### Settings

Fill and save on the Settings page (persisted in backend DB):

**LLM (Chat / Summaries)**
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_API_KEY`

**Embedding**
- `EMBED_BASE_URL`
- `EMBED_MODEL`
- `EMBED_API_KEY`
- `EMBED_COLLECTION`

### Project Status (beta / canary)

This project is in a fast‑moving beta stage:
- Many features (including Chat, Chinese/fine‑grained search, and pipeline flows) may have unexpected bugs or rough edges.
- Issues and PRs are very welcome.

**RAG Notice**
- The default chat path now uses a planner + RAG tool flow:
  the model first outputs `<tool_call>...</tool_call>`, then decides whether to invoke `rag_search`.
- If retrieval is needed: vector retrieval -> optional rerank -> citation-grounded generation.
- If retrieval is not needed (small-talk/simple turns), the backend can skip DB retrieval for that turn.
- It includes lexical fallback, citation validation/repair, and persistent pipeline job resume after restart.
- Legacy chat fields (`use_embeddings/send_full_text/max_chunks/top_k`) remain temporarily for compatibility and are planned for removal after **2026-06-30**.

**Streaming events**
- Streaming `POST /chat` can now emit `tool_call` before answer deltas.
- Typical event order: `tool_call -> delta... -> final -> done`.
- `retrieval_meta` now includes planner/tool-call diagnostics (for example `tool_call_invoked`, `tool_call_reason`, `tool_call_query`).

### Contributing

PRs and Issues are appreciated. Please describe your environment and reproduction steps.

### License

MIT License
