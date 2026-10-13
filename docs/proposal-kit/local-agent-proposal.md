# Proposal draft: a local browser assistant with human approval

I built a local browser assistant that uses an installed Ollama model to draft content, then asks
the human to review the exact destination and text before saving it. SQLite stores the task,
approval and receipt history. The runtime needs no PostgreSQL, Redis or Docker service and does
not require paid inference.

The model produces a typed title/body draft. Maintained templates own the selectors, destination
paths and operation; the model cannot authorize an action. Approval binds the complete proposal
and expires after a configured interval. Editing a draft creates a new proposal, and consumed or
changed approvals cannot be replayed. An interrupted save remains uncertain until the destination
provides a matching receipt.

Three real local-model workflows were exercised in Chromium: maintenance requests, dispatch
handover notes and inspection summaries. Each uses source and form tabs and saves an owned local
record. The native review/edit/approval UI, cancellation, denied browser requests and isolated
CDP attachment were also tested. An attached owner's existing tab remained intact after shutdown.

For a content workflow, I would first define the authorized destination, draft schema and exact
save/publish boundary, then prove it on an owned test page before integrating a production target.
Content drafting and brainstorming can be scoped independently from permission to publish.

Current limits are deliberate: these are three owned record-saving templates, not verified social
network integrations. No autonomous posting, purchases, arbitrary-site navigation or general
vision-model control is claimed. CDP uses a new isolated context and does not inherit an existing
login. The loopback UI and HTTP/WebSocket policy are not an OS-level sandbox for hostile sites;
other browser network channels require independent isolation if that becomes part of the scope.

Evidence: [setup and operating boundary](../operations/local-agent.md),
[real model/browser flows](../../packages/fw_agent/tests/test_browser_flow.py),
[native UI and CDP preservation](../../packages/fw_agent/tests/test_ui_cdp.py),
[WebSocket server-observation regression](../../packages/fw_agent/tests/test_websocket_egress.py).

Portfolio: https://zahidul-islam.com/ · GitHub: https://github.com/Zahidulislam2222
