# Brand kit (`brand_kits/`)

Single flat directory for the built-in brand: **no** `default/` subfolder. Required files:

| File | Purpose |
|------|---------|
| `theme.yaml` | Colors, typography sizes, font **face names** (default `header_generated_face` / `footer_face` = `IDS-Noto-Regular` — same family as `fonts/NotoSansSC-*.ttf`), logo/icon filenames, layout hints. |
| `compliance.md` | English SSOT: footer confidential line, issuer bullet list, WhatsApp URL (`##` sections — see file). Optional `## brand profiles` (first list line) is the preferred `--watermark` org/brand string; else the first **bold** line under *Issuer lines*. If neither yields a name, the watermark is **user only**; `MD_PDF_COMPANY` is **not** used by md-to-pdf. |
| `logo.png` | Header wordmark. |
| `icon.png` | Issuer strip icon. |
| `branding-and-ux.md` | Narrative / layout reference for what the renderer draws (not business workflow). |

Fonts are **not** part of this folder. Built-in `theme.yaml` uses the same **Noto Sans SC** as body / Mermaid / pypdf 页脚条. Custom packs: `footer_face` / `header_generated_face` must be **PostScript names** of fonts **already registered** in `register_fonts()` (typically `IDS-Noto-Regular` / `IDS-Noto-Bold`), not raw `.ttf` paths.

## Custom pack

- **CLI:** `--brand-pack /path/to/dir`
- **Env:** `MDPDF_BRAND_PACK=/path/to/dir`

The directory must contain the same required **pack** files (`theme.yaml`, `compliance.md`, `logo.png`, `icon.png`). Optional: copy `branding-and-ux.md` if you document a custom layout. Implementation loads **only** that directory (whole-pack switch).
