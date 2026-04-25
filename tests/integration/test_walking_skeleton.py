"""End-to-end walking-skeleton: hello.md → PDF, via both API and CLI."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

from mdpdf.pipeline import Pipeline, RenderRequest

FIXTURE = Path(__file__).parent / "fixtures" / "hello.md"


def _resolve_md_to_pdf() -> str:
    """Resolve the `md-to-pdf` console script.

    Prefer PATH lookup; fall back to the script next to the active Python
    interpreter (e.g. `.venv-v2/bin/md-to-pdf`) when the venv's bin dir is
    not on PATH (common when pytest is invoked via its absolute path).
    """
    found = shutil.which("md-to-pdf")
    if found:
        return found
    candidate = Path(sys.executable).parent / "md-to-pdf"
    if candidate.exists():
        return str(candidate)
    raise RuntimeError("md-to-pdf console script not found on PATH or in venv bin")


MD_TO_PDF = _resolve_md_to_pdf()


def test_pipeline_api_renders_hello(tmp_path: Path):
    pipeline = Pipeline.from_env()
    out = tmp_path / "hello.pdf"
    result = pipeline.render(RenderRequest(
        source=FIXTURE,
        source_type="path",
        output=out,
    ))
    assert out.exists()
    assert result.pages >= 1
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    assert "Walking Skeleton" in text
    assert "Goals" in text
    assert "bold" in text
    assert "italic" in text


def test_cli_renders_hello(tmp_path: Path):
    """Invoke the installed `md-to-pdf` console script as a subprocess."""
    out = tmp_path / "hello.pdf"
    proc = subprocess.run(
        [MD_TO_PDF, str(FIXTURE), "-o", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == str(out)
    assert out.exists()


def test_cli_json_mode(tmp_path: Path):
    out = tmp_path / "hello.pdf"
    proc = subprocess.run(
        [MD_TO_PDF, str(FIXTURE), "-o", str(out), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["output_path"] == str(out)
    assert payload["pages"] >= 1
    assert len(payload["sha256"]) == 64
