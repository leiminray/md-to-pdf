# Plan 2 (AST transformers + brand v2) — Review Patches

**Date:** 2026-04-26
**Patches against:** [`2026-04-26-md-to-pdf-v2.0-plan-2-ast-transformers-and-brand.md`](2026-04-26-md-to-pdf-v2.0-plan-2-ast-transformers-and-brand.md)
**Reviewer:** sophie.leiyixiao@gmail.com (cold review by independent subagent; Tasks 1-14 committed, Tasks 15-22 not yet executed)
**Apply how:** patches are independent. Apply all, a subset, or skip — each carries its own rationale. Plan 2 source file is **not modified** by this document.

---

## Severity Legend

| Tag | Meaning |
|---|---|
| 🔴 Critical | Will cause test/runtime failure during execution |
| 🟡 Important | Spec drift, pre-cooked lint/type error, or chronological ordering bug — fix before executing |
| 🟢 Polish | Style / dead code / minor inconsistency |

## Patch Summary

| ID | Severity | Task | Topic |
|---|---|---|---|
| P2-001 | 🔴 | 18 | `CliRunner(mix_stderr=False)` — Click 8.3 removed this constructor argument |
| P2-002 | 🔴 | 18 | `_exit_with_error` uses `sys.exit()` — wrong exit mechanism for Click brand subcommands; unreachable `return` after each call |
| P2-003 | 🔴 | 20 | `apply_overrides(payload, ...)` return value discarded — currently safe (in-place mutation) but fragile to future refactor |
| P2-004 | 🟡 | 12 | `locales: dict[str, dict]` — mypy --strict rejects bare inner `dict` |
| P2-005 | 🟡 | 5, 6 | `out: list = []` and `toc_block: list = [...]` — mypy --strict rejects bare `list` annotation in src/ |
| P2-006 | 🟡 | 20 | Inline `from pathlib import Path as _Path` inside `Pipeline.render()` — `Path` already at module top |
| P2-007 | 🟡 | 20 | Inline `from mdpdf.brand.safe_paths import safe_join` inside `Pipeline.render()` — breaks module-top-imports convention |
| P2-008 | 🟡 | Acceptance / 21 | Criterion 5 says `--brand idimsum` (registry path); Task 21 integration test uses `--brand-pack-dir` (explicit path) — registry path never exercised |
| P2-009 | 🟡 | 21 | `import json` and `import pytest` unused in `test_brand_integration.py` — ruff F401 |
| P2-010 | 🟢 | 20 | `_resolve_brand` dead parameter `render_id: str` is never used in body |
| P2-011 | 🟢 | 18 | `_exit_with_error` defined at end of brand-commands block; inconsistent with `_exit_code_for` near module top |
| P2-012 | 🟢 | 18 | `brand_show` `model_dump()` should use `mode="json"` — defensive against future `Path` field additions |

---

## P2-001 🔴 — `CliRunner(mix_stderr=False)` — Click 8.3 removed this argument

**Location:** Task 18 Step 1 (`tests/unit/test_cli.py`), test `test_brand_validate_legacy_with_flag`.

### Problem

```python
runner = CliRunner(mix_stderr=False)
result = runner.invoke(main, ["brand", "validate", str(bk), "--legacy-brand"])
assert result.exit_code == 0
assert "deprecated" in result.stderr.lower() or "legacy" in result.stderr.lower()
```

Plan 2's "Patches from Plan 1 review" section explicitly notes that **P1-002 taught the project that Click 8.3 dropped `mix_stderr` from `CliRunner`** (Plan 1 commit `fe0e766 fix(cli-test): drop mix_stderr arg removed in Click 8.3 (follow-up to P1-002)`). Despite this documented lesson, Task 18 reintroduces the same pattern. On Click 8.3+, `CliRunner.__init__()` raises `TypeError: CliRunner.__init__() got an unexpected keyword argument 'mix_stderr'` before any assertion runs.

### Patched code

```python
# Before
runner = CliRunner(mix_stderr=False)
result = runner.invoke(main, ["brand", "validate", str(bk), "--legacy-brand"])
assert result.exit_code == 0
assert "deprecated" in result.stderr.lower() or "legacy" in result.stderr.lower()

# After
runner = CliRunner()
result = runner.invoke(main, ["brand", "validate", str(bk), "--legacy-brand"])
assert result.exit_code == 0
# In Click 8.3+ default mode, stderr is merged into result.output.
assert "deprecated" in result.output.lower() or "legacy" in result.output.lower()
```

### Rationale

Identical fix to P1-002. Click 8.3 made the merged-stderr behaviour permanent. The deprecation message written via `click.echo(deprecation, err=True)` is captured in `result.output` when stderr is mixed (the default).

---

## P2-002 🔴 — `_exit_with_error` uses `sys.exit()`; unreachable `return` after each call

**Location:** Task 18 Step 3 (`src/mdpdf/cli.py`), new helper `_exit_with_error` plus call sites in `brand_show`, `brand_validate`, `brand_migrate`.

### Problem

```python
def _exit_with_error(e: MdpdfError) -> None:
    import sys
    for cls, code in _EXIT_BY_CODE.items():
        if isinstance(e, cls):
            sys.exit(code)
    sys.exit(1)
```

And each command call site:

```python
    except MdpdfError as e:
        click.echo(f"{e.code}: {e.user_message}", err=True)
        _exit_with_error(e)
        return                           # ← unreachable: _exit_with_error always raises SystemExit
```

Issues:

1. **Unreachable `return`** after `_exit_with_error()` will be flagged by `mypy --strict --warn-unreachable`.
2. The existing `render_cmd` in Plan 1's CLI uses `ctx.exit(_exit_code_for(e))` — Click's context-aware exit. Introducing a parallel mechanism (`sys.exit`-based) creates two ways to do the same thing and obscures the project pattern.
3. The linear `isinstance` scan over `_EXIT_BY_CODE.items()` does not respect MRO; the existing `_exit_code_for` helper (which uses `for cls in type(e).__mro__:`) is correct for subclasses (e.g., a future `MermaidBrandError(BrandError)` hits the wrong dict entry).

### Patched code

Replace the new `_exit_with_error` helper entirely and use `raise SystemExit(_exit_code_for(e))` at each call site:

```python
# Remove _exit_with_error entirely.

# In each brand command, replace:
#     click.echo(f"{e.code}: {e.user_message}", err=True)
#     _exit_with_error(e)
#     return
# With:
#     click.echo(f"{e.code}: {e.user_message}", err=True)
#     raise SystemExit(_exit_code_for(e))
```

Example for `brand_validate`:

```python
@brand.command(name="validate")
@click.argument("brand_path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--legacy-brand", is_flag=True, default=False, help="Accept v1 brand_kits/-style layout.")
def brand_validate(brand_path: Path, legacy_brand: bool) -> None:
    """Validate a brand pack against the v2 schema."""
    from mdpdf.brand.legacy import load_legacy_brand_pack
    from mdpdf.brand.schema import load_brand_pack
    try:
        if legacy_brand:
            bp, deprecation = load_legacy_brand_pack(brand_path)
            click.echo(deprecation, err=True)
        else:
            bp = load_brand_pack(brand_path)
    except MdpdfError as e:
        click.echo(f"{e.code}: {e.user_message}", err=True)
        raise SystemExit(_exit_code_for(e))
    click.echo(f"valid: brand '{bp.id}' v{bp.version} (schema {bp.schema_version})")
```

Apply the same pattern to `brand_show` and `brand_migrate`.

### Rationale

`raise SystemExit(N)` is equivalent to `sys.exit(N)` inside `CliRunner.invoke()` (both are caught and set `result.exit_code`), but `raise` makes the control flow explicit to mypy and removes the unreachable `return` dead code. Reusing `_exit_code_for` ensures subclass error codes are mapped correctly.

---

## P2-003 🔴 — `apply_overrides(payload, ...)` return value discarded

**Location:** Task 20 Step 4 (`src/mdpdf/pipeline.py`, `Pipeline.render()` validate phase).

### Problem

```python
if request.brand_overrides and brand_pack is not None:
    payload = brand_pack.model_dump()
    apply_overrides(payload, request.brand_overrides)   # ← return value discarded
    brand_pack = BrandPack(**payload)
```

`apply_overrides` (Task 14) signature is `(payload, overrides) -> dict[str, Any]`. It mutates `payload` in-place via `_set_dotted`, AND returns the mutated dict. Discarding the return is currently safe because of the in-place mutation, but:

1. Future refactor that makes `apply_overrides` non-mutating (returns new dict) silently breaks this code path.
2. Mypy --strict (with default config) does not flag discarded return values, but `pyright` does. Project uses both (per Plan 1 dev tooling).
3. Pattern violates "if a function returns a value, capture it" — the same convention applied throughout `cli.py` and `pipeline.py`.

### Patched code

```python
# Before
if request.brand_overrides and brand_pack is not None:
    payload = brand_pack.model_dump()
    apply_overrides(payload, request.brand_overrides)
    brand_pack = BrandPack(**payload)

# After
if request.brand_overrides and brand_pack is not None:
    payload = brand_pack.model_dump()
    payload = apply_overrides(payload, request.brand_overrides)
    brand_pack = BrandPack(**payload)
```

### Rationale

One-character fix. Captures the return value, makes the code robust against future `apply_overrides` refactors, and matches project convention.

---

## P2-004 🟡 — `locales: dict[str, dict]` fails mypy --strict

**Location:** Task 12 Step 3 (`src/mdpdf/brand/schema.py`, `BrandPack` model + `load_brand_pack` body).

### Problem

```python
locales: dict[str, dict] = Field(default_factory=dict)
# ...
locales: dict[str, dict] = {}
```

mypy --strict requires fully parameterized generics. Bare `dict` is `dict[Any, Any]`; mypy flags `error: Missing type parameters for generic type "dict"`. Tasks 1-14 each had to patch similar issues during execution (see Tasks 4, 10, 12 deviation notes from prior subagent reports).

### Patched code

```python
# In BrandPack model:
locales: dict[str, dict[str, Any]] = Field(default_factory=dict)

# In load_brand_pack body:
locales: dict[str, dict[str, Any]] = {}
```

`Any` is already imported in `schema.py` (used by other fields).

### Rationale

Every other `dict` annotation in `schema.py` uses `dict[str, Any]` for YAML payloads. The `locales` field holds raw YAML dicts — same shape.

---

## P2-005 🟡 — Bare `list` annotations in `filter_metadata_blocks` and `promote_toc`

**Location:** Task 5 Step 3 (`src/mdpdf/markdown/transformers/filter_metadata_blocks.py`); Task 6 Step 3 (`src/mdpdf/markdown/transformers/promote_toc.py`).

### Problem

`filter_metadata_blocks.py`:
```python
out: list = []
```

`promote_toc.py`:
```python
toc_block: list = [children[toc_idx]]
```

mypy --strict flags `error: Need type annotation for "out" (hint: "out: list[<type>] = ...")`. The previous subagent that executed Task 5 manually added typing (`out: list[Block]`), but the Plan 2 document still has the un-annotated version, so a future re-execution from scratch would re-introduce the issue.

### Patched code

`filter_metadata_blocks.py`:
```python
# Before
out: list = []
# After
out: list[Block] = []
```

`promote_toc.py`:
```python
# Before
toc_block: list = [children[toc_idx]]
# After
toc_block: list[Block] = [children[toc_idx]]
```

(Both files already import `Block` per the executed code; Plan 2 source needs the import added near the top.)

### Rationale

Establishes the typed-list convention in the plan source so future re-execution (or new Plan-2-style transformer plans) doesn't have to re-discover the lesson.

---

## P2-006 🟡 — Redundant `from pathlib import Path as _Path` inside `Pipeline.render()`

**Location:** Task 20 Step 4 (`src/mdpdf/pipeline.py`, `Pipeline.render()` body).

### Problem

```python
        # Build styles + register fonts
        styles = build_brand_styles(brand_pack) if brand_pack else None
        from pathlib import Path as _Path                    # ← inline import
        bundled_fonts = _Path(__file__).resolve().parents[2] / "fonts"
```

`Path` is already imported at the top of `pipeline.py` (Plan 1 code). The inline alias `_Path` is unnecessary and creates either a redundant binding or shadowing depending on ruff version. Ruff `E401` flags inline stdlib imports in some configurations.

### Patched code

```python
# Before
from pathlib import Path as _Path
bundled_fonts = _Path(__file__).resolve().parents[2] / "fonts"

# After
bundled_fonts = Path(__file__).resolve().parents[2] / "fonts"
```

### Rationale

One-line fix. Zero behavior change. Matches project convention that all imports live at module top.

---

## P2-007 🟡 — Inline `from mdpdf.brand.safe_paths import safe_join` inside `Pipeline.render()`

**Location:** Task 20 Step 4 (`src/mdpdf/pipeline.py`, `Pipeline.render()` body).

### Problem

```python
        if brand_pack and brand_pack.theme.assets.fonts_dir:
            from mdpdf.brand.safe_paths import safe_join    # ← inline import
            try:
                brand_fonts_dir = safe_join(brand_pack.pack_root, brand_pack.theme.assets.fonts_dir)
            except Exception:  # noqa: BLE001
                brand_fonts_dir = None
```

Same issue as P2-006. `safe_join` is a pure utility in the same package; no import-cycle reason for the inline placement. Project convention is module-top imports.

### Patched code

Move the import to the top of `pipeline.py`, alongside the other `mdpdf.brand.*` imports introduced in Task 20:

```python
# At module top alongside other brand imports:
from mdpdf.brand.safe_paths import safe_join

# In render() — remove the inline import line, keep the rest unchanged:
        if brand_pack and brand_pack.theme.assets.fonts_dir:
            try:
                brand_fonts_dir = safe_join(brand_pack.pack_root, brand_pack.theme.assets.fonts_dir)
            except Exception:  # noqa: BLE001
                brand_fonts_dir = None
```

### Rationale

Two-line change. Consistent with the project-wide style enforced since Task 1.

---

## P2-008 🟡 — Acceptance criterion 5 specifies `--brand idimsum` but Task 21 test uses `--brand-pack-dir`

**Location:** Plan 2 §"Acceptance criteria for Plan 2" criterion 5 (line ~71); Task 21 Step 3 (`tests/integration/test_brand_integration.py`, `test_branded_hello_renders`).

### Problem

Acceptance criterion 5 reads:
> `md-to-pdf tests/integration/fixtures/hello.md -o /tmp/hello-branded.pdf --brand idimsum` produces a PDF…

The integration test exercises `--brand-pack-dir` instead:
```python
proc = subprocess.run(
    ["md-to-pdf", str(HELLO), "-o", str(out),
     "--brand-pack-dir", str(IDIMSUM)],   # ← explicit path, not --brand idimsum
    ...
)
```

These exercise different code paths:
- `--brand idimsum` → `BrandRegistry.resolve_brand()` with builtin layer
- `--brand-pack-dir <path>` → `load_brand_pack(explicit_path)` directly

The builtin registry path is never exercised by any integration test, leaving the highest-priority acceptance criterion unverified.

Similarly, criterion 9 reads `md-to-pdf brand-config /tmp/inline-brand.yaml` — missing the input file argument and the `--brand-config` flag (positional `brand-config` is not a valid subcommand).

### Patched code

Add a registry-path test in `test_brand_integration.py`:

```python
def test_brand_id_resolves_via_builtin_registry(tmp_path: Path):
    """Acceptance criterion 5: --brand idimsum resolves via builtin examples/brands/."""
    out = tmp_path / "by-id.pdf"
    proc = subprocess.run(
        ["md-to-pdf", str(HELLO), "-o", str(out), "--brand", "idimsum"],
        capture_output=True, text=True, check=False, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
```

Fix criterion 9 text to read:
> `md-to-pdf tests/integration/fixtures/hello.md -o /tmp/h-inline.pdf --brand-config /tmp/inline-brand.yaml` renders successfully with an inline brand.

### Rationale

Acceptance criteria are contractual verification targets. Criterion 5 exercises the registry resolution code that is the primary feature of Task 11. If that code path is broken, the test suite won't catch it.

---

## P2-009 🟡 — Unused imports in `test_brand_integration.py`

**Location:** Task 21 Step 3 (`tests/integration/test_brand_integration.py`).

### Problem

```python
import json       # ← never used
import subprocess
from pathlib import Path

import pytest     # ← never used
from pypdf import PdfReader
```

Ruff F401: "json" and "pytest" imported but unused. The Task 22 acceptance sweep runs `ruff check src/ tests/` — this will fail.

### Patched code

```python
# After
import subprocess
from pathlib import Path

from pypdf import PdfReader
```

### Rationale

Two-line deletion. Same pattern as every prior plan task that needed F401 fixes at execution time.

---

## P2-010 🟢 — `_resolve_brand` dead parameter `render_id`

**Location:** Task 20 Step 4 (`src/mdpdf/pipeline.py`, `Pipeline._resolve_brand`).

### Problem

```python
def _resolve_brand(self, request: "RenderRequest", render_id: str) -> "BrandPack | None":
    if request.brand_config:
        return load_inline_brand(request.brand_config)
    if request.brand_pack_dir:
        if request.legacy_brand:
            bp, dep = load_legacy_brand_pack(request.brand_pack_dir)
            _log.warning("brand.legacy_loaded", deprecation=dep)
            return bp
        return load_brand_pack(request.brand_pack_dir)
    if request.brand:
        return resolve_brand(BrandRegistry(brand_id=request.brand))
    return None
```

`render_id` is accepted but never read inside the function body. It was likely intended to be passed to error constructors for traceability (matching `FontError(render_id=render_id)` from P1-003), but no errors raised inside `_resolve_brand` use it.

### Patched code

**Option A (preferred — adds traceability):** thread `render_id` into BrandError raises that come up from `load_brand_pack`/`load_inline_brand`/`load_legacy_brand_pack` chain by wrapping calls:

```python
def _resolve_brand(self, request: "RenderRequest", render_id: str) -> "BrandPack | None":
    try:
        if request.brand_config:
            return load_inline_brand(request.brand_config)
        if request.brand_pack_dir:
            if request.legacy_brand:
                bp, dep = load_legacy_brand_pack(request.brand_pack_dir)
                _log.warning("brand.legacy_loaded", deprecation=dep)
                return bp
            return load_brand_pack(request.brand_pack_dir)
        if request.brand:
            return resolve_brand(BrandRegistry(brand_id=request.brand))
    except BrandError as e:
        if e.render_id is None:
            e.render_id = render_id
        raise
    return None
```

**Option B (simpler — drops the parameter):**

```python
def _resolve_brand(self, request: "RenderRequest") -> "BrandPack | None":
    ...

# Update call site in render():
brand_pack = self._resolve_brand(request)
```

### Rationale

Option A preferred — `render_id` in errors helps debugging when brand resolution fails inside a specific render job. Either fix removes the dead parameter.

---

## P2-011 🟢 — `_exit_with_error` placement inconsistent with `_exit_code_for`

**Location:** Task 18 Step 3 (`src/mdpdf/cli.py`).

### Problem

The plan appends `_exit_with_error` at the bottom of the brand-commands block. The existing helper `_exit_code_for` is defined near the module top. Two exit-code helpers in the same file at different positions reduce navigability.

### Patched code

If P2-002 is applied, `_exit_with_error` is removed entirely — this issue resolves automatically.

If `_exit_with_error` must remain (e.g., P2-002 declined): move its definition to sit adjacent to `_exit_code_for`, immediately after the `_EXIT_BY_CODE` dict.

### Rationale

Module-level helpers grouped by purpose reduce reading friction.

---

## P2-012 🟢 — `brand_show` should use `model_dump(mode="json")` for future-proof YAML serialization

**Location:** Task 18 Step 3 (`src/mdpdf/cli.py`, `brand_show` command).

### Problem

```python
click.echo(yaml.safe_dump(bp.model_dump(exclude={"pack_root"}), sort_keys=False, allow_unicode=True))
```

Current Plan 2 schema is safe — only `pack_root: Path` exists, and it's excluded. But pydantic v2's default `model_dump()` returns Python objects as-is. A future schema addition (e.g., `resolved_logo_path: Path`) would silently leak `Path` objects, causing `yaml.safe_dump` to raise `RepresenterError: cannot represent an object: PosixPath(...)`.

### Patched code

```python
# Before
click.echo(yaml.safe_dump(bp.model_dump(exclude={"pack_root"}), sort_keys=False, allow_unicode=True))

# After
click.echo(yaml.safe_dump(bp.model_dump(exclude={"pack_root"}, mode="json"), sort_keys=False, allow_unicode=True))
```

### Rationale

Defensive one-word addition. `mode="json"` serializes all values to JSON-compatible types (Path → str, datetime → ISO string, etc.), making `yaml.safe_dump` robust to future schema growth.

---

## Apply Order & Independence

All 12 patches are independent (P2-002 supersedes P2-011 if applied; otherwise they coexist). Suggested order if applying as separate commits:

1. **P2-001** (CliRunner mix_stderr) — touches `test_cli.py` only.
2. **P2-002** (exit mechanism) — touches `cli.py`; supersedes P2-011.
3. **P2-003** (apply_overrides return value) — touches `pipeline.py` only.
4. **P2-004** (locales dict type) — touches `schema.py` only.
5. **P2-005** (bare list annotations) — touches `filter_metadata_blocks.py` and `promote_toc.py`.
6. **P2-006 + P2-007** (inline imports) — both touch `pipeline.py`; apply together.
7. **P2-008** (criterion 5 / integration test + criterion 9 text) — touches `test_brand_integration.py` + plan document.
8. **P2-009** (unused imports) — touches `test_brand_integration.py`.
9. **P2-010 → P2-012** (polish) — minimal, no inter-dependencies.

Recommended commit messages:

```
fix(cli-test): drop CliRunner(mix_stderr=…) for Click 8.3+ (P2-001)
fix(cli): replace _exit_with_error with raise SystemExit(_exit_code_for) (P2-002)
fix(pipeline): capture apply_overrides return value (P2-003)
fix(brand): parameterise locales as dict[str, dict[str, Any]] (P2-004)
fix(transformers): annotate bare list vars as list[Block] (P2-005)
chore(pipeline): hoist inline imports to module top (P2-006, P2-007)
test(integration): add --brand registry test + fix criterion 5/9 (P2-008)
chore(test): drop unused json/pytest imports (P2-009)
chore(pipeline): thread render_id into _resolve_brand BrandError (P2-010)
chore(cli): remove _exit_with_error helper (P2-011, no-op if P2-002 applied)
chore(cli): use model_dump(mode="json") in brand_show (P2-012)
```

## Patch Acceptance Bar

After all 12 patches applied:

- `CliRunner(mix_stderr=False)` no longer appears in the test suite.
- `ruff check src/ tests/` passes with no findings.
- `mypy --strict src/mdpdf` passes with no findings.
- Acceptance criterion 5 (`--brand idimsum` via registry) is exercised by a dedicated integration test.
- Acceptance criterion 9 text is corrected.
- All Plan 1 + Plan 2 acceptance criteria still hold (no regressions from these patches).

---

## Tasks Reviewed and Found Sound (no patch needed)

The following tasks were inspected and have no warranting issues:

- **Task 15 (font manager):** Sound. `cjk_chars_present` correctly duplicates the Plan 1 helper to avoid circular imports; `_register_dir` heuristic for CJK detection ("Noto" / "CJK" / "SC" in stem) matches the bundled font naming.
- **Task 16 (legacy brand adapter):** Sound. `load_legacy_brand_pack` correctly bypasses the `id == directory_name` check (legacy adapter pattern); `BrandPack(**payload)` with `pack_root=pack_root` is intentional.
- **Task 17 (migrator):** Sound. `migrate_v1_to_v2` chains correctly through `load_legacy_brand_pack` → write v2 files → validate via `load_brand_pack(v2_output)`. Round-trip test covers the full chain.
- **Task 19 (BrandStyles factory):** Sound. `_default_styles()` fallback correctly preserves Plan 1's walking-skeleton behaviour for `ReportLabEngine(brand_styles=None)`.
- **Tasks 1, 3, 4, 7 (chain runner, strip_yaml_frontmatter, normalize_merged_atx_headings, collect_outline):** Test assertions and implementation logic are consistent. Task 4's previously-discovered ATX-semantics bug (`new_level = node.level + n_hashes` → `new_level = n_hashes`) is already fixed in the Plan 2 document.

---

## Summary

**Total: 12 patches — 3 Critical, 6 Important, 3 Polish.**

**Top 3 by severity:**

1. **P2-001 🔴 Task 18** — `CliRunner(mix_stderr=False)` repeats the Click 8.3 breakage that was already fixed once in Plan 1 (P1-002). Will raise `TypeError` before any assertion runs.
2. **P2-002 🔴 Task 18** — `_exit_with_error` uses `sys.exit()` instead of `raise SystemExit(_exit_code_for(e))`. Unreachable `return` statements after each call site will be flagged by mypy --strict --warn-unreachable.
3. **P2-003 🔴 Task 20** — `apply_overrides(payload, ...)` return value discarded. Currently safe (in-place mutation) but fragile; one-character fix (`payload = apply_overrides(...)`) eliminates the latent risk.
