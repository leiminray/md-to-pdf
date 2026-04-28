"""Tests for the Renderer ABC."""
from pathlib import Path

import pytest

from mdpdf.renderers.base import RenderContext, Renderer


def test_renderer_must_implement_render():
    with pytest.raises(TypeError):
        Renderer()  # type: ignore[abstract]


def test_render_context_carries_brand_pack_and_cache_root(tmp_path: Path):
    ctx = RenderContext(
        cache_root=tmp_path / "cache",
        brand_pack=None,
        allow_remote_assets=False,
        deterministic=False,
    )
    assert ctx.cache_root == tmp_path / "cache"
    assert ctx.brand_pack is None
    assert ctx.allow_remote_assets is False
    assert ctx.deterministic is False


def test_render_context_is_frozen(tmp_path: Path):
    ctx = RenderContext(
        cache_root=tmp_path,
        brand_pack=None,
        allow_remote_assets=False,
        deterministic=False,
    )
    with pytest.raises(AttributeError):
        ctx.cache_root = tmp_path / "other"  # type: ignore[misc]


class _Fake(Renderer[str, str]):
    name = "fake"

    def render(self, source: str, ctx: RenderContext) -> str:
        return source.upper()


def test_renderer_subclass_renders(tmp_path: Path):
    r = _Fake()
    ctx = RenderContext(
        cache_root=tmp_path, brand_pack=None,
        allow_remote_assets=False, deterministic=False,
    )
    out = r.render("hi", ctx)
    assert out == "HI"
