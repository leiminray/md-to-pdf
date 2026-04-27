# Plan 4 (Watermarks + Audit + Determinism) — Review Patches

**Date:** 2026-04-27
**Patches against:** [`2026-04-27-md-to-pdf-v2.0-plan-4-watermarks-audit-determinism.md`](2026-04-27-md-to-pdf-v2.0-plan-4-watermarks-audit-determinism.md)
**Reviewer:** sophie.leiyixiao@gmail.com (cold review by independent subagent; Tasks 1–22 authored, none yet executed)
**Apply how:** patches are independent unless noted. Apply all, a subset, or skip — each carries its own rationale. Plan 4 source file is **not modified** by this document.

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
| P4-001 | 🔴 | 10 | `post_process/pipeline.py` imports non-existent `mdpdf.security.watermark` and `mdpdf.security.xmp` modules |
| P4-002 | 🔴 | 12 | `mdpdf.audit` import path wrong + `log_event()` method doesn't exist — should be `mdpdf.security.audit` + `log_start/complete/error` |
| P4-003 | 🔴 | 13 | `derive_render_id` called with wrong keyword args (`input_hash`, `brand_name`, `epoch`) vs actual signature (`input_bytes`, `brand_id`, `brand_version`, `options_serialised`, `watermark_user`); `"det-"` prefix assertion fabricated |
| P4-004 | 🔴 | 20 | `_REQUIRED_XMP_KEYS` 12-key list uses camelCase (`mdpdf:renderUser`, `mdpdf:sourceHash`, etc.) — spec §5.3 and Task 4 implementation use PascalCase (`mdpdf:RenderUser`, `mdpdf:InputHash`, etc.); 5 keys are entirely fictitious |
| P4-005 | 🔴 | 17 | Task 17 invents a `MermaidRendererChain` class with `select()` method — actual code in `mermaid_chain.py` is a `select_mermaid_renderer()` function; the class API doesn't exist |
| P4-006 | 🔴 | 16 | `CliRunner(mix_stderr=False)` repeats the P1-002/P2-001 Click 8.3 breakage in `test_cli_no_watermark_idimsum_exits_3` |
| P4-007 | 🟡 | 11 | `Pipeline.render()` wiring uses wrong field names: `request.watermark_options` (no such field — actual is `request.watermark`); `request.watermark_user` (no such field — use `request.watermark.user`) |
| P4-008 | 🟡 | 15 | `WatermarkOptions` imported from `mdpdf.security.watermark` in `cli.py` — actual location is `mdpdf.pipeline`; `RenderRequest.watermark_options` should be `watermark` |
| P4-009 | 🟡 | 18 | `Path.touch(mode=0o640)` does not reliably set POSIX mode (mode arg is ignored by CPython on many platforms) — must use `open()` + `os.chmod()` |
| P4-010 | 🟡 | 18 | `test_default_path_without_env_var` creates `~/.md-to-pdf/audit.jsonl` on the CI runner's real home directory — violates the "never pollute $HOME" test isolation rule |
| P4-011 | 🟡 | 12 | `test_audit_events_written_on_success` asserts required keys `source_hash` and `tool_version` but `AuditLogger.log_start()` emits neither; also `Pipeline.__init__` currently takes only `engine: RenderEngine` — adding `audit=` changes the public API without a compatibility note |
| P4-012 | 🟢 | 8 | `apply_footer` writes the final PDF with a bare `open(pdf_path, "wb")` — not atomic; all other file-writing helpers in Plan 4 use temp-file-then-rename |

---

## P4-001 🔴 — `post_process/pipeline.py` imports non-existent modules

**Location:** Task 10 Step 3 (`src/mdpdf/post_process/pipeline.py`), module-top imports.

### Problem

```python
from mdpdf.security.watermark import WatermarkOptions, apply_watermark
from mdpdf.security.xmp import inject_xmp
```

Plan 4 creates these files:
- `src/mdpdf/security/watermark_l1.py` — contains `apply_l1_watermark`
- `src/mdpdf/security/watermark_l2.py` — contains `apply_l2_xmp`

There is no `mdpdf.security.watermark` module and no `mdpdf.security.xmp` module. `WatermarkOptions` lives in `mdpdf.pipeline`. Both imports will raise `ModuleNotFoundError` at runtime, making the entire `post_process/pipeline.py` unimportable.

### Patched code

```python
# Before
from mdpdf.security.watermark import WatermarkOptions, apply_watermark
from mdpdf.security.xmp import inject_xmp

# After
from mdpdf.pipeline import WatermarkOptions
from mdpdf.security.watermark_l1 import apply_l1_watermark
from mdpdf.security.watermark_l2 import apply_l2_xmp
```

Update call sites in `PostProcessPipeline.run()` to use the correct function names:

```python
# Before
if opts.watermark.level != "L0":
    apply_watermark(
        pdf_path,
        user=opts.render_user or "unknown",
        brand_name=brand_name,
        render_date=opts.render_date,
        watermark_text=opts.watermark.custom_text,
    )
    inject_xmp(
        pdf_path,
        render_id=opts.render_id,
        ...
    )

# After
if opts.watermark.level != "L0":
    if opts.watermark.level in ("L1", "L1+L2"):
        apply_l1_watermark(
            pdf_path,
            brand_name=brand_name,
            user=opts.render_user or "unknown",
            render_date=opts.render_date,
            template=opts.watermark.custom_text or "{brand_name} // {user} // {render_date}",
        )
    apply_l2_xmp(
        pdf_path,
        dc_creator=brand_name,
        dc_title=opts.document_title,
        render_id=opts.render_id,
        render_user=opts.render_user or "",
        render_host=opts.render_host_hash,
        brand_id=getattr(getattr(opts.brand_pack, "id", None), "__str__", lambda: "")() or "",
        brand_version=getattr(getattr(opts.brand_pack, "version", None), "__str__", lambda: "")() or "",
        input_hash=opts.input_hash,
        create_date=opts.render_date,
        watermark_level=opts.watermark.level,
    )
```

The test file `test_pipeline.py` mocks `mdpdf.post_process.pipeline.apply_watermark` and `mdpdf.post_process.pipeline.inject_xmp` — these mock targets must be updated to `apply_l1_watermark` / `apply_l2_xmp` respectively.

### Rationale

`ModuleNotFoundError` at import time means every test in `tests/unit/post_process/test_pipeline.py` will error (not fail) immediately. The Task 10 plan itself correctly shows `apply_l1_watermark` / `apply_l2_xmp` in Tasks 3–4 but then aliases them under different names in Task 10 without creating the aliased modules.

---

## P4-002 🔴 — Wrong audit module path + non-existent `log_event` method in Task 12

**Location:** Task 12 Step 3 (`src/mdpdf/pipeline.py`, audit integration) and `tests/unit/test_pipeline.py` (`TestPipelineAudit`).

### Problem

```python
# Task 12 Step 3 (pipeline.py):
from mdpdf.audit import AuditLogger

# Task 12 tests (test_pipeline.py):
from mdpdf.audit import AuditLogger
```

`AuditLogger` is defined in `src/mdpdf/security/audit.py`, not `src/mdpdf/audit.py`. There is no `mdpdf.audit` module at any path in the Plan 4 file structure. Both import sites will raise `ModuleNotFoundError`.

Additionally, Task 12 calls a method `self._audit.log_event(...)`:

```python
# Task 12 Step 3 — log_event does not exist
self._audit.log_event("render.start", render_id=render_id, ...)
self._audit.log_event("render.complete", render_id=render_id, ...)
self._audit.log_event("render.error", render_id=render_id, code=..., message=...)
```

`AuditLogger` (Task 6) has three separate methods — `log_start(...)`, `log_complete(...)`, `log_error(...)` — with distinct keyword signatures. There is no `log_event` method. Every call will raise `AttributeError`.

Also, `Pipeline.__init__` currently takes `engine: RenderEngine` (Plan 1). Task 12 changes it to accept `audit: AuditLogger | None = None` without mentioning removal of the `engine` parameter. The patched signature must keep `engine` as a parameter (or use `from_env()` to supply it).

### Patched code

```python
# In pipeline.py — correct import:
from mdpdf.security.audit import AuditLogger

# In pipeline.py — correct __init__ signature (keep existing engine param):
def __init__(
    self,
    engine: RenderEngine,
    audit: AuditLogger | None = None,
) -> None:
    self._engine = engine
    self._audit = audit if audit is not None else AuditLogger()

# In pipeline.py — correct log call for render.start:
if request.audit_enabled and self._audit:
    self._audit.log_start(
        render_id=render_id,
        user=request.watermark.user,
        host_hash=host_hash,
        brand_id=brand_pack.id if brand_pack else "",
        brand_version=str(brand_pack.version) if brand_pack else "",
        template=request.template,
        input_path=Path(request.source) if request.source_type == "path" else None,
        input_size=0,           # populated after reading source bytes
        input_sha256=input_hash,
        watermark_level=request.watermark.level,
        deterministic=request.deterministic,
        locale=request.locale,
    )

# For render.complete:
if request.audit_enabled and self._audit:
    self._audit.log_complete(
        render_id=render_id,
        duration_ms=result.metrics.total_ms,
        output_path=result.output_path,
        output_size=result.bytes,
        output_sha256=result.sha256,
        pages=result.pages,
        renderers_used={},
        warnings=result.warnings,
    )

# For render.error:
if request.audit_enabled and self._audit:
    self._audit.log_error(
        render_id=render_id,
        duration_ms=int((time.perf_counter() - t0) * 1000),
        code=getattr(exc, "code", "UNEXPECTED"),
        message=str(exc),
    )
```

Update test imports:

```python
# Before (both import sites in test_pipeline.py):
from mdpdf.audit import AuditLogger

# After:
from mdpdf.security.audit import AuditLogger
```

`Pipeline(audit=logger)` in the tests must be `Pipeline(engine=ReportLabEngine(), audit=logger)` to keep the existing required `engine` parameter.

### Rationale

Two independent `ModuleNotFoundError` and one `AttributeError` — the entire `TestPipelineAudit` suite would error (not fail) on import. The `from_env()` classmethod is also broken by this change unless updated.

---

## P4-003 🔴 — `derive_render_id` called with wrong keyword arguments in Task 13

**Location:** Task 13 Step 3 (`src/mdpdf/pipeline.py`, deterministic render-id derivation) and `TestPipelineDeterminism` tests.

### Problem

Task 13 Step 3 wires `derive_render_id` as:

```python
render_id = derive_render_id(
    input_hash=input_hash,          # ← wrong kwarg name (actual: input_bytes)
    brand_name=brand_name,          # ← wrong kwarg name (actual: brand_id + brand_version)
    watermark_user=request.watermark_user or "",  # ← no such field (actual: request.watermark.user)
    epoch=source_date_epoch,        # ← not a parameter at all
)
```

The actual signature from Task 5 `deterministic.py` is:

```python
def derive_render_id(
    *,
    input_bytes: bytes,
    brand_id: str,
    brand_version: str,
    options_serialised: str,
    watermark_user: str | None,
) -> str:
```

All four keyword arguments are wrong. `TypeError` will be raised at every deterministic render attempt.

Additionally, `TestPipelineDeterminism.test_deterministic_render_id_is_not_uuid4` asserts:

```python
assert result.render_id.startswith("det-"), ...
```

But `derive_render_id` returns a plain UUID-shaped hex string (e.g. `"a1b2c3d4-e5f6-..."`), not a `"det-"` prefixed string. The prefix assertion is fabricated and will always fail even after the kwarg fix.

### Patched code

```python
# In Pipeline.render(), replace the broken call with:
render_id = derive_render_id(
    input_bytes=source_bytes,           # bytes already read for sha256
    brand_id=brand_pack.id if brand_pack else "",
    brand_version=str(brand_pack.version) if brand_pack else "",
    options_serialised=serialise_options(
        template=request.template,
        locale=request.locale,
        watermark_level=request.watermark.level,
        watermark_custom_text=request.watermark.custom_text,
        brand_overrides=dict(request.brand_overrides),
    ),
    watermark_user=request.watermark.user,
)
```

Fix the `startswith("det-")` assertion:

```python
# Before
assert result.render_id.startswith("det-"), ...

# After
# derive_render_id returns a UUID-shaped hex; verify it is stable across calls, not prefixed
import re
uuid_re = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
assert uuid_re.match(result.render_id), f"Unexpected render-id format: {result.render_id}"
```

Remove the `startswith("det-")` assertion from `test_source_date_epoch_env_triggers_determinism` for the same reason.

### Rationale

`TypeError: derive_render_id() got an unexpected keyword argument 'input_hash'` will be raised on every deterministic render path. The prefix assertion is not supported by the Task 5 implementation.

---

## P4-004 🔴 — `_REQUIRED_XMP_KEYS` in Task 20 contradicts spec §5.3 and Task 4 implementation

**Location:** Task 20 Step 2 (`tests/integration/test_watermarks_audit_determinism.py`), `_REQUIRED_XMP_KEYS` constant; also acceptance check AC-2 in Task 22.

### Problem

```python
# Task 20 — _REQUIRED_XMP_KEYS (12 entries):
_REQUIRED_XMP_KEYS = [
    "mdpdf:renderUser",           # wrong case — spec: mdpdf:RenderUser
    "mdpdf:renderDate",           # not in spec §5.3 at all
    "mdpdf:renderId",             # wrong case — spec: mdpdf:RenderId
    "mdpdf:watermarkLevel",       # wrong case — spec: mdpdf:WatermarkLevel
    "mdpdf:watermarkTemplate",    # not in spec §5.3 at all
    "mdpdf:brandId",              # wrong case — spec: mdpdf:BrandId
    "mdpdf:brandVersion",         # wrong case — spec: mdpdf:BrandVersion
    "mdpdf:sourceHash",           # not in spec — spec: mdpdf:InputHash
    "mdpdf:toolVersion",          # not in spec §5.3 at all
    "mdpdf:locale",               # not in spec §5.3 at all
    "mdpdf:deterministicMode",    # not in spec §5.3 at all
    "mdpdf:auditEnabled",         # not in spec §5.3 at all
]
```

Spec §5.3 defines exactly 12 keys:

| XMP Key | Notes |
|---|---|
| `dc:creator` | |
| `dc:title` | |
| `pdf:Producer` | |
| `xmp:CreatorTool` | |
| `xmp:CreateDate` | |
| `mdpdf:RenderId` | PascalCase |
| `mdpdf:RenderUser` | PascalCase |
| `mdpdf:RenderHost` | PascalCase |
| `mdpdf:BrandId` | PascalCase |
| `mdpdf:BrandVersion` | PascalCase |
| `mdpdf:InputHash` | PascalCase |
| `mdpdf:WatermarkLevel` | PascalCase |

The Task 20 list differs from the spec in three ways: (1) all `mdpdf:` keys use wrong camelCase rather than PascalCase, (2) six keys (`mdpdf:renderDate`, `mdpdf:watermarkTemplate`, `mdpdf:sourceHash`, `mdpdf:toolVersion`, `mdpdf:locale`, `mdpdf:deterministicMode`, `mdpdf:auditEnabled`) are entirely absent from the spec, and (3) five spec-required keys (`dc:creator`, `dc:title`, `pdf:Producer`, `xmp:CreatorTool`, `xmp:CreateDate`, `mdpdf:RenderHost`) are missing from the list. The integration test for AC-2 uses the same wrong list.

### Patched code

```python
# Before
_REQUIRED_XMP_KEYS = [
    "mdpdf:renderUser",
    "mdpdf:renderDate",
    "mdpdf:renderId",
    "mdpdf:watermarkLevel",
    "mdpdf:watermarkTemplate",
    "mdpdf:brandId",
    "mdpdf:brandVersion",
    "mdpdf:sourceHash",
    "mdpdf:toolVersion",
    "mdpdf:locale",
    "mdpdf:deterministicMode",
    "mdpdf:auditEnabled",
]

# After — matches spec §5.3 exactly (same 12 keys as Task 4's apply_l2_xmp)
_REQUIRED_XMP_KEYS = [
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

Apply the same correction to the AC-2 bash one-liner in Task 22 Step 2.

### Rationale

The integration test `test_l2_xmp_keys_present` and the AC-2 acceptance check would never find any of the 12 spec-required keys because every key name is wrong. The test would pass vacuously only if it made the assertion vacuous — but as written, it asserts each key is non-empty, so every key assertion would fail silently (returning `None`). `assert None` evaluates to `AssertionError` for every key.

---

## P4-005 🔴 — Task 17 invents a `MermaidRendererChain` class that doesn't exist

**Location:** Task 17 (all steps) — `src/mdpdf/renderers/mermaid_chain.py` and `tests/unit/renderers/test_mermaid_chain.py`.

### Problem

Task 17 proposes adding a `MermaidRendererChain` class with `__init__(preferred, deterministic, kroki_url)` and `select() -> str` and `_is_available(name) -> bool` methods. It then writes unit tests that instantiate `MermaidRendererChain(preferred="pure", deterministic=True)` and call `.select()`.

The actual code already present in `mermaid_chain.py` (Plan 3 deliverable) is a standalone **function** `select_mermaid_renderer(*, preference, ctx, kroki_url_override)` — no class at all. The deterministic-pure guard is already partially implemented there too:

```python
if preference == "pure":
    if ctx.deterministic:
        raise RendererError(code="RENDERER_NON_DETERMINISTIC", ...)
    return PureMermaidRenderer()
```

Instantiating `MermaidRendererChain(...)` will raise `NameError: name 'MermaidRendererChain' is not defined`. All 7 `TestMermaidChainDeterministicMode` tests will error immediately.

### Patched code

Replace the entire Task 17 class-based API with patches to the existing `select_mermaid_renderer` function:

**Step 1** — verify the existing guard already handles `preference="pure"` + `ctx.deterministic` (it does). Add the auto-deterministic path guard (auto-fallback should not reach `pure` when `ctx.deterministic` is True):

```python
# In mermaid_chain.py — update auto path (currently lines 57-72):
# auto
if kroki_url:
    return KrokiMermaidRenderer(base_url=kroki_url)
if mermaid_puppeteer._find_mmdc() is not None:
    return PuppeteerMermaidRenderer()
if mermaid_pure._import_mermaid() is not None and not ctx.deterministic:
    return PureMermaidRenderer()
# No renderer available
if ctx.deterministic:
    raise RendererError(
        code="RENDERER_NON_DETERMINISTIC",
        user_message=(
            "No deterministic-safe Mermaid renderer available "
            "(tried: kroki, puppeteer). Install puppeteer or set KROKI_URL."
        ),
    )
raise RendererError(
    code="MERMAID_RENDERER_UNAVAILABLE",
    user_message="no mermaid renderer available ...",
)
```

**Step 2** — rewrite `TestMermaidChainDeterministicMode` to use `select_mermaid_renderer()` with a mock `RenderContext`:

```python
from mdpdf.renderers.mermaid_chain import select_mermaid_renderer
from mdpdf.renderers.base import RenderContext

def _ctx(deterministic: bool = False) -> RenderContext:
    return RenderContext(cache_root=Path("/tmp"), deterministic=deterministic, allow_remote=False)

def test_explicit_pure_in_deterministic_mode_raises(monkeypatch):
    with pytest.raises(RendererError) as exc_info:
        select_mermaid_renderer(
            preference="pure",
            ctx=_ctx(deterministic=True),
        )
    assert exc_info.value.code == "RENDERER_NON_DETERMINISTIC"
```

### Rationale

Proposing a class API over an existing function API without removing the function creates two inconsistent entry points. Since Plan 3's `select_mermaid_renderer` is already partially correct (guards `pure` in deterministic mode via `ctx.deterministic`), the correct fix is an additive patch to the auto path, not a new class.

---

## P4-006 🔴 — `CliRunner(mix_stderr=False)` in Task 16 repeats P1-002/P2-001

**Location:** Task 16 Step 4 (`tests/unit/test_pipeline.py`), `test_cli_no_watermark_idimsum_exits_3`.

### Problem

```python
runner = CliRunner(mix_stderr=False)
...
assert "WATERMARK_DENIED" in (result.stderr or result.output)
```

Click 8.3 removed `mix_stderr` from `CliRunner.__init__()`. This is the same breakage caught by P1-002 (Plan 1 review) and P2-001 (Plan 2 review). On Click 8.3+, `CliRunner(mix_stderr=False)` raises `TypeError: CliRunner.__init__() got an unexpected keyword argument 'mix_stderr'`.

### Patched code

```python
# Before
runner = CliRunner(mix_stderr=False)
result = runner.invoke(cli, [...])
assert "WATERMARK_DENIED" in (result.stderr or result.output)

# After
runner = CliRunner()
result = runner.invoke(cli, [...])
# In Click 8.3+ default mode stderr is merged into result.output
assert "WATERMARK_DENIED" in result.output
```

### Rationale

Three plans in a row have introduced this same breakage. The plan's pre-audit checklist (line ~158) does not include a "no `CliRunner(mix_stderr=False)`" check. Suggest adding it.

---

## P4-007 🟡 — `Pipeline.render()` wiring in Task 11 uses non-existent `RenderRequest` field names

**Location:** Task 11 Step 3 (`src/mdpdf/pipeline.py`), `PostProcessOptions` construction.

### Problem

```python
pp_opts = PostProcessOptions(
    brand_pack=resolved_brand,
    watermark=request.watermark_options,    # ← no such field; actual: request.watermark
    render_id=render_id,
    render_user=request.watermark_user,     # ← no such field; actual: request.watermark.user
    ...
)
```

`RenderRequest` (current `pipeline.py` line 56–71) has:
- `watermark: WatermarkOptions` — not `watermark_options`
- No `watermark_user` field — user is accessed via `request.watermark.user`

Both attribute accesses will raise `AttributeError` at runtime.

### Patched code

```python
# Before
watermark=request.watermark_options,
render_user=request.watermark_user,

# After
watermark=request.watermark,
render_user=request.watermark.user,
```

### Rationale

`RenderRequest` was designed in Plan 1 with `watermark: WatermarkOptions` (not `watermark_options`). Plan 4 Task 12 reuses the correct `request.watermark.user` form in some places but not all. Two `AttributeError`s on every render call.

---

## P4-008 🟡 — `WatermarkOptions` imported from wrong module in Task 15

**Location:** Task 15 Step 3 (`src/mdpdf/cli.py`), new import and `RenderRequest` construction.

### Problem

```python
# Task 15 Step 3 — wrong import:
from mdpdf.security.watermark import WatermarkOptions

# And in RenderRequest construction:
req = RenderRequest(
    ...,
    watermark_options=watermark_options,    # ← wrong field name; actual: watermark
)
```

`WatermarkOptions` is defined in `src/mdpdf/pipeline.py`. There is no `mdpdf.security.watermark` module (the watermark *functions* are in `watermark_l1.py` / `watermark_l2.py`). `ModuleNotFoundError` on CLI import.

Additionally, the existing `cli.py` already imports `WatermarkOptions` from `mdpdf.pipeline` (line 27: `from mdpdf.pipeline import Pipeline, RenderRequest, RenderResult, WatermarkOptions`). No new import is needed.

`RenderRequest.watermark_options` does not exist — the field is `watermark`.

### Patched code

```python
# Remove the new import entirely — WatermarkOptions is already imported from mdpdf.pipeline.

# Fix RenderRequest construction:
watermark_options = WatermarkOptions(
    user=watermark_user or "",
    level=watermark_level,
    custom_text=watermark_text,
)
req = RenderRequest(
    ...,
    watermark=watermark_options,    # ← correct field name
)
```

### Rationale

`ModuleNotFoundError` would prevent the CLI from starting. Since the import already exists at module top (from Plan 1), adding a duplicate import under a different path compounds the error.

---

## P4-009 🟡 — `Path.touch(mode=0640)` does not set POSIX permissions reliably

**Location:** Task 18 Step 1 (`src/mdpdf/security/audit.py`), `AuditLogger._ensure_file()`.

### Problem

```python
def _ensure_file(self) -> None:
    self._path.parent.mkdir(parents=True, exist_ok=True)
    if not self._path.exists():
        self._path.touch(mode=0o640)    # ← mode arg ignored by CPython on many platforms
    self._enforce_permissions()
```

`Path.touch(mode=...)` is documented to "apply any umask", meaning the umask is NOT bypassed. A typical umask of `0022` will produce `0640 & ~0022 = 0640` (happens to work) — but a stricter umask of `0027` produces `0640 & ~0027 = 0610`, and umask `0077` produces `0600`. The `mode` parameter to `Path.touch()` is effectively decorative on CPython/POSIX because the underlying `os.open` call respects the process umask. The subsequent `_enforce_permissions()` call does fix this via `os.chmod`, but only for pre-existing files; the `touch` branch is unreachable in the tested path.

More critically, Task 6's `audit.py` (the initial implementation) does NOT call `_ensure_file()` — it creates the file lazily in `_append()`. Task 18's `__init__` adds `self._ensure_file()` which creates the file immediately, breaking `test_no_audit_when_disabled` (Task 12) which asserts the file is NOT created unless a render event is logged.

### Patched code

```python
def _ensure_file(self) -> None:
    """Create the audit file and parent dirs if absent; enforce permissions."""
    self._path.parent.mkdir(parents=True, exist_ok=True)
    if not self._path.exists():
        # os.open bypasses umask correctly; Path.touch(mode=) does not.
        fd = os.open(str(self._path), os.O_CREAT | os.O_WRONLY, 0o640)
        os.close(fd)
    self._enforce_permissions()
```

Remove `self._ensure_file()` from `__init__` and call it lazily from `_append()` instead:

```python
def _append(self, event: dict[str, Any]) -> None:
    try:
        self._ensure_file()   # idempotent — creates + chmod only if needed
        line = json.dumps(event, ...) + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as exc:
        raise PipelineError(...) from exc
```

### Rationale

`Path.touch(mode=0o640)` does not reliably set 0o640 permissions. The `os.open` pattern with the desired mode bypasses umask correctly. The eager-creation behaviour also breaks the `--no-audit` contract.

---

## P4-010 🟡 — `test_default_path_without_env_var` pollutes `$HOME`

**Location:** Task 18 Step 2 (`tests/unit/security/test_audit.py`), `test_default_path_without_env_var`.

### Problem

```python
def test_default_path_without_env_var(self, tmp_path, monkeypatch):
    """Without env var, path defaults to ~/.md-to-pdf/audit.jsonl."""
    monkeypatch.delenv("MD_PDF_AUDIT_PATH", raising=False)
    expected = Path.home() / ".md-to-pdf" / "audit.jsonl"
    logger = AuditLogger()              # ← creates ~/.md-to-pdf/audit.jsonl
    assert logger._path == expected
```

`AuditLogger()` with no arguments and `MD_PDF_AUDIT_PATH` unset defaults to `~/.md-to-pdf/audit.jsonl`. After P4-009's patch (lazy `_ensure_file`), instantiation alone does not create the file — but any subsequent log call does. The test asserts only `logger._path == expected` which is safe.

However, with Task 18's eager `self._ensure_file()` in `__init__` (as written), instantiating `AuditLogger()` immediately creates `~/.md-to-pdf/audit.jsonl` on the CI runner's actual home directory, poisoning the test environment and potentially interfering with concurrent test runs.

### Patched code

```python
# Before
def test_default_path_without_env_var(self, tmp_path, monkeypatch):
    monkeypatch.delenv("MD_PDF_AUDIT_PATH", raising=False)
    expected = Path.home() / ".md-to-pdf" / "audit.jsonl"
    logger = AuditLogger()
    assert logger._path == expected

# After — verify the path is computed correctly without actually touching the filesystem:
def test_default_path_without_env_var(self, monkeypatch):
    monkeypatch.delenv("MD_PDF_AUDIT_PATH", raising=False)
    expected = Path.home() / ".md-to-pdf" / "audit.jsonl"
    # Instantiate with a fake path override to avoid writing to $HOME
    logger = AuditLogger.__new__(AuditLogger)
    object.__setattr__(logger, "_retain_days", 90)
    resolved = logger._resolve_default_path()  # must be a static helper
    assert resolved == expected
```

Alternative simpler approach: add a staticmethod `_resolve_default_path()` to `AuditLogger` and test only that:

```python
@staticmethod
def _resolve_default_path() -> Path:
    env_path = os.environ.get("MD_PDF_AUDIT_PATH")
    if env_path:
        return Path(env_path)
    return Path.home() / ".md-to-pdf" / "audit.jsonl"

def test_default_path_without_env_var(self, monkeypatch):
    monkeypatch.delenv("MD_PDF_AUDIT_PATH", raising=False)
    assert AuditLogger._resolve_default_path() == Path.home() / ".md-to-pdf" / "audit.jsonl"
```

### Rationale

The project-wide rule established since P2-008 is: tests must NEVER write to `~/.md-to-pdf/` or any other real `$HOME` path. Use `tmp_path` or env-var overrides for all I/O. A CI runner that runs this test will permanently create `~/.md-to-pdf/audit.jsonl` under the runner's home.

---

## P4-011 🟡 — `TestPipelineAudit` assertions reference keys not emitted by `log_start`

**Location:** Task 20 Step 2 (`tests/integration/test_watermarks_audit_determinism.py`), `test_audit_jsonl_written`; and Task 12 Step 1 (`tests/unit/test_pipeline.py`).

### Problem

```python
# Task 20 test_audit_jsonl_written:
required_keys = {"event", "timestamp", "render_id", "source_hash", "tool_version"}
for event in events:
    missing = required_keys - set(event.keys())
    assert not missing, ...
```

`AuditLogger.log_start()` (Task 6 implementation) emits these keys: `event`, `timestamp`, `render_id`, `user`, `host_hash`, `brand_id`, `brand_version`, `template`, `input_path`, `input_size`, `input_sha256`, `watermark_level`, `deterministic`, `locale`.

It does NOT emit `source_hash` or `tool_version`. Both are absent from the Task 6 audit schema. The assertion `missing = required_keys - set(event.keys())` will always produce `{"source_hash", "tool_version"}` for the `render.start` event, causing a guaranteed `AssertionError`.

The Appendix A schema in the spec must be consulted to determine the authoritative field list.

### Patched code

Replace the ad-hoc key assertion with a check against the actual `log_start` + `log_complete` field sets:

```python
# In test_audit_jsonl_written:
events = [_json.loads(line) for line in lines]
start_events = [e for e in events if e.get("event") == "render.start"]
complete_events = [e for e in events if e.get("event") == "render.complete"]
assert start_events, "render.start event missing"
assert complete_events, "render.complete event missing"

start = start_events[0]
# Check only keys that log_start actually emits (per Task 6 AuditLogger.log_start)
for key in ("event", "timestamp", "render_id", "host_hash", "watermark_level", "deterministic", "locale"):
    assert key in start, f"render.start missing key: {key}"
```

### Rationale

Testing against keys that don't exist in the implementation ensures the test always fails regardless of implementation quality. The required_keys set must match what `AuditLogger.log_start/complete` actually writes.

---

## P4-012 🟢 — `apply_footer` writes PDF non-atomically

**Location:** Task 8 Step 3 (`src/mdpdf/post_process/footer.py`), `apply_footer` function.

### Problem

```python
with open(pdf_path, "wb") as f:
    writer.write(f)
```

All other file-writing helpers in Plan 4 (Tasks 3, 4, 5, and the issuer card Task 9) use the atomic temp-file-then-rename pattern. `apply_footer` truncates and rewrites the target file directly. If the process is interrupted mid-write, the PDF is corrupted with no recovery path.

### Patched code

```python
# Before
with open(pdf_path, "wb") as f:
    writer.write(f)

# After — atomic write consistent with apply_l1_watermark, apply_l2_xmp, freeze_pdf_dates
import os, tempfile
dir_path = pdf_path.parent
fd, tmp_path_str = tempfile.mkstemp(
    dir=dir_path, prefix=pdf_path.name + ".footer.", suffix=".tmp"
)
try:
    with os.fdopen(fd, "wb") as f:
        writer.write(f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path_str, pdf_path)
except Exception:
    try:
        os.unlink(tmp_path_str)
    except OSError:
        pass
    raise
```

### Rationale

Consistency with every other PDF-writing helper in the plan. `apply_issuer_card` (Task 9) has the same non-atomic write pattern — same fix applies there.

---

## Apply Order & Independence

P4-001 and P4-002 are the highest-priority fixes and must be applied before any other task executes — they make `post_process/pipeline.py` and the audit integration unimportable. P4-003 and P4-007 share `pipeline.py` — apply together. P4-004 is integration-test only. P4-005 touches `mermaid_chain.py` independently. Suggested order:

1. **P4-001** — Fix `post_process/pipeline.py` imports (`security.watermark` → `watermark_l1`/`watermark_l2`; correct function names).
2. **P4-002** — Fix `from mdpdf.audit` → `from mdpdf.security.audit`; replace `log_event` with `log_start/complete/error`; keep `engine` param in `Pipeline.__init__`.
3. **P4-003 + P4-007** — Fix `derive_render_id` kwarg names + `RenderRequest` field names in `pipeline.py`; remove `startswith("det-")` assertion.
4. **P4-004** — Replace `_REQUIRED_XMP_KEYS` with spec §5.3 PascalCase list.
5. **P4-005** — Replace `MermaidRendererChain` class tests with `select_mermaid_renderer` function tests.
6. **P4-006** — Drop `CliRunner(mix_stderr=False)` in Task 16 test.
7. **P4-008** — Fix `WatermarkOptions` import in `cli.py`; fix `watermark_options` → `watermark` in `RenderRequest`.
8. **P4-009 + P4-010** — Fix `Path.touch(mode=...)` with `os.open`; lazy `_ensure_file`; fix home-pollution test.
9. **P4-011** — Fix audit required_keys assertion to match `log_start` schema.
10. **P4-012** — Atomic write for `apply_footer` and `apply_issuer_card`.

Recommended commit messages:

```
fix(post_process): correct module paths for watermark_l1/l2 imports in pipeline (P4-001)
fix(pipeline): use mdpdf.security.audit + log_start/complete/error API; keep engine param (P4-002)
fix(pipeline): fix derive_render_id kwarg names + RenderRequest.watermark.user access (P4-003, P4-007)
fix(test): replace camelCase XMP key list with spec §5.3 PascalCase keys (P4-004)
fix(renderers): rewrite Task 17 tests against select_mermaid_renderer() function (P4-005)
fix(test): drop CliRunner(mix_stderr=False) for Click 8.3+ (P4-006)
fix(cli): remove duplicate WatermarkOptions import; use request.watermark field (P4-008)
fix(audit): use os.open for 0o640 creation; lazy _ensure_file; fix home-pollution test (P4-009, P4-010)
fix(test): align audit required_keys with log_start/complete schema (P4-011)
fix(post_process): atomic PDF write in apply_footer and apply_issuer_card (P4-012)
```

## Patch Acceptance Bar

After all 12 patches applied:

- `from mdpdf.post_process.pipeline import PostProcessOptions, PostProcessPipeline` succeeds without `ModuleNotFoundError`.
- `from mdpdf.security.audit import AuditLogger` is the single import path used everywhere; `mdpdf.audit` does not exist.
- `derive_render_id(input_bytes=..., brand_id=..., brand_version=..., options_serialised=..., watermark_user=...)` is called with the exact keyword arguments matching Task 5's signature.
- `_REQUIRED_XMP_KEYS` in integration tests matches the 12 keys from spec §5.3: `dc:creator`, `dc:title`, `pdf:Producer`, `xmp:CreatorTool`, `xmp:CreateDate`, `mdpdf:RenderId`, `mdpdf:RenderUser`, `mdpdf:RenderHost`, `mdpdf:BrandId`, `mdpdf:BrandVersion`, `mdpdf:InputHash`, `mdpdf:WatermarkLevel`.
- `MermaidRendererChain` class does not appear anywhere; `select_mermaid_renderer()` is the single entry point.
- `CliRunner(mix_stderr=False)` does not appear in any test file.
- `ruff check src/ tests/` passes with no findings.
- `mypy --strict src/mdpdf` passes with no findings.
- No test creates any file under `~/.md-to-pdf/` or `Path.home()`.
- All Plan 1 + Plan 2 + Plan 3 acceptance criteria still hold (no regressions).

---

## Tasks Reviewed and Found Sound (no patch needed)

The following tasks were inspected and have no warranting issues:

- **Task 1 (error codes):** Sound. Tests correctly pattern-match the existing `SecurityError`/`PipelineError` constructor. `_exit_code_for` import from `mdpdf.cli` is correct.
- **Task 2 (contrast.py):** Sound. WCAG sRGB linearisation formula is correct. `_parse_hex` raises `ValueError` on invalid input. `enforce_min_contrast` returns the colour unchanged on success — correct.
- **Task 3 (watermark_l1.py):** Sound. `pypdf.PageObject.merge_page` call order (watermark page calls `merge_page(content_page)`) is correct for underlaying. Atomic write pattern matches project convention. `build_watermark_page` calls `enforce_min_contrast` on every call site.
- **Task 4 (watermark_l2.py):** Sound. `pikepdf.open_metadata(set_pikepdf_as_editor=False)` is the correct keyword argument. `meta.register_xml_namespace(_MDPDF_NS, "mdpdf")` correctly registers the custom namespace before writing keys. The 12 keys written match spec §5.3 exactly. Atomic write uses `pdf.save(tmp_path_str)` + `os.replace` — correct.
- **Task 5 (deterministic.py):** Sound. `derive_render_id` correctly double-hashes (first sha256 of `input_bytes`, then sha256 of the full payload). UUID reshaping to 8-4-4-4-12 from first 32 hex chars is correct (no version/variant bits set, which is fine for a deterministic opaque ID). `freeze_pdf_dates` opens a context manager on `pdf.open_metadata()` with `pass` to ensure XMP stream exists before `/Info` mutation — correct pikepdf sequence.
- **Task 6 (audit.py):** Sound (aside from P4-009/P4-010 covering `_ensure_file` and home pollution). `O_APPEND` atomicity claim is correct for writes under PIPE_BUF. Daily rotation logic correctly compares file mtime date vs today. 90-day retention glob + date parse is defensive (`ValueError` catch). `_now_iso()` using `datetime.now(tz=timezone.utc).isoformat()` produces the correct ISO 8601 with timezone.
- **Task 7 (i18n/strings.py):** Sound. `lookup` falls back to `en` when locale is unknown, then raises `KeyError` if key is also absent in `en` — matches spec requirement. `date_format` falls back to `en` pattern silently — correct.
- **Task 8 (footer.py):** Sound (aside from P4-012 non-atomic write). `_build_overlay` correctly draws `right_text` using `c.stringWidth` to compute the x-coordinate for right-alignment.
- **Task 9 (issuer_card.py):** Sound (aside from P4-012 non-atomic write). Applies overlay only to the last page (`i == total - 1`). Border strip drawn before text — correct layering.
- **Task 14 (CLI flag un-hiding):** Sound. Removing `hidden=True` from four Click options and deleting the "not yet implemented" warning blocks is the correct mechanical implementation. The `render_cmd` signature change to add `no_watermark` and `watermark_text` params follows Click conventions.
- **Task 16 (watermark policy gate):** Sound except for P4-006. `_check_watermark_policy` using an `_ORDER` dict with MRO-safe comparison is correct. `getattr(getattr(brand, "security", None), "watermark_min_level", "L0")` defensive access pattern matches what Plan 2 landed in `BrandPack.security.watermark_min_level`.
- **Task 18 (audit permissions + env var):** Sound except for P4-009/P4-010. `MD_PDF_AUDIT_PATH` env var override pattern is correct. `_WIN32_WARNED` class-level one-shot flag for pywin32 warning is appropriate.
- **Task 19 (deterministic golden corpus):** Sound. `sha256-baseline.json` with `__PLACEHOLDER__` + skip guard is the correct pattern for a golden file not yet generated. `_render()` helper correctly threads the env dict through `subprocess.run`.
- **Task 21 (locale footer integration):** Sound. `re.search(r"第\s*\d+\s*页", all_text)` correctly handles potential whitespace variation in CJK text extraction.
- **Task 22 (acceptance verification):** Sound except for the AC-2 XMP key list (covered by P4-004). Acceptance criteria AC-1 through AC-16 map correctly to the tasks. `$EC` shell variable capture for subprocess exit codes is correct bash.

---

## Summary

**Total: 12 patches — 6 Critical, 5 Important, 1 Polish.**

**Top 3 by severity:**

1. **P4-001 🔴 Task 10** — `post_process/pipeline.py` imports `mdpdf.security.watermark` and `mdpdf.security.xmp`, neither of which exists. Every test in `test_pipeline.py` that imports `PostProcessPipeline` will fail with `ModuleNotFoundError` before any assertion runs. This is the single most impactful defect: it blocks Tasks 10–12 and all integration tests.
2. **P4-002 🔴 Task 12** — Audit integration uses `from mdpdf.audit import AuditLogger` (wrong path) and calls `self._audit.log_event(...)` (method doesn't exist — `AuditLogger` has `log_start`/`log_complete`/`log_error`). The entire `TestPipelineAudit` suite errors immediately.
3. **P4-004 🔴 Task 20** — `_REQUIRED_XMP_KEYS` uses 12 camelCase and largely fictitious key names that do not match spec §5.3 or the Task 4 implementation. The integration test AC-2 ("all 12 XMP keys present") would fail for every key, defeating the entire L2 acceptance gate.
