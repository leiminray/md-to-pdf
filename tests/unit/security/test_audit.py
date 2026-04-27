"""Tests for security.audit — JSONL audit logger."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from mdpdf.errors import PipelineError
from mdpdf.security.audit import AuditLogger


@pytest.fixture()
def audit_log(tmp_path: Path) -> AuditLogger:
    return AuditLogger(path=tmp_path / "audit.jsonl")


def test_log_start_appends_valid_json(audit_log: AuditLogger, tmp_path: Path) -> None:
    audit_log.log_start(
        render_id="test-render-id-001",
        user="alice@example.com",
        host_hash="abcdef01",
        brand_id="acme",
        brand_version="1.0.0",
        template="generic",
        input_path=Path("/tmp/input.md"),
        input_size=1024,
        input_sha256="a" * 64,
        watermark_level="L1+L2",
        deterministic=False,
        locale="en",
    )
    lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "render.start"
    assert event["render_id"] == "test-render-id-001"
    assert event["user"] == "alice@example.com"
    assert event["brand_id"] == "acme"
    assert event["watermark_level"] == "L1+L2"
    assert event["deterministic"] is False
    assert "timestamp" in event


def test_log_complete_appends_valid_json(audit_log: AuditLogger, tmp_path: Path) -> None:
    audit_log.log_complete(
        render_id="test-render-id-001",
        duration_ms=1500,
        output_path=Path("/tmp/out.pdf"),
        output_size=204800,
        output_sha256="b" * 64,
        pages=3,
        renderers_used={"mermaid": "kroki"},
        warnings=[],
    )
    lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "render.complete"
    assert event["render_id"] == "test-render-id-001"
    assert event["duration_ms"] == 1500
    assert event["pages"] == 3
    assert event["output_size"] == 204800


def test_log_error_appends_valid_json(audit_log: AuditLogger, tmp_path: Path) -> None:
    audit_log.log_error(
        render_id="test-render-id-err",
        duration_ms=200,
        code="BRAND_NOT_FOUND",
        message="Brand 'missing' not found in any registry layer.",
    )
    lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "render.error"
    assert event["code"] == "BRAND_NOT_FOUND"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
def test_audit_log_file_permissions(tmp_path: Path) -> None:
    log = AuditLogger(path=tmp_path / "audit.jsonl")
    log.log_error(
        render_id="r",
        duration_ms=1,
        code="TEST",
        message="test",
    )
    mode = stat.S_IMODE((tmp_path / "audit.jsonl").stat().st_mode)
    assert mode == 0o640, f"Expected 0640, got {oct(mode)}"


def test_sequential_appends_produce_multiple_lines(
    audit_log: AuditLogger, tmp_path: Path
) -> None:
    audit_log.log_start(
        render_id="r1",
        user=None,
        host_hash="h1",
        brand_id="b",
        brand_version="1",
        template="generic",
        input_path=None,
        input_size=0,
        input_sha256="0" * 64,
        watermark_level="L2",
        deterministic=True,
        locale="zh-CN",
    )
    audit_log.log_complete(
        render_id="r1",
        duration_ms=100,
        output_path=Path("/tmp/x.pdf"),
        output_size=5000,
        output_sha256="c" * 64,
        pages=1,
        renderers_used={},
        warnings=["some warning"],
    )
    lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    events = [json.loads(line) for line in lines]
    assert events[0]["event"] == "render.start"
    assert events[1]["event"] == "render.complete"
    assert events[1]["warnings"] == ["some warning"]


def test_write_failure_raises_pipeline_error(tmp_path: Path) -> None:
    bad_path = tmp_path / "is_a_dir"
    bad_path.mkdir()
    log = AuditLogger(path=bad_path)
    with pytest.raises(PipelineError) as exc_info:
        log.log_error(render_id="r", duration_ms=1, code="X", message="y")
    assert exc_info.value.code == "AUDIT_LOG_WRITE_FAILED"


# ── Task 18: env-var override + permission re-tighten ────────────────────────


def test_env_var_overrides_default_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MD_PDF_AUDIT_PATH is honoured when no explicit path is passed."""
    custom = tmp_path / "custom.jsonl"
    monkeypatch.setenv("MD_PDF_AUDIT_PATH", str(custom))
    log = AuditLogger()
    assert log._path == custom
    log.log_error(render_id="r", duration_ms=1, code="X", message="y")
    assert custom.exists()


def test_default_path_falls_back_to_home_when_env_var_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without MD_PDF_AUDIT_PATH, the default lives under HOME — patch HOME
    so the test does not pollute the developer's actual ~/.md-to-pdf/.

    Pass-1 P4-010: prevents the previous test from creating
    ~/.md-to-pdf/audit.jsonl on every CI runner.
    """
    monkeypatch.delenv("MD_PDF_AUDIT_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    log = AuditLogger()
    assert log._path == tmp_path / ".md-to-pdf" / "audit.jsonl"
    # Constructor is lazy — file should not exist yet.
    assert not log._path.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only permissions test")
def test_widened_permissions_re_tightened_on_next_write(tmp_path: Path) -> None:
    """If a third party widens the audit file to 0o644, the next event
    re-applies 0o640.
    """
    log = AuditLogger(path=tmp_path / "audit.jsonl")
    log.log_error(render_id="r", duration_ms=1, code="A", message="a")
    os.chmod(tmp_path / "audit.jsonl", 0o644)
    log.log_error(render_id="r", duration_ms=1, code="B", message="b")
    mode = stat.S_IMODE((tmp_path / "audit.jsonl").stat().st_mode)
    assert mode == 0o640
