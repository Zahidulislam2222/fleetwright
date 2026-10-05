# Runbooks

Short, repeatable procedures. Each one says when to use it, the steps, and how to confirm it worked.
Procedures marked **(target)** describe the cloud reference architecture and have not been drilled
yet.

## Deploy (single server)

When: shipping a change to the public site.

1. **Check drift first.** Fetch the live versions of every file you will replace and compare hashes
   with local. If the server is ahead of local, stop and bring those changes into local first.
2. Build an immutable release: `node deploy/build-release.mjs <YYYYMMDD-name>`. It writes the static
   export, web server configuration and a `MANIFEST.sha256`.
3. Upload the release folder to a new release directory on the server; never edit files in place.
4. Switch the active release, reload the web container, and check the health path.
5. **Confirm parity:** hash every deployed file on the server and compare with the manifest. Record
   the result.

Rollback: switch back to the previous release directory and reload; releases are never modified.

## Rotate a secret

When: on schedule, on staff change, or if a secret may be exposed.

1. Generate the new value (never in shell history or logs).
2. Store it in the secret manager / server environment and in the owner's private credential
   record.
3. Restart the services that read it, one at a time.
4. Revoke the old value. For console sessions, revoke all sessions of affected users.
5. Confirm: services healthy, logins work, old value rejected.

**Vault master key:** add the new key with a new `key_id`, restart, re-seal records in batches
(each record names its `key_id`), then retire the old key after every record has moved.

## Restore the database (target)

1. Restore to a **new** instance from point-in-time backup.
2. Run migrations to the current head.
3. Integrity checks: row-level security still forced on every tenant table; no claim in `ACTING`
   without a lease; outbox relay drains.
4. Switch the services' DSN, restart, watch error rates.
5. Record the restore time against the RTO target.

## A cell fails (target)

1. Symptoms: one cell's dispatch latency rises or its Redis is unreachable; other cells normal.
2. Claims for that cell's tenants stay safe in Postgres. Nothing is lost.
3. Either restore the cell's Redis (the outbox relay re-publishes pending work) or move its tenants
   to a healthy cell (`move_tenant`), which hands over queued claims without duplicates.
4. Confirm: queued claims drain; no duplicates in the claims audit.

## A booking outcome is uncertain

1. Claims in `UNKNOWN` are resolved automatically by the reconciler against the target.
2. If a claim stays `UNKNOWN` (for example the account's session cannot be restored), an operator
   checks the account on the target by hand and resolves it; the action is audit-logged.
3. Never re-queue an `UNKNOWN` claim.

## Incident response

1. **Declare** the incident and name one owner.
2. **Contain**: stop the affected cell, worker group or account; revoke suspected sessions or
   secrets.
3. **Investigate** with the claim history, audit log and failure evidence (traces, screenshots).
4. **Recover** and confirm against the evidence.
5. **Notify**: affected clients without undue delay; for personal-data breaches the controller
   informs the supervisory authority within 72 hours where GDPR requires it.
6. **Review** in writing within five working days: timeline, root cause, fix, the check that
   would have caught it.

## Vulnerability handling

1. Receive the report privately ([SECURITY.md](../../SECURITY.md)) and acknowledge it.
2. Reproduce, rate severity, and decide the fix window.
3. If the vulnerability is actively exploited in a released product under the EU Cyber Resilience
   Act: early warning within 24 hours, notification within 72 hours, final report within 14 days
   through the official reporting platform.
4. Fix, release, and disclose in coordination with the reporter. Credit the reporter if they wish.
