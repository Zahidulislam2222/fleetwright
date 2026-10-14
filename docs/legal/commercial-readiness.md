# Customer onboarding and commercial readiness

Complete this handoff for each intended deployment and destination. The copyright holder,
deployment operator, customer and destination operator can be different parties; record their
actual roles and authority privately. Public documentation describes the product and its contracts.

| Decision | Evidence required before customer work | Accountable role |
|---|---|---|
| Software rights | Written permission consistent with the repository license and intended commercial/production use | Copyright holder/customer |
| Destination authority | Permitted origin/accounts/actions/fields, terms, rate policy and revocation procedure | Customer and destination operator |
| Processing roles | Purposes, categories, controller/processor allocation and applicable jurisdiction | Deployment operator/customer |
| Privacy terms | Required notices, lawful grounds, DPA, subprocessors/transfers, rights contact and retention | Responsible controller/operator |
| Identity/access | Named owners/approvers/operators, least privilege, MFA and offboarding | Customer security owner |
| Hosting/data location | Region/provider scope, private network, key ownership and recovery access | Deployment operator |
| Integration acceptance | Exact input/approval/receipt contract, ambiguity handling and adverse-condition tests | Integration owner/customer |
| Release security | Locks, native image/SBOM/signature checks, retained findings and support/patch ownership | Release/security owner |
| Capacity and availability | Agreed workload, supported tier, SLIs/window, limits, incident response and remedies | Service owner/customer |
| Recovery | Archive/key/config ownership, tested restore, retained uncertainty and assessed RPO/RTO | Recovery owner |
| Support/change control | Response channels, support hours, escalation, maintenance and approval for scope changes | Commercial/service owner |
| Exit and portability | Export fields, access revocation, data-return/deletion schedule and archive expiry | Customer/operator |

## Licensing and third-party materials

The current [repository license](../../LICENSE) reserves rights to Zahidul Islam and permits source
inspection and local evaluation. Commercial/production use and third-party destination access require
the stated written permission. A public repository does not automatically grant an open-source or
commercial license. Record any separately agreed rights before shipping to a customer.

Dependencies and media retain their respective terms. Use frozen locks and exact image SBOMs to
inventory components, then assess notices, redistribution and license compatibility for the actual
delivery. A vulnerability result is separate from a license decision. Keep private asset/source
records and relevant permissions available to the delivery owner.

## Legal and privacy assessment

Use the [jurisdiction register](README.md) and its primary sources for computer-access permission,
privacy, content/database rights, consumer protection, AI-system duties and product cybersecurity.
Evaluate the intended use and parties rather than assigning duties from a product label or model
choice. Separate account access from permission for scraping, booking, publication or communications.

For personal data, specify purpose, necessary fields, recipients, retention, rights handling,
security and applicable transfer safeguards. Assess whether sensitive/regulated processing or a
high-risk intended use changes the required approval. Keep responsibility for notifications and
rights requests explicit; [data lifecycle](../security/data-lifecycle.md) maps the technical stores.

## Acceptance, support and service objectives

Write the customer acceptance contract before integration: authentication, allowed actions,
exact human approval, receipt identity, rate limits, failure/UNKNOWN handling, quality/export fields,
retention, recovery and the operational handoff. Use an owned or explicitly authorized destination
for acceptance and retain successful and rejected runs with their workload/release identity.

The product's future scale design targets 1M+ concurrent authorized console users, with 99% initial
and 99.9% multi-zone availability objectives. A customer agreement selects its supported workload,
measurement window, eligible failures, response commitments and remedies after validation.
Follow the [scale promotion plan](../scaling/validation-plan.md) and
[SLI/error-budget policy](../scaling/slo.md) before offering a tier.

Agree support channels/hours, severity definitions, escalation, incident communications and patch
ownership. Budget additional infrastructure, integrations and providers explicitly before activation.
Keep contract pricing and private client details out of reusable public capability materials.

## Go-live and exit record

The release approver signs off destination permission, scoped test results, private recovery access,
configuration/key ownership, backup/restore and monitoring evidence, accepted limitations and the
next review date. The operator verifies public availability/authorization and local/live parity.
Document any outstanding prerequisite and the person responsible before enabling its affected use.

At exit, stop new admission, reconcile accepted/uncertain actions, export permitted records, revoke
grants/accounts, retire profiles and apply the agreed deletion/hold/archive schedule. Confirm that
restoring an older archive will reapply those decisions. Preserve only the evidence authorized by
the applicable retention and legal-hold policy.
