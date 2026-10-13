# Maintenance and release policy

## Release gates

Write acceptance criteria before a substantive change. Run the isolated database/browser suite,
Python and dashboard lint/type checks, package and frontend builds, configuration tests, source
security scans and dependency audits. Get independent review. Retain failures and their fixes in
the defect record. A clean source scan and a clean dependency audit are separate results.

Production deployment follows [the runbook](operations/runbooks.md): detect drift, prepare locally,
commit, build an immutable artifact, rehearse, deploy, verify behavior and prove manifest parity.
Preserve the previous release and database volumes. Review schema compatibility before rollback;
restarting old code is not a substitute for assessing migrations and new persisted states.

## Dependency and vulnerability management

Use locked Python and frontend dependencies. Verify registry packages and published advisories
before upgrades. Rebuild the exact image and rerun affected transport/browser tests. Patch runtime
security issues promptly according to severity, exposure and customer impact. Coordinate sensitive
reports through [SECURITY.md](../SECURITY.md).

Current known finding: the development lint dependency chain includes `braces` 3.0.3 under
[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). At the last verified audit,
there was no patched release. Python and npm production audits were clean; the full npm audit
was not. This package is not part of the application runtime and the reviewed root-directory
pattern configuration is unused. Reassess on each tooling update; no finding is suppressed.

## Routine operations

| Frequency | Action | Evidence |
|---|---|---|
| Continuous | Watch service health, queue age, UNKNOWN age, outbox backlog and authorization failures | Monitoring history and actionable incident |
| Daily | Confirm scheduled backup completion, archive integrity and available storage | Manifest timestamps, hashes and scheduler status |
| Per release | Gates, compatibility, backup, rehearsal, smoke and parity | Commit, immutable manifest and verification record |
| Quarterly target | Restore onto an isolated environment; rotate recovery responsibilities | Measured recovery time and integrity report |
| Per customer/target change | Review authorization, data scope, region, retention and rate policy | Updated onboarding decision |

Frequency is an operational policy; production collection, alert delivery and off-host retention
must be explicitly configured and verified for each deployment. Local restore proof alone does
not establish disaster recovery for the hosting provider.

## Accessibility and documentation

Keep keyboard navigation, focus return, contrast, reduced motion and responsive layout checks in
the release process. WCAG 2.2 AA is the accessibility target; existing automated checks cover a
subset, not a certification. Consult [WCAG2.2](https://www.w3.org/TR/WCAG22/) for full criteria.
Update the root/component READMEs, API contract, architecture, operations, threat model, roadmap
and changelog in the same release. Keep public material free of credentials and private host detail.

## Release compatibility and documentation ownership

Review the stop grace for every browser worker, verify graceful shutdown before dependencies change,
and preserve mailbox state across upgrades. Static rollback must keep compatible backend identities;
an old backend cannot be restarted against new topics merely because its image still exists.

Public documentation is maintained with source: all component READMEs, current architecture,
generated contracts, configuration templates, operations, security/legal registers and roadmap.
Update measured evidence with workload/scope and retain historical results as historical. Keep
future 1M+ user and availability objectives separate from contractual commitments.

The most recent native final application/web scans reported zero HIGH/CRITICAL findings; retain
the exact scan/image identity and rescan before each release. This does not erase development-only
audit findings or lower-severity dynamic findings. Current acceptance records preserve the inline
style CSP exception and cross-origin isolation limitation rather than suppressing them.
