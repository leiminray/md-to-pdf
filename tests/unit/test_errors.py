"""Tests for the MdpdfError hierarchy."""
import pytest

from mdpdf.errors import (
    BrandError,
    FontError,
    MdpdfError,
    PipelineError,
    RendererError,
    SecurityError,
    TemplateError,
)


def test_base_error_carries_code_and_messages():
    err = MdpdfError(
        code="TEST_CODE",
        user_message="something went wrong",
        technical_details="trace info",
    )
    assert err.code == "TEST_CODE"
    assert err.user_message == "something went wrong"
    assert err.technical_details == "trace info"
    assert err.render_id is None


def test_render_id_is_attachable():
    err = MdpdfError(code="X", user_message="y")
    err.render_id = "550e8400-e29b-41d4-a716-446655440000"
    assert err.render_id == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.parametrize("subclass", [
    BrandError, FontError, RendererError, SecurityError, TemplateError, PipelineError,
])
def test_subclasses_inherit_from_base(subclass):
    assert issubclass(subclass, MdpdfError)


def test_brand_error_codes_are_documented():
    err = BrandError(
        code="BRAND_NOT_FOUND",
        user_message="brand 'acme' not found in any registry layer",
    )
    assert err.code == "BRAND_NOT_FOUND"


def test_template_not_found_for_non_generic():
    err = TemplateError(
        code="TEMPLATE_NOT_FOUND",
        user_message="template 'quote' not found; supports only 'generic'",
    )
    assert err.code == "TEMPLATE_NOT_FOUND"


def test_str_includes_code():
    err = MdpdfError(code="X_FAILED", user_message="something failed")
    assert "X_FAILED" in str(err)


def test_str_format_is_bracket_code_space_message():
    """Lock the load-bearing log-line contract: `[<CODE>] <message>`."""
    err = MdpdfError(code="X", user_message="boom")
    assert str(err) == "[X] boom"


def test_args_contains_only_user_message():
    """Document the pickling contract: args[0] is the human-readable message."""
    err = MdpdfError(code="X", user_message="boom")
    assert err.args == ("boom",)


def test_renderer_error_codes_documented():
    """The RendererError codes are documented in the docstring."""
    from mdpdf.errors import RendererError
    docstring = RendererError.__doc__ or ""
    for code in [
        "MERMAID_TIMEOUT",
        "MERMAID_INVALID_SYNTAX",
        "MERMAID_RESOURCE_LIMIT",
        "MERMAID_RENDERER_UNAVAILABLE",
        "RENDERER_NON_DETERMINISTIC",
    ]:
        assert code in docstring, f"missing {code} in RendererError docstring"





def test_watermark_denied_code() -> None:
    err = SecurityError(code="WATERMARK_DENIED", user_message="Watermark denied by brand policy.")
    assert err.code == "WATERMARK_DENIED"
    assert isinstance(err, SecurityError)


def test_watermark_contrast_too_low_code() -> None:
    err = SecurityError(
        code="WATERMARK_CONTRAST_TOO_LOW",
        user_message="Watermark colour contrast ratio 1.02 is below minimum 1.05.",
    )
    assert err.code == "WATERMARK_CONTRAST_TOO_LOW"
    assert isinstance(err, SecurityError)


def test_audit_log_write_failed_code() -> None:
    err = PipelineError(
        code="AUDIT_LOG_WRITE_FAILED",
        user_message="Cannot write to audit log.",
        technical_details="/home/user/.md-to-pdf/audit.jsonl: Permission denied",
    )
    assert err.code == "AUDIT_LOG_WRITE_FAILED"
    assert isinstance(err, PipelineError)


def test_deterministic_violation_code() -> None:
    err = PipelineError(
        code="DETERMINISTIC_VIOLATION",
        user_message="Non-deterministic renderer 'pure' selected in --deterministic mode.",
    )
    assert err.code == "DETERMINISTIC_VIOLATION"
    assert isinstance(err, PipelineError)


def test_security_error_exit_code() -> None:
    """SecurityError maps to exit code 3 via _EXIT_BY_CODE."""
    from mdpdf.cli import _exit_code_for
    err = SecurityError(code="WATERMARK_CONTRAST_TOO_LOW", user_message="contrast too low")
    assert _exit_code_for(err) == 3


def test_pipeline_error_exit_code_for_audit_fail() -> None:
    from mdpdf.cli import _exit_code_for
    err = PipelineError(code="AUDIT_LOG_WRITE_FAILED", user_message="write failed")
    assert _exit_code_for(err) == 1


def test_security_error_docs_plan4_codes() -> None:
    """Error codes are documented in SecurityError docstring."""
    docstring = SecurityError.__doc__ or ""
    for code in ["WATERMARK_DENIED", "WATERMARK_CONTRAST_TOO_LOW"]:
        assert code in docstring, f"missing {code} in SecurityError docstring"


def test_pipeline_error_docs_plan4_codes() -> None:
    """Error codes are documented in PipelineError docstring."""
    docstring = PipelineError.__doc__ or ""
    for code in ["AUDIT_LOG_WRITE_FAILED", "DETERMINISTIC_VIOLATION"]:
        assert code in docstring, f"missing {code} in PipelineError docstring"
