# UAT Fixture — CJK strict

English **structure and notes** (same pattern as `uat-en.md` / `uat-table.md`); **CJK literals** intentionally exercise `wordWrap="CJK"`, embedded Noto, Chinese dates, and merged ATX recovery.

**Coverage:** mixed zh/en wrapping, Chinese date **2026年4月24日** (aligned with `uat-zh.md` ISO `2026-04-24`), run-on `# Part A## Chapter B` → split, narrow table cells.

Latin contact sample: **Alex Morgan** (two-word English name; visual check: no mid-word break).

## Normal H2 (outline sanity)

Section for bookmark level checks.

### H3 sample

Long mixed paragraph: IDIMSUM (Hong Kong) Technology Company Limited 与 简体中文混排 — exercises ReportLab `wordWrap="CJK"` at Latin–Han boundaries; padding is repeated so wrapping occurs at A4 column width. **Alex Morgan** owns interface review; delivery by **2026年4月24日**.

## Merged heading split (reference)

The next line is a **single** source line `# Part A## Chapter B`; the pipeline splits it into H1 + H2 (`normalize_merged_atx_headings`).

# Part A## Chapter B

## Narrow table (wrap stress)

| Column | Details |
|--------|---------|
| Date | 2026年4月24日 |
| Mixed | Alex Morgan 与 中文混排长字段：上海北京深圳香港 IDIMSUM Phase2 |

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 0.1 | 2026年4月24日 | Fixture baseline |
