"""Tests for the Puppeteer-based Mermaid renderer."""
import subprocess
from pathlib import Path

import pytest

from mdpdf.errors import RendererError
from mdpdf.renderers.base import RenderContext
from mdpdf.renderers.mermaid_puppeteer import PuppeteerMermaidRenderer


def _ctx(tmp_path: Path) -> RenderContext:
    return RenderContext(
        cache_root=tmp_path / "cache",
        brand_pack=None,
        allow_remote_assets=False,
        deterministic=False,
    )


def test_render_invokes_mmdc(tmp_path: Path, monkeypatch):
    """Successful mmdc subprocess produces a PNG at the cache target."""
    captured = {"args": []}

    def _fake_run(args, **kwargs):
        captured["args"] = args
        # Find the -o flag and write fake PNG content
        out_idx = args.index("-o")
        out_path = Path(args[out_idx + 1])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")

        class _R:
            returncode = 0
            stdout = b""
            stderr = b""
        return _R()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_puppeteer._find_mmdc", lambda: "/fake/bin/mmdc"
    )

    r = PuppeteerMermaidRenderer()
    out = r.render("graph TD\n A --> B", _ctx(tmp_path))
    assert out.exists()
    assert out.suffix == ".png"
    assert "/fake/bin/mmdc" in captured["args"]
    assert "-i" in captured["args"]
    assert "-o" in captured["args"]


def test_render_raises_when_mmdc_not_found(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_puppeteer._find_mmdc", lambda: None
    )
    r = PuppeteerMermaidRenderer()
    with pytest.raises(RendererError) as ei:
        r.render("graph TD\n A --> B", _ctx(tmp_path))
    assert ei.value.code == "MERMAID_RENDERER_UNAVAILABLE"


def test_render_raises_on_mmdc_timeout(tmp_path: Path, monkeypatch):
    def _fake_run(args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args, timeout=30)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_puppeteer._find_mmdc", lambda: "/fake/bin/mmdc"
    )

    r = PuppeteerMermaidRenderer()
    with pytest.raises(RendererError) as ei:
        r.render("graph TD\n A --> B", _ctx(tmp_path))
    assert ei.value.code == "MERMAID_TIMEOUT"


def test_render_raises_on_nonzero_exit(tmp_path: Path, monkeypatch):
    def _fake_run(args, **kwargs):
        class _R:
            returncode = 2
            stdout = b""
            stderr = b"mmdc syntax error"
        return _R()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_puppeteer._find_mmdc", lambda: "/fake/bin/mmdc"
    )

    r = PuppeteerMermaidRenderer()
    with pytest.raises(RendererError) as ei:
        r.render("graph TD\n A --> B", _ctx(tmp_path))
    assert "mmdc" in ei.value.user_message.lower()
