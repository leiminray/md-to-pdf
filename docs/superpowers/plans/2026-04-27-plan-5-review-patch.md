# Plan 5 (UAT + Golden Harness + Release) — Review Patches

**Date:** 2026-04-27
**Patches against:** [`2026-04-27-md-to-pdf-v2.0-plan-5-uat-golden-release.md`](2026-04-27-md-to-pdf-v2.0-plan-5-uat-golden-release.md)
**Reviewer:** sophie.leiyixiao@gmail.com (cold review by independent subagent; Tasks 1–22 authored, none yet executed)
**Apply how:** patches are independent unless noted. Apply all, a subset, or skip — each carries its own rationale. Plan 5 source file is **not modified** by this document.

---

## Severity Legend

| Tag | Meaning |
|---|---|
| 🔴 Critical | Will cause test/runtime failure during execution |
| 🟡 Important | Spec drift, pre-cooked lint/type error, or ordering bug — fix before executing |
| 🟢 Polish | Style / dead code / minor inconsistency |

## Patch Summary

| ID | Severity | Task | Topic |
|---|---|---|---|
| P5-001 | 🔴 | 19 | `gen_error_docs.py` looks for `MdPdfError` but actual base class is `MdpdfError` — produces zero output files |
| P5-002 | 🔴 | 14 | `FontError` raised with `message=` kwarg but `MdpdfError.__init__` takes `user_message=` — `TypeError` on every raise |
| P5-003 | 🔴 | 11 | GitHub Actions `services.kroki.image` with expression evaluating to empty string crashes non-Linux runners at workflow startup |
| P5-004 | 🔴 | 5 | `REQUIRED_XMP_KEYS` in `test_xmp_snapshots.py` lists 2 fabricated keys (`dc:description`, `xmp:ModifyDate`) and omits 2 spec-required keys (`mdpdf:BrandId`, `mdpdf:BrandVersion`) |
| P5-005 | 🔴 | 9 | `_BRAND_DIR` in `test_comprehensive_uat.py` points to `brand_kits/idimsum/` which is deleted in Task 18 — test permanently broken after Task 18 |
| P5-006 | 🔴 | 12 | `doctor.py` `_probe_mermaid()` and `_probe_brand_registry()` contain inline imports inside function bodies — violates P2-006/P2-007 lesson, triggers ruff E401 |
| P5-007 | 🟡 | 22 | `AC-6` placeholder check reads `src/mdpdf/fonts/manager.py` but the sha256 placeholder lives in `src/mdpdf/fonts/installer.py` — placeholder is never found, `AC-6` always passes vacuously |
| P5-008 | 🟡 | 5 | `_mask_volatile()` in `test_xmp_snapshots.py` has a double `import json` / `import json as _json` inside the function body — inline import + duplicate import |
| P5-009 | 🟡 | 12 | `doctor_cmd` in `cli.py` has `import json as _json` and `from mdpdf.diagnostics.doctor import run_doctor` as inline imports inside the command body — violates P2-006 |
| P5-010 | 🟡 | 14 | Task 14 also adds `FontError` to `src/mdpdf/errors.py`, but `FontError` already exists there (Plan 1/2) — duplicate class definition will shadow the existing one |
| P5-011 | 🟡 | 9 | `test_uat_xmp_metadata_complete` uses `required_keys` list that includes `mdpdf:Template` and `mdpdf:BrandVersion` / `mdpdf:BrandId` but omits `mdpdf:InputHash`, `xmp:CreatorTool`, `pdf:Producer`; list is inconsistent with spec §5.3 |
| P5-012 | 🟢 | 15 | Task 15 Step 1 test `test_render_legacy_brand_emits_deprecation_stderr` asserts `"deprecated" in result.output.lower()` but the deprecation notice is echoed to `err=True` (stderr) which in Click's default `CliRunner` mode is merged into `result.output` — this accidentally works, but the assertion description is misleading |

---

## P5-001 🔴 — `gen_error_docs.py` looks for wrong base-class name

**Location:** Task 19 Step 3 (`scripts/gen_error_docs.py`), `_collect_error_classes()` and the `CONTRIBUTING.md` description.

### Problem

```python
# gen_error_docs.py _collect_error_classes():
def _collect_error_classes() -> list[type]:
    base = getattr(_errors_module, "MdPdfError", None)   # ← wrong name
    if base is None:
        return []
```

The actual base class in `src/mdpdf/errors.py` (line 10) is named `MdpdfError` (lowercase `p`), not `MdPdfError`. `getattr(_errors_module, "MdPdfError", None)` returns `None`. The guard `if base is None: return []` silently exits with an empty list. The script prints:

```
WARNING: No MdPdfError subclasses found — check src/mdpdf/errors.py
```

and exits 0 — producing **zero `.md` files**. The unit test `test_gen_error_docs_produces_files` asserts `len(generated) >= 1` and will fail.

`CONTRIBUTING.md` in `docs/errors/` also describes the process referencing `MdPdfError` and `MdPdfWarning` — both wrong names. The actual hierarchy is: `MdpdfError` → `BrandError`, `TemplateError`, `FontError`, `RendererError`, `SecurityError`, `PipelineError`.

Additionally, `_collect_error_classes()` uses `getattr(cls, "code", "") or ""` to extract error codes. But `MdpdfError.code` is set as an **instance attribute** in `__init__`; there is no class-level `code` attribute. `getattr(cls, "code", "")` on the class returns `""` for every subclass, so every generated page would have no code and be skipped (`if not code: continue`). Even with the name fixed, no pages would be generated with the current code extraction approach.

### Patched code

```python
# In _collect_error_classes() — fix the name:
def _collect_error_classes() -> list[type]:
    base = getattr(_errors_module, "MdpdfError", None)  # correct spelling
    if base is None:
        return []
    results: list[type] = []
    for _name, obj in inspect.getmembers(_errors_module, inspect.isclass):
        if obj is base:
            continue
        if issubclass(obj, base):
            results.append(obj)
    results.sort(key=lambda c: c.__name__)   # sort by class name, not phantom code attr
    return results

# In _render_page() — use class name as the code since there is no class-level code attr:
def _render_page(cls: type) -> str:
    # MdpdfError subclasses do not have a class-level code attr;
    # derive the page identifier from the class name.
    code: str = cls.__name__
    hint: str = ""
    raw_doc = inspect.getdoc(cls) or f"{cls.__name__} error."
    doc = textwrap.dedent(raw_doc).strip()
    # ... rest of template ...
    return f"""\
# {code}

## What it means

{doc}

## How to fix

See the CLI output for the error code returned with this exception.
"""

# In main() — remove the `if not code: continue` guard:
for cls in classes:
    out_path = out_dir / f"{cls.__name__}.md"
    out_path.write_text(_render_page(cls), encoding="utf-8")
    print(f"  wrote {out_path.relative_to(_REPO_ROOT)}")
    written += 1
```

Also fix `CONTRIBUTING.md` and the `docs/errors/CONTRIBUTING.md` template:

```markdown
<!-- Before -->
This script walks `errors.py`, finds all `MdPdfError` subclasses...

<!-- After -->
This script walks `errors.py`, finds all `MdpdfError` subclasses...
```

### Rationale

`MdPdfError` does not exist; `MdpdfError` does. The `getattr` call returns `None`, the function returns `[]`, the script produces no output, and `test_gen_error_docs_produces_files` fails. The secondary issue (class-level `code` attribute not present) would prevent page generation even after the name fix.

---

## P5-002 🔴 — `FontError` raised with `message=` but constructor takes `user_message=`

**Location:** Task 14 Step 4 (`src/mdpdf/fonts/installer.py`), all four `raise FontError(...)` call sites.

### Problem

```python
# Task 14 installer.py — all raise sites use message=:
raise FontError(
    code="FONT_NOT_FOUND",
    message=f"Unknown font '{name}'. Available: {sorted(_KNOWN_FONTS)}",   # ← wrong
)
raise FontError(
    code="FONT_DOWNLOAD_FAILED",
    message=f"Failed to download font '{name}': {exc}",   # ← wrong
)
raise FontError(
    code="FONT_SHA256_MISMATCH",
    message=(
        f"sha256 mismatch for font '{name}'.\n"
        ...
    ),   # ← wrong
)
raise FontError(
    code="FONT_DOWNLOAD_FAILED",
    message=f"Failed to write font file '{dest_path}': {exc}",   # ← wrong
)
```

`MdpdfError.__init__` (the base class, `src/mdpdf/errors.py` line 13–24) has this signature:

```python
def __init__(
    self,
    code: str,
    user_message: str,          # ← parameter name is user_message, not message
    technical_details: str | None = None,
    render_id: str | None = None,
) -> None:
```

Every `raise FontError(code=..., message=...)` will raise:
```
TypeError: MdpdfError.__init__() got an unexpected keyword argument 'message'
```

Since `FontError` inherits directly from `MdpdfError` without overriding `__init__`, all four raises are broken.

### Patched code

```python
# Before (all four sites):
raise FontError(
    code="FONT_NOT_FOUND",
    message=f"Unknown font '{name}'. Available: {sorted(_KNOWN_FONTS)}",
)

# After (all four sites) — rename message= to user_message=:
raise FontError(
    code="FONT_NOT_FOUND",
    user_message=f"Unknown font '{name}'. Available: {sorted(_KNOWN_FONTS)}",
)
```

Apply the same rename to all four `raise FontError(...)` call sites in `installer.py`.

### Rationale

`MdpdfError.__init__` uses `user_message` as the positional-by-name second argument. `message=` is not a recognised parameter. All four raises — `FONT_NOT_FOUND`, `FONT_DOWNLOAD_FAILED` (×2), `FONT_SHA256_MISMATCH` — will raise `TypeError` before the `FontError` is even constructed.

---

## P5-003 🔴 — GitHub Actions `services.kroki.image` empty-string expression crashes non-Linux runners

**Location:** Task 11 Step 1 (`.github/workflows/ci.yml`), `jobs.test.services.kroki.image` expression.

### Problem

```yaml
# Task 11 ci.yml:
services:
  kroki:
    image: ${{ matrix.os == 'ubuntu-latest' && 'yuzutech/kroki:latest' || '' }}
    ports:
      - 8000:8000
    options: >-
      --health-cmd "wget -qO- http://localhost:8000/health || exit 1"
      ...
```

GitHub Actions YAML `services:` blocks are evaluated before the job steps and before `if:` conditions are applied. When the expression evaluates to `''` (an empty string on macOS/Windows runners), GitHub Actions does **not** silently skip the service — it attempts to pull a Docker image with an empty string name, which causes `Error: No such image: ''` at workflow startup. All macOS and Windows test cells will fail at the service-startup phase before any test code runs.

The implementation note in the plan (`"When the image is empty, GitHub silently skips the service container"`) is incorrect — this behaviour was removed and GitHub Actions now errors on empty service image names.

### Patched code

Use a `matrix.include` / `matrix.exclude` approach or a separate Linux-only Kroki job. The cleanest fix is to remove the `services:` block from the matrix job and instead move Kroki to the separate `golden` job (which already has a correct hardcoded Linux Kroki service):

```yaml
# In jobs.test — remove the services block entirely:
# services:           ← DELETE this entire block
#   kroki:
#     image: ${{ ... }}
#     ...

# And remove the KROKI_URL env var from the matrix job:
# env:
#   KROKI_URL: ${{ ... }}   ← DELETE

# The golden job (ubuntu-only) already has a correct Kroki service.
# Kroki-dependent tests in the matrix will skip on all platforms
# (KROKI_URL not set → pytest.skip), which is the intended behaviour.
```

The resulting `jobs.test` section needs no `services:` block. The Kroki integration is validated by the `golden` job which correctly runs only on `ubuntu-latest` with a hardcoded Kroki image.

### Rationale

A service block with an empty-string image name causes workflow startup failure on non-Linux runners. This would break all 8 macOS and Windows CI cells. The plan's own implementation note incorrectly claims GitHub silently skips the service. The `golden` job already provides Kroki coverage on Linux, so removing Kroki from the matrix job causes no coverage regression.

---

## P5-004 🔴 — `REQUIRED_XMP_KEYS` in `test_xmp_snapshots.py` has 2 fabricated keys and misses 2 spec-required keys

**Location:** Task 5 Step 1 (`tests/golden/test_xmp_snapshots.py`), `REQUIRED_XMP_KEYS` constant.

### Problem

```python
# Task 5 REQUIRED_XMP_KEYS (12 entries):
REQUIRED_XMP_KEYS = [
    "mdpdf:RenderId",
    "mdpdf:RenderUser",
    "mdpdf:RenderHost",
    "mdpdf:InputHash",
    "mdpdf:WatermarkLevel",
    "dc:title",
    "dc:creator",
    "dc:description",       # ← NOT in spec §5.3; not written by apply_l2_xmp
    "xmp:CreateDate",
    "xmp:ModifyDate",       # ← NOT in spec §5.3; not written by apply_l2_xmp
    "xmp:CreatorTool",
    "pdf:Producer",
]
```

The P4-004 patch established the authoritative 12 keys from spec §5.3:
`dc:creator`, `dc:title`, `pdf:Producer`, `xmp:CreatorTool`, `xmp:CreateDate`, `mdpdf:RenderId`, `mdpdf:RenderUser`, `mdpdf:RenderHost`, `mdpdf:BrandId`, `mdpdf:BrandVersion`, `mdpdf:InputHash`, `mdpdf:WatermarkLevel`.

Task 5's list:
- Adds `dc:description` — not in spec §5.3, not written by `apply_l2_xmp`.
- Adds `xmp:ModifyDate` — not in spec §5.3, not written by `apply_l2_xmp`.
- Omits `mdpdf:BrandId` — required by spec §5.3.
- Omits `mdpdf:BrandVersion` — required by spec §5.3.

`test_xmp_required_keys` would fail for every fixture because `dc:description` and `xmp:ModifyDate` will be absent from the PDF's XMP metadata.

### Patched code

```python
# Before
REQUIRED_XMP_KEYS = [
    "mdpdf:RenderId",
    "mdpdf:RenderUser",
    "mdpdf:RenderHost",
    "mdpdf:InputHash",
    "mdpdf:WatermarkLevel",
    "dc:title",
    "dc:creator",
    "dc:description",
    "xmp:CreateDate",
    "xmp:ModifyDate",
    "xmp:CreatorTool",
    "pdf:Producer",
]

# After — matches spec §5.3 exactly (same 12 keys as Plan 4 Task 4 apply_l2_xmp)
REQUIRED_XMP_KEYS = [
    "dc:creator",
    "dc:title",
    "pdf:Producer",
    "xmp:CreatorTool",
    "xmp:CreateDate",
    "mdpdf:RenderId",
    "mdpdf:RenderUser",
    "mdpdf:RenderHost",
    "mdpdf:BrandId",
    "mdpdf:BrandVersion",
    "mdpdf:InputHash",
    "mdpdf:WatermarkLevel",
]
```

### Rationale

`dc:description` and `xmp:ModifyDate` are not written by Plan 4's `apply_l2_xmp` (spec §5.3). Every `test_xmp_required_keys` assertion for those two keys will fail. `mdpdf:BrandId` and `mdpdf:BrandVersion` are spec-required and will be present, but the test never checks them. The same issue was flagged as P4-004 for Task 20 of Plan 4 — Plan 5 Task 5 repeats it for a different but related list.

---

## P5-005 🔴 — `test_uat_renders_with_brand_idimsum` hardcodes `brand_kits/idimsum/` which is deleted in Task 18

**Location:** Task 9 Step 1 (`tests/integration/test_comprehensive_uat.py`), `_BRAND_DIR` constant.

### Problem

```python
# Task 9 test_comprehensive_uat.py:
_BRAND_DIR = Path(__file__).parent.parent.parent / "brand_kits" / "idimsum"

...

def test_uat_renders_with_brand_idimsum(tmp_path: Path) -> None:
    """UAT fixture renders with the idimsum brand kit; page count ≥ 5, size > 50 KB."""
    _require_fixture()
    if not _BRAND_DIR.exists():
        pytest.skip(f"Brand kit not found: {_BRAND_DIR}")
    ...
```

Task 18 deletes `brand_kits/` from the repository. After Task 18 executes, `_BRAND_DIR` points to a deleted directory. The test does check `_BRAND_DIR.exists()` before proceeding and calls `pytest.skip` when absent — so the test will permanently **skip** (not fail) after Task 18. This means the brand-kit integration test for the UAT fixture is silently dropped from the suite at Task 18 with no replacement.

The canonical v2 brand pack is `examples/brands/idimsum/` (established in Plan 2). The test should point there.

### Patched code

```python
# Before
_BRAND_DIR = Path(__file__).parent.parent.parent / "brand_kits" / "idimsum"

# After — point to the canonical v2 brand example (examples/brands/idimsum/)
_BRAND_DIR = Path(__file__).parent.parent.parent / "examples" / "brands" / "idimsum"
```

No other changes needed — the `pytest.skip` guard remains appropriate if the example brand is absent.

### Rationale

After Task 18, `brand_kits/idimsum/` is deleted. The test using it would silently skip forever, removing the only brand-rendered UAT integration test from the suite. The canonical v2 path is `examples/brands/idimsum/`. The fix is a one-line path change.

---

## P5-006 🔴 — `doctor.py` has inline imports inside `_probe_mermaid` and `_probe_brand_registry`

**Location:** Task 12 Step 4 (`src/mdpdf/diagnostics/doctor.py`), `_probe_mermaid()` and `_probe_brand_registry()`.

### Problem

```python
# doctor.py _probe_mermaid():
def _probe_mermaid() -> dict[str, Any]:
    kroki_url = os.environ.get("KROKI_URL", "http://localhost:8000")
    kroki_available = False
    try:
        import httpx                   # ← inline import inside function body
        resp = httpx.get(f"{kroki_url}/health", timeout=2.0)
        ...

# doctor.py _probe_brand_registry():
def _probe_brand_registry() -> dict[str, Any]:
    try:
        from mdpdf.brand.registry import BrandRegistry    # ← inline import
        registry = BrandRegistry()
        ...
```

Both are inline imports inside function bodies. The pre-audit checklist (Plan 5 line 183) explicitly forbids this: "No inline imports inside method or function bodies" (lessons from P2-006, P2-007). `ruff` rule `PLC0415` (or `E401`) will flag these. `mypy --strict` will not error but `ruff check` will, causing AC-14 to fail.

Note: `httpx` is already in `[project.dependencies]` (`>=0.27`) and `mdpdf.brand.registry` is part of the package — both are safe to import at module top.

### Patched code

```python
# Before (top of doctor.py):
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import mdpdf

# After — add module-top imports:
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx
import mdpdf
from mdpdf.brand.registry import BrandRegistry

# In _probe_mermaid() — remove the inline import:
def _probe_mermaid() -> dict[str, Any]:
    kroki_url = os.environ.get("KROKI_URL", "http://localhost:8000")
    kroki_available = False
    try:
        resp = httpx.get(f"{kroki_url}/health", timeout=2.0)  # httpx imported at top
        kroki_available = resp.status_code == 200
    except Exception:
        pass
    ...

# In _probe_brand_registry() — remove the inline import:
def _probe_brand_registry() -> dict[str, Any]:
    try:
        registry = BrandRegistry()   # BrandRegistry imported at top
        brands = registry.list_brands()
        return {"count": len(brands), "brands": [b.id for b in brands]}
    except Exception as exc:
        return {"error": str(exc)}
```

### Rationale

Inline imports in `_probe_mermaid` and `_probe_brand_registry` violate the plan's own pre-audit checklist (Plan 5 line 183) and the P2-006/P2-007 lesson carried forward from Plans 2–4. `ruff check` with the default config will flag these, causing AC-14 (`ruff check src/ tests/`) to fail.

---

## P5-007 🟡 — AC-6 placeholder check reads wrong file (`manager.py` instead of `installer.py`)

**Location:** Task 22 Step 2 (`AC-6` verification block).

### Problem

```python
# Task 22 AC-6:
src = pathlib.Path('src/mdpdf/fonts/manager.py').read_text()
if 'PLACEHOLDER_SHA256_REPLACE_BEFORE_RELEASE' in src:
    print('AC-6 WARN: sha256 placeholder not yet replaced — fonts install will fail checksum')
    sys.exit(1)
```

The `PLACEHOLDER_SHA256_REPLACE_BEFORE_RELEASE` string lives in `src/mdpdf/fonts/installer.py` (Task 14 Step 4, `_KNOWN_FONTS` dict). `manager.py` is the font-manager module (font discovery and CJK registration); it contains no such placeholder. Reading `manager.py` will always produce an empty-placeholder check — the warning is never triggered, AC-6a always prints `PASS`, and the actual placeholder in `installer.py` is never verified before attempting `fonts install noto-sans-sc`.

### Patched code

```python
# Before
src = pathlib.Path('src/mdpdf/fonts/manager.py').read_text()

# After
src = pathlib.Path('src/mdpdf/fonts/installer.py').read_text()
```

### Rationale

Reading the wrong file means the placeholder guard never fires. The `fonts install noto-sans-sc` command will reach the sha256 verification step with `PLACEHOLDER_SHA256_REPLACE_BEFORE_RELEASE` as the expected hash, compare it against the real sha256 of the downloaded bytes, and raise `FontError(code="FONT_SHA256_MISMATCH")` — silently invalidating AC-6.

---

## P5-008 🟡 — `_mask_volatile()` in `test_xmp_snapshots.py` has double inline `import json`

**Location:** Task 5 Step 1 (`tests/golden/test_xmp_snapshots.py`), `_mask_volatile()` function.

### Problem

```python
def _mask_volatile(xmp_json: str) -> str:
    """Replace volatile key values with a stable placeholder for comparison."""
    import json                 # ← inline import #1

    data = json.loads(xmp_json)
    for key in VOLATILE_KEYS:
        if key in data:
            data[key] = "<masked>"
    import json as _json        # ← inline import #2 (duplicate)
    return _json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
```

Two violations: (1) both are inline imports inside a function body, violating the plan's own pre-audit checklist; (2) the same module is imported twice under two different names (`json` and `_json`) within one function. `ruff` will flag both (PLC0415 for inline imports).

`json` is already imported at module top in `tests/golden/conftest.py` and is a stdlib module that should be imported at the top of any file that uses it.

### Patched code

```python
# Add at module top of test_xmp_snapshots.py (after existing imports):
import json

# Replace _mask_volatile entirely:
def _mask_volatile(xmp_json: str) -> str:
    """Replace volatile key values with a stable placeholder for comparison."""
    data = json.loads(xmp_json)
    for key in VOLATILE_KEYS:
        if key in data:
            data[key] = "<masked>"
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
```

Also fix the two `import json` inline imports in `test_xmp_required_keys` and `test_xmp_render_user_matches` — move both to module top.

### Rationale

Double inline imports of the same module in one function is a ruff lint error. The second `import json as _json` shadows the first `import json` unnecessarily. Both should be at module top.

---

## P5-009 🟡 — `doctor_cmd` CLI function has inline imports inside command body

**Location:** Task 12 Step 5 (`src/mdpdf/cli.py`), `doctor_cmd` function.

### Problem

```python
@main.command("doctor")
@click.option("--json", "as_json", is_flag=True, help="Emit report as JSON.")
def doctor_cmd(as_json: bool) -> None:
    """Print an environment health report."""
    import json as _json                                    # ← inline import

    from mdpdf.diagnostics.doctor import run_doctor         # ← inline import

    report = run_doctor()
    ...
```

Both `json` and `mdpdf.diagnostics.doctor.run_doctor` are imported inline inside the Click command function body. This violates the P2-006/P2-007 lesson and the plan's own pre-audit checklist (line 183: "No inline imports inside method or function bodies"). `ruff` will flag PLC0415.

### Patched code

```python
# Add at module top of cli.py (alongside other imports):
import json as _json
from mdpdf.diagnostics.doctor import run_doctor

# In doctor_cmd — remove the inline imports:
@main.command("doctor")
@click.option("--json", "as_json", is_flag=True, help="Emit report as JSON.")
def doctor_cmd(as_json: bool) -> None:
    """Print an environment health report."""
    report = run_doctor()
    if as_json:
        click.echo(_json.dumps(report, indent=2))
    else:
        for section, data in report.items():
            click.echo(f"\n[{section}]")
            if isinstance(data, dict):
                for k, v in data.items():
                    click.echo(f"  {k}: {v}")
            else:
                click.echo(f"  {data}")
```

### Rationale

Inline imports inside Click command bodies are flagged by ruff and violate the rule carried forward from Plans 2–4. Since `diagnostics.doctor` is part of the package (not an optional dep), there is no reason to defer the import.

---

## P5-010 🟡 — Task 14 adds `FontError` to `errors.py`, but `FontError` already exists there

**Location:** Task 14 Step 1 (`src/mdpdf/errors.py`), proposed `FontError` addition.

### Problem

Task 14 Step 1 instructs adding a `FontError` class to `src/mdpdf/errors.py`:

```python
class FontError(MdpdfError):
    """Raised for font-related failures (download, sha256, registration).

    Attributes:
        code: Machine-readable error code.
            ``FONT_NOT_FOUND`` — requested font not in the known-font registry.
            ``FONT_DOWNLOAD_FAILED`` — network error during font download.
            ``FONT_SHA256_MISMATCH`` — downloaded bytes do not match expected sha256.
    """
```

But `FontError` **already exists** in `src/mdpdf/errors.py` (line 41):

```python
class FontError(MdpdfError):
    """Font availability / licence errors.

    Codes: FONT_NOT_INSTALLED, FONT_LICENSE_MISSING.
    """
```

Adding a second `FontError` class definition in the same file will **shadow** the first one. The existing codes (`FONT_NOT_INSTALLED`, `FONT_LICENSE_MISSING`) in the docstring will be lost. Any existing code that catches `FontError` to handle those codes would pick up the second definition — which has a different docstring and different expected codes.

### Patched code

Do NOT add a new `FontError` class. Instead, update the existing `FontError` docstring to include the new codes added by Task 14:

```python
# Before (existing errors.py line 41):
class FontError(MdpdfError):
    """Font availability / licence errors.

    Codes: FONT_NOT_INSTALLED, FONT_LICENSE_MISSING.
    """

# After — extend docstring; do NOT add a second class:
class FontError(MdpdfError):
    """Font availability / licence errors.

    Codes:
        ``FONT_NOT_INSTALLED`` — required font is not registered with ReportLab.
        ``FONT_LICENSE_MISSING`` — font file exists but licence file absent.
        ``FONT_NOT_FOUND`` — requested font not in the known-font registry.
        ``FONT_DOWNLOAD_FAILED`` — network error during font download.
        ``FONT_SHA256_MISMATCH`` — downloaded bytes do not match expected sha256.
    """
```

Remove the `FontError` class block entirely from Task 14 Step 1, keeping only the docstring update instruction.

### Rationale

Python does not raise an error on duplicate class names in the same module — the second definition silently replaces the first. Any existing `except FontError` handler would still catch both, but the docstring-advertised codes (`FONT_NOT_INSTALLED`, `FONT_LICENSE_MISSING`) would appear to have disappeared. `gen_error_docs.py` would document only the second definition.

---

## P5-011 🟡 — `test_uat_xmp_metadata_complete` in Task 9 has an inconsistent XMP key list

**Location:** Task 9 Step 1 (`tests/integration/test_comprehensive_uat.py`), `test_uat_xmp_metadata_complete`.

### Problem

```python
# Task 9 test_uat_xmp_metadata_complete:
required_keys = [
    "mdpdf:RenderId",
    "mdpdf:RenderUser",
    "mdpdf:RenderHost",
    "mdpdf:InputHash",
    "mdpdf:WatermarkLevel",
    "mdpdf:BrandId",
    "mdpdf:BrandVersion",
    "mdpdf:Template",       # ← NOT in spec §5.3
    "dc:title",
    "dc:creator",
    "xmp:CreateDate",
    "pdf:Producer",
]
```

Compared to spec §5.3 (authoritative 12 keys):

- `mdpdf:Template` is present here but is **not in spec §5.3**. It is not written by Plan 4's `apply_l2_xmp`.
- `xmp:CreatorTool` is **missing** from this list (required by spec §5.3).

The test will always fail for `mdpdf:Template` (not present in PDF) and silently not check `xmp:CreatorTool` (which may be missing).

### Patched code

```python
# Before
required_keys = [
    "mdpdf:RenderId",
    "mdpdf:RenderUser",
    "mdpdf:RenderHost",
    "mdpdf:InputHash",
    "mdpdf:WatermarkLevel",
    "mdpdf:BrandId",
    "mdpdf:BrandVersion",
    "mdpdf:Template",
    "dc:title",
    "dc:creator",
    "xmp:CreateDate",
    "pdf:Producer",
]

# After — exact spec §5.3 list (same 12 keys as P4-004 + Task 5 fix):
required_keys = [
    "dc:creator",
    "dc:title",
    "pdf:Producer",
    "xmp:CreatorTool",
    "xmp:CreateDate",
    "mdpdf:RenderId",
    "mdpdf:RenderUser",
    "mdpdf:RenderHost",
    "mdpdf:BrandId",
    "mdpdf:BrandVersion",
    "mdpdf:InputHash",
    "mdpdf:WatermarkLevel",
]
```

### Rationale

`mdpdf:Template` is not a field defined in spec §5.3 and is not written by `apply_l2_xmp`. The test assertion for it will always fail. `xmp:CreatorTool` IS spec-required and is silently not tested. This is the third variation of the same issue (P4-004, P5-004, P5-011 all caught XMP key list drift in different tasks).

---

## P5-012 🟢 — Task 15 test assertion comment is misleading about stderr vs stdout routing

**Location:** Task 15 Step 1 (`tests/unit/test_cli.py`), `test_render_legacy_brand_emits_deprecation_stderr`.

### Problem

```python
def test_render_legacy_brand_emits_deprecation_stderr(tmp_path: Path) -> None:
    """md-to-pdf render --legacy-brand emits a deprecation message on stderr."""
    ...
    runner = CliRunner()
    result = runner.invoke(...)
    # The command may succeed or fail depending on whether brand_kits/ exists,
    # but it must emit a deprecation notice somewhere in the combined output.
    assert "deprecated" in result.output.lower() or "legacy-brand" in result.output.lower(), (
        f"Expected deprecation message in output:\n{result.output}"
    )
```

The assertion checks `result.output`. The deprecation notice is emitted via `click.echo(..., err=True)` (Task 15 Step 4), which writes to stderr. In Click's default `CliRunner` configuration (no `mix_stderr` argument, Click 8.3+ default), stderr is mixed into `result.output`. So the assertion accidentally works. However, the docstring says "emits a deprecation message on stderr" and the assertion checks `result.output` — the comment `"somewhere in the combined output"` makes the mismatch obvious but leaves the reader confused.

This is not a test failure risk but a readability issue: the assertion's intent and mechanism are misaligned.

### Patched code

```python
# Before
assert "deprecated" in result.output.lower() or "legacy-brand" in result.output.lower(), (
    f"Expected deprecation message in output:\n{result.output}"
)

# After — clarify that in Click 8.3+ CliRunner, stderr is merged into result.output:
# In Click 8.3+ CliRunner default mode, stderr is merged into result.output.
# click.echo(..., err=True) output is therefore found in result.output.
assert "deprecated" in result.output.lower(), (
    f"Expected 'deprecated' in merged output (Click 8.3+ merges stderr into output):\n{result.output}"
)
```

### Rationale

The working assertion relies on Click 8.3+ stderr-merging behaviour that is not documented at the assertion site. Removing the `or "legacy-brand"` branch makes the assertion narrower and more meaningful (the exact word "deprecated" should appear). The comment clarifies the stderr-merge mechanism so future readers understand why `result.output` catches `err=True` output.

---

## Apply Order & Independence

P5-001 and P5-002 are the most impactful and should be applied before any task executes. P5-003 blocks the CI matrix expansion (Task 11). P5-004 and P5-011 must be applied before golden tests are run. P5-005 should be applied before Task 9 is committed. P5-006 and P5-009 should be applied before Task 12 is committed. P5-007 is needed before Task 22 AC-6 verification. P5-008 and P5-010 are independent cleanups. Suggested order:

1. **P5-001** — Fix `gen_error_docs.py` base-class name `MdPdfError` → `MdpdfError`; fix code-extraction to use class names.
2. **P5-002** — Replace `message=` with `user_message=` in all four `raise FontError(...)` sites in `installer.py`.
3. **P5-003** — Remove `services:` block from `jobs.test` in `ci.yml`; rely on `golden` job for Kroki coverage.
4. **P5-004** — Fix `REQUIRED_XMP_KEYS` in `test_xmp_snapshots.py` to match spec §5.3 exactly.
5. **P5-005** — Change `_BRAND_DIR` in `test_comprehensive_uat.py` from `brand_kits/idimsum` to `examples/brands/idimsum`.
6. **P5-006** — Move inline `httpx` and `BrandRegistry` imports to module top in `doctor.py`.
7. **P5-007** — Fix AC-6 placeholder check: read `installer.py` not `manager.py`.
8. **P5-008** — Move `import json` to module top; remove double import in `_mask_volatile`.
9. **P5-009** — Move `import json as _json` and `from mdpdf.diagnostics.doctor import run_doctor` to module top of `cli.py`.
10. **P5-010** — Do NOT add a second `FontError` class in Task 14 Step 1; update existing class docstring only.
11. **P5-011** — Fix `test_uat_xmp_metadata_complete` key list: remove `mdpdf:Template`, add `xmp:CreatorTool`.
12. **P5-012** — Tighten deprecation assertion; add comment about Click 8.3+ stderr-merge.

Recommended commit messages:

```
fix(docs): fix gen_error_docs.py base class name MdPdfError → MdpdfError; use class.__name__ for codes (P5-001)
fix(fonts): FontError raises use user_message= not message= (P5-002)
fix(ci): remove conditional Kroki service from matrix job to prevent empty-image crash on macOS/Windows (P5-003)
fix(golden): align REQUIRED_XMP_KEYS with spec §5.3 — remove dc:description/xmp:ModifyDate, add BrandId/BrandVersion (P5-004)
fix(integration): point _BRAND_DIR to examples/brands/idimsum (not deleted brand_kits/) (P5-005)
fix(doctor): move inline imports (httpx, BrandRegistry) to module top (P5-006)
fix(test): AC-6 placeholder check reads installer.py not manager.py (P5-007)
fix(golden): move import json to module top; remove double import in _mask_volatile (P5-008)
fix(cli): move doctor_cmd imports (json, run_doctor) to module top (P5-009)
fix(errors): do not duplicate FontError class in Task 14; update existing docstring only (P5-010)
fix(integration): align test_uat_xmp_metadata_complete keys with spec §5.3 (P5-011)
fix(test): clarify deprecation assertion — assert 'deprecated', add Click 8.3+ stderr-merge comment (P5-012)
```

## Patch Acceptance Bar

After all 12 patches applied:

- `scripts/gen_error_docs.py --out-dir /tmp/errdocs` produces ≥ 6 `.md` files (one per `MdpdfError` subclass) without printing `WARNING: No MdPdfError subclasses found`.
- Every `raise FontError(...)` in `installer.py` uses `user_message=` and can be constructed without `TypeError`.
- `.github/workflows/ci.yml` `jobs.test` section has no `services:` block; macOS and Windows cells start without Docker service errors.
- `REQUIRED_XMP_KEYS` in `test_xmp_snapshots.py` matches spec §5.3 exactly: `dc:creator`, `dc:title`, `pdf:Producer`, `xmp:CreatorTool`, `xmp:CreateDate`, `mdpdf:RenderId`, `mdpdf:RenderUser`, `mdpdf:RenderHost`, `mdpdf:BrandId`, `mdpdf:BrandVersion`, `mdpdf:InputHash`, `mdpdf:WatermarkLevel`.
- `_BRAND_DIR` in `test_comprehensive_uat.py` points to `examples/brands/idimsum/`; the test does not permanently skip after Task 18.
- `doctor.py` has `import httpx` and `from mdpdf.brand.registry import BrandRegistry` at module top; no inline imports in `_probe_mermaid` or `_probe_brand_registry`.
- `ruff check src/ tests/` passes clean (no PLC0415 inline-import findings in `doctor.py`, `cli.py`, or `test_xmp_snapshots.py`).
- AC-6 verification reads `src/mdpdf/fonts/installer.py` for the placeholder string.
- `src/mdpdf/errors.py` contains exactly one `FontError` class definition.
- `test_uat_xmp_metadata_complete` `required_keys` list does not include `mdpdf:Template`; includes `xmp:CreatorTool`.
- All Plan 1 + Plan 2 + Plan 3 + Plan 4 acceptance criteria still hold (no regressions).

---

## Tasks Reviewed and Found Sound (no patch needed)

The following tasks were inspected and have no issues warranting a patch:

- **Task 1 (UAT fixture):** Sound. The 11-scenario fixture covers all spec §7.2.1 categories. The integration test in Task 1 uses `CliRunner()` without `mix_stderr=`, `subprocess.run(...).stderr` access pattern is not used here (CLI runner is used instead). `pypdf.PdfReader(str(out_pdf)).pages` API is correct.
- **Task 2 (Image assets):** Sound. `PIL.ImageDraw.Draw.rectangle` + `.text` + `.ellipse` API is correct for Pillow. The SVG uses `<defs>/<marker>` correctly. The `architecture-large.png` at 2400×1800 correctly targets the auto-downsample threshold.
- **Task 3 (Golden harness conftest):** Sound. `pdfplumber.open(str(pdf_path))` as context manager is correct API. `page.extract_words()` returning a list is correct. `pypdf.PdfReader(str(pdf_path))` and `.pages[i].extract_text()` are correct. `pikepdf.open(pdf_path)` with `pdf.open_metadata()` as context manager is correct. `yaml.dump(...)` + `dataclasses.asdict(document)` for AST serialisation is correct. `--update-golden` via `pytest_addoption` + `parser.addoption` is the correct pytest hook pattern.
- **Task 4 (L1 AST snapshots):** Sound. `from tests.golden.conftest import ...` is correct import style for a test file importing from its own package's conftest. `pytest.skip(...)` in the test body for missing fixture files is correct. The three parameterised tests (snapshot, valid-document, deterministic) are well-separated.
- **Task 6 (L3 text-layer snapshots):** Sound. `pypdf` text extraction + form-feed page separator + whitespace normalisation is correct. The render-id strip regex `[0-9a-f]{8}-...-[0-9a-f]{12}` correctly matches UUIDv4 formatted render IDs. The `branch_ops` fixture name mapping is handled correctly.
- **Task 7 (L4 layout fingerprints):** Sound. `pdfplumber.open` + `page.extract_words()` + rounding `w["x0"]`/`w["top"]`/`w["x1"]`/`w["bottom"]` to 0.1 pt is the correct pdfplumber bbox field access pattern. The `pytestmark` module-level skip for missing pdfplumber is correct. The meta-test verifies harness sensitivity without a committed golden.
- **Task 8 (L5 deterministic sha256):** Sound. `_render_deterministic` uses `subprocess.run` + `capture_output=True, text=True` and accesses `.returncode`, `.stderr` (not `.output`). The `__PLACEHOLDER__` skip pattern is correct. `request.config.getoption("--update-golden", default=False)` is the correct way to access a custom pytest option from inside a test.
- **Task 10 (pyproject.toml v2.0.0 bump):** Sound. The dependency list is complete and correctly separates runtime from dev/test deps. `pdfplumber>=0.11` is correctly placed in `[dev]` not `[project.dependencies]`. The version bump from `2.0.0a1` to `2.0.0` is the correct release action.
- **Task 13 (`fonts list`):** Sound. `reportlab.pdfbase.pdfmetrics.getRegisteredFontNames()` is the correct ReportLab API. `list[dict[str, str]]` annotation is used (not bare `list`/`dict`). `json` is imported via `import json as _json` at module top (Task 13 Step 3 adds it, which is correct).
- **Task 14 (fonts install — tests and installer logic):** Sound except for P5-002 and P5-010. `httpx.get(..., follow_redirects=True)` + `response.raise_for_status()` + `response.content` is correct httpx API. Atomic write via `tmp_path.write_bytes(content)` + `os.replace(tmp_path, dest_path)` matches project convention. The mock pattern `patch("mdpdf.fonts.installer.httpx")` correctly patches the module-level `httpx` reference.
- **Task 15 (`--legacy-brand` deprecation):** Sound except for P5-012. The module-level `warnings.warn(..., DeprecationWarning, stacklevel=2)` pattern in `legacy.py` is correct. `pytest.warns(DeprecationWarning)` context manager is the right way to assert warning emission. Adding `@pytest.mark.filterwarnings("ignore::DeprecationWarning")` to existing tests is correct.
- **Task 16 (delete monolith — gate):** Sound. `@pytest.mark.xfail(not GOLDEN_SUITE_VERIFIED, strict=True)` is the correct pytest pattern for a gated pre-flight test. `GOLDEN_SUITE_VERIFIED: bool = False` as a module-level flag that the executor manually flips is a reasonable friction mechanism.
- **Task 17 (delete legacy tests):** Sound. The test `test_no_legacy_test_md_to_pdf_files` correctly uses `tests_root.glob("test_md_to_pdf_*.py")` from the `tests/` root. The `pyproject.toml` `testpaths` update adding `tests/golden` is correct.
- **Task 18 (delete `brand_kits/`):** Sound structurally (except the cross-reference issue caught by P5-005 which is in Task 9). Task 18 correctly identifies `tests/integration/test_brand_integration.py` as needing update and provides both option A (delete) and option B (migrate to `tmp_path` fixture).
- **Task 19 (mkdocs scaffold):** Sound except for the `gen_error_docs.py` issues caught by P5-001. The `mkdocs.yml` `docs_dir: .` + `site_dir: ../site` configuration is valid when `mkdocs build --config-file docs/mkdocs.yml` is invoked from the repo root. The nav entries all point to files created in the same task. `mkdocstrings[python]` plugin configuration with `paths: ["../src"]` is correct.
- **Task 20 (docs.yml):** Sound. `permissions: contents: read; pages: write; id-token: write` is the correct permission set for `actions/deploy-pages`. `concurrency.cancel-in-progress: false` prevents partial deploys. `actions/configure-pages@v5`, `actions/upload-pages-artifact@v3`, `actions/deploy-pages@v4` are the current stable versions of the Pages deployment action chain.
- **Task 21 (release.yml + CHANGELOG):** Sound. `release: types: [published]` trigger is the correct event for a manually-triggered release. `sigstore sign dist/*.whl dist/*.tar.gz` is the correct sigstore v3 CLI invocation (installed as a console script, not `python -m sigstore`). `gh release upload "${{ github.ref_name }}" dist/* --clobber` is the correct `gh` CLI syntax. The `vars.PYPI_TARGET` repository variable gate is a sound safety mechanism.
- **Task 22 (acceptance verification):** Sound except for P5-007 (AC-6 file path). All 18 ACs map correctly to the tasks that implement them. The shell `EC=$?` pattern for capturing subprocess exit codes works in bash. `pypdf.PdfReader.outline` access is the correct API for reading PDF bookmarks.

---

## Summary

**Total: 12 patches — 6 Critical, 5 Important, 1 Polish.**

**Top 3 by severity:**

1. **P5-001 🔴 Task 19** — `gen_error_docs.py` looks up `MdPdfError` by name, but the actual base class is `MdpdfError`. `getattr(_errors_module, "MdPdfError", None)` returns `None`; the function exits immediately returning `[]`; zero `.md` files are generated; `test_gen_error_docs_produces_files` fails. Additionally, even with the name fixed, the code uses `getattr(cls, "code", "")` on class objects that have no class-level `code` attribute (it is an instance attribute), so every subclass produces an empty code and is skipped — still zero pages. Two independent bugs in one function.

2. **P5-002 🔴 Task 14** — All four `raise FontError(...)` call sites in `installer.py` use `message=` as the keyword argument, but `MdpdfError.__init__` takes `user_message=`. Every attempt to raise a `FontError` (on unknown font, network failure, sha256 mismatch, or OS write failure) will itself raise `TypeError: MdpdfError.__init__() got an unexpected keyword argument 'message'` before the `FontError` can be constructed. All five `test_installer.py` tests that exercise error paths will error rather than pass.

3. **P5-003 🔴 Task 11** — The `services.kroki.image` expression evaluating to an empty string on macOS/Windows runners does not cause GitHub Actions to silently skip the service — it causes the workflow to error at startup with `Error: No such image: ''`. All 8 macOS and Windows CI cells (Python 3.10/3.11/3.12/3.13 × 2 OS) will fail before any test runs, defeating the 12-cell matrix expansion that is an explicit v2.0.0 acceptance criterion (AC-4).
