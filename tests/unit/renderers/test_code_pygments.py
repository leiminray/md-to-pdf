"""Tests for the Pygments-backed code renderer (spec §2.1.4)."""
from pathlib import Path

from mdpdf.markdown.ast import CodeFence
from mdpdf.renderers.base import RenderContext
from mdpdf.renderers.code_pygments import CodeRenderer, render_code_fence


def _ctx(tmp_path: Path) -> RenderContext:
    return RenderContext(
        cache_root=tmp_path, brand_pack=None,
        allow_remote_assets=False, deterministic=False,
    )


def test_renderer_returns_list_of_lines(tmp_path: Path):
    fence = CodeFence(lang="python", content="x = 1\ny = 2\n")
    out = render_code_fence(fence, _ctx(tmp_path))
    assert out.lines  # at least one line
    assert all(isinstance(ln, list) for ln in out.lines)


def test_python_keyword_gets_color(tmp_path: Path):
    fence = CodeFence(lang="python", content="def foo(): return 1\n")
    out = render_code_fence(fence, _ctx(tmp_path))
    flat = [frag for ln in out.lines for frag in ln]
    keyword_fragments = [f for f in flat if f.text.strip() == "def"]
    assert keyword_fragments
    # Keyword colour from the GitHub Light palette is a non-default colour
    assert keyword_fragments[0].color != "#1f2328"


def test_unknown_lang_falls_back_to_text_with_default_color(tmp_path: Path):
    fence = CodeFence(lang="totallymadeup", content="hello world\n")
    out = render_code_fence(fence, _ctx(tmp_path))
    flat = [frag for ln in out.lines for frag in ln]
    assert all(f.color == "#1f2328" for f in flat)


def test_empty_lang_treated_as_plain(tmp_path: Path):
    fence = CodeFence(lang="", content="just text\n")
    out = render_code_fence(fence, _ctx(tmp_path))
    assert out.lines


def test_truncates_at_max_lines(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MDPDF_FENCED_MAX_LINES", "3")
    fence = CodeFence(lang="python", content="\n".join(f"x = {i}" for i in range(10)))
    out = render_code_fence(fence, _ctx(tmp_path))
    assert out.truncated is True
    assert len(out.lines) <= 4  # 3 lines + the truncation indicator line


def test_truncates_at_max_chars(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MDPDF_FENCED_MAX_CHARS", "10")
    fence = CodeFence(lang="python", content="x = " + "a" * 100)
    out = render_code_fence(fence, _ctx(tmp_path))
    assert out.truncated is True


def test_class_renderer_callable_via_abc(tmp_path: Path):
    """CodeRenderer.render(...) is the Renderer-ABC-compliant entry point."""
    r = CodeRenderer()
    out = r.render(CodeFence(lang="python", content="x = 1"), _ctx(tmp_path))
    assert out.lines
