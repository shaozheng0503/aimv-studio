"""Unified LLM client — supports OpenAI-compatible and Gemini APIs with streaming.

Backend priority:
  chat / stream      : Qwen  >  OpenAI  >  Gemini  >  fallback
  chat_with_tools    : Qwen-reasoning  >  Qwen  >  OpenAI  >  Gemini

Qwen and OpenAI both speak the OpenAI-compatible wire format, so they share a
single set of _call_compat / _stream_compat / _call_compat_tools helpers.
Only the base URL, auth headers, model name, and extra-body params differ.
"""

import httpx
import json
import os
import re
from typing import AsyncIterator
from app.config import get_settings

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

# Gemini API base — shared with verifier.py
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_BASE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}"


def _strip_think(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from model output (no-op for non-thinking models)."""
    return _THINK_RE.sub("", text).strip()


# Module-level shared client — connection pool is reused across all LLM calls.
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient()
    return _http_client


async def close_http_client() -> None:
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


SYSTEM_PROMPT = """你是 AIMV 的 AI 导演，帮助用户规划和创作专业音乐视频。

你的能力：
- 理解用户的创意愿景（情绪、风格、故事、目标受众）
- 推荐视觉风格：韩娱、国风古典、赛博朋克、复古迪斯科、独立电影、都市甜酷、幻想童话
- 推荐视频模型：Seedance 2.0（舞蹈）、Veo 3.1（电影感）、Grok Video（风格化）、Wan 2.2（本地/定制）
- 推荐音乐模型：ACEStep 1.5（开源器乐）、Suno（人声+歌词）、Google Lyria（高保真）
- 设计包含逐镜描述的分镜方案
- 创建角色档案以保持视觉一致性

沟通风格：
- 简洁但富有创意
- 用户意图模糊时主动提问
- 主动建议风格组合
- 用户准备好后，告知他们点击「生成方案」创建完整制作方案
- 用用户所用的语言回复（中文或英文）"""


class LLMClient:
    def __init__(self):
        self.settings = get_settings()

    # ── backend capability checks ─────────────────────────────────────────────

    def _has_compat(self) -> bool:
        """True when an OpenAI-compatible backend (Qwen or OpenAI) is available."""
        return bool(self.settings.qwen_base_url or self.settings.openai_api_key)

    def _has_gemini(self) -> bool:
        s = self.settings
        return bool(
            s.gemini_api_key
            or (s.google_sa_path and os.path.isfile(s.google_sa_path))
        )

    def _compat_params(self, reasoning: bool = False) -> tuple[str, str, dict, dict]:
        """Return (base_url, model, headers, extra_body) for the active OpenAI-compatible backend.

        When reasoning=True and a reasoning endpoint is configured, it is preferred
        (used for tool calls where structured output quality matters most).
        """
        s = self.settings
        if reasoning and s.qwen_reasoning_base_url:
            return s.qwen_reasoning_base_url, s.qwen_reasoning_model, {}, {}
        if s.qwen_base_url:
            # Disable Qwen3 chain-of-thought — reasoning goes to its own `reasoning` field
            return s.qwen_base_url, s.qwen_model, {}, {"chat_template_kwargs": {"enable_thinking": False}}
        # OpenAI
        return (
            "https://api.openai.com",
            "gpt-4o",
            {"Authorization": f"Bearer {s.openai_api_key}"},
            {},
        )

    # ── public API ────────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        stream: bool = False,
        system: str | None = None,
    ) -> str | AsyncIterator[str]:
        """Send chat messages to LLM. Returns full text or async stream of chunks."""
        if self._has_compat():
            if stream:
                return self._stream_compat(messages, system=system)
            return await self._call_compat(messages, system=system)
        if self._has_gemini():
            if stream:
                return self._stream_gemini(messages, system=system)
            return await self._call_gemini(messages, system=system)
        return self._fallback_response(messages)

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> tuple[dict | None, str]:
        """Call LLM with tool definitions for intent extraction.

        Returns (intent_dict, response_text).
        Returns (None, "") on failure so callers can fall back to plain chat.
        """
        if not tools:
            return None, ""
        try:
            if self._has_compat():
                reasoning = bool(self.settings.qwen_reasoning_base_url)
                return await self._call_compat_tools(messages, tools, reasoning=reasoning)
            if self._has_gemini():
                return await self._call_gemini_tools(messages, tools)
        except Exception:
            pass
        return None, ""

    # ── OpenAI-compatible backend (Qwen + OpenAI) ────────────────────────────

    def _compat_request(
        self,
        messages: list[dict],
        *,
        system: str | None = None,
        reasoning: bool = False,
        max_tokens: int = 2000,
        stream: bool = False,
        tools: list[dict] | None = None,
    ) -> tuple[str, dict, dict]:
        """Build (url, headers, json_body) for an OpenAI-compatible request."""
        base, model, headers, extra = self._compat_params(reasoning)
        body: dict = {
            "model": model,
            "messages": [{"role": "system", "content": system or SYSTEM_PROMPT}] + messages,
            "max_tokens": max_tokens,
            **extra,
        }
        if stream:
            body["stream"] = True
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        return f"{base.rstrip('/')}/v1/chat/completions", headers, body

    async def _call_compat(
        self,
        messages: list[dict],
        system: str | None = None,
        reasoning: bool = False,
    ) -> str:
        max_tokens = 800 if (reasoning and self.settings.qwen_reasoning_base_url) else 2000
        url, headers, body = self._compat_request(
            messages, system=system, reasoning=reasoning, max_tokens=max_tokens,
        )
        resp = await _get_http_client().post(url, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        return _strip_think(resp.json()["choices"][0]["message"]["content"])

    async def _stream_compat(
        self,
        messages: list[dict],
        system: str | None = None,
        reasoning: bool = False,
    ) -> AsyncIterator[str]:
        url, headers, body = self._compat_request(
            messages, system=system, reasoning=reasoning, stream=True,
        )
        in_think = False
        async with _get_http_client().stream(
            "POST", url, headers=headers, json=body, timeout=120,
        ) as resp:
            buffer = ""
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {}).get("content", "") or ""
                        if not delta:
                            continue
                        buffer += delta
                        # Strip <think>...</think> blocks on-the-fly (state machine)
                        while True:
                            if in_think:
                                end = buffer.find("</think>")
                                if end == -1:
                                    buffer = ""
                                    break
                                buffer = buffer[end + 8:]
                                in_think = False
                            else:
                                start = buffer.find("<think>")
                                if start == -1:
                                    yield buffer
                                    buffer = ""
                                    break
                                if start > 0:
                                    yield buffer[:start]
                                buffer = buffer[start + 7:]
                                in_think = True
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass

    async def _call_compat_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        reasoning: bool = False,
    ) -> tuple[dict | None, str]:
        max_tokens = 600 if (reasoning and self.settings.qwen_reasoning_base_url) else 1000
        url, headers, body = self._compat_request(
            messages, reasoning=reasoning, max_tokens=max_tokens, tools=tools,
        )
        resp = await _get_http_client().post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        message = resp.json().get("choices", [{}])[0].get("message", {})
        content = _strip_think(message.get("content") or "")
        intent = None
        if message.get("tool_calls"):
            args_str = message["tool_calls"][0].get("function", {}).get("arguments", "{}")
            try:
                intent = json.loads(args_str)
            except json.JSONDecodeError:
                pass
        return intent, content

    # ── Gemini backend ────────────────────────────────────────────────────────

    def _gemini_auth(self) -> tuple[dict, dict]:
        """Return (headers, params) for Gemini API auth.

        Prefers gemini_api_key; falls back to SA Bearer token.
        """
        if self.settings.gemini_api_key:
            return {}, {"key": self.settings.gemini_api_key}
        if self.settings.google_sa_path:
            from app.adapters.google_image import _get_access_token
            token, _ = _get_access_token(self.settings.google_sa_path)
            return {"Authorization": f"Bearer {token}"}, {}
        return {}, {}

    async def _call_gemini(self, messages: list[dict], system: str | None = None) -> str:
        sys = system or SYSTEM_PROMPT
        headers, params = self._gemini_auth()
        resp = await _get_http_client().post(
            f"{GEMINI_BASE_URL}:generateContent",
            headers=headers,
            params=params,
            json={"system_instruction": {"parts": [{"text": sys}]}, "contents": self._to_gemini_format(messages)},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    async def _stream_gemini(self, messages: list[dict], system: str | None = None) -> AsyncIterator[str]:
        sys = system or SYSTEM_PROMPT
        headers, params = self._gemini_auth()
        async with _get_http_client().stream(
            "POST",
            f"{GEMINI_BASE_URL}:streamGenerateContent",
            headers=headers,
            params={**params, "alt": "sse"},
            json={"system_instruction": {"parts": [{"text": sys}]}, "contents": self._to_gemini_format(messages)},
            timeout=120,
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        text = chunk["candidates"][0]["content"]["parts"][0].get("text", "")
                        if text:
                            yield text
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass

    def _to_gemini_format(self, messages: list[dict]) -> list[dict]:
        return [
            {"role": "model" if m["role"] == "assistant" else "user",
             "parts": [{"text": m["content"]}]}
            for m in messages
        ]

    async def _call_gemini_tools(
        self, messages: list[dict], tools: list[dict]
    ) -> tuple[dict | None, str]:
        """Gemini function calling — converts OpenAI tool schema to Gemini format."""
        fn_decls = [
            {
                "name": t.get("function", {}).get("name"),
                "description": t.get("function", {}).get("description", ""),
                "parameters": t.get("function", {}).get("parameters", {}),
            }
            for t in tools
        ]
        headers, params = self._gemini_auth()
        resp = await _get_http_client().post(
            f"{GEMINI_BASE_URL}:generateContent",
            headers=headers,
            params=params,
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": self._to_gemini_format(messages),
                "tools": [{"function_declarations": fn_decls}],
                "tool_config": {"function_calling_config": {"mode": "AUTO"}},
            },
            timeout=30,
        )
        resp.raise_for_status()
        parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        intent = None
        text_parts = []
        for part in parts:
            if "functionCall" in part:
                intent = part["functionCall"].get("args", {})
            elif "text" in part:
                text_parts.append(part["text"])
        return intent, "".join(text_parts)

    # ── fallback ──────────────────────────────────────────────────────────────

    def _fallback_response(self, messages: list[dict]) -> str:
        last = messages[-1]["content"] if messages else ""
        return (
            f"我理解你的想法：「{last}」\n\n"
            "要启用完整的 AI 对话，请在 `.env` 中配置以下任意一项：\n"
            "- `QWEN_BASE_URL` — 使用本地/自托管 Qwen 模型（无需 API Key）\n"
            "- `OPENAI_API_KEY` — 使用 GPT-4o\n"
            "- `GEMINI_API_KEY` — 使用 Gemini 2.5 Flash\n\n"
            "你可以通过右侧面板手动设置风格并直接生成内容。"
        )


# Module-level singleton — avoids creating a new LLMClient (and re-reading settings)
# on every request. Import get_llm() wherever an LLMClient is needed.
_llm_instance: LLMClient | None = None


def get_llm() -> LLMClient:
    """Return the process-wide LLMClient singleton."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMClient()
    return _llm_instance
