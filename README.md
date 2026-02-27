# 代码写的太烂了，得重写一遍
 **163Email-Agent** 是一个基于 **LangGraph** 框架构建的多智能体协同系统。最初为解决 163 邮箱日常杂乱邮件的自动化分拣而生，现已具备**结构化岗位解析**与 **RAG 简历匹配**能力

系统不仅能自主阅读、分拣邮件并起草回信，还能通过长短期记忆动态学习用户的写作风格与日程偏好，实现高度个性化 AI 体验。

 ## 核心特性
 - **人机回环 (HITL) 安检机制**
   - 绝不盲目发送邮件！在执行写信、预定会议等敏感操作前，通过 LangGraph 的 `interrupt` 机制挂起工作流。
   - 提供交互式“智能收件箱”，允许用户预览、修改 AI 草稿，确保 100% 的操作安全性。
- **动态记忆与偏好管理 (Long-term Memory)**
  - 基于 `InMemoryStore` 与本地 JSON 持久化构建档案库。
  - Agent 能够从用户（如：手动修改草稿、拒绝特定会议）的历史反馈中，自动总结并更新写作风格与日程偏好，实现“越用越懂你”。
- **复杂图工作流 (StateGraph)**
  - 实现了 `邮件分拣 -> 人工审核 -> 草稿生成 -> 记忆更新 -> 自动执行` 的完整闭环状态机。

## 项目架构 (Architecture)

```text
├── agents/             # Agent 核心逻辑
│   ├── prompts.py      # 系统 Prompt（包含分拣、求职信生成、记忆提取）
│   ├── tools.py        # 代理工具 (发送邮件、查询/安排日历等)
│   └── tool_prompt.py  # 工具描述文件
├── core/               # 底层框架支撑
│   ├── apimodels.py    # 大模型接口初始化 (支持 GPT-4o / Gemini)
│   ├── graph.py        # LangGraph 状态图定义与工作流编排
│   ├── memory.py       # 长期记忆的读写与 JSON 持久化逻辑
│   └── state.py        # 全局 State 结构定义设计 (Pydantic Models)
├── Ingestion/          # 数据摄入模块 (RAG)
│   ├── chroma_db/      # Chroma 本地向量数据库
│   └── ingest_resume.py# 简历文档处理脚本 (支持 PDF/Docx，执行向量化切分)
├── services/           # 外部服务集成
│   └── email_163.py    # 163 IMAP 邮箱连接、拉取与 HTML 文本清洗
├── text/               # 独立功能入口
    └── job_hunter.py   # RAG 求职自荐信生成专线脚本




