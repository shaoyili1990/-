"""
Agent核心 - 四角色协奏 + 质检官
  灵猴(Monkey): 路由与审核
  骏马(Horse): 推理与执行
  司库(Keeper): 状态机驱动
  书童(Scribe): 认知与记忆
  质检官(Verifier): 验证审查
"""
from .monkey import Monkey
from .horse import Horse
from .keeper import Keeper
from .scribe import Scribe
from .verifier import Verifier
