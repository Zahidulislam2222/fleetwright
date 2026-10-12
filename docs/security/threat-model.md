# Threat model

Assets: destination credentials/sessions, human authority, action integrity, tenant records,
execution evidence, encryption keys and recoverable backups. Trust boundaries include the public
edge, operator browser, MCP client process, coordinator/database, queue, worker, destination and
host backup service. Destination content and model output are untrusted input.

| Threat | Current mitigation | Residual / next verification |
|---|---|---|
| Account takeover | Password/TOTP, lockout, bounded hashing, cookie/CSRF controls | Guest account is intentionally shared; owner credentials must remain private |
| Model approves its own action | No MCP approval tool; owner console approval bound to exact fingerprint | Human must review exact inputs/account; compromised owner machine remains trusted |
| Approval replay or changed payload | Database-clock expiry, canonical contract hash, one-time consumption | New contract versions require new approval |
| Stale/dead worker repeats accepted action | Fenced leases, ACTING intent, UNKNOWN recovery and receipt reads | Destination may not provide conclusive receipts; operator review then required |
| Tenant crossover / confused deputy | RLS, invocation/job lookup authorization, explicit tenant grant | Privileged system roles and migrations require careful review |
| Revoked client keeps observing/acting | Tool/execution rechecks and idle-stream authorization polling | Data already delivered cannot be recalled; streams close within configured interval |
| Page/prompt injection | Structured allowlisted contracts, owned origin, human approval separate from model | Standalone arbitrary browser agent is not released; broader injection assessment required |
| Credentials in evidence | Safe JSON fields, bounded exports and log filtering | Raw screenshots/traces/archives remain sensitive; no blanket redaction claim |
| Audit crash gap | Shared DB audit transaction; durable external intent and outcome | External operation can remain unresolved after acceptance |
| Target/network denial of service | Timeouts, body/page limits, bounded attempts and queues | Large tenant skew, reconnect storms and slow clients need scale tests |
| SSRF / destination escape | Current owned-origin adapters and internal production network | Arbitrary crawler blocked from release until DNS/redirect/egress guard exists |
| Host or Docker compromise | Hardened app containers and private network | Single host is a shared failure domain; backup Docker authority is privileged |
| Backup loss / tampering | Private permissions, archive/list validation and hashes | Hash alone is not authentication; independent encrypted copy and key recovery pending |
| Dependency compromise | Locked registries, source scans, security CI | Dev-only advisory retained; signed provenance/SBOM/image scanning planned |

Fencing establishes database authority, not universal exactly-once external side effects. The
adapter's evidence semantics and destination constraints must be reviewed for every workflow.
Reassess this model when adding destinations, permissions, model providers, storage, cells or
regions. See [controls](controls.md), [legal scope](../legal/acceptable-use.md) and [roadmap](../roadmap.md).
