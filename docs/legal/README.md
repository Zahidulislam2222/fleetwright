# Legal and deployment compliance register

Fleetwright currently operates owned freight and maintenance workflows. A software license,
authorized account and website permission are separate requirements. Before onboarding another
destination, the operator must establish all three and record jurisdiction-specific obligations.
This register is an engineering checklist for legal review, not a legal opinion or certification.
Primary-source links and the implementation register were rechecked on 2026-10-15; recheck before a commercial deployment or material use change.

## Authorization and use

Use owned systems or destinations whose operator expressly permits the intended automation.
Account access does not automatically permit scraping, booking, messaging or publication. Review
terms, contracts, computer-access law, intellectual property and data protection independently.
Do not bypass access controls, challenges or rate limits. See [acceptable use](acceptable-use.md).
The repository's [license](../../LICENSE) permits local evaluation; commercial/production use
requires the copyright holder's written permission.

## Applicability register

| Area | Review before deployment | Required evidence / engineering action |
|---|---|---|
| US computer access | CFAA authorization boundaries and state computer-access laws | Written destination scope; deny prohibited accounts/actions; preserve revocation |
| Contracts and content rights | Site terms, commercial agreements, copyright and database rights | Permission record, allowed fields/actions, export/reuse limits |
| EU/EEA personal data | GDPR controller/processor roles, lawful basis, rights, security, DPIA and transfers | Data inventory, signed DPA where appropriate, retention/request procedures, transfer assessment |
| California privacy | CCPA/CPRA scope, roles, rights and current regulations | Request/opt-out process, contract restrictions and audit/risk/ADMT assessment where triggered |
| Bangladesh personal data | Personal Data Protection Act 2026, roles, commencement provisions, rules and transfers | Current-law assessment, notices/basis, security, retention/requests and classification/transfer conditions |
| AI systems/content | EU AI Act role, intended use, risk classification and transparency | Per-workflow assessment, human oversight and required AI-content disclosure |
| Product cybersecurity | CRA product/manufacturer scope and reporting applicability | Vulnerability intake, release/support process and applicable reporting escalation |
| Consumer protection | Deceptive claims, fake reviews/testimonials and misleading AI output | Accurate capability claims and prohibition on deceptive engagement |
| Communications/payments | Marketing consent, messaging laws, payment/financial duties | Separate authorized workflow review; no bundled payment or messaging service is represented |
| Other jurisdictions | Operator, customer, destination, hosting and data-subject locations | Local counsel review, including Bangladesh where relevant; no universal-law claim |

The Supreme Court's *Van Buren* decision addresses a CFAA interpretation; it does not authorize
all scraping or eliminate contract/privacy duties. Use the [primary judgment](https://www.supremecourt.gov/opinions/20pdf/19-783_k53l.pdf)
and a scoped legal assessment rather than a blanket “public data is free to use” rule.
California applicability and rights depend on the business and processing. The CPPA's completed
rulemaking took effect on 1 January 2026 and covers updated rules, risk assessments, cybersecurity
audits and automated-decisionmaking rights with applicability and phased compliance conditions.
Review the [CPPA rulemaking and approved text](https://cppa.ca.gov/regulations/ccpa_updates.html)
alongside the [California Attorney General's CCPA guidance](https://oag.ca.gov/privacy/ccpa).
Using an AI tool does not itself establish that every ADMT or audit provision applies.
The [FTC review/testimonial guidance](https://www.ftc.gov/business-guidance/resources/consumer-reviews-testimonials-rule-questions-answers)
informs the prohibition on deceptive review automation.

## Bangladesh: current Act and transition

The official register identifies **Personal Data Protection Act 2026 (Act 63 of 2026), dated
10 April 2026**, in [official register entry 1692](https://bdlaws.minlaw.gov.bd/act-1692/act-chapter-print-2693.html).
Section 1(3) deems the Act effective from 6 November 2025 except sections 23 and 31–35, which
require separate Gazette commencement after the statutory 18-month period. Do not treat those
exceptions as already commenced without the relevant notification.

The [repeal provision](https://bdlaws.minlaw.gov.bd/act-1692/act-chapter-print-2701.html) repeals
the 2025 Personal Data Protection Ordinance 61 and its 2026 amendment Ordinance 23. The
[former ordinance entry 1574](https://bdlaws.minlaw.gov.bd/act-1574/act-chapter-print-2585.html)
also explicitly marks the ordinance repealed. Older ordinance-only summaries are historical.

Assess territorial scope, data-fiduciary/processor roles, permitted processing grounds, rights,
security, retention and cross-border transfer/classification duties against the current Act and
implementing rules. Cover operational records and archives as well as primary database rows.
Do not infer a universal localization rule, consent requirement or complete compliance status
from hosting in Bangladesh. Verify Gazette notifications and applicable rules before onboarding;
English descriptions here are engineering summaries of the official text.

## EU obligations and dates

GDPR obligations depend on processing and roles. Assess legal basis, minimization, retention,
processor terms, security, impact assessment and transfer mechanisms against the
[GDPR text](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng). A configured system is not by itself
GDPR compliance; the controller/operator must implement the organizational duties.

The Commission states that the AI Act generally became applicable on 2 August 2026, with phased
exceptions. The AI Omnibus entered into force on 27 July 2026. Relevant Annex III high-risk rules
apply from 2 December 2027 and regulated-product high-risk rules from 2 August 2028. Relevant
transparency duties apply from 2 August 2026.
Classify each intended use rather than declaring the whole platform low risk. Recheck the
[Commission framework and timeline](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)
and the [Omnibus legal text, Regulation (EU) 2026/1744](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202601744)
before release. Assess provider/deployer roles and intended use separately from the model choice.
Human approval and typed inputs do not determine legal risk classification.

The CRA's reporting obligations apply from 11 September 2026 and main obligations from
11 December 2027 where the product/operator falls within scope. Actively exploited vulnerabilities
and severe incidents have different final-report rules: do not apply one blanket 14-day deadline.
For an in-scope manufacturer, reporting guidance specifies an early warning within 24 hours of
awareness and notification within 72 hours. The final exploited-vulnerability report is due no
later than 14 days after a corrective measure is available; a severe-incident final report is due
within one month of the 72-hour notification. Open-source-steward reporting has a different date,
11 December 2027. Determine the actual role rather than applying an open-source exception to
publicly visible proprietary source. See the
[Commission CRA overview](https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act)
and [incident-specific reporting guidance](https://digital-strategy.ec.europa.eu/en/policies/cra-reporting).
Review product/remote-processing scope; a SaaS label or local installation alone does not resolve it.

## Commercial onboarding deliverables

Prepare a signed scope and license, controller/processor assessment and DPA where appropriate,
subprocessor list, hosting/transfer decision, retention schedule, security responsibilities,
support channels, incident contacts and any SLA with its measurement/exclusions/remedies.
No commercial SLA, DPA template, certification, insurance or universal legal approval is supplied
by this repository. [Privacy](privacy.md), [SLOs](../scaling/slo.md) and
[security controls](../security/controls.md) distinguish implementation from required future work.

Assign an accountable operator and incident/privacy contact before customer processing. Record
who receives requests, approves subprocessors, rotates keys, handles account revocation and
decides retention/legal holds. Recheck after new jurisdictions, destinations, regulated uses,
providers or material law changes; retain the dated assessment privately. Operational approval
does not replace required legal advice.

## Evidence and review ownership

For a customer deployment, maintain the decisions in a scoped onboarding record: destination and
account permission, permitted actions/fields, license, controller/processor roles, notices,
subprocessors/transfers, retention, incident contacts and support responsibilities. Revisit the
record when the workflow, provider, jurisdiction or processing purpose changes.

The [commercial readiness checklist](commercial-readiness.md) provides the handoff structure.
[Data lifecycle](../security/data-lifecycle.md) maps technical stores to retention/access duties;
[availability objectives](../scaling/slo.md) supplies the measurement contract for any later SLA.
