# Security documentation

Fleetwright treats human authority, tenant isolation, destination permission and uncertain external
actions as separate security boundaries. The model proposes typed work; the operator approves
the exact account and inputs; database-backed authority governs execution and recovery.

| Document | Purpose |
|---|---|
| [Control status](controls.md) | Implemented protections, release verification and operational responsibilities |
| [Threat model](threat-model.md) | Assets, trust boundaries, attack scenarios and residual risks |
| [ASVS assurance map](asvs.md) | Selected OWASP ASVS 5 evidence, unassessed controls and explicit exceptions |
| [Security reporting](../../SECURITY.md) | Private vulnerability reporting and supported reporting scope |
| [Privacy and legal register](../legal/README.md) | Deployment-specific permission, data protection and incident obligations |
| [Operations runbooks](../operations/runbooks.md) | Deployment, incident and recovery procedures |

Scan results apply to their exact source/image identities and scan time. Zero reported
HIGH/CRITICAL vulnerabilities does not establish absence of all vulnerabilities, an independent
penetration test or certification. The latest verified release evidence and remaining gates are
recorded in [the assurance map](asvs.md); a newer release repeats relevant artifact gates.

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
