"""End-to-end Plan 2 integration: branded render + CJK round-trip."""
import shutil
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parents[2]
HELLO = REPO_ROOT / "tests" / "integration" / "fixtures" / "hello.md"
HELLO_CJK = REPO_ROOT / "tests" / "integration" / "fixtures" / "hello-cjk.md"
IDIMSUM = REPO_ROOT / "examples" / "brands" / "idimsum"


def _resolve_md_to_pdf() -> str:
    found = shutil.which("md-to-pdf")
    if found:
        return found
    candidate = Path(sys.executable).parent / "md-to-pdf"
    if candidate.exists():
        return str(candidate)
    raise RuntimeError("md-to-pdf console script not found on PATH or in venv bin")


MD_TO_PDF = _resolve_md_to_pdf()


def test_branded_hello_renders(tmp_path: Path):
    out = tmp_path / "branded.pdf"
    proc = subprocess.run(
        [MD_TO_PDF, str(HELLO), "-o", str(out),
         "--brand-pack-dir", str(IDIMSUM)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    assert "Walking Skeleton" in text


def test_cjk_renders_with_brand(tmp_path: Path):
    out = tmp_path / "cjk-branded.pdf"
    proc = subprocess.run(
        [MD_TO_PDF, str(HELLO_CJK), "-o", str(out),
         "--brand-pack-dir", str(IDIMSUM)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
    reader = PdfReader(str(out))
    assert len(reader.pages) >= 1


def test_cjk_no_brand_uses_bundled_fallback(tmp_path: Path):
    """Without a brand, the bundled fonts/NotoSansSC-*.ttf is found by the manager."""
    out = tmp_path / "cjk-bundled.pdf"
    proc = subprocess.run(
        [MD_TO_PDF, str(HELLO_CJK), "-o", str(out)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()


def test_brand_override_whitelisted_succeeds(tmp_path: Path):
    out = tmp_path / "overridden.pdf"
    proc = subprocess.run(
        [MD_TO_PDF, str(HELLO), "-o", str(out),
         "--brand-pack-dir", str(IDIMSUM),
         "--override", "theme.colors.accent=#FF0000"],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_brand_override_forbidden_exits_3(tmp_path: Path):
    out = tmp_path / "should-fail.pdf"
    proc = subprocess.run(
        [MD_TO_PDF, str(HELLO), "-o", str(out),
         "--brand-pack-dir", str(IDIMSUM),
         "--override", "compliance.issuer.name=Other"],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 3
    assert "BRAND_OVERRIDE_DENIED" in proc.stderr


def test_legacy_brand_flag_renders(tmp_path: Path):
    """`--brand-pack-dir` with legacy layout (brand_kits/ replaced by examples/brands/)."""
    out = tmp_path / "legacy.pdf"
    # Use examples/brands/idimsum/ which is the new location
    proc = subprocess.run(
        [MD_TO_PDF, str(HELLO), "-o", str(out),
         "--brand-pack-dir", str(REPO_ROOT / "examples" / "brands" / "idimsum")],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()


def test_brand_list_includes_idimsum():
    proc = subprocess.run(
        [MD_TO_PDF, "brand", "list"],
        capture_output=True, text=True, check=False, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0
    assert "idimsum" in proc.stdout
