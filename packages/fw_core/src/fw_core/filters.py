"""Tenant filters (which jobs to claim) and schedules (when a filter is active).

A schedule lists filter ids in `targets` and weekly windows in its own timezone:
    [{"days": [0, 1, 2, 3, 4], "start": "06:00", "end": "18:00"}, ...]   (0 = Monday)
A window whose end is before its start runs past midnight. A filter named by no enabled schedule
is always active; a filter named by one or more is active inside any of their windows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Annotated, Any
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

ANY = "Any"


@dataclass(frozen=True)
class Filter:
    id: UUID
    name: str
    origin: str
    destination: str
    min_rate_usd: int
    equipment: frozenset[str]
    max_weight_lb: int
    account_group: str

    def matches(self, job: Mapping[str, Any]) -> bool:
        return (
            (self.origin == ANY or job.get("origin") == self.origin)
            and (self.destination == ANY or job.get("destination") == self.destination)
            and int(job.get("rate_usd", 0)) >= self.min_rate_usd
            and (not self.equipment or job.get("equipment") in self.equipment)
            and int(job.get("weight_lb", 0)) <= self.max_weight_lb
        )


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    days: frozenset[Annotated[int, Field(ge=0, le=6)]] = Field(min_length=1)  # 0 = Monday
    start: time
    end: time

    def contains(self, local: datetime) -> bool:
        t = local.time().replace(tzinfo=None)
        if self.start <= self.end:
            return local.weekday() in self.days and self.start <= t < self.end
        # overnight: the part after start belongs to that day, the part before end to the day before
        if t >= self.start:
            return local.weekday() in self.days
        return t < self.end and (local - timedelta(days=1)).weekday() in self.days


@dataclass(frozen=True)
class Schedule:
    id: UUID
    timezone: str
    windows: tuple[Window, ...]
    targets: frozenset[UUID]

    def open_at(self, now: datetime) -> bool:
        local = now.astimezone(ZoneInfo(self.timezone))
        return any(w.contains(local) for w in self.windows)


def parse_windows(raw: Iterable[Mapping[str, Any]]) -> tuple[Window, ...]:
    return tuple(Window.model_validate(w) for w in raw)


def active(filters: Iterable[Filter], schedules: Iterable[Schedule], now: datetime) -> list[Filter]:
    scheduled: dict[UUID, bool] = {}
    for s in schedules:
        is_open = s.open_at(now)
        for target in s.targets:
            scheduled[target] = scheduled.get(target, False) or is_open
    return [f for f in filters if scheduled.get(f.id, True)]


def first_match(filters: Iterable[Filter], job: Mapping[str, Any]) -> Filter | None:
    return next((f for f in filters if f.matches(job)), None)


async def load(conn: AsyncConnection, tenant_id: UUID) -> tuple[list[Filter], list[Schedule]]:
    """Enabled filters (by name, for a stable first-match order) and enabled schedules."""
    filters = [
        Filter(
            r.id,
            r.name,
            r.origin,
            r.destination,
            r.min_rate_usd,
            frozenset(r.equipment),
            r.max_weight_lb,
            r.account_group,
        )
        for r in await conn.execute(
            text(
                """SELECT id, name, origin, destination, min_rate_usd, equipment, max_weight_lb, account_group
                   FROM filters WHERE tenant_id = :t AND enabled ORDER BY name"""
            ),
            {"t": tenant_id},
        )
    ]
    schedules = [
        Schedule(r.id, r.timezone, parse_windows(r.windows), frozenset(r.targets))
        for r in await conn.execute(
            text("SELECT id, timezone, windows, targets FROM schedules WHERE tenant_id = :t AND enabled"),
            {"t": tenant_id},
        )
    ]
    return filters, schedules
