# Adding an execution cell

A cell is a directory assignment plus its Redis transport and separately bounded worker/control
processes. Adding a database directory row alone does not start those services or establish
capacity. Use existing authorized infrastructure for a local rehearsal; paid resources require a
separate verified estimate and approval before provisioning.

1. Inventory the current directory, configured Redis cells, workers, queue ages and resource
   headroom. Snapshot the release/private configuration and take a verified archive. Select a
   unique cell identity and record its limits in maintained deployment configuration.
2. Add the cell's private Redis URL to `FW_REDIS__CELLS` through the typed environment boundary.
   Keep credentials in the protected environment/recovery inventory. Match the cell directory
   record to that identity and transport; do not expose Redis publicly.
3. Start a control process and freight/workflow workers with their corresponding
   `FW_CONTROL__CELL` / `FW_WORKER__CELL` assignment. Configure dedicated pools, resource caps,
   heartbeat and stop grace. The orchestrator's grace must exceed the configured application
   drain timeout plus an explicit margin; verify the rendered Compose values, not only source
   defaults. Start a crawler assigned through `FW_CRAWL__CELL` if needed.
4. Move a test tenant with the reviewed administrative
   `fw_coordinator.control.move_tenant(engine, tenant_id, to_cell, actor)` transaction. It holds
   assignment authority while moving queued claims and resetting unconsumed detection delivery.
   Do not update the directory manually and skip those queue changes.
5. Exercise unread and in-flight detection replay, queued claim leasing, stale old-cell actor
   refusal, workflow admission, receipts, tenant isolation and worker drain. Previously admitted
   actions may finish; investigate `UNKNOWN` outcomes before creating replacement work.
6. Verify exact artifact/config parity, current image identities, queue recovery, bounded fair
   tenant turns and representative latency/memory/CPU. Record the measured workload and rollback
   boundary before moving additional tenants. Test a heavily loaded tenant beside small tenants
   and compare oldest eligible queue age; equal turn counts alone do not establish fair latency.

Removing a cell requires moving or accounting for its tenants and durable work, stopping its
producers, draining old deliveries and preserving uncertainty/evidence. Do not delete its Redis
volume as a routine move. For upgrades involving legacy Redis-only raw detections or older
incompatible backends, follow the explicit [deployment compatibility procedure](../operations/deployment.md).

The reference Terraform describes a configurable cloud topology; offline mock plans do not
provision cells or prove zone-loss recovery. See [capacity arithmetic](capacity-model.md),
[measurements](verification-2026-10-13.md) and [availability objectives](slo.md).
