# Data lifecycle and access responsibilities

The deployment operator owns the processing inventory and retention decisions. Store only fields
needed for the authorized workflow; minimize free text and keep credentials, raw page content and
customer records outside public documentation, issues and release evidence.

| Category | Implemented boundary | Operator responsibility |
|---|---|---|
| Console identity | PostgreSQL role records, Argon2id password hashes and sealed TOTP | Provision/revoke users, review roles, publish identity/privacy contact and recovery procedure |
| Destination credentials/sessions | Tenant/account-bound envelope encryption and vault access | Obtain account permission, rotate credentials, preserve independent vault keys and restrict operators |
| Browser context/profile | Isolated worker context or device-owned local profile | Restrict filesystem/ACL access, avoid cross-account sharing and remove retired profiles safely |
| One-time codes | Short-lived authentication handling | Keep code values out of logs/exports; review mailbox provider and access |
| Claims/workflows/receipts | Tenant-scoped durable state, exact approval and database-clock fencing | Define business retention, legal holds, incident access and uncertain-outcome investigation |
| Grants/approvals/audit | Scope/expiry/revocation, consumed approvals and bounded audit views | Separate approver/executor authority, revoke temporary access and review audit access/retention |
| Raw detections/outbox | Durable authority until decision commit; bounded transport replay | Observe backlog/age, preserve unconsumed work through handover and assess event retention |
| Crawl fields/exports | Contract allowlists, quality guards, private bounded artifacts and retention | Approve target/fields/robots policy, review export recipients and expiration |
| Screenshots/traces | Private investigation storage and configured evidence pruning | Treat page records as sensitive, restrict access and apply incident/legal retention decisions |
| Local agent tasks | Device-owned SQLite/history and approved form/receipt data | Protect local keys/profile, review model/destination data flow and stop/reconcile uncertain saves |
| Database archives | Verified private custom-format dumps and authenticated encrypted off-host bundles | Separate keys from media, control recovery access, document expiry and test actual restore |
| Infrastructure/monitor logs | Bounded operational collection and private local notification/history | Assess network metadata, provider retention, incident recipient and access review |

## Collection and destination scope

Authorize the account, target origin, operation, fields and intended reuse together. Login permission
does not imply permission for every automated action or redistribution. Maintain validated contracts
for form inputs and receipt identity. A new provider or destination changes processing boundaries
and requires the corresponding authorization, privacy and security assessment.

The installed local-model path drafts locally, but an approved destination submission transfers its
fields to that destination. Optional browser attachment, exported artifacts, hosting/CDN services and
any future model provider each have their own handling terms and access controls.

## Access, export and incident handling

Use tenant-scoped restricted transactions for normal access and private owner authority for approval
and grant issuance. Observation tokens carry their approved scope and lifetime. Check current role,
expiry and revocation at each boundary; previous access cannot authorize a later action.

Bound investigations and exports by field allowlist, page/record limits and retention. Redacted JSON
evidence and raw screenshots/traces have different exposure. Verify export recipients and preserve
an access/incident record privately. Rotate compromised access, preserve necessary evidence and
follow the applicable notification process through the responsible operator.

## Retention, deletion and restored data

Typed settings own implemented evidence, crawler, monitor and archive retention. Customer policies
must additionally cover audit/business records, local profiles, caches, temporary downloads, legal
holds and subprocessors. Current pruning functions do not constitute a universal erasure workflow.

For a request, verify identity and tenant authority; locate the affected stores; assess legal and
incident retention; approve the action; record completion and any retained restriction. Archived
records require an expiry policy and restricted recovery access. Reapply approved deletion or
minimization decisions after restoration so a backup cannot silently restore retired processing.

Before recovery, verify the independent key, archive authentication/hash, new isolated target and
tenant/role/bootstrap settings. Restore into fresh verification databases first. Data parity is one
gate; application startup, authorization, fencing and destination reconciliation complete recovery.

See [privacy](../legal/privacy.md), [legal applicability](../legal/README.md),
[commercial readiness](../legal/commercial-readiness.md), [threat model](threat-model.md) and
[recovery procedure](../operations/recovery.md).
