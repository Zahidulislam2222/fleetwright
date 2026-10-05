"""Load feed and rival bots. Exactly one board instance generates the feed: it holds a Postgres
advisory lock on a dedicated connection; another instance takes over when that connection dies."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from mockboard import security, store
from mockboard.models import Adversity, Catalogue

log = logging.getLogger("mockboard.feed")

TICK_S = 0.1  # generator resolution; 100 loads/s means about 10 per tick
SETTINGS_REFRESH_S = 1.0
MAX_PENDING_RIVALS = 5000  # bound on scheduled rival-bot attempts (memory safety under stress)
LEADER_RETRY_S = 2.0


def make_load(cat: Catalogue) -> dict[str, Any]:
    lanes = cat.lanes
    origin = security.choice(lanes.cities)
    destination = security.choice([c for c in lanes.cities if c != origin])
    miles = security.randint(int(lanes.miles.lo), int(lanes.miles.hi))
    rate = round(miles * security.uniform(lanes.rate_per_mile_usd.lo, lanes.rate_per_mile_usd.hi) / 25) * 25
    hours = security.uniform(lanes.pickup_hours_ahead.lo, lanes.pickup_hours_ahead.hi)
    weight = round(security.randint(int(lanes.weight_lb.lo), int(lanes.weight_lb.hi)) / 500) * 500
    return {
        "origin": origin,
        "destination": destination,
        "equipment": security.choice(lanes.equipment),
        "weight_lb": weight,
        "miles": miles,
        "rate_usd": rate,
        "pickup_at": (datetime.now(UTC) + timedelta(hours=hours)).replace(minute=0, second=0, microsecond=0),
    }


class Feed:
    def __init__(self, engine: AsyncEngine, catalogue: Catalogue) -> None:
        self.engine = engine
        self.catalogue = catalogue
        self.is_leader = False
        self._rivals: set[asyncio.Task[None]] = set()

    async def run(self) -> None:
        while True:
            try:
                await self._lead()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("feed leader loop failed; retrying")
            self.is_leader = False
            await asyncio.sleep(LEADER_RETRY_S)

    async def _lead(self) -> None:
        async with self.engine.connect() as lock_conn:
            got = (
                (await lock_conn.execute(text("SELECT pg_try_advisory_lock(hashtext('mockboard-feed')) AS ok")))
                .one()
                .ok
            )
            await lock_conn.commit()
            if not got:
                return
            self.is_leader = True
            log.info("feed leader acquired")
            try:
                await self._generate()
            finally:
                with contextlib.suppress(Exception):
                    await lock_conn.execute(text("SELECT pg_advisory_unlock(hashtext('mockboard-feed'))"))

    async def _generate(self) -> None:
        loop = asyncio.get_running_loop()
        owed = 0.0
        settings: Adversity | None = None
        refreshed = 0.0
        last = loop.time()
        while True:
            await asyncio.sleep(TICK_S)
            now = loop.time()
            if settings is None or now - refreshed >= SETTINGS_REFRESH_S:
                async with self.engine.connect() as conn:
                    settings = await store.get_settings(conn)
                refreshed = now
            owed += settings.feed_rate_per_min / 60.0 * (now - last)
            last = now
            count = int(owed)
            if count <= 0:
                continue
            owed -= count
            rows = [make_load(self.catalogue) for _ in range(count)]
            async with self.engine.begin() as conn:
                created = await store.insert_loads(conn, rows)
            self._send_rivals(created, settings)

    def _send_rivals(self, created: list[Any], settings: Adversity) -> None:
        for load in created:
            if len(self._rivals) >= MAX_PENDING_RIVALS or not security.chance(settings.competitor_share):
                continue
            delay = security.uniform(settings.competitor_delay_ms.lo, settings.competitor_delay_ms.hi) / 1000
            name = security.choice(self.catalogue.competitors.names)
            task = asyncio.create_task(self._rival(load.id, name, delay))
            self._rivals.add(task)
            task.add_done_callback(self._rivals.discard)

    async def _rival(self, load_id: int, name: str, delay_s: float) -> None:
        await asyncio.sleep(delay_s)
        try:
            async with self.engine.begin() as conn:
                await store.competitor_book(conn, load_id, name)
        except Exception:
            log.exception("rival booking failed", extra={"load_id": load_id})
