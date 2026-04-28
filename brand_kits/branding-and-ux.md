# PDF layout reference (`md_to_pdf.py`)

Technical description of what the renderer draws. **Not** a business-workflow spec—callers decide when this layout is appropriate.

## Default output

- **Header**: **IDIMSUM logo** (blue PNG from `company_assets/brand/assets/logos/concepts/IDIMSUM_logo_blue_4k.png`), **left**; **PDF generation timestamp** (`PDF generated: YYYY-MM-DD HH:MM:SS`), **right**; horizontal rule **#0f4c81**.
- **Confidentiality strip**: **IDIMSUM icon** + English confidentiality line; accent **#b91c1c**.
- **Typography**: **Noto Sans SC** via **`NotoSansSC-Regular.ttf`** and **`NotoSansSC-Bold.ttf`** in `.cursor/skills/md-to-pdf/fonts/` (OFL). Legacy `NotoSansCJKsc-*.otf` in `fonts/` may work if embeddable; some repo `external-standard-a/*.otf` use PostScript outlines and fail in ReportLab.
- **Body / tables**: Headings use brand blue; table header row gray; grid **#d1d5db**.
- **MD filter (default)**: Strips leading metadata bullets (`- **Project Name**` …) and **`## Contributor Roles`** + table until `---` so the PDF starts at title / TOC / body.
- **Footer**: **Page i / n** at bottom (pypdf stamp after issuer; same Noto family as `theme.yaml` `footer_face`, default `IDS-Noto-Regular` = `fonts/NotoSansSC-*.ttf`).

## CLI flags

- `--no-filter`: Keep full MD including metadata and Contributor Roles.
- `--no-page-numbers`: Skip pypdf footer stamp.

## Optional polish (caller-defined)

1. **Output names**: Use a stable naming pattern if your process requires it.
2. **Subtitle**: Optional language or context line under the title (e.g. locale label).
3. **Issuer / entity**: Optional second line from `company_assets/COMPANY_PROFILE.md` if you want it in the PDF body.
4. **Watermarks**: Remove third-party tool watermarks from source MD before export if they should not appear in the PDF.
