# Watermarks

v0.2.1 ships two watermark layers:

## L1 — visible diagonal text

Tiled rotated text on every page (Helvetica 13 pt, 38° rotation,
120 pt row spacing). Template:
`{brand_name} // {user} // {render_date}`.

The watermark colour is subject to a WCAG contrast guard
(`enforce_min_contrast`). Default colour `#EBEFF0` against white page
yields ratio ~1.05; brands may override but cannot drop below `min_ratio`.

## L2 — XMP metadata

Twelve XMP keys embedded in the PDF using the custom
`https://md-to-pdf.dev/xmp/1.0/` namespace:

| Key | Source |
|-----|--------|
| `dc:creator` | brand identity name (single-element list) |
| `dc:title` | document H1 or brand default |
| `pdf:Producer` | `md-to-pdf 2.0` |
| `xmp:CreatorTool` | `md-to-pdf 2.0` |
| `xmp:CreateDate` | ISO 8601 (frozen in deterministic mode) |
| `mdpdf:RenderId` | UUID v4 (or derived sha256 in deterministic mode) |
| `mdpdf:RenderUser` | `--watermark-user` |
| `mdpdf:RenderHost` | `sha256(hostname)[:16]` |
| `mdpdf:BrandId` | brand id |
| `mdpdf:BrandVersion` | brand pack version |
| `mdpdf:InputHash` | `sha256(markdown_bytes)` |
| `mdpdf:WatermarkLevel` | `L0` / `L1` / `L2` / `L1+L2` |

## Levels

```
L0       no L1, no L2 (--no-watermark)
L1       L1 visible stamp only
L2       L2 XMP only (no visible mark)
L1+L2    both (default)
```

L3-L5 (steganographic / encrypted / signature) land in v2.3.
