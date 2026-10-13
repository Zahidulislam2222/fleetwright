# AWS reference — never provisioned

This reference is for local validation and **mock-provider plans only**. It creates no resources
when using the commands below. A real apply creates billable ALB, Fargate, RDS, Redis, storage and
logs. No price estimate or authorization to apply is supplied. No AWS credentials are required.

```sh
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
terraform test
```

All deployment choices are input variables; test data resides in `tests/reference.tftest.hcl`.
The mock suite checks private subnets, multi-zone storage, encryption, Redis TLS, archive public
access refusal, immutable images and rejected single-zone placement. Mock plans check module
logic/provider schema; they do not establish deployability, real failover, capacity or SLOs.

The reference deliberately has no private internet egress. Before any independently authorized
deployment, add and review private ECR/Secrets/Logs/S3 endpoints, task execution/IAM policies,
database app roles and RLS initialization, actual application service commands/configuration,
separate gateway/execution cells, migrations and rolling-release controls, DNS, ALB access logs,
KMS policy, restore exercises, and actual zone-loss/load tests. Apply is blocked operationally
until these prerequisites and a current exact-cost warning are reviewed by the owner.

Terraform's [mock providers](https://developer.hashicorp.com/terraform/language/tests/mocking)
generate synthetic computed values. The AWS provider version is pinned to the official registry.
