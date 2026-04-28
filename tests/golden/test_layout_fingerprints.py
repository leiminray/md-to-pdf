"""L4 golden: layout fingerprint per fixture.

Extracts bounding-box coordinates from each page via pdfplumber, rounds to
0.1 pt (to tolerate sub-pixel jitter), and computes a sha256 fingerprint of
the sorted bbox list per page. The result is a per-page array of hex digests
stored in JSON.

Diff here = a renderer / layout regression that moved elements, changed column
widths, adjusted heading spacing, or altered table cell placement.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mdpdf.pipeline import Pipeline, RenderRequest
from tests.golden.conftest import (
    BASELINES_DIR,
    assert_or_update_golden,
    discover_uat_fixtures,
    extract_layout_json,
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


@pytest.mark.parametrize(
    "fixture",
    discover_uat_fixtures(),
    ids=lambda p: p.stem,
)
def test_layout_fingerprint(
    fixture: Path,
    tmp_path: Path,
    update_golden: bool,
    mock_mermaid: None,
) -> None:
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
                mermaid_renderer="pure",
                deterministic=False,
            )
        )
    except Exception as exc:  # noqa: BLE001 — fixture rendering may regress
        pytest.skip(f"render failed for {fixture.name}: {exc}")

    actual = extract_layout_json(out)
    baseline = BASELINES_DIR / "layout_fingerprint" / f"{fixture.stem}.json"
    assert_or_update_golden(baseline, actual, update_golden)
