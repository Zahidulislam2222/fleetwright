# Configuration data

Validated YAML/JSON product data, loaded at start-up. Environment settings (URLs, secrets,
timeouts, model ids, prices, budgets) are **not** here; they come from environment variables (see
[configuration](../docs/operations/configuration.md)). An invalid file stops its service with a clear error.

Current release: `20261125-publication-rc1` (application code from the assistant release `20261125-assistant-rc5`) ([25 November 2026 record](../docs/releases/2026-11-25.md)).

| Data set or file | Contents |
|---|---|
| `targets.yaml` | Authentication selectors and identity API; freight-capable targets additionally define feed/booking paths |
| `browser.yaml` | Browser profiles and which account group uses which |
| `proxy.yaml` | Proxy providers (local provider by default) |
| `board_catalogue.yaml` | Owned freight exchange: maintained lanes, equipment and rates, banner, and the collapsed visitor guide (`branding.guide`, including the `console_label` shown before the console address) |
| `workflows.yaml` | Validated workflow inputs, action identity, browser forms, receipts and operator messages |
| `testing.yaml` | Isolated local test database names |
| `crawls.yaml` | Same-origin crawl seeds, extraction selectors, field/type limits and robots policy |
| `crawl_catalogue.yaml` | Maintained records for the owned paginated crawler destination |
| `agent.yaml` | Maintained local-model templates, prompts, source/form/receipt contracts and UI copy, including the AI-generated and human-edited draft labels |
| `demo.yaml` (file name is historical) | Public workspace seed and preset policy: account groups, filters/schedules, capped workspace controls and owned fault presets |
| `assistant.yaml` | Console help assistant: AI disclosure, human contact route, suggested questions, fallback messages, system prompt, read-only tool descriptions and the list of approved public documents |
| `assistant-knowledge.json` | Generated keyword-search index of those public documents (`version`, `sources`, `sections`); never edited by hand |
| `assistant-eval.yaml` | Held-out evaluation cases and pass thresholds for the paid, opt-in live evaluation |
| `uptime.json` | Independent public HTTPS checks and bounded collector settings |
| `container-security-*.txt`, `web-security-apk.txt` | Reviewed exact image package patch/removal inputs |
| `release-signing-public.pem` | Public verification key; private signing material remains ignored |

Authentication-only targets require `name`, `login`, `captcha` (explicitly `null` when absent),
and `api.me` / `api.csrf_header`. They do not need freight endpoints. Legacy freight workers
select only complete freight target contracts, leaving service-only accounts available to
the general workflow runner. Both verified workflows currently use the owned board account.

See [maintenance](../docs/maintenance.md) for release and configuration review.

## Help assistant data

- **Knowledge.** After changing any document listed under `knowledge_sources` in `assistant.yaml`,
  rebuild the index with `uv run python tools/dev/build_assistant_knowledge.py`. A test fails when
  `assistant-knowledge.json` no longer matches the documents. Only public documentation belongs in
  that list: the assistant quotes it to any visitor.
- **Prompt and copy.** `version` labels the prompt and knowledge release and is copied into the
  generated index. Provider, model, prices and limits are `FW_ASSISTANT__*` settings, not data here.
- **Evaluation.** `assistant-eval.yaml` sets the pass rate, the must-pass safety cases (prompt
  injection, key extraction, write attempts, off-topic and captcha-help refusals, refusing the owner's private contact details),
  a p95 latency ceiling and per-question and per-run cost caps. Running it makes paid model calls
  and needs explicit cost approval; the current release's result is in the
  [release record](../docs/releases/2026-11-25.md). Re-run it after prompt, model or knowledge changes.

## Change control

Change destination scope, selectors, model prompts or allowed fields here, then validate against
current typed loaders and run affected real-flow tests. Workflow contract changes invalidate older
approval fingerprints. Do not repurpose an existing action identity for changed inputs.

Environment URLs/model IDs/storage paths/limits and secrets belong to typed settings, never copied
into control-flow modules. Public signing keys may be committed; private keys and actual credentials
must remain outside this directory. Keep local/VPS environment templates and the generated settings
schema synchronized. See [configuration ownership](../docs/operations/configuration.md).

## Data review and publication

Every maintained data change has a loader/schema owner and an affected behavior check. Workflow
inputs, account groups and receipt rules must remain aligned across seed, API, MCP and workers.
A changed contract fingerprint requires fresh human approval. Crawler extraction/robots policies,
local-agent prompts and the help assistant's prompt and knowledge follow their own bounded
validation paths.

Keep records used for owned verification identifiable as operator-controlled data. Actual customer
records and credentials belong in approved private storage. Review legal/data obligations with
[commercial readiness](../docs/legal/commercial-readiness.md) and
[data lifecycle](../docs/security/data-lifecycle.md); publish only scrubbed configuration examples.
