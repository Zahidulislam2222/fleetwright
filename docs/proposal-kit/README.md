# Fleetwright proposal kit

These drafts describe implemented work and its measured boundaries. They are reusable capability
and integration materials. Results are measured on owned destinations; no external customer's
business outcome is implied.

| Need | Draft |
|---|---|
| Authorized crawling and data quality | [Catalogue crawler proposal](crawler-proposal.md) |
| Coordinated browser workers and crash recovery | [Fleet proposal and eight technical answers](fleet-proposal-and-answers.md) |
| Local model assistance across browser tabs | [Local-agent proposal](local-agent-proposal.md) |
| Engineering decisions and verified outcomes | [Public case study](case-study.md) |

Tailor the destination, authorization, acceptance criteria and delivery scope before sending a
proposal. The fleet document contains eight reusable engineering topics; match them to the exact
questions in a client's brief. These files are drafts only and do not record any external submission.

## Evidence to cite

The current deployed release is `20261125-publication-rc1` (application code from the assistant release `20261125-assistant-rc5`); its
[25 November 2026 release record](../releases/2026-11-25.md) covers the console help assistant,
patched container images, the assistant's live evaluation and the failures found during the
release. Earlier records, such as the [14 October 2026 release record](../releases/2026-10-14.md)
and the [13 October 2026 measurement notes](../scaling/verification-2026-10-13.md), remain dated
history. The [changelog](../../CHANGELOG.md) lists every release. Together they distinguish
deployed releases from local engineering evidence.

When a brief asks for in-product AI help, cite the help assistant from the current record: answers
come from approved documentation and read-only data the asker can already see, every answer is
marked AI-generated, spend is bounded and a documentation-search fallback covers every failure.
Its evaluation (16 held-out cases) is a release check on owned content, not a measure of accuracy
on a client's material. No draft in this kit is dedicated to it yet.

No document here promises monthly availability, cloud deployment, arbitrary-site exactly-once
execution or an unmeasured fleet size. Scale and availability figures elsewhere are design targets
unless a record marks them as measured. Pricing and delivery dates are intentionally absent.

Three capability recordings have been produced from exact release rehearsal and actual local-model
workflows, with transcripts, hashes, full-file decode and browser playback checks. They predate the
25 November release, so they do not show the help assistant. They remain local artifacts and are
not an external publication. Identify their release, owned workload and approval boundary when
attaching them; do not imply customer deployment or production-scale capacity.

## Use and review

Choose the smallest capability that meets the request, confirm destination authorization and
receipt behavior, and define acceptance before estimating. Keep future scale/availability objectives
separate from recorded fixture results. Exact job-post question matching is optional; the eight
technical topics are reusable explanations. Pricing, contractual support and delivery dates require
an independently agreed scope. No proposal here has been sent externally.

## Scope and delivery handoff

Use [commercial readiness](../legal/commercial-readiness.md) to turn a capability discussion into
a destination-authorized delivery scope. Include exact acceptance, data categories, deployment
ownership, support boundaries and relevant dated evidence. Keep estimates tied to the agreed
workload, integrations and validation gates.

For growth planning, attach the [future architecture](../scaling/future-architecture.md),
[capacity assumptions](../scaling/capacity-model.md) and
[validation plan](../scaling/validation-plan.md). A proposed concurrency or reliability tier carries
its own representative workload, failure/recovery tests and operating budget review.
