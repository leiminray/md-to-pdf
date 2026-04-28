# Fonts

Bundled font files used by md-to-pdf for PDF rendering.

## Contents

| File | Weight | License |
|------|--------|---------|
| `NotoSansSC-Regular.ttf` | 400 | SIL Open Font License 1.1 |
| `NotoSansSC-Bold.ttf` | 700 | SIL Open Font License 1.1 |

**Noto Sans SC** is used for Simplified Chinese body text in ReportLab. The font is required for CJK rendering — without it, md-to-pdf will fail loudly when CJK characters are detected in input markdown.

## Why bundle these?

CJK rendering quality is critical for enterprise documents. Bundling Noto Sans SC ensures:
- Out-of-the-box CJK support (no extra installation steps)
- Consistent rendering across platforms (Linux/macOS/Windows)
- Predictable output for deterministic mode (same fonts → same bytes)

## Custom fonts

For brand-specific typography, use a brand pack with a `fonts/` directory containing your custom TTFs. The brand registry will load them in preference to bundled fonts when matching.

## License

Both TTF files are distributed under [SIL OFL 1.1](https://scripts.sil.org/OFL), which permits embedding in PDFs without restriction.

Source: [Google Fonts — Noto Sans SC](https://fonts.google.com/noto/specimen/Noto+Sans+SC)
