"""Thin wrapper around the Claude Messages API with server-side web search / fetch.

Handles:
- streaming (long research turns would otherwise hit SDK non-streaming limits)
- `pause_turn` continuation for long server-tool turns
- robust JSON extraction from the final answer, with one repair attempt
- usage accounting so the UI can show searches / tokens per run
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import anthropic

WEB_SEARCH_TOOL = "web_search_20250305"
WEB_FETCH_TOOL = "web_fetch_20250910"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    web_searches: int = 0
    web_fetches: int = 0
    calls: int = 0

    def add(self, u: Any) -> None:
        if u is None:
            return
        self.calls += 1
        self.input_tokens += getattr(u, "input_tokens", 0) or 0
        self.output_tokens += getattr(u, "output_tokens", 0) or 0
        self.cache_read_tokens += getattr(u, "cache_read_input_tokens", 0) or 0
        stu = getattr(u, "server_tool_use", None)
        if stu is not None:
            self.web_searches += getattr(stu, "web_search_requests", 0) or 0
            self.web_fetches += getattr(stu, "web_fetch_requests", 0) or 0

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Agent:
    api_key: str
    model: str = "claude-opus-5-5"
    system: str = ""
    usage: Usage = field(default_factory=Usage)
    log: Callable[[str], None] = lambda msg: None

    def __post_init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=self.api_key, max_retries=6, timeout=900)

    # ------------------------------------------------------------------ tools
    @staticmethod
    def research_tools(max_searches: int = 12, max_fetches: int = 8,
                       fetch_tokens: int = 40_000) -> list[dict]:
        return [
            {"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": max_searches},
            {
                "type": WEB_FETCH_TOOL,
                "name": "web_fetch",
                "max_uses": max_fetches,
                "max_content_tokens": fetch_tokens,
                "citations": {"enabled": False},
            },
        ]

    # ------------------------------------------------------------------- core
    def run(self, prompt: str, tools: list[dict] | None = None,
            max_tokens: int = 16_000, max_continuations: int = 6) -> str:
        """Run one agent turn (with server tools) and return the final text."""
        messages: list[dict] = [{"role": "user", "content": prompt}]
        system = [{"type": "text", "text": self.system,
                   "cache_control": {"type": "ephemeral"}}] if self.system else anthropic.NOT_GIVEN
        final_text_parts: list[str] = []

        for attempt in range(max_continuations + 1):
            kwargs: dict[str, Any] = dict(model=self.model, max_tokens=max_tokens,
                                          system=system, messages=messages)
            if tools:
                kwargs["tools"] = tools
            msg = self._stream_with_retry(kwargs)
            self.usage.add(msg.usage)

            for block in msg.content:
                btype = getattr(block, "type", "")
                if btype == "server_tool_use":
                    q = (getattr(block, "input", {}) or {})
                    self.log(f"{block.name}: {q.get('query') or q.get('url') or ''}")
                elif btype == "text":
                    final_text_parts.append(block.text)

            if msg.stop_reason == "pause_turn":
                # Send the paused assistant turn back unchanged to let it continue.
                messages = messages + [{"role": "assistant", "content": msg.content}]
                continue
            if msg.stop_reason == "max_tokens":
                self.log("warning: response hit max_tokens; output may be truncated")
            break

        return "".join(final_text_parts)

    def _stream_with_retry(self, kwargs: dict, tries: int = 3):
        last_err: Exception | None = None
        for i in range(tries):
            try:
                with self.client.messages.stream(**kwargs) as stream:
                    return stream.get_final_message()
            except (anthropic.APIConnectionError, anthropic.InternalServerError,
                    anthropic.RateLimitError) as e:  # SDK already retries; this is a backstop
                last_err = e
                wait = 20 * (i + 1)
                self.log(f"API error ({type(e).__name__}); retrying in {wait}s")
                time.sleep(wait)
        raise last_err  # type: ignore[misc]

    # ------------------------------------------------------------------- JSON
    def run_json(self, prompt: str, tools: list[dict] | None = None,
                 max_tokens: int = 16_000) -> Any:
        text = self.run(prompt, tools=tools, max_tokens=max_tokens)
        try:
            return extract_json(text)
        except ValueError:
            self.log("answer was not valid JSON; asking the model to repair it")
            repair = (
                "The text below was supposed to be a single valid JSON value but failed to parse. "
                "Return ONLY the corrected JSON (no prose, no code fences). Do not change any values; "
                "if it was truncated, close the open structures sensibly.\n\n" + text[-60_000:]
            )
            return extract_json(self.run(repair, tools=None, max_tokens=max_tokens))


def extract_json(text: str) -> Any:
    """Pull the JSON payload out of a model answer (fenced or bare)."""
    fences = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    candidates = [f for f in reversed(fences) if f.strip().startswith(("{", "["))]
    # bare JSON: outermost braces
    for opener, closer in (("{", "}"), ("[", "]")):
        s, e = text.find(opener), text.rfind(closer)
        if s != -1 and e > s:
            candidates.append(text[s:e + 1])
    for c in candidates:
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    raise ValueError("no JSON found in model output")
