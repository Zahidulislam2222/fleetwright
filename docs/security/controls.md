# Security control status

Status below describes implemented source and verification boundaries. It is not an independent
penetration test, ASVS certification or a claim of universal security. Deployment evidence and
source tests are separate; see [testing](../testing.md) and [maintenance](../maintenance.md).

| Area | Implemented control | Boundary / remaining work |
|---|---|---|
| Console identity | Argon2id, password/TOTP flow, bounded hashing, account/network lockout | Shared guest credentials/codes are intentionally public and grant only capped workspace controls |
| Sessions | HttpOnly, Secure production, SameSite=Strict cookies; server token digests, CSRF checks | Local HTTP settings differ; protect operator machines and enforce TLS deployment |
| Authorization | Server role checks; owner-only workflow approval/grants; scoped MCP observe/execute | Review every new route/tool and account permission before expansion |
| Approval | Exact tenant/account/input/contract fingerprint, expiry and one-time consumption | Approval does not authorize a changed action or undo an accepted destination action |
| Revocation | Every MCP call and execution boundary rechecks authority; SSE rechecks while idle | Stream revocation is bounded by configured interval, not instantaneous network erasure |
| Tenant data | Forced PostgreSQL RLS and tenant transactions; cross-tenant tests | Infrastructure/system directory roles remain privileged boundaries |
| At-rest credentials | Per-record AES-GCM envelope encryption with row-associated data | Current master key is environment-managed; external KMS/rotation automation remains planned |
| Execution integrity | DB-clock leases, monotonic fences, atomic transitions and account holds | Arbitrary destinations do not validate Fleetwright fences; receipt contracts remain essential |
| Audit | Database mutations and audit commit together; external intent/outcome records | External acceptance can remain uncertain; hashes are not digital signatures |
| Data exposure | Bounded redacted JSON evidence, masked public views, log filtering | Raw browser artifacts/archives need private access and retention; complete DSR automation pending |
| Input/network | Parameterized SQL, validated contracts, action/body limits, owned-origin browser restrictions | Arbitrary crawl SSRF/egress guard required before crawler release |
| Deployment | Private backend network, loopback edge binding, non-root/read-only app containers, limits and dropped capabilities | PostgreSQL init has explicitly required capabilities; host/Docker administrators remain trusted |
| Web security | CSP, nosniff, frame/referrer/permissions policies, production TLS | Static CSP still permits inline scripts/styles; nonce/hash migration planned |
| Supply chain | Lockfiles, pinned container digests, registry validation, Gitleaks/Bandit/Semgrep gates | SBOM/provenance signing, image scanning and broader dynamic assessment planned |
| Recovery | Verified archives, hash refusal, fresh non-destructive restore tests and scheduled loop | Off-host encrypted copy/full-host/key recovery need operational proof |

## Dependency finding

Full npm audit retains the development-only `braces` 3.0.3 advisory
[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) through Next ESLint.
No patch was available at verification. The identified path concerns repository rootDir patterns,
which this project does not configure; no application runtime import was found. Production npm
dependencies and the Python dependency audit were clean at the recorded verification. Retain and
reassess the advisory; do not suppress it or describe the full audit as clean.

## Next assurance work

Assess against [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/),
record control-by-control evidence and perform an authorized dynamic assessment. Test malicious
page content, destination redirects, new adapter origins, artifact access, session lifecycle,
recovery keys and multi-zone failure. Security reports follow [SECURITY.md](../../SECURITY.md).
