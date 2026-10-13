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
| Input/network | Parameterized SQL, validated contracts, action/body limits, crawler DNS/IP pinning, redirect rejection and bounded fetch processes | Public crawl origins need explicit onboarding/egress review; local agent supports controlled form/receipt destinations with HTTP/WS guards |
| Deployment | Private backend network, loopback edge binding, non-root/read-only app containers, limits and dropped capabilities | PostgreSQL init has explicitly required capabilities; host/Docker administrators remain trusted |
| Web security | CSP, nosniff, frame/referrer/permissions policies, production TLS and exact inline-script hashes | Fifteen exact rc4 rehearsal routes passed full ten-second browser checks; inline styles and absent COEP remain explicit ZAP exceptions |
| Supply chain | Lockfiles, pinned upstream images and patch packages, source/native-image scans, CycloneDX inventories and offline Ed25519 release signatures | Verified rc4 native app/web scans each have zero HIGH/CRITICAL; every subsequent release repeats identity/signature/scan gates; no external certification |
| Recovery | Verified archives, hash refusal, fresh restore tests, independent encrypted copy and local table-row parity | Full-host/key/application disaster recovery remains distinct from data-only restoration |

## Verified release boundary and exceptions

The recorded full npm dependency scan retains one development-only HIGH finding:
`braces` 3.0.3, [CVE-2026-93687](https://avd.aquasec.com/nvd/cve-2026-93687), through Next ESLint.
The scanner returned no fixed version; this does not prove no upstream remedy exists. Its raw
exit is 1. The reviewed trusted-build exception is supported by the dependency tree, the final
static image's native SBOM and actual Node/npm/package-tree absence checks. Reassess the finding;
do not suppress it or report the full dependency scan as clean.

Native verification of `20261013-free-local-rc4`, source `bee3ebfc`, found zero HIGH/CRITICAL vulnerabilities in each
actual server app/web image, with 1,094 and 72 SBOM components respectively. Image/report hashes
were checked, and the actual backend passed real Chromium navigation/isolation and module imports.
The frozen runtime Python audit found zero vulnerabilities across 52 external distributions;
workspace packages remained under source review rather than public package lookup.

The exact rc4 passive web baseline completed in 78.450 seconds: zero HIGH, one MEDIUM inline-style
CSP warning, one LOW COEP warning and six informational alerts; raw exit 2 reflects warnings.
Rehearsal image/release/static identities remained unchanged. It did not test all authenticated attack paths.
Exact-image results, source tests and live deployment checks are separate. A later release must
pass its own promotion gates. Deployed rc4 public MCP/UI/HTTP and signed parity checks passed;
see the release record for operational and publication boundaries.

The full source suite passed 274 cases with six expected skips in 762.41 seconds. The signed
inventory binds 144 primary artifacts, including native web identity/SBOM evidence. All 222 source
files matched committed bytes; actual served static hashes matched all 129 manifest files.
Exact freight/workflow/crawler graceful stops, natural-lease crawler recovery and static-only
mailbox-preserving rollback passed separately from source tests.

## Operator responsibilities

Protect the signing and encryption keys separately from public verification keys. Verify the
signature and complete manifest before extraction or activation; preserve the prior release and
compatible rollback boundary. A valid local signature authenticates approved bytes under that
key, not the safety of all behavior or a third party's assessment.

Maintain destination permission records, least-privilege accounts, private evidence/archives,
monitored backup age and restore checks. Review dependency advisories regularly and after new
images or packages. Validate security controls on the exact rendered deployment, including TLS,
trusted proxy headers, session flags, health probes and shutdown grace versus drain deadlines.
Report incidents through [the security process](../../SECURITY.md) and assess the
[applicable legal notification duties](../legal/README.md).

## Next assurance work

Assess against [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/),
record control-by-control evidence and perform an authorized dynamic assessment. Test malicious
page content, destination redirects, new adapter origins, artifact access, session lifecycle,
recovery keys and multi-zone failure. Security reports follow [SECURITY.md](../../SECURITY.md).
