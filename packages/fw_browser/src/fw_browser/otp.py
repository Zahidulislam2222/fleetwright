"""One-time-code adapters. The code itself is never logged (fw_core.logs redacts as a backstop).

- MailpitOtp: reads the demo mailbox through Mailpit's HTTP API (local and demo server).
- ImapOtp: a real mailbox over IMAPS, for a client whose target emails codes.
- ManualOtp: an operator types the code into the dashboard; it arrives through Redis.
"""

from __future__ import annotations

import asyncio
import email
import email.utils
import imaplib
import re
import ssl
from datetime import UTC, datetime
from email.message import Message
from typing import Protocol

import httpx

CODE = re.compile(r"\b(\d{4,10})\b")
POLL_S = 0.25


class OtpTimeout(Exception):
    """No code arrived in time."""


class OtpProvider(Protocol):
    async def wait_for_code(self, address: str, since: datetime, timeout_s: float) -> str: ...


def extract_code(text: str) -> str | None:
    match = CODE.search(text)
    return match.group(1) if match else None


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class MailpitOtp:
    def __init__(self, api_url: str, timeout_s: float = 5.0) -> None:
        self._client = httpx.AsyncClient(base_url=api_url, timeout=timeout_s)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def wait_for_code(self, address: str, since: datetime, timeout_s: float) -> str:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while loop.time() < deadline:
            code = await self._latest(address, since)
            if code is not None:
                return code
            await asyncio.sleep(POLL_S)
        raise OtpTimeout(f"no code for {address} within {timeout_s}s")

    async def _latest(self, address: str, since: datetime) -> str | None:
        res = await self._client.get("/api/v1/search", params={"query": f'to:"{address}"', "limit": 5})
        res.raise_for_status()
        for msg in res.json().get("messages", []):  # newest first
            if _parse_ts(msg["Created"]) < since:
                continue
            code = extract_code(msg.get("Snippet", ""))
            if code is None:
                full = await self._client.get(f"/api/v1/message/{msg['ID']}")
                full.raise_for_status()
                code = extract_code(full.json().get("Text", ""))
            if code is not None:
                return code
        return None


class ImapOtp:
    """Blocking imaplib calls run in a thread. TLS with certificate and hostname checks."""

    def __init__(self, host: str, port: int, username: str, password: str, mailbox: str = "INBOX") -> None:
        self._args = (host, port, username, password, mailbox)

    async def wait_for_code(self, address: str, since: datetime, timeout_s: float) -> str:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while loop.time() < deadline:
            code = await asyncio.to_thread(self._fetch, address, since)
            if code is not None:
                return code
            await asyncio.sleep(max(POLL_S, 2.0))
        raise OtpTimeout(f"no code for {address} within {timeout_s}s")

    def _fetch(self, address: str, since: datetime) -> str | None:
        host, port, username, password, mailbox = self._args
        with imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context()) as imap:
            imap.login(username, password)
            imap.select(mailbox, readonly=True)
            day = since.astimezone(UTC).strftime("%d-%b-%Y")
            _, data = imap.search(None, "TO", f'"{address}"', "SINCE", day)
            for num in reversed(data[0].split()):
                _, parts = imap.fetch(num, "(RFC822)")
                raw = parts[0]
                if not isinstance(raw, tuple):
                    continue
                msg = email.message_from_bytes(raw[1])
                sent = email.utils.parsedate_to_datetime(msg["Date"]) if msg["Date"] else None
                if sent is not None and sent < since:
                    continue
                code = extract_code(_text_of(msg))
                if code is not None:
                    return code
        return None


def _text_of(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                return payload.decode(errors="replace") if isinstance(payload, bytes) else ""
        return ""
    payload = msg.get_payload(decode=True)
    return payload.decode(errors="replace") if isinstance(payload, bytes) else ""
