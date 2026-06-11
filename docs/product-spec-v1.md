# 短剧改编工作台 · V1 全量规格(v1.2)

> 把网文小说改编成竖屏微短剧的专业工作台。核心单位是「集」(Episode),不是「场」。
> AI 负责写,代码负责证明,界面负责让人掌控。

> **v1.1 变更说明**:加入 AI 架构层——新增 A4(Evidence-RAG + Bounded Agent)、新增 B5(AI 运行对象与检索对象)、重写 F4(从 LLMClient 升级为 AI 编排层)、护城河 5→6 根、G 波次/H 测试矩阵/F 完成定义相应更新、新增附录 J(技术目录建议)。**功能清单仍为 F1–F31,无新增编号**;RAG/Agent 是贯穿 F2、F6、F7、F9、F10、F16、F18、F19、F22、F24、F29 的底层架构,不是新功能。

> **v1.2 变更说明**:按外部评审修正四个硬点——① DoD 第 3 条与 F28 导出的矛盾(导出不经 AI 编排层,但可读 AITaskRun 摘要写入导出包);② V1 全量模型改放 `backend/app/schema/short_drama.py`,旧 `models.py` 标为 legacy(B2 / F1 / F31 同步修改);③ F4 增加"先骨架、后接入"实现策略,防止 W0 一次性铺空壳;④ 引用一致性给 `invented_for_adaptation` 留出合法路径(A4 / B3 / DoD14 / H 同步)。另:F29 合规检索对象扩到短剧新增内容且风险依据允许指向剧本元素;新增附录 K(W0 PR 拆解,修正了评审稿中 RetrievalContext 与 AITaskRun 的依赖顺序,并补齐 F27/F30 基础与冒烟任务)。

---

## 0. 这份文档怎么读(先看这段)

**关于编号(F1–F31)**:全部 31 个功能都在首版范围内,没有"以后再做"的。编号只是为了引用方便,不代表谁更重要。

**关于 W0–W7**:这是**先做哪块、后做哪块**的施工顺序(按依赖关系排),**不是**说后面的可以不做。全部做完才算 V1 发布。中间不发半成品版本。

**每个功能有 5 段**:
- **功能意义**——这功能对使用者(编剧/制片/评委)有什么用,用大白话讲。
- **AI 应用**——AI 在这里具体干什么。
- **技术路径**——怎么实现,接口/数据怎么走。
- **创新性**——真实差异化程度,`★★★` 真创新 / `★★` 有特色 / `★` 行业通用,不吹。
- **V1 验收标准**——做到什么程度才算"完成",防止"功能都写了但每个都浅"。

**三条贯穿全局的机制(写在 A4 与第 2 节,所有功能都要遵守)**:
1. **证据绑定**——AI 给出的每个判断都要带「依据 + 把握度 + 是否人工锁定」。
2. **可改但留痕**——AI 的判断使用者都能手动改,但一改就自动记进改编日志。
3. **AI 必走编排层**——任何 AI 任务必须经 F4 编排层运行,带检索上下文与校验报告;没有 AITaskRun 记录的输出不得进入项目状态(见 A4/B5)。

> 说明:这份是重新生成的完整版(之前的工作文件被环境清掉了)。请和你自己存的 v1.0 对一遍,有遗漏的功能或改名告诉我补。

---

## A. 产品定位与边界

### A1 一句话定位
一个**网文 → 竖屏短剧**的改编工作台:上传小说,生成 IP 诊断和故事圣经,自动产出前 10 集大纲 + 前 3 集完整剧本,每一段内容都能追到原文出处;使用者可以对任意一集做受控改写、分出多个方向的版本、对比后选一版装回主线,最后导出一份可交给短剧团队的开发包。

### A2 工程纪律(全程必须守)
1. **所有 LLM 调用只走 F4 的 AI 编排层(`LLMClient` + AITask + Agent)**,业务代码禁止直连大模型 API,也禁止临时拼 prompt 绕过编排层。
2. **三模式**:live(真实调用)/ record(录制)/ replay(回放)。内置样例一律 replay,零成本秒回;使用者自定义生成才走 live。
3. **禁止伪造数据和指标**:任何"完成度""通过率""时长""token 用量"等数字只能来自真实运行(AITaskRun 记录,见 B5),不许手写假值。也不假装有 AI 的地方有 AI(例:导出 F28 是确定性流程,不冒充 Agent)。
4. **AI 输出必须落进 schema**,不允许以游离的纯文本存在;模型只填 schema 里它该填的字段。
5. **代码拥有的字段,prompt 不许让模型输出**(比如估时、忠实度终值、改编日志、id),由代码裁定。
6. **一次只做一件事**:一个功能一个 PR,不破坏已通过的测试基线。

### A3 死守的产品边界
- **只做竖屏微短剧**(免费短剧 / 网文 IP 改编)。**不做**电影、网剧、文艺片——全量已经很大,不能再兼容别的形态。
- **竖屏不是横屏的缩小版**:构图、节奏、单集时长、钩子密度都不同,风格包(F27)按竖屏规则来。
- **合规只做"风险提示 + 备案材料草稿"**:不判断合规/不合规,不替代广电审查,不出法律结论。这条要同时写在产品界面、导出文档、README 里(见 F29)。
- **市场数字不写死**:任何引用的市场规模/用户量数据(如外部分析里提到的行业体量)在用进对外材料前要重新核验口径,文档内部不当作产品事实。

### A4 AI 架构:Evidence-RAG + Bounded Agent

本产品不把大模型当作一次性文本生成接口,而是把 LLM 编排进一个**可检索、可校验、可回放、可人工接管**的短剧改编流程。整体 AI 架构由两层组成:

**1. Evidence-RAG:证据检索层。**
系统将小说原文(分段切块)、章节段落、人物/地点注册表、故事圣经、人物关系、重大揭示、风格包、改编日志、人工覆盖记录统一组织为可检索证据。每次生成、改写、分叉、忠实度评估或合规风险提示前,系统先检索与当前任务相关的证据,再把证据注入 AI 任务。RAG 在本产品中的作用不是"问答检索",而是**保证 AI 改编始终能回到明确的原文依据和项目状态**。

检索策略(重要,和通用 RAG 不同,这是产品立场):
- **确定性检索优先**:大多数任务(单集剧本 F10、改写 F16、分叉 F22)的"该看哪些原文"已经由 `source_ranges` / SourceLink 指定——按章节段落号直接取,可审计、可复现。
- **标签过滤检索**:上传小说时做一次索引,每个 chunk 抽取人物、事件标签、冲突类型、情绪基调等元数据,供 IP 诊断(F6)、故事圣经(F7)等需要"全书找东西"的任务按标签/关键词过滤。
- **向量(embedding)相似度检索为可插拔扩展,不进 V1 验收**。理由:本产品的卖点是反黑箱,确定性 + 标签检索可审计;向量相似度是另一个黑箱,等真实需要时再加,接口预留即可。
- **引用一致性(硬规则)**:凡是给出的 `source_basis` 必须来自本次检索结果,不得引用未检索到的段落;由代码校验,违者打回重生成。**例外**:`invented_for_adaptation`(短剧新增)类型允许没有原文 source_basis,但必须显式标记为短剧新增、不得伪称原文,并记录生成原因(SourceLink 的 invented 类型带可选 `reason` 字段)。这条规则约束的是"**凡引用必须真实**",不是"**必须有引用**"——不许为新增内容编造引用。
- **project_memory**:改编日志与人工覆盖记录也是可检索上下文——AI 不得重复建议使用者已否决/已人工覆盖过的改法。

**2. Bounded Agent:受控任务 Agent。**
系统不允许 Agent 自由行动或自行决定产品流程。每个 Agent 只负责一个明确任务,例如 IP 诊断、故事圣经生成、前 10 集规划、单集剧本生成、集级改写、集级分叉、忠实度评估、语义 Diff、版本卡生成。每个 Agent 都有固定输入、固定输出 schema、可调用工具、校验器、修复策略和日志记录。Agent 不能绕过 schema、不能绕过三类溯源校验、不能绕过 Linter 和 locked_items、不能直接写代码拥有字段。

本产品禁止把复杂任务压成一个大 prompt 一次性生成。所有复杂改编任务必须拆解为固定管线:

```
检索证据
→ 生成候选
→ Schema 校验
→ 三类溯源校验(含引用一致性)
→ 短剧 Linter
→ 必要时自愈修复
→ 生成结构化解释
→ 使用者确认 / 覆盖
→ 写入改编日志
```

因此,本产品的 AI 价值不在于"调用模型写剧本",而在于将 LLM 的开放式生成能力嵌入一个**可追溯、可校验、可版本化、可人工掌控**的短剧改编工作流。

---

## B. 数据模型

### B1 核心层级
```
小说原文 (SourceNovel)
└── 故事圣经 (StoryBible)
    └── 剧集 (Series)
        └── 集 (Episode)        ← 核心单位
            └── 场 (Scene)
                └── 节拍 (Beat)
                    └── 元素 (Element: action / dialogue / ...)
```

### B2 对象清单(都必须在 `backend/app/schema/short_drama.py`、API 响应、前端状态、导出 JSON 里一致存在)
> V1 全量模型放在新模块 `backend/app/schema/short_drama.py`;仓库里旧的 `models.py`(Screenplay/Scene 等剧本模型)保留为 **legacy schema**,老测试基线继续跑,**不再承接 V1 新对象**——避免单文件膨胀失控,也不破坏已通过的测试(A2 第 6 条)。
- `ShortDramaProject`——项目根,挂 source_novel / story_bible / series / profile / version 等。
- `StoryBible`——故事圣经(F7)。
- `Episode`——集,带 `logline / opening_hook / main_conflict / emotional_payoff / cliffhanger / source_ranges / retention_points / fidelity / quality_checks / visual_layer / forks / adaptation_log`。
- `Scene` / `Beat` / `Element`——场 / 节拍 / 元素(动作、对白、表演提示等)。
- `SourceLink`——三类溯源(F2)。
- `RetentionPoint`——留存/付费节点(F12)。
- `Fidelity`——四维忠实度(F18)。
- `VisualLayer`——竖屏视听层(F25)。
- `AdaptationLogEntry`——改编日志条目(F20)。
- `Registry`——角色/地点注册表 + `relationship_map`(人物关系)。
- **AI 运行对象**——`EvidenceChunk` / `RetrievalContext` / `AITaskRun` / `AgentRun`(见 B5)。

### B3 通用机制一:证据绑定(EvidenceMeta)
所有"推断性判断"——故事圣经各项、IP 诊断各项、人物关系、重大揭示、合规风险、成本风险、忠实度——都挂一组元数据:
```
evidence: {
  source_basis: SourceLink[]   # 凭哪些原文得出
  confidence:   float          # 模型把握度 0–1
  is_inferred:  bool           # 是原文有的, 还是推断/新增的
  user_locked:  bool           # 使用者是否锁定为人工确认
}
```
作用:让"全量功能"变可信。一个判断要么有原文依据,要么明确标成"推断/新增",不允许黑箱下结论。**v1.1 起加一条硬约束:给出的 `source_basis` 必须来自该次任务的检索结果;`invented_for_adaptation` 项允许 source_basis 为空,但 `is_inferred` 必须为 true 且显式标记为短剧新增(见 A4 引用一致性)。**

### B4 通用机制二:可改但留痕(Override)
忠实度、风险等级、钩子强度、成本提示等非确定性判断,使用者都能手动覆盖;但任何覆盖都必须写入该集的 `adaptation_log`(谁、改了什么、原值→新值、原因)。这是"专业工作台"和"黑箱评分器"的分界线。覆盖记录同时进入 project_memory,供后续 AI 任务检索(A4)。

### B5 通用机制三:AI 运行对象与检索对象

为避免 AI 调用游离在业务流程之外,V1 增加统一的 AI 运行对象和检索对象。所有 AI 任务必须经过这些对象,不允许业务代码临时拼 prompt 后直接调用模型。

**1. EvidenceChunk:证据片段**——RAG 的基本检索单位,可来自小说原文、故事圣经、注册表、风格包、改编日志或人工覆盖记录。
```
EvidenceChunk {
  chunk_id: string
  source_type: "novel" | "story_bible" | "registry" | "profile" | "adaptation_log" | "override"
  source_ref: SourceLink | null
  text: string
  metadata: {
    chapter_id?: string
    para_range?: [number, number]
    episode_id?: string
    scene_id?: string
    character_ids?: string[]
    location_ids?: string[]
    event_tags?: string[]
    conflict_type?: string
    emotional_tone?: string
    source_hash?: string          # 与 F2 逐字比对联动
  }
}
```

**2. RetrievalContext:任务检索上下文**——每次 AI 任务运行前,系统先根据任务类型检索上下文。
```
RetrievalContext {
  task_name: string
  query: string
  filters: object
  evidence_chunks: EvidenceChunk[]
  locked_items: LockedItems
  profile_context: object
  project_memory: AdaptationLogEntry[]
}
```

**3. AITaskRun:AI 任务运行记录**——每次 AI 任务都记录一次,用于回放、调试、成本统计与质量评估。
```
AITaskRun {
  task_id: string
  task_name: string
  input_schema: string
  output_schema: string
  retrieval_context: RetrievalContext
  llm_mode: "live" | "record" | "replay"
  validation_report: ValidationReport
  repair_attempts: number
  usage: {
    prompt_tokens?: number
    completion_tokens?: number
    calls: number
  }
  status: "success" | "failed" | "repaired"
  created_at: string
}
```
`usage` 字段同时喂给 F30 的成本统计与熔断——预算数字来自真实记录,符合 A2"禁止伪造数据"。

**4. AgentRun:Agent 编排记录**——一个 Agent 可能包含多个 AI 任务(例:ForkAgent 依次执行方向解析、证据检索、候选生成、schema 校验、locked_items 校验、忠实度评估、语义 Diff、版本卡生成)。
```
AgentRun {
  agent_name: string
  project_id: string
  target_id: string
  steps: AITaskRun[]
  final_output_ref: string
  status: "success" | "failed" | "partial"
}
```

这些对象的目的不是增加复杂度,而是保证 AI 行为可追踪、可调试、可复现、可评估。**没有 `RetrievalContext`、`ValidationReport` 和 `AITaskRun` 的 AI 输出,不得进入正式项目状态。**

---

## C. 六根护城河(短剧版)

1. **校验过的溯源,不是声称的溯源**——三类溯源 + 代码逐字比对(F2/F3/F14)。
2. **Evidence-RAG + Bounded Agent 的受控 AI 工作流**——不是把小说丢给大模型一次性生成,而是先检索原文证据、故事圣经、人物关系、风格包、版本日志和人工覆盖记录,再由受控 Agent 分阶段完成诊断、规划、生成、改写、评估、分叉和导出辅助。AI 不自由行动,每一步都有 schema、校验器、修复策略和日志,且 AI 引用必须来自检索结果(A4/B5/F4)。
3. **集级版本化("短剧改编的 Git")**——任意一集可分出多个方向版本、对比、合并、留痕(F22/F23/F24)。
4. **四维忠实度 + 四层语义 Diff**——改了什么、改了多少、对原著忠不忠,都绑定到结构字段说清(F18/F19)。
5. **短剧结构是第一公民**——每集必须有开头钩子、主冲突、情绪爽点、集尾钩子,Linter 按短剧规则查(F5/F9/F11)。
6. **可插拔风格包**——竖屏短剧/女频逆袭/男频爽文等风格做成可扩展的"skill",同时驱动生成和 Linter(F27)。

---

## D. 功能清单 F1–F31

### F1 · 短剧项目数据模型
**功能意义**:整个产品的地基。让"一部小说改成的短剧项目"有一套统一、严格的结构,所有页面、接口、导出读的是同一份数据,不会各拼各的。
**AI 应用**:不直接用 AI;但所有 AI 的输出都必须填进这套 schema。
**技术路径**:Pydantic 严格模型(`extra="forbid"`),按 B1 层级在 **`backend/app/schema/short_drama.py`** 实现 B2 全部对象(含 B5 的 AI 运行对象);旧 `models.py` 保留为 legacy screenplay schema,不动老测试基线;新增字段时同一个 PR 同时改 `short_drama.py` 和 `docs/schema-design.md`。
**创新性**:★★(Episode 为核心、自带钩子/冲突/爽点/集尾字段的短剧专用 schema,比通用剧本 schema 更贴产品)。
**V1 验收标准**:上传小说 → 生成项目 JSON → 重新加载 → 字段一个不丢 → 所有页面能读同一份状态。
**实现波次**:W0

### F2 · 三类溯源校验(确定性)
**功能意义**:短剧常把好几章压成一集、合并重排,所以不能只做"逐字对照"。把每段内容标成三类:**直引原文 / 基于原文改写 / 短剧新增**,而且这个标注是代码校验过的,不是 AI 嘴上说的。
**AI 应用**:AI 提议每段属于哪一类、对应原文哪里。
**技术路径**:`SourceLink{ type: literal_quote|source_based|invented_for_adaptation, chapter, para_range, quote? }`;代码兜底——`literal_quote` 必须和原文逐字匹配,差一个字就降级或清空 quote;`source_based` 必须指向存在且可跳转的原文段落;`invented_for_adaptation` 不许伪称原文。**校验器由 F4 编排层在每次生成后强制调用;同时执行引用一致性检查——`source_basis` 必须 ⊆ 本次 RetrievalContext 的检索结果(A4)。**
**创新性**:★★★(本产品最硬的差异化,把"声称溯源"变成"校验溯源";v1.1 起从"生成后校验"推进到"生成前锁定可引用范围")。
**V1 验收标准**:① 直引错一个字,系统能识别并降级/清除;② source_based 能跳到原文段落;③ invented 在界面明确显示"短剧新增";④ 导出包保留溯源说明;⑤ 引用未检索段落的输出被打回。
**实现波次**:W1

### F3 · 溯源徽标(四态)
**功能意义**:在剧本旁边一眼看出每段内容"从哪来、可不可信"。
**AI 应用**:无(读 F2 的校验结果)。
**技术路径**:四种徽标——✓ 直引(校验通过)/ ≈ 基于原文 / ＋ 短剧新增 / ⚠ 待核(校验未过)。颜色用设计语言里的"墨/暗"系,不喧宾夺主。
**创新性**:★(展示层,价值在背后的 F2)。
**V1 验收标准**:每段都有徽标且与 F2 校验结果一致;点徽标能跳到对应原文或看到"新增"说明。
**实现波次**:W1

### F4 · AI 编排层(LLMClient + AITask + Agent Orchestrator)
**功能意义**:把 AI 从"调用一次大模型接口"升级为"可检索、可校验、可修复、可回放的任务系统"。所有生成、诊断、改写、分叉、评估都通过统一 AI 编排层完成;它是 A4 架构的落地处,也是让整套 AI 能力可测试、可演示、不烧钱的工程底座(内置样例零成本秒回,自定义才真花钱)。
**AI 应用**:所有 LLM 调用的统一入口。AI 不直接参与业务流程,而是以 AITask 或 Agent 的形式被调用。
**技术路径**:AI 编排层分三层——
1. `LLMClient`:live / record / replay 三模式(用 `messages + temperature` 哈希做录制键)、token 统计、模型接口适配、调用记录;`DEMO_MODE=1` 强制 replay。
2. `AITask`:单个 AI 任务,各带 input schema、output schema、prompt、校验器、repair 策略。V1 至少 8 个:IPDiagnosisTask、StoryBibleTask、EpisodeOutlineTask、EpisodeScriptTask、HookGenerationTask、EpisodeReviseTask、FidelityReviewTask、SemanticDiffTask;另有 ComplianceDraftTask 服务 F29。
3. `Agent Orchestrator`:多步骤任务编排。V1 至少 6 个 Agent:DiagnosisAgent(F6)、StoryBibleAgent(F7)、EpisodePlannerAgent(F9)、EpisodeWriterAgent(F10)、ReviseAgent(F16,内部调用 CriticAgent 做忠实度评估 + 语义 Diff)、ForkAgent(F22,固定状态机:parse_directions → retrieve_context → generate_candidates → validate → build_version_cards → save_forks)。版本卡对比由 CompareAgent 汇总既有产物(F24)。**导出(F28)是确定性汇总流程,不设 Agent、不经 LLM——不为凑数假装有 AI。**
所有 Agent 都是 bounded agent:只能调用系统授权工具,不能自由决定流程,不能绕过 schema、三类溯源、Linter、locked_items 或 adaptation_log。风格包(F27)经检索层统一注入。
**实现策略(先骨架、后接入)**:W0 先实现 AITask / AITaskRun / RetrievalContext / AgentRun 的统一运行骨架并接好 LLMClient,且必须接通**一个**最小端到端任务(replay 模式、fixture 证据即可)证明链路真实跑通;具体业务 Agent 自 W2 起按波次逐个接入(W2 接 DiagnosisAgent / StoryBibleAgent,W3 接 EpisodePlannerAgent / EpisodeWriterAgent,W5 接 ReviseAgent / CriticAgent,W6 接 ForkAgent / CompareAgent;PR 拆解见附录 K)。**禁止在 W0 一次性铺设全部 Agent 空壳。**
**创新性**:★★★(引用一致性门控 + 全链路 AITaskRun 留痕,把"调用 API"升级为受控 AI 工作流;这是本产品区别于普通 AI 剧本生成器的关键工程层)。
**V1 验收标准**:
1. **行为门槛(第一条,最重要)**:没有 RetrievalContext + ValidationReport + AITaskRun 的 AI 输出不得进入项目状态;Agent 输出必须先通过 schema 校验、溯源校验、Linter 或相应校验器才能入库。
2. 业务代码中不存在绕过 `LLMClient` 的模型调用(加测试扫描)。
3. 上述 8+ 个 AITask、6 个 Agent 可运行(数量是清单不是目的,第 1 条行为门槛才是验收核心)。
4. 每次 AI 调用都有 `AITaskRun` 记录,包含 input/output schema、retrieval_context、validation_report、repair_attempts、usage;usage 汇入 F30 成本统计。
5. replay 模式下,内置样例可稳定复现完整链路。
6. Agent 失败时返回结构化错误,不允许静默降级为纯文本结果。
**实现波次**:W0

### F5 · 短剧 Linter
**功能意义**:自动挑出"这不是普通剧本、是短剧"该守的硬规则,让生成结果不跑偏。
**AI 应用**:无(确定性规则);规则阈值由风格包提供。
**技术路径**:核心规则——某集无开头钩子 / 无集尾钩子 / 主冲突不清 / 角色或地点未注册 / 单集估时超区间 / 不可拍的心理描写 / 台词或动作块过长。阈值随 F27 风格包变(竖屏短剧的单场/单集时长比院线短得多)。Linter 作为 F4 管线中的固定校验步骤被强制调用。
**创新性**:★★(短剧专属规则集,比通用剧本 lint 更贴)。
**V1 验收标准**:在合法样例上规则真实触发(字段名要和 schema 一致,不能 linter 读 `scene_ids` 而模型写 `scenes`);每条告警能定位到具体集/场。
**实现波次**:W3

### F6 · IP 适配诊断
**功能意义**:上传小说后第一步先"体检"——这本书适不适合改短剧、强在哪、坑在哪,给使用者一个判断起点。
**AI 应用**:AI 通读后给出诊断各项 + 推荐风格包。**由 DiagnosisAgent 执行:先按标签/关键词检索全书证据(A4 标签过滤检索),再生成诊断各项。**
**技术路径**:默认流程为"上传 → IP 诊断 + 故事圣经 → 再进分集生成"。诊断至少含:短剧适配类型、核心冲突强度、主角欲望清晰度、压迫结构强度、连续反转潜力、竖屏表达适配度、制作成本风险、合规风险提示、推荐 Profile。每项带证据绑定(B3),依据必须来自检索结果。
**创新性**:★★(把"网文能不能改短剧"结构化,有产品价值)。
**V1 验收标准**:输出落进 schema(非纯文本);每个诊断项可见依据与把握度;能据此推荐一个 F27 风格包。
**实现波次**:W2

### F7 · 故事圣经(Story Bible)
**功能意义**:先立一份"项目宪法",让后面分出来的十几集不会人设崩、主线散。
**AI 应用**:AI 抽取/生成圣经各项。**由 StoryBibleAgent 执行,检索上下文含全书标签索引。**
**技术路径**:`StoryBible{ premise, core_hook, protagonist, antagonist, relationship_map, major_reveals, source_basis, confidence }`,每项带证据绑定。先做这一份再生成大纲。圣经本身入 Evidence 索引,供后续所有 Agent 检索。
**创新性**:★★(轻量但带证据绑定的圣经,服务于"不漂移")。
**V1 验收标准**:生成后可重载不丢字段;关系/揭示等项可见依据;使用者可锁定某项为人工确认(user_locked),锁定项后续生成不被覆盖。
**实现波次**:W2

### F8 · 多段来源绑定
**功能意义**:一集往往压缩了好几章。让"这一集来自原文哪几段"能完整记录,而不是只挂一段。
**AI 应用**:AI 提议每集的来源区间集合。
**技术路径**:`Episode.source_ranges: SourceRange[]`,每个 range = 章节 + 段落范围;与 F2 的 SourceLink 联动。`source_ranges` 同时是 A4 确定性检索的取数依据(F10/F16/F22 的检索上下文按它取原文段)。
**创新性**:★★(短剧压缩改编的刚需基础)。
**V1 验收标准**:一集绑定多段来源后,工作台能逐段跳转;导出包保留来源区间。
**实现波次**:W1

### F9 · 前 10 集大纲生成
**功能意义**:把一本小说自动拆成前 10 集的分集大纲——每集讲什么、钩子在哪、卡在哪结束。
**AI 应用**:AI 基于故事圣经生成 Episode 级大纲(不是逐章 scene)。**由 EpisodePlannerAgent 执行,检索上下文 = 故事圣经 + 全书标签索引。**
**技术路径**:Pipeline B(分集大纲),每集产出 logline / opening_hook / main_conflict / emotional_payoff / cliffhanger / source_ranges;过 F5 Linter。
**创新性**:★(行业有同类,价值在与圣经/溯源/Linter 串起来)。
**V1 验收标准**:任何一集缺 opening_hook / main_conflict / cliffhanger,**不算成功**(必须重生成或报错)。
**实现波次**:W3

### F10 · 前 3 集完整剧本生成
**功能意义**:把前 3 集写成可读的拍摄向剧本(场、节拍、动作、对白、表演提示)。
**AI 应用**:AI 基于该集大纲 + 锁定的原文上下文生成剧本。**由 EpisodeWriterAgent 执行,检索上下文 = 该集 source_ranges 锁定的原文段 + 圣经 + 风格包(确定性检索,A4)。**
**技术路径**:Pipeline C(单集剧本),输出 Scene/Beat/Element;每段带 SourceLink;过 Linter 与自愈校验。
**创新性**:★(生成本身通用,差异在溯源+结构约束)。
**V1 验收标准**:前 3 集生成后结构完整、可重载、每段有溯源徽标;违反短剧 Linter 核心规则的不算完成。
**实现波次**:W3

### F11 · 钩子生成器
**功能意义**:专门给某一集"换个更抓人的开头钩子或集尾钩子",不用重写整集。
**AI 应用**:AI 围绕指定位置生成多个候选钩子(HookGenerationTask)。
**技术路径**:**钩子生成 = 集级分叉(F22)的子模式**——只对 opening_hook 或 cliffhanger 做分叉,其余内容不动;复用方向弹窗与版本卡。
**创新性**:★★(把"钩子"做成可分叉、可对比的独立动作)。
**V1 验收标准**:能只分叉钩子而不改整集;候选钩子各自可对比、可选定合并、写日志。
**实现波次**:W6

### F12 · 留存 / 付费节点规划
**功能意义**:标出"观众容易跑的地方"和"适合放付费卡点的地方",帮编排节奏。
**AI 应用**:AI 提议各集的留存点/付费点及理由。
**技术路径**:`RetentionPoint{ episode, position, type: retention|payment, reason, evidence }`;必须在分集节奏板、单集工作台、导出包**三处都可见**(否则只是生成文本,不是功能)。
**创新性**:★★(把留存/付费工程化,但不承诺商业效果)。
**V1 验收标准**:留存/付费点在三处一致可见;参数旁注明"建议、不承诺转化效果"。
**实现波次**:W3(初版)/ W7(补全可视化)

### F13 · 三栏分集工作台
**功能意义**:改一集时的主操作台。左边是改编结构图(像 Git 分支),中间是原文,右边是对应剧本,三栏宽度可拖、可折叠。
**AI 应用**:无(承载其它功能)。
**技术路径**:左栏=改编图(暗/机器层),中栏=原文、右栏=剧本(纸/创作层);两条 `⋮` 分隔条拖拽调宽 + 双击重置 + 单栏折叠;宽度记在内存即可。三种模式 Tab:**对照模式**(三栏)/ **分叉对比模式**(F24,中右合并成宽对比区)/ **结构总览**(F26 全片)。≤1280px 靠折叠/模式切换保证可读,≤1000px 降级为纵向堆叠。
**创新性**:★★(三栏 + PS 式图层的心智,贴创作流程)。
**V1 验收标准**:三栏可拖可折叠;点左栏任一节点,中右栏同步切到那一集/场。
**实现波次**:W4

### F14 · 溯源高亮 / 压缩依据视图
**功能意义**:选中一集或一场,中栏原文里对应的段落自动高亮;一集压了多段时,能看清"这一集是由原文哪几块拼来的"。
**AI 应用**:无(读 F2/F8)。
**技术路径**:根据 SourceLink/source_ranges 在原文渲染高亮锚点;压缩视图把多段来源并列展示并标注关系(直引/改写/新增)。
**创新性**:★★(让溯源"看得见、点得到")。
**V1 验收标准**:选集/场→原文高亮准确;压缩视图能列出该集全部来源段并跳转。
**实现波次**:W1(底座)/ W4(视图)

### F15 · 策划标记层(备注层)
**功能意义**:使用者在改编结构图上随手贴标记——"这里是高潮""这段待改、等有灵感再弄"。是人写的备忘,不进 AI,跟着项目走。
**AI 应用**:标记可作为改写/分叉时的**软约束**(例:标了"高潮"的集,AI 别压缩)。
**技术路径**:在左栏 git 图节点上挂 `annotations{ flag: 高潮|起|承|转|合|待改|..., note }`;可按标记筛选(给我看所有"待改");与 F20 改编日志**分开**——日志是系统记"已经改了什么",备注层是人记"我还想改什么"。这些标记可叠成 F26 的"剧作节拍线"。软约束经 RetrievalContext 注入(A4)。
**创新性**:★★(把编剧脑里的节拍/待办显形,且能反哺 AI)。
**V1 验收标准**:节点可加旗标+文字、可筛选、随项目保存;标记能作为软约束传入改写/分叉 prompt。
**实现波次**:W4

### F16 · 集级结构化改写
**功能意义**:对一整集做受控改写——"加强钩子""加强冲突""加强打脸/反转""压缩成本""更忠于原著"等,而不是漫无目的地重写。
**AI 应用**:AI 按指定改写目标 + 锁定项重写该集。**由 ReviseAgent 执行;检索上下文除该集原文段/圣经/风格包外,额外含 project_memory——不重复建议使用者已否决过的改法(A4)。**
**技术路径**:改写对象可为 集/场/前3集节奏/人物线;改写目标为枚举 + 自由文本;请求带 `locked_items`(F17);prompt 禁止输出代码拥有字段(估时/忠实度/日志)。改写产生的版本走 F22 的分叉/合并体系。
**创新性**:★★★(受控、结构化、可锁定的改编,是"工作台"而非"生成器"的核心)。
**V1 验收标准**:改写结果过整集校验;改写目标真实生效(可在 Diff 中看到对应变化);改写写入改编日志。
**实现波次**:W5

### F17 · 锁定项(locked_items)
**功能意义**:改写前先按住几样东西不让 AI 动——人物关系、核心秘密、集尾钩子、制作成本约束。
**AI 应用**:AI 改写时必须遵守锁定项。
**技术路径**:`locked_items: { relationships?, secrets?, cliffhanger?, production_cost? }` 随改写/分叉请求传入(进 RetrievalContext,B5);代码兜底校验(不只靠模型自觉)。
**创新性**:★★★(让 AI 改编"可控不脱缰",护城河关键)。
**V1 验收标准**:锁"核心秘密"→结果不得提前泄露;锁"低成本"→不得新增群演/复杂外景/特效;锁"人物关系"→关系结构不得无说明突变。违反即判失败。
**实现波次**:W5

### F18 · 四维忠实度
**功能意义**:改完一集,用四个维度量"改得离原著多远",而且每个分数都说得出理由。
**AI 应用**:AI 参与人物/剧情维度的评估并给理由;代码裁定能确定的部分。**由 FidelityReviewTask(CriticAgent)产出,理由必须引用检索到的证据。**
**技术路径**:
- `source_fidelity`——由三类溯源与逐字比对确定(偏确定性)。
- `character_fidelity`——基于 registry + relationship_map + 改写前后人物摘要,规则+LLM 评估,**须显示理由**。
- `plot_fidelity`——基于改写前后事件表(event list)的增删改判定,**须显示事件差异**。
- `adaptation_intensity`——综合压缩/重排/新增/重构指令与变更幅度。
- 使用者可手动覆盖,但覆盖写入 adaptation_log(B4)。代码有兜底规则(如直引已不逐字匹配 → 不能标 faithful)。
**创新性**:★★★(多维 + 有依据 + 可覆盖留痕,远超"较强/较弱"一句话)。
**V1 验收标准**:四维都有结果且每维可见依据/理由;非确定性维度可人工覆盖并留痕;代码兜底规则生效。
**实现波次**:W5

### F19 · 四层语义 Diff
**功能意义**:对比两版,不只看文字哪里不一样,还看**剧情事件、人物关系、短剧节奏**哪里变了。
**AI 应用**:LLM 辅助解释差异,但不允许只给泛泛总结。**由 SemanticDiffTask(CriticAgent)执行。**
**技术路径**:
- **文本 Diff**——确定性结构对比,必做。
- **剧情事件 Diff**——先抽取两版 event list,再比增删改。
- **人物关系 Diff**——比 relationship_map 中相关人物的关系变化。
- **短剧节奏 Diff**——比 opening_hook / main_conflict / emotional_payoff / cliffhanger / retention_points 的变化。
- 每个 diff 项**必须绑定到具体 schema 字段**,LLM 只解释、不只总结。
**创新性**:★★★(语义分层 diff,且每层落到结构字段,是真专业能力)。
**V1 验收标准**:四层都能产出且每项绑定到结构字段;无任何一层只输出"大致差不多"式总结。
**实现波次**:W5

### F20 · 改编决策日志
**功能意义**:这一集被谁、在什么时候、为什么、怎么改的,全程留痕,可回看。
**AI 应用**:无(系统记录)。
**技术路径**:`Episode.adaptation_log: AdaptationLogEntry[]`,每条含 时间/对象/指令(instruction)/原值→新值/原因/是否人工覆盖;改写、分叉、合并、覆盖都写入。`instruction` 字段为代码拥有,模型不输出。日志同时进入 project_memory 索引,供后续 AI 任务检索(A4)。
**创新性**:★(审计能力通用,但对"受控改编"必备)。
**V1 验收标准**:改写/分叉/合并/覆盖均产生日志条目;日志可重载、可在工作台查看。
**实现波次**:W5

### F21 · 低成本拍摄改写
**功能意义**:一键把一集往"更省钱拍"的方向改——少换景、少群演、少特效——同时尽量不丢核心冲突。
**AI 应用**:AI 按低成本目标改写,并报告成本相关变化。
**技术路径**:F16 改写的一个预设目标;与 F25 视听层、`production_cost_hint` 联动;改写后给出对比报告。
**创新性**:★★(把"省钱拍"做成可量化的改写动作)。
**V1 验收标准**:改写前后显示——场景数变化 / 群演需求变化 / 道具特效变化 / 核心冲突是否保留 / 成本风险是否下降。
**实现波次**:W6

### F22 · 集级分叉(数量可选)
**功能意义**:对某一集分出多个不同方向的版本来比较。**分叉是可选动作,不强制**;要不要分、分几个,使用者自己定。
**AI 应用**:AI 按使用者给的方向,生成 N 个独立版本。**由 ForkAgent 执行,固定状态机:parse_directions → retrieve_context → generate_candidates → validate → build_version_cards → save_forks;每步落 AITaskRun(B5)。**
**技术路径**:`POST /api/episode/{id}/fork`,请求带 `n: int` 和/或 `directions: string[]`;**后端把 N clamp 到 [2,5],默认 3**(N=1 就是单集改写 F16);每个版本独立过校验,存入 `episode.forks[]`,回显各自实际用的方向。
**创新性**:★★★("短剧改编的 Git",灵魂功能)。
**V1 验收标准**:N 在后端 clamp(前端限制不算);每版独立校验通过;版本存入 forks 且方向回显;状态机顺序可被测试验证。
**实现波次**:W6

### F23 · 分叉方向弹窗
**功能意义**:每次点分叉**必弹窗**,让使用者告诉 AI 每一版往哪改;不给方向就不开始生成。
**AI 应用**:AI 按弹窗里的方向展开各版本。
**技术路径**:两种输入(可混用)——① 预设方向轴(短剧专属:**爽点强度 / 忠实↔大胆 / 节奏快慢 / 成本高低 / 平台侧重 / 集尾走向**),选轴后 AI 自动展开成 N 个方向;② 自由文本,可逐版写(一行一版,行数与数量选择器联动)。映射到 F22 的 `directions`,超过 5 行截断。
**创新性**:★★★(每次分叉都由人指定方向,把控制权交回创作者)。
**V1 验收标准**:点分叉必弹窗;不填方向不生成;多行自由文本正确解析成逐版方向;响应回显实际方向。
**实现波次**:W6

### F24 · 版本卡对比与合并
**功能意义**:把分出来的几版并排比,每版一张"版本卡"(钩子/冲突/爽点/集尾/忠实度一目了然),选定一版装回主线。
**AI 应用**:无(读各版本结构;摘要 logline 可由 AI 生成辅助比较)。**版本卡字段由 CompareAgent 汇总既有产物(忠实度/Diff/Linter 结果),不重复生成。**
**技术路径**:进入"分叉对比模式"(F13),左栏 git 图保留作上下文,中右合并成宽对比区横排 N 列;每版版本卡展示关键短剧字段 + 四维忠实度;选定 → 合并回主线 → 左栏版本图更新 → 写 adaptation_log(原因)。
**创新性**:★★★(版本卡 + 合并 + 留痕,完成版本化闭环)。
**V1 验收标准**:选 E03 → 输入若干方向 → 生成多版 → 每版有版本卡 → 选一版合并 → 版本图更新 → 日志记录原因。
**实现波次**:W6

### F25 · 内容分层(编剧 / 导演 / 制片)
**功能意义**:同一场戏分图层看(像 PS):编剧只看干净的剧作;导演勾上"视听层"看竖屏构图建议;制片勾上"制片层"看成本/道具/顺场信息。各取所需。
**AI 应用**:导演层/制片层的建议按需由 AI 生成,且随风格包变(竖屏构图 ≠ 横屏)。
**技术路径**:
- **编剧层(底层,默认)**——动作(现在时白描)+ 对白 + 表演提示(括号,别滥用)。
- **视听层(可开关,按需生成)**——`VisualLayer`:竖屏画面重点、站位、情绪特写、关键道具、可拍场景、群演需求、成本提示。**限定为竖屏拍摄重点,不冒充专业电影分镜。**
- **制片层(可开关)**——目标/冲突/节拍、时长、道具、顺场信息。
**创新性**:★★★(把"图层"从 UI 贯穿到剧本内容本身,尊重编剧稿 vs 拍摄稿的行业分工)。
**V1 验收标准**:三层可独立开关;视听层内容随风格包变化;关闭时不污染编剧层视图。
**实现波次**:W4(编剧层)/ W7(视听+制片层补全)

### F26 · 分集节奏板(= 项目首页)
**功能意义**:项目的门面。一进来就是前 10 集的"分集板",每集一张卡,能看情绪/爽点/反转/成本/风险,能筛选、能看分叉标记。
**AI 应用**:无(汇总展示)。
**技术路径**:**设为默认首页**。结构:顶部=项目名/Profile/当前版本/导出按钮/风险总览;主体=E01–E10 Episode Board(表格 + 单集卡片 + 风险筛选 + 分叉标记 + 情绪/爽点/反转/成本/风险基础可视化);右栏=待处理问题;底部=最近改编日志。多轨曲线(人物热力/节奏/改编强度/质量标记)可简化视觉但不能缺席;F15 的标记可叠成剧作节拍线。
**创新性**:★★(短剧分集体检视图,把多条信息叠在一条时间线上)。
**V1 验收标准**:首页即显示前 10 集结构与风险;可按风险筛选;分叉过的集有标记;点卡片进单集工作台。
**实现波次**:W4(表格+基础可视化)/ W7(多轨曲线)

### F27 · 风格包架构(Profile / skill)
**功能意义**:小说语感 ≠ 短剧 ≠ 文艺片。把"风格"做成可插拔的包,换风格就换一套生成规范和检查规则;还能让使用者自己丢新风格进来。
**AI 应用**:生成/改写/分叉时注入对应风格包,作为模型的写作规范。注入经 RetrievalContext 的 `profile_context` 统一进行(B5),不允许各 prompt 自行拼接。
**技术路径**:借 SKILL.md 结构,每个风格包一个文件夹:① `style.md`(给模型读的文字规范:语感、句子节奏、对白习惯、禁忌);② `style.yaml`(机器参数:单场/单集时长区间、钩子节奏、对白密度、竖屏/横屏、是否默认开视听层)。**同时驱动 F5 Linter 按风格变规则**。内置至少 5 个:女频逆袭 / 男频爽文 / 悬疑反转 / 现实情感 / 漫剧·动态漫。开放用户自定义目录。
**创新性**:★★★(风格包同时驱动生成和校验,是原"film/series/short_drama 三态"的可无限扩展升级)。
**V1 验收标准**:至少 5 个内置风格包可用且各自改变生成与 Linter 规则;支持放入自定义风格包目录并生效。
**实现波次**:W0(基础)/ W7(补全内置包)

### F28 · 短剧开发包导出
**功能意义**:把工作台里的成果打包成一份能直接交给短剧团队的开发包,而不是只能在线上看。
**AI 应用**:无(汇总导出)。**导出为确定性流程,不设 Agent、不经 LLM(见 F4);可选附每集 AITaskRun 摘要供审计。**
**技术路径**:导出含——故事圣经 / 人物关系表 / 前 10 集分集大纲 / 前 3 集完整剧本 / 每集原文依据 / 改编日志 / 风险提示 / 备案材料草稿。同时导出结构化 JSON,且**可重新导入**(round-trip 不丢字段)。
**创新性**:★(交付物通用,但是"工作台"落地的关键)。
**V1 验收标准**:开发包 8 件套齐全;导出的 JSON 重新导入后字段无损。
**实现波次**:W7

### F29 · 备案材料辅助(风险提示)
**功能意义**:帮使用者起草备案需要的材料,并提示可能的内容风险——但只是辅助,不替你做合规判断。
**AI 应用**:AI 生成材料草稿 + 列出风险点(ComplianceDraftTask);每条风险的依据必须来自检索结果。
**技术路径**:输出备案材料草稿 + 风险提示清单,每条风险带依据(B3)。**检索对象不止原文**:含原文证据、当前剧本内容(短剧新增/改写段)、已合并版本与人工覆盖记录——AI 改写时新增出来的风险也必须检得到,不得只查原文。相应地,风险依据允许指向**剧本元素**(集/场/元素 id)而不只是原文 SourceLink,两类引用都必须真实存在、可跳转。**严守边界:只出草稿和风险提示,不判断合规/不合规,不替代广电审查,不出法律结论。**这条边界文案必须出现在产品界面、导出文档、README 三处。
**创新性**:★(有用但通用,价值在边界守得住)。
**V1 验收标准**:能产出材料草稿与风险清单;界面/导出/README 均含"不替代审查、不出法律结论"声明;不出现任何"合规/通过"式断言。
**实现波次**:W7

### F30 · 服务端托管 API Key(免登录直接用)
**功能意义**:使用者打开网页就能用,不用自己填 key。Key 在服务端,前端永远碰不到。
**AI 应用**:无(基础设施)。
**技术路径**:后端从环境变量读 key,所有 LLM 调用走后端代理;前端移除"填 key"入口。内置样例走 replay(零成本),自定义改写/分叉才走 live(你的 key)。**成本统计来自 AITaskRun.usage(B5)的真实记录,不另行手记。因为 key 在公开网页背后跑,以下为必做(不是可选)**:① 按 IP/会话限频 + 每日上限;② 输入上限(分叉 N 已 clamp、上传小说长度封顶);③ 超限给友好提示不直接 500;④ 可选总额熔断——烧到预算上限自动切回 replay-only,网页仍可用但不再花钱。
**创新性**:★★(零门槛体验,但成本/安全防护是重点)。
**V1 验收标准**:前端无 key 入口;限频、输入上限、超限提示均生效;触发熔断后自动降级 replay-only 且页面可用;成本面板数字可追溯到 AITaskRun。
**实现波次**:W0(基础)/ W7(权限分级补全)

### F31 · 文档与 API(README / schema-design / api-design)
**功能意义**:让协作者(和未来的你、Codex)能照着做,不靠口口相传。
**AI 应用**:无。
**技术路径**:`README`(去比赛化:删"参赛/72小时/P0/P1/P2"语境,定位为"短剧改编工作台 V1")、`docs/schema-design.md`(唯一权威字段说明,不能空,含 B5 AI 运行对象)、`docs/api-design.md`、`docs/technical-spec-v1.md`(AI 架构与目录结构,见附录 J)、本规格文档、`docs/v1-definition-of-done.md`。新增字段时同 PR 更新 schema 文档。
README 的技术亮点段按下面口径写(不写空话"本项目使用 RAG 和 Agent 技术"):
> 本项目采用 Evidence-RAG + Bounded Agent 架构。Evidence-RAG 将小说原文、故事圣经、人物关系、风格包、版本日志与人工覆盖记录组织为可检索证据,使每次生成、改写和分叉都能回到明确上下文,且 AI 引用必须来自检索结果;Bounded Agent 将 IP 诊断、故事圣经构建、分集规划、单集剧本生成、忠实度评估、语义 Diff、版本分叉拆解为可校验任务节点。所有 Agent 都在 schema、三类溯源、短剧 Linter、locked_items 和 adaptation_log 约束下工作,避免 LLM 黑箱生成。
**创新性**:★(基础工程卫生)。
**V1 验收标准**:schema-design.md 与 `backend/app/schema/short_drama.py` 字段一致且非空(legacy `models.py` 在文档中单独标注、不混入 V1 字段说明);README 无比赛/优先级语境且含上述技术亮点段;API 文档覆盖全部对外接口。
**实现波次**:W0(框架)/ W7(补全)

---

## E. 界面与设计

### E1 设计语言:纸 / 暗
- **纸 = 创作物**(原文、剧本):暖白底、衬线/类手稿质感,是摊在台面上的稿子。
- **暗 = 机器层**(改编图、徽标、校验、版本图):深色、克制,是分析/剪辑台。
- **明令禁止"AI 默认审美"**:不用纯白卡片堆叠、蓝紫渐变、Inter 通用字体那一套。

### E2 三栏分集工作台
见 F13。左(改编 git 图·暗)/ 中(原文·纸)/ 右(剧本·纸),可拖可折叠;三种模式:对照 / 分叉对比 / 结构总览。

### E3 产品视觉动线(7 步故事板)
上传小说 → 暗房显影式生成进度 → 拍摄稿登场 → 溯源高亮亮起 → 分叉分支图展开(N 条分支线,N 由作者定)→ 选定版本流入主线 → 回到全片结构图俯看全局。

### E4 内容分层
见 F25。编剧 / 视听 / 制片三图层,像 PS 一样开关。

### E5 全片结构可视化
见 F26。横轴=集序,多轨叠加(人物出场热力 / 节奏曲线 / 改编强度 / 质量标记 / 剧作节拍线),每轨对应一根护城河。

---

## F. V1 Definition of Done(全部满足才算完成)

1. F1–F31 均有前后端实现,或明确的 API/导出实现。
2. 所有 AI 输出都落进 schema,不以纯文本游离存在。
3. 所有涉及 AI 的诊断、生成、改写、分叉、评估与风险提示都必须经过 F4 的 AI 编排层(LLMClient + AITask + Agent);F28 导出为确定性汇总流程,不经 LLM、不设 Agent,但可读取 AITaskRun 摘要并写入导出包。
4. 每个 Episode 都具备 source_ranges、opening_hook、main_conflict、emotional_payoff、cliffhanger。
5. 三类溯源可视化、可跳转、可导出。
6. 集级改写支持 locked_items 且代码兜底。
7. 集级分叉支持版本卡、合并、日志,N 后端 clamp [2,5]。
8. 四维忠实度与四层 Diff 每项都绑定结构字段,无纯泛化总结。
9. 分集节奏板作为首页,显示前 10 集结构与风险。
10. 开发包可导出且 JSON 可无损重新导入。
11. 合规边界声明出现在界面、导出、README 三处。
12. 所有非确定性判断均"可覆盖且留痕"。
13. **每次 AI 调用都有 AITaskRun 记录(含 RetrievalContext 与 ValidationReport);没有这三样的输出不得进入项目状态。**
14. **引用一致性:AI 输出中给出的 source_basis 必须来自该次检索结果,违者被代码打回;`invented_for_adaptation` 允许无原文依据,但必须显式标记为短剧新增并记录生成原因(见 A4)。**

---

## G. 实现波次 W0–W7(施工顺序,不是发布优先级)

| 波次 | 主题 | 功能 | 目标 |
|---|---|---|---|
| W0 | AI 与数据底座 | F1, F4(LLMClient+AITask+Orchestrator), F27(基础), F30(基础), F31(框架) | 统一 schema、AI 编排层、profile loader(PR 拆解见附录 K) |
| W1 | 原文与证据 | F2, F3, F8, F14(底座), Evidence Index(chunk 切块+标签索引+确定性检索) | 所有内容能绑定来源,建立证据检索 |
| W2 | IP 资产层 | F6, F7, DiagnosisAgent, StoryBibleAgent | 用检索证据生成 IP 诊断与故事圣经 |
| W3 | 分集生成 | F9, F10, F5, F12(初版), EpisodePlannerAgent, EpisodeWriterAgent | 前10集大纲 + 前3集剧本,过短剧 Linter |
| W4 | 主工作台 | F13, F15, F26(表格+基础可视化), F25(编剧层) | 能浏览、修改、标记 |
| W5 | 改写系统 | F16, F17, F18, F19, F20, ReviseAgent, CriticAgent | 受控改写、锁定项校验、忠实度、语义 Diff、日志 |
| W6 | 分叉系统 | F11, F22, F23, F24, F21, ForkAgent, CompareAgent | 版本化工作流成立 |
| W7 | 交付与治理 | F25(视听/制片层), F26(多轨曲线), F28, F29, F30(权限), F31(完整) | 能交付给真实短剧团队(导出不设 Agent) |

---

## H. 测试矩阵(全量首版必须配,否则越做越散)

- Schema 测试(对象/字段/round-trip,含 B5 AI 运行对象)
- Legacy 兼容测试(旧 `models.py` 测试基线继续通过,新 schema 不破坏老链路)
- 三类溯源校验测试(直引错字降级、source 跳转、新增标记)
- LLM replay 测试(内置样例稳定复现完整链路)
- 前 10 集大纲生成测试(缺钩子/冲突/集尾即失败)
- 单集剧本生成测试
- 改写 locked_items 测试(锁定项不被破坏)
- 分叉 N clamp 测试(后端边界)
- 合并写日志测试
- 四维忠实度 / 四层 Diff 字段绑定测试(无纯总结)
- 开发包导出 round-trip 测试
- 合规边界文案测试(界面/导出/README 不出现越界断言)
- **Evidence-RAG 检索测试**:给定 episode / character / conflict 查询,能检索到正确原文段落与故事圣经条目。
- **RetrievalContext 测试**:每个 AI 任务运行前必须生成 retrieval_context,不允许空上下文直接生成。
- **AITaskRun 测试**:每次 AI 调用都记录 task_name、input/output schema、validation_report、usage。
- **Agent 状态机测试**:ForkAgent 必须按 parse_directions → retrieve_context → generate_candidates → validate → build_version_cards → save_forks 顺序执行。
- **Agent 越权测试**:Agent 不得直接写项目状态,必须通过 ProjectStore / schema 校验入库。
- **引用一致性测试**:AI 输出中给出的 source_basis 必须来自本次检索结果,不得引用未检索的原文段落;`invented_for_adaptation` 允许空 source_basis,但必须带显式"短剧新增"标记,缺标记即失败。

---

## I. 创新度速览

| 真创新 ★★★ | 有特色 ★★ | 行业通用 ★ |
|---|---|---|
| F2 三类溯源校验 | F1 短剧 schema | F3 徽标 |
| F4 AI 编排层 | F5 短剧 Linter | F9 大纲生成 |
| F16 集级结构化改写 | F6 IP 诊断 | F10 剧本生成 |
| F17 锁定项 | F7 故事圣经 | F20 改编日志 |
| F18 四维忠实度 | F8 多段来源 | F28 开发包导出 |
| F19 四层语义 Diff | F11 钩子生成器 | F29 备案辅助 |
| F22 集级分叉 | F12 留存/付费节点 | F31 文档 |
| F23 分叉方向弹窗 | F13 三栏工作台 | |
| F24 版本卡对比合并 | F14 溯源高亮 | |
| F25 内容分层 | F15 策划标记层 | |
| F27 风格包架构 | F21 低成本改写 | |
| | F26 分集节奏板 | |
| | F30 服务端 Key | |

**一句话**:差异化全集中在「AI 写 + 代码证明 + 创作者掌控」这条链上——三类溯源让改编可信,集级版本化让改编可控,忠实度/Diff 让改编透明,风格包让产品聚焦短剧;而 Evidence-RAG + Bounded Agent(A4/B5/F4)是这条链的运行时底座,保证 AI 的每一步都检索过、校验过、记录过。

> 注:F4 的三星不在 Agent 数量,而在"引用一致性门控 + AITaskRun 留痕 + bounded workflow"——堆 Agent 个数不加分,行为门槛(F4 验收第 1 条)才是创新所在。

---

## J. 附录:技术目录建议(写入 docs/technical-spec-v1.md)

```
backend/app/schema/
└── short_drama.py            # V1 全量短剧模型(F1/B2/B5);旧 models.py 为 legacy,不再承接新对象

backend/app/ai/
├── client.py                 # 可迁移现有 LLMClient,或继续从 app.llm.client 引用
├── task.py                   # AITask 基类
├── orchestrator.py           # Agent Orchestrator
├── prompt_registry.py
├── repair.py
├── validation.py
└── tasks/
    ├── ip_diagnosis.py
    ├── story_bible.py
    ├── episode_outline.py
    ├── episode_script.py
    ├── hook_generation.py
    ├── episode_revise.py
    ├── episode_fork.py
    ├── fidelity_review.py
    ├── semantic_diff.py
    └── compliance_draft.py

backend/app/rag/
├── chunker.py                # 原文切块 + 元数据抽取(上传时一次)
├── indexer.py                # 标签/关键词索引;embedding 接口预留但 V1 不实现
├── retriever.py              # 确定性检索(source_ranges)+ 标签过滤检索
├── evidence_store.py
├── project_memory.py         # 改编日志/人工覆盖的检索接口
├── profile_retriever.py      # 风格包注入
└── types.py                  # EvidenceChunk / RetrievalContext

backend/app/agents/
├── base.py
├── diagnosis_agent.py
├── story_bible_agent.py
├── episode_planner_agent.py
├── episode_writer_agent.py
├── revise_agent.py
├── fork_agent.py
├── critic_agent.py           # 忠实度 + 语义 Diff
└── compare_agent.py          # 版本卡汇总
```

> 注意:**没有 export_agent.py**——F28 导出是确定性流程,不经 LLM、不设 Agent(A2 第 3 条:不假装有 AI 的地方有 AI)。

---

## K. 附录:W0 PR 拆解(一个 PR 只做一件事,不破坏老测试基线)

> 评审稿给的 8 个 PR 方向正确,但有一处**依赖倒置**(B5 里 AITaskRun 内含 RetrievalContext,所以 rag/types 必须先于 ai/task),且未覆盖 W0 应有的 F27/F30 基础与"最小端到端冒烟任务"。修正并补齐如下:

| PR | 内容 | 对应 | 依赖 |
|---|---|---|---|
| PR-001 | README 去比赛化 + v1.2 产品定位 | F31 | — |
| PR-002 | 新增 docs/product-spec-v1.md(本规格入库) | F31 | — |
| PR-003 | 新增 docs/technical-spec-v1.md(A4 / B5 / F4 / 附录 J) | F31 | — |
| PR-004 | 新增 backend/app/schema/short_drama.py;旧 models.py 标 legacy,老测试不动 | F1 | — |
| PR-005 | 新增 backend/app/rag/types.py(EvidenceChunk / RetrievalContext) | B5 | PR-004 |
| PR-006 | 新增 backend/app/ai/task.py(AITask 基类 + AITaskRun 模型) | F4 | PR-005 |
| PR-007 | 新增 backend/app/agents/base.py(AgentRun + bounded 基类) | F4 | PR-006 |
| PR-008 | LLMClient 接线(迁移或继续引用 app.llm.client)+ **一个**最小端到端任务(replay 模式 + fixture 证据,产出含 RetrievalContext 与 ValidationReport 的完整 AITaskRun 并入库) | F4 | PR-006 |
| PR-009 | 风格包 loader 基础(读 style.md / style.yaml,经 profile_context 注入) | F27 基础 | PR-005 |
| PR-010 | 服务端 Key 代理 + 基础限频(前端无 key 入口,超限友好提示) | F30 基础 | PR-008 |
| PR-011 | 字段一致性核查:若存在 linter 读 `scene_ids` / 模型写 `scenes` 类不一致即修复,字段名以 schema 为准 | F5 前置 | PR-004 |

每个 PR 的验收都引用本文对应功能的"V1 验收标准"。**W0 完成的标志**:PR-008 跑通——replay 模式下,一条最小任务能产出含 RetrievalContext + ValidationReport 的 AITaskRun 并入库;此后 W2–W6 按 F4 的"先骨架、后接入"策略逐波接入业务 Agent,**不在 W0 铺设任何业务 Agent 空壳**。