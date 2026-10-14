# Threat model

Current release: [14 October browser recovery](../releases/2026-10-14.md). Its native app/web
scans each reported zero HIGH/CRITICAL at the signed identities; source gates, real public flows,
image/artifact parity and fresh operational checks passed. Earlier rc4 measurements below retain
their 13 October boundary; the passive ZAP/dev-dependency exceptions are not new scan results.


Assets: destination credentials/sessions, human authority, action integrity, tenant records,
execution evidence, encryption keys and recoverable backups. Trust boundaries include the public
edge, operator browser, MCP client process, coordinator/database, queue, worker, destination and
host backup service and local agent/API/browser profile. Destination content and model output
are untrusted input. The OS, Docker daemon and privileged infrastructure roles remain trusted
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
Reassess this model when adding destinations, permissions, model providers, storage, cells or
regions. See [controls](controls.md), [legal scope](../legal/acceptable-use.md) and [roadmap](../roadmap.md).
