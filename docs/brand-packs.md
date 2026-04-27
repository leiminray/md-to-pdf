# Brand packs

A brand pack is a directory containing:

```
mybrand/
├── brand.yaml         # required — schema_version, id, name, version
├── theme.yaml         # colours, typography, layout
├── compliance.yaml    # footer, issuer, watermark, disclaimer
├── logo.png           # required by theme.yaml.assets.logo
├── icon.png           # required by theme.yaml.assets.icon
└── fonts/             # optional — additional .ttf/.otf
```

See `examples/brands/idimsum/` in the repo for a complete reference
implementation.

## 3-layer registry

`md-to-pdf brand list` resolves brands from (highest precedence first):

1. `./brand_packs/<id>/` — project-local
2. `~/.md-to-pdf/brand_packs/<id>/` — user
3. Bundled with the package — built-in

## SecurityConfig watermark gate

`brand.yaml` may set:

```yaml
security:
  watermark_min_level: "L1+L2"   # L0 / L1 / L1+L2
  allow_remote_assets: false
```

If a render request asks for a watermark level below `watermark_min_level`,
the pipeline raises `SecurityError(WATERMARK_DENIED)` (exit code 3).
This is what stops `--no-watermark` from silently disabling stamps on
brands that mandate them.

## Inline overrides

```bash
md-to-pdf README.md -o README.pdf \
  --brand acme \
  --override theme.colors.primary=#ff0000 \
  --override compliance.footer.text="Confidential — DO NOT DISTRIBUTE"
```

Overrides are gated by `brand.yaml`'s `forbidden_override_fields` list.
A forbidden override raises `BrandError(BRAND_OVERRIDE_DENIED)`.
