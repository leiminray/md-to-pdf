"""
Tests for fenced code + Mermaid handling in md_to_pdf.py.

Run / CI notes: see README.md in this directory.
"""

from __future__ import annotations

import os
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
    """Load md_to_pdf from scripts/ without running main."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("md_to_pdf_skill", MD_TO_PDF)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_normalize_fence_lang():
    mdp = _import_md_to_pdf()
    assert mdp.normalize_fence_lang("mermaid {.line-numbers}") == "mermaid"
    assert mdp.normalize_fence_lang("mermaid{foo}") == "mermaid"
    assert mdp.normalize_fence_lang("  Mermaid  ") == "mermaid"
    assert mdp.normalize_fence_lang("mmd") == "mmd"
    assert mdp.normalize_fence_lang("python") == "python"
    assert mdp.normalize_fence_lang("") == ""


def test_strip_yaml_frontmatter():
    mdp = _import_md_to_pdf()
    lines = ["---", "name: x", "foo: bar", "---", "", "# Hello", "Body."]
    assert mdp.strip_yaml_frontmatter(lines) == ["", "# Hello", "Body."]
    assert mdp.strip_yaml_frontmatter(["# No fence"]) == ["# No fence"]
    assert mdp.strip_yaml_frontmatter(["---", "orphan: 1", "# no closing"]) == ["---", "orphan: 1", "# no closing"]


def test_fence_truncate():
    mdp = _import_md_to_pdf()
    lines = ["a", "b", "c", "d"]
    out, trunc = mdp._fence_truncate(lines, max_lines=2, max_chars=100)
    assert out == ["a", "b"]
    assert trunc is True
    out2, trunc2 = mdp._fence_truncate(["hello"], max_lines=500, max_chars=3)
    assert out2 == ["hel"]
    assert trunc2 is True


def test_fenced_rl_cjk_mixed_xml():
    """CJK in code must use body font runs (mono often has no CJK glyphs)."""
    import sys

    sys.path.insert(0, str(SCRIPTS))
    import fenced_rl  # noqa: E402

    x = fenced_rl.fenced_cjk_mixed_line_xml("a中文b", "IDS-Noto-Regular")
    assert "IDS-Noto-Regular" in x
    assert "中文" in x

    java = "class X { /** 内部 orchestration */\n  int a;\n}"
    y = fenced_rl.pygments_to_reportlab_paragraph_xml(
        java, "java", cjk_body_font="IDS-Noto-Regular"
    )
    assert "IDS-Noto-Regular" in y
    assert "内部" in y


def test_mermaid_too_large_skips_subprocess(tmp_path: Path):
    mdp = _import_md_to_pdf()
    huge = "x" * (mdp._DEFAULT_MERMAID_MAX_CHARS + 10)
    png, err = mdp.render_mermaid_to_png(huge, tmp_path, preset="S")
    assert png is None
    assert err.startswith("too_large:")


def _pdf_text(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "".join(parts)


def _pdf_image_count(pdf_path: Path) -> int:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    n = 0
    for page in reader.pages:
        try:
            imgs = page.images
            n += len(imgs) if imgs is not None else 0
        except Exception:
            pass
    return n


def test_yaml_frontmatter_not_in_pdf(python_exe: Path, tmp_path: Path):
    md = tmp_path / "fm.md"
    md.write_text(
        "---\nname: SecretMeta\ntodos: []\n---\n\n# Title\n\nParagraph.\n",
        encoding="utf-8",
    )
    out = tmp_path / "fm.pdf"
    r = subprocess.run(
        [str(python_exe), str(MD_TO_PDF), str(md), "-o", str(out), "--no-mermaid"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    text = _pdf_text(out)
    assert "SecretMeta" not in text
    assert "Title" in text
    assert "Paragraph" in text


def test_utf8_bom_stripped(python_exe: Path, tmp_path: Path):
    """Leading UTF-8 BOM must not break the first heading (utf-8-sig read)."""
    md = tmp_path / "bom.md"
    md.write_bytes(b"\xef\xbb\xbf# BOM Heading\n\nParagraph.\n")
    out = tmp_path / "bom.pdf"
    r = subprocess.run(
        [str(python_exe), str(MD_TO_PDF), str(md), "-o", str(out), "--no-mermaid"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    text = _pdf_text(out)
    assert "BOM Heading" in text
    assert "Paragraph" in text


def test_fenced_fixture_in_pdf(python_exe: Path, tmp_path: Path):
    md = FIXTURES / "fenced-mermaid-smoke.md"
    out = tmp_path / "out.pdf"
    r = subprocess.run(
        [str(python_exe), str(MD_TO_PDF), str(md), "-o", str(out), "--no-mermaid"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert out.is_file()
    text = _pdf_text(out)
    assert "def hello():" in text
    assert "return" in text
    assert "line one" in text
    assert "Empty diagram block" in text
    assert "MERMAID" in text  # GitHub-style lang badge (uppercase)
    assert "flowchart LR" in text
    assert "Diagram rendering was skipped" not in text


@pytest.mark.skipif(
    os.environ.get("MDPDF_SKIP_MERMAID_TEST", "").lower() in ("1", "true", "yes"),
    reason="MDPDF_SKIP_MERMAID_TEST set — skip mmdc/Chromium integration",
)
def test_mermaid_renders_when_mmdc_available(python_exe: Path, tmp_path: Path):
    """Requires mmdc + headless Chromium on PATH / Puppeteer config. Skips if mmdc missing."""
    mdp = _import_md_to_pdf()
    if not mdp.resolve_mmdc_executable():
        pytest.skip("mmdc not on PATH (install @mermaid-js/mermaid-cli or set PATH)")
    md = FIXTURES / "mermaid-noto-presets.md"
    out = tmp_path / "mermaid.pdf"
    out_nom = tmp_path / "no-mermaid.pdf"
    r = subprocess.run(
        [str(python_exe), str(MD_TO_PDF), str(md), "-o", str(out)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    text = _pdf_text(out)
    if "[Mermaid] mmdc was found but failed" in text:
        pytest.skip(
            "mmdc on PATH but Chromium/Puppeteer failed to launch in this environment "
            "(common in CI/sandbox); fix browser or set MDPDF_SKIP_MERMAID_TEST=1"
        )
    assert "[Mermaid] mmdc not found" not in text
    r2 = subprocess.run(
        [
            str(python_exe),
            str(MD_TO_PDF),
            str(md),
            "-o",
            str(out_nom),
            "--no-mermaid",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r2.returncode == 0, r2.stderr + r2.stdout
    # Diagrams are raster images; body text alone does not prove mmdc ran.
    assert _pdf_image_count(out) > _pdf_image_count(out_nom)
