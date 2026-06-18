from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai.task import AITaskRun

AgentStepStatus = Literal["pending", "success", "failed", "skipped"]
AgentRunStatus = Literal["success", "failed", "partial"]


class StrictAgentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentStep(StrictAgentModel):
    step_name: str = Field(min_length=1)
    task_run: AITaskRun | None = None
    status: AgentStepStatus
    message: str | None = None


class AgentRun(StrictAgentModel):
    agent_name: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    steps: list[AgentStep] = Field(default_factory=list)
    final_output_ref: str | None = None
    output: Any | None = None
    status: AgentRunStatus


class BoundedAgent:
    agent_name: str
    allowed_steps: list[str]

    def __init__(self, *, agent_name: str, allowed_steps: list[str]) -> None:
        if not agent_name:
            raise ValueError("agent_name is required")
        if not allowed_steps:
            raise ValueError("allowed_steps must not be empty")

        self.agent_name = agent_name
        self.allowed_steps = allowed_steps

    def validate_step_order(self, steps: list[str]) -> None:
        unknown_steps = [step for step in steps if step not in self.allowed_steps]
        if unknown_steps:
            raise ValueError(f"Unknown agent step(s): {', '.join(unknown_steps)}")

    def run(self, *args: object, **kwargs: object) -> AgentRun:
        raise NotImplementedError("BoundedAgent.run must be implemented by a concrete agent")
