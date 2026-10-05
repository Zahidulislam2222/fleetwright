# Claim lifecycle

The claim state machine (`packages/fw_core/src/fw_core/claims.py`) is the part of Fleetwright that
guarantees **no job is acted on twice**. Every rule below is enforced by a database statement, not
by worker code.

```
DETECTED ──▶ QUEUED ──▶ LEASED ──▶ ACTING ──▶ CONFIRMED
                ▲          │          │   └──▶ FAILED
                │          │          └──────▶ UNKNOWN ──▶ RECONCILED
                └──────────┘  lease expired before acting (re-queued)
```

## States

| State | Meaning | Who moves it |
|---|---|---|
| `QUEUED` | A detection matched a filter; one claim exists for the job | Dispatcher |
| `LEASED` | A claimer holds it with fencing token *n* until the lease expires | Claimer |
| `ACTING` | The claimer is sending the booking now | Claimer, only while its lease is current |
| `CONFIRMED` / `FAILED` | The target gave a definite answer | Claimer |
| `UNKNOWN` | The action may have happened but the answer is missing | Claimer (lost answer) or sweep (expired during `ACTING`) |
| `RECONCILED` | The reconciler checked the target and recorded what really happened | Reconciler |

## Rules

1. **One claim per job.** `INSERT … ON CONFLICT (tenant_id, target_job_key) DO NOTHING`. Exactly
   one detection wins, whatever the number of watchers.
2. **Fencing tokens.** Leasing takes `nextval('claim_fence')`. Every later step includes the token,
   and the `UPDATE` matches only if it is still current. A worker that paused (garbage collection,
   a frozen VM, a network stall) and woke up late is rejected.
3. **Database clock only.** Lease expiry compares against `clock_timestamp()` in Postgres. Worker
   clocks are measured (midpoint rule) for latency reporting but never trusted for correctness.
4. **Only claims that never reached `ACTING` are re-queued.** A claim whose lease expired while
   `LEASED` goes back to `QUEUED` (or `FAILED` when too old). A claim that expired while `ACTING`
   becomes `UNKNOWN`.
5. **`UNKNOWN` is never retried.** Retrying could book the job twice. The reconciler opens the
   account's sealed session, asks the target what the account has booked, and resolves the claim
   as booked or not booked.
6. **A late actor still wins with the truth.** If the reconciler marked a claim `UNKNOWN` and the
   original actor then returns a definite answer with a still-current fence, that answer is
   recorded.
7. **One active lease per account.** A partial unique index prevents two concurrent actions on
   one target account.
8. **History and outbox in the same statement.** Each sweep rule is a single statement that moves
   the rows, writes `claim_events` and writes the outbox messages, so row locks are held for one
   round trip.

## Evidence

| Test | What it proves |
|---|---|
| 20-way lease race | Exactly one lease wins |
| Stale fence | An old token cannot move the claim |
| Crash while `LEASED` | The claim is re-queued and booked once |
| Crash while `ACTING` | The claim becomes `UNKNOWN` and is reconciled against the board |
| Hypothesis interleavings (40 generated schedules) | A terminal state never changes |
| 200 competitors × 10,000 jobs | 9,897 confirmed claims = 9,897 bookings on the board, 0 duplicates |
| Engine chaos run (5xx errors, slow responses, lost acknowledgements, rival bots) | Every claim ends confirmed, failed or reconciled, and matches the board's ground truth |
