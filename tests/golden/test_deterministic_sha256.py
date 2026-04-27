"""L5 golden: deterministic sha256 baseline per fixture.

Asserts that rendering each UAT fixture in deterministic mode + a fixed
``SOURCE_DATE_EPOCH`` + a fixed ``--watermark-user`` produces a PDF whose
sha256 matches a committed baseline. Together with L1 (AST) and L3
(text-layer) this completes the v2.0 self-consistency parity gate.

Diff here is one of:
- a real renderer / determinism regression (the bit-identical contract
  from Plan 4 broke for this fixture), OR
- an intentional change (font metrics, layout tweak, brand pack edit) —
  regenerate with ``pytest tests/golden/ --update-golden``.

The baselines are the canonical fingerprint for the v1.8.9 → v2.0
parity gate (CLAUDE.md "Never strip v1.8.9 until v2.0 passes the
v1-parity golden suite"). Once these baselines are committed and CI
shows them green for every uat-*.md fixture, Phase 7 (deletion of
scripts/md_to_pdf.py + brand_kits/ + the legacy test files) can land.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from mdpdf.pipeline import Pipeline, RenderRequest, WatermarkOptions
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
# Fixed for deterministic baselines — chosen to be a stable, well-known epoch
# (2024-04-29 UTC) so the create-date is predictable across regenerations.
_SOURCE_DATE_EPOCH = "1714400000"
_WATERMARK_USER = "ci@example.com"


@pytest.mark.parametrize(
    "fixture",
    discover_uat_fixtures(),
    ids=lambda p: p.stem,
)
def test_deterministic_sha256(
    fixture: Path,
    tmp_path: Path,
    update_golden: bool,
    mock_mermaid: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _HAS_CAIRO and "branch_ops" in fixture.name:
        pytest.skip("libcairo not available — branch_ops fixture has an SVG asset")

    monkeypatch.setenv("SOURCE_DATE_EPOCH", _SOURCE_DATE_EPOCH)
    out = tmp_path / f"{fixture.stem}.pdf"
    pipeline = Pipeline.from_env()
    pipeline.render(
        RenderRequest(
            source=fixture,
            source_type="path",
            output=out,
            mermaid_renderer="pure",
            deterministic=True,
            watermark=WatermarkOptions(user=_WATERMARK_USER),
        )
    )
    actual = hashlib.sha256(out.read_bytes()).hexdigest()
    baseline = BASELINES_DIR / "sha256" / f"{fixture.stem}.txt"
    assert_or_update_golden(baseline, actual + "\n", update_golden)
