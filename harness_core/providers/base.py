"""
模型适配器抽象基类
定义所有AI提供者的统一接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator


@dataclass
class LLMResponse:
    """统一LLM响应格式"""
    content: str = ""
    model: str = ""
    provider: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: str = ""
    raw: Any = None

    @property
    def input_tokens(self) -> int:
        return self.usage.get("input_tokens", 0) or self.usage.get("prompt_tokens", 0)

    @property
    def output_tokens(self) -> int:
        return self.usage.get("output_tokens", 0) or self.usage.get("completion_tokens", 0)


class LLMProvider(ABC):
    """LLM提供者抽象基类"""

    def __init__(self, config: Dict):
        self.name = config.get("name", "unknown")
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "")
        self.model = config.get("model", "")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 4096)
        self.is_local = config.get("is_local", False)

    @abstractmethod
    def generate(self, messages: List[Dict], **kwargs) -> LLMResponse:
        """同步生成"""
        ...

    def stream(self, messages: List[Dict], **kwargs) -> Generator[str, None, None]:
        """流式生成(可选重写)"""
        resp = self.generate(messages, **kwargs)
        yield resp.content

    async def async_generate(self, messages: List[Dict], **kwargs) -> LLMResponse:
        """异步生成(可选重写)"""
        return self.generate(messages, **kwargs)

    async def async_stream(self, messages: List[Dict], **kwargs) -> AsyncGenerator[str, None]:
        """异步流式(可选重写)"""
        for chunk in self.stream(messages, **kwargs):
            yield chunk

    def count_tokens(self, text: str) -> int:
        """估算token数(可选重写)"""
        return len(text) // 2

    def get_models(self) -> List[str]:
        """获取可用模型列表(可选重写)"""
        return [self.model] if self.model else []

    def _build_headers(self) -> Dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _prepare_messages(self, messages: List[Dict]) -> List[Dict]:
        """预处理消息(子类可重写)"""
        return messages
