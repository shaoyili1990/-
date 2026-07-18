"""
本地模型适配器
支持: Ollama (OpenAI兼容模式) / vLLM (OpenAI兼容) / 直接HTTP调用
"""

import json
from typing import List, Dict, Optional, Generator
from .base import LLMProvider, LLMResponse
from .registry import register_provider
from ..messages.content import load_image


class LocalProvider(LLMProvider):
    """本地模型适配器 (OpenAI兼容接口)"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.is_local = True
        self.base_url = config.get("base_url", "http://localhost:11434").rstrip("/")
        # Ollama原生API端点不同于OpenAI兼容
        self._use_ollama_native = "11434" in self.base_url and "v1" not in self.base_url

    def generate(self, messages: List[Dict], **kwargs) -> LLMResponse:
        if self._use_ollama_native:
            return self._ollama_native_generate(messages, kwargs)
        return self._openai_compat_generate(messages, kwargs)

    def _openai_compat_generate(self, messages: List[Dict], kwargs: Dict) -> LLMResponse:
        """OpenAI兼容模式 (vLLM / Ollama v1端点)"""
        import httpx
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": False,
        }

        try:
            with httpx.Client(timeout=300.0) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return LLMResponse(
                content=f"[Local Model Error] {e}",
                provider="local",
                model=self.model,
            )

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        return LLMResponse(
            content=message.get("content", ""),
            model=data.get("model", self.model),
            provider=f"local({self.model})",
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
            finish_reason=choice.get("finish_reason", ""),
        )

    def _ollama_native_generate(self, messages: List[Dict], kwargs: Dict) -> LLMResponse:
        """Ollama原生API模式"""
        import httpx

        # 转换消息格式到Ollama原生格式
        ollama_messages = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                # 提取文本部分
                texts = [p.get("text", "") for p in content if p.get("type") == "text"]
                content = "\n".join(texts)
            ollama_messages.append({
                "role": msg.get("role", "user"),
                "content": content,
            })

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
                "num_predict": kwargs.get("max_tokens", self.max_tokens),
            },
        }

        try:
            with httpx.Client(timeout=300.0) as client:
                resp = client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return LLMResponse(
                content=f"[Ollama Error] {e}",
                provider="ollama",
                model=self.model,
            )

        return LLMResponse(
            content=data.get("message", {}).get("content", ""),
            model=data.get("model", self.model),
            provider="ollama",
            usage={"input_tokens": 0, "output_tokens": 0},
        )

    def stream(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        import httpx
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        api_base = self.base_url
        if self._use_ollama_native:
            api_base = api_base.rstrip("/")
            url = f"{api_base}/api/chat"
            # 简化消息
            simple_msgs = []
            for msg in messages:
                c = msg.get("content", "")
                if isinstance(c, list):
                    c = " ".join(p.get("text", "") for p in c if p.get("type") == "text")
                simple_msgs.append({"role": msg.get("role"), "content": c})
            payload = {
                "model": kwargs.get("model", self.model),
                "messages": simple_msgs,
                "stream": True,
            }
        else:
            url = f"{api_base}/chat/completions"
            payload = {
                "model": kwargs.get("model", self.model),
                "messages": messages,
                "temperature": kwargs.get("temperature", self.temperature),
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "stream": True,
            }

        try:
            with httpx.Client(timeout=600.0) as client:
                with client.stream("POST", url, headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        if self._use_ollama_native:
                            try:
                                chunk = json.loads(line)
                                content = chunk.get("message", {}).get("content", "")
                                if content:
                                    yield content
                                if chunk.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue
                        else:
                            if line.startswith("data: "):
                                if line == "data: [DONE]":
                                    break
                                try:
                                    chunk = json.loads(line[6:])
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                                except json.JSONDecodeError:
                                    continue
        except Exception as e:
            yield f"[Stream Error] {e}"


class OllamaProvider(LocalProvider):
    """Ollama专属适配器"""
    def __init__(self, config: Dict):
        config.setdefault("base_url", "http://localhost:11434")
        config.setdefault("model", "llama3")
        super().__init__(config)
        self.name = "ollama"
        self._use_ollama_native = True


class VLLMProvider(LocalProvider):
    """vLLM适配器 (纯OpenAI兼容)"""
    def __init__(self, config: Dict):
        config.setdefault("base_url", "http://localhost:8000/v1")
        config.setdefault("model", "")
        super().__init__(config)
        self.name = "vllm"
        self._use_ollama_native = False


register_provider("ollama", OllamaProvider)
register_provider("vllm", VLLMProvider)
register_provider("local", LocalProvider)
