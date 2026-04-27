# Plan 5 — Review Patch (Pass 2)

Independent technical review found 8 additional defects that the first-pass review (P5-001..P5-012) did not capture. Apply these in addition to pass 1.

## Severity Legend

- 🔴 **Critical** — Plan as written will fail to compile, fail tests, or skip the work it claims to do.
- 🟡 **Notable** — Plan will run but introduces a real bug or silent mis-pass.
- 🟢 **Polish** — Cosmetic / consistency.

## Patch Summary

| ID | Severity | Area | Issue |
|---|---|---|---|
| P5-013 | 🔴 | Task 19 Step 3 | `_render_page()` uses `getattr(cls, "code", "")` which returns "" because `code` is an instance attribute |
| P5-014 | 🔴 | Task 14 Step 5 | `fonts_install` CLI command has inline `from mdpdf.fonts.installer import install_font` |
| P5-015 | 🔴 | Task 1 Step 3 | `test_json_output_parseable` has inline `import json` |
| P5-016 | 🔴 | Task 9 Step 1 | `test_uat_renders_baseline` and `test_uat_renders_with_brand_idimsum` have inline `import pypdf` |
| P5-017 | 🔴 | Task 14 Step 2 | `test_install_font_network_error_raises` has inline `import httpx` |
| P5-018 | 🟡 | Task 16 | Parity-gate fixture list is hardcoded — won't pick up new `uat-*.md` added later |
| P5-019 | 🟡 | Task 22 AC-5 | Asserts `'NotoSansSC' in txt` but AC-6 still has placeholder gate — will silently mis-pass |
| P5-020 | 🟡 | Pre-audit | Exit-code list omits `FontError → 4` |

---

## P5-013 🔴 — `_render_page()` uses `getattr(cls, "code", "")` — always returns empty

**Location:** Task 19 Step 3 (`scripts/gen_error_docs.py`, `_render_page()` function).

### Problem

P5-001 patches `_collect_error_classes()` and `main()` to use `cls.__name__` as the document identifier. But the `_render_page()` function (lines ~5112–5145 of the plan) was not updated:

```python
def _render_page(cls: type) -> tuple[str, str]:
    code = getattr(cls, "code", "")          # ← ALWAYS returns "" 
    template = f"# E{code}: {cls.__name__}\n..."
    return f"{code}.md", template
```

`MdpdfError.code` is an **instance attribute** set in `__init__(code, user_message, …)` — it is not a class attribute. `getattr(cls, "code", "")` returns the default `""`. The downstream `main()` then has `if not code: continue` (per P5-001) → every error class is skipped → the docs directory is empty.

### Patched code

Use `cls.__name__` as the page filename and header (matching P5-001's `main()` patch):

```python
def _render_page(cls: type) -> tuple[str, str]:
    name = cls.__name__
    template = (
        f"# {name}\n\n"
        f"## What it means\n\n"
        f"{cls.__doc__ or '(undocumented)'}\n\n"
        f"## How to fix\n\n"
        f"_Documentation pending — see source._\n"
    )
    return f"{name}.md", template
```

### Acceptance

After P5-001 + P5-013: running `scripts/gen_error_docs.py` writes one `<ClassName>.md` per error class (e.g., `BrandError.md`, `RendererError.md`) with non-empty content.

---

## P5-014 🔴 — `fonts_install` CLI command has an inline import

**Location:** Task 14 Step 5 (`src/mdpdf/cli.py`, `fonts_install` command body).

### Problem

```python
@fonts.command(name="install")
def fonts_install(...):
    from mdpdf.fonts.installer import install_font   # ← ruff PLC0415
    ...
```

P5-009 catches the same anti-pattern in `doctor_cmd` but does not flag `fonts_install`.

### Patched code

Hoist to module top of `cli.py`:

```python
from mdpdf.fonts.installer import install_font
```

### Acceptance

`ruff check src/mdpdf/cli.py` reports zero PLC0415 findings.

---

## P5-015 🔴 — `test_json_output_parseable` has inline `import json`

**Location:** Task 1 Step 3 (`tests/integration/test_comprehensive_uat.py`, `TestComprehensiveUAT.test_json_output_parseable`).

### Problem

```python
def test_json_output_parseable(...):
    import json   # ← ruff PLC0415
    ...
```

### Patched code

Move to module top.

### Acceptance

`ruff check tests/integration/test_comprehensive_uat.py` clean.

---

## P5-016 🔴 — `import pypdf` inlined inside test functions

**Location:** Task 9 Step 1 (`tests/integration/test_comprehensive_uat.py`, `test_uat_renders_baseline` lines ~2538–2543, `test_uat_renders_with_brand_idimsum` lines ~2558–2563).

### Problem

```python
def test_uat_renders_baseline(...):
    try:
        import pypdf
    except ImportError:
        pytest.skip("pypdf required")
    ...
```

`pypdf` is a hard dependency in `pyproject.toml [dev]`, so the try/except is dead code. The inline import is also flagged by ruff.

### Patched code

Hoist to module top:

```python
import pypdf
```

(Drop the try/skip — `pypdf` is installed in any env where these tests run.)

### Acceptance

`ruff check tests/integration/test_comprehensive_uat.py` clean and tests still collect.

---

## P5-017 🔴 — `test_install_font_network_error_raises` has inline `import httpx`

**Location:** Task 14 Step 2 (`tests/unit/fonts/test_installer.py`).

### Problem

```python
def test_install_font_network_error_raises(...):
    import httpx   # ← ruff PLC0415
    ...
```

### Patched code

Move to module top.

### Acceptance

`ruff check tests/unit/fonts/test_installer.py` clean.

---

## P5-018 🟡 — Parity-gate fixture list hardcoded

**Location:** Task 16 Step 1 (precondition language).

### Problem

Task 16's deletion gate enumerates a fixed list of fixtures (`uat-en.md`, `uat-cjk.md`, `uat-table.md`, `branch_ops_*`). If a new `uat-*.md` is authored between plan write-time and execution-time, it silently escapes the gate.

### Patched code

Replace the static list with a glob:

```python
GATE_FIXTURES = sorted(Path("fixtures").glob("uat-*.md")) + [
    Path("fixtures/branch_ops_ai_robot_product_brief.md"),
]
```

### Acceptance

`ls fixtures/uat-*.md` is the source of truth for what the gate runs.

---

## P5-019 🟡 — AC-5 asserts NotoSansSC presence but AC-6 has placeholder gate

**Location:** Task 22 AC-5 (line ~5682).

### Problem

```python
# AC-5
result = subprocess.run([MD_TO_PDF, "fonts", "list"], ...)
assert "NotoSansSC" in result.stdout
```

`fonts list` only shows `NotoSansSC` once `fonts install noto-sans-sc` has succeeded. AC-6 ("font sha256 placeholder replaced") gates that. If AC-6 is not yet fulfilled, AC-5 silently mis-passes (no install → no NotoSansSC → assertion fails for the *wrong* reason, blaming "fonts list" rather than the placeholder).

### Patched code

Tighten AC-5 to assert only built-in fonts that are guaranteed present:

```python
assert "Helvetica" in result.stdout  # built-in
# Conditional NotoSansSC check moved to AC-6.
```

### Acceptance

AC-5 passes regardless of whether AC-6 has run; AC-6 owns the NotoSansSC check.

---

## P5-020 🟡 — Pre-audit exit-code list omits `FontError → 4`

**Location:** Task 1 pre-audit, "exit code mapping".

### Problem

The pre-audit lists `BrandError → 3`, `SecurityError → 3`, `RendererError → 5` but omits `FontError → 4`. Any Plan-5 test that asserts an exit code for a font failure (e.g., Task 14 install errors) needs to use `4`, not `3`.

### Patched code

Update the pre-audit comment block to include:

```
FontError → 4
```

And spot-check Task 14 test assertions (`assert proc.returncode == 4` for install failures).

### Acceptance

`grep -nE "returncode == [0-9]" tests/unit/fonts/ tests/integration/test_comprehensive_uat.py` shows `4` (not `3` or `5`) for `FontError` cases.

---

## Apply Order

All 8 patches are independent. Suggested ordering:
1. P5-014 through P5-017 (inline-import fixes — touch different files; trivial).
2. P5-013 (gen_error_docs.py — touches a single function).
3. P5-018, P5-019, P5-020 (acceptance / scope tweaks — pure plan-doc edits).

## Patch Acceptance Bar

After P5-001..P5-020 applied:

- `ruff check src/ tests/ scripts/` — clean (no PLC0415 inline-import findings).
- `scripts/gen_error_docs.py` produces one `.md` per error class with non-empty content.
- `tests/integration/test_comprehensive_uat.py` and `tests/unit/fonts/test_installer.py` collect without ruff complaints.
- Task 22 AC-5 passes regardless of AC-6 state.

---

## Parity-Gate Architectural Note

Pass-2 review additionally observes that Plan 5's golden harness commits baselines from the v2.0 engine via `--update-golden` — proving v2.0 *self-consistency* across runs, not v1.8.9 ↔ v2.0 visual equivalence. CLAUDE.md says "diff-zero output for every existing fixtures/uat-*.md". If the user's intent is true v1↔v2 visual parity, Plan 5 needs an additional task that renders the same fixtures through both engines and asserts layout-fingerprint equality. If the user's intent is "v2.0 stability across CI runs", Plan 5 as-written is correct and this note is informational.

**Decision required from user:** Is the parity gate (a) v2.0 self-consistency across CI runs, or (b) v1.8.9 ↔ v2.0 visual equivalence? Plan 5 implements (a); CLAUDE.md text suggests (b).
