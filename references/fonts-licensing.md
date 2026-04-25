# Approved fonts for PDF output (IDS)

Authoritative typography standard: `company_assets/brand/guidelines/IDIMSUM_ExternalTypography_Standard_20260307_v1.0.md`.

Audit alignment: `.cursor/rules/std-audit.mdc` (font licensing + external typography checks for client-facing deliverables).

## Commercial-use requirement

All fonts embedded or relied upon in deliverables must have a **verified commercial-use license** (see `agent-core.mdc` Instruction 13). Typical approved families in this repo’s standard:

| Role | Font | License (typical) |
|------|------|-------------------|
| English body | Inter | SIL Open Font License 1.1 |
| Simplified Chinese | Noto Sans SC | SIL OFL 1.1 |
| Traditional Chinese | Noto Sans TC | SIL OFL 1.1 |
| Evidence / IDs | JetBrains Mono | SIL OFL 1.1 |

Do **not** treat system UI fonts (e.g. Arial) as the formal primary for **client-facing** PDFs unless explicitly approved outside Standard A.

## Where to obtain OTF/TTF

- **Google Fonts / Noto** official releases (OFL).
- **Inter** official release (OFL).
- **JetBrains Mono** official release (OFL).

Prefer the **skill-local** font directory **`.cursor/skills/md-to-pdf/fonts/`** (OFL Noto Sans SC TTF shipped there) so Markdown → PDF stays self-contained; reuse it across runs to avoid repeated large downloads.

## External vs internal

- **Client-facing PDF**: Strictly follow Standard A fonts above; run `/audit` before share.
- **Internal-only PDF**: Still use licensed fonts; avoid unlicensed or unknown system fonts for anything that might be forwarded externally.
