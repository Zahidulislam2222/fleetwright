"""Failure evidence: a Playwright trace (actions, network, DOM snapshots) and a screenshot for the
operation that failed, written under the storage directory per tenant and day, pruned after the
retention period. Tracing runs in chunks so only the failing operation is kept."""

from __future__ import annotations

import re
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

from playwright.async_api import BrowserContext, Page

_SAFE = re.compile(r"[^a-z0-9-]+")


class EvidenceStore:
    def __init__(self, root: Path, retention_days: int) -> None:
        self.root = root
        self.retention_days = retention_days

    def folder(self, tenant_id: UUID, label: str, now: datetime) -> Path:
        safe = _SAFE.sub("-", label.lower()).strip("-")[:60] or "operation"
        path = self.root / str(tenant_id) / now.strftime("%Y%m%d") / f"{now.strftime('%H%M%S%f')}-{safe}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def capture(self, context: BrowserContext, page: Page | None, tenant_id: UUID, label: str) -> Path:
        """Ends the current trace chunk into the evidence folder and adds a screenshot."""
        folder = self.folder(tenant_id, label, datetime.now(UTC))
        if page is not None and not page.is_closed():
            await page.screenshot(path=folder / "screenshot.png", full_page=True)
        await context.tracing.stop_chunk(path=folder / "trace.zip")
        return folder

    def prune(self, today: date) -> int:
        """Removes day folders older than the retention period; returns how many were removed."""
        cutoff = (today - timedelta(days=self.retention_days)).strftime("%Y%m%d")
        removed = 0
        if not self.root.exists():
            return 0
        for tenant in self.root.iterdir():
            if not tenant.is_dir():
                continue
            for day in tenant.iterdir():
                if day.is_dir() and day.name.isdigit() and day.name < cutoff:
                    shutil.rmtree(day)
                    removed += 1
        return removed
