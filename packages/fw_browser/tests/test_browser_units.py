"""Phase 4 unit tests: config files load and validate, proxy stickiness/rotation/health, session
refresh timing, evidence retention."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fw_browser.evidence import EvidenceStore
from fw_browser.otp import extract_code
from fw_browser.profiles import Profiles, load_profiles
from fw_browser.proxy import ProxyConfig, ProxyPool, load_proxy_config
from fw_core.targets import load_targets
from fw_core.vault import StoredSession, session_expiry

CONFIG = Path(__file__).resolve().parents[3] / "config"


def test_shipped_config_files_validate() -> None:
    assert load_targets(CONFIG).get("demo-board").api.book.endswith("{ref}/book")
    assert load_profiles(CONFIG).for_group("unknown-group") == load_profiles(CONFIG).profiles["default"]
    assert load_proxy_config(CONFIG).provider == "mock"
    with pytest.raises(KeyError, match="no adapter"):
        load_targets(CONFIG).get("some-real-board")


def test_profiles_reject_dangling_group() -> None:
    with pytest.raises(ValidationError, match="unknown profiles"):
        Profiles.model_validate(
            {
                "profiles": {
                    "default": {"locale": "en-US", "timezone": "UTC", "viewport": {"width": 800, "height": 600}}
                },
                "groups": {"x": "missing"},
            }
        )


def _pool(rotate_after: int = 3) -> ProxyPool:
    cfg = ProxyConfig.model_validate(
        {
            "provider": "mock",
            "sticky_minutes": 30,
            "rotate_after_blocks": rotate_after,
            "health_window": 10,
            "exits": [{"id": f"e{i}", "server": None, "region": "r"} for i in range(3)],
        }
    )
    return ProxyPool(cfg)


def test_proxy_is_sticky_and_spreads_accounts() -> None:
    pool = _pool()
    first = {a: pool.exit_for(a, now=0).id for a in ("a", "b", "c")}
    assert len(set(first.values())) == 3, "accounts are spread over exits"
    assert all(pool.exit_for(a, now=60).id == first[a] for a in first), "same exit within the sticky window"


def test_proxy_rotates_after_consecutive_blocks_and_prefers_healthy_exits() -> None:
    pool = _pool(rotate_after=3)
    start = pool.exit_for("a", now=0).id
    assert not pool.record("a", blocked=True, now=1)
    assert not pool.record("a", blocked=False, now=2), "a success resets the streak"
    assert not pool.record("a", blocked=True, now=3)
    assert not pool.record("a", blocked=True, now=4)
    assert pool.record("a", blocked=True, now=5), "third block in a row rotates"
    moved = pool.exit_for("a", now=6).id
    assert moved != start
    assert pool.block_rate(start) == pytest.approx(0.8)
    assert pool.exit_for("new", now=7).id != start, "new accounts avoid the blocked exit"


def test_session_expiry_and_refresh_share() -> None:
    now = datetime(2026, 10, 5, 12, tzinfo=UTC)
    state = {
        "cookies": [{"name": "s", "expires": (now + timedelta(hours=1)).timestamp()}, {"name": "x", "expires": -1}]
    }
    assert session_expiry(state) == now + timedelta(hours=1)
    assert session_expiry({"cookies": [{"name": "x", "expires": -1}]}) is None
    session = StoredSession(state, "fresh", now + timedelta(hours=1), now)
    assert not session.needs_refresh(now + timedelta(minutes=41), 0.7)
    assert session.needs_refresh(now + timedelta(minutes=42), 0.7)
    assert StoredSession(state, "expired", None, now).needs_refresh(now, 0.7)
    assert not StoredSession(state, "fresh", None, now).needs_refresh(now + timedelta(days=9), 0.7)


def test_evidence_retention(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path, retention_days=7)
    tenant = uuid4()
    old = store.folder(tenant, "Sign In / step 2!", datetime(2026, 9, 1, tzinfo=UTC))
    new = store.folder(tenant, "sign-in", datetime(2026, 10, 4, tzinfo=UTC))
    assert old.name.endswith("-sign-in-step-2"), "labels are made filesystem-safe"
    assert store.prune(date(2026, 10, 5)) == 1
    assert not old.exists() and new.exists()


def test_extract_code() -> None:
    assert extract_code("Your code is 482913. It expires in 5 minutes.") == "482913"
    assert extract_code("no digits here") is None
