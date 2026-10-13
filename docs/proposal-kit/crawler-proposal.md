# Proposal draft: reliable authorized catalogue crawling

I build crawlers that make failures visible and preserve progress across worker interruptions.
Fleetwright demonstrates this against an owned, paginated catalogue using maintained JSON/CSS
extraction contracts, a durable frontier, robots rules, shared origin pacing and bounded retries.
Operators can inspect progress and export only the approved fields as private JSONL.

The important part is data quality: an incomplete crawl must not silently erase records. The
implementation distinguishes complete cycles from failures, detects zero results and substantial
result drops, deduplicates identities and avoids classifying unseen records as removed when a
cycle is incomplete. Network checks validate and pin destination addresses, reject prohibited
redirect targets, bound response sizes and terminate over-budget fetch processes before retrying.
Those behaviors have real HTTP/TLS, slow-response, layout-change and crash-recovery tests.

For your destination, I would first agree the permitted origin, required fields, identity rules,
request budget and output contract. The first reviewable milestone would be one authorized crawl
with repeatable extraction and an inspected export. Recovery, quality alarms and deployment would
then be checked against written acceptance criteria rather than a successful one-off scrape.

Current proof covers owned catalogue fixtures and the documented extraction contract. Residential
proxy providers, commercial CAPTCHA services, arbitrary webhook delivery, Parquet and S3 export
are not enabled in the current crawler. Any destination that requires those capabilities needs a
separate integration and authorization assessment; their operating costs are not included here.

Evidence: [crawler operations](../operations/crawler.md),
[real crawl/export tests](../../apps/coordinator/tests/test_crawler.py),
[adversarial network and recovery tests](../../apps/coordinator/tests/test_crawler_adversity.py).

Portfolio: https://zahidul-islam.com/ · GitHub: https://github.com/Zahidulislam2222
