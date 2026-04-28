"""
CJK / typography regression tests for md_to_pdf.py.
See fixtures/uat-cjk.md and tests/README.md (visual wrap checklist).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = SKILL_ROOT / "scripts"
FIXTURES = SKILL_ROOT / "fixtures"
MD_TO_PDF = SCRIPTS / "md_to_pdf.py"
VENV_PY = SKILL_ROOT / ".venv" / "bin" / "python"


@pytest.fixture(scope="module")
def python_exe() -> Path:
    return VENV_PY if VENV_PY.is_file() else Path(sys.executable)


def _import_md_to_pdf():
    import importlib.util

    spec = importlib.util.spec_from_file_location("md_to_pdf_skill", MD_TO_PDF)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_resolve_output_pdf_default_is_fixtures_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Default PDF path is skill fixtures/out/<stem>.pdf; -o relative uses cwd."""
    mdp = _import_md_to_pdf()
    md = tmp_path / "hello.md"
    md.write_text("# Hi\n", encoding="utf-8")
    default_out = mdp.resolve_output_pdf(md.resolve(), None)
    assert default_out.name == "hello.pdf"
    assert default_out.parent.resolve() == mdp.DEFAULT_FIXTURES_OUT_DIR.resolve()

    monkeypatch.chdir(tmp_path)
    cwd_out = mdp.resolve_output_pdf(md.resolve(), Path("custom.pdf"))
    assert cwd_out.resolve() == (tmp_path / "custom.pdf").resolve()


def test_normalize_merged_atx_headings():
    mdp = _import_md_to_pdf()
    assert mdp.normalize_merged_atx_headings(["# Part A## Chapter B"]) == [
        "# Part A",
        "## Chapter B",
    ]
    assert mdp.normalize_merged_atx_headings(["  # X## Y Z"]) == ["  # X", "  ## Y Z"]
    assert mdp.normalize_merged_atx_headings(["# Normal Title"]) == ["# Normal Title"]
    assert mdp.normalize_merged_atx_headings(["## L2### L3"]) == ["## L2", "### L3"]
    # Inside fence: do not split
    lines = ["```", "# keep## together", "```"]
    assert mdp.normalize_merged_atx_headings(lines) == lines


def _pdf_text(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "".join(parts)


def _pdf_embeds_noto(pdf_path: Path) -> bool:
    raw = pdf_path.read_bytes()
    return b"Noto" in raw or b"noto" in raw.lower() or b"IDS-Noto" in raw


def test_cjk_strict_fixture_pdf(python_exe: Path, tmp_path: Path):
    md = FIXTURES / "uat-cjk.md"
    out = tmp_path / "cjk.pdf"
    r = subprocess.run(
        [str(python_exe), str(MD_TO_PDF), str(md), "-o", str(out), "--no-mermaid"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    text = _pdf_text(out)
    assert "2026年4月24日" in text
    assert "Alex Morgan" in text
    assert "Part A" in text
    assert "Chapter B" in text
    # Run-on title should not remain as a single visible "Part A## Chapter" blob in text extraction
    assert "Part A## Chapter" not in text.replace(" ", "")
    if not _pdf_embeds_noto(out):
        pytest.skip("Bundled Noto TTF not embedded in this environment (PDF byte probe)")


def test_merged_heading_split_in_pdf(python_exe: Path, tmp_path: Path):
    """Split line produces two outline-visible headings (Chapter B appears)."""
    md = tmp_path / "m.md"
    md.write_text("# One## Two\n\nBody.\n", encoding="utf-8")
    out = tmp_path / "m.pdf"
    r = subprocess.run(
        [str(python_exe), str(MD_TO_PDF), str(md), "-o", str(out), "--no-mermaid"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    t = _pdf_text(out)
    assert "One" in t and "Two" in t and "Body" in t
    assert "One## Two" not in t.replace("\n", "").replace(" ", "")
