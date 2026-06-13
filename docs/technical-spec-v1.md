# Novel2Script Studio · Technical Spec V1

> Scope: expand the V1 product spec sections A4, B5, F4, and appendix J into an engineering contract for W0 and later waves.
> This document defines architecture boundaries only. It does not replace `docs/product-spec-v1.md`.

## 1. 技术目标

V1 的技术目标是把旧的"小说 -> 场景级剧本"流水线升级为"网文 IP -> 竖屏短剧 Episode 工作台"。核心工程原则是:

1. AI 输出必须可检索、可校验、可回放、可审计。
2. V1 新模型与 legacy screenplay schema 分离。
3. 所有 AI 调用最终必须经过 `LLMClient + AITask + Agent Orchestrator`。
4. 每次 AI 任务都必须生成 `RetrievalContext`、`ValidationReport`、`AITaskRun`。
5. W0 只建立运行时骨架和一个 replay 冒烟任务, 不提前实现业务 Agent 空壳。
6. 成本、token、调用次数等统计只累计 `llm_mode=live` 的真实调用; `replay` 一律计零。

V1 的差异化不在于"能调用模型写剧本", 而在于让模型输出进入一个有证据、有 schema、有校验、有日志、有人工接管点的短剧改编系统。

## 2. Legacy 与 V1 模型边界

当前仓库已有 `backend/app/schema/models.py`, 它继续作为 legacy screenplay schema 使用。legacy 链路包含:

- `/api/generate`
- `Screenplay`
- legacy `Scene`
- legacy `Episode`
- 旧 pipeline 与 linter 测试基线

V1 新对象放在 `backend/app/schema/short_drama.py`。这里承载短剧工作台的领域模型:

- `ShortDramaProject`
- `SourceNovel`
- `StoryBible`
- `Series`
- `Episode`
- `Scene`
- `Beat`
- `Element`
- `SourceLink`
- `EvidenceMeta`
- `Registry`
- `RetentionPoint`
- `Fidelity`
- `VisualLayer`
- `AdaptationLogEntry`

边界规则:

1. 不把 V1 全量模型塞进旧 `models.py`。
2. 不删除 legacy schema 和 legacy tests。
3. 新增 V1 字段时同步更新 `docs/schema-design.md`。
4. PR-004 定义 V1 嵌套层级: `ShortDramaProject.series -> Series.episodes -> Episode.scenes -> Scene.beats -> Beat.elements`。
5. V1 不使用 `scene_ids` 作为 Episode 的主结构字段; legacy 若仍使用间接引用, 在 schema 文档中单独说明。

## 3. Evidence-RAG 架构

Evidence-RAG 不是通用问答检索, 而是短剧改编的证据约束层。它负责在 AI 任务运行前组织可引用上下文, 并限制 AI 输出的引用范围。

### 3.1 证据来源

证据可以来自:

- 小说原文 chunk
- 章节段落
- 故事圣经
- 角色/地点注册表
- 人物关系
- 重大揭示
- 风格包
- 改编日志
- 人工覆盖记录
- 当前剧本内容

F29 风险提示允许证据指向剧本元素, 因此 `EvidenceChunk.source_type` 需要覆盖 `script`。

### 3.2 检索策略

V1 优先实现可审计检索:

1. 确定性检索: 按 `source_ranges`、章节、段落号取证据。
2. 标签过滤检索: 按人物、地点、事件标签、冲突类型、情绪基调取证据。
3. project memory 检索: 把改编日志和人工覆盖记录注入后续 AI 任务。

向量相似度和 embedding 检索只保留扩展接口, 不列为 W0 或 V1 必做项。V1 的验收重点是反黑箱的确定性证据链。

### 3.3 引用一致性

AI 输出中的 `source_basis` 必须来自本次 `RetrievalContext.evidence_chunks`。如果输出引用了未检索到的原文段落, 代码必须打回。

例外路径:

- `SourceLink.type = invented_for_adaptation` 表示短剧新增。
- invented 内容可以没有原文 `source_range` 和 `quote`。
- 对应内容的 `EvidenceMeta.source_basis` 可以为空。
- `EvidenceMeta.is_inferred` 必须为 `true`。
- 必须显式记录新增原因, 不得伪称来自原文。

这条规则约束的是"凡引用必须真实", 不是"所有新增内容都必须伪造引用"。

## 4. Bounded Agent 架构

Bounded Agent 是受控任务编排, 不是自由行动 Agent。每个 Agent 只能负责一个明确业务任务, 并受固定输入、固定输出 schema、工具白名单、校验器、修复策略和日志约束。

### 4.1 Agent 行为边界

Agent 必须遵守:

1. 不能绕过 schema。
2. 不能绕过三类溯源校验。
3. 不能绕过引用一致性检查。
4. 不能绕过短剧 Linter。
5. 不能绕过 `locked_items`。
6. 不能直接写入项目状态。
7. 必须通过受控 store 或 schema validation 后入库。
8. 必须写入 `AgentRun` 和关联 `AITaskRun`。

### 4.2 W0 不创建业务 Agent 空壳

W0 只创建:

- `backend/app/agents/base.py`
- `AgentStep`
- `AgentRun`
- `BoundedAgent`

W0 不创建以下文件:

- `diagnosis_agent.py`
- `story_bible_agent.py`
- `episode_planner_agent.py`
- `episode_writer_agent.py`
- `revise_agent.py`
- `fork_agent.py`
- `critic_agent.py`
- `compare_agent.py`
- `export_agent.py`

业务 Agent 从 W2 起按波次接入。没有 Evidence Index 之前, 业务 Agent 只能空转, 所以不得提前铺空壳。

### 4.3 导出不是 Agent

F28 开发包导出是确定性汇总流程:

- 不经 LLM。
- 不设 Agent。
- 不创建 `export_agent.py`。
- 可以读取已有 `AITaskRun` 摘要写入导出包。

明确要求: 不创建 export_agent.py。

这条边界用于避免"没有 AI 的地方假装有 AI"。

## 5. AI Runtime 对象

AI Runtime 是 W0 的核心。它把一次模型调用升级为可检索、可校验、可回放、可审计的任务运行记录。

### 5.1 `backend/app/rag/types.py`

该模块定义 Evidence-RAG 的类型层。

`EvidenceChunk`:

- `chunk_id`
- `source_type`
- `source_ref`
- `text`
- `metadata`

`RetrievalContext`:

- `task_name`
- `query`
- `filters`
- `evidence_chunks`
- `locked_items`
- `profile_context`
- `project_memory`

结构要求:

- `RetrievalContext.evidence_chunks` 使用类型层约束 `min_length=1`。
- 不允许空上下文直接生成。
- `profile_context` 只通过 RetrievalContext 注入, 不允许各 prompt 自行拼接风格包。

### 5.2 `backend/app/ai/task.py`

该模块定义单个 AI 任务的运行骨架。

核心对象:

- `ValidationReport`
- `AITaskRun`
- `AITaskResult`
- `AITask`

`ValidationReport` 至少记录:

- 是否通过
- 错误列表
- 警告列表

`AITaskRun` 至少记录:

- `task_id`
- `task_name`
- `input_schema`
- `output_schema`
- `retrieval_context`
- `llm_mode`
- `validation_report`
- `repair_attempts`
- `usage`
- `status`
- `created_at`

`AITaskResult` 至少包含:

- 结构化 `output`
- 对应 `task_run`

PR-006 实现映射:

- `backend/app/ai/task.py` 只提供基础类型和 `AITask` 模板。
- `AITaskRun.retrieval_context` 使用 `backend/app/rag/types.py` 的 `RetrievalContext`。
- W0 不在该模块中实现具体业务 task、Agent 或真实 LLM 调用。

### 5.3 `backend/app/agents/base.py`

该模块定义 bounded agent 的基础类型。

核心对象:

- `AgentStep`
- `AgentRun`
- `BoundedAgent`

`BoundedAgent` 至少能校验 step 是否属于 `allowed_steps`。W0 不实现业务状态机。

### 5.4 `LLMClient` 接线

现有 `backend/app/llm/client.py` 已支持 live / record / replay。W0 不需要重写它, 但要通过 `AITask` 统一接入。

模式语义:

- `live`: 真实调用服务端配置的模型接口。
- `record`: 真实调用并保存录制响应。
- `replay`: 读取录制响应, 不发起网络模型调用。
- `DEMO_MODE=1`: 强制 replay。

### 5.5 usage 与成本口径

usage 记录与成本统计分离:

1. `AITaskRun.usage` 如实记录任务运行看到的 usage。
2. `llm_mode=replay` 的 usage 只用于链路验证。
3. 成本面板、限频额度、预算熔断只累计 `llm_mode=live`。
4. replay fixture 内的合成 usage 必须标记来源, 不得进入成本展示。

## 6. 目录结构

V1 建议目录:

```text
backend/app/schema/
└── short_drama.py

backend/app/rag/
├── __init__.py
├── types.py
├── chunker.py
├── indexer.py
├── retriever.py
├── evidence_store.py
├── project_memory.py
└── profile_retriever.py

backend/app/ai/
├── __init__.py
├── task.py
├── smoke_task.py
├── orchestrator.py
├── prompt_registry.py
├── repair.py
├── validation.py
└── tasks/

backend/app/agents/
├── __init__.py
└── base.py

backend/app/profiles/
├── __init__.py
├── loader.py
└── builtin/
```

W0 只落地必要文件:

- `backend/app/schema/short_drama.py`
- `backend/app/rag/types.py`
- `backend/app/ai/task.py`
- `backend/app/ai/smoke_task.py`
- `backend/app/agents/base.py`
- `backend/app/profiles/loader.py`

W0 不创建业务 Agent 文件。`backend/app/ai/tasks/` 可以等业务任务进入时再创建。

## 7. W0 最小链路

W0 完成标志不是"文件存在", 而是 replay 模式下跑通一条最小 AI runtime 链路:

```text
fixture EvidenceChunk
-> RetrievalContext
-> SmokeRewriteTask(AITask)
-> LLMClient replay
-> output schema parsing
-> ValidationReport
-> AITaskRun
-> AITaskResult
```

Smoke task 只用于证明运行时链路, 不是正式产品功能。

Smoke task 输入:

```json
{
  "instruction": "把这句话改成更短剧化",
  "text": "她站在雨里,终于意识到自己不能再退让。"
}
```

Smoke task replay 输出:

```json
{
  "rewritten_text": "她抬头看向雨幕:这一次,我不退了。",
  "source_basis": [],
  "is_inferred": true
}
```

验收要求:

- `RetrievalContext.evidence_chunks` 非空。
- `ValidationReport.passed = true`。
- `AITaskRun.llm_mode = replay`。
- `AITaskRun.status = success`。
- replay 文件缺失时测试失败, 不静默 fallback。
- 不调用真实 API。

## 8. 禁止事项

W0 禁止:

- 不改写完整前端工作台。
- 不删除旧 `/api/generate`。
- 不删除 legacy tests。
- 不把 V1 模型写进 legacy `models.py`。
- 不创建业务 Agent 空壳。
- 不创建 `export_agent.py`。
- 不接入向量数据库。
- 不把 embedding 检索写成 V1 必做。
- 不伪造完成度、通过率、token、成本、时长等指标。
- 不让 prompt 输出代码拥有的字段, 如 id、估时、最终成本、日志。
- 不把 replay usage 计入成本或限频额度。
- 不在导出流程里调用 LLM。

## 9. 测试策略

W0 测试矩阵:

1. Schema tests
   - V1 `ShortDramaProject` 最小项目可 validate。
   - 所有 V1 模型拒绝 extra fields。
   - legacy `models.py` 仍可导入。

2. RAG type tests
   - `EvidenceChunk` 可表达 novel/story_bible/registry/profile/adaptation_log/override/script。
   - `RetrievalContext.evidence_chunks` 为空时校验失败。
   - `profile_context` 可被结构化注入。

3. AITask tests
   - `AITaskRun` 包含 `RetrievalContext`、`ValidationReport`、usage、status。
   - `ValidationReport` 能表达错误和警告。
   - `AITaskResult` 同时返回 output 和 task_run。

4. Agent base tests
   - `AgentRun` 能记录多个 `AgentStep`。
   - `AgentStep` 能关联 `AITaskRun`。
   - `BoundedAgent` 拒绝未知 step。
   - 仓库不存在 `export_agent.py`。

5. Smoke replay tests
   - `DEMO_MODE=1` 下 smoke task 稳定运行。
   - 缺 replay fixture 时明确失败。
   - 不调用 live API。
   - replay usage 不计入成本统计。

6. Profile loader tests
   - 至少一个内置 profile 可列出。
   - `style.md` 和 `style.yaml` 可读取。
   - `profile_to_context` 返回 dict。

7. F30 base tests
   - demo mode 不要求 API key。
   - live 模式要求 API key、base URL、model 齐备。
   - 限频超限返回 429 和结构化 JSON。
   - replay 调用不计额度。

通用命令:

```bash
PYTHONPATH=backend pytest backend/tests -v
```

文档类 PR 的最小验收:

```bash
test -f docs/technical-spec-v1.md
grep -n "W0 最小链路" docs/technical-spec-v1.md
grep -n "不创建 export_agent.py" docs/technical-spec-v1.md
grep -n "RetrievalContext" docs/technical-spec-v1.md
grep -n "AITaskRun" docs/technical-spec-v1.md
```
