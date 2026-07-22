"""天道系统 — 马的双通道Harness整合层。

模块结构：
- tiandao_bridge.py  状态机↔天道联动接口（trigger_event, get_character_state 等）
- y_engine.py        Y值计算引擎（公式01-10完整链）
- harness.py         Harness双通道主控（子链通道+天道通道整合）
- db_init.py         数据库DDL初始化和种子数据
"""

__all__ = ["tiandao_bridge", "y_engine", "harness"]
