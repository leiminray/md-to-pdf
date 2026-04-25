# Plan 1 (Walking Skeleton) — Review Patches

**Date:** 2026-04-26
**Patches against:** [`2026-04-26-md-to-pdf-v2.0-plan-1-walking-skeleton.md`](2026-04-26-md-to-pdf-v2.0-plan-1-walking-skeleton.md)
**Reviewer:** sophie.leiyixiao@gmail.com (cold review of authored plan)
**Apply how:** patches are independent. Apply all, a subset, or skip — each carries its own rationale. Plan 1 source file is **not modified by this document**.

---

## Severity Legend

| Tag | Meaning |
|---|---|
| 🔴 Critical | Will cause test/runtime failure during execution |
| 🟡 Important | Spec drift or UX trap; should fix in Plan 1, not defer |
| 🟢 Polish | Style / dead code / minor inconsistency |

## Patch Summary

| ID | Severity | Task | Topic |
|---|---|---|---|
| P1-001 | 🔴 | 9, 12 | `atomic_write` must guard against pre-closed file |
| P1-002 | 🔴 | 13 | `CliRunner` test uses `result.stderr_bytes` without `mix_stderr=False` |
| P1-003 | 🟡 | 11 | CJK input silently renders tofu — fail loudly to match spec §2.1.2 step 5 |
| P1-004 | 🟡 | 13 | No-op CLI flags create UX trap; mark `hidden=True` until later plans wire them |
| P1-005 | 🟡 | 13 | Test name says "exits 4" but asserts 2 — rename + TODO marker for Plan 5 |
| P1-006 | 🟢 | 8 | `getSampleStyleSheet()` called twice in `engine_reportlab.render()` |
| P1-007 | 🟢 | 8 | Heading-style fallback at `i <= 4` should be `i <= 6` (sample stylesheet has 1–6) |
| P1-008 | 🟢 | 10 | `test_level_filtering` calls `capsys.readouterr()` twice (second is empty) |
| P1-009 | 🟢 | 5 | AST `Forward declarations … see end of module` comment references nonexistent `Node` union |
| P1-010 | 🟢 | 14 | `tests/conftest.py` `sys.path.insert` is redundant under editable install |
| P1-011 | 🟢 | 13 | `_resolve_default_user`: lazy `import os` / `import getpass` can move to module top |

---

## P1-001 🔴 — `atomic_write` must guard against pre-closed file

**Location:** Task 9 Step 3 (`src/mdpdf/cache/tempfiles.py`); also relevant to Task 12 Step 3.

### Problem

`atomic_write` yields a binary file object to its caller. In Task 12, `ReportLabEngine.render()` passes that file to `SimpleDocTemplate(fp, …).build(...)`. ReportLab's behaviour when given a user-provided file-like object is implementation-specific across versions: some code paths leave the file open (caller owns it), others call `fp.close()` after writing the PDF trailer.

If ReportLab closes the file, the post-yield section in `atomic_write`:

```python
yield f
f.flush()                  # ← raises ValueError on closed file
os.fsync(f.fileno())       # ← raises ValueError on closed file
```

throws `ValueError: I/O operation on closed file`, the `os.replace(tmp_path, target)` never runs, and the user gets a partial-or-missing PDF instead of the expected output.

### Patched code

In `src/mdpdf/cache/tempfiles.py`, replace the `atomic_write` body with:

```python
@contextmanager
def atomic_write(target: Path) -> Iterator:
    """Open a file for binary write, finalising via atomic rename.

    On exception, the partial file is removed and the original (if any) is
    untouched. Robust to consumers that close the file themselves
    (e.g., ReportLab's SimpleDocTemplate in some 4.x code paths).
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = secrets.token_hex(8)
    tmp_path = target.with_suffix(target.suffix + f".tmp.{suffix}")
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as f:
            yield f
            # Caller may have closed the file (ReportLab does this in some paths).
            # Only flush/fsync if still open — closed file is fine, the bytes are
            # already on disk via the os.fdopen context manager exit.
            if not f.closed:
                f.flush()
                os.fsync(f.fileno())
        os.replace(tmp_path, target)
    except BaseException:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise
```

### Add a regression test

Append to `tests/unit/cache/test_tempfiles.py`:

```python
def test_atomic_write_tolerates_consumer_closing_file(tmp_path: Path):
    """Mirrors the ReportLab pattern: consumer may close fp before context exit."""
    target = tmp_path / "consumer-closed.bin"
    with atomic_write(target) as f:
        f.write(b"payload")
        f.close()
    assert target.read_bytes() == b"payload"
```

### Rationale

Defensive guard is a 3-line addition with no downside. Even if ReportLab 4.x in fact never closes the file, the guard documents the invariant and prevents future regressions if ReportLab's behaviour changes.

---

## P1-002 🔴 — CLI test uses `result.stderr_bytes` without `mix_stderr=False`

**Location:** Task 13 Step 1 (`tests/unit/test_cli.py`), test `test_render_template_other_than_generic_exits_2`.

### Problem

```python
def test_render_template_other_than_generic_exits_2(tmp_path: Path):
    runner = CliRunner()                                   # default: mix_stderr=True
    result = runner.invoke(main, [str(src), "-o", str(out), "--template", "quote"])
    assert result.exit_code == 2
    assert "TEMPLATE_NOT_FOUND" in result.output \
        or "TEMPLATE_NOT_FOUND" in result.stderr_bytes.decode()
                                  # ↑ in mixed mode, stderr_bytes is None or raises
```

Click 8.x `CliRunner` defaults to `mix_stderr=True`, which routes stderr into `result.output` and leaves `result.stderr_bytes` either `None` (8.0–8.1) or a captured stream that's already merged (8.2+). Accessing `.decode()` on `None` raises `AttributeError`; on the merged stream the substring check is duplicate work.

### Patched code

Replace the test with:

```python
def test_render_template_other_than_generic_exits_2(tmp_path: Path):
    src = tmp_path / "in.md"
    src.write_text("# x")
    out = tmp_path / "out.pdf"
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(main, [str(src), "-o", str(out), "--template", "quote"])
    assert result.exit_code == 2
    assert "TEMPLATE_NOT_FOUND" in result.stderr
```

### Rationale

Setting `mix_stderr=False` makes `result.stderr` the captured stderr directly (a `str`, not bytes), eliminating the brittle `or` clause. Tests that assert *which* stream errors go to are more useful than tests that fudge the question with `output or stderr`.

### Knock-on check

Audit other tests in the same file. `test_render_writes_pdf` and `test_render_json_emits_render_result` both assert `result.output` strictness; once `mix_stderr=False` is the default, those tests should still pass because logs go to stderr (per `cli.py` configuration) — but verify that `--json` output goes to stdout cleanly with no log bleed.

---

## P1-003 🟡 — CJK input silently renders tofu (spec §2.1.2 step 5 violation)

**Location:** Task 11 Step 3 (`src/mdpdf/pipeline.py`, `Pipeline.render` validate phase).

### Problem

Foundation spec §2.1.2 step 5 says: *"`fonts/manager`: confirm CJK fonts available iff input markdown contains CJK chars; else fail loudly with `FONT_NOT_INSTALLED`."*

Plan 1 explicitly defers `fonts/manager.py` to Plan 2 (correct scoping). However, the Plan 1 minimal `ReportLabEngine` uses `getSampleStyleSheet()` which configures Helvetica — Helvetica has zero CJK glyphs. If a user feeds the walking skeleton CJK input (e.g., `# 你好`), the engine renders character-position rectangles ("tofu") with no warning.

Users will conclude v2.0 broke CJK support, undermining the whole rationale for the existing v1.8.9 CJK story (the user is on macOS and reads/writes Simplified Chinese — this matters).

### Patched code

Add to `src/mdpdf/pipeline.py` `Pipeline.render()`, immediately after the template-allowlist check and before the `_log.info("render.start", …)` line:

```python
        # Spec §2.1.2 step 5: fail loudly on CJK input until font manager ships in Plan 2.
        # We use a byte-level CJK detector here (no font registry needed) — the proper
        # font/manager.py with brand-pack font resolution lands in Plan 2.
        if request.source_type == "path":
            _preview = Path(request.source).read_bytes()[:65536].decode("utf-8", errors="ignore")
        else:
            assert isinstance(request.source, str)
            _preview = request.source[:65536]
        if any(_is_cjk(c) for c in _preview):
            from mdpdf.errors import FontError
            raise FontError(
                code="FONT_NOT_INSTALLED",
                user_message=(
                    "Input contains CJK characters but v2.0a1 walking skeleton ships "
                    "no CJK font support. Use the v1.8.9 monolith "
                    "(`scripts/md_to_pdf.py`) for CJK input until Plan 2 lands."
                ),
                render_id=render_id,
            )
```

Add helper at module top in `src/mdpdf/pipeline.py`:

```python
def _is_cjk(ch: str) -> bool:
    """Detect Chinese/Japanese/Korean code points (CJK Unified, Hiragana, Katakana, Hangul)."""
    cp = ord(ch)
    return (
        0x3040 <= cp <= 0x309F      # Hiragana
        or 0x30A0 <= cp <= 0x30FF   # Katakana
        or 0x3400 <= cp <= 0x4DBF   # CJK Extension A
        or 0x4E00 <= cp <= 0x9FFF   # CJK Unified
        or 0xAC00 <= cp <= 0xD7AF   # Hangul Syllables
        or 0xF900 <= cp <= 0xFAFF   # CJK Compatibility
    )
```

### Add a regression test

Append to `tests/unit/test_pipeline.py`:

```python
def test_pipeline_fails_loudly_on_cjk_input(tmp_path: Path):
    from mdpdf.errors import FontError
    pipeline = Pipeline.from_env()
    req = RenderRequest(
        source="# 你好世界",
        source_type="content",
        output=tmp_path / "cjk.pdf",
    )
    try:
        pipeline.render(req)
    except FontError as e:
        assert e.code == "FONT_NOT_INSTALLED"
        assert "CJK" in e.user_message
        assert not (tmp_path / "cjk.pdf").exists()
    else:
        raise AssertionError("expected FontError on CJK input in v2.0a1")
```

### Rationale

~25 lines of code closes a real spec violation and prevents user confusion. Plan 2 will replace the byte-level detector with a proper font-manager check that distinguishes "CJK present + font registered" (✓ proceed) from "CJK present + no font" (raise). The byte detector remains as the cheap pre-check; nothing wasted.

---

## P1-004 🟡 — No-op CLI flags create UX trap

**Location:** Task 13 Step 3 (`src/mdpdf/cli.py`).

### Problem

The Plan 1 CLI declares four flags that look fully functional but are no-ops:

| Flag | Plan 1 behaviour | Implemented in |
|---|---|---|
| `--deterministic` | Stored in `RenderRequest`; never read | Plan 4 |
| `--watermark-user` | Stored in `WatermarkOptions`; never applied | Plan 4 |
| `--no-audit` | Stored as `audit_enabled=False`; no audit log exists | Plan 4 |
| `--locale` | Stored in `RenderRequest`; no header/footer uses it | Plan 2+ |

A user passing `--deterministic` reasonably expects bit-identical output across runs and will report a "non-determinism bug" when timestamps differ. A user passing `--watermark-user "alice"` will be confused that the PDF has no visible watermark.

### Patched code

In `src/mdpdf/cli.py`, modify the four `@click.option` decorators to add `hidden=True`:

```python
@click.option("--template", default="generic", show_default=True,
              help="Template id; v2.0 supports only 'generic'.")
@click.option("--locale", default="en", show_default=True, hidden=True,
              help="(v2.0a1: no-op; locale-aware header/footer lands in Plan 2+.)")
@click.option("--deterministic", is_flag=True, default=False, hidden=True,
              help="(v2.0a1: no-op; deterministic mode lands in Plan 4.)")
@click.option("--no-audit", is_flag=True, default=False, hidden=True,
              help="(v2.0a1: no-op; audit log lands in Plan 4.)")
@click.option("--watermark-user", default=None, hidden=True,
              help="(v2.0a1: no-op; watermarking lands in Plan 4.)")
@click.option("--json", "json_output", is_flag=True, default=False,
              help="Emit RenderResult as JSON to stdout.")
```

When a future plan implements the feature, remove `hidden=True` and update the help string.

Optionally, also add a runtime warning when a hidden flag is non-default. Before `pipeline.render(req)`:

```python
    if deterministic:
        click.echo("warning: --deterministic accepted but not yet implemented (lands in Plan 4)", err=True)
    if watermark_user:
        click.echo("warning: --watermark-user accepted but watermarking not yet implemented (lands in Plan 4)", err=True)
```

(Skip the warning for `--no-audit` and `--locale` since those defaults match no-op behaviour anyway.)

### Add tests

Append to `tests/unit/test_cli.py`:

```python
def test_help_does_not_advertise_unimplemented_flags():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
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
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(main, [str(src), "-o", str(out), "--deterministic"])
    assert result.exit_code == 0
    assert "not yet implemented" in result.stderr
```

### Rationale

`hidden=True` keeps the option signatures stable (forward-compat for Plan 4) without lying to users about what works today. The runtime warning catches users who learned the flag from somewhere else and tried it.

---

## P1-005 🟡 — Test name says "exits 4" but asserts 2

**Location:** Task 13 Step 1 (`tests/unit/test_cli.py`).

### Problem

```python
def test_render_missing_input_exits_4(tmp_path: Path):       # ← name says 4
    ...
    assert result.exit_code == 2                              # ← asserts 2
```

The test comment correctly explains *why* it's 2 (Click rejects the path before our code maps it to `RESOURCE_MISSING`), but the divergence between name and assertion is itself a smell — and the spec §6.1 row 4 (exit 4 = "Resource missing") suggests Plan 5 may want to take over path validation from Click to be spec-compliant.

### Patched code

```python
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
```

### Rationale

Test name now matches behaviour. The TODO captures the intent so Plan 5 doesn't lose the deferred work.

---

## P1-006 🟢 — `getSampleStyleSheet()` called twice in `ReportLabEngine.render()`

**Location:** Task 8 Step 3 (`src/mdpdf/render/engine_reportlab.py`).

### Problem

```python
def render(self, document: Document, output: Path) -> int:
    flowables = self._convert(document)
    styles = getSampleStyleSheet()       # ← line 1598; never used
    page_count = [0]
    ...

def _convert(self, document: Document) -> list[Flowable]:
    styles = getSampleStyleSheet()       # ← line 1621; this is the one that matters
    ...
```

The first call's result is bound but never read.

### Patched code

Delete the `styles = getSampleStyleSheet()` line from `render()` (line ~1598). `_convert()` already gets its own.

### Rationale

Dead code; ruff's `F841` (`local variable assigned but never used`) would flag this.

---

## P1-007 🟢 — Heading-style fallback at `i <= 4` should be `i <= 6`

**Location:** Task 8 Step 3 (`src/mdpdf/render/engine_reportlab.py`, `_convert`).

### Problem

```python
h_styles = {
    i: ParagraphStyle(
        f"H{i}",
        parent=styles[f"Heading{i}"] if i <= 4 else styles["Heading4"],
    )
    for i in range(1, 7)
}
```

ReportLab's `getSampleStyleSheet()` provides `Heading1` through `Heading6`. The fallback at `i <= 4` collapses h5 and h6 onto Heading4 styling for no documented reason.

### Patched code

```python
h_styles = {
    i: ParagraphStyle(f"H{i}", parent=styles[f"Heading{i}"])
    for i in range(1, 7)
}
```

### Rationale

Plan 1 doesn't have brand-driven typography yet; using all 6 sample heading levels gives engineers a recognisable visual hierarchy when eyeballing walking-skeleton output.

---

## P1-008 🟢 — `test_level_filtering` calls `capsys.readouterr()` twice

**Location:** Task 10 Step 1 (`tests/unit/test_logging.py`).

### Problem

```python
def test_level_filtering(capsys):
    ...
    captured = capsys.readouterr().err + capsys.readouterr().out
    #                ^^ first call drains buffer       ^^ second call sees empty
```

`capsys.readouterr()` consumes the buffer; the second call returns empty `out`/`err`. The test happens to pass because the assertions check `"kept" in captured` (✓ present in first call's `.err`) and `"filtered_out" not in captured` (✓ trivially true), but the code is misleading and could mask a real regression where the level filter stops working.

### Patched code

```python
def test_level_filtering(capsys):
    configure_logging(json_output=True, level="WARNING")
    log = structlog.get_logger("test")
    log.info("filtered_out")
    log.warning("kept")
    captured = capsys.readouterr()
    combined = captured.err + captured.out
    assert "kept" in combined
    assert "filtered_out" not in combined
```

### Rationale

One `readouterr()` call, both streams checked — same assertion intent, accurate semantics.

---

## P1-009 🟢 — AST `Forward declarations` comment references nonexistent `Node` union

**Location:** Task 5 Step 3 (`src/mdpdf/markdown/ast.py`).

### Problem

```python
# Forward declarations are deferred via `Node` union; see end of module.
```

The module defines `Inline` and `Block` unions at the end, but no `Node` union. The comment is misleading.

### Patched code

```python
# Forward references for `Inline` and `Block` are resolved by the
# `Inline` / `Block` Union aliases declared at the bottom of this module
# (Python evaluates dataclass annotations as strings under
# `from __future__ import annotations`).
```

### Rationale

Documentation accuracy. No behaviour change.

---

## P1-010 🟢 — `tests/conftest.py` `sys.path.insert` is redundant

**Location:** Task 14 Step 1 (`tests/conftest.py`).

### Problem

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

Every Plan 1 task instructs `pip install -e ".[dev]"` first, which adds `src/` to the package discovery path automatically (hatchling's editable install creates a `.pth` entry). The `sys.path.insert` is belt-and-braces but obscures the intended workflow ("you must `pip install -e .` before running tests").

### Patched code

Replace `tests/conftest.py` with:

```python
"""Repo-level pytest configuration.

Tests assume the package is installed editable (`pip install -e ".[dev]"`).
No sys.path manipulation here — that would mask install regressions.
"""
```

### Rationale

If editable install is broken, tests *should* fail at import — not silently work via the conftest workaround. Removing the workaround surfaces install bugs faster.

---

## P1-011 🟢 — `_resolve_default_user` lazy imports

**Location:** Task 13 Step 3 (`src/mdpdf/cli.py`).

### Problem

```python
def _resolve_default_user() -> str | None:
    import os
    import getpass
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return os.environ.get("USER") or os.environ.get("USERNAME")
```

Lazy imports are a Python idiom for breaking import cycles or avoiding unused-import overhead. Neither applies here — `os` and `getpass` are stdlib, cheap, and used elsewhere.

### Patched code

Add to the existing top-of-file imports in `cli.py`:

```python
import getpass
import os
```

Then simplify the function:

```python
def _resolve_default_user() -> str | None:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return os.environ.get("USER") or os.environ.get("USERNAME")
```

### Rationale

Module-top imports match PEP 8 and the rest of the file's style.

---

## Apply Order & Independence

All 11 patches are independent. Suggested order if applying as separate commits:

1. **P1-001** (atomic_write guard) — touches `tempfiles.py` + adds 1 test; no other patch depends on this.
2. **P1-002** (CliRunner mix_stderr) — touches `test_cli.py` only.
3. **P1-005** (test rename + TODO) — touches `test_cli.py` only.
4. **P1-003** (CJK fail-loud) — touches `pipeline.py` + adds 1 test.
5. **P1-004** (hidden CLI flags) — touches `cli.py` + adds 2 tests; mildly conflicts with P1-002 (both edit `test_cli.py`).
6. **P1-006 → P1-011** (polish) — six tiny commits, no inter-dependencies.

Recommended commit messages:

```
fix(cache): guard atomic_write against pre-closed file (P1-001)
fix(cli-test): use CliRunner(mix_stderr=False) for stderr assertion (P1-002)
test(cli): rename missing-input test + TODO for plan-5 spec compliance (P1-005)
feat(pipeline): fail loudly on CJK input until font manager ships (P1-003)
chore(cli): hide unimplemented flags from --help, warn on use (P1-004)
chore(render): remove duplicate getSampleStyleSheet call (P1-006)
chore(render): use all 6 sample heading levels (P1-007)
fix(test): single readouterr call in test_level_filtering (P1-008)
docs(ast): correct Forward-declarations comment (P1-009)
chore(tests): remove redundant sys.path manipulation in conftest (P1-010)
chore(cli): move getpass/os imports to module top (P1-011)
```

## Patch Acceptance Bar

After all 11 patches applied, Plan 1's existing 8 acceptance criteria still hold, plus:

- New tests added by P1-001, P1-003, P1-004 all green.
- `md-to-pdf --help` does not list `--deterministic`, `--watermark-user`, `--no-audit`, `--locale`.
- Rendering CJK markdown (`# 你好`) exits with code 4 (`FontError → FONT_NOT_INSTALLED`) rather than producing a tofu PDF.
- `ruff check` and `mypy --strict` remain clean.
