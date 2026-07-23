"""
OpenAI兼容适配器
支持: OpenAI / DeepSeek / OpenRouter / 任何OpenAI兼容API

消息格式:
  system: {"role": "system", "content": "..."}
  user:   {"role": "user", "content": "..."}
  多模态: {"role": "user", "content": [{"type":"text","text":"..."}, {"type":"image_url","image_url":{"url":"data:image;base64,..."}}]}
"""

import json
from typing import List, Dict, Optional, Generator
from .base import LLMProvider, LLMResponse
from .registry import register_provider


class OpenAIProvider(LLMProvider):
    """OpenAI兼容API适配器"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = config.get("base_url", "https://api.openai.com/v1").rstrip("/")

    def generate(self, messages: List[Dict], **kwargs) -> LLMResponse:
        """同步调用API"""
        import httpx
        headers = self._build_headers()
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": self._prepare_messages(messages),
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": False,
        }
        # 可选参数
        for key in ("top_p", "stop", "presence_penalty", "frequency_penalty"):
            if key in kwargs:
                payload[key] = kwargs[key]

        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return LLMResponse(
                content=f"[API Error: {self.name}] {e}",
                provider=self.name,
                model=self.model,
            )

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""

        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            provider=self.name,
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            finish_reason=choice.get("finish_reason", ""),
            raw=data,
        )

    def stream(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """流式调用"""
        import httpx
        headers = self._build_headers()
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": self._prepare_messages(messages),
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": True,
        }

        try:
            with httpx.Client(timeout=300.0) as client:
                with client.stream("POST", f"{self.base_url}/chat/completions",
                                   headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line or line.startswith(":") or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            try:
                                chunk = json.loads(line[6:])
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            yield f"[Stream Error: {self.name}] {e}"

    def _build_headers(self) -> Dict:
        """构建请求头 - 支持不同厂商的认证方式"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            if self.name == "anthropic":
                headers["x-api-key"] = self.api_key
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"
        # OpenRouter额外头
        if self.name == "openrouter":
            headers["HTTP-Referer"] = "https://monkey-harness.local"
            headers["X-Title"] = "Hermes Agent Universal"
        return headers


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek适配器 (OpenAI兼容)"""
    def __init__(self, config: Dict):
        config.setdefault("base_url", "https://api.deepseek.com/v1")
        config.setdefault("model", "deepseek-v4-flash")
        super().__init__(config)
        self.name = "deepseek"


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter适配器"""
    def __init__(self, config: Dict):
        config.setdefault("base_url", "https://openrouter.ai/api/v1")
        super().__init__(config)
        self.name = "openrouter"


# 注册提供者
register_provider("openai", OpenAIProvider)
register_provider("deepseek", DeepSeekProvider)
register_provider("openrouter", OpenRouterProvider)
