#!/usr/bin/env python3
"""Release-blocking acceptance audit.

Reads `docs/acceptance/<version>.yaml` (default: v0.2.1.yaml), then verifies:

  1. Every required golden baseline file exists and is non-empty
     (closes the silent-skip loophole).
  2. Every deterministic sha256 baseline exists and is non-empty.
  3. pyproject.toml [project.optional-dependencies] includes every required
     extras name from the matrix.
  4. examples/brands/ contains at least `min_count` brand directories.
  5. (Phase 2) spec-frontmatter ↔ acceptance.yaml are in sync.

Exits 0 on full pass, non-zero (with a structured report) on any gap.

Usage:
    python scripts/check_acceptance.py
    python scripts/check_acceptance.py --acceptance docs/acceptance/v0.2.1.yaml
    python scripts/check_acceptance.py --skip-pytest      # for fast local iteration
    python scripts/check_acceptance.py --json             # SIEM/CI output

Exit codes:
    0  all green
    1  one or more acceptance criteria failed
    2  audit script itself encountered a configuration error
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ACCEPTANCE = REPO_ROOT / "docs" / "acceptance" / "v0.2.1.yaml"


@dataclass
class AuditReport:
    """Structured result of an acceptance audit run."""

    passes: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def add_pass(self, msg: str) -> None:
        self.passes.append(msg)

    def add_fail(self, msg: str) -> None:
        self.failures.append(msg)

    def render_text(self) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append(f"Acceptance audit  ·  {len(self.passes)} pass  ·  {len(self.failures)} fail")
        lines.append("=" * 70)
        if self.failures:
            lines.append("\nFAILURES:")
            for f in self.failures:
                lines.append(f"  ✗ {f}")
        if self.passes:
            lines.append("\nPASSES:")
            for p in self.passes:
                lines.append(f"  ✓ {p}")
        return "\n".join(lines)

    def render_json(self) -> str:
        return json.dumps(
            {"ok": self.ok, "passes": self.passes, "failures": self.failures},
            indent=2,
        )


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_golden_baselines(spec: dict[str, Any], report: AuditReport) -> None:
    """Each fixture × layer must have a baseline file that exists and is non-empty."""
    section = spec.get("golden_baselines", {})
    layers = {layer["id"]: layer for layer in section.get("layers", [])}
    fixtures = section.get("fixtures", [])

    for fixture in fixtures:
        name = fixture["name"]
        for layer_id in fixture.get("required_layers", []):
            layer = layers.get(layer_id)
            if layer is None:
                report.add_fail(
                    f"fixture {name!r} requires layer {layer_id!r} but no such layer "
                    f"is defined in golden_baselines.layers"
                )
                continue
            baseline = REPO_ROOT / layer["directory"] / f"{name}{layer['extension']}"
            if not baseline.exists():
                report.add_fail(
                    f"missing baseline: {baseline.relative_to(REPO_ROOT)} "
                    f"(fixture={name}, layer={layer_id})"
                )
                continue
            if baseline.stat().st_size == 0:
                report.add_fail(
                    f"empty baseline: {baseline.relative_to(REPO_ROOT)} "
                    f"(fixture={name}, layer={layer_id})"
                )
                continue
            report.add_pass(f"baseline ok: {baseline.relative_to(REPO_ROOT)}")


def check_deterministic_sha256(spec: dict[str, Any], report: AuditReport) -> None:
    """Deterministic-mode sha256 baselines per spec §2.3 / §7.2.1."""
    section = spec.get("deterministic_sha256", {})
    if not section:
        return  # optional
    directory = REPO_ROOT / section["directory"]
    extension = section["extension"]
    for fixture_name in section.get("fixtures", []):
        baseline = directory / f"{fixture_name}{extension}"
        if not baseline.exists():
            report.add_fail(
                f"missing deterministic sha256 baseline: "
                f"{baseline.relative_to(REPO_ROOT)} (fixture={fixture_name})"
            )
            continue
        if baseline.stat().st_size == 0:
            report.add_fail(
                f"empty deterministic sha256 baseline: "
                f"{baseline.relative_to(REPO_ROOT)} (fixture={fixture_name})"
            )
            continue
        report.add_pass(f"sha256 baseline ok: {baseline.relative_to(REPO_ROOT)}")


def check_extras_matrix(spec: dict[str, Any], report: AuditReport) -> None:
    """pyproject.toml extras keyset must include every required entry."""
    matrix = spec.get("extras_matrix", {})
    required = set(matrix.get("required", []))
    if not required:
        return

    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.exists():
        report.add_fail("pyproject.toml not found at repo root")
        return

    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    extras = set((data.get("project") or {}).get("optional-dependencies", {}).keys())

    missing = required - extras
    if missing:
        report.add_fail(
            f"pyproject.toml missing required extras: {sorted(missing)} "
            f"(found: {sorted(extras)})"
        )
    else:
        report.add_pass(f"extras matrix ok: {sorted(required)} present")


def check_example_brands(spec: dict[str, Any], report: AuditReport) -> None:
    """examples/brands/ must contain at least min_count brand directories."""
    section = spec.get("example_brands", {})
    if not section:
        return
    directory = REPO_ROOT / section["directory"]
    min_count = int(section.get("min_count", 1))
    if not directory.exists():
        report.add_fail(f"example brands directory missing: {directory.relative_to(REPO_ROOT)}")
        return
    brands = [p for p in directory.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if len(brands) < min_count:
        report.add_fail(
            f"example brands count {len(brands)} < min {min_count} "
            f"(found: {sorted(b.name for b in brands)})"
        )
    else:
        report.add_pass(
            f"example brands ok: {len(brands)} present (min {min_count})"
        )


def check_pytest_strict(spec: dict[str, Any], report: AuditReport) -> None:
    """Run the configured pytest invocation in strict-golden mode.

    A passing run proves baselines are not just present but content-correct.
    """
    cmd = spec.get("pytest_strict_command")
    if not cmd:
        return
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        report.add_pass(f"pytest strict run ok: {' '.join(cmd)}")
    else:
        tail = (proc.stdout + proc.stderr).strip().splitlines()
        excerpt = "\n      ".join(tail[-25:]) if tail else "(no output)"
        report.add_fail(
            f"pytest strict run failed (exit {proc.returncode}): {' '.join(cmd)}\n"
            f"      {excerpt}"
        )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def load_spec(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"acceptance spec not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise SystemExit(f"acceptance spec is not a mapping: {path}")
    return data


def run_audit(
    acceptance_path: Path,
    *,
    skip_pytest: bool = False,
) -> AuditReport:
    spec = load_spec(acceptance_path)
    report = AuditReport()
    check_golden_baselines(spec, report)
    check_deterministic_sha256(spec, report)
    check_extras_matrix(spec, report)
    check_example_brands(spec, report)
    if not skip_pytest:
        check_pytest_strict(spec, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--acceptance",
        type=Path,
        default=DEFAULT_ACCEPTANCE,
        help=f"Path to acceptance yaml (default: {DEFAULT_ACCEPTANCE.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip the pytest --strict-golden run (fast local iteration only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a structured JSON report on stdout",
    )
    args = parser.parse_args(argv)

    try:
        report = run_audit(args.acceptance, skip_pytest=args.skip_pytest)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — top-level error reporter
        print(f"audit script failure: {exc!r}", file=sys.stderr)
        return 2

    if args.json:
        print(report.render_json())
    else:
        print(report.render_text())

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
