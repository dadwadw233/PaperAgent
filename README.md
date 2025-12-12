# SuperPaperAgent / 论文智能管理助手

SuperPaperAgent 是一个面向研究者的本地论文库管理与 AI 辅助阅读工具，支持导入 Zotero/其他来源的 CSV、PDF 切片、向量嵌入、AI 摘要与聊天检索等流程。

本 README 为中英文双语。中文在前，英文在后。

---

## 中文说明

### 功能概览

- 论文库：导入/浏览/筛选论文元信息，查看详情。
- 切片 Pipeline：从 PDF 提取文本并切分为 chunks，支持跳过已完成切片与停止任务。
- 向量嵌入 Pipeline：对 chunks 生成 embeddings 写入向量库，支持模型配置、跳过已嵌入内容与停止任务，并显示完成进度。
- AI 摘要 Pipeline：为论文生成多种形式的 AI 摘要/标签，支持跳过已摘要与停止任务。
- AI Chat：基于论文内容对话（当前仍处于灰度阶段，见下文“项目状态”）。
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
- 当前向量嵌入与向量库构建已可用，但端到端 RAG（检索增强生成）的完整体验仍未完全完成。  
- 后续会逐步把检索、引用、对话上下文等能力打通并提供可选开关。

### 常见问题

- **后端启动报 `sqlmodel/uvicorn` 未找到**：请确保使用 `.venv` 中的 Python；推荐直接运行 `./start_app.sh`。
- **前后端无法互联**：确认后端 host 使用 `localhost/127.0.0.1`，并与前端 `VITE_API_BASE` 一致。

---

## English Guide

### What It Is

SuperPaperAgent is a local paper library manager with AI-assisted reading. It supports importing Zotero-like CSV libraries, PDF chunking, vector embedding, AI summaries/tags, and paper-centric chat & search.

### Key Features

- Paper library: import/browse/filter metadata, view details.
- PDF Chunking pipeline: extract & split PDFs into chunks, with skip-existing and stop controls.
- Embedding pipeline: generate embeddings for chunks into a vector store, with model settings, skip-existing and stop, plus completion stats.
- AI Summary pipeline: generate multi-form summaries/tags, with skip-existing and stop, plus progress stats.
- AI Chat: converse over your papers (currently in beta; see “Project Status”).
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
- Embedding + vector store building works today, but full end‑to‑end RAG is not fully integrated yet.
- We will progressively connect retrieval, citations, and chat context, and expose optional toggles.

### Contributing

PRs and Issues are appreciated. Please describe your environment and reproduction steps.

### License

MIT License
