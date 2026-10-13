"""Measure isolated Chromium contexts against an owned fixture; never attach user Chrome.

Progress is atomically published after each sampling tick. A resource refusal is evidence of
an incomplete benchmark, never a successful capacity claim. Run with project Python:
python -m loadtest.density loadtest/density.json
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import psutil
from playwright.async_api import BrowserContext, async_playwright
from pydantic import BaseModel, ConfigDict, Field


class DensityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context_counts: list[int] = Field(min_length=1, max_length=10)
    duration_s: float = Field(gt=0, le=86400)
    tick_s: float = Field(gt=0)
    launch_batch: int = Field(ge=1, le=10)
    action_timeout_ms: int = Field(gt=0)
    minimum_available_bytes: int = Field(gt=0)
    maximum_process_rss_bytes: int = Field(gt=0)
    memory_accounting: Literal["rss", "cgroup-v2"]
    report_dir: Path
    fixture: Path


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def cgroup_memory(root: Path) -> int:
    """Read the kernel's container-wide charge, counting shared pages once.

    The caller explicitly selects cgroup accounting. Missing/unbounded controller data must
    refuse the run instead of silently substituting a different memory measurement.
    """
    try:
        limit = int((root / "memory.max").read_text().strip())
        current = int((root / "memory.current").read_text().strip())
        swap = int((root / "memory.swap.current").read_text().strip())
        if limit <= 0 or current < 0 or swap < 0:
            raise ValueError("invalid cgroup memory counters")
        return current + swap
    except (OSError, ValueError) as error:
        raise RuntimeError("resource accounting: bounded cgroup-v2 memory unavailable") from error


def resources(cfg: DensityConfig) -> dict[str, Any]:
    root = psutil.Process()
    processes = [root, *root.children(recursive=True)]
    rss, cpu = 0, 0.0
    for process in processes:
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            rss += process.memory_info().rss
            times = process.cpu_times()
            cpu += times.user + times.system
    memory = cgroup_memory(Path("/sys/fs/cgroup")) if cfg.memory_accounting == "cgroup-v2" else rss
    return {
        "rss_bytes": rss,
        "enforced_memory_bytes": memory,
        "memory_accounting": cfg.memory_accounting,
        "cpu_s": cpu,
        "available_bytes": psutil.virtual_memory().available,
    }


def require_resources(cfg: DensityConfig, sample: dict[str, Any]) -> None:
    if sample["available_bytes"] < cfg.minimum_available_bytes:
        raise RuntimeError("resource floor: insufficient available system memory")
    if sample["enforced_memory_bytes"] > cfg.maximum_process_rss_bytes:
        raise RuntimeError("resource ceiling: benchmark process memory exceeded")


async def run_count(cfg: DensityConfig, count: int, fixture: str) -> dict[str, Any]:
    if not 1 <= count <= 100:
        raise ValueError("context count must be within local safety bound1..100")
    report: dict[str, Any] = {
        "status": "starting",
        "contexts_requested": count,
        "contexts_created": 0,
        "requested_duration_s": cfg.duration_s,
        "started_utc": datetime.now(UTC).isoformat(),
        "workload": "owned static fixture and click/read; not freight booking",
        "memory_accounting": cfg.memory_accounting,
        "memory_ceiling_bytes": cfg.maximum_process_rss_bytes,
        "samples": [],
        "action_rounds": 0,
        "action_errors": 0,
        "hardware": {
            "logical_cpus": psutil.cpu_count(),
            "physical_cpus": psutil.cpu_count(logical=False),
            "total_memory_bytes": psutil.virtual_memory().total,
            "platform": sys.platform,
        },
    }
    output = cfg.report_dir / f"contexts-{count}.json"
    atomic_json(output, report)
    start = time.monotonic()
    contexts: list[BrowserContext] = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            report["browser_version"] = browser.version
            try:
                for batch_start in range(0, count, cfg.launch_batch):
                    require_resources(cfg, resources(cfg))
                    for _ in range(min(cfg.launch_batch, count - batch_start)):
                        context = await browser.new_context()
                        context.set_default_timeout(cfg.action_timeout_ms)
                        page = await context.new_page()
                        await page.set_content(fixture)
                        contexts.append(context)
                    report["contexts_created"] = len(contexts)
                    atomic_json(output, report)
                start = time.monotonic()
                report["status"] = "running"
                while time.monotonic() - start < cfg.duration_s:
                    sample = resources(cfg)
                    require_resources(cfg, sample)
                    action_start = time.perf_counter()
                    # Bounded concurrency avoids creating a CPU spike that measures only startup.
                    for batch_start in range(0, count, cfg.launch_batch):
                        batch = contexts[batch_start : batch_start + cfg.launch_batch]
                        await asyncio.gather(*(context.pages[0].locator("#tick").click() for context in batch))
                    report["action_rounds"] += 1
                    expected = str(report["action_rounds"])
                    for context in contexts:
                        if await context.pages[0].locator("#count").inner_text() != expected:
                            raise RuntimeError("isolated page counter mismatch")
                    report["samples"].append(
                        {
                            "elapsed_s": time.monotonic() - start,
                            "action_round_ms": (time.perf_counter() - action_start) * 1000,
                            **sample,
                        }
                    )
                    report["actual_duration_s"] = time.monotonic() - start
                    atomic_json(output, report)
                    await asyncio.sleep(min(cfg.tick_s, max(0, cfg.duration_s - (time.monotonic() - start))))
                report["status"] = "passed"
            finally:
                await browser.close()
    except Exception as error:
        report["status"] = "incomplete"
        report["error_type"] = type(error).__name__
        # Exception messages from browsers may include paths/targets; keep reports bounded/safe.
        report["reason"] = str(error) if isinstance(error, (RuntimeError, ValueError)) else "browser operation failed"
        report["action_errors"] += 1
    report["actual_duration_s"] = time.monotonic() - start
    report["finished_utc"] = datetime.now(UTC).isoformat()
    atomic_json(output, report)
    return report


async def main(config_path: Path) -> None:
    cfg = DensityConfig.model_validate_json(await asyncio.to_thread(config_path.read_text, encoding="utf-8"))
    fixture = await asyncio.to_thread((config_path.parent / cfg.fixture).read_text, encoding="utf-8")
    for count in cfg.context_counts:
        report = await run_count(cfg, count, fixture)
        print(json.dumps({k: v for k, v in report.items() if k != "samples"}), flush=True)
        if report["status"] != "passed":
            raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
