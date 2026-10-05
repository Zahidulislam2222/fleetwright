"""Captcha handling. The only automatic solver is for the demo board's own arithmetic check, which
exists to exercise the pause-and-resume path. For any real target the configured solver is
"operator": the slot pauses and a person completes the challenge (no third-party solving service)."""

from __future__ import annotations

from playwright.async_api import Page

from fw_core.targets import CaptchaSpec


class CaptchaNeedsOperator(Exception):
    """A human has to complete the challenge in the slot's browser before it continues."""


async def solve(page: Page, spec: CaptchaSpec, timeout_ms: int) -> None:
    if spec.solver != "demo_arithmetic" or spec.operand_a is None or spec.operand_b is None:
        raise CaptchaNeedsOperator(f"captcha at {page.url} needs an operator")
    a = int((await page.locator(spec.operand_a).text_content(timeout=timeout_ms) or "").strip())
    b = int((await page.locator(spec.operand_b).text_content(timeout=timeout_ms) or "").strip())
    await page.locator(spec.answer).fill(str(a + b), timeout=timeout_ms)
    async with page.expect_navigation(timeout=timeout_ms):
        await page.locator(spec.submit).click(timeout=timeout_ms)
