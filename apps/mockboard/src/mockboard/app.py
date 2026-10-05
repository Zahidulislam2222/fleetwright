"""Demo Freight Exchange: a fictitious load board that Fleetwright's fleet is tested against.

Pages: /login -> emailed code (/otp) -> /loads (polls the JSON API like a real board) and /watch
(public, read-only ground truth). JSON: /api/loads, /api/loads/{ref}/book, /api/bookings, /api/me.
Admin API (bearer token): adversity toggles, accounts, forced session expiry, ground truth.
"""

# No `from __future__ import annotations` here: FastAPI must resolve dependency types declared
# inside create_app(), which postponed (string) annotations would hide from it.
import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from importlib import resources
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from fw_core.data import load_yaml
from fw_core.db import make_engine
from fw_core.logs import setup_logging
from fw_core.settings import BoardAppSettings, load
from fw_core.timeutil import iso
from mockboard import security, store
from mockboard.feed import Feed
from mockboard.mail import send_otp
from mockboard.models import Adversity, Catalogue

log = logging.getLogger("mockboard")

SESSION_COOKIE = "mb_session"
CHALLENGE_COOKIE = "mb_challenge"
OTP_MAX_ATTEMPTS = 5
BOOKINGS_LIMIT = 200
PUBLIC_RECENT_LIMIT = 60
GROUND_TRUTH_MAX = 5000
SETTINGS_CACHE_S = 1.0
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
}


class LoadOut(BaseModel):
    ref: str
    origin: str
    destination: str
    equipment: str
    weight_lb: int
    miles: int
    rate_usd: int
    pickup_at: str
    published_at: str
    status: str  # open | booked
    booked_at: str | None
    booked_by: str | None = None  # only on the public watch feed and the admin ground truth


def load_out(row: Any, public: bool = False) -> LoadOut:
    booked = row.booked_at is not None
    who = row.booked_by_username or row.booked_by_competitor
    return LoadOut(
        ref=row.ref,
        origin=row.origin,
        destination=row.destination,
        equipment=row.equipment,
        weight_lb=row.weight_lb,
        miles=row.miles,
        rate_usd=row.rate_usd,
        pickup_at=iso(row.pickup_at) or "",
        published_at=iso(row.published_at) or "",
        status="booked" if booked else "open",
        booked_at=iso(row.booked_at),
        booked_by=who if public else None,
    )


class AccountIn(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,40}$")
    password: str = Field(min_length=12, max_length=200)


class ExpireIn(BaseModel):
    username: str | None = None


def create_app(settings: BoardAppSettings | None = None) -> FastAPI:
    cfg = settings or load(BoardAppSettings)
    setup_logging("mockboard", cfg.log_level)
    catalogue = load_yaml(cfg.config_dir, "board_catalogue.yaml", Catalogue)
    engine: AsyncEngine = make_engine(cfg.board_db.dsn, cfg.board_db, "mockboard")
    board = cfg.board
    package = resources.files("mockboard")
    templates = Jinja2Templates(directory=str(package.joinpath("templates")))
    templates.env.globals.update(branding=catalogue.branding)
    feed = Feed(engine, catalogue)
    cache: dict[str, Any] = {"at": 0.0, "value": None}

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await store.apply_schema(engine)
        await store.ensure_settings(engine, Adversity(feed_rate_per_min=board.feed_rate_per_min))
        task = asyncio.create_task(feed.run())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            await engine.dispose()

    app = FastAPI(
        title="Demo Freight Exchange (mock)", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.mount("/static", StaticFiles(directory=str(package.joinpath("static"))), name="static")
    app.state.engine = engine
    app.state.feed = feed

    @app.middleware("http")
    async def headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response

    async def adversity() -> Adversity:
        loop = asyncio.get_running_loop()
        if cache["value"] is None or loop.time() - cache["at"] > SETTINGS_CACHE_S:
            async with engine.connect() as conn:
                cache["value"] = await store.get_settings(conn)
            cache["at"] = loop.time()
        return cache["value"]  # type: ignore[no-any-return]

    def set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
        response.set_cookie(
            name, value, max_age=max_age, httponly=True, secure=board.cookie_secure, samesite="lax", path="/"
        )

    def _new_question() -> str:
        lo, hi = int(catalogue.captcha.operands.lo), int(catalogue.captcha.operands.hi)
        return f"{security.randint(lo, hi)}+{security.randint(lo, hi)}"

    # ---------------- admin ----------------

    def require_admin(authorization: Annotated[str | None, Header()] = None) -> None:
        expected = "Bearer " + board.admin_token.get_secret_value()
        if authorization is None or not security.same(authorization, expected):
            raise HTTPException(status_code=401, detail="admin token required")

    admin = [Depends(require_admin)]

    @app.get("/admin/settings", dependencies=admin)
    async def admin_get_settings() -> Adversity:
        async with engine.connect() as conn:
            return await store.get_settings(conn)

    @app.patch("/admin/settings", dependencies=admin)
    async def admin_patch_settings(patch: dict[str, Any]) -> Adversity:
        unknown = sorted(set(patch) - set(Adversity.model_fields))
        if unknown:
            raise HTTPException(status_code=422, detail=f"unknown settings: {unknown}")
        async with engine.connect() as conn:
            current = await store.get_settings(conn)
        try:
            merged = Adversity.model_validate({**current.model_dump(), **patch})
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_context=False)) from exc
        cache["value"] = None
        return await store.put_settings(engine, merged, "admin-api")

    @app.post("/admin/accounts", dependencies=admin)
    async def admin_account(body: AccountIn) -> dict[str, Any]:
        account_id = await store.upsert_account(
            engine, body.username, f"{body.username}@{board.email_domain}", security.hash_password(body.password)
        )
        return {"id": account_id, "username": body.username, "email": f"{body.username}@{board.email_domain}"}

    @app.post("/admin/sessions/expire", dependencies=admin)
    async def admin_expire(body: ExpireIn) -> dict[str, int]:
        return {"revoked": await store.expire_sessions(engine, body.username)}

    @app.get("/admin/ground-truth", dependencies=admin)
    async def admin_ground_truth(
        since: datetime, limit: Annotated[int, Query(ge=1, le=GROUND_TRUTH_MAX)] = 1000
    ) -> dict[str, Any]:
        async with engine.connect() as conn:
            rows = await store.ground_truth(conn, since, limit)
        return {"loads": [{**load_out(r, public=True).model_dump(), "attempts": r.attempts} for r in rows]}

    @app.get("/admin/audit/duplicates", dependencies=admin)
    async def admin_duplicates(since: datetime) -> dict[str, Any]:
        async with engine.connect() as conn:
            return await store.duplicate_audit(conn, since)

    @app.post("/admin/reset", dependencies=admin)
    async def admin_reset() -> dict[str, str]:
        if cfg.environment not in {"local", "test"}:
            raise HTTPException(status_code=403, detail="reset is only allowed in local and test environments")
        await store.reset_data(engine)
        return {"status": "reset"}

    # ---------------- health ----------------

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        async with engine.connect() as conn:
            now = await store.db_now(conn)
        return {"ok": True, "db_time": iso(now), "feed_leader": feed.is_leader}

    # ---------------- login ----------------

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> Response:
        return RedirectResponse("/loads" if request.cookies.get(SESSION_COOKIE) else "/login", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request, error: str | None = None) -> Response:
        return templates.TemplateResponse(request, "login.html", {"error": error})

    @app.post("/login")
    async def login(
        username: Annotated[str, Form(max_length=64)], password: Annotated[str, Form(max_length=200)]
    ) -> Response:
        async with engine.connect() as conn:
            account = await store.find_account(conn, username.strip().lower())
        if not security.verify_password(account.password_hash if account else None, password):
            return RedirectResponse("/login?error=credentials", status_code=303)
        challenge = security.new_token()
        code = security.new_otp(board.otp_length)
        async with engine.begin() as conn:
            await store.create_challenge(
                conn, security.token_hash(challenge), account.id, security.otp_hash(challenge, code), board.otp_ttl_s
            )
        await send_otp(board, account.email, code, catalogue.branding.name)
        response = RedirectResponse("/otp", status_code=303)
        set_cookie(response, CHALLENGE_COOKIE, challenge, board.otp_ttl_s)
        return response

    @app.get("/otp", response_class=HTMLResponse)
    async def otp_page(request: Request, error: str | None = None) -> Response:
        if not request.cookies.get(CHALLENGE_COOKIE):
            return RedirectResponse("/login", status_code=303)
        return templates.TemplateResponse(request, "otp.html", {"error": error})

    @app.post("/otp")
    async def otp(request: Request, code: Annotated[str, Form(max_length=12)]) -> Response:
        challenge = request.cookies.get(CHALLENGE_COOKIE)
        if not challenge:
            return RedirectResponse("/login", status_code=303)
        async with engine.begin() as conn:
            row = await store.take_challenge_attempt(conn, security.token_hash(challenge))
            if row is None or row.attempts > OTP_MAX_ATTEMPTS:
                if row is not None:
                    await store.drop_challenge(conn, security.token_hash(challenge))
                return RedirectResponse("/login?error=expired", status_code=303)
            if not security.same(row.otp_hash, security.otp_hash(challenge, code.strip())):
                return RedirectResponse("/otp?error=code", status_code=303)
            await store.drop_challenge(conn, security.token_hash(challenge))
            token = security.new_token()
            await store.create_session(
                conn,
                token_hash=security.token_hash(token),
                account_id=row.account_id,
                csrf=security.new_token(),
                ttl_s=board.session_ttl_s,
                single=(await adversity()).single_session,
            )
        response = RedirectResponse("/loads", status_code=303)
        response.delete_cookie(CHALLENGE_COOKIE, path="/")
        set_cookie(response, SESSION_COOKIE, token, board.session_ttl_s)
        return response

    @app.post("/logout")
    async def logout(request: Request) -> Response:
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            async with engine.begin() as conn:
                await store.revoke_session(conn, security.token_hash(token))
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    # ---------------- session gate for the JSON API ----------------

    class Gate(BaseModel):
        account_id: int
        username: str
        csrf: str
        expires_at: str
        token_hash: str

    async def api_session(request: Request) -> Gate:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            raise HTTPException(status_code=401, detail="login required")
        th = security.token_hash(token)
        rules = await adversity()
        captcha = False
        async with engine.begin() as conn:
            hit = await store.touch_session(conn, th, rules.captcha_window_s)
            if hit is not None and hit.captcha_question is not None:
                captcha = True
            elif hit is not None and rules.captcha_enabled and hit.window_count > rules.captcha_after_requests:
                # Set inside the transaction, raise after it commits (raising here would roll it back).
                await store.set_captcha(conn, th, _new_question())
                captcha = True
        if hit is None:
            raise HTTPException(status_code=401, detail="session expired")
        if captcha:
            raise HTTPException(status_code=403, detail={"captcha_required": True, "challenge_url": "/captcha"})
        if rules.rate_limit_per_min and hit.minute_count > rules.rate_limit_per_min:
            raise HTTPException(status_code=429, detail="rate limited", headers={"Retry-After": "60"})
        if security.chance(rules.slow_rate) and rules.slow_ms:
            await asyncio.sleep(rules.slow_ms / 1000)
        if security.chance(rules.error_rate):
            raise HTTPException(status_code=503, detail="upstream error (simulated)")
        return Gate(
            account_id=hit.account_id,
            username=hit.username,
            csrf=hit.csrf,
            expires_at=iso(hit.expires_at) or "",
            token_hash=th,
        )

    SessionDep = Annotated[Gate, Depends(api_session)]

    @app.get("/api/me")
    async def me(gate: SessionDep) -> dict[str, Any]:
        return {"username": gate.username, "session_expires_at": gate.expires_at, "csrf": gate.csrf}

    @app.get("/api/loads")
    async def api_loads(
        gate: SessionDep,
        after: Annotated[int | None, Query(ge=0)] = None,
        limit: Annotated[int | None, Query(ge=1)] = None,
    ) -> dict[str, Any]:
        n = min(limit or board.feed_page_limit, board.feed_page_limit)
        async with engine.connect() as conn:
            rows = await store.list_loads(conn, after, board.load_visible_s, n)
            now = await store.db_now(conn)
        cursor = rows[-1].id if rows else after
        return {"loads": [load_out(r) for r in rows], "cursor": cursor, "server_time": iso(now)}

    @app.post("/api/loads/{ref}/book")
    async def api_book(
        ref: str, gate: SessionDep, x_csrf_token: Annotated[str | None, Header()] = None
    ) -> JSONResponse:
        if x_csrf_token is None or not security.same(x_csrf_token, gate.csrf):
            raise HTTPException(status_code=403, detail="csrf token missing or wrong")
        rules = await adversity()
        ack_lost = security.chance(rules.ack_loss_rate)
        async with engine.begin() as conn:
            result = await store.book(conn, ref, gate.account_id, ack_lost)
        if result.outcome == "not_found":
            raise HTTPException(status_code=404, detail="no such load")
        if result.outcome == "already_booked":
            if result.booked_by_self:
                log.warning(
                    "duplicate booking attempt by the same account", extra={"ref": ref, "account": gate.username}
                )
            return JSONResponse(
                {"status": "already_booked", "ref": ref, "by_you": result.booked_by_self}, status_code=409
            )
        if ack_lost:
            # The booking stands; only the answer is lost. Clients must check /api/bookings.
            return JSONResponse({"detail": "internal error (simulated after commit)"}, status_code=500)
        return JSONResponse({"status": "booked", "ref": ref, "booked_at": iso(result.booked_at)})

    @app.get("/api/bookings")
    async def api_bookings(gate: SessionDep) -> dict[str, Any]:
        async with engine.connect() as conn:
            rows = await store.my_bookings(conn, gate.account_id, BOOKINGS_LIMIT)
        return {"bookings": [{"ref": r.ref, "booked_at": iso(r.booked_at), "rate_usd": r.rate_usd} for r in rows]}

    # ---------------- pages ----------------

    @app.get("/loads", response_class=HTMLResponse)
    async def loads_page(request: Request) -> Response:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return RedirectResponse("/login", status_code=303)
        rules = await adversity()
        async with engine.begin() as conn:
            hit = await store.touch_session(conn, security.token_hash(token), rules.captcha_window_s)
        if hit is None:
            return RedirectResponse("/login?error=expired", status_code=303)
        return templates.TemplateResponse(
            request,
            f"loads_{rules.layout_variant}.html",
            {"username": hit.username, "csrf": hit.csrf, "poll_ms": board.feed_poll_ms},
        )

    @app.get("/captcha", response_class=HTMLResponse)
    async def captcha_page(request: Request, error: str | None = None) -> Response:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return RedirectResponse("/login", status_code=303)
        async with engine.begin() as conn:
            question = await store.set_captcha(conn, security.token_hash(token), _new_question())
        a, b = question.split("+")
        return templates.TemplateResponse(request, "captcha.html", {"a": a, "b": b, "error": error})

    @app.post("/captcha")
    async def captcha(request: Request, answer: Annotated[str, Form(max_length=8)]) -> Response:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return RedirectResponse("/login", status_code=303)
        th = security.token_hash(token)
        async with engine.begin() as conn:
            question = await store.set_captcha(conn, th, _new_question())
            a, b = (int(x) for x in question.split("+"))
            if answer.strip() != str(a + b):
                return RedirectResponse("/captcha?error=wrong", status_code=303)
            await store.clear_captcha(conn, th)
        return RedirectResponse("/loads", status_code=303)

    @app.get("/watch", response_class=HTMLResponse)
    async def watch(request: Request) -> Response:
        return templates.TemplateResponse(request, "watch.html", {"poll_ms": max(board.feed_poll_ms, 1000)})

    @app.get("/api/public/recent")
    async def public_recent() -> dict[str, Any]:
        async with engine.connect() as conn:
            rows = await store.recent_public(conn, PUBLIC_RECENT_LIMIT)
            settings = await store.get_settings(conn)
            now = await store.db_now(conn)
        return {
            "loads": [load_out(r, public=True) for r in rows],
            "server_time": iso(now),
            "feed_rate_per_min": settings.feed_rate_per_min,
            "adversity": settings.model_dump(exclude={"feed_rate_per_min"}),
        }

    return app
