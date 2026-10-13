"""Only a local Ollama model may draft content; no tools, URLs or selectors in model output."""

from __future__ import annotations

import json
from typing import Any

import httpx

from fw_agent.contracts import OLLAMA_CHAT_PATH, OLLAMA_SHOW_PATH, OLLAMA_TAGS_PATH, Draft, loopback_url
from fw_core.settings import AgentSettings


class LocalModel:
    def __init__(self, settings: AgentSettings, system_prompt: str) -> None:
        self.settings = settings
        self.system_prompt = system_prompt
        loopback_url(settings.model_url)
        if "cloud" in settings.model_id.lower():
            raise ValueError("cloud models are disabled")

    async def _request(
        self, client: httpx.AsyncClient, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        async with client.stream(method, self.settings.model_url.rstrip("/") + path, json=payload) as response:
            response.raise_for_status()
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > self.settings.model_max_bytes:
                    raise ValueError("local model response exceeded configured budget")
            result: dict[str, Any] = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("local model response must be an object")
            return result

    async def draft(self, prompt: str, request: str, source: str) -> Draft:
        async with httpx.AsyncClient(
            timeout=self.settings.model_timeout_s, follow_redirects=False, trust_env=False
        ) as client:
            tags = await self._request(client, "GET", OLLAMA_TAGS_PATH)
            local = [m for m in tags.get("models", []) if m.get("name") == self.settings.model_id]
            if not local or local[0].get("remote_host"):
                raise ValueError("configured model must already be installed locally")
            info = await self._request(client, "POST", OLLAMA_SHOW_PATH, {"model": self.settings.model_id})
            if info.get("remote_host") or info.get("remote_model"):
                raise ValueError("remote-backed Ollama models are disabled")
            result = await self._request(
                client,
                "POST",
                OLLAMA_CHAT_PATH,
                {
                    "model": self.settings.model_id,
                    "stream": False,
                    "think": False,
                    "keep_alive": self.settings.model_keep_alive_s,
                    "options": {"num_predict": self.settings.model_max_tokens},
                    "format": Draft.model_json_schema(),
                    "messages": [
                        {"role": "system", "content": self.system_prompt + "\n" + prompt},
                        {"role": "user", "content": json.dumps({"request": request, "untrusted_source_text": source})},
                    ],
                },
            )
            draft = Draft.model_validate_json(result["message"]["content"])
            if len(draft.body) > self.settings.max_content_chars:
                raise ValueError("draft exceeded configured content budget")
            return draft
