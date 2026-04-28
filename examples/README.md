# Examples

Reference brand packs and contributed integrations for md-to-pdf.

## Layout

```
examples/
├── brands/         # Example brand packs (theme + assets + compliance text)
│   └── idimsum/    # Sample brand demonstrating the brand v2 schema
└── contributed/    # Community-contributed integrations and templates
    └── quotation/  # Enterprise quotation document template (real-world schema)
```

## Brand packs

The `brands/idimsum/` directory is a complete reference brand pack showing:

- `brand.yaml` — schema-validated theme definition (colors, typography, layout)
- `assets/` — logos, icons, and other brand imagery
- `compliance.md` — issuer information and footer text
- `LICENSE` — required brand-pack licensing declaration

To use a brand pack:

```bash
md-to-pdf input.md -o output.pdf --brand-pack-dir examples/brands/idimsum
```

To validate a brand pack against the schema:

```bash
md-to-pdf brand validate examples/brands/idimsum
```

## Contributed templates

The `contributed/` directory holds end-user-contributed integrations and document templates that demonstrate non-trivial real-world usage patterns. They are not part of the core distribution but serve as reference implementations.

## Creating your own

See the [Brand Pack Authoring Guide](https://leiminray.github.io/md-to-pdf/brand-pack-authoring/) on the documentation site for a walkthrough of creating custom brand packs.
