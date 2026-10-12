"""Owned maintenance-request portal: a different workflow from booking published freight."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from mockboard import security
from mockboard.models import Adversity


class RequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: str = Field(min_length=1, max_length=80, pattern="^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=120)
    priority: Literal["normal", "urgent"]


def install(
    app: FastAPI,
    engine: AsyncEngine,
    templates: Jinja2Templates,
    session: Callable[..., Awaitable[Any]],
    rules: Callable[[], Awaitable[Adversity]],
) -> None:
    Session = Annotated[Any, Depends(session)]

    @app.get("/portal", response_class=HTMLResponse)
    async def page(request: Request, gate: Session) -> HTMLResponse:
        return templates.TemplateResponse(request, "portal.html", {"csrf": gate.csrf})

    @app.post("/api/portal/requests")
    async def create(body: RequestIn, gate: Session, x_csrf_token: str | None = Header(default=None)) -> JSONResponse:
        if x_csrf_token is None or not security.same(x_csrf_token, gate.csrf):
            raise HTTPException(403, "csrf token missing or wrong")
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text("""INSERT INTO portal_requests(account_id,reference,title,priority)
                        VALUES (:a,:r,:t,:p) ON CONFLICT (account_id,reference) DO NOTHING RETURNING reference"""),
                    {"a": gate.account_id, "r": body.reference, "t": body.title, "p": body.priority},
                )
            ).one_or_none()
        if row is None:
            return JSONResponse({"detail": "reference already used; reconcile before retry"}, status_code=409)
        if security.chance((await rules()).ack_loss_rate):
            return JSONResponse({"detail": "response lost after commit (simulated)"}, status_code=500)
        return JSONResponse({"status": "submitted", **body.model_dump()}, status_code=201)

    @app.get("/api/portal/requests")
    async def receipts(reference: str, gate: Session) -> dict[str, Any]:
        async with engine.connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text(
                            "SELECT reference,title,priority FROM portal_requests WHERE account_id=:a AND reference=:r"
                        ),
                        {"a": gate.account_id, "r": reference},
                    )
                )
                .mappings()
                .all()
            )
        return {"requests": [dict(row) for row in rows]}
