"""Tests for the Click CLI (spec §6.1)."""
import json
from pathlib import Path

from click.testing import CliRunner

from mdpdf.cli import main


def test_version_subcommand_prints_version():
    runner = CliRunner()
    result = runner.invoke(main, ["version"])
    assert result.exit_code == 0
    assert "2.0.0a1" in result.output


def test_render_writes_pdf(tmp_path: Path):
    src = tmp_path / "in.md"
    src.write_text("# Hi\n\nBody.")
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [str(src), "-o", str(out)])
    assert result.exit_code == 0
    # stdout single line = absolute path of the produced PDF (spec §6.1)
    assert result.output.strip() == str(out)
    assert out.exists()


def test_render_json_emits_render_result(tmp_path: Path):
    src = tmp_path / "in.md"
    src.write_text("# Hi")
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [str(src), "-o", str(out), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["output_path"] == str(out)
    assert payload["pages"] >= 1
    assert payload["bytes"] > 0
    assert len(payload["sha256"]) == 64
    assert "render_id" in payload
    assert "metrics" in payload


def test_render_template_other_than_generic_exits_2(tmp_path: Path):
    src = tmp_path / "in.md"
    src.write_text("# x")
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [str(src), "-o", str(out), "--template", "quote"])
    assert result.exit_code == 2  # configuration / argument error per spec §6.1
    # Error printed to stderr; CliRunner mixes stderr into result.output by default
    # only when mix_stderr=True (the default in older Click; in 8.x it's the default).
    combined = result.output
    assert "TEMPLATE_NOT_FOUND" in combined


def test_render_missing_input_exits_2(tmp_path: Path):
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [str(tmp_path / "missing.md"), "-o", str(out)])
    # Click rejects the path before our code runs; exit 2 (Click default for usage errors).
    # Using exit code 2 (argument error) is consistent with spec §6.1 row 2.
    assert result.exit_code == 2
