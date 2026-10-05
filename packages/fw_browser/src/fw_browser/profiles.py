"""Browser profiles (config/browser.yaml). One stable profile per account group keeps an account's
locale, timezone and screen size consistent across restarts and machines."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fw_core.data import load_yaml


class Viewport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    width: int = Field(ge=320, le=7680)
    height: int = Field(ge=240, le=4320)


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    locale: str
    timezone: str
    viewport: Viewport

    def context_options(self) -> dict[str, Any]:
        return {
            "locale": self.locale,
            "timezone_id": self.timezone,
            "viewport": {"width": self.viewport.width, "height": self.viewport.height},
        }


class Profiles(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    profiles: dict[str, Profile]
    groups: dict[str, str]

    @model_validator(mode="after")
    def _known(self) -> Profiles:
        if "default" not in self.profiles:
            raise ValueError("browser.yaml needs a 'default' profile")
        missing = {p for p in self.groups.values() if p not in self.profiles}
        if missing:
            raise ValueError(f"groups point at unknown profiles: {sorted(missing)}")
        return self

    def for_group(self, group: str) -> Profile:
        return self.profiles[self.groups.get(group, "default")]


def load_profiles(config_dir: Path) -> Profiles:
    return load_yaml(config_dir, "browser.yaml", Profiles)
