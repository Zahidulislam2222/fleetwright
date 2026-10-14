# Operational monitoring

Fleetwright includes a free Python collector with a private SQLite history and JSON notification
sink. Run one collector on the existing server for workflow metrics and archive age, and another
on an independent operator machine for public HTTPS availability. Neither uses a paid monitoring
API. A collector on the production host does not prove independent availability.

## Configuration and use

All settings use the central typed `MonitorSettings`, `ProbeSettings` and optional
`MonitorGrantSettings` models. Set the `FW_MONITOR__*` variables in the environment template,
including the database, notification file and JSON probe list. Probe names must be unique.

```sh
uv run python -m fw_coordinator.monitor once
uv run python -m fw_coordinator.monitor report
uv run python -m fw_coordinator.monitor loop
uv run python -m fw_coordinator.monitor once --settings-file config/uptime.json
```

`once` performs one cycle, prints a safe status report and exits nonzero for any unhealthy check in
that cycle, even before the notification threshold. `report` reads committed history without
contacting any destination. `loop` prints failure/recovery notifications to its local terminal or
service journal and keeps the private JSON sink synchronized from committed notification records.
If the process dies after a database commit, the next recorded check regenerates that sink. These
notifications do not deliver email, SMS, Slack messages or desktop push alerts.

HTTP requests have a configured total wall-time budget, byte ceiling, expected status and no
redirect following. Proxy environment variables are ignored. Public independent probes should use
HTTPS. Credentials, headers, URLs, HTTP bodies and arbitrary exception strings are excluded from
the collector history and notifications. Samples, metric history and notices expire under the
configured retention window; notification output uses the configured latest-record limit.

The authenticated workflow endpoint requires a tenant-bound `observe` grant. The collector accepts
only the fixed workflow-job states and three scalar gauges defined by the workflow metrics
protocol. It rejects missing alert gauges, duplicate known metrics, malformed numeric values,
negative values, NaN and infinity. Only these allowlisted numeric values enter metric history.
Workflow alerts, failed checks and stale backup manifests count toward the configured consecutive
failure threshold. A healthy check after an alert generates a separate recovery record.
The existing `outbox_pending` gauge counts unpublished rows. It does not include a published raw
detection still awaiting a committed dispatch decision; the durable relay retries those rows, but
that backlog needs direct operational inspection. This gauge alone is not proof that all detection
work is drained, and workflow alerts are not a complete fleet/host alert catalogue.

## Server collector and credential renewal

The release builder renders `monitor.service` and `monitor.env` from committed templates and typed
deployment configuration. The private deployment installer fills seeded tenant/owner identifiers
without printing them. Install only the reviewed release and compare generated environment/unit
hashes after installation, together with the running process's release working directory.

The optional authority adapter runs the configured existing Docker executable and API container
using an argument vector and protected JSON pipes. It uses the API's existing database authority
to issue only `observe` scope. It cannot approve or execute browser actions. On startup and before
expiry, it creates a replacement grant and revokes the predecessor in the same transaction. The
current credential is atomically stored in a private mode-0600 recovery file; bearer values never
appear in arguments or logs. No database port is exposed for monitoring, and no permanent bearer
is required. Direct database authority is available for a controlled local installation instead of
the subprocess adapter. Authority errors are recorded as safe categories while health/backup
checks continue.

The native service has restart supervision, a private temporary directory, a read-only filesystem
outside the configured state directory, no new privileges and a configured memory cap. Its root
authority comes from using the existing Docker socket; this is an explicit administrator trust
boundary. Do not expose its recovery file or turn the authority adapter into a network endpoint.

## Independent availability and proof limits

The deployed `20261015-publication-rc1` collector passed protected unit/environment/source
parity and current-release process-directory checks. An actual process death recovered in 26.65
seconds, renewed observe-only authority, revoked its predecessor and produced four fresh healthy
probes with zero active alerts. The retained history snapshot includes one earlier unhealthy
workflow-metrics sample (1,608 of 1,609 healthy); its cause is not established by this proof.
The four latest post-restart checks are healthy. This is collector recovery, not whole-service availability.
Notifications remain a local file/journal sink. See [current release evidence](../releases/2026-10-15.md).

Historically, the `20261013-free-local-rc4` host collector passed active service/source/unit/environment
parity checks. Its four configured probes—archive freshness, observation grant, origin health and
workflow metrics—were healthy with zero recorded failures in the verification window. Actual
process death triggered supervised recovery in 28.42 seconds; observe-only replacement authority
and predecessor revocation were verified. This is recovery of the collector process, not a
measurement of whole-service downtime. Its notifications remain a local file/journal sink.

An independent operator-PC collector was exercised against public production HTTPS for three
successful samples at 60-second intervals on 13 October 2026. A separate real loopback HTTP test
returned failures until the configured threshold, restarted the collector, then returned success:
both failure and recovery notifications survived in the durable sink.

The repository also defines an independent `independent-uptime` GitHub Actions workflow with a
five-minute UTC schedule and manual dispatch. It runs only when the repository is public and uses
a standard `ubuntu-latest` runner, a frozen collector environment and the maintained
`config/uptime.json` probe configuration. It checks public `/healthz` and `/v1/session`, records safe
summary lines in job logs and fails the job on the first unhealthy response. There is no artifact
upload, cache, paid integration, issue creation or outbound message action. Standard hosted runs
in public repositories are [free under GitHub's current billing rules](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
The default-branch workflow was published and enabled, and its actual manual
[verification run](https://github.com/Zahidulislam2222/fleetwright/actions/runs/38437549799)
passed both public probes on 13 October 2026. This verifies independent execution, not every
future scheduled invocation. Runs are independent of both the owner PC and the production server,
but scheduled jobs have no shared persistent SQLite history between runners.

The operator PC must stay awake and online to collect continuously. The observation establishes
only its recorded window; it does not establish monthly availability, a 24/7 alert service or an
availability SLO. The exact rc4 host installation/supervisor result above does not establish
independent 24/7 availability collection. Add an independently always-on free host only
after verifying its current terms, ownership and absence of charges.

GitHub schedules are best effort: high load can delay/drop runs, only the default-branch workflow
is scheduled, and public repositories lose scheduled execution after 60 days without activity.
Check the Actions page periodically; see [GitHub's schedule event limitations](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

Official references: [SQLite transaction contexts](https://docs.python.org/3/library/sqlite3.html),
[systemd service supervision](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html).

## Operator response and continuity

Assign an operator to review failure/recovery notifications and archive age. This implementation's
notification sink is a private file/journal, not an unattended email/SMS paging service. Define who
checks it, how quickly and how incidents are escalated before treating it as an operational alert.

After release replacement, restart the collector and verify its process directory, rendered
configuration hashes, recent committed samples, credential renewal and predecessor revocation.
Preserve history; a healthy report without new samples is not current collection evidence. Test a
bounded failed probe followed by recovery and confirm both notices survive process restart.

Independent scheduled probes are published and enabled, with the successful run linked above.
They do not share persistent history with the host collector.
Availability objectives remain [future SLOs](../scaling/slo.md), and operational status belongs in
the [release record](../releases/2026-10-13.md).
