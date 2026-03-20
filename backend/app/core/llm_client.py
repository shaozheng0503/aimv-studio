"""Unified LLM client — supports OpenAI-compatible and Gemini APIs with streaming."""

import httpx
import json
from typing import AsyncIterator
from app.config import get_settings

SYSTEM_PROMPT = """You are the AI Director of AIMV, an AI Music Video creation platform.
You help users plan and create professional music videos.

Your capabilities:
- Understand the user's creative vision (mood, style, story, target audience)
- Recommend visual styles: K-Pop, Chinese Classical, Cyberpunk, Retro Disco, Indie Film, Urban Cool, Fantasy
- Recommend video models: Seedance 2.0 (dance), Veo 3.1 (cinematic), Grok Video (stylized), Wan 2.2 (local/custom)
- Recommend music models: ACEStep 1.5 (open-source instrumental), Suno (vocals+lyrics), Google Lyria (high-fidelity)
- Design storyboards with shot-by-shot descriptions
- Create character profiles for visual consistency

Communication style:
- Be concise but creative
- Ask clarifying questions when the user's intent is vague
- Proactively suggest style combinations
- When the user is ready, tell them to click "Generate Plan" to create the full production plan
- Respond in the same language the user uses (Chinese or English)"""


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

    def _fallback_response(self, messages: list[dict]) -> str:
        last = messages[-1]["content"] if messages else ""
        return (
            f"I understand your request: \"{last}\"\n\n"
            "To enable full AI conversation, please configure an API key:\n"
            "- Set `OPENAI_API_KEY` for GPT-4o\n"
            "- Or set `GEMINI_API_KEY` for Gemini 2.5 Flash\n\n"
            "Meanwhile, you can still set styles and generate content using the sidebar controls."
        )
