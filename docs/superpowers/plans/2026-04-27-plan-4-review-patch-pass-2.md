# Plan 4 — Review Patch (Pass 2)

Independent technical review found 5 additional defects that the first-pass review (P4-001..P4-012) did not capture. Apply these in addition to pass 1.

## Severity Legend

- 🔴 **Critical** — Plan as written will fail to compile, fail tests, or violate explicit project guard rails.
- 🟡 **Notable** — Plan will run but introduces a real bug or contradicts a stated invariant.
- 🟢 **Polish** — Cosmetic / consistency.

## Patch Summary

| ID | Severity | Area | Issue |
|---|---|---|---|
| P4-013 | 🔴 | Task 10 tests | Mock targets `apply_watermark` / `inject_xmp` not renamed alongside P4-001 |
| P4-014 | 🔴 | Tasks 11, 12 tests | `Pipeline()` instantiation missing required `engine=` positional arg |
| P4-015 | 🔴 | Task 17 | Existing deterministic-pure guard already in `select_mermaid_renderer` — Task 17 reduces to 4-line addition, not a class refactor |
| P4-016 | 🟡 | Task 9 | `apply_issuer_card` final write is non-atomic — same bug as P4-012 footer |
| P4-017 | 🟡 | Task 18 | `_enforce_windows_acl()` block imports `pywin32` — Windows ACL is deferred to v2.3 per CLAUDE.md |

---

## P4-013 🔴 — Task 10 test mocks reference renamed callees

**Location:** Task 10 Step 1 (`tests/unit/post_process/test_pipeline.py`).

### Problem

The test file patches:

```python
patch("mdpdf.post_process.pipeline.apply_watermark")
patch("mdpdf.post_process.pipeline.inject_xmp")
```

P4-001 renames `apply_watermark` → `apply_l1_watermark` and `inject_xmp` → `apply_l2_xmp` in `post_process/pipeline.py`. The mocks must be renamed in lockstep, otherwise both `test_l0_skips_l1_and_l2` and `test_l1_plus_l2_runs_both` will silently mock nothing and pass vacuously — the guard branches under test never execute.

The same file's `from mdpdf.security.watermark import WatermarkOptions` is also wrong — `WatermarkOptions` lives in `mdpdf.pipeline` (verify with `grep -n "class WatermarkOptions" src/mdpdf/`).

### Patched code

```python
# In tests/unit/post_process/test_pipeline.py:
from mdpdf.pipeline import WatermarkOptions  # not mdpdf.security.watermark

# Mock targets:
with patch("mdpdf.post_process.pipeline.apply_l1_watermark") as l1, \
     patch("mdpdf.post_process.pipeline.apply_l2_xmp") as l2:
```

### Acceptance

After P4-001 + P4-013: both `test_l0_skips_l1_and_l2` and `test_l1_plus_l2_runs_both` exercise the real call sites; mocks fire when expected.

---

## P4-014 🔴 — `Pipeline()` instantiation missing required `engine` argument

**Location:** Task 11 Step 1 (`TestPipelinePostProcess`), Task 12 Step 1 (`TestPipelineAudit`), Task 13 Step 1 (`TestPipelineDeterminism`) — all in `tests/unit/test_pipeline.py`.

### Problem

The current production signature is:

```python
class Pipeline:
    def __init__(self, engine: RenderEngine) -> None: ...
```

`engine` is a **required positional parameter**. The new test classes call:

```python
pipeline = Pipeline()                    # Task 11
pipeline = Pipeline(audit=logger)        # Task 12
```

Both raise `TypeError: __init__() missing 1 required positional argument: 'engine'`.

P4-002 fixes `TestPipelineAudit` only. The post-process and determinism test classes are not patched.

### Patched code

In every new `Pipeline(...)` call within `TestPipelinePostProcess` and `TestPipelineDeterminism`, pass an explicit engine:

```python
from mdpdf.render.engine_reportlab import ReportLabEngine

pipeline = Pipeline(engine=ReportLabEngine())
pipeline = Pipeline(engine=ReportLabEngine(), audit=logger)
```

Alternatively, prefer `Pipeline.from_env()` which Plan 1 already provides as a no-arg factory.

### Acceptance

`pytest tests/unit/test_pipeline.py -v` collects all tests without `TypeError` at instantiation.

---

## P4-015 🔴 — Task 17 should be a 4-line addition, not a class refactor

**Location:** Task 17 Step 1.

### Problem

Task 17 frames the change as "Add `deterministic` parameter to `MermaidRendererChain`". P4-005 already noted that `MermaidRendererChain` does not exist — only the `select_mermaid_renderer()` function. But P4-005 stops at "rewrite to use the function"; it does not point out that the deterministic guard **already exists** in the function:

```python
# src/mdpdf/renderers/mermaid_chain.py (current state)
if preference == "pure":
    if ctx.deterministic:
        raise RendererError(
            code="RENDERER_NON_DETERMINISTIC",
            user_message="--mermaid-renderer pure rejected in --deterministic mode",
        )
    return PureMermaidRenderer()
# ...
# auto path (lines 57-64)
if mermaid_pure._import_mermaid() is not None and not ctx.deterministic:
    return PureMermaidRenderer()
raise RendererError(
    code="MERMAID_RENDERER_UNAVAILABLE",
    user_message=("no mermaid renderer available. Install one of: ...")
)
```

The only missing behaviour: when `auto` mode falls through to the final raise *because* `ctx.deterministic` excluded `pure`, the error code should be `RENDERER_NON_DETERMINISTIC` rather than `MERMAID_RENDERER_UNAVAILABLE` (so the user sees a determinism-specific message, not a "install mmdc" suggestion).

### Patched code

In `src/mdpdf/renderers/mermaid_chain.py`, replace the auto-path final raise:

```python
    if mermaid_pure._import_mermaid() is not None and not ctx.deterministic:
        return PureMermaidRenderer()
    # If deterministic mode excluded the only available renderer, raise the
    # determinism-specific error so the message points at the right fix.
    if ctx.deterministic and mermaid_pure._import_mermaid() is not None:
        raise RendererError(
            code="RENDERER_NON_DETERMINISTIC",
            user_message=(
                "deterministic mode requires a deterministic mermaid renderer "
                "(kroki or puppeteer); install one or drop --deterministic"
            ),
        )
    raise RendererError(
        code="MERMAID_RENDERER_UNAVAILABLE",
        user_message=("no mermaid renderer available. Install one of: ...")
    )
```

### Test (replace Task 17 Step 2):

```python
def test_auto_in_deterministic_mode_with_only_pure_raises_non_deterministic(
    monkeypatch
):
    monkeypatch.delenv("KROKI_URL", raising=False)
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_puppeteer._find_mmdc", lambda: None
    )
    monkeypatch.setattr(
        "mdpdf.renderers.mermaid_pure._import_mermaid", lambda: object()
    )
    ctx = RenderContext(
        cache_root=Path("/tmp"), brand_pack=None,
        allow_remote_assets=False, deterministic=True,
    )
    with pytest.raises(RendererError) as ei:
        select_mermaid_renderer(preference="auto", ctx=ctx)
    assert ei.value.code == "RENDERER_NON_DETERMINISTIC"
```

### Acceptance

`select_mermaid_renderer(preference="auto", ctx=ctx_with_deterministic)` raises `RENDERER_NON_DETERMINISTIC` (not `MERMAID_RENDERER_UNAVAILABLE`) when only `pure` would have been selected. The pure-direct (`preference="pure"`) path is unchanged.

---

## P4-016 🟡 — `apply_issuer_card` non-atomic write (same bug as P4-012)

**Location:** Task 9 Step 3 (`src/mdpdf/post_process/issuer_card.py`).

### Problem

P4-012 patches `apply_footer` to use the tempfile → fsync → rename pattern, and the closing line says "the same fix applies to `issuer_card`" — but does not provide a patched block. The executor will not write atomic code unless the patch is concrete.

### Patched code

Apply the identical pattern from `mdpdf.cache.tempfiles.atomic_write` (already used elsewhere in the codebase):

```python
from mdpdf.cache.tempfiles import atomic_write

def apply_issuer_card(pdf_path: Path, ...) -> None:
    ...
    with atomic_write(pdf_path) as fp:
        writer.write(fp)
```

### Acceptance

A SIGKILL during `apply_issuer_card` leaves the original PDF intact (no truncated output).

---

## P4-017 🟡 — Task 18 Windows ACL block is out of scope

**Location:** Task 18 Step 3 (`src/mdpdf/security/audit.py`).

### Problem

Task 18 includes a `_enforce_windows_acl()` helper that imports `pywin32` and `ntsecuritycon` to apply Windows file ACLs. CLAUDE.md "v2.0 scope guard rails — what NOT to build" lists Windows ACL hardening as a v2.3 deferral. The task's own scope notes acknowledge this but the implementation block contradicts it.

### Patched code

Replace `_enforce_windows_acl()` with a one-shot stderr warning:

```python
import sys, warnings

def _warn_windows_acl_unsupported() -> None:
    if sys.platform.startswith("win"):
        warnings.warn(
            "audit log file permissions are POSIX-only in v2.0; "
            "Windows ACL hardening is planned for v2.3",
            stacklevel=2,
        )
```

Call it once during `AuditLogger.__init__` (after the file is created). Drop the `pywin32` and `ntsecuritycon` imports.

### Acceptance

`pip show pywin32` returns "Package not installed" and `pytest -q` still passes on Windows runners — proving the dependency was not introduced.

---

## Apply Order

P4-013, P4-014, P4-015 are independent and can be applied in parallel. P4-016 depends on P4-012 (apply atomic_write pattern after pass-1 fix). P4-017 is independent.

## Patch Acceptance Bar

After P4-001..P4-017 applied:

- `ruff check src/ tests/` — clean.
- `mypy --strict src/mdpdf` — clean.
- `pytest tests/unit/post_process tests/unit/test_pipeline.py` collects without `TypeError`.
- No `pywin32` import anywhere in `src/`.
- `select_mermaid_renderer(preference="auto", ctx=…deterministic…)` raises `RENDERER_NON_DETERMINISTIC` when only `pure` is available.
