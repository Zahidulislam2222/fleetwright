# Legal and deployment compliance register

Fleetwright currently operates owned freight and maintenance workflows. A software license,
authorized account and website permission are separate requirements. Before onboarding another
destination, the operator must establish all three and record jurisdiction-specific obligations.
This register is an engineering checklist for legal review, not a legal opinion or certification.
Sources were checked on 2026-10-13; recheck before a commercial deployment or material use change.

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
| California privacy | CCPA/CPRA scope, business/service-provider role, rights and contract conditions | Applicability assessment; request process and appropriate contractual restrictions |
| AI systems/content | EU AI Act role, intended use, risk classification and transparency | Per-workflow assessment, human oversight and required AI-content disclosure |
| Product cybersecurity | CRA product/manufacturer scope and reporting applicability | Vulnerability intake, release/support process and applicable reporting escalation |
| Consumer protection | Deceptive claims, fake reviews/testimonials and misleading AI output | Accurate capability claims and prohibition on deceptive engagement |
| Communications/payments | Marketing consent, messaging laws, payment/financial duties | Separate authorized workflow review; no bundled payment or messaging service is represented |
| Other jurisdictions | Operator, customer, destination, hosting and data-subject locations | Local counsel review, including Bangladesh where relevant; no universal-law claim |

The Supreme Court's *Van Buren* decision addresses a CFAA interpretation; it does not authorize
all scraping or eliminate contract/privacy duties. Use the [primary judgment](https://www.supremecourt.gov/opinions/20pdf/19-783_k53l.pdf)
and a scoped legal assessment rather than a blanket “public data is free to use” rule.
California applicability and rights depend on the business and processing: see the
[California Attorney General's CCPA guidance](https://oag.ca.gov/privacy/ccpa).
The [FTC review/testimonial guidance](https://www.ftc.gov/business-guidance/resources/consumer-reviews-testimonials-rule-questions-answers)
informs the prohibition on deceptive review automation.

## EU obligations and dates

GDPR obligations depend on processing and roles. Assess legal basis, minimization, retention,
processor terms, security, impact assessment and transfer mechanisms against the
[GDPR text](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng). A configured system is not by itself
GDPR compliance; the controller/operator must implement the organizational duties.

The Commission states that the AI Act generally became applicable on 2 August 2026, with phased
exceptions. Following the AI Omnibus, relevant Annex III high-risk rules apply from 2 December
2027 and regulated-product high-risk rules from 2 August 2028. Transparency duties already matter.
Classify each intended use rather than declaring the whole platform low risk. Recheck the
[Commission framework and timeline](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)
and applicable legal text before release.

The CRA's reporting obligations apply from 11 September 2026 and main obligations from
11 December 2027 where the product/operator falls within scope. Actively exploited vulnerabilities
and severe incidents have different final-report rules: do not apply one blanket 14-day deadline.
Use the [Commission CRA overview](https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act)
and its linked reporting guidance for the incident-specific timeline.

## Commercial onboarding deliverables

Prepare a signed scope and license, controller/processor assessment and DPA where appropriate,
subprocessor list, hosting/transfer decision, retention schedule, security responsibilities,
support channels, incident contacts and any SLA with its measurement/exclusions/remedies.
No commercial SLA, DPA template, certification, insurance or universal legal approval is supplied
by this repository. [Privacy](privacy.md), [SLOs](../scaling/slo.md) and
[security controls](../security/controls.md) distinguish implementation from required future work.
