# Threat model

Current release: [25 November 2026, `20261125-publication-rc1`](../releases/2026-11-25.md), whose
application code comes from `20261125-assistant-rc5`, which added
the console help assistant. Native Trivy scans reported zero HIGH/CRITICAL in the application image
and zero HIGH/CRITICAL with one MEDIUM in the web image; Ed25519 provenance verified; Gitleaks, Bandit
and Semgrep passed (Semgrep blocked one commit, fixed rather than suppressed). Earlier results are
history: the [15 October publication](../releases/2026-10-15.md) and the rc4 measurements below
retain their 13 October boundary; the passive ZAP/dev-dependency exceptions are not new scan results.


Assets: destination credentials/sessions, human authority, action integrity, tenant records,
execution evidence, encryption keys and recoverable backups. Trust boundaries include the public
edge, operator browser, MCP client process, coordinator/database, queue, worker, destination and
host backup service, local agent/API/browser profile and the help assistant's model provider.
Destination content, documentation passages given to a model, tool results and model output are
untrusted input. The OS, Docker daemon and privileged infrastructure roles remain trusted
administrative boundaries; application controls are not an operating-system sandbox.

| Threat | Current mitigation | Residual / next verification |
|---|---|---|
| Account takeover | Password/TOTP, lockout, bounded hashing, cookie/CSRF controls | Guest account is intentionally shared; owner credentials must remain private |
| Model approves its own action | No MCP approval tool; owner console approval bound to exact fingerprint | Human must review exact inputs/account; compromised owner machine remains trusted |
| Approval replay or changed payload | Database-clock expiry, canonical contract hash, one-time consumption | New contract versions require new approval |
| Stale/dead worker repeats accepted action | Fenced leases, ACTING intent, UNKNOWN recovery and receipt reads | Destination may not provide conclusive receipts; operator review then required |
| Tenant crossover / confused deputy | RLS, invocation/job lookup authorization, explicit tenant grant | Privileged system roles and migrations require careful review |
| Revoked client keeps observing/acting | Tool/execution rechecks and idle-stream authorization polling | Data already delivered cannot be recalled; streams close within configured interval |
| Page/prompt injection | Typed allowlisted contracts, approved owned origins, HTTP/WebSocket guards and approval separate from the model | Local agent supports maintained controlled templates; arbitrary-site autonomy and complete injection resistance are not claimed |
| Help assistant prompt injection (question, documentation or tool result tries to change rules, reveal the prompt or a key, or act) | No write tools, so an injected instruction cannot change state; passages and tool results wrapped as untrusted data; tool names/arguments allowlisted; provider key held server-side and never in the prompt; plain-text output, no links except the maintained contact; held-out cases for prompt and key extraction, write attempts and captcha help passed 16/16 | Complete injection resistance is not claimed; answers can be wrong or misleading; re-run the evaluation after any prompt, model, tool or knowledge change |
| Help assistant data leakage across tenants | Tools run as the asker through the console's own tenant views and RLS; anonymous visitors reach only the public workspace, through the same read views the console already shows them; audit and user lists (the views holding personal data) are not exposed; daily counters only to the public workspace owner; nothing the asker types stored, so there is no cross-user history to leak | Any future answer cache must exclude tool results and tenant data; a new tool needs a cross-tenant denial test |
| Help assistant cost exhaustion (scripted questions, long prompts, tool loops) | Per-user and per-address-range hourly limits; per-process concurrency; bounded question/history/prompt/output sizes, 3 model calls and 4 tool calls per step; daily budget reserved atomically at worst-case price; overflow falls back to documentation search | One deployment-wide budget means an attacker can use up the day's AI answers for everyone (degrading to search, not to cost); per-tenant quotas, budget sharding and a dedicated provider-side capped key are future work |
| Help assistant provider outage, slowness or Redis failure | Per-call timeout and one 25 s whole-answer deadline below the 30 s edge timeout; provider and timeout errors return documentation passages (Redis errors too for anonymous visitors; signed-in sessions need Redis); a timed-out call keeps its reservation | No assistant alert yet; a second provider is a future option that needs its own review |
| Help assistant egress misuse (SSRF from the API) | API calls only the configured provider endpoint and never fetches visitor-supplied URLs; only the API joins the egress network; `backend` stays internal | The API now has a general outbound route; any new outbound feature needs the crawler's egress guard or a provider-only egress proxy ([ADR 0016](../adr/0016-assistant-provider-egress.md)) |
| Credentials in evidence | Safe JSON fields, bounded exports and log filtering | Raw screenshots/traces/archives remain sensitive; no blanket redaction claim |
| Audit crash gap | Shared DB audit transaction; durable external intent and outcome | External operation can remain unresolved after acceptance |
| Target/network denial of service | Timeouts, body/page limits, bounded attempts and queues | Large tenant skew, reconnect storms and slow clients need scale tests |
| SSRF / destination escape | Crawler DNS/IP pinning and prohibited-address checks, redirects rejected, bounded HTTP fetch subprocess; agent HTTP/WS origin guards | New public origins need onboarding/egress review; test DNS changes, TLS, length mismatch, slow drip and malicious links for each expansion |
| Host or Docker compromise | Hardened app containers and private network | Single host is a shared failure domain; backup Docker authority is privileged |
| Backup loss / tampering | Private permissions, archive/list validation, hashes and authenticated encrypted off-host copy with fresh-database restore proof | Full-host/key/application recovery drill and measured RPO/RTO remain |
| Dependency compromise | Registry-verified locks, pinned images/security patches, source scans, native SBOMs and offline signed release manifests | Dev-only npm HIGH retained under reviewed build boundary; exact rc4 native app/web images have zero HIGH/CRITICAL; signatures do not eliminate malicious dependency risk |
| Lost detection during cell move | Durable raw mailbox before Redis, authoritative payload, atomic current-cell dispatch/claim/filter consumption, retries and retention protection | Legacy Redis-only backlog requires explicit zero-backlog upgrade drain; ephemeral gateway hints require refetch |
| Tenant starvation or pool exhaustion | Bounded cell directory pages/tenant turns, account holds/action cooldowns and finite configured pools | Weighted fairness, large skew and multi-zone pool/fan-out capacity remain future acceptance gates |
| Release shutdown exceeds orchestrator grace | Bounded application drain, signal-aware crawler cleanup and durable uncertain state | Exact rc4 freight/workflow/crawler stops passed with configured 60-second grace; recheck after timing changes and inspect successful non-OOM exit/released holds |

Fencing establishes database authority, not universal exactly-once external side effects. The
adapter's evidence semantics and destination constraints must be reviewed for every workflow.

## Failure and abuse assessments

Test both sides of each boundary: an allowed action succeeds, while changed inputs, revoked
authority, another tenant, a stale fence or prohibited destination are refused. Exercise process
death after destination acceptance and retain `UNKNOWN` until conclusive receipt reconciliation.
For streams, distinguish direct bounded-queue overflow from network slow readers buffered by TCP.

At higher scale, test credential attacks, tenant skew, reconnect storms, cache loss, pool overload,
writer failover and loss of a cell/zone together with active work. A healthy container or a passing
passive scan does not establish correctness under those failures. Future architecture and failure
promotion gates are specified in [the scaling design](../scaling/future-architecture.md).
Reassess this model when adding destinations, permissions, model providers, assistant tools,
storage, cells or regions. See [controls](controls.md), [legal scope](../legal/acceptable-use.md) and [roadmap](../roadmap.md).
