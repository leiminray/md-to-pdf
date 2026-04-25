---
name: md-to-pdf
description: Converts Markdown to PDF using this bundle (.venv, scripts/md_to_pdf.py, OFL Noto Sans SC TTF in fonts/). Use for MD→PDF export or batch render. Does not select business workflows—callers supply context. Keywords—markdown, PDF, export.
author: IDS CGO Agent
version: 1.8.9
license: Complete terms in LICENSE.txt
---

# Skill: Markdown → PDF

**Scope:** Technical conversion **Markdown → PDF** only (single toolchain: **ReportLab**). No routing to product commands—that belongs to the **caller** (instructions, **commands**, or **skills** layered on top).

## When to use

- Input is (or should be) **Markdown**; output should be **PDF**.
- Use one skill-local **`.venv`**, **`fonts/`**, and **`scripts/md_to_pdf.py`**.

---

## CLI

From the **repository root** (adjust if the clone path differs):

```bash
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py INPUT.md
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py INPUT.md -o OUTPUT.pdf
```

- **Setup:** [`README.md`](README.md) (venv + optional Mermaid bootstrap), [`fonts/README.md`](fonts/README.md), [`requirements-md-pdf.txt`](requirements-md-pdf.txt) (Step A + Step B).
- **Success reply:** Exactly one line: `Wrote: …/OUTPUT.pdf`. No second line.
- **Failure:** Emit the tool error or follow [`README.md`](README.md) (venv / deps).

### CLI reference

| Item | Required | Description |
|------|----------|-------------|
| `markdown` | yes | Input `.md` path (positional) |
| `-o` / `--output` | no | Output `.pdf`. **Relative** paths resolve from the **current working directory**; absolute paths are accepted. **Default** (omit `-o`): `fixtures/out/<input-basename>.pdf` under this skill (e.g. `.cursor/skills/md-to-pdf/fixtures/out/doc.pdf` for `doc.md`) |
| `--no-filter` | no | Keep metadata and Contributor Roles (default: strip for branded PDF) |
| `--no-page-numbers` | no | Skip pypdf footer stamp (confidential line + page numbers; issuer merge unchanged) |
| `--brand-pack` | no | Directory with `theme.yaml`, `compliance.md`, `logo.png`, `icon.png`. Overrides `MDPDF_BRAND_PACK`; default: `brand_kits/` (flat, no `default/` subdir) |
| `--no-company-footer` | no | Omit ReportLab issuer block (icon + lines + QR); footer stamp may still apply unless `--no-page-numbers` |
| `--no-mermaid` | no | Do not run mmdc/Puppeteer; fenced `mermaid` blocks render as **source code** (same shaded style as other fences), not PNG |
| `--mermaid-E` / `--mermaid-S` / `--mermaid-H` | no (mutually exclusive) | Viewport for PNG export: **E** 800×600, **S** 1024×768 (default when **none** of these flags), **H** 1920×1080. Overrides `MDPDF_MERMAID_PRESET` |
| `--watermark` | no | After footer: pypdf **tiled** diagonal gray watermark **under** body/footer text (full page, **120pt** between text baselines / “rows”; repeated string + column gap). **Company / brand** only from `compliance.md` (`## brand profiles` first list line, else **Issuer** first `**bold**`); if none, watermark text is **user only** (no company). When both are present, text is ``company//user`` (literal `//`). **User** is required (`MD_PDF_WATERMARK_USER` or `getpass` / `USER` / `USERNAME`); if user is missing, **no** watermark. ``MD_PDF_COMPANY`` is **not** used by this skill for watermark text. |

**Fence language:** The first token on the opening line is used (` ```mermaid {.opts}` → `mermaid`). Other fenced blocks render as shaded code, not dropped.

**Mermaid environment variables** (with `--no-mermaid`, skipping render wins):

| Variable | Effect |
|----------|--------|
| `MDPDF_SKIP_MERMAID` | Non-empty `1` / `true` / `yes` (case-insensitive) → same as `--no-mermaid` |
| `MDPDF_MERMAID_PRESET` | `E` / `S` / `H` when no `--mermaid-E|S|H` is passed; default `S`; invalid → `S` (stderr note if `MDPDF_MERMAID_VERBOSE`) |
| `MDPDF_MERMAID_NPX` | Truthy → invoke mmdc via `npx` (needs network) |
| `MDPDF_MERMAID_VERBOSE` | Truthy → stderr diagnostics (`mmdc --version` once, browser path, cache dir, `-C`/`-c`, argv) |
| `MDPDF_PUPPETEER_CACHE_FIRST` | **macOS** — if truthy, use cache **headless-shell** and **return** when found; **does not** use cache-only *Chrome for Testing* as a short-circuit (that skipped `/Applications/…` Edge/Chromium and was crash-prone) |
| `MDPDF_PUPPETEER_SKIP_CFT` | **macOS** — if truthy, omit **Google Chrome for Testing** (Puppeteer cache) from mmdc browser tries; set when CFT **SIGABRT** / **SEGV** under Cursor |
| `MDPDF_PUPPETEER_ALLOW_DARWIN_STABLE_CHROME` | **macOS** — if `1`/`true`/`yes`/`on`, allow **`/Applications/Google Chrome.app/...`** in the Mermaid browser list. **Omit (default):** that bundle is **not** used: it often **SIGABRT**s when mmdc runs under Cursor. Prefer Edge, Chromium, Beta, or install headless-shell into the Puppeteer cache |
| `MDPDF_MERMAID_LEAD_MM` | Millimetres of vertical **Spacer** inserted before a rendered Mermaid PNG (after the preceding paragraph’s `spaceAfter`). Default `0.5`, clamp 0–5 |
| `MDPDF_MERMAID_MAX_CHARS` | Max Mermaid source length (default 200000); excess → in-PDF notice, no mmdc |
| `MDPDF_BRAND_PACK` | Path to brand directory (same layout as `brand_kits/`). Ignored if `--brand-pack` is passed |
| `MD_PDF_WATERMARK_USER` | **Watermark only** — display user; if unset, `getpass.getuser()` then `USER` / `USERNAME` (if all empty, no watermark) |

**Non-Mermaid fenced blocks:**

| Variable | Effect |
|----------|--------|
| `MDPDF_FENCED_MAX_CHARS` | Max characters for a single non-Mermaid fence body (default 262144) |
| `MDPDF_FENCED_MAX_LINES` | Max lines per fence (default 500); overflow → truncated body + note |
| `MDPDF_FENCED_PYGMENTS` | Default `1` / on: Pygments + limited “GitHub light” token colors; set `0` / `off` to plain mono (NBSP indents) |
| `MDPDF_FENCED_LINE_NUMBERS` | `1` / `true` / `yes` / `on` → right-aligned line-number column (logical lines; long wrapped lines may visually diverge) |
| `MDPDF_FENCED_CARD_ABOVE_MM` | **Millimetres** of vertical space inside the card table **before** the lang bar (default `0.0`, clamp 0–25). Large gaps above a fence are usually the **preceding** paragraph/heading `spaceAfter`; the renderer also uses a tight `spaceAfter` when the next line is a ``` fence. |

**Mermaid fonts:** When `fonts/NotoSansSC-*.ttf` are present, mmdc runs with [`references/mermaid-noto-config.json`](references/mermaid-noto-config.json) and generated `mdpdf-mermaid.css` (`@font-face`) so diagram text matches bundled Noto. If TTFs are missing, diagrams still render with Chromium default fonts. **Minimum tested mmdc:** 11.x (`mmdc -c` / `-C` for config and CSS). Docker: mount the skill directory so font paths resolve.

**Examples:**

```bash
# Default output: skill fixtures/out/doc.pdf (strip metadata; Mermaid depends on env/deps)
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py doc.md

# Explicit output path
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py doc.md -o out.pdf

# Keep metadata and Contributor Roles from the `.md`
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py doc.md --no-filter

# No confidential line / page-number footer overlay
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py doc.md --no-page-numbers

# No company issuer block
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py doc.md --no-company-footer

# Skip Mermaid (or: export MDPDF_SKIP_MERMAID=1)
.cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py doc.md --no-mermaid
```

---

## Prerequisites

```bash
python3 -m venv .cursor/skills/md-to-pdf/.venv
.cursor/skills/md-to-pdf/.venv/bin/pip install -r .cursor/skills/md-to-pdf/requirements-md-pdf.txt
```

**Mermaid:** Not on `pip`. Follow **Step B** in [`requirements-md-pdf.txt`](requirements-md-pdf.txt), or run [`scripts/ensure_mermaid_deps.py`](scripts/ensure_mermaid_deps.py) (`--auto-install` / `--puppeteer-chrome` optional). See [`README.md`](README.md) §2.

Body fonts: **`fonts/NotoSansSC-Regular.ttf`**, **`fonts/NotoSansSC-Bold.ttf`** (OFL — see [`fonts/README.md`](fonts/README.md)). Fenced code: **`register_mono_font()`** first tries **Noto Sans Mono** (`NotoSansMono-Regular.ttf`) on the **system** (same default *intent* as body Noto — not stored under `fonts/`), then other monos, else **Courier**; see [`fonts/README.md`](fonts/README.md).

## Behavior

- A leading YAML **frontmatter** block (`---` … `---`, as in some plan exports) is **removed** before PDF layout so metadata is not printed as body text.
- **Run-on ATX headings** on one line (e.g. `# Part## Chapter`) are split into two headings before parsing (not applied inside fenced code blocks).
- **Body / tables / issuer (ReportLab)** use **Noto Sans SC** (`IDS-Noto-Regular` / `IDS-Noto-Bold`); **Generated:** and the **pypdf** footer strip (confidential + page numbers) use the same family via **`theme.yaml`** (default `IDS-Noto-Regular`). English copy in **`compliance.md`**. Missing `fonts/*.ttf`: see **`fonts/README.md`** (Git restore, curl, or copy from another clone).
- MD → ReportLab `Paragraph` / `Table` / `SimpleDocTemplate`; preserve **bold** and tables where supported.
- **`## 目录` / `## Table of Contents`** with a **pipe table** of entries: each body row (after the header row) is matched **against all document headings** (plain text, first match) and rendered with a **clickable internal PDF link** to the same named destination as the PDF outline (`ids-h-*`); if no match, the row is plain text as before. Multi-column cells are tried as `A · B · …` then each cell.
- Fenced code blocks (triple backticks): `mermaid` / `mmd` → PNG via mmdc (when enabled); any other language tag → code block in the PDF. On **macOS**, if the first browser (often Puppeteer **chrome-headless-shell**) crashes, mmdc is retried with **other** executables in order (e.g. Edge, Chromium) without requiring user flags. **Fenced code layout (GitHub-like):** optional vertical space **above** the lang bar is **row 0** inside a **`FencedCodeCardTable`** (`MDPDF_FENCED_CARD_ABOVE_MM`); the large gap that users see under a heading is usually that heading’s `spaceAfter` — when the next material line is a ``` fence, the previous paragraph/heading list item uses a **tight** `spaceAfter`. The table takes the frame’s **`availWidth`** at `wrap` so the block **left/right** match body text. **Header strip** (language badge) then **body** with **~8.5pt** mono, **~12pt** leading; **left accent** via `fenced_rl.lang_accent_hex`. **Pygments** (default on; `MDPDF_FENCED_PYGMENTS=0` to disable) applies a **limited** syntax palette on common fence languages; **mermaid** fence uses `text` lexer when Pygments has no mermaid. **CJK / fullwidth** runs in code use the **body Noto** font so they are not “tofu” in monospace. **Line numbers** optional (`MDPDF_FENCED_LINE_NUMBERS=1`). **Monospace** as **`IDS-Mono`** (see `register_mono_font` / `fonts/README.md`) then system paths, else **Courier**; indents: NBSP. **Mermaid caption (default):** below each image, a **centered** line in muted color at **50%** of body font size, text from diagram YAML `title:` or nearest ATX heading above the block (omitted if neither resolves). **Mermaid** lead: `MDPDF_MERMAID_LEAD_MM` (default 0.5mm) before the image. `KeepTogether` for small Mermaid image blocks (scaled height under ~45% of body) is automatic; no CLI for that.
- Embed **licensed** fonts; **body** Noto files live in **`fonts/`**; code mono may be **system-only** (Noto Sans Mono) or **Courier** fallback.

---

## Renderer layout

[`scripts/md_to_pdf.py`](scripts/md_to_pdf.py) applies a **fixed visual template** (header band, logos from the active **brand pack** under **`brand_kits/`**, pypdf footer + issuer merge, table styling). SSOT: [`brand_kits/README.md`](brand_kits/README.md). Layout narrative: [`brand_kits/branding-and-ux.md`](brand_kits/branding-and-ux.md). **Book-style** font pairs (e.g. Palatino + 宋体) are **not** this skill’s default; the bundle standard is **Noto Sans SC** for CJK body text.

**Tables:** Pipe tables use content-weighted column widths; cap per column; compact cell padding (`wordWrap=CJK`).

---

## Anti-patterns

- New venv per sandbox folder — reuse **this skill’s** `.venv`.
- Re-fetch large font bundles every run — keep **`fonts/`** filled per [`fonts/README.md`](fonts/README.md).
- After success: **`Wrote:` only** — no extra commentary.
