# Acceptable use and client onboarding gate

Fleetwright is a tool for automating web workflows **that the client is allowed to automate**.
This page sets the rules for any deployment outside the bundled demo.

## Allowed

- Sites and systems the client owns or operates.
- Third-party sites whose terms permit automated access, or that have given the client written
  permission (for example, an API agreement or a partner programme).
- Testing and demonstration against the fictitious board in `apps/mockboard`.

## Not allowed

- Sites whose terms prohibit automation, without written approval from the site operator. Many
  freight load boards fall into this category.
- Bypassing logins, IP blocks, rate limits, captchas or other technical access controls.
- Using accounts the client does not own, shared or bought accounts, or credentials obtained
  without the account holder's consent.
- Collecting personal data without a lawful basis, or beyond what the task needs.
- Fake engagement, fake reviews, or AI-generated content presented as human without disclosure.
- Anything that degrades the target service (load beyond normal human-like use).

## Onboarding gate (required before any real target)

No real target is configured until every item is answered in writing and kept with the contract.

| # | Question | Evidence kept |
|---|---|---|
| 1 | Which site or platform, and which accounts? | Target list, account owners |
| 2 | Is automation allowed by its terms, or is there written permission? | Link to the terms clause, or the permission letter |
| 3 | Does the workflow touch personal data? If yes: lawful basis, balancing test, DPIA if large scale | Legitimate-interest assessment / DPIA |
| 4 | Which proxy, captcha and OTP providers, and are their terms compatible? | Provider list and terms |
| 5 | Data retention period and deletion process | Retention setting |
| 6 | Jurisdictions involved (client, target, data subjects, hosting) | Hosting region, transfer mechanism |
| 7 | Rate limits agreed with, or acceptable to, the target | Configured per-account limits |

**If question 2 cannot be answered with "yes", the project does not go ahead.**

## Operator responsibilities

Operators with console access must not change targets, accounts or rate limits outside what was
approved at onboarding. Every change is recorded in the tenant's audit log.
