# Privacy and data protection

How Fleetwright handles personal data, written for clients, data protection officers and
reviewers. Not legal advice.

## Roles

- For a client deployment, the **client is the controller** and Fleetwright (the operator of the
  service) is the **processor**, bound by a data processing agreement.
- For the public demo site, the site owner is the controller. The demo uses only fictitious data.

## What data is processed

| Category | Examples | Why | Where it lives | Protection |
|---|---|---|---|---|
| Console users | Name, work email, role, last sign-in time | Access control and audit | Postgres (`users`) | Row-level security; password hashed (argon2id); TOTP secret encrypted |
| Target-site accounts | Login email, password, session cookies | To act for the client | Postgres (`accounts`, `account_sessions`) | Envelope encryption (AES-256-GCM); never logged |
| One-time codes | Codes from email or typed by an operator | To finish a login | In memory and short-lived Redis keys only | Never logged or stored in Postgres |
| Job data from the target | Load details: lanes, rates, times | The business purpose | Postgres (`target_jobs`, `claims`) | Row-level security; minimised to needed fields |
| Audit records | Who did what, when, from which network | Accountability and security | Postgres (`audit_log`, append-only) | Client addresses stored as a network prefix (/24 IPv4, /48 IPv6), not a full IP |
| Failure evidence | Browser trace and screenshot of a failed step | Troubleshooting | Local object storage | Retention limit (7 days by default); access restricted |

## Principles applied

- **Minimisation:** only the fields a task needs are stored. The planned crawler adds a per-job
  "may contain personal data" flag with a field allowlist.
- **Retention:** evidence files are deleted after the configured retention period; job data
  retention is set per client at onboarding.
- **Security:** see [security controls](../security/controls.md).
- **Masking:** anonymous visitors and the shared demo login see masked emails and no client
  addresses.
- **Cookies:** the console uses strictly necessary cookies only (session and CSRF). No analytics,
  advertising or tracking cookies.

## Data-subject requests

Requests (access, correction, deletion, objection) are handled by the controller with the
processor's help:

1. Identify the tenant and the records (by email or account).
2. Export or delete within the legal deadline (one month under GDPR, extendable in complex cases;
   45 days under the CCPA).
3. Audit-log entries are kept for accountability, with the person's identifiers removed where the
   law allows.
4. Record the request and the outcome.

## International transfers

Hosting region is chosen per client. Transfers of EU personal data outside the EEA rely on the EU–US
Data Privacy Framework or Standard Contractual Clauses, recorded in the DPA.

## Breach notification

Personal-data breaches are handled under the [incident runbook](../operations/runbooks.md#incident-response):
the processor informs the controller without undue delay; the controller notifies the supervisory
authority within 72 hours where GDPR requires it.
