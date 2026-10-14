# AWS reference — never provisioned

This reference is for local validation and **provider-substituted validation plans only**. It creates no resources
when using the commands below. A real apply creates billable ALB, Fargate, RDS, Redis, storage and
logs. No price estimate or authorization to apply is supplied. No AWS credentials are required.

```sh
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
terraform test
```

All deployment choices are input variables; test data resides in `tests/reference.tftest.hcl`.
The test suite checks private subnets, multi-zone storage, encryption, Redis TLS, archive public
access refusal, immutable images and rejected single-zone placement. Provider-substituted plans check module
logic/provider schema; they do not establish deployability, real failover, capacity or SLOs.

The reference deliberately has no private internet egress. Before any independently authorized
deployment, add and review private ECR/Secrets/Logs/S3 endpoints, task execution/IAM policies,
database app roles and RLS initialization, actual application service commands/configuration,
separate gateway/execution cells, migrations and rolling-release controls, DNS, ALB access logs,
KMS policy, restore exercises, and actual zone-loss/load tests. Apply is blocked operationally
until these prerequisites and a current exact-cost warning are reviewed by the owner.

Terraform's [provider substitution support](https://developer.hashicorp.com/terraform/language/tests/mocking)
generate synthetic computed values. The AWS provider version is pinned to the official registry.

## Position in the architecture

The current production topology is an existing single server, managed by the separate immutable
release procedure. This reference is future infrastructure design; it is not a deployed AWS
installation or evidence of 1M-user capacity. Acceptance requires representative load, connection
pooling, durable queues, zone-loss, restore and operational cost measurements before any promotion.
See [future scale](../../docs/scaling/README.md), [availability objectives](../../docs/scaling/slo.md)
and [deployment](../../docs/operations/deployment.md).

## Promotion from reference to managed service

Before any separately approved apply, produce a complete region-specific dependency and access
inventory, cost model, IAM/data-residency review, release/migration plan and operator handoff. Test
zone failure at the proposed traffic tier with existing spare capacity and bounded reconnects.
Keep database writer ownership, RLS and uncertain-action reconciliation intact through failover.

The [validation plan](../../docs/scaling/validation-plan.md) specifies the 1k→10k→100k→1M+ workload
ladder; [customer readiness](../../docs/legal/commercial-readiness.md) covers legal, privacy, support
and SLA decisions. The present task uses the existing server and local tools only.
