#!/usr/bin/env python3
"""天道临时执行脚本 — 任务 params-test

由 Harness v0.1.0 自动生成。
生成时间: 2026-07-23T09:01:41.613703

任务类型: 01_一因一果因果链
"""

import json


def main():
    """执行剧本分析。"""
    narrative_instruction = "【因果类型】单个原因导致单个结果的结构，因果关系简单直接\n【分析路径】确认唯一原因。 → 确认唯一直接结果。 → 说明原因到结果的直接机制。 → 排除其他原因和额外结果的干扰。"

    characters = [
  "张平凡[Y=55.0](重要人物) 情绪:喜3.0、思5.0 动机:好奇心",
  "冷月[Y=45.0](重要人物) 情绪:思2.0、欲1.0"
]

    print("=" * 50)
    print("任务: params-test")
    print("=" * 50)
    print()
    print("【叙事指令】")
    print(narrative_instruction)
    print()
    print("【人物状态】")
    for c in characters:
        print("  -", c)
    print()
    print("【完成】请根据以上信息进行创作。")


if __name__ == "__main__":
    main()
