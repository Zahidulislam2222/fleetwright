"""Redis Streams with consumer groups: at-least-once delivery. Consumers must be idempotent (the
claim lease is: only one lease can win). Messages from dead consumers are reclaimed with XAUTOCLAIM;
after too many deliveries a message moves to the dead-letter stream."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from fw_queue.keys import dead_letter


@dataclass(frozen=True)
class Message:
    stream: str
    id: str
    fields: dict[str, str]


async def ensure_group(redis: Redis, stream: str, group: str) -> None:
    try:
        await redis.xgroup_create(stream, group, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def add(redis: Redis, stream: str, fields: dict[str, str], maxlen: int) -> str:
    return str(await redis.xadd(stream, fields, maxlen=maxlen, approximate=True))  # type: ignore[arg-type]


async def read(redis: Redis, streams: list[str], group: str, consumer: str, count: int, block_ms: int) -> list[Message]:
    # redis-py's reply type is a loose union; with decode_responses=True the shape is
    # [[stream, [[id, {field: value}], ...]], ...].
    reply = cast(
        "list[tuple[str, list[tuple[str, dict[str, str]]]]] | None",
        await redis.xreadgroup(group, consumer, dict.fromkeys(streams, ">"), count=count, block=block_ms),
    )
    return [Message(stream, msg_id, fields) for stream, entries in reply or [] for msg_id, fields in entries]


async def ack(redis: Redis, msg: Message, group: str) -> None:
    await redis.xack(msg.stream, group, msg.id)


async def reclaim(
    redis: Redis, stream: str, group: str, consumer: str, idle_ms: int, count: int, max_deliveries: int
) -> list[Message]:
    """Takes over messages idle longer than idle_ms (their consumer probably died). Messages delivered
    too often go to the dead-letter stream instead of being returned."""
    _, entries, _ = await redis.xautoclaim(stream, group, consumer, min_idle_time=idle_ms, start_id="0-0", count=count)
    if not entries:
        return []
    pending = cast(
        "list[dict[str, Any]]",
        await redis.xpending_range(stream, group, min="-", max="+", count=max(count * 4, 100), consumername=consumer),
    )
    counts: dict[str, int] = {str(e["message_id"]): int(e["times_delivered"]) for e in pending}
    live: list[Message] = []
    for msg_id, fields in entries:
        if fields is None:  # deleted from the stream meanwhile
            await redis.xack(stream, group, msg_id)
            continue
        if counts.get(msg_id, 0) > max_deliveries:
            await redis.xadd(dead_letter(stream), {**fields, "origin_id": msg_id}, maxlen=100_000, approximate=True)
            await redis.xack(stream, group, msg_id)
            continue
        live.append(Message(stream, msg_id, fields))
    return live
