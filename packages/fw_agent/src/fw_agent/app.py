"""Loopback UI/API. No unauthenticated cross-origin API or unbound action endpoints."""

from __future__ import annotations

import ipaddress
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlunsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import Field
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from fw_agent.contracts import CSRF_HEADER, SESSION_COOKIE, Draft, StrictModel, load_data
from fw_agent.runner import Runner
from fw_agent.store import Conflict, Store
from fw_core.settings import AgentAppSettings


class StartRequest(StrictModel):
    template_id: str = Field(max_length=41)
    origin: str = Field(max_length=2048)
    request: str = Field(min_length=1, max_length=20000)


class ApprovalRequest(StrictModel):
    hash: str = Field(pattern="^[0-9a-f]{64}$")


class EditRequest(ApprovalRequest):
    draft: Draft


class LabRequest(StrictModel):
    task_id: str = Field(pattern="^[0-9a-f]{32}$")
    hash: str = Field(pattern="^[0-9a-f]{64}$")
    token: str = Field(max_length=200)
    title: str = Field(max_length=200)
    body: str = Field(max_length=8000)


class LoopbackBoundary:
    def __init__(self, app: ASGIApp, authority: str, limit: int) -> None:
        self.app, self.authority, self.limit = app, authority, limit
        self.local_origin = urlunsplit(("http", authority, "", "", ""))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        client = scope.get("client")
        try:
            local = client is not None and ipaddress.ip_address(client[0]).is_loopback
        except ValueError:
            local = False
        # Host comes from explicit settings, never from an attacker-supplied request base URL.
        initial_navigation = (
            scope["path"] == "/"
            and scope["method"] == "GET"
            and headers.get("sec-fetch-mode") == "navigate"
            and headers.get("sec-fetch-dest") == "document"
        )
        if (
            not local
            or headers.get("host") != self.authority
            or headers.get("origin", self.local_origin) != self.local_origin
            or (headers.get("sec-fetch-site") == "cross-site" and not initial_navigation)
        ):
            await JSONResponse({"detail": "loopback same-origin boundary refused request"}, status_code=403)(
                scope, receive, send
            )
            return
        chunks = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunks.extend(message.get("body", b""))
            if len(chunks) > self.limit:
                await JSONResponse({"detail": "request budget exceeded"}, status_code=413)(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        consumed = False

        async def bounded_receive() -> Message:
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(chunks), "more_body": False}
            return await receive()

        async def security_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend(
                    [
                        (
                            b"content-security-policy",
                            b"default-src 'self'; script-src 'self'; style-src 'self'; "
                            b"connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
                        ),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"cache-control", b"no-store"),
                    ]
                )
            await send(message)

        await self.app(scope, bounded_receive, security_send)


def create_app(settings: AgentAppSettings) -> FastAPI:
    config = settings.agent
    host = config.host
    if not ipaddress.ip_address(host).is_loopback:
        raise ValueError("local agent API must bind to loopback")
    authority = f"[{host}]:{config.port}" if ":" in host else f"{host}:{config.port}"
    local_origin = urlunsplit(("http", authority, "", "", ""))
    data = load_data(settings.config_dir)
    store = Store(config.database)
    runner = Runner(config, data, store)
    session, csrf = secrets.token_urlsafe(), secrets.token_urlsafe()
    assets = Path(__file__).parent / "assets"

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await runner.stop()
        store.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.runner, app.state.store = runner, store
    app.add_middleware(LoopbackBoundary, authority=authority, limit=config.max_request_bytes)

    @app.exception_handler(Conflict)
    async def conflict(_: Request, exc: Conflict) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing(_: Request, __: KeyError) -> JSONResponse:
        return JSONResponse({"detail": "task not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=400)

    def require_session(request: Request, *, mutation: bool = False) -> None:
        if not secrets.compare_digest(request.cookies.get(SESSION_COOKIE, ""), session):
            raise HTTPException(401, "open the local agent UI first")
        if mutation and (
            request.headers.get("origin") != local_origin
            or not secrets.compare_digest(request.headers.get(CSRF_HEADER, ""), csrf)
        ):
            raise HTTPException(403, "same-origin CSRF token required")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        response = HTMLResponse((assets / "index.html").read_text(encoding="utf-8"))
        response.set_cookie(SESSION_COOKIE, session, httponly=True, samesite="strict", secure=False)
        return response

    @app.get("/assets/{name}")
    async def asset(name: str) -> FileResponse:
        if name not in {"agent.js", "agent.css", "lab.js"}:
            raise HTTPException(404)
        return FileResponse(assets / name)

    @app.get("/api/bootstrap")
    async def bootstrap(request: Request) -> dict[str, Any]:
        require_session(request)
        return {
            "data": data.model_dump(),
            "origins": config.allowed_origins,
            "csrf": csrf,
            "model": config.model_id,
            "stopped": runner.stopped,
            "max_content_chars": config.max_content_chars,
        }

    @app.get("/api/tasks")
    async def tasks(request: Request) -> list[dict[str, Any]]:
        require_session(request)
        return store.list(config.history_limit)

    @app.get("/api/tasks/{task_id}")
    async def task_detail(task_id: str, request: Request) -> dict[str, Any]:
        require_session(request)
        return store.get(task_id)

    @app.get("/api/tasks/{task_id}/evidence")
    async def evidence(task_id: str, request: Request) -> Response:
        require_session(request)
        task = store.get(task_id)
        if task["state"] != "CONFIRMED":
            raise HTTPException(409, "only confirmed tasks have final evidence")
        file = config.evidence_directory / f"{task_id}.json"
        if not file.is_file():
            raise HTTPException(404, "evidence not available")
        return FileResponse(file, media_type="application/json", filename=f"agent-{task_id}.json")

    @app.post("/api/tasks", status_code=202)
    async def start(body: StartRequest, request: Request) -> dict[str, str]:
        require_session(request, mutation=True)
        return {"task_id": runner.start(body.template_id, body.origin, body.request)}

    @app.post("/api/tasks/{task_id}/approve", status_code=202)
    async def approve(task_id: str, body: ApprovalRequest, request: Request) -> dict[str, str]:
        require_session(request, mutation=True)
        runner.approve(task_id, body.hash)
        return {"state": "ACTING"}

    @app.post("/api/tasks/{task_id}/edit")
    async def edit(task_id: str, body: EditRequest, request: Request) -> dict[str, str]:
        require_session(request, mutation=True)
        runner.edit(task_id, body.hash, body.draft)
        return {"state": "SUPERSEDED"}

    @app.post("/api/tasks/{task_id}/cancel")
    async def cancel(task_id: str, request: Request) -> dict[str, Any]:
        require_session(request, mutation=True)
        await runner.cancel(task_id)
        return store.get(task_id)

    @app.post("/api/tasks/{task_id}/reconcile")
    async def reconcile(task_id: str, request: Request) -> dict[str, Any]:
        require_session(request, mutation=True)
        await runner.reconcile(task_id)
        return store.get(task_id)

    @app.post("/api/stop")
    async def stop(request: Request) -> dict[str, bool]:
        require_session(request, mutation=True)
        await runner.stop()
        return {"stopped": True}

    def lab_template(template_id: str) -> None:
        if not config.lab_enabled:
            raise HTTPException(404)
        data.template(template_id)

    def lab_access(template_id: str, task_id: str, token: str) -> None:
        lab_template(template_id)
        task = store.get(task_id)
        if task["proposal"]["template"]["id"] != template_id or not secrets.compare_digest(
            store.lab_token(task_id), token
        ):
            raise HTTPException(403, "invalid owned-destination capability")

    @app.get("/lab/{template_id}/source", response_class=HTMLResponse)
    async def lab_source(template_id: str) -> str:
        lab_template(template_id)
        template = data.template(template_id)
        return (
            f"<!doctype html><html><head><title>{escape(template.name)}</title></head>"
            f"<body><h1>{escape(template.name)}</h1><article id='source'>{escape(template.lab_source)}</article></body></html>"
        )

    @app.get("/lab/{template_id}/form", response_class=HTMLResponse)
    async def lab_form(template_id: str, task_id: str = "", token: str = "") -> str:
        lab_template(template_id)
        if task_id:
            lab_access(template_id, task_id, token)
        return (
            (assets / "lab-form.html")
            .read_text(encoding="utf-8")
            .replace("{template_id}", escape(template_id))
            .replace("{token}", escape(token))
        )

    @app.post("/lab/{template_id}/accept")
    async def lab_accept(template_id: str, body: LabRequest, request: Request) -> dict[str, Any]:
        lab_access(template_id, body.task_id, body.token)
        if request.headers.get("origin") != local_origin:
            raise HTTPException(403, "owned destination requires same origin")
        return store.accept_lab(body.task_id, body.hash, body.token, body.title, body.body)

    @app.get("/lab/{template_id}/receipt")
    async def lab_receipt(template_id: str, task_id: str, token: str) -> dict[str, Any]:
        lab_access(template_id, task_id, token)
        receipt = store.receipt(task_id)
        if receipt is None:
            raise HTTPException(404, "no receipt; never infer that the action is safe to retry")
        return receipt

    return app
