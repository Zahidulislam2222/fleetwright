# Threat model

Method: STRIDE per component, reviewed at every phase. Status column: **in place** (built and
tested), **partial**, or **planned** (on the [roadmap](../roadmap.md)).

## What we protect

| Asset | Why it matters |
|---|---|
| Target-site credentials and logged-in sessions | Anyone holding them can act as the client's account |
| Claim integrity | A duplicate or phantom booking costs the client money and reputation |
| Tenant data (filters, jobs, bookings, audit log) | Commercially sensitive; must never cross tenants |
| One-time codes | Short-lived, but enough to take over a session |
| Operator accounts | Control the whole fleet of a tenant |
| Master encryption key | Unwraps every sealed record |

## Trust boundaries

1. Internet ↔ edge (CDN/WAF, TLS termination)
2. Edge ↔ console and API
3. API / control processes ↔ Postgres and Redis (private network only)
4. Workers ↔ target sites (untrusted responses)
5. Workers ↔ email / OTP providers
6. Operators' browsers (untrusted input)

## Threats and responses

| # | Threat (STRIDE) | Component | Response | Status |
|---|---|---|---|---|
| T1 | **Spoofing**: operator account takeover by password guessing | API | argon2id hashing; mandatory TOTP for every account; lockout per email and per client network; constant-time answer for unknown users | Partial (built, not yet released) |
| T2 | **Spoofing**: replay of a TOTP code | API | Each time step accepted once (atomic compare-and-set) | Partial (built, not yet released) |
| T3 | **Tampering**: a stale or paused worker acts on a claim it no longer owns | Claims | Fencing tokens checked in every `UPDATE`; database clock only | In place |
| T4 | **Tampering**: a sealed session copied into another account's row | Vault | Associated data binds ciphertext to tenant + account + purpose | In place |
| T5 | **Repudiation**: "the system booked that, not me" | Audit | Append-only `audit_log` (no update or delete grant); full claim history in `claim_events` | In place (claims); partial (console actions) |
| T6 | **Information disclosure**: tenant A reads tenant B | Database | Row-level security `ENABLE` + `FORCE`; tested, mutation-checked | In place |
| T7 | **Information disclosure**: secrets in logs or failure evidence | Workers | Secrets, cookies and codes never logged; a test scans logs and events | In place |
| T8 | **Information disclosure**: database dump exposes sessions | Vault | Envelope encryption, AES-256-GCM per record | In place |
| T9 | **Information disclosure**: secrets in source control | Repository | gitleaks on every edit, commit and push; `.env` and credential files ignored | In place |
| T10 | **Denial of service**: a hostile target page returns huge or never-ending bodies | Workers | Bounded body reads, timeouts on every action, body read only when needed | In place |
| T11 | **Denial of service**: unbounded queries or streams | Platform | Pagination limits, statement timeouts, stream length caps, dead-letter after N deliveries | In place |
| T12 | **Elevation of privilege**: viewer performs operator actions | API | Role check on every endpoint server-side; per-endpoint tests | Planned (with the API release) |
| T13 | **Elevation of privilege**: worker credentials used to read the whole database | Database | Worker role has column-level grants only | In place |
| T14 | **CSRF / XSS** against the console | Console | `SameSite=Strict` httpOnly session cookie + CSRF token; Content-Security-Policy, `nosniff`, referrer and permissions policies | Headers in place; cookie/CSRF planned with the API |
| T15 | **SSRF** from crawl targets reaching internal services | Crawler | Egress guard after DNS resolution, blocking private, loopback, link-local and metadata ranges | Planned (crawler phase) |
| T16 | **Prompt injection** into the local AI agent | Agent | Page content treated as data; human approval before publish, send, purchase or delete; domain allowlist | Planned (agent phase) |
| T17 | **Insider misuse**: an operator automates a site the client is not allowed to automate | Process | Onboarding gate with written authorisation ([acceptable use](../legal/acceptable-use.md)) | In place (policy) |
| T18 | **Supply chain**: malicious or typo-squatted dependency | Build | Exact version pins, lock files, registry check before adding; image digests pinned in Compose | In place; SBOM and image signing planned |

## Residual risks (accepted for now)

- The public demo runs on a single shared server: a host compromise exposes the demo's data. The
  demo holds only fictitious data.
- The local master key comes from the environment. Production moves the wrap to a KMS.
- Third-party captcha solving is not implemented by design; real targets with captchas go to a
  human operator.
