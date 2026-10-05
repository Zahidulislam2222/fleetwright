# Security policy

## Reporting a vulnerability

Please report security problems **privately**. Do not open a public issue.

- Use GitHub's private vulnerability reporting: **Security → Report a vulnerability** on this
  repository.
- Include what you found, how to reproduce it, and the impact you expect.

What happens next:

| Step | Target time |
|---|---|
| Acknowledgement | 3 working days |
| First assessment (valid or not, severity) | 10 working days |
| Fix or mitigation for high and critical issues | 30 days, or sooner if actively exploited |
| Public disclosure | Coordinated with the reporter after the fix ships |

Actively exploited vulnerabilities in a released product are handled under the EU Cyber
Resilience Act timelines where they apply (early warning within 24 hours, notification within 72
hours, final report within 14 days). See [runbooks](docs/operations/runbooks.md#vulnerability-handling).

## Scope

| In scope | Out of scope |
|---|---|
| Code in this repository | Third-party services and their own vulnerabilities |
| The public site at `fleetwright.zahidul-islam.com` | Denial-of-service and volumetric testing |
| | Social engineering, physical attacks |
| | Findings that need a compromised operator machine |

Testing the public site must stay non-destructive: no automated scanning that degrades the service,
no access to data that is not yours.

## Supported versions

Fleetwright is pre-1.0. Only the latest commit on `main` receives fixes.

## How the project handles security

- Every file change by an automated or human author is scanned for secrets (gitleaks) and Python
  security issues (bandit); commits also run semgrep. Findings are fixed, never suppressed.
- The same scanners run in GitHub Actions on every push to `main` and every pull request.
- Real secrets never enter the repository. `.env.example` documents variable names with
  placeholders only.

Details: [threat model](docs/security/threat-model.md) · [security controls](docs/security/controls.md).
