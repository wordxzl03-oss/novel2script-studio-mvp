__all__ = [
    "SourceLinkVerdict",
    "SourceValidationChange",
    "SourceValidationStepResult",
    "check_citation_consistency",
    "compute_compression_view",
    "compute_element_badges",
    "compute_highlight_anchors",
    "derive_badge_state",
    "lint_episode",
    "lint_outline",
    "run_source_validation_step",
    "validate_source_link",
]


def __getattr__(name: str):
    if name == "check_citation_consistency":
        from app.validation.citation_check import check_citation_consistency

        return check_citation_consistency
    if name in {
        "compute_compression_view",
        "compute_element_badges",
        "compute_highlight_anchors",
        "derive_badge_state",
    }:
        from app.validation import highlight

        return getattr(highlight, name)
    if name in {
        "SourceValidationChange",
        "SourceValidationStepResult",
        "run_source_validation_step",
    }:
        from app.validation import pipeline_step

        return getattr(pipeline_step, name)
    if name in {"SourceLinkVerdict", "validate_source_link"}:
        from app.validation import source_validation

        return getattr(source_validation, name)
    if name in {"lint_episode", "lint_outline"}:
        from app.validation import short_drama_linter

        return getattr(short_drama_linter, name)
    raise AttributeError(f"module 'app.validation' has no attribute {name!r}")
