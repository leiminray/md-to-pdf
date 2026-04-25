# CLAUDE.md — md-to-pdf

Project guidance for AI agents working in this repo. Read this first; it overrides anything you may remember from training data about how to invoke the tool.

## What this project is

A **Markdown → PDF** conversion engine targeted at enterprise use:
- Brand kits (logo, colours, fonts, footer, compliance text)
- Watermarks for data security
- Mermaid diagrams, syntax-highlighted code, embedded images, CJK text
- PDF bookmarks + table of contents
- Designed to ship as an open-source tool consumable from CLI, Python API, Claude Code / Cursor / Gemini CLI skills, MCP servers, and GitHub Actions.

The repo is currently in a **transition state**: v1.8.9 (a 3,443-line monolith) is the working tool, while v2.0 (a modular refactor) is fully designed but not yet implemented.

## Repository state today (do not assume otherwise)

| Layer | Status | Location |
|---|---|---|
| **v1.8.9 monolith** | ✅ Working — what `SKILL.md` and `README.md` describe | `scripts/md_to_pdf.py`, `scripts/brand_pack.py`, `scripts/fenced_rl.py`, `scripts/ensure_mermaid_deps.py` |
| **v2.0 foundation** | 📋 Designed, not yet implemented | Planned at `src/mdpdf/` (does not exist yet) |
| **v2.x roadmap** (templates, MCP, L3-L5, PDF/A, …) | 📋 Designed for later versions | Spec exists; **do not implement in this round** |
| **Single brand pack** | ✅ Working at root `brand_kits/` | Will become a v2 brand and migrate via `md-to-pdf brand migrate` once v2.0 ships |
| **Bundled CJK fonts** | ✅ Noto Sans SC OFL | `fonts/` (~20MB, kept in repo for v1.8.9; v2.0 makes them an opt-in extra) |
| **Tests** | ⚠️ ~20% coverage on v1.8.9 | `tests/` (4 pytest files, mostly unit) |
| **Specs** | ✅ Authoritative for next work | `docs/superpowers/specs/` (see below) |
| **Implementation plans** | ⏳ To be authored | `docs/superpowers/plans/` (currently empty) |

## Authoritative spec documents (read before writing code)

| Doc | Purpose | When to consult |
|---|---|---|
| [`docs/superpowers/specs/2026-04-26-md-to-pdf-v2.0-foundation-design.md`](docs/superpowers/specs/2026-04-26-md-to-pdf-v2.0-foundation-design.md) | **v2.0 MVP scope** — what we're building right now | Always — this is the build target |
| [`docs/superpowers/specs/2026-04-25-md-to-pdf-v2.x-roadmap.md`](docs/superpowers/specs/2026-04-25-md-to-pdf-v2.x-roadmap.md) | Long-term vision v2.0 → v2.4 (templates, MCP, L3-L5, PDF/A, dual engine) | Only when designing forward-compatibility hooks; **do not implement** anything past v2.0 |
| [`SKILL.md`](SKILL.md) | v1.8.9 invocation (legacy, still works) | When user asks to render a PDF *today* (use v1.8.9; v2.0 not built) |
| [`README.md`](README.md) | v1.8.9 setup (venv, Mermaid, fonts) | Same |

If the two specs disagree on a feature, the **v2.0 foundation spec wins** for implementation; the roadmap is reference only.

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

**`markdown-it-py` parity vs the v1.8.9 regex parser.** Until every existing fixture in `fixtures/uat-*.md` (plus the new `fixtures/branch_ops_ai_robot_product_brief.md`) produces diff-zero output through the new pipeline, do not move past Step 1 of the implementation plan. See foundation spec §2.1.3 and §7.2.

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

### v1.8.9 (works today)

The v1.8.9 SKILL.md describes the path as `.cursor/skills/md-to-pdf/.venv/...` but in this repo the layout is at the project root:

```bash
# Render a markdown file
.venv/bin/python scripts/md_to_pdf.py INPUT.md -o OUTPUT.pdf

# With watermark
MD_PDF_WATERMARK_USER="alice@example.com" .venv/bin/python scripts/md_to_pdf.py INPUT.md --watermark

# Skip Mermaid (faster; no Chromium dependency)
MDPDF_SKIP_MERMAID=1 .venv/bin/python scripts/md_to_pdf.py INPUT.md

# Run tests
.venv/bin/pytest tests/

# Bootstrap Mermaid dependencies (one-off)
.venv/bin/python scripts/ensure_mermaid_deps.py --auto-install --puppeteer-headless-shell
```

### v2.0 (not yet built — placeholder for when implementation lands)

```bash
# Will be:
md-to-pdf INPUT.md -o OUTPUT.pdf --brand acme --watermark-user "$USER"
md-to-pdf brand list | brand show <id> | brand validate <path> | brand migrate <path>
md-to-pdf doctor       # environment diagnostics
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
| Implementation plan for v2.0 | `docs/superpowers/plans/` (currently empty) |
| Future spec revisions | `docs/superpowers/specs/<YYYY-MM-DD>-<topic>.md` |
| New module code | `src/mdpdf/<area>/` (does not exist yet — create when implementing) |
| Tests | `tests/unit/`, `tests/integration/`, `tests/golden/` |
| Examples for users | `examples/brands/`, `examples/inputs/` |
| Documentation site | `docs/` (mkdocs-material; not yet scaffolded) |

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
