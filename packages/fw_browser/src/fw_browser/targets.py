"""Target adapter specs (config/targets.yaml): selectors, URLs and endpoints for each site a worker
signs in to. Kept as data so a selector change is a config edit, not a code change."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from fw_core.data import load_yaml


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LoginSpec(_Spec):
    path: str
    username: str
    password: str
    submit: str
    otp_url: str
    otp_field: str
    otp_submit: str
    home_url: str


class CaptchaSpec(_Spec):
    url: str
    solver: Literal["demo_arithmetic", "operator"]
    operand_a: str | None = None
    operand_b: str | None = None
    answer: str
    submit: str


class ApiSpec(_Spec):
    me: str
    loads: str
    book: str
    bookings: str
    csrf_header: str


class TargetSpec(_Spec):
    name: str
    login: LoginSpec
    captcha: CaptchaSpec
    api: ApiSpec
    blocked_statuses: frozenset[int]


class Targets(_Spec):
    targets: dict[str, TargetSpec]

    def get(self, target: str) -> TargetSpec:
        try:
            return self.targets[target]
        except KeyError:
            raise KeyError(f"no adapter configured for target {target!r}") from None


def load_targets(config_dir: Path) -> Targets:
    return load_yaml(config_dir, "targets.yaml", Targets)
