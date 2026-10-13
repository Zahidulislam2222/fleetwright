# Privacy and data protection

This describes current processing and the deployment obligations an operator must complete.
Owned destination records are maintained for workflow verification; operator identities, network
metadata and security logs can still be personal data. Do not treat an owned workspace as exempt
from privacy obligations.

## Responsibility

The public site's operator determines its processing purposes. In a customer deployment,
controller/processor roles depend on actual decisions and contracts; they are not automatically
assigned by the software. Document roles, lawful basis, notices and a DPA where required before
processing customer data. Use [the legal register](README.md) for applicability and source links.

## Data inventory

| Data | Purpose / storage | Current protection |
|---|---|---|
| Console email, role and password hash | Identity and authorization in PostgreSQL | Argon2id; role checks; encrypted TOTP secret |
| Target credentials/session state | Authorized destination login in account vault | Envelope encryption, row-bound associated data and tenant RLS |
| One-time codes | Login completion in memory/short-lived messaging | Limited lifetime, no intended log persistence |
| Freight/job/request inputs and receipts | Execution and reconciliation in PostgreSQL | Tenant isolation, exact-action fingerprint and bounded evidence |
| Approval/grant/session records | Human authority and client access | Expiry/revocation checks; stored token digests |
| Audit identity and network prefix | Investigation/accountability | Append-only application grants; IPv4 /24 or IPv6 /48 prefix in application audit |
| Browser screenshots/traces | Private failure investigation | Private storage and configured pruning; artifacts may contain page data |
| Database archives | Recovery | Restricted host permissions, verified manifests; archives remain sensitive |

Edge, hosting and infrastructure access logs may have different network metadata than application
audit. Review their retention and vendor terms separately. Evidence redaction in JSON exports does
not establish that raw screenshots/traces or database archives are anonymous.

## Retention and requests

Browser evidence has a configured retention period, seven days by default, and pruning in the
freight worker. Backup loop retention defaults to seven completed archives. Database job/audit
retention is not a complete automated deletion policy today. Before customer onboarding, assign
periods by category, legal holds, backup expiry, deletion ownership and verification. Restrict free
text and prohibit unnecessary sensitive personal data in workflow inputs.

Handle access, correction, deletion and objection requests through the deployment operator:
verify identity/authority, identify the tenant and records, assess legal retention duties, export
or correct/delete through an approved procedure, and record completion. Append-only audit records
need a legally reviewed minimization/pseudonymization policy; do not promise automatic deletion
that is not implemented. Apply the applicable jurisdiction's deadline and extensions.

Maintain an operator request register with receipt date, verified requester/authority, applicable
jurisdiction, affected categories, legal holds, deadline, decision and completion evidence.
Processing-record duties are separate from permission to retain all raw personal data. Apply the
current [Bangladesh Act and jurisdiction-specific requirements](README.md) where relevant;
older ordinance summaries are not the current legal baseline.

Deletion must account for rows, caches, browser profiles, screenshots/traces, exports and archive
expiry. Where a protected archive is retained for recovery, restrict access, record expiry and
reapply approved minimization/deletion decisions after restoration. Preserve necessary legal or
incident evidence under an assessed hold; indefinite retention is not a security control.

## Cookies, providers and transfers

The application uses necessary session/CSRF mechanisms and local browser preferences; no application
advertising or analytics integration is configured. Hosting/CDN providers may apply their own
security mechanisms. Document subprocessors and hosting regions in a deployment-specific notice.
International transfer safeguards require an assessed legal mechanism and contract; choosing a
region or provider does not by itself complete that assessment.

MCP exports exclude credentials, cookies, arbitrary payloads and raw page HTML. Client prompts
and model-provider retention are outside that export boundary: send only necessary redacted
material and review the selected provider's terms. There is no automatic paid model API fallback.

The standalone agent keeps private local state/history and uses a dedicated profile or isolated
CDP context. Its configured
local Ollama flow avoids a hosted model API for that path, but destination submissions still leave
the device. CDP connection, exports, remote destinations and any newly selected provider each need
assessment; local inference is not a promise that all processing remains local.

Before deployment, publish the actual operator identity/contact, purposes and legal bases,
retention schedule, rights channels, recipients/subprocessors and transfer safeguards. This
engineering inventory is not a completed deployment-specific privacy notice or DPA.

## Security incidents

Contain unauthorized access, preserve private evidence, identify affected data and notify the
responsible controller/operator promptly. GDPR controller notification to a supervisory authority
is generally within 72 hours where required; processor notification is without undue delay.
Other jurisdictions can differ. Follow [incident response](../operations/runbooks.md#incident-response).
