"""Tests for the pure-Python Mermaid renderer (extras-gated)."""
from pathlib import Path

import pytest

from mdpdf.errors import RendererError
from mdpdf.renderers.base import RenderContext
from mdpdf.renderers.mermaid_pure import PureMermaidRenderer


def _ctx(tmp_path: Path, *, deterministic: bool = False) -> RenderContext:
    return RenderContext(
        cache_root=tmp_path / "cache",
        brand_pack=None,
        allow_remote_assets=False,
        deterministic=deterministic,
    )


def test_render_rejected_in_deterministic_mode(tmp_path: Path):
    r = PureMermaidRenderer()
    with pytest.raises(RendererError) as ei:
        r.render("graph TD\n A --> B", _ctx(tmp_path, deterministic=True))
    assert ei.value.code == "RENDERER_NON_DETERMINISTIC"


def test_render_when_mermaid_py_missing_raises(tmp_path: Path, monkeypatch):
    """If `mermaid` (the package) isn't installed, raise RENDERER_UNAVAILABLE."""
    monkeypatch.setattr("mdpdf.renderers.mermaid_pure._import_mermaid", lambda: None)
    r = PureMermaidRenderer()
    with pytest.raises(RendererError) as ei:
        r.render("graph TD\n A --> B", _ctx(tmp_path))
    assert ei.value.code == "MERMAID_RENDERER_UNAVAILABLE"


def test_render_calls_mermaid_module(tmp_path: Path, monkeypatch):
    """When mermaid-py is mocked-present, the renderer asks it for a PNG."""

    class _FakeMermaid:
        @staticmethod
        def to_png(source: str) -> bytes:
            return b"\x89PNG\r\n\x1a\nfake-payload"

    monkeypatch.setattr("mdpdf.renderers.mermaid_pure._import_mermaid", lambda: _FakeMermaid)

    r = PureMermaidRenderer()
    out = r.render("graph TD\n A --> B", _ctx(tmp_path))
    assert out.exists()
    assert out.read_bytes().startswith(b"\x89PNG")
