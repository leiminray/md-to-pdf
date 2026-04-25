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
    runner = CliRunner()  # Click 8.3+ separates stderr by default
    result = runner.invoke(main, [str(src), "-o", str(out), "--template", "quote"])
    assert result.exit_code == 2  # configuration / argument error per spec §6.1
    assert "TEMPLATE_NOT_FOUND" in result.stderr


def test_help_does_not_advertise_unimplemented_flags():
    runner = CliRunner()
    result = runner.invoke(main, ["render", "--help"])
    assert result.exit_code == 0
    # Hidden flags must NOT appear in --help output.
    assert "--deterministic" not in result.output
    assert "--watermark-user" not in result.output
    assert "--no-audit" not in result.output
    assert "--locale" not in result.output
    # Visible flags MUST appear.
    assert "--template" in result.output
    assert "--json" in result.output


def test_deterministic_flag_warns(tmp_path: Path):
    src = tmp_path / "in.md"
    src.write_text("# x")
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [str(src), "-o", str(out), "--deterministic"])
    assert result.exit_code == 0
    assert "not yet implemented" in result.stderr


def test_render_missing_input_exits_2_via_click_validation(tmp_path: Path):
    """Click rejects the missing path with usage error (exit 2) before our
    RESOURCE_MISSING (exit 4) handler runs. Plan 5 may move path validation
    inside the pipeline so this becomes exit 4 per spec §6.1 row 4.
    """
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [str(tmp_path / "missing.md"), "-o", str(out)])
    assert result.exit_code == 2
    # TODO(plan-5): move path-existence check into Pipeline.render's validate
    # phase so RESOURCE_MISSING (exit 4) is returned per spec §6.1.
