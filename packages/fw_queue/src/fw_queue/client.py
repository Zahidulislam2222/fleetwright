"""Redis clients: one for the control plane (core) and one per cell. Every call has a timeout."""

from __future__ import annotations

from redis.asyncio import Redis

from fw_core.settings import RedisSettings


def core(cfg: RedisSettings) -> Redis:
    return Redis.from_url(
        cfg.core_url.get_secret_value(),
        socket_timeout=cfg.socket_timeout_s,
        socket_connect_timeout=cfg.socket_timeout_s,
        decode_responses=True,
        health_check_interval=30,
    )


def cell(cfg: RedisSettings, cell_id: str, block_ms: int = 0) -> Redis:
    """A cell client. `block_ms` widens the socket timeout for blocking stream reads."""
    try:
        url = cfg.cells[cell_id].get_secret_value()
    except KeyError as exc:
        raise KeyError(f"no Redis configured for cell {cell_id!r}") from exc
    timeout = cfg.socket_timeout_s + block_ms / 1000
    return Redis.from_url(
        url,
        socket_timeout=timeout,
        socket_connect_timeout=cfg.socket_timeout_s,
        decode_responses=True,
        health_check_interval=30,
    )
