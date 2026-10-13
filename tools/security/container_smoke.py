"""Network-free runtime image proof: module imports and isolated Chromium navigation/actions."""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright


async def main(fixture: Path) -> None:
    modules = sys.argv[2:]
    for name in modules:
        importlib.import_module(name)
    html = await asyncio.to_thread(fixture.read_text, encoding="utf-8")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            first, second = await browser.new_context(), await browser.new_context()
            page, other = await first.new_page(), await second.new_page()
            url = "data:text/html," + quote(html)
            await page.goto(url)
            await other.goto(url)
            await page.locator("#tick").click()
            assert await page.locator("#count").inner_text() == "1"
            assert await other.locator("#count").inner_text() == "0"
            print(
                json.dumps(
                    {
                        "status": "passed",
                        "module_imports": modules,
                        "browser_version": browser.version,
                        "contexts": 2,
                        "navigation": "owned data page",
                        "isolated_counter": True,
                    }
                ),
                flush=True,
            )
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
