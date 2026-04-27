"""Tests for the MdpdfError hierarchy (spec §7.5)."""
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
        user_message="template 'quote' not found; v2.0 supports only 'generic'",
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
    """The new Plan 3 RendererError codes are documented in the docstring."""
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
