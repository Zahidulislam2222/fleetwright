# Deployment and release verification

The current deployment uses an existing single server, immutable release directories and Docker
Compose. It is a release target; local committed source remains authoritative. Only the edge web
service binds a loopback port behind the TLS proxy. Databases, Redis, owned destinations and
workers share a private backend network without general internet egress.
Every browser worker's configured container stop grace must exceed its typed application drain
timeout; check freight and approved-workflow workers individually, and the crawler when present.
Verify old slots become stopped across a replacement; retain historical records and
investigate stale active rows rather than removing them from health checks.

## Release inputs and gates

Deployment-specific paths, hostname, resource limits and backup paths belong to
`deploy/deploy.config.json`. Backend settings belong to the typed environment boundary; image
data-service digests come from `infra/compose/local.yaml`. The web base digest/build inputs and
unique web image tag belong to the deployment configuration; exact OS patch versions live in
`config/web-security-apk.txt`. Secrets remain in protected environment files.
`node deploy/build-release.mjs <YYYYMMDD-name>` refuses uncommitted release inputs and creates
static output, rendered web/Compose/backup configuration, exact committed backend `src.tar`,
full commit metadata and a SHA-256 manifest. Release IDs are immutable.

1. Snapshot/hash the current live release and private environment; reconcile drift locally first.
2. Run behavior, lint, types, build, configuration and source-security gates; review the diff.
3. Commit under the repository owner's established identity. Build the immutable release.
4. Rehearse from its source archive under an isolated local Compose project. Exercise password/TOTP,
   CSRF/roles, public limits, owner approval, both browser workflows, evidence and SSE revocation.
5. Upload to a new release directory and verify every manifest entry before starting it.
6. Build both application and web images from the archive. Pass the configured immutable base as
   `WEB_BASE_IMAGE` to `deploy/docker/web.Dockerfile`; it has no implicit base fallback. Scan both
   native server images and record their inspected identities and native SBOMs. Include web image
   metadata/SBOM as additional signed primary release artifacts before finalizing the signature.
7. Gracefully stop freight, approved-workflow and present crawler workers before recreating any
   dependencies. Verify successful non-OOM exits and released holds. Keep old control available
   until every configured legacy stream has zero unread/pending work and no unexplained dead letters.
8. Stop old control, validate a fresh pre-migration archive, then apply reviewed migrations and
   idempotent seed. Verify trusted image identities immediately before startup; start the separate
   control, freight, workflow and crawler services using the reviewed release configuration.
9. Verify origin/public HTTP and TLS, authenticated behavior, destination receipts and service state.
10. Verify every deployed artifact hash and running image identity, record release/commit and retain rollback.

## Scheduled backup service

The release contains `backup.service` and a minimal `backup.env`. The host command uses the
existing Docker CLI; it does not require database passwords in arguments or a public database port.
Install a host virtual environment from the release source with the same frozen lockfile. A pinned
uv binary is already present in the application image and can be copied to a root-owned host tool
directory; use it with the existing Python 3.12 interpreter and `uv sync --frozen --no-dev --no-editable`.
See [uv's container guidance](https://docs.astral.sh/uv/guides/integration/docker/).

Install backup environment mode 0600, backup directory mode 0700 and the generated unit under the
host service manager. Validate the unit, start/enable it, then verify a real archive and manifest,
permissions, service restart behavior and source/config hash parity. The unit invokes the existing
typed backup loop; interval and retention are owned by `BackupSettings` / `FW_BACKUP__*`, rather
than a second timer policy. Docker authority is host-administrator authority; never expose it to
MCP clients or mount the host Docker socket into untrusted browser containers.
When replacing an active unit with a newer immutable release, reload the service-manager
configuration and explicitly restart it. Enabling an already-running unit does not replace its
process. Verify the running process uses the new release directory and produces a fresh archive.
See [systemd service semantics](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html).

Local archives do not establish off-host disaster protection. Add an approved independent encrypted
copy, monitor backup age/failure and prove restoration with configuration and keys.

## Rollback and data safety

The durable-detection mailbox upgrade is a **backend compatibility boundary**. The previous rc5
relay accepts only claim messages; it can reject new detection messages or prune published rows
whose detection decision has not committed. Do not restart that old control/worker backend against
the upgraded database and queues. Keep the compatible backend and roll back only static web
assets, or deploy a reviewed forward fix. A full backend rollback requires a separately tested
mailbox-preserving migration/export/import procedure; it is not the normal rollback path.

Before this upgrade, gracefully stop ALL browser/execution workers: freight watchers/actors,
the approved-workflow worker, and the crawler when present. Keep the old control loop available.
Verify each stopped container exited successfully, was not OOM-killed, released its account holds
and left post-action uncertainty inspectable. Do not recreate dependencies while any old actor is
still running. Verify every configured cell's legacy detection streams have zero unread
and pending messages, with no dead-letter backlog, then stop the old control loop and take a fresh pre-migration archive. Abort the
upgrade if the backlog cannot be accounted for. Migration cannot make a previously unpersisted
Redis-only detection durable retroactively. Keep the old stream data and private evidence.

Rehearse static-only rollback with a pending durable detection: replace only the web service's
static/config mounts, keep all backend image identities unchanged, then restore the current web
mounts. Verify public pages/API and the pending mailbox record survive both changes. The current
release pointer continues to identify the compatible backend; record a temporary static override
explicitly. Stop the new monitor before any deliberately incompatible full backend recovery.

Retain the previous manifest/image and use the same Compose project/volumes when rolling back.
Check schema compatibility first: additive workflow migrations preserve old freight tables, but
an older API cannot supervise new jobs. Pause new execution if its UI/worker authority would be
inconsistent. Never drop volumes or run destructive database downgrade as a routine rollback.
Reconcile any accepted/unknown actions after recovery; redeployment does not undo destination work.

Hash parity proves deployed bytes match the release, not service correctness. Both hash checks and
behavioral verification are required. See [runbooks](runbooks.md), [workflow operations](reliable-browser.md)
and [recovery objectives](../scaling/slo.md).

## Exact image identity before and after startup

Verify the entire finalized artifact with the configured separately trusted signing key before
starting services. The application and web images have different identities: map each backend role
to the signed application image and the web role to its separately attested web image. A tag is a
locator, not identity proof. Compare the actual immutable IDs immediately before Compose startup
and the running containers' IDs afterward. Reject a missing, substituted or mismatched image.

Retain native SBOMs and scanner findings for both deployment images. Local and server builds may
differ; scanning a locally built image cannot establish the server image's condition. Verify static
served-file hashes as well as artifact-directory parity. A signed inventory does not itself prove
service correctness, secret hygiene or vulnerability absence. See
[exact release verification](../../tools/security/release-artifacts.md).

## Acceptance and operational handoff

The deployed release is completion rc4 from source `bee3ebfc`. Exact signature/native
image checks, local MCP/browser/crawler/HTTP/CSP flows and all-worker lifecycle checks passed.
Its configured 60-second grace was exercised for freight, approved-workflow and crawler stops.
The crawler resumed across separate processes after natural lease expiry with a higher fence.
Static-only rollback preserved the pending mailbox record and backend identities, then restored
current mounts and resumed control. Production migration/seed/startup, public MCP/UI/HTTP/TLS,
eight-role native image identity and all 146 artifact manifest entries passed. The backup service
is active/enabled with current-release process directory, unit/environment parity and all 222
source hashes verified. Monitoring/recovery and publication retain their own evidence. Use the
[release record](../releases/2026-10-13.md) for installation status.

Final public CSP observations passed all 15 hydrated routes. A fresh post-activity archive
restored into two new databases with workflow row parity; a single backup-process death recovered
under supervision in 70.13 seconds and produced another valid archive. These checks do not
establish whole-host recovery or a measured RPO/RTO.

Before closing a rollout, verify protected backup/monitor service working directories and config
hashes, a fresh archive, observe-only grant renewal and an independent encrypted restore. Record
remaining risks, support/incident ownership, retention and the next restore exercise. Keep private
host paths, credentials, raw reports and browser artifacts out of public documentation.
