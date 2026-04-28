"""Golden test harness: pytest fixtures + diff helpers for 4-layer golden testing.

Layers:
  L1  AST snapshots       — tests/golden/ast/<name>.yaml
  L2  XMP snapshots       — tests/golden/xmp/<name>.json
  L3  text-layer          — tests/golden/text/<name>.txt
  L4  layout fingerprint  — tests/golden/layout/<name>.json
  det deterministic sha256 — tests/golden/deterministic/<name>.sha256
"""

from __future__ import annotations

import dataclasses
import difflib
import hashlib
import io
import json
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pikepdf
import pypdf
import pytest
import yaml
from PIL import Image as _PILImage

# pdfplumber is a dev-only dep; import is guarded so missing package gives skip.
try:
    import pdfplumber  # type: ignore[import]
    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _PDFPLUMBER_AVAILABLE = False

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "fixtures"
BASELINES_DIR = Path(__file__).parent / "baselines"
GOLDEN_ROOT = Path(__file__).parent


# ---------------------------------------------------------------------------
# pytest option registration
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register --update-golden option."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Overwrite committed golden snapshots with current output (for intentional changes).",
    )


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    """Return True if --update-golden was passed on the command line."""
    return bool(request.config.getoption("--update-golden"))


@pytest.fixture(scope="session")
def golden_root() -> Path:
    """Return the absolute path to tests/golden/."""
    return GOLDEN_ROOT


@pytest.fixture
def rendered_pdf(tmp_path: Path) -> "RenderedPdfFactory":
    """Return a factory that renders a fixture markdown file to a temp PDF.

    Usage::

        def test_something(rendered_pdf):
            pdf_path = rendered_pdf("uat-en", extra_args=["--deterministic"])
    """
    return RenderedPdfFactory(tmp_path)


class RenderedPdfFactory:
    """Renders a named fixture to a temporary PDF using the installed CLI."""

    def __init__(self, tmp_path: Path) -> None:
        self._tmp = tmp_path

    def __call__(
        self,
        fixture_name: str,
        *,
        extra_args: list[str] | None = None,
        fixture_dir: Path | None = None,
    ) -> Path:
        """Render *fixture_name*.md and return the PDF Path."""
        search_dir = fixture_dir or FIXTURES_DIR
        md_path = search_dir / f"{fixture_name}.md"
        if not md_path.exists():
            pytest.skip(f"Fixture not found: {md_path}")
        out_pdf = self._tmp / f"{fixture_name}.pdf"
        cmd: list[str] = ["md-to-pdf", str(md_path), "-o", str(out_pdf)]
        if extra_args:
            cmd.extend(extra_args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            pytest.fail(
                f"md-to-pdf failed for fixture '{fixture_name}':\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return out_pdf


# ---------------------------------------------------------------------------
# Fixture discovery (for existing layer tests)
# ---------------------------------------------------------------------------


def discover_uat_fixtures() -> list[Path]:
    """All fixtures/uat-*.md plus the comprehensive branch_ops fixture.

    Glob-discovered so the parity gate auto-picks up new fixtures.
    """
    fixtures = sorted(FIXTURES_DIR.glob("uat-*.md"))
    branch_ops = FIXTURES_DIR / "branch_ops_ai_robot_product_brief.md"
    if branch_ops.exists():
        fixtures.append(branch_ops)
    return fixtures


# ---------------------------------------------------------------------------
# Layer helpers
# ---------------------------------------------------------------------------


def extract_ast_yaml(md_path: Path) -> str:
    """L1: Parse markdown file → Document AST → canonical YAML string.

    Uses markdown-it-py via the mdpdf parser module. The AST is serialised
    using dataclasses.asdict, keys sorted, YAML dumped with default_flow_style=False.
    """
    from mdpdf.markdown.parser import parse_markdown

    document = parse_markdown(md_path.read_text(encoding="utf-8"))
    raw = dataclasses.asdict(document)
    return yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)


def extract_xmp_json(pdf_path: Path) -> str:
    """L2: Extract pikepdf XMP metadata → sorted JSON string.

    Keys in `xmp:CreateDate` and `mdpdf:RenderId` are excluded from the
    comparison in non-deterministic mode (they change per-run). The full
    dict is returned; callers decide which keys to mask.
    """
    with pikepdf.open(pdf_path) as pdf:
        with pdf.open_metadata() as meta:
            raw: dict[str, Any] = dict(meta)
    return json.dumps(raw, indent=2, sort_keys=True, ensure_ascii=False)


def extract_text_txt(pdf_path: Path) -> str:
    """L3: Extract per-page text via pypdf → normalised string.

    Pages are separated by a form-feed character. Whitespace within each page
    is stripped of leading/trailing blank lines; internal whitespace is
    normalised (multiple spaces → single space, trailing spaces removed).
    """
    reader = pypdf.PdfReader(str(pdf_path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        normalised_lines = [
            " ".join(line.split()) for line in text.splitlines()
        ]
        pages.append("\n".join(line for line in normalised_lines if line))
    return "\f".join(pages)


def extract_layout_json(pdf_path: Path) -> str:
    """L4: Extract per-page bbox fingerprints via pdfplumber → JSON string.

    Float coordinates are rounded to 0.1 pt to tolerate sub-pixel jitter
    across platform/version. Each page produces a sha256 of its sorted
    bounding-box list. The result is a JSON array of per-page hex digests.
    """
    if not _PDFPLUMBER_AVAILABLE:
        pytest.skip(
            "pdfplumber not installed. Run: pip install 'md-to-pdf[dev]'"
        )
    page_hashes: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            words = page.extract_words() or []
            bboxes = sorted(
                (
                    round(float(w["x0"]), 1),
                    round(float(w["top"]), 1),
                    round(float(w["x1"]), 1),
                    round(float(w["bottom"]), 1),
                )
                for w in words
            )
            page_data = json.dumps(bboxes, separators=(",", ":"))
            page_hashes.append(hashlib.sha256(page_data.encode()).hexdigest())
    return json.dumps(page_hashes, indent=2)


def compute_pdf_sha256(pdf_path: Path) -> str:
    """Deterministic sha256 of a PDF file (used for det-mode baselines)."""
    h = hashlib.sha256()
    with pdf_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Golden comparison helper
# ---------------------------------------------------------------------------


def assert_golden_match(
    actual: str,
    golden_path: Path,
    *,
    update: bool = False,
) -> None:
    """Compare *actual* string to the committed golden file at *golden_path*.

    Args:
        actual: The freshly-computed string representation.
        golden_path: Absolute path to the committed golden file.
        update: If True, overwrite the golden file and return without failing.

    On mismatch:
        - Writes *actual* to ``golden_path.with_suffix(golden_path.suffix + '.actual')``
        - Calls ``pytest.fail`` with a unified diff (first 60 lines).

    If the golden file does not exist:
        - With ``update=True``: writes the golden file and returns.
        - Without ``update``: calls ``pytest.skip`` with regen instructions.
    """
    if update:
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(actual, encoding="utf-8")
        return

    if not golden_path.exists():
        pytest.skip(
            f"Golden file missing: {golden_path}\n"
            f"Run pytest with --update-golden to generate it."
        )

    expected = golden_path.read_text(encoding="utf-8")
    if actual == expected:
        return

    actual_path = golden_path.parent / (golden_path.name + ".actual")
    actual_path.write_text(actual, encoding="utf-8")

    diff_lines = list(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=str(golden_path),
            tofile=str(actual_path),
            n=3,
        )
    )
    diff_excerpt = "".join(diff_lines[:60])
    if len(diff_lines) > 60:
        diff_excerpt += f"\n... ({len(diff_lines) - 60} more diff lines)"

    pytest.fail(
        f"Golden mismatch for {golden_path.name}:\n{diff_excerpt}\n"
        f"Actual written to: {actual_path}\n"
        f"Run pytest with --update-golden to accept the new output."
    )


# ---------------------------------------------------------------------------
# Legacy mermaid mock (for compatibility with existing tests)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Legacy assert helper (for compatibility with existing tests)
# ---------------------------------------------------------------------------


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
