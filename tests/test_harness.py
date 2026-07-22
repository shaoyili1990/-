"""天道系统 - Harness 双通道集成测试

测试Harness的三大核心流程：
  1. 子链通道读取与解析
  2. 天道通道数据获取
  3. 整合输出为执行指令
  4. 临时脚本生成

所有测试使用本地临时目录和临时数据库，不依赖服务器。
"""

import json
import os
import sqlite3
import tempfile
import unittest

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from harness_core.tiandao.db_init import create_database, execute_ddl
from harness_core.tiandao.harness import (
    Harness, SubchainReader, TiandaoChannel,
    build_chain_input, build_tiandao_input, assemble_output,
)
from harness_core.tiandao.tiandao_bridge import TiandaoDB


def setup_test_db(db_path: str) -> None:
    """创建测试数据库并插入种子数据。"""
    conn = create_database(db_path)
    try:
        execute_ddl(conn)

        # 小说
        conn.execute(
            "INSERT INTO tiandao_novels (novel_id, name, status, style) "
            "VALUES ('novel-test', '测试小说', 'active', '玄幻')"
        )

        # 人物
        chars = [
            ("novel-test", "张平凡", "ENFP", 50.0, "protagonist", "主角",
             '{"traits":["乐观"]}'),
            ("novel-test", "冷月", "INTJ", 45.0, "antagonist", "反派",
             '{"traits":["冷静"]}'),
            ("novel-test", "老李头", "ESFJ", 60.0, "major", "导师",
             '{"traits":["慈祥"]}'),
        ]
        for c in chars:
            conn.execute(
                "INSERT INTO tiandao_characters "
                "(novel_id, name, mbti, y_base, weight_class, description, persona_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)", c
            )

        # 预先创建一条状态快照
        conn.execute(
            """INSERT INTO tiandao_states
               (novel_id, char_id, chapter, event_seq, y_current, y_effective,
                emotions_json, desires_json, motivation, breakthrough_flag)
               VALUES ('novel-test', 1, '第1章', 0, 55.0, 0.55,
                       '{"喜":3,"思":5}', '{"权力":0.3}', '好奇心', 0)"""
        )

        conn.commit()
    finally:
        conn.close()


def create_sample_subchains(tmpdir: str) -> str:
    """在临时目录创建几个示例子链markdown文件。

    Returns:
        str: 子链目录路径。
    """
    subchains_dir = os.path.join(tmpdir, "subchains")
    os.makedirs(subchains_dir, exist_ok=True)

    # 反噬反转因果链
    with open(os.path.join(subchains_dir, "08_反噬反转因果链.md"), "w", encoding="utf-8") as f:
        f.write("""# 反噬反转因果链深度定制化提示词模板

## 1. 子类定义
初期带来正向作用的原因，发展到临界点后反向催生负面结果

## 2. 模板定位
所属集合：因果链

## 3. 子类工作定义
围绕"反噬反转"完成专属分析。

## 4. 适用与不适用
### 适用
- 材料中存在可抽取的节点、步骤、条件、关系
- 用户希望看清"反噬反转因果链"如何成立

### 不适用
- 材料信息过少

## 5. 本子类专属分析重点
分析原有作用如何被另一力量牵制、抵消、逆转、反噬或中断。

## 6. 强制分析流程
1. 识别原始推动力量。
2. 识别介入的反向力量或限制。
3. 找出发生抵消、反转或阻断的临界点。
4. 说明最终路径如何被改写。
5. 回到整体材料，说明结构对判断或结果的影响。

## 7. 深度分析提示词
```text
【任务】反噬反转因果链深度分析
【子类定义】初期带来正向作用的原因，发展到临界点后反向催生负面结果
请严格以"反噬反转因果链"为唯一核心视角进行分析。
```

## 8. 通用抽象提示词
基于上一份分析提取通用模型。

## 9. 模板自检清单
- [ ] 是否把定义拆成了可执行动作？
- [ ] 是否没有限定材料类型？
- [ ] 是否解释了运行机制和失效边界？
""")

    # 一因一果因果链
    with open(os.path.join(subchains_dir, "01_一因一果因果链.md"), "w", encoding="utf-8") as f:
        f.write("""# 一因一果因果链深度定制化提示词模板

## 1. 子类定义
单个原因导致单个结果的结构，因果关系简单直接

## 2. 模板定位
所属集合：因果链

## 3. 子类工作定义
围绕"一因一果"完成专属分析。

## 4. 适用与不适用
### 适用
- 存在可抽取的节点和因果关系

### 不适用
- 材料信息过少

## 5. 本子类专属分析重点
锁定一个明确原因和一个直接结果，排除多因混杂。

## 6. 强制分析流程
1. 确认唯一原因。
2. 确认唯一直接结果。
3. 说明原因到结果的直接机制。
4. 排除其他原因和额外结果的干扰。

## 7. 深度分析提示词
```text
【任务】一因一果因果链深度分析
```

## 9. 模板自检清单
- [ ] 是否保持单因单果闭合？
""")

    # 权谋博弈因果链（不在标准编号里，测试搜索）
    with open(os.path.join(subchains_dir, "05_博弈推导法.md"), "w", encoding="utf-8") as f:
        f.write("""# 博弈推导法深度定制化提示词模板

## 1. 子类定义
多方在利益冲突中通过策略选择达成均衡或最优解的分析方法

## 5. 本子类专属分析重点
分析多方策略互动中的最优选择。

## 6. 强制分析流程
1. 识别参与方。
2. 列出各方的策略空间。
3. 分析收益矩阵。
4. 求解均衡点。
""")

    return subchains_dir


class TestSubchainReader(unittest.TestCase):
    """子链通道读取测试。"""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.subchains_dir = create_sample_subchains(self.tmpdir.name)
        self.reader = SubchainReader(self.subchains_dir)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_get_chain_by_id_with_ext(self):
        """带.md后缀的ID能正确读取。"""
        info = self.reader.get_chain_info("08_反噬反转因果链.md")
        self.assertIsNotNone(info)
        self.assertEqual(info["name"], "反噬反转因果链深度定制化提示词模板")

    def test_get_chain_by_id_without_ext(self):
        """不带.md后缀的ID也能正确读取。"""
        info = self.reader.get_chain_info("08_反噬反转因果链")
        self.assertIsNotNone(info)

    def test_chain_definition_parsed(self):
        """子类定义被正确解析。"""
        info = self.reader.get_chain_info("08_反噬反转因果链")
        self.assertIn("初期带来正向作用的原因", info["definition"])

    def test_chain_flow_steps_parsed(self):
        """强制分析流程步骤被正确解析。"""
        info = self.reader.get_chain_info("08_反噬反转因果链")
        self.assertEqual(len(info["flow_steps"]), 5)
        self.assertIn("识别原始推动力量", info["flow_steps"][0])

    def test_chain_focus_parsed(self):
        """分析重点被正确解析。"""
        info = self.reader.get_chain_info("08_反噬反转因果链")
        self.assertIn("牵制、抵消、逆转", info["focus"])

    def test_chain_prompt_parsed(self):
        """深度分析提示词被正确解析。"""
        info = self.reader.get_chain_info("08_反噬反转因果链")
        self.assertIn("反噬反转因果链深度分析", info["prompt_template"])

    def test_chain_checklist_parsed(self):
        """自检清单被正确解析。"""
        info = self.reader.get_chain_info("08_反噬反转因果链")
        self.assertGreater(len(info["checklist"]), 0)
        self.assertIn("是否把定义拆成了可执行动作", info["checklist"][0])

    def test_chain_not_found(self):
        """不存在的子链返回None。"""
        info = self.reader.get_chain_info("不存在链")
        self.assertIsNone(info)

    def test_search_by_name(self):
        """按名称搜索能匹配到正确文件。"""
        info = self.reader.get_chain_info("博弈")
        self.assertIsNotNone(info)
        self.assertIn("博弈", info["name"])

    def test_list_chains(self):
        """列出所有子链。"""
        chains = self.reader.list_chains()
        self.assertGreaterEqual(len(chains), 3)

    def test_list_chains_by_category(self):
        """按类别编号过滤。"""
        chains = self.reader.list_chains(category_code="08")
        self.assertEqual(len(chains), 1)
        self.assertEqual(chains[0]["category_code"], "08")

    def test_one_to_one_chain(self):
        """一因一果链正确解析。"""
        info = self.reader.get_chain_info("01_一因一果因果链")
        self.assertIsNotNone(info)
        self.assertIn("单个原因导致单个结果", info["definition"])
        self.assertEqual(len(info["flow_steps"]), 4)


class TestTiandaoChannel(unittest.TestCase):
    """天道通道测试。"""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "rnd_tiandao.db")
        setup_test_db(self.db_path)
        self.db = TiandaoDB(self.db_path)
        self.channel = TiandaoChannel(self.db)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_get_characters_for_event_no_event(self):
        """无事件时返回空列表。"""
        chars = self.channel.get_characters_for_event("novel-test", 999)
        self.assertEqual(chars, [])

    def test_build_tiandao_input_structure(self):
        """天道通道输入有正确结构。"""
        result = self.channel.build_tiandao_input("novel-test", 0)
        self.assertIn("novel_id", result)
        self.assertIn("event_id", result)
        self.assertIn("characters", result)
        self.assertEqual(result["novel_id"], "novel-test")

    def test_build_tiandao_input_with_context(self):
        """带额外上下文信息。"""
        result = self.channel.build_tiandao_input(
            "novel-test", 0,
            extra_context={"chapter": "第1章", "scene": "觉醒"},
        )
        self.assertIn("context", result)
        self.assertEqual(result["context"]["chapter"], "第1章")


class TestHarnessIntegration(unittest.TestCase):
    """Harness集成测试。"""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.subchains_dir = create_sample_subchains(self.tmpdir.name)
        self.db_path = os.path.join(self.tmpdir.name, "rnd_tiandao.db")
        setup_test_db(self.db_path)
        self.db = TiandaoDB(self.db_path)
        self.harness = Harness(
            subchains_dir=self.subchains_dir,
            db=self.db,
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_harness_full_flow(self):
        """完整Harness流程测试。"""
        output = self.harness.run(
            task_id="test-001-event-001",
            chain_type="因果链-反噬反转",
            chain_id="08_反噬反转因果链",
            novel_id="novel-test",
            event_id=0,
            char_ids=[1],
            params={"key_event": "主角获得力量"},
        )

        # 验证输出结构
        self.assertIn("task_id", output)
        self.assertIn("harness_version", output)
        self.assertIn("inputs", output)
        self.assertIn("output", output)

        # 验证任务ID
        self.assertEqual(output["task_id"], "test-001-event-001")

        # 验证子链通道输入
        chain_input = output["inputs"]["chain"]
        self.assertEqual(chain_input["chain_type"], "因果链-反噬反转")
        self.assertEqual(chain_input["chain_id"], "08_反噬反转因果链")

        # 验证天道通道输入
        tiandao_input = output["inputs"]["tiandao"]
        self.assertEqual(tiandao_input["novel_id"], "novel-test")
        self.assertGreater(tiandao_input["character_count"], 0)

        # 验证叙事指令包含子链定义
        narrative = output["output"]["narrative_instruction"]
        self.assertIn("初期带来正向作用", narrative)

        # 验证人物状态
        char_states = output["output"]["character_states_after"]
        self.assertGreater(len(char_states), 0)
        self.assertIn("张平凡", char_states[0])

        # 验证逻辑流
        chain_detail = output["output"]["chain_detail"]
        self.assertGreater(len(chain_detail["logic_flow"]), 0)

        # 验证脚本生成
        self.assertIn("script_path", output)
        self.assertTrue(os.path.isfile(output["script_path"]))

    def test_harness_no_chain_file(self):
        """子链文件不存在时仍然能输出基本格式。"""
        output = self.harness.run(
            task_id="no-chain-test",
            chain_type="未知链型",
            chain_id="unknown_chain",
            novel_id="novel-test",
            event_id=0,
            char_ids=[1],
        )

        # 仍然有基本输出结构
        self.assertEqual(output["task_id"], "no-chain-test")
        self.assertEqual(output["inputs"]["chain"]["chain_type"], "未知链型")

    def test_harness_chain_with_params(self):
        """自定义参数传递。"""
        output = self.harness.run(
            task_id="params-test",
            chain_type="因果链-一因一果",
            chain_id="01_一因一果因果链",
            novel_id="novel-test",
            event_id=0,
            char_ids=[1, 2],
            params={"custom_param": "test_value"},
        )

        # 验证params传递
        chain_detail = output["output"]["chain_detail"]
        self.assertGreater(len(chain_detail["logic_flow"]), 0)

    def test_harness_empty_characters(self):
        """无人物时也能正常输出。"""
        output = self.harness.run(
            task_id="no-char-test",
            chain_type="因果链-反噬反转",
            chain_id="08_反噬反转因果链",
            novel_id="novel-test",
            event_id=999,
        )

        self.assertEqual(output["output"]["character_states_after"], [])


class TestQuickFunctions(unittest.TestCase):
    """快捷函数测试。"""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.subchains_dir = create_sample_subchains(self.tmpdir.name)
        self.db_path = os.path.join(self.tmpdir.name, "rnd_tiandao.db")
        setup_test_db(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_build_chain_input(self):
        """build_chain_input快捷函数。"""
        result = build_chain_input(
            self.subchains_dir,
            "因果链-反噬反转",
            "08_反噬反转因果链",
        )
        self.assertIsNotNone(result)
        self.assertIn("chain_type", result)
        self.assertIn("output_template", result)

    def test_build_tiandao_input(self):
        """build_tiandao_input快捷函数。"""
        result = build_tiandao_input(
            self.db_path,
            "novel-test", 0,
            char_ids=[1],
        )
        self.assertIn("novel_id", result)
        self.assertIn("characters", result)
        self.assertEqual(len(result["characters"]), 1)

    def test_assemble_output(self):
        """assemble_output快捷函数。"""
        chain_input = {
            "chain_type": "测试链",
            "chain_id": "test",
            "output_template": {
                "logic_flow": ["步骤1", "步骤2"],
                "expected_outcome": "测试结果",
            },
        }
        tiandao_input = {
            "novel_id": "test",
            "event_id": 0,
            "characters": [
                {"name": "角色A", "y_current": 50.0, "event_role": "重要人物",
                 "emotions": {"喜": 3}}
            ],
        }
        output = assemble_output("quick-test", chain_input, tiandao_input)

        self.assertEqual(output["task_id"], "quick-test")
        self.assertIn("narrative_instruction", output["output"])
        self.assertIn("character_states_after", output["output"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
