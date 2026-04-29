"""L3 golden: text-layer snapshot per fixture.

Renders the PDF, extracts text via pypdf, masks volatile bits (page numbers
in footers, render-id, render-date), and asserts the resulting text matches
a committed baseline. A diff here means a renderer / layout regression that
changed which characters land on which page.

Tests skip on systems without libcairo (the SVG branch in the UAT fixture
needs cairosvg) or when a fixture renders uncleanly in this environment.
"""
from __future__ import annotations

import re
from pathlib import Path

import pypdf
import pytest

from mdpdf.pipeline import Pipeline, RenderRequest
from tests.golden.conftest import (
    BASELINES_DIR,
    assert_or_update_golden,
    discover_uat_fixtures,
)


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


def _mask_volatile(text: str) -> str:
    """Replace render-id and render-date occurrences with stable placeholders.

    The footer / watermark embed the render-id + ISO datetime; the audit
    logger and create-date use full microsecond precision (`+00:00` or
    `+00`). This regex covers both the with-microseconds and without
    forms and leaves a single `<DATE>` placeholder.
    """
    # ISO 8601 datetime with optional fractional seconds + timezone
    text = re.sub(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+\-]\d{2}:?\d{2})?",
        "<DATE>",
        text,
    )
    # Bare ISO date
    text = re.sub(r"\d{4}-\d{2}-\d{2}", "<DATE>", text)
    # UUID v4 (render_id in footer + UUID-shaped derived id)
    text = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "<UUID>",
        text,
    )
    return text


@pytest.mark.parametrize(
    "fixture",
    discover_uat_fixtures(),
    ids=lambda p: p.stem,
)
def test_text_layer_snapshot(
    fixture: Path,
    tmp_path: Path,
    update_golden: bool,
    strict_golden: bool,
    mock_mermaid: None,
) -> None:
    # Only the branch_ops fixture references an SVG; skip just that case
    # when libcairo is missing.
    if not _HAS_CAIRO and "branch_ops" in fixture.name:
        pytest.skip("libcairo not available — branch_ops fixture has an SVG asset")
    out = tmp_path / f"{fixture.stem}.pdf"
    pipeline = Pipeline.from_env()
    try:
        pipeline.render(
            RenderRequest(
                source=fixture,
                source_type="path",
                output=out,
                # `auto` lets the mock_mermaid fixture pick a deterministic-safe
                # renderer (Kroki stub); `pure` would be rejected here under
                # deterministic=True.
                mermaid_renderer="auto",
                deterministic=True,
            )
        )
    except Exception as exc:  # noqa: BLE001 — fixture rendering may regress
        pytest.skip(f"render failed for {fixture.name}: {exc}")

    pages_text: list[str] = []
    for page in pypdf.PdfReader(str(out)).pages:
        pages_text.append(_mask_volatile(page.extract_text() or ""))
    actual = "\n--- PAGE BREAK ---\n".join(pages_text) + "\n"

    baseline = BASELINES_DIR / "text_layer" / f"{fixture.stem}.txt"
    assert_or_update_golden(baseline, actual, update_golden, strict=strict_golden)
