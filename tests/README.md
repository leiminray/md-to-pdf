# md-to-pdf — internal tests

For **maintainers / CI** only. End-user-facing usage stays in [`../SKILL.md`](../SKILL.md) and [`../README.md`](../README.md).

## Run

From repository root (skill venv recommended):

```bash
.cursor/skills/md-to-pdf/.venv/bin/pip install -r .cursor/skills/md-to-pdf/requirements-dev.txt
.cursor/skills/md-to-pdf/.venv/bin/python -m pytest .cursor/skills/md-to-pdf/tests/ -v
```

## Mermaid integration

`test_mermaid_renders_when_mmdc_available` runs when `mmdc` resolves on `PATH`; otherwise it **skips**. To force-skip (e.g. CI image without Node/Chromium):

```bash
MDPDF_SKIP_MERMAID_TEST=1 .cursor/skills/md-to-pdf/.venv/bin/python -m pytest .cursor/skills/md-to-pdf/tests/ -v
```

Review context: [`../references/mermaid-review-checklist.md`](../references/mermaid-review-checklist.md), [`../references/validation-scenarios.md`](../references/validation-scenarios.md).

## TOC bookmark map + watermark (unit)

[`test_md_to_pdf_toc_watermark.py`](test_md_to_pdf_toc_watermark.py) — pure-Python checks for `collect_bookmark_plain_to_key`, `lookup_toc_row_bookmark_key`, and `resolve_watermark_text()`.

## CJK / line breaking (manual)

[`test_md_to_pdf_cjk.py`](test_md_to_pdf_cjk.py) + [`../fixtures/uat-cjk.md`](../fixtures/uat-cjk.md) cover text presence and merged-heading split. **Latin word boundaries** (e.g. `Alex Morgan` not broken mid-word) are not asserted in code: open `uat-cjk.pdf` and visually confirm wrapping in the long mixed paragraph and narrow table column.

## Header / footer vs body (fonts)

Body uses embedded **Noto Sans SC** when `fonts/NotoSansSC-*.ttf` are present. The **Generated:** stamp and pypdf footer band use **`theme.yaml`** / English **`compliance.md`**. Chinese dates in the fixture appear in **body/table**, not in that stamp.

**Future (product):** localized `Generated:` and CJK footer text would require theme + compliance changes and embedding a CJK-capable font in ReportLab / footer stamp paths (see [`../README.md`](../README.md)).
