"""Tests for the Kroki Mermaid renderer (spec §2.1.4)."""
from pathlib import Path

import pytest

from mdpdf.errors import RendererError
from mdpdf.renderers.base import RenderContext
from mdpdf.renderers.mermaid_kroki import KrokiMermaidRenderer


def _require_cairo() -> None:
    """Skip cleanly if libcairo isn't installed (e.g. macOS w/o `brew install cairo`)."""
    try:
        import cairosvg
        cairosvg.svg2png(
            bytestring=b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'
        )
    except OSError as e:
        pytest.skip(f"libcairo not available: {e}")


def _ctx(tmp_path: Path) -> RenderContext:
    return RenderContext(
        cache_root=tmp_path / "cache",
        brand_pack=None,
        allow_remote_assets=False,
        deterministic=False,
    )


def test_render_posts_to_kroki(tmp_path: Path, monkeypatch):
    """Kroki POST → SVG response → cairosvg → PNG."""
    _require_cairo()
    import httpx

    captured: dict[str, str] = {}

    class _FakeResp:
        status_code = 200
        # Minimal SVG so cairosvg accepts it
        content = b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"></svg>'

        def raise_for_status(self) -> None:
            return None

    def _fake_post(url: str, content: bytes, headers: dict[str, str], timeout: float):
        captured["url"] = url
        captured["body"] = content.decode("utf-8")
        return _FakeResp()

    monkeypatch.setattr(httpx, "post", _fake_post)

    r = KrokiMermaidRenderer(base_url="http://kroki.example")
    out = r.render("graph TD\n A --> B", _ctx(tmp_path))
    assert out.exists()
    assert out.suffix == ".png"
    assert captured["url"].endswith("/mermaid/svg")
    assert "graph TD" in captured["body"]


def test_render_failure_raises(tmp_path: Path, monkeypatch):
    import httpx

    def _fake_post(*a, **k):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "post", _fake_post)

    r = KrokiMermaidRenderer(base_url="http://unreachable.example")
    with pytest.raises(RendererError) as ei:
        r.render("graph TD\n A --> B", _ctx(tmp_path))
    assert ei.value.code == "MERMAID_RENDERER_UNAVAILABLE"
    assert "kroki" in ei.value.user_message.lower()


def test_render_uses_cache_on_repeat(tmp_path: Path, monkeypatch):
    _require_cairo()
    import httpx
    call_count = {"n": 0}

    class _FakeResp:
        status_code = 200
        content = b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"></svg>'

        def raise_for_status(self) -> None:
            return None

    def _fake_post(*a, **k):
        call_count["n"] += 1
        return _FakeResp()

    monkeypatch.setattr(httpx, "post", _fake_post)

    r = KrokiMermaidRenderer(base_url="http://kroki.example")
    src = "graph TD\n A --> B"
    out1 = r.render(src, _ctx(tmp_path))
    out2 = r.render(src, _ctx(tmp_path))
    assert out1 == out2
    assert call_count["n"] == 1  # cache hit on second call
