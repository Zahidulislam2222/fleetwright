# Contributing

Fleetwright is a source-available project owned by one author (see [LICENSE](LICENSE)). Issues
that report bugs or ask questions are welcome. Pull requests are reviewed case by case; please open
an issue first to discuss the change.

Security problems: **do not** open an issue. Follow [SECURITY.md](SECURITY.md).

## How changes are made here

1. **Acceptance criteria first.** Write down what "done" means, or a failing test for a bug.
2. **Smallest change.** One feature or fix per branch.
3. **No hardcoded configuration.** URLs, timeouts, limits, model IDs and secrets go through
   `fw_core.settings` and `.env.example`; product data goes in `config/` YAML.
4. **Gates, all green:**
   ```bash
   uv run ruff check . && uv run ruff format --check .
   uv run mypy
   uv run pytest
   cd apps/dashboard && npm run lint && npm run typecheck && npm run build
   ```
   Security scanners (gitleaks, bandit, semgrep) must pass. Fix findings; never suppress them.
5. **Real behaviour.** Exercise the actual flow (HTTP, CLI or browser), not only unit tests.
6. **Review.** Every change is reviewed against its acceptance criteria before merge.

## Style

- Python 3.12, ruff (line length 120), mypy strict, async SQLAlchemy with static parameterised SQL.
- Tests live next to the code they test (`apps/*/tests`, `packages/*/tests`).
- Comments explain *why*, not *what*.
