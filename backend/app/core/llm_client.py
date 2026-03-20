"""Unified LLM client — supports OpenAI-compatible and Gemini APIs with streaming."""

import httpx
import json
from typing import AsyncIterator
from app.config import get_settings

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

    async def chat(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        """Send chat messages to LLM. Returns full text or async stream of chunks."""
        if self.settings.openai_api_key:
            if stream:
                return self._stream_openai(messages)
            return await self._call_openai(messages)
        elif self.settings.gemini_api_key:
            if stream:
                return self._stream_gemini(messages)
            return await self._call_gemini(messages)
        else:
            return self._fallback_response(messages)

    async def _call_openai(self, messages: list[dict]) -> str:
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                json={
                    "model": "gpt-4o",
                    "messages": full_messages,
                    "max_tokens": 2000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _stream_openai(self, messages: list[dict]) -> AsyncIterator[str]:
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                json={
                    "model": "gpt-4o",
                    "messages": full_messages,
                    "max_tokens": 2000,
                    "stream": True,
                },
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass

    async def _call_gemini(self, messages: list[dict]) -> str:
        contents = self._to_gemini_format(messages)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                params={"key": self.settings.gemini_api_key},
                json={
                    "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                    "contents": contents,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    async def _stream_gemini(self, messages: list[dict]) -> AsyncIterator[str]:
        contents = self._to_gemini_format(messages)
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent",
                params={"key": self.settings.gemini_api_key, "alt": "sse"},
                json={
                    "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                    "contents": contents,
                },
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
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        return contents

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> tuple[dict | None, str]:
        """Call LLM with tool definitions.

        Returns (intent_dict, response_text). Both can be non-empty when the LLM
        provides a text reply AND calls a tool in the same turn.
        If intent extraction fails, returns (None, "") so the caller can fall back
        to a regular llm.chat() call.
        """
        if not tools:
            return None, ""
        try:
            if self.settings.openai_api_key:
                return await self._call_openai_tools(messages, tools)
            elif self.settings.gemini_api_key:
                return await self._call_gemini_tools(messages, tools)
        except Exception:
            pass
        return None, ""

    async def _call_openai_tools(
        self, messages: list[dict], tools: list[dict]
    ) -> tuple[dict | None, str]:
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                json={
                    "model": "gpt-4o",
                    "messages": full_messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "max_tokens": 1000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls", [])
            intent = None
            if tool_calls:
                args_str = tool_calls[0].get("function", {}).get("arguments", "{}")
                try:
                    intent = json.loads(args_str)
                except json.JSONDecodeError:
                    pass
        return intent, content

    async def _call_gemini_tools(
        self, messages: list[dict], tools: list[dict]
    ) -> tuple[dict | None, str]:
        """Gemini function calling — convert OpenAI tool schema to Gemini format."""
        contents = self._to_gemini_format(messages)
        fn_decls = []
        for t in tools:
            fn = t.get("function", {})
            fn_decls.append({
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
            })
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                params={"key": self.settings.gemini_api_key},
                json={
                    "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                    "contents": contents,
                    "tools": [{"function_declarations": fn_decls}],
                    "tool_config": {"function_calling_config": {"mode": "AUTO"}},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            intent = None
            text_parts = []
            for part in parts:
                if "functionCall" in part:
                    intent = part["functionCall"].get("args", {})
                elif "text" in part:
                    text_parts.append(part["text"])
        return intent, "".join(text_parts)

    def _fallback_response(self, messages: list[dict]) -> str:
        last = messages[-1]["content"] if messages else ""
        return (
            f"我理解你的想法：「{last}」\n\n"
            "要启用完整的 AI 对话，请配置 API Key：\n"
            "- 设置 `OPENAI_API_KEY` 使用 GPT-4o\n"
            "- 或设置 `GEMINI_API_KEY` 使用 Gemini 2.5 Flash\n\n"
            "你可以通过右侧面板手动设置风格并直接生成内容。"
        )
