"""Validated models for the mock board: product data (catalogue) and live adversity settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Range(BaseModel):
    model_config = ConfigDict(frozen=True)
    lo: float
    hi: float

    @model_validator(mode="before")
    @classmethod
    def _from_pair(cls, v: object) -> object:
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return {"lo": v[0], "hi": v[1]}
        return v


class Lanes(BaseModel):
    cities: list[str] = Field(min_length=2)
    equipment: list[str] = Field(min_length=1)
    weight_lb: Range
    miles: Range
    rate_per_mile_usd: Range
    pickup_hours_ahead: Range


class Branding(BaseModel):
    name: str
    banner: str


class CaptchaData(BaseModel):
    operands: Range


class Competitors(BaseModel):
    names: list[str] = Field(min_length=1)


class Catalogue(BaseModel):
    lanes: Lanes
    branding: Branding
    captcha: CaptchaData
    competitors: Competitors


class Adversity(BaseModel):
    """Live switches for testing a fleet against a hostile target. All off by default."""

    # Reading ignores unknown keys so an older board instance survives a newer one adding a switch
    # (rolling deploys). The admin API rejects unknown keys itself (see app.admin_patch_settings).
    model_config = ConfigDict(extra="ignore")

    feed_rate_per_min: float = Field(ge=0)  # initial value comes from BoardSettings
    rate_limit_per_min: int = Field(default=0, ge=0)  # per session; 0 = off; over it -> 429
    error_rate: float = Field(default=0.0, ge=0, le=1)  # API answers 5xx
    slow_rate: float = Field(default=0.0, ge=0, le=1)  # share of API calls delayed by slow_ms
    slow_ms: int = Field(default=0, ge=0, le=30000)
    ack_loss_rate: float = Field(default=0.0, ge=0, le=1)  # booking stands but the answer is a 500
    layout_variant: Literal["a", "b"] = "a"  # "b" renames the HTML structure (silent crawler failure)
    competitor_share: float = Field(default=0.0, ge=0, le=1)  # share of loads a rival bot goes for
    competitor_delay_ms: Range = Range(lo=300, hi=3000)
    captcha_enabled: bool = True
    captcha_after_requests: int = Field(default=600, ge=5)  # API calls per session per window
    captcha_window_s: int = Field(default=60, ge=1)
    single_session: bool = False  # a new login revokes the account's other sessions
