"""Tests for the Mermaid renderer chain selector (spec §2.1.4)."""
from pathlib import Path

import pytest

from mdpdf.errors import RendererError
from mdpdf.renderers.base import RenderContext
from mdpdf.renderers.mermaid_chain import select_mermaid_renderer


def _ctx(tmp_path: Path, *, deterministic: bool = False) -> RenderContext:
    return RenderContext(
        cache_root=tmp_path / "cache",
        brand_pack=None,
        allow_remote_assets=False,
        deterministic=deterministic,
    )


def test_kroki_selected_when_url_set(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("KROKI_URL", "http://kroki.example")
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_puppeteer._find_mmdc", lambda: None
    )
    r = select_mermaid_renderer(preference="auto", ctx=_ctx(tmp_path))
    assert r.name == "mermaid-kroki"


def test_puppeteer_selected_when_mmdc_present(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("KROKI_URL", raising=False)
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_puppeteer._find_mmdc", lambda: "/fake/mmdc"
    )
    r = select_mermaid_renderer(preference="auto", ctx=_ctx(tmp_path))
    assert r.name == "mermaid-puppeteer"


def test_pure_selected_when_others_unavailable(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("KROKI_URL", raising=False)
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_puppeteer._find_mmdc", lambda: None
    )
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_pure._import_mermaid", lambda: object()
    )
    r = select_mermaid_renderer(preference="auto", ctx=_ctx(tmp_path))
    assert r.name == "mermaid-pure"


def test_no_renderer_available_raises(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("KROKI_URL", raising=False)
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_puppeteer._find_mmdc", lambda: None
    )
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_pure._import_mermaid", lambda: None
    )
    with pytest.raises(RendererError) as ei:
        select_mermaid_renderer(preference="auto", ctx=_ctx(tmp_path))
    assert ei.value.code == "MERMAID_RENDERER_UNAVAILABLE"


def test_explicit_preference_overrides_auto(tmp_path: Path, monkeypatch):
    """`--mermaid-renderer kroki` forces Kroki even if no KROKI_URL env."""
    monkeypatch.delenv("KROKI_URL", raising=False)
    r = select_mermaid_renderer(
        preference="kroki", ctx=_ctx(tmp_path), kroki_url_override="http://k.example",
    )
    assert r.name == "mermaid-kroki"


def test_explicit_kroki_with_no_url_raises(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("KROKI_URL", raising=False)
    with pytest.raises(RendererError) as ei:
        select_mermaid_renderer(preference="kroki", ctx=_ctx(tmp_path))
    assert ei.value.code == "MERMAID_RENDERER_UNAVAILABLE"


def test_pure_preference_in_deterministic_mode_raises(tmp_path: Path):
    with pytest.raises(RendererError) as ei:
        select_mermaid_renderer(
            preference="pure", ctx=_ctx(tmp_path, deterministic=True),
        )
    assert ei.value.code == "RENDERER_NON_DETERMINISTIC"
