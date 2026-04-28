"""End-to-end integration tests for renderers + flowables.

Mocks the Mermaid renderer chain so tests don't require Kroki / mmdc / mermaid-py
in CI; the chain selection logic itself is exercised in unit tests.

Tests that need a real subprocess (the installed `md-to-pdf` console script) use
``MD_TO_PDF`` resolved from PATH or the venv bin dir; tests that need the in-process
``Pipeline`` (so the ``mock_mermaid_pure`` monkeypatch takes effect) call the pipeline
directly.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PIL import Image as _PILImage
from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "integration" / "fixtures"


def _resolve_md_to_pdf() -> str:
    found = shutil.which("md-to-pdf")
    if found:
        return found
    candidate = Path(sys.executable).parent / "md-to-pdf"
    if candidate.exists():
        return str(candidate)
    raise RuntimeError("md-to-pdf console script not found on PATH or in venv bin")


MD_TO_PDF = _resolve_md_to_pdf()


def _libcairo_available() -> bool:
    try:
        import cairosvg

        cairosvg.svg2png(
            bytestring=b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'
        )
    except OSError:
        return False
    return True


_HAS_CAIRO = _libcairo_available()


def _real_png_bytes() -> bytes:
    """1x1 white PNG that survives PIL.Image.open() in the engine pass."""
    buf = io.BytesIO()
    _PILImage.new("RGB", (1, 1), color="white").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def mock_mermaid_pure(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    png_bytes = _real_png_bytes()

    class _FakeMermaid:
        @staticmethod
        def to_png(source: str) -> bytes:
            return png_bytes

    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_pure._import_mermaid", lambda: _FakeMermaid
    )
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_puppeteer._find_mmdc", lambda: None
    )
    monkeypatch.delenv("KROKI_URL", raising=False)
    yield


def _run_md_to_pdf(*args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [MD_TO_PDF, *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        **kwargs,
    )


def test_acceptance_1_code_suite(tmp_path: Path) -> None:
    out = tmp_path / "code.pdf"
    proc = _run_md_to_pdf(str(FIXTURES / "code-suite.md"), "-o", str(out))
    assert proc.returncode == 0, proc.stderr
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    assert "def hello" in text
    assert "[unsupported" not in text


@pytest.mark.skipif(
    not _HAS_CAIRO,
    reason="libcairo not available — install via `brew install cairo` (macOS)",
)
def test_acceptance_2_image_suite(tmp_path: Path) -> None:
    out = tmp_path / "img.pdf"
    proc = _run_md_to_pdf(str(FIXTURES / "image-suite.md"), "-o", str(out))
    assert proc.returncode == 0, proc.stderr
    size = out.stat().st_size
    assert 5_000 < size < 2_000_000


def test_acceptance_3_mermaid_pure(
    tmp_path: Path, mock_mermaid_pure: None
) -> None:
    """Mermaid renders via pure-py shim; PDF contains an image."""
    from mdpdf.pipeline import Pipeline, RenderRequest

    pipeline = Pipeline.from_env()
    out = tmp_path / "mm.pdf"
    pipeline.render(
        RenderRequest(
            source=FIXTURES / "mermaid-suite.md",
            source_type="path",
            output=out,
            mermaid_renderer="pure",
        )
    )
    assert out.exists()
    assert out.stat().st_size > 1024


@pytest.mark.skipif(
    "KROKI_URL" not in os.environ,
    reason="Skipped when KROKI_URL is not set (CI provides via services:)",
)
def test_acceptance_4_mermaid_kroki(tmp_path: Path) -> None:
    out = tmp_path / "mm-kroki.pdf"
    proc = _run_md_to_pdf(
        str(FIXTURES / "mermaid-suite.md"),
        "-o", str(out),
        "--mermaid-renderer", "kroki",
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()


def test_acceptance_5_mermaid_bomb_rejected(tmp_path: Path) -> None:
    """Lint runs inside renderer.render() — pass --mermaid-renderer pure so
    PureMermaidRenderer is constructed without a renderer-availability check;
    the >50K-char source then trips the size limit before mermaid-py is touched.
    """
    out = tmp_path / "no.pdf"
    proc = _run_md_to_pdf(
        str(FIXTURES / "mermaid-bomb.md"),
        "-o", str(out),
        "--mermaid-renderer", "pure",
    )
    assert proc.returncode == 5, (proc.returncode, proc.stderr)
    assert "MERMAID_RESOURCE_LIMIT" in proc.stderr


def test_acceptance_6_mermaid_xss_rejected(tmp_path: Path) -> None:
    out = tmp_path / "no.pdf"
    proc = _run_md_to_pdf(
        str(FIXTURES / "mermaid-xss.md"),
        "-o", str(out),
        "--mermaid-renderer", "pure",
    )
    assert proc.returncode == 5, (proc.returncode, proc.stderr)
    assert "MERMAID_INVALID_SYNTAX" in proc.stderr


def test_acceptance_7_table_suite(tmp_path: Path) -> None:
    out = tmp_path / "tbl.pdf"
    proc = _run_md_to_pdf(str(FIXTURES / "table-suite.md"), "-o", str(out))
    assert proc.returncode == 0, proc.stderr
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    for word in ("col1", "col6", "header here"):
        assert word in text


def test_acceptance_8_outline_present(tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    proc = _run_md_to_pdf(str(FIXTURES / "outline-suite.md"), "-o", str(out))
    assert proc.returncode == 0, proc.stderr
    reader = PdfReader(str(out))
    assert len(reader.outline) >= 2  # at least 2 top-level chapters


def test_acceptance_9_blockquote_callout(tmp_path: Path) -> None:
    out = tmp_path / "cq.pdf"
    proc = _run_md_to_pdf(str(FIXTURES / "blockquote-callout.md"), "-o", str(out))
    assert proc.returncode == 0, proc.stderr
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    assert "quoted line in a callout box" in text


def test_acceptance_10_list_suite(tmp_path: Path) -> None:
    out = tmp_path / "list.pdf"
    proc = _run_md_to_pdf(str(FIXTURES / "list-suite.md"), "-o", str(out))
    assert proc.returncode == 0, proc.stderr
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    for word in ("alpha", "first", "outer-1", "inner-a"):
        assert word in text


def test_acceptance_11_comprehensive_with_brand(
    tmp_path: Path, mock_mermaid_pure: None
) -> None:
    """Comprehensive doc through the in-process pipeline so mock_mermaid_pure
    applies (subprocess wouldn't see the monkeypatch).
    """
    from mdpdf.pipeline import Pipeline, RenderRequest

    idimsum = REPO_ROOT / "examples" / "brands" / "idimsum"
    if not idimsum.exists():
        pytest.skip("idimsum brand pack not present")
    pipeline = Pipeline.from_env()
    out = tmp_path / "all.pdf"
    pipeline.render(
        RenderRequest(
            source=FIXTURES / "comprehensive-mini.md",
            source_type="path",
            output=out,
            brand_pack_dir=idimsum,
            mermaid_renderer="pure",
        )
    )
    reader = PdfReader(str(out))
    assert len(reader.pages) >= 1


def test_acceptance_12_asset_resolve_ms(
    tmp_path: Path, mock_mermaid_pure: None
) -> None:
    """asset_resolve_ms >= 0 when document has at least one mermaid block."""
    from mdpdf.pipeline import Pipeline, RenderRequest

    pipeline = Pipeline.from_env()
    out = tmp_path / "asset.pdf"
    result = pipeline.render(
        RenderRequest(
            source=FIXTURES / "mermaid-suite.md",
            source_type="path",
            output=out,
            mermaid_renderer="pure",
        )
    )
    assert result.metrics.asset_resolve_ms >= 0
