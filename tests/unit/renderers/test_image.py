"""Tests for the image renderer."""
from pathlib import Path

import pytest
from PIL import Image as PILImage

from mdpdf.errors import SecurityError
from mdpdf.markdown.ast import Image as ASTImage
from mdpdf.renderers.base import RenderContext
from mdpdf.renderers.image import ImageRenderer

FIXTURES = Path(__file__).parent / "fixtures"


def _ctx(
    tmp_path: Path, *, allow_remote: bool = False, deterministic: bool = False,
) -> RenderContext:
    return RenderContext(
        cache_root=tmp_path / "cache",
        brand_pack=None,
        allow_remote_assets=allow_remote,
        deterministic=deterministic,
    )


def test_renders_small_png_as_is(tmp_path: Path):
    ast = ASTImage(src=str(FIXTURES / "small.png"), alt="small")
    out = ImageRenderer().render(ast, _ctx(tmp_path))
    assert out.path.exists()
    with PILImage.open(out.path) as img:
        assert img.size == (100, 100)


def test_downsamples_huge_raster_to_300dpi(tmp_path: Path):
    ast = ASTImage(src=str(FIXTURES / "large.png"), alt="large")
    out = ImageRenderer().render(ast, _ctx(tmp_path))
    assert out.path.exists()
    with PILImage.open(out.path) as img:
        # 3000px is above the 2400px threshold; downsampled.
        assert max(img.size) <= 2400


def test_renders_svg_via_cairosvg(tmp_path: Path):
    # cairosvg requires the libcairo system library; skip cleanly when
    # absent (e.g. macOS without `brew install cairo`). The renderer
    # itself is exercised by integration tests in CI environments where
    # libcairo is provisioned.
    try:
        import cairosvg
        _probe = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'
        cairosvg.svg2png(bytestring=_probe)
    except OSError as e:
        pytest.skip(f"libcairo not available: {e}")
    ast = ASTImage(src=str(FIXTURES / "icon.svg"), alt="icon")
    out = ImageRenderer().render(ast, _ctx(tmp_path))
    assert out.path.suffix == ".png"
    assert out.path.exists()
    with PILImage.open(out.path) as img:
        assert img.size[0] > 0


def test_remote_url_rejected_by_default(tmp_path: Path):
    ast = ASTImage(src="http://example.com/x.png", alt="x")
    with pytest.raises(SecurityError) as ei:
        ImageRenderer().render(ast, _ctx(tmp_path, allow_remote=False))
    assert ei.value.code == "REMOTE_ASSET_DENIED"


def test_remote_url_accepted_when_flag_set(tmp_path: Path, monkeypatch):
    """When --allow-remote-assets is set, remote fetching is attempted (mocked)."""
    ast = ASTImage(src="http://example.com/y.png", alt="y")
    # Mock httpx.get to avoid real network
    import httpx

    class _FakeResp:
        status_code = 200
        content = (FIXTURES / "small.png").read_bytes()

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(httpx, "get", lambda url, timeout=10.0: _FakeResp())
    out = ImageRenderer().render(ast, _ctx(tmp_path, allow_remote=True))
    assert out.path.exists()


def test_missing_local_file_raises(tmp_path: Path):
    ast = ASTImage(src=str(tmp_path / "nonexistent.png"), alt="n")
    with pytest.raises(FileNotFoundError):
        ImageRenderer().render(ast, _ctx(tmp_path))
