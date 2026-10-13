"""Draft, approve once, execute or reconcile. Uncertainty never unlocks a repeat action."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from typing import Any

from fw_agent.browser import Browser
from fw_agent.contracts import TEMPLATE_ACTION_COST, AgentData, Draft, Template
from fw_agent.model import LocalModel
from fw_agent.privacy import private_file
from fw_agent.store import Conflict, Store
from fw_core.settings import AgentSettings


class Runner:
    def __init__(self, settings: AgentSettings, data: AgentData, store: Store) -> None:
        self.settings = settings
        self.data = data
        self.store = store
        self.browser = Browser(settings)
        self.model = LocalModel(settings, data.model_system_prompt)
        self.running: dict[str, asyncio.Task[None]] = {}
        self.stopped = False

    def _spawn(self, task_id: str, coroutine: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coroutine)
        self.running[task_id] = task
        task.add_done_callback(lambda _: self.running.pop(task_id, None))

    def start(self, template_id: str, destination: str, request: str) -> str:
        if self.stopped:
            raise Conflict("agent stopped; restart the application to enable new work")
        if self.running:
            raise Conflict("one bounded task at a time; wait for the current task")
        if self.settings.max_actions < TEMPLATE_ACTION_COST:
            raise ValueError("template exceeds the configured browser action budget")
        template = self.data.template(template_id)
        destination = self.browser.destination(destination)
        if not request.strip() or len(request) > self.settings.max_content_chars:
            raise ValueError("request is empty or exceeds the configured content budget")
        task_id = self.store.create({"template": template.model_dump(), "origin": destination, "request": request})
        self._spawn(task_id, self._prepare(task_id))
        return task_id

    async def _prepare(self, task_id: str) -> None:
        try:
            async with asyncio.timeout(self.settings.task_timeout_s):
                proposal = self.store.get(task_id)["proposal"]
                template = Template.model_validate(proposal["template"])
                source = await self.browser.source(template, proposal["origin"])
                draft = await self.model.draft(template.prompt, proposal["request"], source)
                proposal.update({"source": source, "draft": draft.model_dump()})
                self.store.ready(task_id, proposal, self.settings.approval_ttl_s)
        except asyncio.CancelledError:
            if self.store.get(task_id)["state"] == "PREPARING":
                self.store.transition(task_id, "CANCELLED", "draft cancelled before approval")
            raise
        except Exception as exc:
            if self.store.get(task_id)["state"] == "PREPARING":
                self.store.transition(task_id, "FAILED", f"draft failed: {type(exc).__name__}")

    def edit(self, task_id: str, approval_hash: str, draft: Draft) -> None:
        task = self.store.get(task_id)
        if task["state"] != "AWAITING_APPROVAL" or task["hash"] != approval_hash:
            raise Conflict("proposal changed or is no longer editable")
        if len(draft.body) > self.settings.max_content_chars:
            raise ValueError("draft exceeds configured content budget")
        # Revoke the old proposal and make a new proposal, preserving history for both.
        self.store.transition(task_id, "CANCELLED", "human edited draft; superseded by fresh proposal")
        new_proposal = dict(task["proposal"])
        new_proposal["draft"] = draft.model_dump()
        replacement = self.store.create(new_proposal)
        self.store.ready(replacement, new_proposal, self.settings.approval_ttl_s)

    def approve(self, task_id: str, approval_hash: str) -> None:
        if self.stopped or self.running:
            raise Conflict("agent stopped or busy")
        task = self.store.get(task_id)
        template = self.data.template(task["proposal"]["template"]["id"])
        if template.model_dump() != task["proposal"]["template"]:
            raise Conflict("template changed; prepare a fresh proposal")
        self.browser.destination(task["proposal"]["origin"])
        self.store.claim(task_id, approval_hash)
        self._spawn(task_id, self._execute(task_id))

    def _confirm(self, task_id: str, receipt: dict[str, Any]) -> None:
        task = self.store.get(task_id)
        draft = task["proposal"]["draft"]
        expected = {"task_id": task_id, "hash": task["hash"], "title": draft["title"], "body": draft["body"]}
        if any(receipt.get(key) != value for key, value in expected.items()):
            raise ValueError("receipt does not match the exact approved content")
        evidence = self.settings.evidence_directory / f"{task_id}.json"
        private_file(evidence)
        evidence.write_text(
            json.dumps({"task_id": task_id, "approval_hash": task["hash"], "receipt": receipt}, indent=2),
            encoding="utf-8",
        )
        self.store.transition(task_id, "CONFIRMED", "matching destination receipt confirmed; evidence saved")

    async def _execute(self, task_id: str) -> None:
        try:
            async with asyncio.timeout(self.settings.task_timeout_s):
                task = self.store.get(task_id)
                receipt = await self.browser.execute(
                    task_id, task["hash"], task["proposal"], self.store.lab_token(task_id)
                )
                self._confirm(task_id, receipt)
        except asyncio.CancelledError:
            self.store.transition(task_id, "UNKNOWN", "cancelled during action; reconcile only, never repeat")
            raise
        except Exception as exc:
            self.store.transition(task_id, "UNKNOWN", f"uncertain action: {type(exc).__name__}; reconcile only")

    async def reconcile(self, task_id: str) -> None:
        if self.running:
            raise Conflict("agent busy")
        task = self.store.get(task_id)
        if task["state"] != "UNKNOWN":
            raise Conflict("only UNKNOWN tasks may be reconciled")
        async with asyncio.timeout(self.settings.task_timeout_s):
            receipt = await self.browser.reconcile(task_id, task["proposal"], self.store.lab_token(task_id))
            self._confirm(task_id, receipt)

    async def cancel(self, task_id: str) -> None:
        task = self.store.get(task_id)
        running = self.running.get(task_id)
        if running:
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)
            # Cancellation can arrive before the coroutine's first instruction.
            state = self.store.get(task_id)["state"]
            if state == "PREPARING":
                self.store.transition(task_id, "CANCELLED", "cancelled before drafting started")
            elif state == "ACTING":
                self.store.transition(task_id, "UNKNOWN", "cancelled before action acknowledgement; reconcile only")
        elif task["state"] in {"PREPARING", "AWAITING_APPROVAL"}:
            self.store.transition(task_id, "CANCELLED", "cancelled before any action")
        else:
            raise Conflict("task is terminal or requires receipt reconciliation")

    async def stop(self) -> None:
        self.stopped = True
        active = list(self.running.items())
        tasks = [task for _, task in active]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for task_id, _ in active:
            state = self.store.get(task_id)["state"]
            if state == "PREPARING":
                self.store.transition(task_id, "CANCELLED", "agent stopped before drafting started")
            elif state == "ACTING":
                self.store.transition(task_id, "UNKNOWN", "agent stopped during action; reconcile only")
        self.running.clear()
        await self.browser.stop()
