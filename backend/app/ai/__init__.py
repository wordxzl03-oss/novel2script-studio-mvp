__all__ = [
    "AITask",
    "AITaskResult",
    "AITaskRun",
    "SmokeRewriteOutput",
    "SmokeRewriteTask",
    "StructuredGenerationTask",
    "ValidationFinding",
    "ValidationReport",
]


def __getattr__(name: str):
    if name in {
        "AITask",
        "AITaskResult",
        "AITaskRun",
        "ValidationFinding",
        "ValidationReport",
    }:
        from app.ai import task

        return getattr(task, name)
    if name in {"SmokeRewriteOutput", "SmokeRewriteTask"}:
        from app.ai import smoke_task

        return getattr(smoke_task, name)
    if name == "StructuredGenerationTask":
        from app.ai.structured_task import StructuredGenerationTask

        return StructuredGenerationTask
    raise AttributeError(f"module 'app.ai' has no attribute {name!r}")
