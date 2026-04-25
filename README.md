# md-to-pdf

> **v2.0 walking skeleton (alpha) is now available.** Plan 1 of the [v2.0 foundation refactor](docs/superpowers/specs/2026-04-26-md-to-pdf-v2.0-foundation-design.md) ships a minimal `mdpdf` Python package with end-to-end markdown → PDF rendering via the new architecture (markdown-it-py → AST → ReportLab → atomic write). Brand packs, watermarks, Mermaid, code highlighting, and the comprehensive UAT fixture land in plans 2–5.
>
> **Try v2.0a1:**
>
> ```bash
> python3 -m venv .venv-v2
> .venv-v2/bin/pip install -e ".[dev]"
> .venv-v2/bin/md-to-pdf tests/integration/fixtures/hello.md -o /tmp/hello.pdf
> ```
>
> **Status:** 77 tests green (ruff + mypy --strict clean). CJK input intentionally fails loudly with `FONT_NOT_INSTALLED` until Plan 2 ships the font manager — use the legacy v1.8.9 monolith below for CJK rendering in the meantime.
>
> The v1.8.9 instructions below remain authoritative for the existing `scripts/md_to_pdf.py` workflow until v2.x reaches feature parity (planned for Plan 5).

---

# md-to-pdf v1.8.9 — one-time setup (self-contained skill)

**Scripts**, **fonts** (OFL), and **venv** live under **`.cursor/skills/md-to-pdf/`**. One **ReportLab** path only — no Pandoc/TeX. Do not create a new venv per sandbox folder.

## 1. Virtual environment

From the **repository root**:

```bash
python3 -m venv .cursor/skills/md-to-pdf/.venv
.cursor/skills/md-to-pdf/.venv/bin/pip install -r .cursor/skills/md-to-pdf/requirements-md-pdf.txt
```

Use this venv for every Markdown → PDF run.

## 2. Mermaid (optional; same skill folder)

Mermaid is **not** installed by `pip`. After §1, check or bootstrap **`mmdc`** (from `@mermaid-js/mermaid-cli`) and a Chromium-class browser (Puppeteer, used by `mmdc`):

```bash
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/ensure_mermaid_deps.py
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/ensure_mermaid_deps.py --auto-install
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/ensure_mermaid_deps.py --auto-install --puppeteer-chrome
# macOS (Cursor): prefer headless-shell over full “chrome” — fewer SIGABRTs when mmdc runs
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/ensure_mermaid_deps.py --auto-install --puppeteer-headless-shell
```

- **Node.js LTS** must be on `PATH` before `--auto-install` (install from [nodejs.org](https://nodejs.org/) if the script says `node` is missing).
- If you skip this step: use `--no-mermaid` / `MDPDF_SKIP_MERMAID=1`, or set `MDPDF_MERMAID_NPX=1` at render time (uses `npx`, needs network).
- Full one-line narrative is in [`requirements-md-pdf.txt`](requirements-md-pdf.txt) (Step A + Step B).

## 3. Fonts (bundled)

**Noto Sans SC** TTF (SIL OFL) in **`fonts/`** — see [`fonts/README.md`](fonts/README.md).

## 4. Skill entry

- Procedure: [`SKILL.md`](SKILL.md)
- Font reference: [`references/fonts-licensing.md`](references/fonts-licensing.md)
- Before a versioned release: [`references/release-checklist.md`](references/release-checklist.md)

## 5. CLI reference

Run from **repository root** (same venv as §1; Mermaid optional per §2):

```bash
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py INPUT.md
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py INPUT.md -o OUTPUT.pdf
```

| Item | Required | Description |
|------|----------|-------------|
| `markdown` | yes | Input `.md` path (positional) |
| `-o` / `--output` | no | Output `.pdf`; **relative** `-o` resolves from **cwd**. **Default** (omit): `fixtures/out/<stem>.pdf` under the skill directory |
| `--no-filter` | no | Keep metadata and Contributor Roles (default: strip for branded PDF) |
| `--no-page-numbers` | no | Skip pypdf footer stamp (confidential line + page numbers; separate from issuer merge) |
| `--brand-pack` | no | Brand directory (`theme.yaml`, `compliance.md`, logos). Overrides `MDPDF_BRAND_PACK`; default: skill `brand_kits/` |
| `--no-company-footer` | no | Omit ReportLab issuer block (icon + lines + QR) |
| `--no-mermaid` | no | Do not run mmdc/Puppeteer; mermaid fences render as **source** (shaded code block) |
| `--mermaid-E` / `--mermaid-S` / `--mermaid-H` | no (pick one) | PNG viewport: `E` / `S` (default if none) / `H`; overrides `MDPDF_MERMAID_PRESET` |
| `--watermark` | no | Tiled diagonal gray watermark under text (pypdf, full page, 120pt row spacing); `company//user` when both; company from `compliance.md` only; if none, user only; see [`SKILL.md`](SKILL.md) |

Fenced blocks whose language is not `mermaid` / `mmd` render as **GitHub-like** code cards (label bar, mono body, left accent). The **gap above the lang bar** (default **21mm**, `MDPDF_FENCED_CARD_ABOVE_MM`) is **built into** the `FencedCodeCardTable` (not a separate pre-`Spacer` in the story), so changing mm is visually stable next to the previous paragraph. Card width follows the **frame** `availWidth` (aligns with body). Optional **Pygments** (`MDPDF_FENCED_PYGMENTS`, default on) and **line numbers** (`MDPDF_FENCED_LINE_NUMBERS`). See `MDPDF_FENCED_MAX_*` and [`SKILL.md`](SKILL.md). **Mermaid:** centered caption under images (50% of body, YAML `title` or heading). Small Mermaid uses `KeepTogether` when the scaled block is under about 45% of body height.

**Watermark env:** `MD_PDF_WATERMARK_USER` (optional; else `getpass` / `USER` / `USERNAME`). Organization name is **not** read from `MD_PDF_COMPANY` — use `compliance.md` only. No separate flag to turn watermark on except CLI `--watermark`.

**Mermaid env (optional):**

| Variable | Effect |
|----------|--------|
| `MDPDF_SKIP_MERMAID` | `1` / `true` / `yes` → same as `--no-mermaid` |
| `MDPDF_MERMAID_PRESET` | `E` / `S` / `H` if no `--mermaid-E|S|H`; default `S` |
| `MDPDF_MERMAID_NPX` | truthy → use `npx` for mmdc (needs network) |
| `MDPDF_MERMAID_VERBOSE` | truthy → stderr diagnostics (`mmdc --version` once, browser path, cache, `-C`/`-c`) |
| `MDPDF_PUPPETEER_CACHE_FIRST` | **macOS** — try cache `chrome-headless-shell` / CFT before `/Applications/` (uncommon) |
| `MDPDF_PUPPETEER_ALLOW_DARWIN_STABLE_CHROME` | **macOS** — allow `/Applications/Google Chrome.app` (default: **omitted**; that binary often **crashes** when driven by mmdc from Cursor) |
| `MDPDF_MERMAID_MAX_CHARS` | cap Mermaid source size (default 200000) |
| `MDPDF_SKIP_MERMAID_TEST` | `1` / `true` / `yes` → pytest skips mmdc/Chromium integration only (does not affect PDF rendering) |
| `MDPDF_BRAND_PACK` | Path to brand pack directory (ignored if `--brand-pack` is set) |

**Mermaid + Noto:** With bundled TTFs, mmdc uses [`references/mermaid-noto-config.json`](references/mermaid-noto-config.json) and per-run CSS for `@font-face`. Pin **@mermaid-js/mermaid-cli** to 11.x–12.x in CI (`mmdc -V`). In Docker, mount the repo/skill so `fonts/` paths work; `file:` font URLs may be blocked in hardened images.

**CJK / page chrome:** Body, **Generated:**, and the pypdf footer strip all use **Noto Sans SC** (see **`theme.yaml`**, default `IDS-Noto-Regular`) and English **`compliance.md`**. Regression: [`fixtures/uat-cjk.md`](fixtures/uat-cjk.md) and [`tests/test_md_to_pdf_cjk.py`](tests/test_md_to_pdf_cjk.py).

**Tests (maintainers):** [`tests/README.md`](tests/README.md) — `pytest` and Mermaid integration / `MDPDF_SKIP_MERMAID_TEST`.

**Examples:**

```bash
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py doc.md
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py doc.md -o out.pdf
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py doc.md --no-filter
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py doc.md --no-page-numbers --no-company-footer
MDPDF_SKIP_MERMAID=1 .cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py doc.md
```

Canonical CLI tables and agent notes: [`SKILL.md`](SKILL.md) (section **CLI** → **CLI reference**).

