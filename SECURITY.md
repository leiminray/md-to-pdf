# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in md-to-pdf, please report it responsibly to:

**Email:** [sophie.leiyixiao@gmail.com](mailto:sophie.leiyixiao@gmail.com)

**Please do NOT open a public GitHub issue for security vulnerabilities.**

## Disclosure Window

We follow a **90-day responsible disclosure window**:

1. **Day 0**: You report the vulnerability via email
2. **Day 1**: We acknowledge receipt and begin triage
3. **Days 1–30**: We work on a fix and prepare a security patch
4. **Days 30–90**: We coordinate release timing with you and finalize the patch
5. **Day 90**: We publish the security advisory and release the patched version publicly

If a fix cannot be completed within 90 days, we will issue a public advisory explaining the situation and any interim mitigations.

## Security Best Practices

When using md-to-pdf:

### 1. Input Validation

- Validate markdown input before rendering if it comes from untrusted sources
- Use `--allow-remote-assets=false` (default) to block remote image/asset URLs
- Enable `--deterministic` mode to detect tampering with input content

### 2. Watermarking & Audit Logs

- Enable watermarks with `--watermark-user` to track document ownership
- L2 XMP watermarks are cryptographically hashed for tamper detection (Plan 5+)
- Audit logs (`~/.md-to-pdf/audit.jsonl`) record all render operations; monitor for unexpected entries

### 3. Font & Asset Management

- Only install fonts from trusted sources via `md-to-pdf fonts install`
- Brand packs should be validated before deployment; use `md-to-pdf brand validate`
- SVG assets are converted to PNG before embedding (via cairosvg); embedded SVGs are not executable

### 4. Output Validation

- Use `md-to-pdf doctor` to verify your environment before production use
- Test rendering with `--deterministic` to detect any non-deterministic behavior (e.g., from untrusted Mermaid renderers)
- Verify page counts and file sizes match expectations (sudden changes may indicate injection)

## Supported Versions

| Version | Status | Security Updates |
|---------|--------|------------------|
| 2.0.x   | Current | Yes — all patches |
| 2.0.0a1 | Pre-release | No — upgrade to 2.0.0 |
| 1.8.9   | Deprecated | No — migrate to 2.0.0 |

## Known Security Considerations

### Remote Assets (Opt-In)

By default, md-to-pdf rejects remote image/asset URLs in markdown to prevent unexpected network requests. Use `--allow-remote-assets` explicitly if you need remote assets.

### Mermaid Rendering

Mermaid diagrams are rendered via one of three backends (in order of preference):
- **Kroki** (external service): requires network access; diagrams sent to kroki.io unless you run a local instance
- **Puppeteer** (Chromium): runs headless browser; more resource-intensive but isolated
- **Pure Python** (mermaid-js transpiled): no external dependencies; fallback if Kroki/Puppeteer unavailable

For sensitive documents, use the pure-Python renderer or validate diagram source before rendering.

### PDF/A Compliance

md-to-pdf v2.0 does not yet produce PDF/A-2b (archive format). Use external tools like veraPDF if archival compliance is required. PDF/A support is planned for v2.3.

## Version History

- **2.0.0** (2026-04-28): First release with comprehensive security model (L1 + L2 watermarks, audit logging, determinism verification)

## Contact

For security-related questions that don't constitute a vulnerability report, email: [sophie.leiyixiao@gmail.com](mailto:sophie.leiyixiao@gmail.com)
