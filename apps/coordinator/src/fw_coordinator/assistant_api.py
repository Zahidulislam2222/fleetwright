"""`/v1/assistant`: the console help assistant over the existing principal and role checks.

The assistant's tools are read-only and run as the asker, inside the asker's tenant transaction, so
it can never show more than the console's own read endpoints already show that role. Audit and
user lists (personal data) are deliberately not exposed to it. Signed-in callers must send their
CSRF token like any other POST; anonymous visitors carry no session for a forged request to borrow."""

import hmac
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from fw_coordinator import schemas, views
from fw_coordinator.assistant import HISTORY_MAX_TURNS, TURN_MAX_CHARS, Assistant, Turn, clean
from fw_coordinator.auth import ip_prefix
from fw_core.db import tenant_tx
from fw_queue.sessions import Principal


class AskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=TURN_MAX_CHARS)
    history: list[Turn] = Field(default=[], max_length=HISTORY_MAX_TURNS)


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=8, max_length=40)
    helpful: bool


def _trim(page: dict[str, Any], limit: int) -> dict[str, Any]:
    items = page.get("items", [])
    return {"total": len(items), "items": items[:limit], "shown": min(len(items), limit)}


def install(
    app: FastAPI,
    services: Callable[..., Any],
    principal: Callable[..., Any],
    client_ip: Callable[[Request, int], str | None],
) -> None:
    Svc = Annotated[Any, Depends(services)]
    Who = Annotated[Principal, Depends(principal)]

    def assistant_of(svc: Any) -> Assistant:
        found: Assistant | None = getattr(svc, "assistant", None)
        if found is None:
            raise HTTPException(404, "the help assistant is not available on this deployment")
        return found

    def check_csrf(request: Request, svc: Any, who: Principal) -> None:
        if who.session is None:
            return  # anonymous visitors carry no session for a forged request to borrow
        sent = request.headers.get(svc.cfg.auth.csrf_header, "")
        if not who.csrf or not hmac.compare_digest(sent.encode(), who.csrf.encode()):
            raise HTTPException(403, "missing or wrong CSRF token")

    @app.get("/v1/assistant", response_model=schemas.AssistantInfo)
    async def describe(svc: Svc, who: Who) -> dict[str, Any]:
        assistant = assistant_of(svc)
        out = assistant.describe()
        # The counters are deployment-wide, so only the owner of the public workspace (the operator
        # of this deployment) sees them; owners of other tenants do not.
        if who.session is not None and who.role == "owner" and who.tenant_id == await svc.demo_tenant_id():
            out["today"] = await assistant.stats()  # counters only; no question text exists to show
        return out

    @app.post("/v1/assistant/ask", response_model=schemas.AssistantAnswer)
    async def ask(body: AskIn, request: Request, svc: Svc, who: Who) -> dict[str, Any]:
        assistant = assistant_of(svc)
        check_csrf(request, svc, who)
        limits = assistant.cfg
        if len(body.question.strip()) > limits.max_question_chars:
            raise HTTPException(422, f"questions are limited to {limits.max_question_chars} characters")
        if not clean(body.question, limits.max_question_chars):
            raise HTTPException(422, "ask a question")
        if who.session is not None and who.user_id is not None:
            subject = f"user:{who.user_id}"
        else:
            subject = f"ip:{ip_prefix(client_ip(request, svc.cfg.api.trusted_proxy_hops)) or 'unknown'}"
        demo_tenant = who.tenant_id == await svc.demo_tenant_id()

        async def run_tool(name: str, args: dict[str, Any]) -> Any:
            if name == "get_demo_status":
                return await svc.demo.status() if demo_tenant else {"demo": "this tenant has no demo"}
            async with tenant_tx(svc.engine, who.tenant_id) as conn:
                if name == "get_overview":
                    found = await views.overview(conn, who.tenant_id, svc.cfg.api)
                    found.pop("series", None)  # chart points: large and not useful in words
                    return found
                if name == "list_workers":
                    return _trim(await views.workers(conn, who.tenant_id, svc.cfg.api), limits.tool_list_limit)
                if name == "list_claims":
                    return await views.claims(conn, who.tenant_id, None, limits.tool_claims_limit, args.get("state"))
                if name == "get_latency":
                    return {
                        "window_s": svc.cfg.api.latency_window_s,
                        "stages": await views.latency(conn, who.tenant_id, svc.cfg.api.latency_window_s),
                    }
                if name == "list_filters":
                    return _trim(await views.filters(conn, who.tenant_id), limits.tool_list_limit)
                if name == "list_schedules":
                    return _trim(await views.schedules(conn, who.tenant_id), limits.tool_list_limit)
                if name == "list_accounts":
                    return _trim(await views.accounts(conn, who.tenant_id), limits.tool_list_limit)
            raise ValueError(f"unknown tool {name}")

        return await assistant.ask(subject, who.session is not None, body.question, body.history, run_tool)

    @app.post("/v1/assistant/feedback", response_model=schemas.FeedbackResult)
    async def feedback(body: FeedbackIn, request: Request, svc: Svc, who: Who) -> dict[str, bool]:
        check_csrf(request, svc, who)  # any viewer may vote on an answer they were given; ids are single-use
        return {"recorded": await assistant_of(svc).feedback(body.id, body.helpful)}
