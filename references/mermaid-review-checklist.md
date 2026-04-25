# Mermaid & fenced blocks — review checklist (md-to-pdf)

Last reviewed: 2026-04-24 (CJK tests added). Use with [`scripts/md_to_pdf.py`](../scripts/md_to_pdf.py).

| Dimension | Status | Notes |
|-----------|--------|--------|
| Parsing: extended lang tags (`mermaid {.opts}`, `mermaid{...}`) | Pass | `normalize_fence_lang()` — first token; brace strip |
| Parsing: empty Mermaid body | Pass | In-PDF `[Mermaid] Empty diagram block…` |
| Parsing: unclosed fence (EOF) | Pass | `consume_fenced_code_block` reads to EOF (unchanged) |
| Parsing: indented ``` fences | Pass | `strip()` on opening line (unchanged) |
| BOM on first line | Pass | Input `.md` read with `utf-8-sig` (strips UTF-8 BOM before parsing) |
| Content: non-Mermaid ``` blocks | Pass | Shaded `Code (lang)` blocks; `MDPDF_FENCED_MAX_*` truncation note |
| Content: Mermaid + code same doc | Pass | Fixture `fenced-mermaid-smoke.md` |
| Pipeline: PNG scaling / max height | Pass | `MERMAID_MAX_HEIGHT_PT` + preset `-w/-H` |
| Pipeline: KeepTogether | Pass | When scaled block height (with optional caption) is below ~45% of body height; no user switch — automatic |
| Pipeline: caption | Pass | Default: centered, 50% body size, muted; YAML `title` or ATX heading above fence |
| Fonts: Noto CSS + JSON | Pass | When TTFs present; verbose logs `-C`/`-c` |
| Fonts: missing TTF | Pass | Falls back to browser fonts; stderr note when verbose |
| Fonts: `file:` in containers | Known limitation | Local `@font-face` URIs may be blocked; mount skill path or accept fallback |
| Errors: mmdc / Puppeteer | Pass | Meta paragraphs + `MDPDF_MERMAID_VERBOSE` |
| Errors: oversize Mermaid | Pass | `MDPDF_MERMAID_MAX_CHARS` → `too_large` message in PDF |
| Errors: npx-only hint | Pass | `no_mmdc` message mentions `MDPDF_MERMAID_NPX` |
| Resource: timeouts | Pass | 180s / 300s (H preset) |
| Resource: Chromium | Documented | User content runs headless Chromium via mmdc |
| Tests | Pass | `pytest` on `tests/` — fences/Mermaid + `test_md_to_pdf_cjk.py` (CJK fixture / merged headings). `MDPDF_SKIP_MERMAID_TEST=1` force-skips mmdc integration |

## Known limitations (deferrals)

- **PDF/UA / `/Alt` on diagram images:** PNG embeds are not tagged for screen readers beyond optional visible caption.
- **SVG or vector Mermaid:** Not implemented; raster PNG only.
- **Per-diagram preset in fence:** Not implemented; use global `--mermaid-E|S|H` or `MDPDF_MERMAID_PRESET`.

## Acceptance mapping (plan §9)

- **A1–A7:** Satisfied for this revision; see table above. Re-run this checklist after any change to `render_mermaid_to_png` or fenced-block parsing.
