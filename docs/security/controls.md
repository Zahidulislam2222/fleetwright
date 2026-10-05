# Security controls

A checklist of the controls Fleetwright applies, grouped by area. **Status:** in place, partial, or
planned.

## Identity and access

| Control | Status |
|---|---|
| Passwords hashed with argon2id | Partial: built for the console API, not yet released |
| TOTP multi-factor authentication required for every console account | Partial: built, not yet released |
| Login lockout by email and by client network; the shared demo login is limited per network only | Partial: built, not yet released |
| Session token in an httpOnly, `Secure`, `SameSite=Strict` cookie; only its SHA-256 stored server-side | Partial: built, not yet released |
| Roles: owner, operator, viewer, demo; anonymous read-only demo view with personal data masked | Partial: model built, endpoints planned |
| Role check on every endpoint, with a test per endpoint | Planned |

## Data protection

| Control | Status |
|---|---|
| Postgres row-level security `ENABLE` + `FORCE` on every tenant table | In place |
| Separate database roles: owner (migrations), app, worker (column grants), board | In place |
| Envelope encryption (AES-256-GCM, per-record data key, row-bound associated data) for credentials and sessions | In place |
| Append-only audit log (no update/delete grants) | In place |
| Personal data masked for anonymous and demo viewers (emails, client addresses) | Partial: built, not yet released |
| TLS for all public traffic | In place (edge) |
| Databases and Redis bound to private interfaces only | In place (local and server) |

## Application safety

| Control | Status |
|---|---|
| All SQL parameterised and static; no string-built queries (bandit B608 enforced) | In place |
| Every external call has a timeout; response bodies read with size limits | In place |
| Content-Security-Policy, `X-Content-Type-Options`, referrer and permissions policies on the console | In place |
| Secrets, cookies and one-time codes never logged (tested) | In place |
| Third-party captcha defeat code: none, by policy | In place |
| SSRF egress guard for crawlers | Planned |

## Software supply chain

| Control | Status |
|---|---|
| gitleaks + bandit on every file edit (local hook); gitleaks, bandit and semgrep before each commit | In place |
| gitleaks (full history), semgrep and bandit in GitHub Actions on push and pull request | In place |
| Exact version pins (`uv.lock`, `package-lock.json`); container images pinned by digest | In place |
| New dependencies checked on the real registry before adding (anti-typosquatting) | In place (process) |
| SBOM per release, image scanning, signed images | Planned |

## Operations

| Control | Status |
|---|---|
| Secrets only in environment / secret manager; `.env.example` holds placeholders | In place |
| Local-first deploys with file-hash parity checks between local and server | In place |
| Secret rotation, restore drill, incident response runbooks | Documented ([runbooks](../operations/runbooks.md)); drills planned |
| Containers: non-root, read-only filesystem, dropped capabilities, resource limits | Planned |
