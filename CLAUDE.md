# CLAUDE.md — md-to-pdf

Project guidance for AI agents working in this repo. Read this first; it overrides anything you may remember from training data about how to invoke the tool.

## What this project is

A **Markdown → PDF** conversion engine targeted at enterprise use:
- Brand kits (logo, colours, fonts, footer, compliance text)
- Watermarks for data security
- Mermaid diagrams, syntax-highlighted code, embedded images, CJK text
- PDF bookmarks + table of contents
- Designed to ship as an open-source tool consumable from CLI, Python API, Claude Code / Cursor / Gemini CLI skills, MCP servers, and GitHub Actions.

The repo is currently in a **transition state**: v1.8.9 (a 3,443-line monolith) and v2.0a1 (a modular walking skeleton from Plan 1) coexist. Plan 1 is done; Plans 2–5 (AST transformers + brand v2, renderers, watermarks, comprehensive UAT) are pending.

## Repository state today (do not assume otherwise)

| Layer | Status | Location |
|---|---|---|
| **v1.8.9 monolith** | ✅ Working — what legacy `SKILL.md` describes | `scripts/md_to_pdf.py`, `scripts/brand_pack.py`, `scripts/fenced_rl.py`, `scripts/ensure_mermaid_deps.py` |
| **v2.0a1 walking skeleton** | ✅ **Plan 1 complete** — `md-to-pdf` CLI installs and renders English-only markdown via markdown-it-py → AST → ReportLab | `src/mdpdf/` (pipeline, errors, cli, logging, markdown/parser+ast, render/engine_base+reportlab, cache/tempfiles) |
| **Plan 1 patches applied** | ✅ All 11 (P1-001..P1-011) plus a follow-up review pass (I2/I3/I4/I5, m2, m5) | See git log for `P1-XXX` and `final-review fixes` commits |
| **Plans 2–5** | 📋 Sketched in Plan 1 §Roadmap; full plans not yet authored | `docs/superpowers/plans/` will hold them when written |
| **v2.x roadmap** (templates, MCP, L3-L5, PDF/A, dual engine) | 📋 Designed for later versions | Spec exists; **do not implement in this round** |
| **Single brand pack** | ✅ Working at root `brand_kits/` (v1 layout) | Will migrate via `md-to-pdf brand migrate` in Plan 2 |
| **Bundled CJK fonts** | ✅ Noto Sans SC OFL | `fonts/` (~20MB, kept for v1.8.9; v2.0 wires them via font manager in Plan 2; v2.0a1 fails loud on CJK input until then) |
| **v1.8.9 tests** | ⚠️ ~20% coverage; **skipped under v2 pytest config** | `tests/test_md_to_pdf_*.py` preserved but excluded by `[tool.pytest.ini_options] testpaths` |
| **v2.0 tests** | ✅ 81 tests passing (unit + integration walking-skeleton) | `tests/unit/`, `tests/integration/` |
| **CI** | ✅ GitHub Actions workflow on Python 3.12 / Ubuntu, lint + mypy + pytest | `.github/workflows/ci.yml` (multi-OS / multi-Python matrix lands in Plan 5) |
| **Remote** | ✅ `origin/main` → `github.com/leiminray/md-to-pdf.git` | Branch protection assumed but not yet enforced |
| **Specs** | ✅ Authoritative for next work | `docs/superpowers/specs/` (see below) |

## Authoritative documents (read before writing code)

| Doc | Purpose | When to consult |
|---|---|---|
| [`docs/superpowers/specs/2026-04-26-md-to-pdf-v2.0-foundation-design.md`](docs/superpowers/specs/2026-04-26-md-to-pdf-v2.0-foundation-design.md) | **v2.0 MVP scope** — what's being built across Plans 1–5 | Always — this is the build target |
| [`docs/superpowers/specs/2026-04-25-md-to-pdf-v2.x-roadmap.md`](docs/superpowers/specs/2026-04-25-md-to-pdf-v2.x-roadmap.md) | Long-term vision v2.0 → v2.4 (templates, MCP, L3-L5, PDF/A, dual engine) | Only when designing forward-compatibility hooks; **do not implement** anything past v2.0 |
| [`docs/superpowers/plans/2026-04-26-md-to-pdf-v2.0-plan-1-walking-skeleton.md`](docs/superpowers/plans/2026-04-26-md-to-pdf-v2.0-plan-1-walking-skeleton.md) | Plan 1 — **already executed** | Reference for v2.0a1 architecture decisions; sketches Plans 2–5 |
| [`docs/superpowers/plans/2026-04-26-plan-1-review-patch.md`](docs/superpowers/plans/2026-04-26-plan-1-review-patch.md) | Plan 1 review patches (P1-001..P1-011) — **all applied** | Reference only |
| [`README.md`](README.md) | v2.0a1 walking-skeleton banner + v1.8.9 setup | When the user wants to install / run either version |
| [`SKILL.md`](SKILL.md) | v1.8.9 invocation (legacy, still works in parallel) | When the user explicitly asks for v1.8.9 (CJK / Mermaid / brand-kit features beyond Plan 1) |

If the spec and roadmap disagree, the **v2.0 foundation spec wins** for implementation; the roadmap is reference only. If a Plan and the spec disagree, the **spec wins** unless the Plan was approved with an explicit deviation note.

## v2.0 scope guard rails — what NOT to build

The v2.0 foundation deliberately ships **less** than the roadmap. If you find yourself writing any of the following, stop and confirm with the user first:

| Feature | Status |
|---|---|
| Template-pack system (typed front-matter, computed fields, registry) | ❌ v2.1 — only hard-coded `generic` template in v2.0 |
| `quote` / `user-manual` / `certificate` / any non-`generic` template | ❌ v2.1 |
| WeasyPrint or any second rendering engine | ❌ v2.x (and only if real users ask) |
| MCP server / Skill bundle / GitHub Action / Docker images | ❌ v2.2 |
| L3 steganographic / L4 encryption / L5 signature watermarks | ❌ v2.3 |
| `policy.yaml` / brand-lock / template-lock / system-wide enforcement | ❌ v2.3 |
| PDF/A-2b output | ❌ v2.3 |
| `forensics extract` / `forensics verify` | ❌ v2.3 |
| Prometheus / OpenTelemetry metrics | ❌ v2.3+ |
| HMAC tamper-protection on XMP | ❌ v2.3 |
| Pre-release audit / wording-assist / business-process gating | ❌ permanently out of scope |

What v2.0 **does** ship: ReportLab-only engine, hard-coded `generic` template, brand v2 schema with 3-layer registry (project / user / built-in; system-wide added in v2.3), L1 visible + L2 XMP watermarks, Mermaid sandboxed (Kroki / Puppeteer / pure), CLI + Python API, audit log (user-mode JSONL), markdown-it-py AST replacing regex parsing.

## Highest-risk task in v2.0 (gate everything else on this)

**`markdown-it-py` parity vs the v1.8.9 regex parser.** Plan 1 proved the basic markdown-it-py path works for English-only CommonMark + GFM (14 parser tests + walking-skeleton e2e green). The full parity gate — diff-zero output for every existing `fixtures/uat-*.md` plus the new `fixtures/branch_ops_ai_robot_product_brief.md` — is **Plan 5's** acceptance bar. Plan 2 (AST transformers) and Plan 3 (renderers) progressively close the gap; do not declare the gate met before Plan 5. See foundation spec §2.1.3 and §7.2.

## Architectural rules for v2.0

- **AST-first.** All markdown parsing goes through `markdown-it-py` → internal AST → render. Never reintroduce regex-based markdown handling.
- **Single orchestrator.** Every render path goes through `Pipeline.render(RenderRequest) → RenderResult` in `src/mdpdf/pipeline.py`. CLI and Python API are thin wrappers around this.
- **Engine ABC even with one impl.** `RenderEngine` is an ABC with one concrete `engine_reportlab.py` in v2.0; the dispatch path is exercised by tests so adding a second engine later is mechanical.
- **Schema validate before parse.** Brand pack and request inputs validate via pydantic v2 before any markdown parsing happens.
- **Fail loudly on missing CJK fonts** when input contains CJK chars. No silent tofu rendering.
- **No remote network access by default.** `--allow-remote-assets` is opt-in; remote URLs in markdown / brand assets are rejected otherwise.
- **Atomic file writes.** PDF output via `output.pdf.tmp.<random>` → `fsync` → `rename`.
- **Determinism mode is contract.** With `--deterministic` or `SOURCE_DATE_EPOCH`, same input + same brand + same options + same `--watermark-user` produces bit-identical PDF. Only Kroki and Puppeteer Mermaid renderers are deterministic-safe.
- **Never strip the existing v1.8.9 file** (`scripts/md_to_pdf.py`) until v2.0 passes the v1-parity golden suite. Keep it working in parallel.

## Development conventions

- **Language:** Python 3.10+ (CI matrix: 3.10–3.13).
- **Lint:** `ruff` (formatting + lint) + `mypy --strict` + `pyright`.
- **Test:** `pytest`, `pytest-asyncio`. Coverage target ≥ 80% on `src/mdpdf/`.
- **License:** Apache-2.0 (chosen for explicit patent grant — do not switch to MIT without discussion).
- **Commit style:** Conventional Commits encouraged; sign-off (DCO) required.
- **Branch protection:** PRs to `main` need passing CI. No direct pushes.

## Common commands

### v2.0a1 walking skeleton (preferred for new work; English-only)

Console script installed via `.venv-v2/`:

```bash
# Render a markdown file (English-only in v2.0a1; CJK fails loud until Plan 2)
.venv-v2/bin/md-to-pdf INPUT.md -o OUTPUT.pdf

# Same with structured JSON output
.venv-v2/bin/md-to-pdf INPUT.md -o OUTPUT.pdf --json

# Version
.venv-v2/bin/md-to-pdf version       # → md-to-pdf 2.0.0a1

# Test, lint, type-check (same .venv-v2/)
.venv-v2/bin/pytest -v
.venv-v2/bin/ruff check src/ tests/
.venv-v2/bin/mypy --strict src/mdpdf
```

Re-create the v2.0 venv if needed: `rm -rf .venv-v2 && python3 -m venv .venv-v2 && .venv-v2/bin/pip install -e ".[dev]"`.

The CLI deliberately hides the not-yet-implemented flags (`--deterministic`, `--watermark-user`, `--no-audit`, `--locale`) from `--help` per P1-004; they accept input but warn on use. Don't promise these features in v2.0a1.

### v1.8.9 monolith (still works in parallel; use for CJK / Mermaid / brand kits today)

The legacy `SKILL.md` describes the path as `.cursor/skills/md-to-pdf/.venv/...`; in this repo the layout is at the project root:

```bash
# Render a markdown file
.venv/bin/python scripts/md_to_pdf.py INPUT.md -o OUTPUT.pdf

# With watermark
MD_PDF_WATERMARK_USER="alice@example.com" .venv/bin/python scripts/md_to_pdf.py INPUT.md --watermark

# Skip Mermaid (faster; no Chromium dependency)
MDPDF_SKIP_MERMAID=1 .venv/bin/python scripts/md_to_pdf.py INPUT.md

# Bootstrap Mermaid dependencies (one-off)
.venv/bin/python scripts/ensure_mermaid_deps.py --auto-install --puppeteer-headless-shell
```

The v1.8.9 tests under `tests/test_md_to_pdf_*.py` are intentionally **excluded** by the v2 pytest config (`testpaths` scoped to `tests/unit`, `tests/integration`). Run them via `python scripts/...` directly if needed.

### v2.0 commands not yet implemented (placeholder for later plans)

```bash
# Plan 2:  brand resolution
md-to-pdf brand list | brand show <id> | brand validate <path> | brand migrate <path>

# Plan 4:  watermarks + audit + determinism
md-to-pdf INPUT.md -o OUTPUT.pdf --brand acme --watermark-user "$USER" --deterministic

# Plan 5:  environment diagnostics
md-to-pdf doctor
```

## Asset reference

- **Reference quotation system** (real TJI HK quote with full enterprise schema): `examples/contributed/quotation/` — informs v2.1's `quote` template's front-matter schema. **Not** a v2.0 deliverable; do not port it now.
- **Existing brand pack** at root `brand_kits/` — the v1 reference brand. The `md-to-pdf brand migrate` command (v2.0 deliverable) targets exactly this layout.
- **Existing fixtures**: `fixtures/uat-*.md` are the v1-parity golden test inputs. `fixtures/branch_ops_ai_robot_product_brief.md` (foundation spec §7.2.1) is to be authored as part of v2.0 work.

## Working with the user

- The user is on macOS, works in VS Code with Claude Code and also uses Cursor.
- The user reads and writes Chinese (Simplified) and English; CJK rendering quality is a hard requirement.
- Spec discussions happen in detail — when a question is ambiguous, ask one question at a time rather than batch.
- The user split the design into two specs (foundation vs roadmap) deliberately to keep v2.0 ruthlessly scoped. Respect that boundary.

## Where to put new things

| New artifact | Path |
|---|---|
| Plan 2/3/4/5 implementation plans | `docs/superpowers/plans/<YYYY-MM-DD>-md-to-pdf-v2.0-plan-N-<topic>.md` (Plan 1 + its review patch already exist) |
| Future spec revisions | `docs/superpowers/specs/<YYYY-MM-DD>-<topic>.md` |
| New module code | `src/mdpdf/<area>/` (existing: pipeline, errors, cli, logging, markdown, render, cache; later: brand, fonts, renderers, security, i18n) |
| New tests | `tests/unit/<area>/`, `tests/integration/`, `tests/golden/` (added in Plan 5) |
| Walking-skeleton fixture | `tests/integration/fixtures/hello.md` (already exists) |
| Comprehensive UAT fixture | `fixtures/branch_ops_ai_robot_product_brief.md` (Plan 5 deliverable) |
| Examples for users | `examples/brands/`, `examples/inputs/` (Plan 2 / contributed) |
| Documentation site | `docs/` (mkdocs-material; not yet scaffolded — Plan 5) |

## When you're unsure

If a request could be interpreted as v2.0 vs v2.x scope, **assume v2.0 and confirm**. The roadmap doc shows what's coming later; respecting that boundary keeps v2.0 shippable.

## Appendix · General LLM Behavioural Guidelines

General-purpose guidelines (sourced from [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills)) that complement the project-specific rules above. Bias toward caution over speed; for trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
