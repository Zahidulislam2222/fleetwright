"""Manual one-time codes: the worker announces that an account needs a code; an operator types it
in the dashboard; the API pushes it to a per-account Redis list that the worker reads here."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from uuid import UUID

from redis.asyncio import Redis

from fw_browser.otp import OtpTimeout
from fw_queue import keys


class ManualOtp:
    def __init__(
        self, redis: Redis, tenant_id: UUID, account_id: UUID, announce: Callable[[], Awaitable[None]], poll_s: float
    ) -> None:
        self._redis = redis
        self._key = keys.manual_otp(tenant_id, account_id)
        self._announce = announce
        self._poll_s = poll_s

    async def wait_for_code(self, address: str, since: datetime, timeout_s: float) -> str:
        await self._redis.delete(self._key)  # a code typed for an earlier attempt is stale
        await self._announce()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while loop.time() < deadline:
            code = await self._redis.lpop(self._key)
            if code:
                return str(code)
            await asyncio.sleep(self._poll_s)
        raise OtpTimeout("no code was entered by an operator in time")
