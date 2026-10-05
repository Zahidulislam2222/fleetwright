"""Generate Fleetwright media through OpenRouter (images + video).

Usage:
    uv run python tools/media/generate.py image <prompt-id>
    uv run python tools/media/generate.py video <prompt-id>
    uv run python tools/media/generate.py resume <prompt-id>     # poll an already-submitted video job
    uv run python tools/media/generate.py resubmit <prompt-id>   # submit again after a lost submit response

Configuration lives in tools/media/config.json; prompts in tools/media/prompts.json.
The API key is read from the file named by the env var in config["key_file_env"]; it is never printed.
Every job writes a JSON record (model, params, job id, reported cost) to config["jobs_dir"].
Before any paid call the script checks the key's remaining limit against an estimate and refuses
to submit when the estimate does not fit.
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
PROMPTS = json.loads((HERE / "prompts.json").read_text(encoding="utf-8"))
OUT_DIR = ROOT / CONFIG["output_dir"]
JOBS_DIR = ROOT / CONFIG["jobs_dir"]
API = CONFIG["api_base"].rstrip("/")
API_HOST = urlsplit(API).hostname
# Explicit verifying context: certificate chain + hostname checks are required, never optional.
TLS = ssl.create_default_context()


# Verifying TLS (chain + hostname) and no automatic redirects: the caller decides where credentials go.
_CLIENT = httpx.Client(verify=TLS, follow_redirects=False, timeout=CONFIG["request_timeout_s"])


def _fetch(method: str, url: str, body: bytes | None, headers: dict) -> tuple[int, bytes, str | None]:
    """One HTTPS exchange: (status, payload, Location header). Any other scheme is refused."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError(f"refusing a non-HTTPS URL (host {parts.hostname!r})")
    resp = _CLIENT.request(method, url, content=body, headers=headers)
    return resp.status_code, resp.content, resp.headers.get("Location")


def _key() -> str:
    env_name = CONFIG["key_file_env"]
    path = os.environ.get(env_name)
    if not path:
        sys.exit(f"Set {env_name} to the path of the OpenRouter key file.")
    return Path(path).read_text(encoding="utf-8").strip()


def _request(method: str, url: str, body: dict | None = None, raw: bool = False, redirects: int = 3):
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError(f"Refusing non-HTTPS URL: {url}")
    # The API key goes only to the configured API host. Any other host (e.g. a storage URL
    # returned by the API) is fetched without credentials.
    if parts.hostname != API_HOST:
        if method != "GET" or body is not None:
            raise ValueError(f"Refusing authenticated {method} to non-API host {parts.hostname}")
        payload = _download_unauthenticated(url)
        return payload if raw else json.loads(payload)
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {_key()}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    status, payload, location = _fetch(method, url, data, headers)
    if status in {301, 302, 303, 307, 308} and location and redirects > 0:
        # Signed download URLs redirect to storage; never forward the API key to another host.
        target = urljoin(url, location)
        if urlsplit(target).hostname != parts.hostname:
            return _download_unauthenticated(target) if raw else json.loads(_download_unauthenticated(target))
        return _request(method, target, body, raw, redirects - 1)
    # A redirect we could not follow (no Location, or hops exhausted) is a failure, not a payload.
    if status >= 300:
        raise RuntimeError(f"HTTP {status} from {url}: {payload.decode(errors='replace')[:800]}")
    return payload if raw else json.loads(payload)


def _download_unauthenticated(url: str, redirects: int = 3) -> bytes:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError(f"Refusing non-HTTPS URL: {url}")
    status, payload, location = _fetch("GET", url, None, {})
    if status in {301, 302, 303, 307, 308} and location and redirects > 0:
        return _download_unauthenticated(urljoin(url, location), redirects - 1)
    if status >= 300:
        raise RuntimeError(f"HTTP {status} downloading from {parts.hostname}")
    return payload


def remaining_limit() -> float:
    data = _request("GET", f"{API}/key")["data"]
    remaining = data.get("limit_remaining")
    if remaining is None:
        # Fail closed: an uncapped key gives the cost guard nothing to check against.
        sys.exit("This key has no spending limit. Set a limit on the key before running paid jobs.")
    return float(remaining)


def _guard(estimate: float) -> None:
    remaining = remaining_limit()
    print(f"Key limit remaining: ${remaining}  |  estimated max for this job: ${estimate:.2f}")
    if remaining < estimate:
        sys.exit("Estimate exceeds the key's remaining limit. Raise the key limit or reduce the job.")


def _record(prompt_id: str, record: dict) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    path = JOBS_DIR / f"{prompt_id}.json"
    history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    history.append(record)
    path.write_text(json.dumps(history, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def generate_image(prompt_id: str) -> None:
    spec = PROMPTS[prompt_id]
    model = CONFIG["image"]["model"]
    _guard(CONFIG["image"]["estimated_max_cost_usd"])
    body = {"model": model, "prompt": spec["prompt"], **spec.get("params", {})}
    started = _now()
    result = _request("POST", f"{API}/images", body)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for index, item in enumerate(result.get("data", [])):
        ext = (item.get("media_type") or "image/png").split("/")[-1]
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        target = OUT_DIR / f"{prompt_id}-{stamp}-{index}.{ext}"
        target.write_bytes(base64.b64decode(item["b64_json"]))
        files.append(str(target.relative_to(ROOT)))
    cost = (result.get("usage") or {}).get("cost")
    _record(
        prompt_id,
        {
            "kind": "image",
            "model": model,
            "params": spec.get("params", {}),
            "started": started,
            "finished": _now(),
            "files": files,
            "reported_cost_usd": cost,
        },
    )
    print(f"Saved {files}  |  reported cost: ${cost}")


def _video_estimate(spec: dict) -> float:
    est = spec["estimate"]
    tokens = est["width"] * est["height"] * est["fps"] * spec["params"]["duration"] / 1024
    return tokens * CONFIG["video"]["price_per_video_token_usd"] * CONFIG["video"]["estimated_safety_factor"]


def _latest_file(prompt_id: str) -> Path:
    record = JOBS_DIR / f"{prompt_id}.json"
    history = json.loads(record.read_text(encoding="utf-8")) if record.exists() else []
    for entry in reversed(history):
        if entry.get("files"):
            return ROOT / entry["files"][0]
    sys.exit(f"No generated file recorded for {prompt_id!r}; generate it first.")


def _unconfirmed_submit(prompt_id: str) -> str | None:
    """Timestamp of a submit attempt that never got a job id back (the job may still be billed)."""
    record = JOBS_DIR / f"{prompt_id}.json"
    history = json.loads(record.read_text(encoding="utf-8")) if record.exists() else []
    for entry in reversed(history):
        if entry.get("kind") == "video":
            return None
        if entry.get("kind") == "video-submit-attempt":
            return entry.get("submitted", "unknown time")
    return None


def generate_video(prompt_id: str, allow_resubmit: bool = False) -> None:
    pending = _unconfirmed_submit(prompt_id)
    if pending and not allow_resubmit:
        sys.exit(
            f"A submit at {pending} never returned a job id, so that job may still be running and billed. "
            f"Check the OpenRouter activity page; to submit again anyway, use: resubmit {prompt_id}"
        )
    spec = PROMPTS[prompt_id]
    model = CONFIG["video"]["model"]
    _guard(_video_estimate(spec))
    body: dict = {"model": model, "prompt": spec["prompt"], **spec["params"]}
    if spec.get("first_frame"):
        frame = _latest_file(spec["first_frame"])
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(
            frame.suffix.lower()
        )
        if mime is None:
            sys.exit(f"Unsupported first-frame type {frame.suffix!r}; use PNG, JPEG or WebP.")
        data_url = f"data:{mime};base64,{base64.b64encode(frame.read_bytes()).decode()}"
        body["frame_images"] = [{"type": "image_url", "image_url": {"url": data_url}, "frame_type": "first_frame"}]
    # Logged before submitting: if the response is lost (timeout), the job may still be running and
    # billed. Check the OpenRouter activity page before re-running rather than paying twice.
    _record(prompt_id, {"kind": "video-submit-attempt", "model": model, "submitted": _now()})
    submitted = _request("POST", f"{API}/videos", body)
    job_id = submitted["id"]
    _record(
        prompt_id,
        {
            "kind": "video",
            "model": model,
            "params": spec["params"],
            "first_frame": spec.get("first_frame"),
            "job_id": job_id,
            "submitted": _now(),
            "status": submitted.get("status"),
        },
    )
    print(f"Submitted video job {job_id}")
    poll_video(prompt_id, job_id)


def poll_video(prompt_id: str, job_id: str) -> None:
    deadline = time.monotonic() + CONFIG["video_poll_ceiling_s"]
    status: dict = {}
    while time.monotonic() < deadline:
        status = _request("GET", f"{API}/videos/{job_id}")
        state = status.get("status")
        print(f"{_now()}  job {job_id}: {state}")
        if state in {"completed", "failed", "cancelled", "expired"}:
            break
        time.sleep(CONFIG["video_poll_interval_s"])
    files = []
    if status.get("status") == "completed":
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for index, url in enumerate(status.get("unsigned_urls", [])):
            target = OUT_DIR / f"{prompt_id}-{job_id}-{index}.mp4"
            target.write_bytes(_request("GET", url, raw=True))
            files.append(str(target.relative_to(ROOT)))
    cost = (status.get("usage") or {}).get("cost")
    _record(
        prompt_id,
        {
            "kind": "video-result",
            "job_id": job_id,
            "status": status.get("status"),
            "finished": _now(),
            "files": files,
            "reported_cost_usd": cost,
            "error": status.get("error"),
        },
    )
    print(f"Status {status.get('status')}  |  files {files}  |  reported cost: ${cost}")


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in {"image", "video", "resume", "resubmit"}:
        sys.exit(__doc__)
    action, prompt_id = sys.argv[1], sys.argv[2]
    if prompt_id not in PROMPTS:
        sys.exit(f"Unknown prompt id {prompt_id!r}")
    if action == "image":
        generate_image(prompt_id)
    elif action in {"video", "resubmit"}:
        generate_video(prompt_id, allow_resubmit=action == "resubmit")
    else:
        record = JOBS_DIR / f"{prompt_id}.json"
        history = json.loads(record.read_text(encoding="utf-8")) if record.exists() else []
        job_id = next((r["job_id"] for r in reversed(history) if r.get("kind") == "video"), None)
        if job_id is None:
            sys.exit(f"No submitted video job recorded for {prompt_id!r}.")
        poll_video(prompt_id, job_id)


if __name__ == "__main__":
    main()
