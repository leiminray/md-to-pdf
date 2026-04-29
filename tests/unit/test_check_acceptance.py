"""Unit tests for scripts/check_acceptance.py.

The audit tool is itself code — if it has a bug, the gate is silently broken
and we are back to the original failure mode (silent green CI). These tests
exercise each individual check in isolation against a synthetic acceptance
spec built in tmp_path.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_audit_module() -> Any:
    """Load scripts/check_acceptance.py as an importable module."""
    spec = importlib.util.spec_from_file_location(
        "check_acceptance",
        SCRIPTS_DIR / "check_acceptance.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_acceptance"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit() -> Any:
    return _load_audit_module()


# ---------------------------------------------------------------------------
# Synthetic-repo helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_pyproject(root: Path, extras: list[str]) -> Path:
    body = '[project]\nname = "x"\nversion = "0.0.0"\n'
    if extras:
        body += "\n[project.optional-dependencies]\n"
        for name in extras:
            body += f'{name} = []\n'
    return _write(root / "pyproject.toml", body)


def _make_acceptance(
    root: Path,
    *,
    fixtures: list[dict[str, Any]] | None = None,
    deterministic: list[str] | None = None,
    extras_required: list[str] | None = None,
    example_brands_min: int = 0,
    spec_files: list[str] | None = None,
) -> Path:
    spec: dict[str, Any] = {
        "schema_version": "1.0",
        "target_version": "test",
        "golden_baselines": {
            "layers": [
                {"id": "ast", "directory": "tests/golden/baselines/ast", "extension": ".txt"},
            ],
            "fixtures": fixtures or [],
        },
        "deterministic_sha256": {
            "directory": "tests/golden/baselines/sha256",
            "extension": ".txt",
            "fixtures": deterministic or [],
        },
        "extras_matrix": {"required": extras_required or []},
        "example_brands": {"directory": "examples/brands", "min_count": example_brands_min},
        "spec_files": spec_files or [],
    }
    return _write(root / "acceptance.yaml", yaml.safe_dump(spec))


# ---------------------------------------------------------------------------
# Test cases — one per check
# ---------------------------------------------------------------------------


def test_baseline_present_passes(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    _write(tmp_path / "tests/golden/baselines/ast/uat-en.txt", "non-empty\n")
    spec_path = _make_acceptance(
        tmp_path,
        fixtures=[{"name": "uat-en", "required_layers": ["ast"]}],
    )

    report = audit.run_audit(spec_path, skip_pytest=True)
    assert report.ok, report.failures
    assert any("baseline ok" in p for p in report.passes)


def test_baseline_missing_fails(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    spec_path = _make_acceptance(
        tmp_path,
        fixtures=[{"name": "uat-en", "required_layers": ["ast"]}],
    )

    report = audit.run_audit(spec_path, skip_pytest=True)
    assert not report.ok
    assert any("missing baseline" in f for f in report.failures)


def test_baseline_empty_fails(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A zero-byte file would slip through naive 'exists' check — verify we catch it."""
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    _write(tmp_path / "tests/golden/baselines/ast/uat-en.txt", "")
    spec_path = _make_acceptance(
        tmp_path,
        fixtures=[{"name": "uat-en", "required_layers": ["ast"]}],
    )

    report = audit.run_audit(spec_path, skip_pytest=True)
    assert not report.ok
    assert any("empty baseline" in f for f in report.failures)


def test_deterministic_baseline_required(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """On Linux (or with --strict-platform on macOS/Windows), missing sha256 fails."""
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "_LINUX", True)  # simulate Linux runner
    spec_path = _make_acceptance(tmp_path, deterministic=["uat-en"])

    report = audit.run_audit(spec_path, skip_pytest=True)
    assert not report.ok
    assert any("deterministic sha256" in f for f in report.failures)


def test_deterministic_baseline_skipped_on_non_linux(
    tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On non-Linux without --strict-platform, missing sha256 downgrades to pass."""
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "_LINUX", False)  # simulate macOS / Windows
    spec_path = _make_acceptance(tmp_path, deterministic=["uat-en"])

    report = audit.run_audit(spec_path, skip_pytest=True, strict_platform=False)
    assert report.ok, report.failures
    assert any("platform-conditional" in p for p in report.passes)


def test_deterministic_baseline_strict_platform_overrides(
    tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--strict-platform on a non-Linux dev box still fails missing sha256."""
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "_LINUX", False)
    spec_path = _make_acceptance(tmp_path, deterministic=["uat-en"])

    report = audit.run_audit(spec_path, skip_pytest=True, strict_platform=True)
    assert not report.ok
    assert any("deterministic sha256" in f for f in report.failures)


def test_extras_matrix_missing_fails(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    _make_pyproject(tmp_path, extras=["dev"])
    spec_path = _make_acceptance(tmp_path, extras_required=["dev", "docs"])

    report = audit.run_audit(spec_path, skip_pytest=True)
    assert not report.ok
    assert any("missing required extras" in f for f in report.failures)


def test_extras_matrix_present_passes(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    _make_pyproject(tmp_path, extras=["dev", "docs", "extra"])
    spec_path = _make_acceptance(tmp_path, extras_required=["dev", "docs"])

    report = audit.run_audit(spec_path, skip_pytest=True)
    assert report.ok, report.failures


def test_example_brands_below_min_fails(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    (tmp_path / "examples/brands/only-one").mkdir(parents=True)
    spec_path = _make_acceptance(tmp_path, example_brands_min=2)

    report = audit.run_audit(spec_path, skip_pytest=True)
    assert not report.ok
    assert any("example brands count" in f for f in report.failures)


def test_example_brands_meets_min_passes(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    (tmp_path / "examples/brands/one").mkdir(parents=True)
    (tmp_path / "examples/brands/two").mkdir(parents=True)
    (tmp_path / "examples/brands/.hidden").mkdir(parents=True)  # hidden ignored
    spec_path = _make_acceptance(tmp_path, example_brands_min=2)

    report = audit.run_audit(spec_path, skip_pytest=True)
    assert report.ok, report.failures


# ---------------------------------------------------------------------------
# Spec-drift check (the deepest root-cause guard)
# ---------------------------------------------------------------------------


def _make_spec_md(root: Path, name: str, acceptance: dict[str, Any]) -> Path:
    frontmatter = yaml.safe_dump({"acceptance": acceptance})
    body = f"---\n{frontmatter}---\n\n# Test spec\n"
    return _write(root / "docs" / name, body)


def test_spec_drift_aligned_passes(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    _write(tmp_path / "tests/golden/baselines/ast/foo.txt", "x\n")
    spec_path = _make_acceptance(
        tmp_path,
        fixtures=[{"name": "foo", "required_layers": ["ast"]}],
        spec_files=["docs/spec-aligned.md"],
    )
    _make_spec_md(
        tmp_path, "spec-aligned.md",
        {"fixtures": ["foo"], "deterministic": [], "extras": [], "example_brands_min": 0},
    )

    report = audit.run_audit(spec_path, skip_pytest=True)
    assert report.ok, report.failures
    assert any("spec frontmatter aligned" in p for p in report.passes)


def test_spec_drift_extra_fixture_in_spec_fails(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec promises a fixture that yaml does not enforce — most dangerous drift."""
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    _write(tmp_path / "tests/golden/baselines/ast/foo.txt", "x\n")
    spec_path = _make_acceptance(
        tmp_path,
        fixtures=[{"name": "foo", "required_layers": ["ast"]}],
        spec_files=["docs/spec.md"],
    )
    _make_spec_md(
        tmp_path, "spec.md",
        {
            "fixtures": ["foo", "extra-promised-but-not-enforced"],
            "deterministic": [], "extras": [], "example_brands_min": 0,
        },
    )

    report = audit.run_audit(spec_path, skip_pytest=True)
    assert not report.ok
    assert any("promised in spec but missing from yaml" in f for f in report.failures)


def test_spec_drift_missing_frontmatter_fails(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    spec_path = _make_acceptance(tmp_path, spec_files=["docs/no-frontmatter.md"])
    _write(tmp_path / "docs/no-frontmatter.md", "# plain markdown, no frontmatter\n")

    report = audit.run_audit(spec_path, skip_pytest=True)
    assert not report.ok
    assert any("no parseable YAML frontmatter" in f for f in report.failures)


# ---------------------------------------------------------------------------
# Driver / output formatting
# ---------------------------------------------------------------------------


def test_main_returns_nonzero_on_failure(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    spec_path = _make_acceptance(
        tmp_path,
        fixtures=[{"name": "missing", "required_layers": ["ast"]}],
    )
    rc = audit.main(["--acceptance", str(spec_path), "--skip-pytest"])
    assert rc == 1


def test_main_returns_zero_when_clean(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    spec_path = _make_acceptance(tmp_path)  # no fixtures, no extras → trivially clean
    rc = audit.main(["--acceptance", str(spec_path), "--skip-pytest"])
    assert rc == 0


def test_json_output_is_valid(tmp_path: Path, audit: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    spec_path = _make_acceptance(tmp_path)
    audit.main(["--acceptance", str(spec_path), "--skip-pytest", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "ok" in payload and "passes" in payload and "failures" in payload
