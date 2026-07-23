"""
提供者注册表 - 动态管理和路由到不同AI厂商
"""

from typing import Dict, Optional, Type
from .base import LLMProvider


class ProviderRegistry:
    """提供者注册表"""

    def __init__(self):
        self._providers: Dict[str, Type[LLMProvider]] = {}

    def register(self, name: str, provider_class: Type[LLMProvider]):
        """注册提供者"""
        self._providers[name] = provider_class

    def get(self, name: str) -> Optional[Type[LLMProvider]]:
        """获取提供者类"""
        return self._providers.get(name)

    def list_providers(self) -> Dict[str, Type[LLMProvider]]:
        return dict(self._providers)

    def create(self, name: str, config: Dict) -> Optional[LLMProvider]:
        """创建提供者实例"""
        cls = self.get(name)
        if cls:
            return cls(config)
        return None


# 全局注册表
_registry = ProviderRegistry()


def register_provider(name: str, provider_class: Type[LLMProvider]):
    _registry.register(name, provider_class)


def get_provider(name: str, config: Dict) -> Optional[LLMProvider]:
    """获取提供者实例的快捷方式"""
    # 1. 直接从注册表创建
    provider = _registry.create(name, config)
    if provider:
        return provider

    # 2. 尝试从环境变量读取API Key
    if not config.get("api_key"):
        import os
        env_keys = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        env_key = env_keys.get(name)
        if env_key:
            config["api_key"] = os.environ.get(env_key, "")
            provider = _registry.create(name, config)
            if provider:
                return provider

    # 3. 最后兜底: 返回MockProvider(用于测试/演示)
    return MockProvider(config)


class MockProvider(LLMProvider):
    """Mock提供者 - 无API Key时的兜底，返回模拟响应"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = config.get("name", "mock")

    def generate(self, messages, **kwargs):
        from .base import LLMResponse
        last_msg = messages[-1].get("content", "") if messages else ""
        if isinstance(last_msg, list):
            texts = [p.get("text", "") for p in last_msg if isinstance(p, dict) and p.get("type") == "text"]
            last_msg = " ".join(texts)

        return LLMResponse(
            content=f"[Mock {self.name}] 已收到您的消息。请设置有效的API Key以获取真实响应。\n\n"
                    f"您可以通过以下方式之一设置:\n"
                    f"1. 环境变量: export {self.name.upper()}_API_KEY=sk-xxx\n"
                    f"2. 桌面版配置面板\n"
                    f"3. CLI: monkey-harness config set {self.name}_key sk-xxx\n\n"
                    f"收到消息: {last_msg[:200]}",
            model="mock",
            provider=self.name,
            finish_reason="stop",
        )

    def stream(self, messages, **kwargs):
        yield self.generate(messages).content
