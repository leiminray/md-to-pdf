# UAT fixtures (ReportLab)

Small Markdown files for regression runs of [`scripts/md_to_pdf.py`](../scripts/md_to_pdf.py). **Fixtures in this folder are English by default**; use `uat-zh.md` for Simplified Chinese body and diagram labels.

- `uat-en.md` — English body
- `uat-zh.md` — Simplified Chinese (uses `../fonts/NotoSansSC-*.ttf`)
- `uat-table.md` — pipe table
- `mermaid-noto-presets.md` — Mermaid flowchart / sequence / state (English; mmdc + Noto smoke)
- `fenced-mermaid-smoke.md` — Python/text fences, noisy Mermaid tag, empty Mermaid (`pytest` fixture)
- `uat-cjk.md` — CJK strict regression (mixed wrap, dates aligned with `uat-zh.md`, merged `#`/`##` line; `pytest`: `tests/test_md_to_pdf_cjk.py`)

**PDF output path:** If you **omit** `-o`, the CLI writes **`out/<same-stem-as-input>.pdf`** under this folder (the script ensures `fixtures/out/` exists). You can still override with `-o` (relative paths are resolved from your **current working directory**).

```bash
# From repo root — writes fixtures/out/uat-en.pdf
.../md_to_pdf.py .cursor/skills/md-to-pdf/fixtures/uat-en.md

# Explicit path (relative to cwd)
.../md_to_pdf.py .cursor/skills/md-to-pdf/fixtures/uat-en.md -o .cursor/skills/md-to-pdf/fixtures/out/uat-en.pdf
```

Root-level `*.pdf` next to a fixture `.md` should not appear when using the default output; such files are **gitignored** (see [`.gitignore`](.gitignore)). Canonical PDFs for UAT live under **`out/`** per [`references/validation-scenarios.md`](../references/validation-scenarios.md).
