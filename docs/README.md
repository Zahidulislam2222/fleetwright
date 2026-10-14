# Fleetwright documentation

Start with [product scope](product.md). New operators should complete local installation,
configuration and destination authorization before enabling actions. Integrators should read the
API/MCP reference and exact-approval contract; service owners should use deployment, monitoring,
recovery and incident runbooks.

Deployed frontend/backend release: `20261014-browser-recovery-rc3`, source `41f5f16`.
Its runtime regression passed 289 cases with six expected skips; exact rehearsal, native image scans,
signatures and lifecycle checks passed. Public workflows/UI/HTTP, signed service-image identities
and deployed artifact parity passed. Use the [release record](releases/2026-10-14.md) for status.

| Area | Documents |
|---|---|
| Product and integration | [Product and boundaries](product.md) · [API and MCP reference](integrations.md) · [Reliable browser workflows](operations/reliable-browser.md) |
| Architecture | [Overview](architecture/overview.md) · [Claim lifecycle](architecture/claim-lifecycle.md) · [Decision records](adr/README.md) |
| Setup and operations | [Local development](operations/local-development.md) · [Configuration](operations/configuration.md) · [Deployment](operations/deployment.md) · [Runbooks](operations/runbooks.md) |
| Crawling and local agent | [Catalogue crawler](operations/crawler.md) · [Standalone local agent](operations/local-agent.md) |
| Monitoring and recovery | [Collectors and free external probes](operations/monitoring.md) · [Encrypted off-host recovery](operations/recovery.md) |
| Portfolio and proposals | [Three capability drafts, technical answers and public case study](proposal-kit/README.md) |
| Security | [Reporting policy](../SECURITY.md) · [Threat model](security/threat-model.md) · [Control status](security/controls.md) |
| Law and privacy | [Legal register](legal/README.md) · [Acceptable use](legal/acceptable-use.md) · [Privacy and retention](legal/privacy.md) |
| Future scale and availability | [1M+ simultaneous users](scaling/README.md) · [Capacity arithmetic](scaling/capacity-model.md) · [Add an execution cell](scaling/adding-a-cell.md) · [99% / 99.9% SLOs and recovery](scaling/slo.md) |
| Assurance and maintenance | [Testing and measurements](testing.md) · [Maintenance and accessibility](maintenance.md) · [Roadmap](roadmap.md) · [Changelog](../CHANGELOG.md) |
| Operating ownership | [Service dependencies and release handoff](operations/service-ownership.md) · [Data lifecycle](security/data-lifecycle.md) |
| Customer and expansion readiness | [Commercial/legal handoff](legal/commercial-readiness.md) · [Tiered scale/availability validation](scaling/validation-plan.md) |

Measured results include their workload and date. Estimates explain assumptions. Targets have
acceptance gates before becoming capacity commitments or contractual service levels.

## Choose a starting path

- **Operator:** [local setup](operations/local-development.md) → [configuration](operations/configuration.md)
  → [approved workflows](operations/reliable-browser.md) or [crawler](operations/crawler.md).
- **Local assistant user:** [standalone app](operations/local-agent.md), including model installation,
  private state, approval, cancellation and uncertain-outcome recovery.
- **Integrator:** [API/MCP](integrations.md) → [architecture](architecture/overview.md) → target onboarding
  in [acceptable use](legal/acceptable-use.md).
- **Service owner:** [release procedure](operations/deployment.md) → [monitoring](operations/monitoring.md)
  → [encrypted recovery](operations/recovery.md) → [incident runbooks](operations/runbooks.md).

Documentation describes implemented contracts and explicit limits. A passed fixture test, an image
scan, a signed artifact and a successful deployment establish different things; none substitutes for
representative customer load or measured monthly availability.

## Complete operating and expansion package

Use [service ownership](operations/service-ownership.md) for process dependencies, health and
shutdown responsibilities; [data lifecycle](security/data-lifecycle.md) for records/evidence/
export/archive controls; and [commercial readiness](legal/commercial-readiness.md) for permission,
license, privacy and support decisions. The [scale validation plan](scaling/validation-plan.md)
connects the future 1M+ session architecture and 99%/99.9% objectives to repeatable promotion gates.

Each component README describes its public contract and operating checks. Dated release records
bind actual measurements to source, signed artifacts and deployment verification. Update those
records after the relevant gates complete, and keep customer data and private access details out
of public issues, documentation and release bundles.
