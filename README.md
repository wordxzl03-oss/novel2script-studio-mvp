# Novel2Script Studio

Novel2Script Studio 是一个面向网文 IP 改编的竖屏微短剧工作台。核心单位是 Episode, 不是 Scene。

系统采用 Evidence-RAG + Bounded Agent 架构, 将小说原文、故事圣经、人物关系、风格包、版本日志与人工覆盖记录组织为可检索证据, 并通过受控 AI 任务完成诊断、规划、生成、改写、评估与分叉。

AI 负责写, 代码负责证明, 界面负责让人掌控。

## 产品定位

本项目面向网文小说到竖屏微短剧的专业改编流程。用户上传小说后, 系统围绕 Episode 生成 IP 诊断、故事圣经、前 10 集分集大纲和前 3 集完整剧本。每段 AI 输出都必须落入结构化 schema, 并能追溯到原文证据或明确标记为短剧新增。

工作台不是一次性文本生成器。它强调三件事:

- 可信: 三类溯源校验让每段内容可追踪、可跳转、可导出。
- 可控: 使用者可以锁定内容、改写单集、创建分叉版本并合并回主线。
- 可交付: 最终导出短剧开发包, 包含故事圣经、人物关系、分集大纲、完整剧本、原文依据、改编日志、风险提示和备案材料草稿。

## V1 全量范围

V1 是完整竖屏短剧改编工作台, 不再以旧版场景级剧本生成链路作为产品边界。全量功能按 F1-F31 实现, 覆盖:

- 短剧项目数据模型与 Episode-first schema。
- 三类溯源、溯源徽标、多段来源绑定和原文高亮。
- Evidence-RAG + Bounded Agent 的 AI 编排层。
- IP 诊断、故事圣经、前 10 集规划、前 3 集剧本生成。
- 短剧 Linter、钩子、留存节点、策划标记层和分集节奏板。
- 集级改写、锁定项、四维忠实度、四层语义 Diff 和改编日志。
- 集级分叉、方向弹窗、版本卡对比与合并。
- 风格包、内容分层、开发包导出、风险提示和服务端 Key 基础设施。

旧 `backend/app/schema/models.py` 保留为 legacy screenplay schema, 继续服务已有测试和旧 `/api/generate` 链路。V1 新模型放在 `backend/app/schema/short_drama.py`, 不再向 legacy schema 塞新对象。

## Legacy 兼容能力

当前仓库已有一条 legacy 场景级剧本流水线, 在 V1 改造期间继续保留:

- 粘贴 3 章以上小说文本并自动切章。
- 全局扫描角色、地点、别名和章节摘要。
- 逐章生成场景级结构化剧本。
- 使用 Pydantic schema 校验和自愈重试。
- 运行 legacy 剧本 Linter。
- 在前端展示角色注册表、地点注册表、场景列表、检查结果和 JSON 下载。

这些能力服务旧 `/api/generate` 和 legacy 测试基线。V1 工作会在新 schema、新文档和新 AI runtime 上推进, 不会把短剧全量对象混入 legacy schema。

## 核心工作流

```text
上传小说
-> 原文切块与证据索引
-> IP 诊断与故事圣经
-> 前 10 集分集大纲
-> 前 3 集完整剧本
-> 三栏分集工作台审阅
-> 集级改写或分叉
-> 忠实度 / Diff / Linter 校验
-> 合并版本并写入改编日志
-> 导出短剧开发包
```

W3 status: IP diagnosis, story bible generation, first-10 episode outlines,
first-3 complete episodes, short-drama linter checks, and retention/paywall
point suggestions are available in replay mode. UI workbench, rewrite/diff,
forking, export, and W7 retention visualization remain future waves.

所有涉及 AI 的诊断、生成、改写、分叉、评估与风险提示都必须经过 AI 编排层。没有 `RetrievalContext`、`ValidationReport` 和 `AITaskRun` 的 AI 输出不得进入正式项目状态。

F28 开发包导出是确定性汇总流程, 不经 LLM, 不设 Agent。导出可以读取已有 `AITaskRun` 摘要写入审计材料, 但不会为了凑 AI 流程而创建 `export_agent.py`。

## 技术亮点

本项目采用 Evidence-RAG + Bounded Agent 架构。Evidence-RAG 将小说原文、故事圣经、人物关系、风格包、版本日志与人工覆盖记录组织为可检索证据, 使每次生成、改写和分叉都能回到明确上下文, 且 AI 引用必须来自检索结果; Bounded Agent 将 IP 诊断、故事圣经构建、分集规划、单集剧本生成、忠实度评估、语义 Diff、版本分叉拆解为可校验任务节点。所有 Agent 都在 schema、三类溯源、短剧 Linter、locked_items 和 adaptation_log 约束下工作, 避免 LLM 黑箱生成。

工程纪律:

- 所有 LLM 调用只走 `LLMClient + AITask + Agent Orchestrator`。
- 支持 live / record / replay 三模式; 内置样例优先 replay。
- AI 输出必须落进 schema, 不以游离纯文本存在。
- 代码拥有 id、估时、成本、通过率、日志等确定性字段。
- 成本与 token 统计只能来自真实 `AITaskRun` 记录; replay 不计入成本。
- 一个 PR 只做一件事, 不破坏 legacy 测试基线。

## 本地运行

后端:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

前端:

```bash
cd frontend
npm install
npm run dev
```

无 Key 演示:

```bash
set DEMO_MODE=1
cd backend
uvicorn app.main:app --reload
```

服务端托管 Key 时, Key 只放在后端环境变量中。前端不需要也不能接触 `LLM_API_KEY`。

## 测试命令

后端测试统一使用:

```bash
PYTHONPATH=backend pytest backend/tests -v
```

Windows PowerShell:

```powershell
$env:PYTHONPATH="backend"; pytest backend/tests -v
```

前端被修改时再运行:

```bash
cd frontend
npm run build
```

## 文档入口

- `docs/product-spec-v1.md`: V1 全量产品规格。
- `docs/technical-spec-v1.md`: Evidence-RAG、Bounded Agent、AI Runtime 和目录结构。
- `docs/schema-design.md`: schema 字段权威说明。
- `docs/api-design.md`: API 设计文档; W1 起随对外 API 填充。
- `docs/v1-definition-of-done.md`: V1 完成定义。

## 合规边界

本项目只做风险提示与材料草稿, 不判断合规/不合规, 不替代审查, 不出法律结论。

风险提示用于帮助创作者发现可能需要人工复核的内容。最终投放、备案、审查和法律判断必须由使用者及其专业团队完成。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
