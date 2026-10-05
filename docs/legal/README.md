# Law and compliance (US and EU)

> **Not legal advice.** This is an engineering compliance register: the laws that shape how
> Fleetwright is built, and the design rule each one produced. A lawyer must review any commercial
> deployment against a real target site. Sources were checked on 2026-10-05 and are listed at the
> end; secondary sources are marked as such.

## The short version

1. **Fleetwright only automates sites the client is allowed to automate.** That means sites the
   client owns, or sites whose terms or written permission allow automation. Automated logged-in
   use is the riskiest category, because it is bound by the site's terms.
2. **Major freight load boards forbid bots.** For example, DAT's terms (last updated 30 July 2026)
   prohibit using "any automated means including … a bot, AI agent, spider, a browser extension or
   plug-in, or web crawler" without prior written approval, and allow immediate termination. Using
   Fleetwright on such a board without written approval is a breach of contract and can get the
   account banned. This repository therefore ships with its **own fictitious board**, and real
   targets go through the [onboarding gate](acceptable-use.md).
3. **No code that defeats third-party access controls or captchas** is in this repository.
4. **Personal data is minimised, protected and deletable** ([privacy](privacy.md)).

## United States

| Law or case | What it means | Design rule in Fleetwright |
|---|---|---|
| **Computer Fraud and Abuse Act**, *Van Buren v. United States* (2021), *hiQ Labs v. LinkedIn* (9th Cir. 2022) | Accessing public pages is generally not access "without authorization" under the CFAA (as read by the Ninth Circuit after *Van Buren*). Bypassing a login or a technical block can still create liability *(secondary sources)* | Workers only use accounts the client owns and is authorised to automate. No bypassing of authentication, IP blocks or captchas |
| **Breach of contract / terms of service** (*hiQ v. LinkedIn* final judgment 2022; *Meta v. Bright Data*, N.D. Cal. 2024) | Courts have moved the fight to contract law. In *Meta v. Bright Data*, logged-out scraping of public data was held not to breach Meta's terms; terms bind **logged-in use** *(secondary sources)* | Fleetwright's claim workers are logged in by nature, so the client must show the platform allows automation (onboarding gate) |
| **DMCA §1201** (anti-circumvention) | Defeating technical access controls can create risk *(engineering assessment)* | No captcha-solving or anti-bot bypass for third-party sites; captchas go to a human operator |
| **Copyright** | Scraped content can be protected even when access is allowed | Store facts and fields needed for the job, not copies of pages |
| **State privacy laws** (California CCPA/CPRA and others) | Notice, deletion and purpose limits for personal data. CCPA applies to businesses above a revenue threshold (USD 26.625M for 2026, adjusted every odd year) or data-volume tests *(secondary source)* | Data minimisation, retention limits, deletion on request ([privacy](privacy.md)) |
| **FTC Act §5** and the FTC rule on fake reviews (2024) | Automated fake engagement or undisclosed AI personas can be deceptive | The planned AI agent refuses fake-review tasks, labels AI-generated content and needs human approval to publish |
| **ADA** (accessibility of the web console) | Accessibility claims risk | WCAG 2.2 AA tested in the console |

## European Union

| Law | What it means | Design rule in Fleetwright |
|---|---|---|
| **GDPR** | Public personal data is still personal data. Processing needs a lawful basis (often legitimate interest with a balancing test), minimisation, retention limits and data-subject rights; large-scale scraping may need a DPIA | Fleetwright acts as a **processor** for clients; DPA template; retention jobs; data-subject request runbook ([privacy](privacy.md)) |
| **ePrivacy Directive** | Cookies on the console | Strictly necessary cookies only; no analytics or tracking cookies |
| **Database Directive** (sui generis right) | Extracting a substantial part of a protected database can infringe | Per-client scope review; extraction limits in crawl configuration (crawler phase) |
| **Copyright DSM Directive, Art. 4** | Rights holders can opt out of text and data mining in machine-readable form | The planned crawler respects robots.txt and TDM opt-out signals by default |
| **AI Act, Art. 50** (transparency) | Applies from 2 August 2026; machine-readable marking of AI-generated content has a grace period to 2 December 2026 | The planned AI agent labels generated content and tells users when they interact with AI |
| **AI Act, high-risk rules** | Postponed to December 2027 by the Digital Omnibus. Fleetwright's uses are not expected to be high-risk *(engineering assessment)* | Re-assessed if use cases change |
| **Cyber Resilience Act** | Vulnerability reporting duties apply from 11 September 2026 (24 h early warning, 72 h notification, 14-day final report). Most other duties apply later | [`SECURITY.md`](../../SECURITY.md), vulnerability-handling runbook, SBOM per release (planned) |
| **International data transfers** | Hosting location matters for EU personal data | Hosting region chosen per client; Data Privacy Framework or Standard Contractual Clauses in the DPA |

## Documents in this folder

- [Acceptable use and client onboarding gate](acceptable-use.md)
- [Privacy and data protection](privacy.md)

## Sources (checked 2026-10-05)

- DAT Terms and Conditions, automated-means clause: <https://www.dat.com/terms-and-conditions>
- *hiQ v. LinkedIn* (9th Cir., April 2022), Jenner & Block client alert:
  <https://www.jenner.com/en/news-insights/publications/client-alert-data-scraping-in-hiq-v-linkedin-the-ninth-circuit-reaffirms-narrow-interpretation-of-cfaa> *(secondary)*
- *hiQ*, *Van Buren* and contract claims, Farella Braun + Martel:
  <https://www.fbm.com/publications/what-recent-rulings-in-hiq-v-linkedin-and-other-cases-say-about-the-legality-of-data-scraping/> *(secondary)*
- *Meta v. Bright Data* (2024), Farella Braun + Martel:
  <https://www.fbm.com/technology/publications/major-decision-affects-law-of-scraping-and-online-data-collection-meta-platforms-v-bright-data/> *(secondary)*
- CCPA 2026 threshold, Jackson Lewis FAQ:
  <https://www.jacksonlewis.com/insights/navigating-california-consumer-privacy-act-30-essential-faqs-covered-businesses-including-clarifying-regulations-effective-1126> *(secondary)*
- EU AI Act Art. 50 timing and Digital Omnibus; CRA reporting dates: law-firm and Commission
  summaries reviewed during project planning on 2026-10-05 *(secondary; confirm with counsel)*
