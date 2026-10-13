# ASVS 5.0 assurance map — 13 October 2026

This is an engineering evidence map, **not ASVS Level 2 compliance, certification, or an independent
penetration test**. L2 requires every applicable L1 and L2 requirement; selected passing controls
cannot establish that claim. Unlisted requirements remain unassessed. The application, owned
mock destination and local browser agent have different trust boundaries; destination login
controls are not evidence for console identity controls.

Reference: [OWASP ASVS 5.0.0 release](https://github.com/OWASP/ASVS/tree/v5.0.0/5.0/en).
Requirement identifiers below were checked against that release; descriptions are brief project
interpretations. Evidence paths are relative to this repository. Source coverage and deployed
behavior must both be reviewed again for the final release.

| ASVS requirement / area | Project evidence | Status / assessment boundary |
|---|---|---|
| 8.1.1 function/data authorization rules | `docs/security/controls.md`, `docs/security/threat-model.md`, API role checks and scoped grants | Documented baseline; owner must review rules for every new endpoint |
| 8.1.2 field permissions | Strict workflow input contracts, bounded public views, owner-only grant/approval mutation | Partial: field-level matrix for every route not independently assessed |
| 8.2.1 explicit function authority | API/MCP role checks; `apps/coordinator/tests/test_workflow_review.py`, `test_workflows.py` | Existing tests; final full-suite/deployment evidence required |
| 8.2.2 object authority | Tenant predicates, PostgreSQL forced RLS, job/grant lookup checks | Existing tenant/workflow tests; privileged system-role queries remain trusted boundary |
| 8.2.3 field authority | Allowlisted contract fields, evidence export projection, capped demo controls | Partial; no complete property-by-property independent assessment |
| 8.3.1 trusted enforcement | Approval and grant checks execute in API/core/database; model cannot issue approval | Existing browser workflow suite passed in the local 31-case runtime acceptance |
| 8.4.1 tenant separation | RLS and tenant-bound workflow grants; API/gateway tests | Existing positive/negative cases; large skew/multi-zone expansion not proven |
| 6.1.1 authentication attack controls | `fw_coordinator/auth.py`, central AuthSettings, threat model | Rate/hash concurrency/lockout implemented; configuration operational review remains |
| 6.3.1 anti-automation | Bounded password hashing and account/network attempt budgets | Existing authentication tests; distributed attack simulation not performed |
| 6.3.2 default identities | Public capped demo identity deliberately exists; private owner access separate | Documented exception: public demo is not a private production tenant |
| 6.3.3 MFA | Console password+TOTP; token hashes and challenge expiry | Public demo code is intentionally visible; owner route requires private factors |
| 6.5.1 single-use authentication code | `auth.py` records successful TOTP steps; replay checks | Existing implementation; do not equate destination email OTP with console MFA |
| 6.2.2–6.2.4 password lifecycle | No public self-service password change/reset interface | Gap: operator-mediated recovery does not satisfy self-service password requirements |
| 5.1.1, 5.2.1–5.2.3 file input | Application has bounded generated JSON evidence, not general public file upload | Upload controls not applicable to absent upload feature; reassess if added |
| 5.3.2 safe file paths | UUID/digest-derived evidence names, archive manifest validation; backup/recovery tests | Partial: all artifact/archive flows require final release path traversal assessment |
| 5.4.1–5.4.2 download names | Fixed/generated JSON export names; owner-authorized evidence endpoints | Existing contract/browser export checks; broader header fuzzing unassessed |
| V1 encoding/query construction | Parameterized SQL and React rendering | Source patterns reviewed; independent injection assessment not complete |
| V2 validation/business integrity | Fingerprinted exact-action approval, expiry/replay/changed-input tests, DB fencing | 31-case runtime acceptance includes real owned Chromium workflows and crash recovery |
| V3 frontend | CSRF, cookie flags, CSP/security headers and origin checks | Static release builder replaces inline-script relaxation with exact hashes; inline styles remain an exception; final browser/deployment proof required |
| V4 API | Typed request/response contracts, bounded pagination, HTTP authorization | Network mixed-load test below; authorization fuzzing remains bounded test coverage |
| V7 sessions | Opaque session digests, expiry/revocation, idle SSE authority checks | Existing gateway/session tests; stolen-device posture assessment absent |
| V9 self-contained tokens | Console/MCP authority is opaque server-side state, not JWT | JWT-specific controls not applicable to present token design |
| V10 OAuth/OIDC | No public OAuth/OIDC authorization-server/client flow in application | Not applicable to present application; external documentation integrations are separate |
| V11 cryptography | AES-GCM envelopes with AAD; Ed25519 offline release signature tooling | Key custody/rotation depend on operator; hardware KMS not deployed |
| V12 transport | Public TLS and private backend network; pinned crawl HTTP destination | Internal database/Redis TLS is not established on current single-host network |
| V13 configuration | Typed environment boundary, lockfiles, no public credentials | Final full-tree secret/config scan remains a release gate |
| V14 data protection | Redacted evidence, bounded artifacts, retention, private archives | Full data-subject request automation and independent retention assessment absent |
| V15 supply chain/design | Native Trivy CycloneDX inventory, source hashes, signed-release helper, source scans | Hardened candidate removed11HIGHfindings (0HIGH/CRITICAL); frozen candidate pip-audit2.10.1 found0vulnerabilities in52externalPythonpackages; native verification-image scan0HIGH/CRITICAL and1094-componentSBOM; final exact-release image needs separate scan/signature; no SLSA claim |
| V16 audit/errors | Transactional DB audit, redaction, intent/outcome records | External uncertainty retained as UNKNOWN; no automatic replay |
| V17 WebRTC | No WebRTC feature | Not applicable to present application |

## Authorized dynamic verification

Run adversarial requests only against isolated local databases and owned local destinations; the
shared public demo is checked functionally and is not a stress/penetration-test target.

| Scenario | Reproducible test / observed boundary |
|---|---|
| Changed/replayed/expired exact approval; revoked grant | Workflow core, review, browser and gateway suites |
| Cross-tenant job/evidence/stream access | Tenant/RLS, workflow and gateway suites; no broad internet scanning |
| Account group mismatch, simultaneous pacing admissions, delayed preparation/action cooldown | `packages/fw_core/tests/test_account_admission.py` and actual-browser `test_workflow_pacing.py`; targeted 27-case runtime suite and final integrated source suite passed |
| Unread/in-flight cell handover and relay/dispatch crashes | `apps/coordinator/tests/test_detection_handover.py`: 9 real DB/Redis cases, including batched payload authority and rollback; atomic directory/queuedclaim/rawmailbox moves; authoritative payload and retention protection; legacy backlog requires upgrade drain |
| Safe cell turns and worker drain | `apps/worker/tests/test_scheduler_and_drain.py`: real directory paging plus bounded cancel/release cases |
| API/SSE reconnect and slow consumer | `loadtest/tests/test_http.py`: real loopback coordinator/gateway, bounded clients; direct Hub overflow separately |
| Prompt injection/destination escape | Local agent and crawler suites; arbitrary third-party-site safety is not claimed |
| Archive tamper/wrong recovery key and manifest/path attacks | Backup/recovery suites; off-host operational restore is a separate gate |
| Browser process death after destination acceptance | Existing real workflow crash child + receipt reconciliation; blind retry forbidden |

Exceptions are tracked here openly; do not turn missing controls into passing findings. This map
must be updated with final release test/scan outcomes before a public security assurance claim.

## Dependency audit boundary

The full npm dependency scan includes development packages and retains one HIGH finding:
`braces` 3.0.3, CVE-2026-93687. The scanner returned no fixed version. That scan exits 1 and must
not be reported as green. The package is used in the trusted repository build toolchain;
production static assets do not require Node tooling. Acceptance of this exception requires
review and confirmation that the final static image contains neither Node nor this dependency.
No scanner rule or vulnerability identifier has been suppressed.

The frozen Python candidate inventory was extracted from its actual virtual environment.
`pip-audit` 2.10.1 reported zero vulnerabilities across 52 external distributions. Local workspace
packages were excluded from public PyPI lookups and remain covered by source review/scans.
Native image scanning covers operating-system and inherited global packages separately.

## Final source and bounded capacity evidence

The integrated release-source suite passed **260 tests with 6 platform/opt-in skips** in
777.824 seconds. Four agent state-privacy cases and the release symlink case separately passed
on real POSIX. The installed local-model/browser verification separately produced three
confirmed receipts. These supplemental checks retain their distinct platform/workload scope.

Independent source scanning covered all 154 staged files with zero findings and zero parser
errors after fixes; four later source/test deltas also passed. The configured Gitleaks, Bandit
and Semgrep hooks passed. Final artifact identity, native image scan and deployment rehearsal
remain separate release gates; selected source results do not establish ASVS certification.

The isolated no-network browser fixture sustained both 50 and 70 contexts for uninterrupted
hours: 3,601.986 and 3,602.632 seconds, respectively, with zero action errors and exit code 0.
The containers retained their 6/8 GiB caps, 2 CPU quotas and 2 GiB host-memory floor. See the
[scale evidence](../scaling/verification-2026-10-13.md) for complete rounds, actual sampled
resource charges, prior incomplete attempts, hardware and workload limitations.
