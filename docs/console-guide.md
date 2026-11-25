# Console guide

A plain-language guide to the Fleetwright operator console: what each screen shows, what the states
mean and what to do when something looks wrong. The console's help assistant answers from this
guide and the other published documentation.

## What you are looking at

Fleetwright runs a fleet of browser workers that watch a job board, hold exactly one claim per matching job,
and crawl catalogues. The public workspace runs against an **owned freight exchange**: a
load board owned and operated by this project, so nothing commercial is booked and no third-party site is touched.

Anonymous visitors get a **read-only, redacted** view of the public workspace: emails and client addresses
are masked. The public workspace login (shown on the sign-in page) adds the workspace controls. Staff
accounts sign in with a password and a one-time code from an authenticator app.

Roles, from least to most access: **Visitor** (anonymous, read-only), **Viewer** and **Guest**
(signed-in, read-only; Guest can use workspace controls), **Operator** (can change filters and enter
one-time codes), **Owner** (everything, including workflow approvals and access grants). The server
checks the role on every request; hiding a button is never the only protection.

## Screens

### Overview

Claims by state over the last hour, worker health and alerts. **Healthy** workers sent a heartbeat
recently; **stale** ones missed several; **dead** ones stopped answering. Alerts appear for stale
workers, sessions that need attention, and claims being reconciled.

### Workers

Every browser worker slot, its cell, mode (watcher or claimer), account and last heartbeat. Slots
stopped on purpose during a redeploy are not counted as missing. A worker is killed and replaced
safely at any time: it keeps no state of its own.

### Accounts & sessions

The board accounts the claimers act as. Session states: **fresh** (logged in), **expiring** (will be
refreshed before it lapses), **expired**, and **one-time code needed** (the board asked for a code;
an operator can type it here, it goes straight to the waiting worker and is never stored or logged).

### Filters

Which loads the fleet tries to claim: origin, destination, minimum rate, equipment and weight.
Filters are data. Every edit is versioned, written to the audit log and reloaded by the dispatchers
immediately, without a restart.

### Schedules

Time-zone-aware windows that switch filters and accounts on and off.

### Claims

Every detected load and what happened to it, with the full state timeline:

- **QUEUED** — a detection matched a filter; exactly one claim exists for that job.
- **LEASED** — one worker holds the claim with a fencing token until the lease expires.
- **ACTING** — that worker is sending the booking now.
- **CONFIRMED** / **FAILED** — the board gave a definite answer.
- **UNKNOWN** — the booking may have happened but the answer was lost (for example the worker died
  mid-action). Fleetwright never retries an UNKNOWN claim blindly, because a retry could book twice.
- **RECONCILED** — the reconciler asked the board what the account really booked and recorded it.

If you see UNKNOWN claims, that is the system being honest about uncertainty, not a failure. They
normally move to RECONCILED within seconds. One that stays UNKNOWN needs a human to check.

### Latency

Each stage is measured separately: board publish → detection, detection → queued → leased → action
sent → confirmed. Publish→detect is never averaged into detect→action, so you can see where time goes.
Percentiles (p50/p95/p99) are over the recent window.

### Crawl jobs

Crawls are defined as data (seeds, scope rules, extractors). Each cycle reports item counts; a sudden
drop or zero results raises an alarm, which catches silent page-layout changes. Exports are private.

### Browser workflows

Approved, versioned workflows that AI clients can request through the scoped MCP interface. Risky
actions wait for an exact owner approval; access grants are scoped, expire and can be revoked.

### Audit log

Append-only. Every change and every claim action is recorded with who, what and when. Visitors see
it redacted.

### Settings

Tenant, people and security information for your tenant.

## Workspace controls

Signed in with the public workspace login, you can start a capped load burst (a few minutes, rate
limited) and inject faults on the owned board: rate limits, server errors, slow responses, forced
session expiry, a layout change and competing bots. Settings reset themselves after a while. Then
watch Claims, Latency and the Overview react.

## Common questions

**Why did a claim fail?** Usually another bot booked the load first, the board returned an error,
or the lease ran out before acting. The claim's timeline shows the step and the reason.

**Can two workers book the same load?** No. Postgres allows exactly one claim per job, and a fencing
token rejects any worker that lost its lease. See the claim lifecycle and ADR 0001.

**Is the data live?** The header says **Live** with **Live updates** when the event stream is
connected, or "Refreshing every N s" while it reconnects. The static reference build says it shows offline reference data.

**What is measured and what is a target?** Measured results include 50 and 70 browser contexts sustained
for an hour on one PC (fixture pages, not authenticated freight workers) and the recorded test runs. 1M+ console users and 99.9% availability are design
targets with a documented path, not measured results; the public workspace runs on one shared server.

**Who do I contact?** Open an issue on the public GitHub repository. Report security problems as
described in SECURITY.md, not in an issue.

## The help assistant

The assistant is an AI. It answers from this documentation and from read-only console data your
role can already see; it cannot change anything. It can be wrong, so check important answers against
the linked sources. When the AI is unavailable or the daily AI budget is used up, it shows the most
relevant documentation passages instead. Questions are not stored by Fleetwright; the AI provider
processes them to produce an answer (see the privacy notes).
