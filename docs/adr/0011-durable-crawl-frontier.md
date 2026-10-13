# ADR 0011 — One durable crawl frontier

Status: accepted for the crawler implementation.

The crawler uses PostgreSQL as both its durable job authority and frontier. A second Redis
frontier would introduce another recovery boundary without improving this deployment's measured
workload. Existing freight dispatch continues to use Redis Streams and its transactional outbox.

Each crawl cycle stores an immutable extraction contract and fingerprint, a database-clock lease,
monotonic fence and unique pending paths. Pages commit independently. A replacement worker resumes
the pending frontier after lease expiry; a stale worker cannot commit. Cell ownership is checked
at every page transaction. Per-origin admission is shared across tenants through a database row.

HTTP fetching validates the allowed origin and every resolved address before connecting to the
chosen address. HTTPS retains the original hostname for certificate verification. Redirects and
compressed responses are rejected. The owned test destination has an explicit private-address
exception; additional configured origins do not inherit it. No page scripts or subresources run.

JSON Pointer and CSS extraction contracts specify allowed fields, required fields, types and
identity lengths. Outputs use private JSONL files; current items and hashes support change
classification. Only a complete successful cycle can classify removals. An extraction failure,
zero-result cycle, major result drop or page limit preserves earlier unseen records.

This is a bounded catalogue crawler. Commercial destination authorization, proxy/captcha vendor
integration and larger storage/throughput measurements require separate onboarding and evidence.
The existing production network has no general Internet egress; adding a public crawl origin does
not silently open that network.
