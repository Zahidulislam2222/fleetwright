# Catalogue crawling

An operator or owner can start an approved catalogue cycle from **Console → Crawl jobs**. The
console shows durable progress, extraction errors, change counts and quality alerts. Exports contain
only the configured allowed fields. Public visitors can inspect aggregate progress; submission,
cancellation and export require an authenticated operator role and mutations require CSRF.

Start the worker with `uv run python -m fw_coordinator.crawls`. Apply database migrations first.
The release template supervises the crawler independently from freight and approved browser jobs.
The API and crawler share the private export volume. The local environment template documents
all `FW_CRAWL__*` settings; deployment settings control the volume path and resource limits.

Definitions live in `config/crawls.yaml`: approved origin name, seed paths, JSON Pointer or CSS row
selector, optional next-page selector, field allowlist/types/lengths, identity field and robots
policy. Arbitrary operators cannot submit selectors or destinations through the API. Additional
public origin URLs belong to typed `FW_CRAWL__ORIGINS`; they receive no private-address exception.
Review destination authorization and network egress before enabling one.

Robots are respected by default. Robots errors fail closed; redirects are refused. Requests have
response-size and time bounds. Shared per-origin admission, bounded retries and a durable failed
frontier prevent an unbounded retry loop. Cancellation finishes at the next bounded page boundary.
An expired lease is recovered with a new fence, retaining pages already committed.

A layout change can produce an extraction failure or result-drop alert. Inspect the maintained
contract and destination before running another cycle. An incomplete cycle does not report old
unseen items as removed. JSONL exports for failed cycles contain only records actually extracted
in that cycle. Missing identity/type/length data causes page failure rather than silent truncation.

The configured retention period deletes old export files, corresponding frontier data and old
current-item rows. Run the worker regularly for retention enforcement. Backups have their own
retention policy; deleting an export does not erase data from previously retained database archives.

The owned catalogue provides a stable, paginated target. Its alternate layout exercises the quality
alarm. It is separate from the live freight feed. External webhooks, paid proxy/captcha services and
Parquet/S3 delivery are not enabled in this release; use the private JSONL export interface.
