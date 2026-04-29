#!/usr/bin/env python3
"""Release-blocking acceptance audit.

Reads `docs/acceptance/<version>.yaml` (default: v0.2.1.yaml), then verifies:

  1. Every required golden baseline file exists and is non-empty
     (closes the silent-skip loophole).
  2. Every deterministic sha256 baseline exists and is non-empty.
  3. pyproject.toml [project.optional-dependencies] includes every required
     extras name from the matrix.
  4. examples/brands/ contains at least `min_count` brand directories.
  5. spec-file frontmatter `acceptance:` block matches acceptance.yaml.
     This catches the case where a spec adds a new promise but the yaml
     (and hence CI) is never updated to enforce it.

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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomllib
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ACCEPTANCE = REPO_ROOT / "docs" / "acceptance" / "v0.2.1.yaml"

# Deterministic sha256 baselines are platform-specific (PDF rasterisation
# varies per-OS) — the canonical platform is Linux. On macOS/Windows the
# audit downgrades them to informational unless --strict-platform is set.
_LINUX = sys.platform.startswith("linux")


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


def check_deterministic_sha256(
    spec: dict[str, Any],
    report: AuditReport,
    *,
    strict_platform: bool = False,
) -> None:
    """Deterministic-mode sha256 baselines per spec §2.3 / §7.2.1.

    These baselines are platform-specific (Linux is canonical). On non-Linux
    platforms the missing-file failure downgrades to a 'pass with note'
    unless ``--strict-platform`` was passed. CI on Linux always enforces
    strictly.
    """
    section = spec.get("deterministic_sha256", {})
    if not section:
        return  # optional
    directory = REPO_ROOT / section["directory"]
    extension = section["extension"]
    enforce = _LINUX or strict_platform
    for fixture_name in section.get("fixtures", []):
        baseline = directory / f"{fixture_name}{extension}"
        rel = baseline.relative_to(REPO_ROOT)
        if not baseline.exists():
            msg = f"missing deterministic sha256 baseline: {rel} (fixture={fixture_name})"
            if enforce:
                report.add_fail(msg)
            else:
                report.add_pass(
                    f"sha256 baseline absent (platform-conditional, non-Linux dev OK): {rel}"
                )
            continue
        if baseline.stat().st_size == 0:
            msg = f"empty deterministic sha256 baseline: {rel} (fixture={fixture_name})"
            if enforce:
                report.add_fail(msg)
            else:
                report.add_pass(f"sha256 baseline empty (non-Linux): {rel}")
            continue
        report.add_pass(f"sha256 baseline ok: {rel}")


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
            f"pyproject.toml missing required extras: {sorted(missing)} (found: {sorted(extras)})"
        )
    else:
        report.add_pass(f"extras matrix ok: {sorted(required)} present")


def check_example_brands(spec: dict[str, Any], report: AuditReport) -> None:
    """examples/brands/ must contain at least min_count brand directories.

    `min_count <= 0` disables the check entirely (useful for synthetic specs
    in unit tests that don't exercise this dimension).
    """
    section = spec.get("example_brands", {})
    if not section:
        return
    min_count = int(section.get("min_count", 1))
    if min_count <= 0:
        return
    directory = REPO_ROOT / section["directory"]
    if not directory.exists():
        report.add_fail(f"example brands directory missing: {section['directory']}")
        return
    brands = [p for p in directory.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if len(brands) < min_count:
        report.add_fail(
            f"example brands count {len(brands)} < min {min_count} "
            f"(found: {sorted(b.name for b in brands)})"
        )
    else:
        report.add_pass(f"example brands ok: {len(brands)} present (min {min_count})")


def _parse_spec_frontmatter(spec_path: Path) -> dict[str, Any] | None:
    """Extract YAML frontmatter from a markdown spec file.

    Returns the parsed mapping, or None if the file has no frontmatter
    (frontmatter is identified by a `---\n…\n---` block at file head).
    """
    if not spec_path.exists():
        return None
    text = spec_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    # Locate the closing `---` on its own line.
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    frontmatter_text = text[4:end]
    try:
        parsed = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def check_spec_drift(spec: dict[str, Any], report: AuditReport) -> None:
    """Detect drift between spec frontmatter and acceptance.yaml.

    For every spec file listed under `spec_files`, parse its YAML frontmatter
    and compare its `acceptance:` block against the equivalent fields in
    acceptance.yaml. Mismatches (added/removed fixtures, extras, etc.) fail.

    The intent is: if a spec promises a new fixture, the acceptance.yaml
    must be updated in the same PR — otherwise the new promise is unenforced
    and CI passes silently. This is the deepest root cause of the original
    deviation report.
    """
    spec_files = spec.get("spec_files", [])
    if not spec_files:
        return

    yaml_fixtures = {f["name"] for f in spec.get("golden_baselines", {}).get("fixtures", [])}
    yaml_deterministic = set(spec.get("deterministic_sha256", {}).get("fixtures", []))
    yaml_extras_required = set(spec.get("extras_matrix", {}).get("required", []))
    yaml_brands_min = int(spec.get("example_brands", {}).get("min_count", 0))

    for spec_relpath in spec_files:
        spec_path = REPO_ROOT / spec_relpath
        frontmatter = _parse_spec_frontmatter(spec_path)
        if frontmatter is None:
            report.add_fail(
                f"spec drift: {spec_relpath} has no parseable YAML frontmatter "
                f"with an `acceptance:` block"
            )
            continue
        acceptance_block = frontmatter.get("acceptance")
        if not isinstance(acceptance_block, dict):
            report.add_fail(
                f"spec drift: {spec_relpath} frontmatter is missing the `acceptance:` block"
            )
            continue

        spec_fixtures = set(acceptance_block.get("fixtures", []))
        spec_deterministic = set(acceptance_block.get("deterministic", []))
        spec_extras = set(acceptance_block.get("extras", []))
        spec_brands_min = int(acceptance_block.get("example_brands_min", 0))

        problems: list[str] = []
        if spec_fixtures != yaml_fixtures:
            only_in_spec = sorted(spec_fixtures - yaml_fixtures)
            only_in_yaml = sorted(yaml_fixtures - spec_fixtures)
            if only_in_spec:
                problems.append(f"fixtures promised in spec but missing from yaml: {only_in_spec}")
            if only_in_yaml:
                problems.append(f"fixtures in yaml but absent from spec: {only_in_yaml}")
        if spec_deterministic != yaml_deterministic:
            problems.append(
                f"deterministic mismatch: spec={sorted(spec_deterministic)} "
                f"yaml={sorted(yaml_deterministic)}"
            )
        if not yaml_extras_required.issubset(spec_extras):
            missing_in_spec = sorted(yaml_extras_required - spec_extras)
            problems.append(
                f"yaml requires extras not declared in spec frontmatter: {missing_in_spec}"
            )
        if spec_brands_min != yaml_brands_min:
            problems.append(
                f"example_brands_min mismatch: spec={spec_brands_min} yaml={yaml_brands_min}"
            )

        if problems:
            joined = "\n      ".join(problems)
            report.add_fail(f"spec drift in {spec_relpath}:\n      {joined}")
        else:
            report.add_pass(f"spec frontmatter aligned with yaml: {spec_relpath}")


def check_pytest_strict(spec: dict[str, Any], report: AuditReport) -> None:
    """Run the configured pytest invocation in strict-golden mode.

    A passing run proves baselines are not just present but content-correct.
    The literal token "python" is rewritten to ``sys.executable`` so the
    pytest run always uses the same interpreter as the audit script (i.e.
    the venv with project deps installed), regardless of PATH.
    """
    cmd = spec.get("pytest_strict_command")
    if not cmd:
        return
    resolved = [sys.executable if tok == "python" else tok for tok in cmd]
    proc = subprocess.run(  # noqa: S603 — cmd source is the repo's own acceptance.yaml
        resolved,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        report.add_pass(f"pytest strict run ok: {' '.join(cmd)}")
    else:
        tail = (proc.stdout + proc.stderr).strip().splitlines()
        excerpt = "\n      ".join(tail[-25:]) if tail else "(no output)"
        report.add_fail(
            f"pytest strict run failed (exit {proc.returncode}): {' '.join(cmd)}\n      {excerpt}"
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
    strict_platform: bool = False,
) -> AuditReport:
    spec = load_spec(acceptance_path)
    report = AuditReport()
    check_golden_baselines(spec, report)
    check_deterministic_sha256(spec, report, strict_platform=strict_platform)
    check_extras_matrix(spec, report)
    check_example_brands(spec, report)
    check_spec_drift(spec, report)
    if not skip_pytest:
        check_pytest_strict(spec, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--acceptance",
        type=Path,
        default=DEFAULT_ACCEPTANCE,
        help="Path to acceptance yaml (default: docs/acceptance/v0.2.1.yaml)",
    )
    parser.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip the pytest --strict-golden run (fast local iteration only)",
    )
    parser.add_argument(
        "--strict-platform",
        action="store_true",
        help=(
            "Enforce platform-conditional baselines (Linux-only sha256) on all "
            "platforms. CI on Linux runners always behaves as if this is set."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a structured JSON report on stdout",
    )
    args = parser.parse_args(argv)

    try:
        report = run_audit(
            args.acceptance,
            skip_pytest=args.skip_pytest,
            strict_platform=args.strict_platform,
        )
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
