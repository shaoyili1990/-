"""
Anthropic Claude 适配器
处理Claude特有的: system分离、图像格式、工具格式
"""

import json
from typing import List, Dict, Optional, Generator
from .base import LLMProvider, LLMResponse
from .registry import register_provider


class AnthropicProvider(LLMProvider):
    """Anthropic Claude适配器"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = config.get("base_url", "https://api.anthropic.com/v1").rstrip("/")
        self.api_version = "2023-06-01"

    def generate(self, messages: List[Dict], **kwargs) -> LLMResponse:
        import httpx

        # 分离system消息
        system_prompt, api_messages = self._split_system(messages)

        # 转换消息格式为Anthropic格式
        anthropic_messages = self._to_anthropic_messages(api_messages)

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
        }

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return LLMResponse(
                content=f"[API Error: Anthropic] {e}",
                provider="anthropic",
                model=self.model,
            )

        # 解析响应
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            provider="anthropic",
            usage={
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
            finish_reason=data.get("stop_reason", ""),
            raw=data,
        )

    def stream(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        import httpx

        system_prompt, api_messages = self._split_system(messages)
        anthropic_messages = self._to_anthropic_messages(api_messages)

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
        }

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            with httpx.Client(timeout=300.0) as client:
                with client.stream("POST", f"{self.base_url}/messages",
                                   headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line or line.startswith("event:"):
                            continue
                        if line.startswith("data: "):
                            try:
                                chunk = json.loads(line[6:])
                                if chunk.get("type") == "content_block_delta":
                                    delta = chunk.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        yield delta.get("text", "")
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            yield f"[Stream Error: Anthropic] {e}"

    def _split_system(self, messages: List[Dict]) -> tuple:
        """分离system消息(Claude特殊处理)"""
        system_parts = []
        other_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(c.get("text", "") for c in content if c.get("type") == "text")
                system_parts.append(content)
            else:
                other_messages.append(msg)
        return "\n".join(system_parts), other_messages

    def _to_anthropic_messages(self, messages: List[Dict]) -> List[Dict]:
        """将通用消息格式转为Anthropic格式"""
        anthropic_msgs = []
        for msg in messages:
            content = msg.get("content", "")
            role = "assistant" if msg["role"] == "assistant" else "user"

            if isinstance(content, str):
                anthropic_msgs.append({"role": role, "content": content})
            elif isinstance(content, list):
                # 多模态内容转换
                parts = []
                for part in content:
                    if part.get("type") == "text":
                        parts.append({"type": "text", "text": part["text"]})
                    elif part.get("type") == "image":
                        img = self._convert_image(part)
                        if img:
                            parts.append(img)
                anthropic_msgs.append({"role": role, "content": parts})

        return anthropic_msgs

    def _convert_image(self, part: Dict) -> Optional[Dict]:
        """转换图像格式为Anthropic格式"""
        image_url = part.get("image_url", {})
        url = image_url.get("url", "")
        if url and url.startswith("data:"):
            # data:image/{mime};base64,{data}
            try:
                mime = url.split(";")[0].split(":")[1]
                data = url.split(",")[1]
                return {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime,
                        "data": data,
                    }
                }
            except:
                pass
        return None


register_provider("anthropic", AnthropicProvider)
