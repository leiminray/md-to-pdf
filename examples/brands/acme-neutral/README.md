# ACME Neutral Reference Brand

A content-neutral brand pack used by md-to-pdf documentation and the
dual-brand integration tests required by spec §7.2.1.

## Contents

```
acme-neutral/
├── brand.yaml         # schema entry
├── theme.yaml         # colours, typography, layout
├── compliance.yaml    # footer, issuer, watermark
├── LICENSE            # Apache-2.0
└── README.md          # this file
```

## Usage

```bash
md-to-pdf input.md -o out.pdf --brand acme-neutral
```

This brand intentionally has no logo or icon assets so the rendering
behaviour can be tested without binary fixtures. Add an `assets/`
subdirectory and reference the files from `theme.yaml` if you need them.

## License

Apache-2.0. See [LICENSE](./LICENSE).
