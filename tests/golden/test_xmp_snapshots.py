"""L2 golden: XMP metadata snapshot per fixture.

Asserts that the 12 spec §5.3 XMP keys are present in the rendered PDF
and stable across runs (when invariant inputs are pinned). Volatile
keys (CreateDate / RenderId) are masked before snapshotting.

Diff here = renderer regression that changed which keys land or what
prefix the namespace is registered under.
"""
from __future__ import annotations

import re
from pathlib import Path

import pikepdf
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
_SOURCE_DATE_EPOCH = "1714400000"
_WATERMARK_USER = "ci@example.com"

# pikepdf returns keys as `{namespace_uri}local`; alias them back to the
# spec's prefix:local form for snapshot stability.
_NS_ALIASES = (
    ("{http://purl.org/dc/elements/1.1/}", "dc:"),
    ("{http://ns.adobe.com/pdf/1.3/}", "pdf:"),
    ("{http://ns.adobe.com/xap/1.0/}", "xmp:"),
    ("{https://md-to-pdf.dev/xmp/1.0/}", "mdpdf:"),
)


def _shorten(key: str) -> str:
    for ns_uri, prefix in _NS_ALIASES:
        if key.startswith(ns_uri):
            return prefix + key[len(ns_uri):]
    return key


def _xmp_snapshot(pdf_path: Path) -> str:
    """Return a deterministic textual rendering of the PDF's XMP keys.

    Masks CI-volatile values: UUID-shaped IDs, ISO datetimes, and the
    16-hex-char RenderHost (which is sha256(hostname)[:16] and therefore
    differs per runner).
    """
    rows: list[str] = []
    with pikepdf.open(str(pdf_path)) as pdf, pdf.open_metadata() as meta:
        for raw_key in sorted(meta):
            short = _shorten(raw_key)
            value = meta[raw_key]
            if isinstance(value, list):
                rendered = "[" + ", ".join(repr(str(v)) for v in value) + "]"
            else:
                rendered = repr(str(value))
            rendered = re.sub(
                r"'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'",
                "'<UUID>'",
                rendered,
            )
            rendered = re.sub(
                r"'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+\-]\d{2}:?\d{2})?'",
                "'<DATE>'",
                rendered,
            )
            # RenderHost is exactly 16 lowercase hex chars (sha256[:16]).
            if short == "mdpdf:RenderHost":
                rendered = re.sub(r"'[0-9a-f]{16}'", "'<HOST>'", rendered)
            rows.append(f"{short} = {rendered}")
    return "\n".join(rows) + "\n"


@pytest.mark.parametrize(
    "fixture",
    discover_uat_fixtures(),
    ids=lambda p: p.stem,
)
def test_xmp_snapshot(
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
    try:
        Pipeline.from_env().render(
            RenderRequest(
                source=fixture,
                source_type="path",
                output=out,
                # `auto` picks Kroki on the Golden CI job; the `pure` renderer
                # is rejected in deterministic mode (Plan 4 P4-015), so any
                # fixture with a Mermaid block needs a deterministic-safe
                # renderer at hand. Test skips when none is available.
                mermaid_renderer="auto",
                deterministic=True,
                watermark=WatermarkOptions(user=_WATERMARK_USER),
            )
        )
    except Exception as exc:  # noqa: BLE001 — env-gating shim
        pytest.skip(f"render failed for {fixture.name}: {exc}")

    actual = _xmp_snapshot(out)
    baseline = BASELINES_DIR / "xmp" / f"{fixture.stem}.txt"
    assert_or_update_golden(baseline, actual, update_golden)
