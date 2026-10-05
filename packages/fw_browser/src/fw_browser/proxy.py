"""Proxy exits per account: sticky assignment, rotation after repeated blocks, and a block-rate
health score per exit. The demo ships only the mock provider (exits that connect directly); a paid
residential provider is a per-client addition after cost approval, with its credentials in env."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from fw_core.data import load_yaml


class Exit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    server: str | None
    region: str


class ProxyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: Literal["mock"]
    sticky_minutes: int = Field(ge=1)
    rotate_after_blocks: int = Field(ge=1)
    health_window: int = Field(ge=1)
    exits: list[Exit] = Field(min_length=1)


def load_proxy_config(config_dir: Path) -> ProxyConfig:
    return load_yaml(config_dir, "proxy.yaml", ProxyConfig)


@dataclass
class _Assignment:
    exit_id: str
    since: float
    blocks_in_a_row: int = 0


@dataclass
class ProxyPool:
    """In-process state for one worker. `now` is passed in (monotonic seconds) so tests are exact."""

    cfg: ProxyConfig
    _assigned: dict[str, _Assignment] = field(default_factory=dict)
    _history: dict[str, deque[bool]] = field(default_factory=dict)

    def exit_for(self, account: str, now: float) -> Exit:
        current = self._assigned.get(account)
        if current is not None and now - current.since < self.cfg.sticky_minutes * 60:
            return self._exit(current.exit_id)
        chosen = self._healthiest(exclude=None)
        self._assigned[account] = _Assignment(chosen.id, now)
        return chosen

    def record(self, account: str, blocked: bool, now: float) -> bool:
        """Records one response seen through the account's exit; returns True if the account moved."""
        current = self._assigned.get(account)
        if current is None:
            return False
        self._history.setdefault(current.exit_id, deque(maxlen=self.cfg.health_window)).append(blocked)
        current.blocks_in_a_row = current.blocks_in_a_row + 1 if blocked else 0
        if current.blocks_in_a_row < self.cfg.rotate_after_blocks:
            return False
        replacement = self._healthiest(exclude=current.exit_id)
        self._assigned[account] = _Assignment(replacement.id, now)
        return replacement.id != current.exit_id

    def block_rate(self, exit_id: str) -> float:
        history = self._history.get(exit_id)
        return sum(history) / len(history) if history else 0.0

    @staticmethod
    def playwright_proxy(exit_: Exit) -> dict[str, Any] | None:
        return None if exit_.server is None else {"server": exit_.server}

    def _exit(self, exit_id: str) -> Exit:
        return next(e for e in self.cfg.exits if e.id == exit_id)

    def _healthiest(self, exclude: str | None) -> Exit:
        candidates = [e for e in self.cfg.exits if e.id != exclude] or list(self.cfg.exits)
        load = dict.fromkeys((e.id for e in candidates), 0)
        for a in self._assigned.values():
            if a.exit_id in load:
                load[a.exit_id] += 1
        return min(candidates, key=lambda e: (self.block_rate(e.id), load[e.id], e.id))
