# Acceptable use and client onboarding gate

Fleetwright is a tool for automating web workflows **that the client is allowed to automate**.
These rules apply to private, customer and public workspace operation. Software licensing,
destination permission and a lawful processing purpose are separate onboarding requirements.

## Allowed

- Sites and systems the client owns or operates.
- Third-party sites whose terms permit automated access, or that have given the client written
  permission (for example, an API agreement or a partner programme).
- Testing and verification against the owned freight board in `apps/mockboard`.

## Not allowed

- Sites whose terms prohibit automation, without written approval from the site operator. Many
  freight load boards fall into this category.
- Bypassing logins, IP blocks, rate limits, captchas or other technical access controls.
- Using accounts the client does not own, shared or bought accounts, or credentials obtained
  without the account holder's consent.
- Collecting personal data without a lawful basis, or beyond what the task needs.
- Fake engagement, fake reviews, or AI-generated content presented as human without disclosure.
- Anything that degrades the target service (load beyond normal human-like use).

## Onboarding gate (required before any new destination)

No new destination is configured until every item is answered in writing and retained with its
scope/contract. The repository's [license](../../LICENSE) separately requires written permission
for production/commercial use or third-party-site access.

| # | Question | Evidence kept |
|---|---|---|
| 1 | Which site or platform, and which accounts? | Target list, account owners |
| 2 | Is automation allowed by its terms, or is there written permission? | Link to the terms clause, or the permission letter |
| 3 | Does it process personal data, and which basis/rights/risk-assessment duties apply? | Data inventory, assessed legal basis and DPIA where required; do not assume every task uses legitimate interests |
| 4 | Which hosting, model, proxy, OTP and other providers are used, with compatible permission/privacy terms? | Provider/subprocessor register; no CAPTCHA or access-control bypass |
| 5 | Data retention period and deletion process | Retention setting |
| 6 | Jurisdictions involved (client, target, data subjects, hosting) | Hosting region, transfer mechanism |
| 7 | Rate limits agreed with, or acceptable to, the target | Configured per-account limits |
| 8 | Who approves exact actions, handles uncertainty and revokes access? | Named authority, workflow contract, receipt/reconciliation and incident contacts |

**If question 2 cannot be answered with "yes", the project does not go ahead.**

## Operator responsibilities

Operators with console access must not change targets, accounts or rate limits outside what was
approved at onboarding. Every change is recorded in the tenant's audit log.

Stop affected admission when permission expires, an account is revoked, destination behavior
changes materially or execution becomes uncertain. Preserve evidence and reconcile accepted
actions before replacements. A working selector or login does not override permission boundaries.
Do not present generated reviews, identities or engagement as authentic human activity.
