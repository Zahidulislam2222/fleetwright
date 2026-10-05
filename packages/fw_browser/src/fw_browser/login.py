"""Sign-in flow driven by the target spec: username/password, then the one-time code from the
account's OTP channel, then (if the target asks) the captcha step. Secrets are passed in memory
only and never logged."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from playwright.async_api import Page

from fw_browser import captcha
from fw_browser.otp import OtpProvider
from fw_browser.targets import TargetSpec


class SignInFailed(Exception):
    """The target did not accept the sign-in (wrong password or code, or an unexpected page)."""


@dataclass(frozen=True)
class SignInTimeouts:
    page_ms: int
    otp_wait_s: float
    otp_clock_margin_s: float  # mail-server clocks lag; look this far back for the code


async def sign_in(
    page: Page,
    base_url: str,
    spec: TargetSpec,
    *,
    username: str,
    password: str,
    otp_address: str,
    otp: OtpProvider,
    timeouts: SignInTimeouts,
) -> None:
    login = spec.login
    await page.goto(base_url + login.path, timeout=timeouts.page_ms)
    await page.locator(login.username).fill(username, timeout=timeouts.page_ms)
    await page.locator(login.password).fill(password, timeout=timeouts.page_ms)
    since = datetime.now(UTC) - timedelta(seconds=timeouts.otp_clock_margin_s)
    async with page.expect_navigation(timeout=timeouts.page_ms):
        await page.locator(login.submit).click(timeout=timeouts.page_ms)
    if not _matches(page.url, login.otp_url):
        raise SignInFailed("password step was not accepted")
    code = await otp.wait_for_code(otp_address, since, timeouts.otp_wait_s)
    await page.locator(login.otp_field).fill(code, timeout=timeouts.page_ms)
    async with page.expect_navigation(timeout=timeouts.page_ms):
        await page.locator(login.otp_submit).click(timeout=timeouts.page_ms)
    if _matches(page.url, spec.captcha.url):
        await captcha.solve(page, spec.captcha, timeouts.page_ms)
    if not _matches(page.url, login.home_url):
        raise SignInFailed("one-time code step was not accepted")


def _matches(url: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(url.split("?", 1)[0], pattern)
