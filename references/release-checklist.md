# md-to-pdf — release checklist

Use before tagging a skill version or publishing an internal “gold” revision.

## Automated

1. **Skill pack validation** (if `ids-create-skill` is in the repo):
   ```bash
   python3 .cursor/skills/ids-create-skill/scripts/quick_validate.py .cursor/skills/md-to-pdf
   ```
2. **Unit tests** (venv + dev deps; see [`tests/README.md`](../tests/README.md)):
   ```bash
   .cursor/skills/md-to-pdf/.venv/bin/pip install -r .cursor/skills/md-to-pdf/requirements-dev.txt
   .cursor/skills/md-to-pdf/.venv/bin/python -m pytest .cursor/skills/md-to-pdf/tests/
   ```
   (Includes `test_md_to_pdf_cjk.py` — CJK fixture, merged headings, Noto font probe.)
   - **Mermaid E2E** (`test_mermaid_renders_when_mmdc_available`) runs automatically when `mmdc` resolves on `PATH`; otherwise it is **skipped**. Requires a Chromium-class browser for Puppeteer.
   - To force-skip that test (e.g. CI image without Node): `MDPDF_SKIP_MERMAID_TEST=1 pytest …`

## Manual / UAT

- Run the regression block in [`validation-scenarios.md`](validation-scenarios.md) (including `mermaid-noto-presets.md` when Mermaid is enabled).
- Spot-check: `SKILL.md` frontmatter `version` matches the change log or release note you publish.
- Re-read [`mermaid-review-checklist.md`](mermaid-review-checklist.md) after any change to `render_mermaid_to_png` or fence parsing.

## Dependencies

- **Python:** `requirements-md-pdf.txt` — pin bumps deserve a short note in the release summary.
- **Mermaid:** `mmdc -V` should be **≥ 11** for Noto `--configFile` / `--cssFile` (see `ensure_mermaid_deps.py`).

## Ship

- Bump `version` in [`SKILL.md`](../SKILL.md).
- Commit with a conventional message; do not commit generated PDFs under `fixtures/out/`.
