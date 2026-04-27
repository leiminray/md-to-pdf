# Plan 3 (Renderers + Custom Flowables) — Review Patches

**Date:** 2026-04-27
**Patches against:** [`2026-04-27-md-to-pdf-v2.0-plan-3-renderers-and-flowables.md`](2026-04-27-md-to-pdf-v2.0-plan-3-renderers-and-flowables.md)
**Reviewer:** sophie.leiyixiao@gmail.com (cold review by independent subagent; Tasks 1–22 authored, none yet executed)
**Apply how:** patches are independent unless noted. Apply all, a subset, or skip — each carries its own rationale. Plan 3 source file is **not modified** by this document.

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
| P3-001 | 🔴 | 21 | `proc.output` — `subprocess.CompletedProcess` has no `.output` attribute |
| P3-002 | 🔴 | 17 | Dead variables `outline_iter` and `outline_by_id` in `_convert` — ruff F841 |
| P3-003 | 🔴 | 19 | `_prerender_assets`: all imports inline + `RendererError` imported but unused — F401 + convention |
| P3-004 | 🟡 | 9, 10, 11 | Mermaid cache key omits `theme` — violates spec §2.1.4 contract |
| P3-005 | 🟡 | 9 | `KrokiMermaidRenderer`: `httpx.HTTPError` (including `ConnectError`) mapped to `MERMAID_TIMEOUT` — wrong code |
| P3-006 | 🟡 | 15 | Table width hardcodes `210 mm` (A4) — breaks Letter / B5 / Legal brands |
| P3-007 | 🟡 | 17 | Inline import of `_inline_to_plain` inside `_convert` method body — P2-006 pattern |
| P3-008 | 🟡 | 7 | Duplicate inline `mm` import inside `_convert_block` — P2-006 pattern (two imports, two aliases) |
| P3-009 | 🟢 | 4 | `FencedCodeCard._build`: inline `from xml.sax.saxutils import escape` inside method body |
| P3-010 | 🟢 | 19 | `_prerender_assets` dead parameter `render_id` — never used in function body |

---

## P3-001 🔴 — `proc.output` is not an attribute of `subprocess.CompletedProcess`

**Location:** Task 21 Step 3 (`tests/integration/test_renderers_integration.py`), `test_acceptance_5_mermaid_bomb_rejected` and `test_acceptance_6_mermaid_xss_rejected`.

### Problem

```python
# test_acceptance_5_mermaid_bomb_rejected (line ~3960)
assert "MERMAID_RESOURCE_LIMIT" in proc.stderr or "MERMAID_RESOURCE_LIMIT" in proc.output

# test_acceptance_6_mermaid_xss_rejected (line ~3970)
assert "MERMAID_INVALID_SYNTAX" in proc.stderr or "MERMAID_INVALID_SYNTAX" in proc.output
```

`subprocess.CompletedProcess` has `.stdout` and `.stderr`, not `.output`. Accessing `.output` raises `AttributeError: 'CompletedProcess' object has no attribute 'output'` at runtime. The error message from `md-to-pdf` goes to stderr (per `cli.py`'s `click.echo(..., err=True)` pattern), so the correct check is `.stderr` only.

Note also: the `mock_mermaid_pure` fixture uses `monkeypatch`, which patches only the current process. For these two subprocess-based tests the fixture is unnecessary — the lint rejection fires before renderer dispatch, so the tests would pass without any mermaid mock. The fixture adds test-dependency coupling with no benefit.

### Patched code

```python
# Before (test_acceptance_5)
assert "MERMAID_RESOURCE_LIMIT" in proc.stderr or "MERMAID_RESOURCE_LIMIT" in proc.output

# After
assert "MERMAID_RESOURCE_LIMIT" in proc.stderr

# Before (test_acceptance_6)
assert "MERMAID_INVALID_SYNTAX" in proc.stderr or "MERMAID_INVALID_SYNTAX" in proc.output

# After
assert "MERMAID_INVALID_SYNTAX" in proc.stderr
```

Remove `mock_mermaid_pure` from both test signatures (the decorator/fixture is harmless but misleading):

```python
# Before
def test_acceptance_5_mermaid_bomb_rejected(tmp_path: Path, mock_mermaid_pure):
def test_acceptance_6_mermaid_xss_rejected(tmp_path: Path, mock_mermaid_pure):

# After
def test_acceptance_5_mermaid_bomb_rejected(tmp_path: Path):
def test_acceptance_6_mermaid_xss_rejected(tmp_path: Path):
```

### Rationale

`AttributeError` on `proc.output` will surface as an error (not a failure) in pytest, masking the actual acceptance test. The error message the CLI writes to stderr is already captured by `capture_output=True, text=True` in `subprocess.run`.

---

## P3-002 🔴 — Dead variables `outline_iter` and `outline_by_id` in `_convert` — ruff F841

**Location:** Task 17 Step 4 (`src/mdpdf/render/engine_reportlab.py`, modified `_convert` method).

### Problem

```python
    def _convert(self, document: Document) -> list[Flowable]:
        body = self._brand_styles.paragraph_styles["Body"]
        out: list[Flowable] = []
        outline_iter = iter(document.outline)          # ← assigned, never used
        # Build a map plain_text → OutlineEntry for matching headings to bookmarks
        # (multiple headings may share text; use a counter to disambiguate)
        outline_by_id: dict[str, OutlineEntry] = {e.bookmark_id: e for e in document.outline}   # ← assigned, never used
        consumed: set[str] = set()
        ...
```

`outline_iter` is created but never iterated; `outline_by_id` is built but the lookup inside `_next_entry_for` iterates `document.outline` directly. Ruff F841 (`local variable is assigned to but never used`) will flag both. Additionally, `outline_by_id` constructs a complete dict of every entry, a wasted allocation that becomes noisy in mypy's unused-variable pass.

### Patched code

```python
    def _convert(self, document: Document) -> list[Flowable]:
        body = self._brand_styles.paragraph_styles["Body"]
        out: list[Flowable] = []
        consumed: set[str] = set()

        def _next_entry_for(plain: str) -> OutlineEntry | None:
            for entry in document.outline:
                if entry.plain_text == plain and entry.bookmark_id not in consumed:
                    consumed.add(entry.bookmark_id)
                    return entry
            return None

        for node in document.children:
            flowables = self._convert_block(node, body)
            if isinstance(node, Heading) and flowables:
                plain = _inline_to_plain(node.children)
                entry = _next_entry_for(plain)
                if entry is not None:
                    flowables[0] = HeadingBookmark(inner=flowables[0], entry=entry)
            out.extend(flowables)
        return out
```

(The `_inline_to_plain` import issue is addressed separately in P3-007.)

### Rationale

Two dead variables. Both will be flagged by `ruff check` with F841, failing the `Task 22` acceptance sweep. Removing them makes the code match its actual behaviour.

---

## P3-003 🔴 — `_prerender_assets`: inline imports + unused `RendererError` import (F401 + convention)

**Location:** Task 19 Step 3 (`src/mdpdf/pipeline.py`, new `_prerender_assets` method).

### Problem

```python
    def _prerender_assets(
        self, document: Document, request: "RenderRequest", render_id: str,
    ) -> None:
        """Walk AST, eagerly render Mermaid and Image assets to populate cache."""
        from mdpdf.markdown.ast import Image as ASTImage, MermaidBlock
        from mdpdf.renderers.base import RenderContext
        from mdpdf.renderers.image import ImageRenderer
        from mdpdf.renderers.mermaid_chain import select_mermaid_renderer
        from mdpdf.errors import RendererError        # ← imported but never used

        ctx = RenderContext(...)

        for node in document.children:
            if isinstance(node, MermaidBlock):
                renderer = select_mermaid_renderer(preference="auto", ctx=ctx)
                renderer.render(node.source, ctx)
            elif isinstance(node, ASTImage):
                ImageRenderer().render(node, ctx)
```

Issues:

1. **All five imports are inline** inside the method body, violating the module-top-imports convention enforced since P2-006/P2-007. These are pure domain imports with no import-cycle justification.
2. **`RendererError` is imported but never referenced** in the body — ruff F401 will fail. It appears to have been left over from a draft that would catch and suppress renderer failures (a useful feature but not implemented).

### Patched code

Move all four used imports to the module top of `pipeline.py`, alongside the existing `mdpdf.*` imports:

```python
# Add to module-top imports in pipeline.py (alongside existing mdpdf.* imports):
from mdpdf.markdown.ast import Image as ASTImage, MermaidBlock
from mdpdf.renderers.base import RenderContext as RendererContext
from mdpdf.renderers.image import ImageRenderer
from mdpdf.renderers.mermaid_chain import select_mermaid_renderer
```

Note: use an alias (`RendererContext`) or a different name to avoid shadowing, since `pipeline.py` already uses `RenderContext` as a local variable name at some call sites. Alternatively keep `RenderContext` if it isn't already imported under that name.

Remove the inline imports from `_prerender_assets` entirely. Remove the `from mdpdf.errors import RendererError` line (not used in this method).

### Rationale

Same pattern as P2-006/P2-007. Ruff F401 will fail the Task 22 sweep on `RendererError` alone. The inline imports also mislead readers into thinking there's an import-cycle reason for the placement.

---

## P3-004 🟡 — Mermaid cache key omits `theme` — violates spec §2.1.4

**Location:** Task 9 (`src/mdpdf/renderers/mermaid_kroki.py`), Task 10 (`src/mdpdf/renderers/mermaid_puppeteer.py`), Task 11 (`src/mdpdf/renderers/mermaid_pure.py`).

### Problem

Foundation spec §2.1.4 states:

> Cache key: `sha256(source + theme + renderer_version)`.

All three renderers omit `theme` from the cache key:

```python
# mermaid_kroki.py
cache_key = f"{_RENDERER_VERSION}|{self.base_url}|{source}"

# mermaid_puppeteer.py
cache_key = f"{_RENDERER_VERSION}|{source}"

# mermaid_pure.py
cache_key = f"{_RENDERER_VERSION}|{source}"
```

If a brand pack specifies a Mermaid theme in Plan 4 (`brand.compliance.mermaid_theme`), a cache entry keyed without theme could be re-used for a diagram rendered under a different theme, producing incorrect visual output silently. The `theme` slot should be included now (as an empty string or `"default"` placeholder) so the cache key format is stable when Plan 4 wires the actual theme.

### Patched code

Define a module-level constant for the theme placeholder and include it in the key:

```python
# In each mermaid renderer (kroki / puppeteer / pure):
_THEME = "default"  # Plan 4 will wire brand.compliance.mermaid_theme here

# mermaid_kroki.py
cache_key = f"{_RENDERER_VERSION}|{_THEME}|{self.base_url}|{source}"

# mermaid_puppeteer.py
cache_key = f"{_RENDERER_VERSION}|{_THEME}|{source}"

# mermaid_pure.py
cache_key = f"{_RENDERER_VERSION}|{_THEME}|{source}"
```

When Plan 4 lands `mermaid_theme`, replace `_THEME` with a parameter threaded through `RenderContext`.

### Rationale

The spec is explicit on the three-component key. Building the wrong key now means Plan 4 will need to invalidate or rekey all existing cache entries. The one-word addition costs nothing.

---

## P3-005 🟡 — `KrokiMermaidRenderer`: `httpx.HTTPError` mapped to `MERMAID_TIMEOUT` — wrong code

**Location:** Task 9 Step 3 (`src/mdpdf/renderers/mermaid_kroki.py`), error handling block.

### Problem

```python
        except httpx.TimeoutException as e:
            raise RendererError(
                code="MERMAID_TIMEOUT",
                user_message=f"kroki request timed out after {_TIMEOUT_S}s",
            ) from e
        except httpx.HTTPError as e:
            raise RendererError(
                code="MERMAID_TIMEOUT",            # ← wrong code for a network failure
                user_message=f"kroki request failed: {e}",
            ) from e
```

`httpx.HTTPError` is the base class for all httpx exceptions including `ConnectError`, `RemoteProtocolError`, and non-timeout network failures. Mapping a `ConnectError` (Kroki not reachable) to `MERMAID_TIMEOUT` misleads users and operators: the spec defines `MERMAID_RENDERER_UNAVAILABLE` for the "renderer not reachable" case and `MERMAID_TIMEOUT` for the "took too long" case.

The unit test `test_render_failure_raises` uses `httpx.ConnectError` and asserts `ei.value.code == "MERMAID_TIMEOUT" or "kroki" in ei.value.user_message.lower()` — the `or` branch lets this pass, masking the wrong code.

### Patched code

```python
        except httpx.TimeoutException as e:
            raise RendererError(
                code="MERMAID_TIMEOUT",
                user_message=f"kroki request timed out after {_TIMEOUT_S}s",
            ) from e
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise RendererError(
                code="MERMAID_RENDERER_UNAVAILABLE",
                user_message=f"kroki unreachable at {self.base_url}: {e}",
            ) from e
        except httpx.HTTPError as e:
            raise RendererError(
                code="MERMAID_TIMEOUT",
                user_message=f"kroki HTTP error: {e}",
            ) from e
```

Update the test to match:

```python
# Before (test_render_failure_raises)
    assert ei.value.code == "MERMAID_TIMEOUT" or "kroki" in ei.value.user_message.lower()

# After
    assert ei.value.code == "MERMAID_RENDERER_UNAVAILABLE"
    assert "kroki" in ei.value.user_message.lower()
```

### Rationale

The spec defines these as distinct failure modes because operators respond to them differently: `MERMAID_TIMEOUT` → increase `_TIMEOUT_S`; `MERMAID_RENDERER_UNAVAILABLE` → check KROKI_URL or start container. Conflating them makes on-call debugging harder.

---

## P3-006 🟡 — Table width hardcodes `210 mm` (A4) — wrong for Letter / B5 / Legal brands

**Location:** Task 15 Step 4 (`src/mdpdf/render/engine_reportlab.py`, `ASTTable` dispatch in `_convert_block`).

### Problem

```python
        if isinstance(node, ASTTable):
            ...
            available_pt = (210 - self._brand_styles.left_margin - self._brand_styles.right_margin) * mm
            widths = compute_column_widths(cells_text, available_width_pt=available_pt)
```

`210` is the width of an A4 page in millimetres. A brand using `page_size: Letter` (215.9 mm), `B5` (176 mm), or `Legal` (215.9 mm) will get wrong column widths — either too narrow (B5 tables starve) or slightly too wide (Letter/Legal columns overflow the margins).

`BrandStyles.page_size` is the string `"A4"`, `"Letter"`, etc. The engine already has `_PAGE_SIZES` that maps these to ReportLab point tuples; the page width in points is at `_PAGE_SIZES[page_size][0]`.

### Patched code

```python
        if isinstance(node, ASTTable):
            ...
            # Use the actual page width for the current brand (default A4 = 210mm).
            _page_w_pt = _PAGE_SIZES.get(self._brand_styles.page_size, A4)[0]
            _margins_pt = (self._brand_styles.left_margin + self._brand_styles.right_margin) * mm
            available_pt = _page_w_pt - _margins_pt
            widths = compute_column_widths(cells_text, available_width_pt=available_pt)
```

`_PAGE_SIZES` and `A4` are already imported at module top in `engine_reportlab.py`.

### Rationale

All four supported page sizes (A4, Letter, B5, Legal) are exercised by brand integration tests. A B5-branded document with a 6-column table will see 176 mm − margins vs. 210 mm − margins — a 34 mm (≈96 pt) error, enough to cause ReportLab layout failures for wide tables.

---

## P3-007 🟡 — `_convert` imports `_inline_to_plain` inline inside method body — P2-006 pattern

**Location:** Task 17 Step 4 (`src/mdpdf/render/engine_reportlab.py`, modified `_convert` method).

### Problem

```python
        for node in document.children:
            flowables = self._convert_block(node, body)
            if isinstance(node, Heading) and flowables:
                from mdpdf.markdown.transformers.collect_outline import _inline_to_plain   # ← inline
                plain = _inline_to_plain(node.children)
```

Inline import inside a hot loop (called once per heading, per render). No import-cycle reason — `engine_reportlab.py` already imports from `mdpdf.markdown.ast`; importing from `mdpdf.markdown.transformers` creates no cycle. This import fires on every heading rendering pass (Python caches the module, but `importlib` still does a sys.modules dict lookup each time).

Additionally, `_inline_to_plain` is a private function. While importing privates across modules is not a lint error, it does mean `collect_outline.py`'s internal refactors silently break `engine_reportlab.py` with no static warning.

### Patched code

Move the import to module top of `engine_reportlab.py`:

```python
# At module top (alongside other mdpdf.markdown imports):
from mdpdf.markdown.transformers.collect_outline import _inline_to_plain
```

Remove the inline import line from inside `_convert`.

### Rationale

Consistent with P2-006/P2-007 — no inline imports in src/ unless there is a documented import-cycle reason. The loop overhead from repeated `sys.modules` lookups is negligible but the style violation compounds.

---

## P3-008 🟡 — Task 7 engine code has two inline `mm` imports inside `_convert_block` — P2-006 pattern

**Location:** Task 7 Step 3 (`src/mdpdf/render/engine_reportlab.py`, `ASTImage` dispatch block in `_convert_block`).

### Problem

```python
        if isinstance(node, ASTImage):
            ctx = RenderContext(...)
            result = ImageRenderer().render(node, ctx)
            # Render at 72 dpi → 1px = 1pt
            from reportlab.lib.units import mm
            max_width_mm = 170  # leave margin
            from reportlab.lib.units import mm as _mm
            scale = min(1.0, (max_width_mm * _mm) / result.width_px)
            return [RLImage(
                str(result.path),
                width=result.width_px * scale,
                height=result.height_px * scale,
            )]
```

Two inline imports: `from reportlab.lib.units import mm` followed immediately by `from reportlab.lib.units import mm as _mm`. The first is shadowed by the second before it is used. The plan's own checklist note says `(Hoist any duplicate imports above to module top per anti-pattern checklist.)` but the code does not do this.

`mm` is already imported at module top in `engine_reportlab.py` (line 15). Both inline imports are redundant.

### Patched code

```python
# Before
        if isinstance(node, ASTImage):
            ctx = RenderContext(...)
            result = ImageRenderer().render(node, ctx)
            # Render at 72 dpi → 1px = 1pt
            from reportlab.lib.units import mm
            max_width_mm = 170  # leave margin
            from reportlab.lib.units import mm as _mm
            scale = min(1.0, (max_width_mm * _mm) / result.width_px)
            ...

# After — both inline import lines deleted; use the module-top `mm`
        if isinstance(node, ASTImage):
            ctx = RenderContext(...)
            result = ImageRenderer().render(node, ctx)
            max_width_mm = 170  # leave margin; 1px = 1pt at 72dpi
            scale = min(1.0, (max_width_mm * mm) / result.width_px)
            return [RLImage(
                str(result.path),
                width=result.width_px * scale,
                height=result.height_px * scale,
            )]
```

### Rationale

`mm` is already at module top. The two inline imports together will be flagged by ruff's `E401`/`E402` rules and duplicate-import detection. The second one (`as _mm`) shadows the first before it is used — effectively dead code.

---

## P3-009 🟢 — `FencedCodeCard._build` has inline `from xml.sax.saxutils import escape`

**Location:** Task 4 Step 3 (`src/mdpdf/render/flowables.py`, `FencedCodeCard._build` method, line ~896).

### Problem

```python
    def _build(self) -> None:
        ...
        for line_frags in self.result.lines:
            html_parts: list[str] = []
            for frag in line_frags:
                from xml.sax.saxutils import escape    # ← inline import inside nested loop
                html_parts.append(...)
```

`xml.sax.saxutils.escape` is a stdlib utility with no import-cycle risk. It is called once per fragment inside a doubly-nested loop. The import is cached by Python after the first call, but its placement inside the loop body is inconsistent with the project's P2-006/P2-007 lessons.

### Patched code

Add to the module-level imports in `flowables.py`:

```python
from xml.sax.saxutils import escape
```

Remove the inline import line from `_build`.

### Rationale

Consistent with the project-wide "module-top imports" rule. One-line addition, no behavior change.

---

## P3-010 🟢 — `_prerender_assets` dead parameter `render_id` — never used in body

**Location:** Task 19 Step 3 (`src/mdpdf/pipeline.py`, `_prerender_assets` method signature).

### Problem

```python
    def _prerender_assets(
        self, document: Document, request: "RenderRequest", render_id: str,   # ← render_id unused
    ) -> None:
```

`render_id` is accepted but never referenced inside the function body. Pyright/mypy's `--strict` mode (with `--warn-unused-ignores` and the equivalent ARG002 rule) flags unused method parameters in class methods when they don't form an interface. Ruff B006/ARG002 may also flag this depending on configuration.

The intent was presumably to thread `render_id` into error constructors (matching the P2-010 Option A pattern). Plan 3's `_prerender_assets` doesn't raise `RendererError` itself — it lets renderer exceptions propagate uncaught — so there is currently no site to attach `render_id` to.

### Patched code

**Option A (preferred — adds traceability):** wrap the renderer calls and attach `render_id` to propagated errors:

```python
    def _prerender_assets(
        self, document: Document, request: RenderRequest, render_id: str,
    ) -> None:
        ...
        for node in document.children:
            if isinstance(node, MermaidBlock):
                try:
                    renderer = select_mermaid_renderer(preference=request.mermaid_renderer, ctx=ctx,
                                                       kroki_url_override=request.kroki_url)
                    renderer.render(node.source, ctx)
                except RendererError as e:
                    if e.render_id is None:
                        e.render_id = render_id
                    raise
```

**Option B (simpler — remove the dead parameter):**

```python
    def _prerender_assets(
        self, document: Document, request: RenderRequest,
    ) -> None:
        ...

# Update call site:
self._prerender_assets(document, request)
```

### Rationale

Option A preferred — consistent with P2-010 Option A pattern already adopted for `_resolve_brand`. Either fix removes the dead parameter that ruff/pyright would flag.

---

## Apply Order & Independence

All 10 patches are independent. P3-003 and P3-010 share `pipeline.py` — apply together. P3-002 and P3-007 share `engine_reportlab.py` — apply together for a single commit. Suggested order:

1. **P3-001** (proc.output → proc.stderr) — touches `test_renderers_integration.py` only.
2. **P3-002 + P3-007** (dead vars + inline import in engine) — both touch `engine_reportlab.py`.
3. **P3-003 + P3-010** (inline imports in pipeline + dead render_id) — both touch `pipeline.py`.
4. **P3-004** (cache key + theme) — touches `mermaid_kroki.py`, `mermaid_puppeteer.py`, `mermaid_pure.py`.
5. **P3-005** (Kroki error code) — touches `mermaid_kroki.py` + `test_mermaid_kroki.py`.
6. **P3-006** (table width page-size) — touches `engine_reportlab.py`.
7. **P3-008** (duplicate inline mm) — touches `engine_reportlab.py`.
8. **P3-009** (xml.sax inline) — touches `flowables.py`.

Recommended commit messages:

```
fix(test): replace proc.output with proc.stderr in mermaid acceptance tests (P3-001)
fix(render): remove dead outline_iter/outline_by_id variables in _convert (P3-002)
chore(render): hoist _inline_to_plain import to module top in engine (P3-007)
chore(pipeline): hoist renderer imports to module top; remove unused RendererError import (P3-003)
chore(pipeline): thread render_id into _prerender_assets RendererError propagation (P3-010)
fix(renderers): add theme slot to mermaid cache key per spec §2.1.4 (P3-004)
fix(renderers): map ConnectError to MERMAID_RENDERER_UNAVAILABLE not MERMAID_TIMEOUT (P3-005)
fix(render): use brand page_size for table available width (P3-006)
fix(render): remove duplicate inline mm imports in ASTImage dispatch (P3-008)
chore(render): hoist xml.sax.saxutils.escape to module top in flowables (P3-009)
```

## Patch Acceptance Bar

After all 10 patches applied:

- `proc.output` no longer appears in any test file.
- `ruff check src/ tests/` passes with no F841, F401, or E401 findings.
- `mypy --strict src/mdpdf` passes with no unused-variable or unresolved-name findings.
- All three mermaid renderers produce cache keys of the form `<version>|<theme>|<source>` (or `<version>|<theme>|<base_url>|<source>` for Kroki).
- `KrokiMermaidRenderer` returns `MERMAID_RENDERER_UNAVAILABLE` for `ConnectError`, `MERMAID_TIMEOUT` only for `TimeoutException`.
- Table column widths respect the brand's `page_size` (A4 / Letter / B5 / Legal).
- All Plan 1 + Plan 2 acceptance criteria still hold.

---

## Tasks Reviewed and Found Sound (no patch needed)

The following tasks were inspected and have no warranting issues:

- **Task 1 (Renderer ABC):** Sound. `RenderContext` is a frozen dataclass. `Renderer[SourceT, OutputT]` generic ABC is correctly defined; `Generic[SourceT, OutputT]` + `ABC` multiple inheritance is valid Python. Tests verify `TypeError` on direct instantiation.
- **Task 2 (DiskCache):** Sound. `path_for` correctly sha256-hashes the key. `put` correctly uses `atomic_write` for safe writes. `clear` only removes files (not subdirectories), which is the right behaviour for a flat cache root.
- **Task 3 (Pygments code renderer):** Sound. Token hierarchy walk (`cur.parent`) correctly handles Pygments' token tree. Truncation by `_max_lines()` / `_max_chars()` via env vars is compatible with v1.8.9's `MDPDF_FENCED_MAX_LINES` convention.
- **Task 5 (CodeFence → FencedCodeCard dispatch):** Sound. `RenderContext` construction in the engine (with hardcoded `cache_root=Path.home()`) is intentional for the Plan 3 walking skeleton; Plan 4 will thread the full context. The accent extraction via `.hexval()` with `hasattr` fallback is defensive and correct.
- **Task 6 (Image renderer):** Sound. PIL `img.resize()` inside the `with` block is correct — PIL `resize()` does NOT operate in-place (unlike `thumbnail()`), it returns a new image. `w, h` are captured from the resized image before the context exits. The no-resize code path exits after the `with` block, where `w, h` are still in scope.
- **Task 8 (Mermaid input lint):** Sound. Arrow-count node estimation (`arrow_count * 2`) is a documented conservative upper bound. All five `_PATTERNS_BAD` regexes correctly target the documented XSS vectors. Exit codes match spec §5.5.
- **Task 10 (Puppeteer renderer):** Sound. `TempContext` is correctly used as a context manager (`.path` is the temp dir). Sandboxing flags match spec §5.5 (`--no-sandbox`, `--disable-features=NetworkService,Extensions`). `capture_output=True` + `check=False` is the correct pattern for subprocess error inspection.
- **Task 11 (Pure renderer):** Sound. Deterministic-mode rejection fires before `lint_mermaid_source`, which is correct (no point linting if we know we'll reject). `_import_mermaid()` returns the module object (or `None`), and `mermaid_mod.to_png(source)` matches the test mock's `_FakeMermaid.to_png` signature.
- **Task 12 (Chain selector):** Sound. Auto-selection priority (Kroki → Puppeteer → pure) matches spec §2.1.4. The `ctx.deterministic` guard in the `auto` branch correctly blocks pure when deterministic is requested. `_find_mmdc` and `_import_mermaid` are imported as module-level names from their respective modules (not inline).
- **Task 13 (MermaidImage + dispatch):** Sound. `KeepTogether` delegation in `MermaidImage` is the correct ReportLab pattern for wrapping a compound flowable. `drawOn` correctly delegates to `_inner.drawOn`.
- **Task 14 (CalloutBox + BlockQuote):** Sound. Row construction `[["", body_item] for body_item in self.body]` correctly maps each body flowable to the accent-column pattern used by `FencedCodeCard`. The guard `if not rows` catches empty blockquotes.
- **Task 16 (ListBlock → ListFlowable):** Sound. `ast_list_to_flowable` recurses for nested `ListBlock` children, using `RLListItem` correctly. `bulletType="1"` for ordered, `"bullet"` for unordered, matches ReportLab's API.
- **Task 17 (HeadingBookmark):** Sound (modulo P3-002/P3-007). `HeadingBookmark.drawOn` correctly calls `canvas.bookmarkPage` before `addOutlineEntry` (order matters for ReportLab's PDF writer). `level=self.entry.level - 1` is correct because `addOutlineEntry` uses 0-indexed depth while `OutlineEntry.level` is 1-indexed.
- **Task 18 (RendererError docstring):** Sound. The test correctly asserts against the docstring text. No new class hierarchy is introduced — all new codes are conventional string values on `RendererError`, consistent with the existing pattern.
- **Task 20 (CLI flags):** Sound. `RenderRequest` additions (`mermaid_renderer`, `kroki_url`, `allow_remote_assets`) are backwards-compatible (all have defaults). CLI test assertions avoid the `mix_stderr=False` pitfall. `click.Choice(["auto", "kroki", "puppeteer", "pure"])` correctly provides validation.
- **Task 21 (Integration fixtures + test):** Sound except for P3-001. Fixture image generation is idempotent. The `mock_mermaid_pure` fixture is correct for `test_acceptance_3` and `test_acceptance_11`/`test_acceptance_12` (which use the Python API directly). The Kroki skipif marker correctly uses `"KROKI_URL" not in os.environ`.
- **Tasks 22 (completion sweep):** Sound. Acceptance criteria count (15) is correct: criteria 1–12 are directly verified + criteria 13–15 are reflexive sweep gates. The criterion 4 caveat about Kroki requiring a container is documented.

---

## Summary

**Total: 10 patches — 3 Critical, 5 Important, 2 Polish.**

**Top 3 by severity:**

1. **P3-001 🔴 Task 21** — `proc.output` is not an attribute of `subprocess.CompletedProcess`. Tests `test_acceptance_5_mermaid_bomb_rejected` and `test_acceptance_6_mermaid_xss_rejected` will raise `AttributeError` at runtime, appearing as errors (not failures) in pytest and masking the acceptance gate.
2. **P3-002 🔴 Task 17** — Dead variables `outline_iter` and `outline_by_id` in `_convert`. Ruff F841 will fail the Task 22 acceptance sweep. The `outline_by_id` dict is built but the lookup function ignores it entirely — the code works around it by iterating `document.outline` directly, but the dead variable remains.
3. **P3-003 🔴 Task 19** — `_prerender_assets` has five inline imports plus one unused `RendererError` import. Ruff F401 will fail on `RendererError`; the inline pattern violates the P2-006/P2-007 convention enforced throughout the project.
