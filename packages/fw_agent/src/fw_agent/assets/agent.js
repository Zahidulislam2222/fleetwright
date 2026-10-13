"use strict";
let csrf = "";
let copy = {};
let busy = false;
let maxContent = 0;
const unsavedDrafts = new Map();
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
async function api(path, body) {
  const options = body === undefined ? {} : {method: "POST", headers: {
    "Content-Type": "application/json", "X-CSRF-Token": csrf}, body: JSON.stringify(body)};
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
  return data;
}
async function action(operation) {
  document.querySelector("#error").textContent = "";
  try { await operation(); await refresh(); }
  catch (error) { document.querySelector("#error").textContent = error.message; }
}
function button(text, operation, className) {
  const node = el("button", text, className);
  node.addEventListener("click", () => action(operation));
  return node;
}
function renderTask(task) {
  const card = el("article", undefined, "task");
  const proposal = task.proposal;
  card.append(el("h3", `${proposal.template.name} · ${task.state}`));
  card.append(el("p", `${proposal.origin}${proposal.template.form_path}`));
  card.append(el("small", task.id));
  card.append(el("p", proposal.request));
  if (proposal.draft) {
    const editable = task.state === "AWAITING_APPROVAL";
    const displayed = editable ? (unsavedDrafts.get(task.id) ?? proposal.draft) : proposal.draft;
    const title = el("input"); title.value = displayed.title; title.maxLength = 200;
    const body = el("textarea"); body.value = displayed.body; body.maxLength = maxContent;
    if (editable) {
      const remember = () => unsavedDrafts.set(task.id, {title: title.value, body: body.value});
      title.addEventListener("input", remember); body.addEventListener("input", remember);
    }
    title.readOnly = !editable; body.readOnly = !editable;
    const titleLabel = el("label", copy.title); titleLabel.append(title);
    const bodyLabel = el("label", copy.body); bodyLabel.append(body);
    card.append(titleLabel, bodyLabel);
    if (editable) {
      card.append(el("p", `${copy.expiry}: ${new Date(task.expires * 1000).toLocaleString()}`));
      card.append(el("code", task.hash));
      const approve = button(copy.approve, async () => {
        if (title.value !== proposal.draft.title || body.value !== proposal.draft.body)
          throw new Error(copy.edits_required);
        await api(`/api/tasks/${task.id}/approve`, {hash: task.hash});
      });
      approve.disabled = task.expires * 1000 <= Date.now() || busy;
      card.append(approve, button(copy.save_edit, () => api(`/api/tasks/${task.id}/edit`, {
        hash: task.hash, draft: {title: title.value, body: body.value}})));
    }
  }
  if (["PREPARING", "AWAITING_APPROVAL", "ACTING"].includes(task.state))
    card.append(button(copy.cancel, () => api(`/api/tasks/${task.id}/cancel`, {})));
  if (task.state === "UNKNOWN")
    card.append(button(copy.reconcile, () => api(`/api/tasks/${task.id}/reconcile`, {})));
  if (task.state === "CONFIRMED") {
    const download = el("a", copy.evidence);
    download.href = `/api/tasks/${task.id}/evidence`; download.download = ""; card.append(download);
  }
  const log = el("details"); log.append(el("summary", copy.details));
  log.append(el("pre", JSON.stringify({proposal: task.proposal, events: task.events}, null, 2)));
  card.append(log); return card;
}
async function refresh() {
  const tasks = await api("/api/tasks");
  busy = tasks.some((task) => ["PREPARING", "ACTING"].includes(task.state));
  document.querySelector("#prepare").disabled = busy;
  const target = document.querySelector("#tasks");
  // Avoid replacing editable inputs while the human is reviewing or typing.
  if (target.contains(document.activeElement) && ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
  const editableIds = new Set(tasks.filter(task => task.state === "AWAITING_APPROVAL").map(task => task.id));
  for (const id of unsavedDrafts.keys()) if (!editableIds.has(id)) unsavedDrafts.delete(id);
  target.replaceChildren(...tasks.map(renderTask));
}
async function init() {
  const config = await api("/api/bootstrap"); csrf = config.csrf; copy = config.data.ui;
  maxContent = config.max_content_chars;
  document.querySelector("#request").maxLength = maxContent;
  const assignments = {heading: config.data.title, subtitle: config.data.subtitle, notice: config.data.safety_notice,
    model: `${copy.model}: ${config.model}`, "template-label": copy.template, "origin-label": copy.origin,
    "request-label": copy.request, prepare: copy.prepare, "tasks-heading": copy.tasks, refresh: copy.refresh, kill: copy.kill};
  for (const [id, text] of Object.entries(assignments)) document.getElementById(id).textContent = text;
  for (const template of config.data.templates) {
    const option = el("option", template.name); option.value = template.id;
    document.querySelector("#template").append(option);
  }
  for (const origin of config.origins) {
    const option = el("option", origin); option.value = origin; document.querySelector("#origin").append(option);
  }
  document.querySelector("#task-form").addEventListener("submit", (event) => {
    event.preventDefault();
    action(() => api("/api/tasks", {template_id: document.querySelector("#template").value,
      origin: document.querySelector("#origin").value, request: document.querySelector("#request").value}));
  });
  document.querySelector("#refresh").addEventListener("click", () => action(refresh));
  document.querySelector("#kill").addEventListener("click", () => action(() => api("/api/stop", {})));
  await refresh();
  setInterval(() => refresh().catch(error => {
    document.querySelector("#error").textContent = error.message;
  }), config.data.poll_interval_ms);
}
init().catch((error) => { document.querySelector("#error").textContent = error.message; });
