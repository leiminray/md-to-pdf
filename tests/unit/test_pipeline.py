"""Tests for RenderRequest, RenderResult, RenderMetrics + Pipeline (spec §2.1)."""
import hashlib
import uuid
from pathlib import Path

import pytest

from mdpdf.errors import TemplateError
from mdpdf.pipeline import (
    Pipeline,
    RenderMetrics,
    RenderRequest,
    RenderResult,
    WatermarkOptions,
)


def test_render_request_defaults():
    req = RenderRequest(
        source="/tmp/in.md",
        source_type="path",
        output=Path("/tmp/out.pdf"),
    )
    assert req.brand is None
    assert req.brand_overrides == {}
    assert req.template == "generic"
    assert req.watermark.user is None
    assert req.deterministic is False
    assert req.locale == "en"
    assert req.audit_enabled is True


def test_render_request_is_frozen():
    req = RenderRequest(source="x", source_type="content", output=Path("/tmp/o.pdf"))
    with pytest.raises(AttributeError):
        req.brand = "acme"  # type: ignore[misc]


def test_render_request_template_only_generic_allowed_in_v20():
    # The dataclass itself accepts any string; allowlist enforcement happens
    # at validate-phase step 4 (Task 11). This test just confirms
    # the field exists and defaults to "generic".
    req = RenderRequest(source="x", source_type="content", output=Path("/o.pdf"))
    assert req.template == "generic"


def test_watermark_options_defaults():
    wm = WatermarkOptions()
    assert wm.user is None
    assert wm.level == "L1+L2"
    assert wm.custom_text is None


def test_render_metrics_construction():
    m = RenderMetrics(
        parse_ms=10,
        asset_resolve_ms=0,
        render_ms=200,
        post_process_ms=5,
        total_ms=215,
    )
    assert m.total_ms == 215


def test_render_result_construction():
    result = RenderResult(
        output_path=Path("/tmp/o.pdf"),
        render_id="550e8400-e29b-41d4-a716-446655440000",
        pages=3,
        bytes=12345,
        sha256="ab" * 32,
        warnings=[],
        metrics=RenderMetrics(0, 0, 0, 0, 0),
    )
    assert result.pages == 3
    assert result.bytes == 12345


def test_pipeline_rejects_non_generic_template(tmp_path: Path):
    pipeline = Pipeline.from_env()
    req = RenderRequest(
        source="x",
        source_type="content",
        output=tmp_path / "out.pdf",
        template="quote",  # not allowed in v2.0
    )
    try:
        pipeline.render(req)
    except TemplateError as e:
        assert e.code == "TEMPLATE_NOT_FOUND"
    else:
        raise AssertionError("expected TemplateError")


def test_pipeline_renders_content_string(tmp_path: Path):
    pipeline = Pipeline.from_env()
    req = RenderRequest(
        source="# Hello\n\nWalking skeleton.",
        source_type="content",
        output=tmp_path / "out.pdf",
    )
    result = pipeline.render(req)
    assert result.output_path.exists()
    assert result.pages == 1
    assert result.bytes > 0
    assert len(result.sha256) == 64
    expected_sha = hashlib.sha256(result.output_path.read_bytes()).hexdigest()
    assert result.sha256 == expected_sha


def test_pipeline_renders_path_source(tmp_path: Path):
    src = tmp_path / "in.md"
    src.write_text("# Title\n\nBody paragraph.\n")
    pipeline = Pipeline.from_env()
    req = RenderRequest(
        source=src,
        source_type="path",
        output=tmp_path / "out.pdf",
    )
    result = pipeline.render(req)
    assert result.output_path.exists()
    assert result.metrics.total_ms >= 0
    assert result.metrics.parse_ms >= 0
    assert result.metrics.render_ms >= 0


def test_pipeline_render_id_is_uuid_in_default_mode(tmp_path: Path):
    pipeline = Pipeline.from_env()
    req = RenderRequest(
        source="hi",
        source_type="content",
        output=tmp_path / "out.pdf",
    )
    result = pipeline.render(req)
    # parses without error
    parsed = uuid.UUID(result.render_id)
    assert str(parsed) == result.render_id
