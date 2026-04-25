#!/usr/bin/env python3
"""
Check or bootstrap Mermaid rendering deps for md-to-pdf (mmdc + browser for Puppeteer).

Requires: Python venv already installed per requirements-md-pdf.txt (imports md_to_pdf).
Does not install Node.js — print a download link if `node` is missing.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

MERMAID_CLI_PACKAGE = "@mermaid-js/mermaid-cli"
MERMAID_CLI_MIN_MAJOR = 11  # Noto injection uses mmdc -c / -C (config + CSS); tested on 11.x
_SCRIPTS_DIR = Path(__file__).resolve().parent


def _warn_if_mmdc_too_old(mmdc_exe: str) -> None:
    """stderr warning when mmdc is older than MERMAID_CLI_MIN_MAJOR (best-effort parse)."""
    try:
        r = subprocess.run(
            [mmdc_exe, "-V"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    if r.returncode != 0:
        return
    line = (r.stdout or r.stderr or "").strip().splitlines()
    ver = line[0].strip() if line else ""
    if not ver:
        return
    major_s = ver.lstrip("vV").split(".")[0]
    try:
        major = int(major_s)
    except ValueError:
        return
    if major < MERMAID_CLI_MIN_MAJOR:
        print(
            f"Warning: mmdc reports {ver}; Noto-aligned Mermaid PNGs expect "
            f"@mermaid-js/mermaid-cli {MERMAID_CLI_MIN_MAJOR}.x or newer (--configFile / --cssFile).",
            file=sys.stderr,
        )


def _run(cmd: list[str], *, timeout: int | None, env: dict[str, str] | None = None) -> int:
    print("+", " ".join(cmd), flush=True)
    try:
        r = subprocess.run(cmd, timeout=timeout, env=env)
        return int(r.returncode)
    except subprocess.TimeoutExpired:
        print("Timed out.", file=sys.stderr)
        return 124
    except OSError as e:
        print(e, file=sys.stderr)
        return 1


def _which_node_npm_npx() -> tuple[str | None, str | None, str | None]:
    return shutil.which("node"), shutil.which("npm"), shutil.which("npx")


def _resolve_mmdc():
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    import md_to_pdf  # noqa: E402

    return md_to_pdf.resolve_mmdc_executable(), md_to_pdf._enriched_path()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Mermaid CLI (mmdc) check/install helper for md-to-pdf skill.",
    )
    ap.add_argument(
        "--auto-install",
        action="store_true",
        help=f"Run: npm install -g {MERMAID_CLI_PACKAGE} (needs npm + network; may require admin on some OS).",
    )
    ap.add_argument(
        "--puppeteer-chrome",
        action="store_true",
        help="Run: npx puppeteer browsers install chrome (large download; needs network).",
    )
    ap.add_argument(
        "--puppeteer-headless-shell",
        action="store_true",
        help=(
            "Run: npx puppeteer browsers install chrome-headless-shell "
            "(smaller; preferred on macOS when Cursor + mmdc would SIGABRT full Chrome)."
        ),
    )
    args = ap.parse_args()

    node, npm, npx = _which_node_npm_npx()
    if not node:
        print(
            "Node.js is not on PATH. Install an LTS release from https://nodejs.org/ "
            "then re-run this script.",
            file=sys.stderr,
        )
        return 1

    mmdc_path, ep = _resolve_mmdc()
    if mmdc_path:
        print(f"OK: mmdc -> {mmdc_path}")
        _warn_if_mmdc_too_old(mmdc_path)
    elif not args.auto_install:
        print("mmdc not found on PATH.", file=sys.stderr)
        print(
            "Fix one of:\n"
            f"  1) Install CLI globally: npm install -g {MERMAID_CLI_PACKAGE}\n"
            "  2) Re-run with: --auto-install\n"
            "  3) At PDF render time set MDPDF_MERMAID_NPX=1 (npx downloads per run; needs network).",
            file=sys.stderr,
        )
        return 1
    else:
        if not npm:
            print("npm not found next to node; install Node.js LTS (includes npm).", file=sys.stderr)
            return 1

        env = os.environ.copy()
        env["PATH"] = ep
        rc = _run([npm, "install", "-g", MERMAID_CLI_PACKAGE], timeout=600, env=env)
        if rc != 0:
            print(
                f"npm install -g failed (exit {rc}). Try in a terminal with sufficient permissions.",
                file=sys.stderr,
            )
            return rc

        # Same-shell PATH refresh: global npm bin is often not in the pre-install PATH snapshot.
        try:
            br = subprocess.run(
                [npm, "bin", "-g"],
                capture_output=True,
                text=True,
                timeout=15,
                env=os.environ.copy(),
            )
            if br.returncode == 0 and br.stdout.strip():
                gb = br.stdout.strip().splitlines()[-1].strip()
                if gb:
                    os.environ["PATH"] = gb + os.pathsep + os.environ.get("PATH", "")
        except (OSError, subprocess.TimeoutExpired):
            pass

        mmdc_path, ep = _resolve_mmdc()
        if not mmdc_path:
            print(
                "mmdc still not resolved. Open a new shell (PATH refresh) or run: hash -r",
                file=sys.stderr,
            )
            return 1
        print(f"OK: mmdc -> {mmdc_path}")
        _warn_if_mmdc_too_old(mmdc_path)

    if args.puppeteer_chrome or args.puppeteer_headless_shell:
        if not npx:
            print("npx not on PATH; skip Puppeteer browser install.", file=sys.stderr)
            return 0
        env_px = os.environ.copy()
        env_px["PATH"] = ep
        # Prefer headless-shell for macOS + IDE-driven mmdc; full "chrome" also installs
        # Google Chrome for Testing; both may exist after running both flags.
        browser_ids: list[str] = []
        if args.puppeteer_headless_shell:
            browser_ids.append("chrome-headless-shell")
        if args.puppeteer_chrome:
            browser_ids.append("chrome")
        for browser_id in browser_ids:
            px_rc = _run(
                [npx, "--yes", "puppeteer", "browsers", "install", browser_id],
                timeout=1200,
                env=env_px,
            )
            if px_rc != 0:
                print(
                    f"Puppeteer install failed for {browser_id!r}. "
                    " Install Microsoft Edge, run with --puppeteer-headless-shell, or set "
                    "PUPPETEER_EXECUTABLE_PATH; see md_to_pdf.py _apply_mermaid_puppeteer_env.",
                    file=sys.stderr,
                )
                return px_rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
