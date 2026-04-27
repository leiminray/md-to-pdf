"""Tests for diagnostics.doctor — run_doctor() report structure."""
from __future__ import annotations

import json
import sys
from typing import Any

import pytest
from click.testing import CliRunner

from mdpdf.cli import main
from mdpdf.diagnostics.doctor import run_doctor


def test_run_doctor_returns_dict() -> None:
    assert isinstance(run_doctor(), dict)


def test_run_doctor_has_required_sections() -> None:
    report = run_doctor()
    required = {
        "python", "mdpdf", "fonts", "mermaid",
        "brand_registry", "audit_log", "temp_paths",
    }
    missing = required - set(report.keys())
    assert not missing, f"missing sections: {missing}"


def test_run_doctor_python_section() -> None:
    py = run_doctor()["python"]
    assert py["version"] == sys.version
    assert py["executable"] == sys.executable
    assert "platform" in py


def test_run_doctor_mdpdf_section() -> None:
    import mdpdf

    m = run_doctor()["mdpdf"]
    assert m["version"] == mdpdf.__version__
    assert "install_location" in m


def test_run_doctor_fonts_section() -> None:
    f = run_doctor()["fonts"]
    assert isinstance(f["bundled_count"], int)
    assert isinstance(f["system_cjk_available"], bool)


def test_run_doctor_mermaid_section() -> None:
    mm = run_doctor()["mermaid"]
    for k in ("kroki_available", "puppeteer_available", "mermaid_py_available"):
        assert k in mm


def test_run_doctor_audit_log_section() -> None:
    al = run_doctor()["audit_log"]
    assert "path" in al
    assert isinstance(al["exists"], bool)


def test_run_doctor_temp_paths_section() -> None:
    tp = run_doctor()["temp_paths"]
    assert "tmpdir" in tp
    assert isinstance(tp["writable"], bool)


def test_run_doctor_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Subsystem failure → section gets an `error` key, no exception escapes."""

    def _explode(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("simulated subsystem failure")

    monkeypatch.setattr("mdpdf.diagnostics.doctor._probe_fonts", _explode)
    report = run_doctor()
    assert "error" in report["fonts"]


# ── CLI: md-to-pdf doctor ───────────────────────────────────────────────────


def test_cli_doctor_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0, result.output


def test_cli_doctor_json_output_parses() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "python" in data
    assert "mdpdf" in data
