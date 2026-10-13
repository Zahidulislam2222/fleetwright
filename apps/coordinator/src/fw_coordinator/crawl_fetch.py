"""Disposable fetch process: the parent can terminate DNS/TLS/slow-drip I/O at its total deadline.

URLs and response bytes travel only through private standard pipes, never process arguments or
logs. The worker owns this child and always waits for its exit before retrying another request.
"""

from __future__ import annotations

import base64
import http.client
import json
import sys

from pydantic import BaseModel, ConfigDict, Field

from fw_coordinator.crawl_http import fetch


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    origin: str
    allow_private: bool
    timeout: float = Field(gt=0)
    limit: int = Field(ge=1)
    user_agent: str


def main() -> None:
    try:
        request = Request.model_validate_json(sys.stdin.buffer.read())
        response = fetch(**request.model_dump())
    except (OSError, ValueError, http.client.HTTPException):
        print('{"error":"destination_failure"}')
        raise SystemExit(1) from None
    print(
        json.dumps(
            {
                "status": response.status,
                "content_type": response.content_type,
                "body": base64.b64encode(response.body).decode(),
            }
        )
    )


if __name__ == "__main__":
    main()
