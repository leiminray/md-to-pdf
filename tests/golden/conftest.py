"""Golden-suite test infrastructure (spec §7.2).

Layered snapshot tests assert v2.0's *self-consistency* across runs against
committed baselines. Layers (in order of fidelity to visual rendering):

  L1 (AST)            — markdown-it-py + transformer chain output
  L2 (XMP)            — pikepdf-extracted XMP metadata keys
  L3 (text-layer)     — pypdf .extract_text() per page
  L4 (layout fp)      — pypdf page-size / page-count digest
  L5 (deterministic)  — sha256 of bit-identical PDF (deterministic mode)

Each layer's snapshot is committed under tests/golden/baselines/<layer>/<fixture>.
The `--update-golden` pytest flag rewrites baselines instead of asserting.

Per pass-2 P5-018 the fixture set is glob-discovered, not hardcoded — any
fixtures/uat-*.md added later is automatically covered.
"""
from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from PIL import Image as _PILImage

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "fixtures"
BASELINES_DIR = Path(__file__).parent / "baselines"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Rewrite golden baselines instead of asserting against them.",
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    """True when --update-golden is on the command line."""
    return bool(request.config.getoption("--update-golden"))


def discover_uat_fixtures() -> list[Path]:
    """All fixtures/uat-*.md plus the comprehensive branch_ops fixture.

    Glob-discovered so the parity gate auto-picks up new fixtures.
    """
    fixtures = sorted(FIXTURES_DIR.glob("uat-*.md"))
    branch_ops = FIXTURES_DIR / "branch_ops_ai_robot_product_brief.md"
    if branch_ops.exists():
        fixtures.append(branch_ops)
    return fixtures


def _real_png_bytes() -> bytes:
    """1x1 white PNG that survives PIL.Image.open() in the engine pass."""
    buf = io.BytesIO()
    _PILImage.new("RGB", (1, 1), color="white").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def mock_mermaid(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make the mermaid renderer chain return a real 1x1 PNG so golden tests
    don't depend on Kroki / mmdc / mermaid-py being installed.
    """
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


def assert_or_update_golden(baseline_path: Path, actual: str, update: bool) -> None:
    """Either rewrite the baseline (if `update`) or assert it matches `actual`."""
    if update:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(actual, encoding="utf-8")
        return
    if not baseline_path.exists():
        pytest.skip(
            f"Baseline missing: {baseline_path.relative_to(REPO_ROOT)}. "
            "Run `pytest tests/golden/ --update-golden` to create it."
        )
    expected = baseline_path.read_text(encoding="utf-8")
    assert actual == expected, (
        f"Snapshot diverged from {baseline_path.relative_to(REPO_ROOT)}.\n"
        "If the change is intentional, regenerate with: "
        "pytest tests/golden/ --update-golden"
    )
