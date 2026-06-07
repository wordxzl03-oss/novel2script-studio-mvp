from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class LintRule:
    rule_id: str
    severity: Severity
    title: str
    description: str


@dataclass(frozen=True)
class LintFinding:
    rule_id: str
    severity: Severity
    path: str
    message: str
    suggestion: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
            "suggestion": self.suggestion,
        }


RULES: dict[str, LintRule] = {
    # E-level: blocking structural errors
    "E001": LintRule(
        rule_id="E001",
        severity="error",
        title="对白引用未注册角色",
        description="dialogue.speaker_id 必须出现在 characters 注册表中。",
    ),
    "E002": LintRule(
        rule_id="E002",
        severity="error",
        title="场景 id 缺失或重复",
        description="每个 scene 必须有唯一 scene_id。",
    ),
    "E003": LintRule(
        rule_id="E003",
        severity="error",
        title="对白角色不在该场出场人物表",
        description="dialogue.speaker_id 必须同时出现在当前 scene.characters 中。",
    ),
    "E004": LintRule(
        rule_id="E004",
        severity="error",
        title="场景缺少 source",
        description="每个 scene 必须绑定 source.chapter 与 source.para_range。",
    ),
    "E005": LintRule(
        rule_id="E005",
        severity="error",
        title="heading 引用了未注册地点",
        description="scene.heading.location_id 必须出现在 locations 注册表中。",
    ),
    "E006": LintRule(
        rule_id="E006",
        severity="error",
        title="short_drama 集缺少集末钩子",
        description="short_drama profile 下每集必须有 hook / ending_hook。",
    ),
    "E007": LintRule(
        rule_id="E007",
        severity="error",
        title="short_drama 单集估时超出设定上限",
        description="short_drama 每集估算时长不得超过设定上限。",
    ),

    # W-level: non-blocking quality risks
    "W001": LintRule(
        rule_id="W001",
        severity="warning",
        title="动作块过长",
        description="连续动作文本过长，疑似小说腔残留。",
    ),
    "W002": LintRule(
        rule_id="W002",
        severity="warning",
        title="动作描写不可直接拍摄",
        description="动作文本包含心理活动或抽象认知表达。",
    ),
    "W003": LintRule(
        rule_id="W003",
        severity="warning",
        title="单句台词过长",
        description="单句对白过长，可能影响表演和短剧节奏。",
    ),
    "W004": LintRule(
        rule_id="W004",
        severity="warning",
        title="幽灵角色",
        description="角色只出现一次，可能是别名未归一或无效角色。",
    ),

    # I-level: optimization hints
    "I001": LintRule(
        rule_id="I001",
        severity="info",
        title="场景缺少戏剧学标注",
        description="scene 缺少 objective 或 conflict，不阻断导出，但影响后续质量分析。",
    ),
}


def get_rule(rule_id: str) -> LintRule:
    try:
        return RULES[rule_id]
    except KeyError as exc:
        raise KeyError(f"Unknown lint rule id: {rule_id}") from exc