# TODO / Backlog

## Pipeline
- [ ] CSV 导入：支持全量跑完、非论文处理确认（当前脚本已支持标记）。
- [ ] PDF 解析：本地运行 `process_pdfs` 处理全部论文，确认缺失/损坏 PDF 的报表。
- [ ] 嵌入：实现 chunk 嵌入脚本（可配置 baseURL/model/key），写入 Chroma 持久化存储；处理重试/超时。
- [ ] 摘要/评价/分类：批处理生成详细摘要、一句话总结、尖刻评价，以及领域/任务/关键词标签。
- [ ] 检索/RAG：关键词检索 + 向量检索 + 可选 rerank，整理成 API。
- [ ] 聊天：基于检索的对话接口，带对话记忆（自写历史表或检索式记忆）。

## Backend/API
- [ ] 配置接口：读取/写入模型 baseURL、model、api key、温度等。
- [ ] Papers API：列表/搜索、详情、标签、摘要获取。
- [ ] Chat API：对话、上下文记忆管理。

## Frontend
- [ ] 基础页：搜索列表（过滤器）、详情页（摘要/评价/标签）、聊天侧栏。
- [ ] 设置页：配置模型 endpoint/model/key/参数。

## Ops
- [ ] 环境变量样例 `.env.example`。
- [ ] README 运行指南。

## Nice to have
- [ ] 缺失 PDF 的自动下载（arXiv abs→pdf）。
- [ ] 简易任务队列/重试机制。
