# Fleetwright — rules for coding agents

Read this before changing anything. It states this repository's commands, conventions, protected
areas and local gates. `CLAUDE.md` (local, not tracked) only imports this file, so both stay identical.
The owner's global engineering rules apply too; they are referenced here by number, not copied.

## Orientation

- Product and architecture overview: [README.md](README.md), [docs/README.md](docs/README.md),
  [docs/architecture/](docs/architecture/), ADRs in [docs/adr/](docs/adr/).
- Design usage: [DESIGN.md](DESIGN.md). Contributor order of gates: [CONTRIBUTING.md](CONTRIBUTING.md).
- Private, untracked context (exists only on the owner's machine): the project dossier (requirements
  §2, architecture §3), `memory/` (current state and handoffs), `TASKS.md` (tracker), the build plan
  and the credentials file. Read memory and the tracker first; documents orient, source and tests prove.

## Layout

- `apps/coordinator` — FastAPI `/v1` console API, auth, demo controls, workflows, crawls, assistant.
- `apps/gateway` — live-update stream. `apps/worker` — Playwright runtime. `apps/mockboard` — the
  fictitious demo load board (test target). `apps/dashboard` — Next.js landing + console.
- `packages/fw_core` — settings (the only configuration boundary), DB, claims, crypto, workflows.
- `packages/fw_queue`, `fw_browser`, `fw_mcp`, `fw_agent` — streams/sessions, browser, MCP, local agent.
- `config/` — validated YAML/JSON product data (demo catalogue, prompts, assistant knowledge).
- `infra/`, `deploy/` — Compose, Postgres roles, Terraform reference (plan only), release tooling.

## Commands (gates — all must pass before a change is called done)

```bash
cd apps/dashboard && npx next typegen && npm run lint && npm run typecheck && npm run build && cd ../..
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run python tools/dev/run_tests.py -q
gitleaks detect --no-banner && bandit -q -ll -r .
```

Semgrep (`p/security-audit`) runs in pre-commit and in `.github/workflows/security.yml`.

Build the dashboard before the full suite (the real login test serves that build). Never reset the
development databases; the test runner creates its own `*_test` databases.

## Conventions

- Python 3.12, ruff line length 120, mypy strict, async SQLAlchemy with static parameterised SQL.
- Every environment-dependent value goes through `fw_core.settings` and `.env.example` (global Rule 12);
  copy, prompts and maintained content live in `config/` or `apps/dashboard/src/content/`, not in logic.
- Every tenant table has `tenant_id` + row-level security; every list is bounded; every external call
  has a timeout. Roles are checked server-side on every endpoint; mutations need CSRF and write audit.
- Tests live next to the code (`apps/*/tests`, `packages/*/tests`). Root `/tests/` is the owner's
  private manual folder — never delete or commit it (Rule 13).
- Add a dependency only for a stated need with no existing equivalent (Rule 14). Keep `/v1` API and
  event contracts compatible, or version them (Rule 23).
- Follow the recorded stack and design; propose substitutions with reasons before implementing (Rule 25).

## Protected areas — do not change without an explicit owner request

- Deployment, pushes, paid services or model calls (Rules 5/9). A money warning comes first, always.
- `my-project-view/` and the Google Doc/PDF (Rule 6).
- Credentials, `.env`, keys, private dossier/memory files: never print, commit or copy values (Rules 8/12).
- Security hooks, scanners and pre-commit: never disable, suppress or bypass findings (Rule 14).
- Live server: snapshot and drift-check before any deployment; prove byte parity after (Rule 9).

## Done means

Acceptance criteria written first, gates green, the real flow exercised, a fresh-context review,
defects logged in `DEFECT-LOG.md`, and the dossier, memory and tracker updated (Rules 11/15/25).
