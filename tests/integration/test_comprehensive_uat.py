"""Integration test: comprehensive UAT fixture renders successfully.

The fixture (`fixtures/branch_ops_ai_robot_product_brief.md`) exercises 11
scenario categories per spec §7.2.1. Mermaid renderers are mocked so the
test does not require Kroki / mmdc / mermaid-py in CI.
"""
from __future__ import annotations

import io
import json
from collections.abc import Iterator
from pathlib import Path

import pypdf
import pytest
from PIL import Image as _PILImage

REPO_ROOT = Path(__file__).resolve().parents[2]
UAT_FIXTURE = REPO_ROOT / "fixtures" / "branch_ops_ai_robot_product_brief.md"


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
def mock_mermaid(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Mock the pure mermaid renderer so the test runs in any environment."""
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


@pytest.fixture
def isolated_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("MD_PDF_AUDIT_PATH", str(audit_path))
    yield audit_path


@pytest.mark.skipif(not UAT_FIXTURE.exists(), reason="UAT fixture not authored")
@pytest.mark.skipif(
    not _HAS_CAIRO,
    reason="libcairo not available — fixture has an embedded SVG",
)
class TestComprehensiveUAT:
    def test_renders_successfully(
        self, tmp_path: Path, mock_mermaid: None, isolated_audit: Path
    ) -> None:
        from mdpdf.pipeline import Pipeline, RenderRequest

        out = tmp_path / "uat.pdf"
        pipeline = Pipeline.from_env()
        result = pipeline.render(
            RenderRequest(
                source=UAT_FIXTURE,
                source_type="path",
                output=out,
                mermaid_renderer="pure",
            )
        )
        assert out.exists()
        assert result.pages >= 5

    def test_minimum_file_size(
        self, tmp_path: Path, mock_mermaid: None, isolated_audit: Path
    ) -> None:
        from mdpdf.pipeline import Pipeline, RenderRequest

        out = tmp_path / "uat.pdf"
        Pipeline.from_env().render(
            RenderRequest(
                source=UAT_FIXTURE,
                source_type="path",
                output=out,
                mermaid_renderer="pure",
            )
        )
        assert out.stat().st_size > 50_000

    def test_pdf_text_contains_key_sections(
        self, tmp_path: Path, mock_mermaid: None, isolated_audit: Path
    ) -> None:
        from mdpdf.pipeline import Pipeline, RenderRequest

        out = tmp_path / "uat.pdf"
        Pipeline.from_env().render(
            RenderRequest(
                source=UAT_FIXTURE,
                source_type="path",
                output=out,
                mermaid_renderer="pure",
            )
        )
        text = "".join(p.extract_text() or "" for p in pypdf.PdfReader(str(out)).pages)
        for marker in (
            "Branch Operations AI Robot",
            "Market Positioning",
            "Technical Specifications",
            "deploy.sh",
        ):
            assert marker in text, f"Expected marker {marker!r} in PDF text"

    def test_json_output_parseable(
        self, tmp_path: Path, mock_mermaid: None, isolated_audit: Path
    ) -> None:
        """Pipeline.render's RenderResult dumps to a parseable JSON shape."""
        from mdpdf.pipeline import Pipeline, RenderRequest

        out = tmp_path / "uat.pdf"
        result = Pipeline.from_env().render(
            RenderRequest(
                source=UAT_FIXTURE,
                source_type="path",
                output=out,
                mermaid_renderer="pure",
            )
        )
        # Mirrors the JSON structure the CLI emits via --json
        payload = json.dumps({
            "output_path": str(result.output_path),
            "render_id": result.render_id,
            "pages": result.pages,
            "bytes": result.bytes,
            "sha256": result.sha256,
        })
        roundtrip = json.loads(payload)
        assert roundtrip["pages"] >= 5
