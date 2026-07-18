"""模型适配层 - 支持所有AI厂商"""
from .base import LLMProvider, LLMResponse
from .registry import ProviderRegistry, get_provider, register_provider

# 导入并注册所有提供者
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .local import LocalProvider, OllamaProvider, VLLMProvider
from . import openai as _openai  # 触发 register_provider("openai", OpenAIProvider)

# 显式确保注册
register_provider("openai", OpenAIProvider)
register_provider("deepseek", _openai.DeepSeekProvider)
register_provider("openrouter", _openai.OpenRouterProvider)
register_provider("anthropic", AnthropicProvider)
register_provider("ollama", OllamaProvider)
register_provider("vllm", VLLMProvider)
register_provider("local", LocalProvider)
