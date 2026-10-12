# Deployment and release verification

The current deployment uses an existing single server, immutable release directories and Docker
Compose. It is a release target; local committed source remains authoritative. Only the edge web
service binds a loopback port behind the TLS proxy. Databases, Redis, owned destinations and
workers share a private backend network without general internet egress.

## Release inputs and gates

Deployment-specific paths, hostname, resource limits and backup paths belong to
`deploy/deploy.config.json`. Backend settings belong to the typed environment boundary; image
digests come from `infra/compose/local.yaml`. Secrets remain in protected environment files.
`node deploy/build-release.mjs <YYYYMMDD-name>` refuses uncommitted release inputs and creates
static output, rendered web/Compose/backup configuration, exact committed backend `src.tar`,
full commit metadata and a SHA-256 manifest. Release IDs are immutable.

1. Snapshot/hash the current live release and private environment; reconcile drift locally first.
2. Run behavior, lint, types, build, configuration and source-security gates; review the diff.
3. Commit under the repository owner's established identity. Build the immutable release.
4. Rehearse from its source archive under an isolated local Compose project. Exercise password/TOTP,
   CSRF/roles, public limits, owner approval, both browser workflows, evidence and SSE revocation.
5. Upload to a new release directory and verify every manifest entry before starting it.
6. Build the application image from the archive. Back up data, then run additive migrations and
   idempotent seed before API startup. Start freight and approved-workflow workers separately.
7. Verify origin/public HTTP and TLS, authenticated behavior, destination receipts and service state.
8. Verify every deployed artifact hash against local, record release/commit and retain rollback.

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
See [systemd service semantics](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html).

Local archives do not establish off-host disaster protection. Add an approved independent encrypted
copy, monitor backup age/failure and prove restoration with configuration and keys.

## Rollback and data safety

Retain the previous manifest/image and use the same Compose project/volumes when rolling back.
Check schema compatibility first: additive workflow migrations preserve old freight tables, but
an older API cannot supervise new jobs. Pause new execution if its UI/worker authority would be
inconsistent. Never drop volumes or run destructive database downgrade as a routine rollback.
Reconcile any accepted/unknown actions after recovery; redeployment does not undo destination work.

Hash parity proves deployed bytes match the release, not service correctness. Both hash checks and
behavioral verification are required. See [runbooks](runbooks.md), [workflow operations](reliable-browser.md)
and [recovery objectives](../scaling/slo.md).
