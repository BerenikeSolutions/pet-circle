"""
PetCircle — Unified AI Client Adapter

Provides get_ai_client() and get_sync_ai_client() that return Anthropic-API-compatible
objects when AI_PROVIDER='openai'. This lets all services call client.messages.create(...)
and access response.content[0].text without any changes to response-parsing code.

Routing:
    AI_PROVIDER='claude'  → returns native AsyncAnthropic / Anthropic clients
    AI_PROVIDER='openai'  → returns _OpenAIAdapter / _SyncOpenAIAdapter which translate
                             Anthropic-style calls into OpenAI ChatCompletion calls and
                             wrap results in Anthropic-shaped response objects.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-initialised client singletons
# ---------------------------------------------------------------------------

_async_anthropic_client = None
_async_openai_client = None
_sync_openai_client = None
_sync_anthropic_client = None

_async_openai_adapter: _OpenAIAdapter | None = None
_sync_openai_adapter: _SyncOpenAIAdapter | None = None


# ---------------------------------------------------------------------------
# Anthropic-shaped response shims
# ---------------------------------------------------------------------------

class _TextContent:
    """Mimics Anthropic TextBlock: response.content[0].text"""
    __slots__ = ("text",)

    def __init__(self, text: str) -> None:
        self.text = text


class _ToolUseContent:
    """Mimics Anthropic ToolUseBlock: response.content[0].input (a dict)"""
    __slots__ = ("input",)

    def __init__(self, input_dict: dict) -> None:
        self.input = input_dict


class _FakeResponse:
    """Anthropic-shaped response wrapper for OpenAI replies."""
    __slots__ = ("content", "stop_reason")

    def __init__(self, content_items: list, stop_reason: str = "end_turn") -> None:
        self.content = content_items
        self.stop_reason = stop_reason


# ---------------------------------------------------------------------------
# OpenAI image block translation helper
# ---------------------------------------------------------------------------

def _translate_messages_to_openai(
    messages: list[dict], system: str | None = None
) -> list[dict]:
    """
    Convert Anthropic-style messages (possibly with image content blocks) to
    OpenAI ChatCompletion messages format.

    Anthropic image block:
        {"type": "image", "source": {"type": "base64", "media_type": "...", "data": "..."}}
    OpenAI image block:
        {"type": "image_url", "image_url": {"url": "data:...;base64,...", "detail": "high"}}
    """
    oai_messages: list[dict] = []
    if system:
        oai_messages.append({"role": "system", "content": system})

    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            # Multi-part content (vision or mixed)
            oai_content: list[dict] = []
            for part in content:
                ptype = part.get("type")
                if ptype == "text":
                    oai_content.append({"type": "text", "text": part["text"]})
                elif ptype == "image":
                    src = part.get("source", {})
                    if src.get("type") == "base64":
                        data_url = f"data:{src['media_type']};base64,{src['data']}"
                        oai_content.append({
                            "type": "image_url",
                            "image_url": {"url": data_url, "detail": "high"},
                        })
            oai_messages.append({"role": msg["role"], "content": oai_content})
        else:
            oai_messages.append(msg)

    return oai_messages


def _anthropic_tools_to_openai(tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool schema list to OpenAI function definitions."""
    oai_tools = []
    for t in tools:
        oai_tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            },
        })
    return oai_tools


def _anthropic_tool_choice_to_openai(tool_choice: dict | None) -> Any:
    """Convert Anthropic tool_choice dict to OpenAI format."""
    if not tool_choice:
        return "auto"
    if tool_choice.get("type") == "tool":
        return {"type": "function", "function": {"name": tool_choice["name"]}}
    return "auto"


# ---------------------------------------------------------------------------
# Async adapter — routes client.messages.create() to OpenAI async
# ---------------------------------------------------------------------------

class _AsyncMessagesProxy:
    """
    Async proxy for client.messages.  Accepts Anthropic-style kwargs and
    routes to the OpenAI async ChatCompletion API.
    """

    async def create(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 1500,
        system: str | None = None,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
        **_kwargs: Any,
    ) -> _FakeResponse:
        client = _get_async_openai_client()
        oai_messages = _translate_messages_to_openai(messages, system)

        if tools:
            oai_tools = _anthropic_tools_to_openai(tools)
            oai_tc = _anthropic_tool_choice_to_openai(tool_choice)

            response = await client.chat.completions.create(
                model=model,
                messages=oai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=oai_tools,
                tool_choice=oai_tc,
            )
            tool_call = response.choices[0].message.tool_calls[0]
            input_dict = json.loads(tool_call.function.arguments)
            stop_reason = response.choices[0].finish_reason or "end_turn"
            return _FakeResponse([_ToolUseContent(input_dict)], stop_reason=stop_reason)

        response = await client.chat.completions.create(
            model=model,
            messages=oai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content or ""
        stop_reason = response.choices[0].finish_reason or "end_turn"
        return _FakeResponse([_TextContent(text)], stop_reason=stop_reason)


class _OpenAIAdapter:
    """
    Drop-in async replacement for AsyncAnthropic.
    Exposes the `.messages` attribute so `client.messages.create(...)` works unchanged.
    """

    def __init__(self) -> None:
        self.messages = _AsyncMessagesProxy()


# ---------------------------------------------------------------------------
# Sync adapter — routes client.messages.create() to OpenAI sync
# ---------------------------------------------------------------------------

class _SyncMessagesProxy:
    """Sync proxy for client.messages used by nudge_scheduler and similar."""

    def create(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 1500,
        system: str | None = None,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
        **_kwargs: Any,
    ) -> _FakeResponse:
        client = _get_sync_openai_client()
        oai_messages = _translate_messages_to_openai(messages, system)

        if tools:
            oai_tools = _anthropic_tools_to_openai(tools)
            oai_tc = _anthropic_tool_choice_to_openai(tool_choice)

            response = client.chat.completions.create(
                model=model,
                messages=oai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=oai_tools,
                tool_choice=oai_tc,
            )
            tool_call = response.choices[0].message.tool_calls[0]
            input_dict = json.loads(tool_call.function.arguments)
            stop_reason = response.choices[0].finish_reason or "end_turn"
            return _FakeResponse([_ToolUseContent(input_dict)], stop_reason=stop_reason)

        response = client.chat.completions.create(
            model=model,
            messages=oai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content or ""
        stop_reason = response.choices[0].finish_reason or "end_turn"
        return _FakeResponse([_TextContent(text)], stop_reason=stop_reason)


class _SyncOpenAIAdapter:
    """Drop-in sync replacement for anthropic.Anthropic."""

    def __init__(self) -> None:
        self.messages = _SyncMessagesProxy()


# ---------------------------------------------------------------------------
# Internal client constructors
# ---------------------------------------------------------------------------

def _get_async_openai_client():
    global _async_openai_client
    if _async_openai_client is None:
        from openai import AsyncOpenAI  # noqa: PLC0415
        from app.config import settings  # noqa: PLC0415
        _async_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _async_openai_client


def _get_sync_openai_client():
    global _sync_openai_client
    if _sync_openai_client is None:
        from openai import OpenAI  # noqa: PLC0415
        from app.config import settings  # noqa: PLC0415
        _sync_openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _sync_openai_client


def _get_async_anthropic_client():
    global _async_anthropic_client
    if _async_anthropic_client is None:
        from anthropic import AsyncAnthropic  # noqa: PLC0415
        from app.config import settings  # noqa: PLC0415
        _async_anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _async_anthropic_client


def _get_sync_anthropic_client():
    global _sync_anthropic_client
    if _sync_anthropic_client is None:
        import anthropic  # noqa: PLC0415
        from app.config import settings  # noqa: PLC0415
        _sync_anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _sync_anthropic_client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_ai_client():
    """
    Return the appropriate async AI client based on the AI_PROVIDER setting.

    - AI_PROVIDER='claude' → AsyncAnthropic (native)
    - AI_PROVIDER='openai' → _OpenAIAdapter (Anthropic-compatible interface over OpenAI)

    Both expose `client.messages.create(...)` and return responses with `.content[0].text`
    so no changes are needed in service response-parsing code.
    """
    from app.core.constants import AI_PROVIDER  # noqa: PLC0415

    if AI_PROVIDER == "openai":
        global _async_openai_adapter
        if _async_openai_adapter is None:
            _async_openai_adapter = _OpenAIAdapter()
        return _async_openai_adapter

    return _get_async_anthropic_client()


def get_sync_ai_client():
    """
    Return the appropriate sync AI client based on the AI_PROVIDER setting.

    Used by services that call the AI API synchronously (nudge_scheduler,
    medicine_recurrence_service, etc.).

    - AI_PROVIDER='claude' → anthropic.Anthropic (native sync)
    - AI_PROVIDER='openai' → _SyncOpenAIAdapter (Anthropic-compatible interface over OpenAI)
    """
    from app.core.constants import AI_PROVIDER  # noqa: PLC0415

    if AI_PROVIDER == "openai":
        global _sync_openai_adapter
        if _sync_openai_adapter is None:
            _sync_openai_adapter = _SyncOpenAIAdapter()
        return _sync_openai_adapter

    return _get_sync_anthropic_client()
