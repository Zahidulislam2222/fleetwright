# Security documentation

Fleetwright treats human authority, tenant isolation, destination permission and uncertain external
actions as separate security boundaries. The model proposes typed work; the operator approves
the exact account and inputs; database-backed authority governs execution and recovery.

| Document | Purpose |
|---|---|
| [Control status](controls.md) | Implemented protections, release verification and operational responsibilities |
| [Threat model](threat-model.md) | Assets, trust boundaries, attack scenarios and residual risks, including help assistant misuse |
| [ASVS assurance map](asvs.md) | Selected OWASP ASVS 5 evidence, unassessed controls and explicit exceptions |
| [Data lifecycle](data-lifecycle.md) | Handling of identities, credentials, records, evidence, profiles, exports and archives |
| [Security reporting](../../SECURITY.md) | Private vulnerability reporting and supported reporting scope |
| [Privacy and legal register](../legal/README.md) | Deployment-specific permission, data protection and incident obligations |
| [Operations runbooks](../operations/runbooks.md) | Deployment, incident and recovery procedures |
| [Supply-chain tooling](../../tools/security/README.md) | Local Trivy scans, SBOMs, provenance signing and verification |

## Current release evidence

The current deployed release is `20261125-publication-rc1` (application code from the assistant release `20261125-assistant-rc5`, source `26ebe46`). Its
[25 November 2026 release record](../releases/2026-11-25.md) is the source for current security
results. Older release records, and the earlier measurements in the ASVS map, keep their dated
boundaries as history.

- **Patched images.** The previously deployed images carried advisories published after the October
  release (application: 1 CRITICAL, 6 HIGH; web: 6 CRITICAL, 19 HIGH). The affected packages were
  upgraded and pinned. Native Trivy 0.75.0 scans of the deployed images then reported 0 HIGH/CRITICAL
  findings for the application image and 0 HIGH/CRITICAL with one MEDIUM for the web image
  (nginx 1.30.8). Next.js was upgraded to 16.4.6 after the CI dependency audit reported published
  advisories.
- **Rejected candidates.** Two release candidates were rejected before activation because native
  image scans found new advisories, and one because a reused web image was vulnerable.
- **Signing.** Ed25519 provenance was verified against the separately trusted key: 145 primary
  artifacts with the application image identity and SBOM bound; the web image identity and SBOM were
  attested before signing. This is an operator-controlled signature, not independent certification.
- **Source gates.** Gitleaks, Bandit (medium and above) and Semgrep `p/security-audit` passed. Semgrep
  blocked one commit; the finding was fixed, not suppressed.

## Help assistant boundary

The console help assistant adds a model provider and the API's only outbound internet route.
Controls, recorded in [ADR 0016](../adr/0016-assistant-provider-egress.md) and the
[threat model](threat-model.md): read-only tools that run as the asker inside the asker's tenant (no
audit or user-list tools, no write tools); documentation and tool results treated as untrusted data;
plain-text answers marked AI-generated; CSRF on signed-in requests; hourly question limits, a
concurrency limit and a daily budget reserved before each paid call (a dedicated provider key with
its own monthly cap is planned); documentation-search fallback for every assistant limit or failure. Fleetwright stores no
question text; provider-side retention follows the provider's terms. Answers can still be wrong.
The release's 16-case live evaluation, including prompt-injection, key-extraction and write-attempt
cases, passed 16/16; that is a release check, not a guarantee.

## Scope of these results

Scan results apply to their exact source/image identities and scan time. Zero reported
HIGH/CRITICAL vulnerabilities does not establish absence of all vulnerabilities, an independent
penetration test or certification. A newer release repeats the relevant artifact gates.

Additions to destinations, model providers, permissions, storage or topology require a threat-model
and legal-scope review. Never submit private keys, account sessions, raw page traces or customer
records through a public issue.

## Data, authority and operational handoff

[Data lifecycle](data-lifecycle.md) assigns handling requirements for identities, credentials,
workflow records, raw evidence, local profiles, exports and archives. Review it alongside the
threat model when adding a destination, provider, storage location or permission.

Security acceptance includes real role/CSRF/revocation behavior, tenant isolation, exact-action
approval, browser recovery, private evidence and verified backup/key recovery. Track unsupported
controls and retained advisories explicitly. [Service ownership](../operations/service-ownership.md)
and [commercial readiness](../legal/commercial-readiness.md) assign follow-up and incident duties.
