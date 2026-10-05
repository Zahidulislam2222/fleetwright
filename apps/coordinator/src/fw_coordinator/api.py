"""The console's `/v1` API.

Every request resolves a Principal: a signed-in user (session cookie) or, when public reading is
on, an anonymous viewer of the demo tenant. Roles are checked server-side on every endpoint;
every mutation also needs the session's CSRF token in a header and writes an audit row. Response
shapes follow the console's contract (apps/dashboard/src/mocks/types.ts)."""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID, uuid4

import httpx
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from fw_coordinator import schemas, views
from fw_coordinator.auth import Auth, BadCredentials, LockedOut, ip_prefix
from fw_coordinator.demo import Demo, DemoConfig, RunActive, load_demo
from fw_core.crypto import Envelope
from fw_core.db import make_engine, system_tx, tenant_tx
from fw_core.logs import setup_logging
from fw_core.settings import CoordinatorSettings, load
from fw_queue import client, keys, sessions
from fw_queue.sessions import Principal, Role

log = logging.getLogger(__name__)

CLAIM_STATES = ("QUEUED", "LEASED", "ACTING", "CONFIRMED", "FAILED", "UNKNOWN", "RECONCILED")


@dataclass
class Services:
    cfg: CoordinatorSettings
    engine: AsyncEngine
    redis: Redis
    auth: Auth
    demo: Demo
    demo_tenant: UUID | None = None

    async def demo_tenant_id(self) -> UUID | None:
        if self.demo_tenant is None:
            async with system_tx(self.engine) as conn:
                self.demo_tenant = (
                    await conn.execute(text("SELECT id FROM tenants WHERE slug = :s"), {"s": self.cfg.demo.tenant_slug})
                ).scalar_one_or_none()
        return self.demo_tenant


# ---------------- request bodies ----------------


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class MfaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=6, max_length=12)


class FilterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    origin: str = Field(default="Any", min_length=1, max_length=80)
    destination: str = Field(default="Any", min_length=1, max_length=80)
    min_rate_usd: int = Field(default=0, ge=0, le=1_000_000)
    equipment: list[Annotated[str, Field(min_length=1, max_length=40)]] = Field(default=[], max_length=20)
    max_weight_lb: int = Field(default=80000, gt=0, le=200_000)


class FilterPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None
    origin: str | None = Field(default=None, min_length=1, max_length=80)
    destination: str | None = Field(default=None, min_length=1, max_length=80)
    min_rate_usd: int | None = Field(default=None, ge=0, le=1_000_000)
    equipment: list[Annotated[str, Field(min_length=1, max_length=40)]] | None = Field(default=None, max_length=20)
    max_weight_lb: int | None = Field(default=None, gt=0, le=200_000)


class OtpIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=4, max_length=12, pattern=r"^[0-9A-Za-z]+$")


class AdversityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: dict[str, float | str] = Field(min_length=1, max_length=10)


# ---------------- dependencies ----------------


def services(request: Request) -> Services:
    return request.app.state.services  # type: ignore[no-any-return]


Svc = Annotated[Services, Depends(services)]


def client_ip(request: Request, hops: int) -> str | None:
    """The client address as seen by the outermost trusted proxy."""
    forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if hops and len(forwarded) >= hops:
        return forwarded[-hops]
    return request.client.host if request.client else None


async def principal(request: Request, svc: Svc) -> Principal:
    found = await sessions.load(svc.redis, request.cookies.get(svc.cfg.auth.cookie_name))
    if found is not None:
        return found
    if svc.cfg.demo.public_read and (tenant := await svc.demo_tenant_id()) is not None:
        return Principal(tenant, "public")
    raise HTTPException(401, "sign in required")


Who = Annotated[Principal, Depends(principal)]


async def csrf_checked(request: Request, svc: Svc, who: Who) -> Principal:
    """Mutations: a real session, and the session's CSRF token echoed in the header."""
    sent = request.headers.get(svc.cfg.auth.csrf_header, "")
    if who.session is None or not who.csrf or not _same(sent, who.csrf):
        raise HTTPException(403, "missing or wrong CSRF token")
    return who


def _same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


Mutator = Annotated[Principal, Depends(csrf_checked)]


def needs(who: Principal, role: Role) -> None:
    if who.role == "public" or not who.at_least(role):
        raise HTTPException(403, "not allowed for this role")


async def can_control_demo(svc: Services, who: Principal) -> None:
    if who.tenant_id != await svc.demo_tenant_id():
        raise HTTPException(403, "demo controls exist only on the demo tenant")
    if who.role not in ("demo", "operator", "owner"):
        raise HTTPException(403, "not allowed for this role")


async def audit(svc: Services, who: Principal, request: Request, action: str, target: str, detail: str) -> None:
    async with tenant_tx(svc.engine, who.tenant_id) as conn:
        await conn.execute(
            text(
                """INSERT INTO audit_log (tenant_id, actor, role, action, target, detail, ip_prefix)
                   VALUES (:t, :a, :r, :action, :target, :d, :ip)"""
            ),
            {
                "t": who.tenant_id,
                "a": who.email or "anonymous",
                "r": who.role,
                "action": action,
                "target": target,
                "d": detail,
                "ip": ip_prefix(client_ip(request, svc.cfg.api.trusted_proxy_hops)),
            },
        )


def _limit(svc: Services, limit: int | None) -> int:
    return min(limit or svc.cfg.api.page_size_default, svc.cfg.api.page_size_max)


# ---------------- application ----------------


def create_app(cfg: CoordinatorSettings | None = None, demo_data: DemoConfig | None = None) -> FastAPI:
    cfg = cfg or load(CoordinatorSettings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(cfg.app_db.dsn, cfg.app_db, "fw-api")
        redis = client.core(cfg.redis)
        http = httpx.AsyncClient(timeout=cfg.board_client.timeout_s)
        envelope = Envelope(cfg.vault.master_key_b64.get_secret_value(), cfg.vault.key_id)
        shared = frozenset({cfg.demo.account_email.lower()}) if cfg.demo.account_password else frozenset()
        svc = Services(
            cfg=cfg,
            engine=engine,
            redis=redis,
            auth=Auth(cfg.auth, redis, engine, envelope, shared_emails=shared),
            demo=Demo(cfg.demo, demo_data or load_demo(cfg.config_dir), cfg.board_client, redis, http),
        )
        app.state.services = svc
        stopping = asyncio.Event()
        reset = asyncio.create_task(svc.demo.reset_loop(cfg.demo.reset_check_s, stopping), name="demo-reset")
        try:
            yield
        finally:
            stopping.set()
            with contextlib.suppress(asyncio.CancelledError):
                await reset
            await http.aclose()
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(title="Fleetwright API", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.exception_handler(LockedOut)
    async def _locked(_: Request, exc: LockedOut) -> JSONResponse:
        return JSONResponse(
            {"detail": "too many attempts; try again later"},
            status_code=429,
            headers={"Retry-After": str(exc.retry_after_s)},
        )

    @app.exception_handler(BadCredentials)
    async def _bad(_: Request, __: BadCredentials) -> JSONResponse:
        return JSONResponse({"detail": "wrong email, password or code"}, status_code=401)

    @app.get("/healthz", include_in_schema=False)
    async def healthz(svc: Svc) -> dict[str, str]:
        async with system_tx(svc.engine) as conn:
            await conn.execute(text("SELECT 1"))
        await svc.redis.ping()
        return {"status": "ok"}

    # ---------------- session and sign-in ----------------

    @app.get("/v1/session", response_model=schemas.Session)
    async def session_info(svc: Svc, who: Who) -> dict[str, Any]:
        async with system_tx(svc.engine) as conn:
            tenant = (
                await conn.execute(text("SELECT id, slug, name FROM tenants WHERE id = :t"), {"t": who.tenant_id})
            ).one()
        demo_tenant = who.tenant_id == await svc.demo_tenant_id()
        return {
            "authenticated": who.session is not None,
            "role": who.role,
            "name": who.name,
            "email": views.mask_email(who.email) if who.redacted else who.email,
            "redacted": who.redacted,
            "csrf": who.csrf,
            "csrf_header": svc.cfg.auth.csrf_header,
            "tenant": {"id": str(tenant.id), "slug": tenant.slug, "name": tenant.name},
            "demo": {"tenant": demo_tenant, "can_control": demo_tenant and who.role in ("demo", "operator", "owner")},
        }

    @app.post("/v1/auth/login", response_model=schemas.LoginResult)
    async def login(body: LoginIn, request: Request, response: Response, svc: Svc) -> dict[str, bool]:
        token = await svc.auth.password_step(
            body.email, body.password, client_ip(request, svc.cfg.api.trusted_proxy_hops)
        )
        response.set_cookie(
            svc.cfg.auth.mfa_cookie_name,
            token,
            max_age=svc.cfg.auth.mfa_pending_ttl_s,
            httponly=True,
            secure=svc.cfg.auth.cookie_secure,
            samesite="strict",
            path="/v1/auth",
        )
        return {"mfa_required": True}

    @app.post("/v1/auth/mfa", response_model=schemas.MfaResult)
    async def mfa(body: MfaIn, request: Request, response: Response, svc: Svc) -> dict[str, Any]:
        token, who = await svc.auth.mfa_step(
            request.cookies.get(svc.cfg.auth.mfa_cookie_name),
            body.code,
            client_ip(request, svc.cfg.api.trusted_proxy_hops),
        )
        response.delete_cookie(svc.cfg.auth.mfa_cookie_name, path="/v1/auth")
        response.set_cookie(
            svc.cfg.auth.cookie_name,
            token,
            max_age=svc.cfg.auth.session_ttl_s,
            httponly=True,
            secure=svc.cfg.auth.cookie_secure,
            samesite="strict",
            path="/",
        )
        return {"role": who.role, "csrf": who.csrf}

    @app.post("/v1/auth/logout", response_model=schemas.SignedOut)
    async def logout(response: Response, svc: Svc, who: Mutator) -> dict[str, bool]:
        await sessions.revoke(svc.redis, who)
        response.delete_cookie(svc.cfg.auth.cookie_name, path="/")
        return {"signed_out": True}

    @app.get("/v1/auth/demo-hint", response_model=schemas.DemoHint)
    async def demo_hint(svc: Svc) -> dict[str, Any]:
        """The shared demo login, shown on the public login page by design (demo role only)."""
        password = svc.cfg.demo.account_password
        if not svc.cfg.demo.show_demo_mfa_code or password is None:
            raise HTTPException(404, "no public demo login")
        code = await svc.auth.current_code(svc.cfg.demo.account_email)
        if code is None:
            raise HTTPException(404, "no public demo login")
        return {"email": svc.cfg.demo.account_email, "password": password.get_secret_value(), "code": code}

    # ---------------- reads ----------------

    @app.get("/v1/overview", response_model=schemas.Overview)
    async def overview(svc: Svc, who: Who) -> dict[str, Any]:
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            return await views.overview(conn, who.tenant_id, svc.cfg.api)

    @app.get("/v1/workers", response_model=schemas.WorkerPage)
    async def workers(svc: Svc, who: Who) -> dict[str, Any]:
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            return await views.workers(conn, who.tenant_id, svc.cfg.api)

    @app.get("/v1/accounts", response_model=schemas.AccountPage)
    async def accounts(svc: Svc, who: Who) -> dict[str, Any]:
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            return await views.accounts(conn, who.tenant_id)

    @app.get("/v1/claims", response_model=schemas.ClaimPage)
    async def claims_page(
        svc: Svc,
        who: Who,
        cursor: Annotated[str | None, Query(max_length=200)] = None,
        limit: Annotated[int | None, Query(ge=1)] = None,
        state: Annotated[str | None, Query(pattern="^(" + "|".join(CLAIM_STATES) + ")$")] = None,
    ) -> dict[str, Any]:
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            return await views.claims(conn, who.tenant_id, cursor, _limit(svc, limit), state)

    @app.get("/v1/claims/{claim_id}", response_model=schemas.Claim)
    async def claim_detail(claim_id: UUID, svc: Svc, who: Who) -> dict[str, Any]:
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            found = await views.claim(conn, who.tenant_id, claim_id)
        if found is None:
            raise HTTPException(404, "no such claim")
        return found

    @app.get("/v1/filters", response_model=schemas.FilterPage)
    async def filters_list(svc: Svc, who: Who) -> dict[str, Any]:
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            return await views.filters(conn, who.tenant_id)

    @app.get("/v1/schedules", response_model=schemas.SchedulePage)
    async def schedules(svc: Svc, who: Who) -> dict[str, Any]:
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            return await views.schedules(conn, who.tenant_id)

    @app.get("/v1/latency", response_model=schemas.Latency)
    async def latency(svc: Svc, who: Who) -> dict[str, Any]:
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            stages = await views.latency(conn, who.tenant_id, svc.cfg.api.latency_window_s)
        return {"tenant_id": str(who.tenant_id), "window_s": svc.cfg.api.latency_window_s, "stages": stages}

    @app.get("/v1/audit", response_model=schemas.AuditPage)
    async def audit_page(
        svc: Svc,
        who: Who,
        cursor: Annotated[str | None, Query(max_length=200)] = None,
        limit: Annotated[int | None, Query(ge=1)] = None,
    ) -> dict[str, Any]:
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            return await views.audit(conn, who.tenant_id, cursor, _limit(svc, limit), who.redacted)

    @app.get("/v1/users", response_model=schemas.UserPage)
    async def users(svc: Svc, who: Who) -> dict[str, Any]:
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            return await views.users(conn, who.tenant_id, who.redacted)

    @app.get("/v1/cells", response_model=schemas.CellList)
    async def cells(svc: Svc, who: Who) -> dict[str, Any]:
        async with system_tx(svc.engine) as conn:
            directory = await views.cells(conn)
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            mine = await views.workers_per_cell(conn, who.tenant_id, svc.cfg.api)
        own = str(who.tenant_id)
        # Other tenants are counted, never named; worker counts are the viewer's own (RLS).
        return {
            "items": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "region": c["region"],
                    "capacity": c["capacity"],
                    "tenant_count": len(c["tenants"]),
                    "hosts_you": own in c["tenants"],
                    "your_workers": mine.get(c["id"], 0),
                }
                for c in directory
            ]
        }

    # ---------------- filters ----------------

    @app.post("/v1/filters", status_code=201, response_model=schemas.Filter)
    async def filter_create(body: FilterIn, request: Request, svc: Svc, who: Mutator) -> dict[str, Any]:
        needs(who, "operator")
        filter_id = uuid4()
        try:
            async with tenant_tx(svc.engine, who.tenant_id) as conn:
                await conn.execute(
                    text(
                        """INSERT INTO filters (tenant_id, id, name, enabled, origin, destination, min_rate_usd,
                                                equipment, max_weight_lb)
                           VALUES (:t, :i, :name, :enabled, :origin, :dest, :rate, CAST(:equipment AS text[]), :weight)"""
                    ),
                    {
                        "t": who.tenant_id,
                        "i": filter_id,
                        "name": body.name,
                        "enabled": body.enabled,
                        "origin": body.origin,
                        "dest": body.destination,
                        "rate": body.min_rate_usd,
                        "equipment": body.equipment,
                        "weight": body.max_weight_lb,
                    },
                )
        except IntegrityError as exc:
            raise HTTPException(409, "a filter with this name exists") from exc
        await _filters_changed(svc, who, request, "filter.create", body.name, json.dumps(body.model_dump()))
        return await _one_filter(svc, who, filter_id)

    @app.patch("/v1/filters/{filter_id}", response_model=schemas.Filter)
    async def filter_update(
        filter_id: UUID, body: FilterPatch, request: Request, svc: Svc, who: Mutator
    ) -> dict[str, Any]:
        needs(who, "operator")
        changes = body.model_dump(exclude_none=True)
        if not changes:
            raise HTTPException(422, "nothing to change")
        try:
            async with tenant_tx(svc.engine, who.tenant_id) as conn:
                row = (
                    await conn.execute(
                        text(
                            """UPDATE filters SET
                                 name = coalesce(:name, name),
                                 enabled = coalesce(:enabled, enabled),
                                 origin = coalesce(:origin, origin),
                                 destination = coalesce(:dest, destination),
                                 min_rate_usd = coalesce(:rate, min_rate_usd),
                                 equipment = coalesce(CAST(:equipment AS text[]), equipment),
                                 max_weight_lb = coalesce(:weight, max_weight_lb),
                                 version = version + 1, updated_at = clock_timestamp()
                               WHERE tenant_id = :t AND id = :i RETURNING name"""
                        ),
                        {
                            "t": who.tenant_id,
                            "i": filter_id,
                            "name": body.name,
                            "enabled": body.enabled,
                            "origin": body.origin,
                            "dest": body.destination,
                            "rate": body.min_rate_usd,
                            "equipment": body.equipment,
                            "weight": body.max_weight_lb,
                        },
                    )
                ).one_or_none()
        except IntegrityError as exc:
            raise HTTPException(409, "a filter with this name exists") from exc
        if row is None:
            raise HTTPException(404, "no such filter")
        await _filters_changed(svc, who, request, "filter.update", row.name, json.dumps(changes))
        return await _one_filter(svc, who, filter_id)

    async def _filters_changed(
        svc: Services, who: Principal, request: Request, action: str, target: str, detail: str
    ) -> None:
        await audit(svc, who, request, action, target, detail)
        try:
            await svc.redis.publish(keys.filters_channel(who.tenant_id), "changed")
        except OSError:
            log.warning("filter reload publish failed; dispatchers reload on their timer")

    async def _one_filter(svc: Services, who: Principal, filter_id: UUID) -> dict[str, Any]:
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            listed = await views.filters(conn, who.tenant_id)
        return next(f for f in listed["items"] if f["id"] == str(filter_id))

    # ---------------- accounts ----------------

    @app.post("/v1/accounts/{account_id}/otp", status_code=202, response_model=schemas.Accepted)
    async def manual_otp(account_id: UUID, body: OtpIn, request: Request, svc: Svc, who: Mutator) -> dict[str, bool]:
        """An operator types the one-time code the target sent; the waiting worker picks it up."""
        needs(who, "operator")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            label = (
                await conn.execute(
                    text("SELECT label FROM accounts WHERE tenant_id = :t AND id = :a"),
                    {"t": who.tenant_id, "a": account_id},
                )
            ).scalar_one_or_none()
        if label is None:
            raise HTTPException(404, "no such account")
        key = keys.manual_otp(who.tenant_id, account_id)
        async with svc.redis.pipeline(transaction=True) as pipe:
            pipe.rpush(key, body.code)
            pipe.expire(key, svc.cfg.auth.mfa_pending_ttl_s)
            await pipe.execute()
        await audit(svc, who, request, "account.otp_entered", label, "one-time code entered (value not stored)")
        return {"accepted": True}

    # ---------------- demo ----------------

    @app.get("/v1/demo", response_model=schemas.DemoStatus)
    async def demo_status(svc: Svc, who: Who) -> dict[str, Any]:
        if who.tenant_id != await svc.demo_tenant_id():
            raise HTTPException(404, "this tenant has no demo")
        return await svc.demo.status()

    @app.post("/v1/demo/run", response_model=schemas.DemoStatus)
    async def demo_run(request: Request, svc: Svc, who: Mutator) -> dict[str, Any]:
        await can_control_demo(svc, who)
        try:
            status = await svc.demo.start_run()
        except RunActive:
            raise HTTPException(409, "a demo run is already going; wait for it to end") from None
        await audit(svc, who, request, "demo.run", "board", f"feed at {status['feed_rate_per_min']}/min")
        return status

    @app.patch("/v1/demo/adversity", response_model=schemas.DemoStatus)
    async def demo_adversity(body: AdversityIn, request: Request, svc: Svc, who: Mutator) -> dict[str, Any]:
        await can_control_demo(svc, who)
        try:
            status = await svc.demo.change_adversity(dict(body.changes))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        await audit(svc, who, request, "demo.adversity", "board", json.dumps(body.changes))
        return status

    return app


def main() -> None:
    cfg = load(CoordinatorSettings)
    setup_logging("api", cfg.log_level)
    uvicorn.run(create_app(cfg), host=cfg.api.host, port=cfg.api.port, proxy_headers=False, log_config=None)


if __name__ == "__main__":
    main()
