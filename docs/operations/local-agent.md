# Standalone local browser agent

The standalone application runs on the owner's machine with SQLite, Playwright Chromium and an
already-installed local Ollama model. It uses neither the fleet's PostgreSQL/Redis services nor a
Docker runtime. No cloud model, API key or paid service is required or enabled.

## Start and use

1. Install the workspace with `uv sync`, then install Chromium with `python -m playwright install chromium`.
2. Start Ollama with an already-installed model. Set `FW_AGENT__MODEL_ID` to its exact installed name.
   The application refuses cloud-suffixed models, models absent from local inventory, remote-backed
   model metadata, redirects and non-numeric/non-loopback model endpoints.
3. Copy the agent group from `.env.example` into the local ignored `.env`. The typed boundary owns
   the model URL/name, database/profile/evidence paths, loopback host/port, destination origins,
   headless setting, deadlines, body/content/model/tab/action/approval budgets and optional CDP URL.
   `FW_AGENT__HISTORY_LIMIT` controls how many recent tasks the UI/API lists, newest first; older
   records remain in SQLite and can still be retrieved by their identifiers.
4. Run `python -m fw_agent` from the repository root. Open the exact HTTP origin defined by the
   configured numeric loopback host and port. The API deliberately rejects alternate Host headers,
   remote clients, cross-site requests and mutation requests without same-origin CSRF authorization.
5. Select a template and explicit destination, describe the draft, and choose **Read pages and draft
   locally**. Wait for `AWAITING_APPROVAL`; inspect the source, final draft, full proposal and hash.
6. Edit the draft if necessary. Saving edits cancels the old proposal and creates a new proposal/hash.
   **Approve this exact save** consumes one unexpired approval. Download the receipt after confirmation.
7. Use **Cancel task** or **Stop all agent tasks** to halt work. The global stop requires application
   restart before new tasks can start. An action interrupted after approval becomes `UNKNOWN`.

## Three maintained workflows

| Template | Source tab | Destination tab | Effect |
|---|---|---|---|
| Maintenance request | Owned equipment status | Maintenance draft form | Saves an owned local record |
| Dispatch handover note | Owned dispatch status | Handover draft form | Saves an owned local record |
| Inspection summary | Owned inspection observations | Inspection draft form | Saves an owned local record |

The lab is enabled explicitly by configuration. These are functional owned workflows;
they do not send emails, post publicly, buy anything or integrate with a third-party production app.
Other explicitly authorized origins can be configured only when they implement the same strict form
and receipt contract. This is not an arbitrary-site autonomous agent. CAPTCHA/login bypass is absent.

## Approval and uncertainty

SQLite WAL with full synchronous durability is the action authority. SHA-256 binds the complete
template snapshot, origin, request, captured source and final title/body. Approval is atomically
consumed before browser execution. Expired, replayed and changed approvals are refused. Changing a
template after a proposal was created also requires a fresh proposal. Approval cannot be emitted by
the model: its schema contains only `title` and `body`, with extra fields forbidden.

`PREPARING → AWAITING_APPROVAL → ACTING → CONFIRMED` is the normal flow. Interrupted actions become
`UNKNOWN`, including `ACTING` rows found at application restart. The agent never blindly resubmits
an UNKNOWN action. **Check destination receipt** performs a read only. A receipt must match the task
identifier, hash, title and body before confirmation. Missing or mismatched receipts retain UNKNOWN
for human investigation. The owned lab records one idempotent receipt for each exact task.

## Browser and local API boundary

Dedicated persistent profiles are the default. Only that application's profile pages are controlled.
Optional loopback CDP attaches to Chromium and creates a new isolated context; it deliberately does
not inherit the owner's existing tabs or login. Closing the agent closes its own context and stops
the Playwright connection. It does not call `browser.close()` on the owner's attached browser.

The agent uses two tabs and nine explicit navigation/fill/click interactions for a complete template.
The title/body wire schema, identifier formats, hash serialization and named adapter interaction
cost are versioned protocol constraints; deployment limits come from the central settings boundary.
Waits, reads and evidence capture have bounded timeouts. Context routing blocks other origins,
and a configured request ceiling bounds each prepare, execute or reconciliation phase. It blocks
preapproval mutations, popup navigation and all mutation payloads except the single exact approved
POST to the maintained template's accept path. Service workers are blocked.
WebSockets are denied for the entire dedicated/isolated-CDP context lifetime, before task pages
are opened; rejection does not connect to the remote WebSocket server. HTTP request routing alone
does not cover that transport. The model cannot choose selectors, URLs or operations.
Destination page text remains untrusted reference material; this
constrains authority even if the model repeats poisoned prose. Human content review remains necessary.

The UI uses same-site HTTP-only session cookies, same-origin CSRF tokens, strict Host/client/Origin
checks, bounded bodies, no CORS wildcard, a self-only content security policy and no-store responses.
Loopback HTTP is intentional; remote exposure/reverse proxying is unsupported. Local hostile software
with access to the same user account is outside this boundary. Keep the SQLite database, profile,
screenshots and receipt exports private: they can contain the source and human draft.
On POSIX, the application restricts its owned state/profile/evidence directories to0700 and state
files to0600, including SQLite WAL/SHM. It preserves existing content while tightening permissions
and refuses symlink or foreign-owned state paths. Use dedicated directories for these paths.
Windows inherits the chosen directory's ACLs; POSIX mode checks do not establish Windows ACL privacy.

These application-level HTTP/WebSocket controls are not an operating-system network sandbox.
Other browser channels such as WebRTC, WebTransport and DNS are not claimed to be constrained by
Playwright HTTP routing. Use only owned or expressly authorized contract pages; do not use this
application to execute arbitrary hostile sites. Isolating hostile executable pages requires an
independent OS/container egress policy, which this lightweight standalone runtime does not install.

## Verification and recovery

`pytest -q packages/fw_agent/tests -m 'not slow'` runs authority, API and real Chromium tests without
a local model. `pytest -q packages/fw_agent/tests --agent-model-proof` additionally exercises all three
templates with the installed local model and prints its private local evidence directory.
CI does not claim to have an installed model: that one proof skips unless explicitly requested.

After power loss, restart the application against the same SQLite database and profile. Review
UNKNOWN tasks and reconcile
receipts; never delete task rows to force a retry. JSON evidence records the exact approval hash and
matching receipt; screenshots show the destination acknowledgement.

## Model and review maintenance

The installed model is selected by typed settings, not by task text. The adapter checks local
inventory and remote-backed metadata, requests a strict title/body JSON schema, bounds model
response size/tokens/time, and supplies no action tools. See the
[official structured chat format](https://docs.ollama.com/api/chat).

Treat page content and model prose as untrusted. Review both title and body, including any
unsupported inference. Unsaved fields survive blur, manual refresh and polling; approval refuses
them until Save edits produces a new proposal. Confirm that the final receipt matches the reviewed
content rather than checking only the CONFIRMED label.

For upgrades, stop active tasks, preserve the SQLite/profile/evidence directories, back up private
state and inspect UNKNOWN tasks after restart. Re-run approval, cancellation, injection and
two-origin HTTP/WebSocket tests when changing templates or browser policy. Actual installed-model
proof is separate from default CI; POSIX permission checks do not establish Windows ACL privacy.
