# md-to-pdf — validation scenarios and UAT

Scenario IDs: **M** (mechanical), **B** (ReportLab E2E), **R** (scope), **U** (Cursor). Aligns with ids-create-skill / `skill-spec.md` and repo handbook.

**Regression commands (repo root)**

Use the **skill venv** when present; otherwise any Python 3 with deps per `requirements-md-pdf.txt`.

```bash
python3 .cursor/skills/ids-create-skill/scripts/quick_validate.py .cursor/skills/md-to-pdf
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py .cursor/skills/md-to-pdf/fixtures/uat-en.md -o .cursor/skills/md-to-pdf/fixtures/out/uat-en.pdf
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py .cursor/skills/md-to-pdf/fixtures/uat-zh.md -o .cursor/skills/md-to-pdf/fixtures/out/uat-zh.pdf
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py .cursor/skills/md-to-pdf/fixtures/uat-table.md -o .cursor/skills/md-to-pdf/fixtures/out/uat-table.pdf
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py .cursor/skills/md-to-pdf/fixtures/mermaid-noto-presets.md -o .cursor/skills/md-to-pdf/fixtures/out/mermaid-noto.pdf --mermaid-S
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py .cursor/skills/md-to-pdf/fixtures/fenced-mermaid-smoke.md -o .cursor/skills/md-to-pdf/fixtures/out/fenced-smoke.pdf --no-mermaid
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py .cursor/skills/md-to-pdf/fixtures/uat-cjk.md -o .cursor/skills/md-to-pdf/fixtures/out/uat-cjk.pdf --no-mermaid
```

**CJK / merged-heading tests:** `pytest .cursor/skills/md-to-pdf/tests/test_md_to_pdf_cjk.py`.

**TOC internal links + watermark:** `pytest .cursor/skills/md-to-pdf/tests/test_md_to_pdf_toc_watermark.py`. Manual: `--watermark` — org/brand from `compliance.md` only, else user-only string; no `MD_PDF_COMPANY`; open PDF and confirm gray diagonal text **under** body text.

Fixtures: [`../fixtures/`](../fixtures/). PDF outputs under `fixtures/out/` are gitignored.

**Mermaid / fenced blocks:** [`mermaid-review-checklist.md`](mermaid-review-checklist.md); automated checks: `pip install -r ../requirements-dev.txt` then `pytest ../tests/` (includes `test_md_to_pdf_fences.py`, `test_md_to_pdf_cjk.py`).

---

## UAT result table (sign-off)

| 场景 ID | Pass / Fail / N/A | 证据（命令 / 日志 / 审查） | 执行人 / 日期 |
|---------|-------------------|---------------------------|---------------|
| **M1** | **Pass** | `quick_validate.py` exit 0, `Skill is valid!` | CGO Agent |
| **M2** | **Pass** | `md_to_pdf.py`; `fonts/NotoSansSC-*.ttf`; `company_assets/` if used | CGO Agent |
| **M3** | **Pass** | `agent-skills-handbook.md` row `md-to-pdf` | CGO Agent |
| **M4** | **Pass** | Onboarding checklist (handbook) | CGO Agent |
| **B1** | **Pass** | `fixtures/out/uat-en.pdf`; pypdf text extract | CGO Agent |
| **B2** | **Pass** | `fixtures/out/uat-zh.pdf`; CJK from skill `fonts/` | CGO Agent |
| **B3** | **Pass** | `fixtures/out/uat-table.pdf`; table text | CGO Agent |
| **B4** | **Pass** | Import guard → `README.md` + `requirements-md-pdf.txt` | CGO Agent |
| **B5** | **Pass** | Script prints `Wrote: …` one line | CGO Agent |
| **R1–R3** | **Pass** | `SKILL.md`: ReportLab only; no product routing | Static |
| **R4** | **Pass** | YAML keywords + Live prompts | CGO Agent |
| **U1** | **Pass** | Skill folder + frontmatter; `/` after reload | CGO Agent |
| **U2** | **N/A** | — | — |
| **U3** | **Pass** | YAML ↔ body | CGO Agent |

**Gate:** All non-**N/A** rows **Pass** → UAT **通过**.

---

## Live Cursor prompts (R4 / U1)

1. “Export `.cursor/skills/md-to-pdf/fixtures/uat-en.md` to PDF.”
2. “Convert this Markdown file to PDF using ReportLab.”
3. “Batch render these `.md` files to PDF.”

---

## Handbook onboarding checklist (M4 detail)

- [x] YAML `name` = folder `md-to-pdf`
- [x] `description` valid per `skill-spec.md`
- [x] No Claude Code paths / wrong tool names
- [x] Paths exist (M2)
- [x] Referenced paths in `SKILL.md` / `references/` exist where cited

---

## Change log (this file only)

- **2026-04-24** — `uat-cjk.md` regression command; `pytest tests/test_md_to_pdf_cjk.py`.
- **2026-04-24** — Mermaid pytest: auto-run when `mmdc` on `PATH`; `MDPDF_SKIP_MERMAID_TEST` to force-skip in CI.
- **2026-04-22** — Added [`release-checklist.md`](release-checklist.md) for versioned releases; input Markdown uses `utf-8-sig` (BOM-safe).
- **2026-04-22** — Script **`md_to_pdf.py`** (renamed from `md_to_pdf_reportlab.py`).
- **2026-04-22** — Removed Path A (Pandoc); scenario set M/B/R/U only.
- **2026-04-22** — Skill-local `scripts/`, `fonts/`, `fixtures/`; regression commands updated.
- **2026-04-22** — Import guard, frontmatter metadata (earlier).
