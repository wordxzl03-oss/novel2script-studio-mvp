# V1 Definition of Done

全部满足以下 14 条, 才算 V1 完成:

1. F1-F31 均有前后端实现, 或明确的 API/导出实现。
2. 所有 AI 输出都落进 schema, 不以纯文本游离存在。
3. 所有涉及 AI 的诊断、生成、改写、分叉、评估与风险提示都必须经过 F4 的 AI 编排层(LLMClient + AITask + Agent); F28 导出为确定性汇总流程, 不经 LLM、不设 Agent, 但可读取 AITaskRun 摘要并写入导出包。
4. 每个 Episode 都具备 source_ranges、opening_hook、main_conflict、emotional_payoff、cliffhanger。
5. 三类溯源可视化、可跳转、可导出。
6. 集级改写支持 locked_items 且代码兜底。
7. 集级分叉支持版本卡、合并、日志, N 后端 clamp [2,5]。
8. 四维忠实度与四层 Diff 每项都绑定结构字段, 无纯泛化总结。
9. 分集节奏板作为首页, 显示前 10 集结构与风险。
10. 开发包可导出且 JSON 可无损重新导入。
11. 合规边界声明出现在界面、导出、README 三处。
12. 所有非确定性判断均"可覆盖且留痕"。
13. 每次 AI 调用都有 AITaskRun 记录(含 RetrievalContext 与 ValidationReport); 没有这三样的输出不得进入项目状态。
14. 引用一致性: AI 输出中给出的 source_basis 必须来自该次检索结果, 违者被代码打回; `invented_for_adaptation` 允许无原文依据, 但必须显式标记为短剧新增并记录生成原因。
