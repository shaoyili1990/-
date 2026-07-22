"""天道系统 - tiandao_bridge 接口测试

测试四大接口的基本功能。每个测试使用独立的临时数据库以避免状态污染。
"""

import json
import os
import sqlite3
import tempfile
import unittest

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from harness_core.tiandao.tiandao_bridge import TiandaoDB


def build_test_db(db_path: str) -> None:
    """在指定路径创建包含种子数据的测试数据库。"""
    from harness_core.tiandao.db_init import create_database, execute_ddl

    conn = create_database(db_path)
    try:
        execute_ddl(conn)

        # 测试用小说
        conn.execute(
            "INSERT INTO tiandao_novels (novel_id, name, status, style) "
            "VALUES ('novel-test', '测试小说', 'active', '玄幻')"
        )

        # 测试用人物 (排序固定: id 1,2,3,4)
        test_chars = [
            ("novel-test", "主角", "ENFP", 50.0, "protagonist", "测试主角",
             '{"traits": ["乐观"]}'),
            ("novel-test", "反派", "INTJ", 45.0, "antagonist", "测试反派",
             '{"traits": ["冷静"]}'),
            ("novel-test", "配角", "ESFJ", 55.0, "major", "测试配角",
             '{"traits": ["友善"]}'),
            ("novel-test", "龙套", "ISTJ", 50.0, "minor", "测试龙套",
             '{"traits": ["普通"]}'),
        ]
        for char in test_chars:
            conn.execute(
                "INSERT INTO tiandao_characters "
                "(novel_id, name, mbti, y_base, weight_class, description, persona_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                char,
            )

        conn.commit()
    finally:
        conn.close()


class TestTiandaoBridge(unittest.TestCase):
    """天道Bridge接口测试套件。每个测试方法使用独立数据库。"""

    def setUp(self):
        """每个测试前创建临时数据库。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "rnd_tiandao.db")
        build_test_db(self.db_path)
        self.db = TiandaoDB(self.db_path)

    def tearDown(self):
        """每个测试后清理临时目录。"""
        self.tmpdir.cleanup()

    # ── 辅助方法 ──────────────────────────────────────────────────

    def _char_id(self, name: str) -> int:
        """按名称查询人物ID。"""
        conn = self.db._connect()
        try:
            row = conn.execute(
                "SELECT id FROM tiandao_characters WHERE name = ?",
                (name,),
            ).fetchone()
            return row["id"] if row else -1
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════════════════
    # trigger_event 测试
    # ═══════════════════════════════════════════════════════════════

    def test_trigger_event_basic(self):
        """触发简单事件，验证Y值变化"""
        char_id = self._char_id("主角")

        result = self.db.trigger_event(
            "novel-test",
            {
                "chapter": "第1章",
                "title": "主角觉醒",
                "description": "主角发现神秘印记",
                "impact": 8.0,
                "characters": [{"char_id": char_id}],
            },
        )

        self.assertEqual(len(result), 1)
        state = result[0]
        # 主角 weight=protagonist→1.5, influence 从 weight_class 推导→1.0
        # delta_y = 8.0 * 1.0 * 1.5 = 12.0 → y = 50 + 12 = 62
        self.assertEqual(state["char_id"], char_id)
        self.assertEqual(state["name"], "主角")
        self.assertAlmostEqual(state["y_current"], 62.0, delta=0.01)
        self.assertAlmostEqual(state["y_effective"], 0.62, delta=0.01)

    def test_trigger_event_with_explicit_role(self):
        """使用显式指定的role_type和influence_score"""
        char_id = self._char_id("龙套")

        result = self.db.trigger_event(
            "novel-test",
            {
                "chapter": "第1章",
                "title": "龙套路过",
                "description": "龙套打了个喷嚏",
                "impact": 10.0,
                "characters": [{
                    "char_id": char_id,
                    "role_type": "extra",
                    "influence_score": 0.3,
                }],
            },
        )

        # 龙套 weight=minor→0.3, influence=0.3
        # delta_y = 10.0 * 0.3 * 0.3 = 0.9 → y = 50 + 0.9 = 50.9
        self.assertAlmostEqual(result[0]["y_current"], 50.9, delta=0.01)

    def test_trigger_event_multiple_characters(self):
        """多人事件，验证角色权重差异"""
        ids = {
            "主角": self._char_id("主角"),
            "反派": self._char_id("反派"),
            "配角": self._char_id("配角"),
        }

        result = self.db.trigger_event(
            "novel-test",
            {
                "chapter": "第2章",
                "title": "正面对决",
                "description": "主角与反派对峙",
                "impact": 15.0,
                "characters": [
                    {"char_id": ids["主角"]},
                    {"char_id": ids["反派"]},
                    {"char_id": ids["配角"]},
                ],
            },
        )

        self.assertEqual(len(result), 3)
        states = {r["char_id"]: r for r in result}

        # 主角: 15.0 * 1.0(推导influence) * 1.5(protagonist) = 22.5
        # 但最大delta_y = min(22.5, 20) = 20 → y = 50 + 20 = 70
        self.assertAlmostEqual(states[ids["主角"]]["y_current"], 70.0, delta=0.5)

        # 反派: 15.0 * 1.0 * 1.5 = 22.5 → clamp 20 → y = 45 + 20 = 65
        self.assertAlmostEqual(states[ids["反派"]]["y_current"], 65.0, delta=0.5)

        # 配角: 15.0 * 0.8(推导influence) * 1.0(major) = 12.0 → y = 55 + 12 = 67
        self.assertAlmostEqual(states[ids["配角"]]["y_current"], 67.0, delta=0.5)

        # 所有角色都有情绪
        for r in result:
            self.assertIn("emotions", r)
            self.assertIsInstance(r["emotions"], dict)

    def test_trigger_event_novel_not_found(self):
        """不存在的小说应抛出ValueError"""
        with self.assertRaises(ValueError) as ctx:
            self.db.trigger_event("novel-not-exist", {
                "chapter": "第1章", "title": "不存在", "description": "嘛也没有",
            })
        self.assertIn("novel-not-exist", str(ctx.exception))

    def test_trigger_event_missing_fields(self):
        """缺少必要字段应抛出ValueError"""
        with self.assertRaises(ValueError):
            self.db.trigger_event("novel-test", {
                "chapter": "第1章",
            })

    def test_trigger_event_no_characters(self):
        """事件无关联人物应返回空列表"""
        result = self.db.trigger_event(
            "novel-test",
            {
                "chapter": "第3章", "title": "空事件",
                "description": "没有人物的事件",
                "characters": [],
            },
        )
        self.assertEqual(result, [])

    def test_trigger_event_delta_y_clamped_to_20(self):
        """单次事件Y值变化不应超过±20"""
        char_id = self._char_id("主角")

        # impact=100, protagonist=1.5倍 → 150 → clamp到20
        result = self.db.trigger_event(
            "novel-test",
            {
                "chapter": "第5章", "title": "核爆级事件",
                "description": "毁天灭地的冲击",
                "impact": 100.0,
                "characters": [{"char_id": char_id}],
            },
        )

        # 50 + 20 = 70 (被clamp)
        self.assertAlmostEqual(result[0]["y_current"], 70.0, delta=0.01)

    # ═══════════════════════════════════════════════════════════════
    # get_character_state 测试
    # ═══════════════════════════════════════════════════════════════

    def test_get_character_state_no_history(self):
        """无状态历史时应返回基线信息"""
        # 配角还没有任何事件
        state = self.db.get_character_state("novel-test", self._char_id("配角"))

        self.assertEqual(state["name"], "配角")
        self.assertAlmostEqual(state["y_current"], 55.0)  # y_base
        self.assertAlmostEqual(state["y_effective"], 0.55)

    def test_get_character_state_after_event(self):
        """触发事件后能正确读取状态"""
        char_id = self._char_id("主角")
        self.db.trigger_event(
            "novel-test",
            {"chapter": "第4章", "title": "状态测试",
             "description": "检查状态读取", "impact": 5.0,
             "characters": [{"char_id": char_id}]},
        )

        state = self.db.get_character_state("novel-test", char_id)
        self.assertGreater(state["y_current"], 50.0)
        self.assertIn("emotions", state)

    def test_get_character_state_unknown(self):
        """不存在的人物应返回空字典"""
        state = self.db.get_character_state("novel-test", 9999)
        self.assertEqual(state, {})

    def test_get_character_state_with_chapter(self):
        """指定章节读取应返回正确章节的状态"""
        char_id = self._char_id("主角")

        self.db.trigger_event(
            "novel-test",
            {"chapter": "第5章-专测", "title": "章节测试",
             "description": "测试章节定位", "impact": 3.0,
             "characters": [{"char_id": char_id}]},
        )

        state = self.db.get_character_state(
            "novel-test", char_id, chapter="第5章-专测"
        )
        self.assertEqual(state["chapter"], "第5章-专测")

    def test_get_character_state_no_chapter_returns_latest(self):
        """不指定章节应返回最新状态"""
        char_id = self._char_id("主角")
        self.db.trigger_event(
            "novel-test",
            {"chapter": "第1章", "title": "事件A",
             "description": "早期事件", "impact": 5.0,
             "characters": [{"char_id": char_id}]},
        )
        self.db.trigger_event(
            "novel-test",
            {"chapter": "第2章", "title": "事件B",
             "description": "后续事件", "impact": 10.0,
             "characters": [{"char_id": char_id}]},
        )

        state = self.db.get_character_state("novel-test", char_id)
        self.assertEqual(state["chapter"], "第2章")
        self.assertGreater(state["y_current"], 60.0)

    # ═══════════════════════════════════════════════════════════════
    # get_event_roles 测试
    # ═══════════════════════════════════════════════════════════════

    def test_get_event_roles_normal(self):
        """事件角色应按 role_type 排序返回"""
        conn = self.db._connect()
        try:
            cursor = conn.execute(
                "INSERT INTO tiandao_events (novel_id,chapter,title,description) "
                "VALUES (?,?,?,?)",
                ("novel-test", "第X章", "角色测试", "测试事件"),
            )
            event_id = cursor.lastrowid

            conn.execute(
                "INSERT INTO tiandao_event_roles "
                "(event_id, char_id, role_type, influence_score) VALUES "
                "(?, ?, 'major', 1.0), (?, ?, 'supporting', 0.6), (?, ?, 'extra', 0.3)",
                (event_id, self._char_id("主角"),
                 event_id, self._char_id("反派"),
                 event_id, self._char_id("龙套")),
            )
            conn.commit()
        finally:
            conn.close()

        roles = self.db.get_event_roles("novel-test", event_id)

        self.assertEqual(len(roles), 3)
        self.assertEqual(roles[0]["role_type"], "major")
        self.assertEqual(roles[1]["role_type"], "supporting")
        self.assertEqual(roles[2]["role_type"], "extra")
        self.assertEqual(roles[0]["influence_score"], 1.0)

    def test_get_event_roles_not_found(self):
        """不存在的事件应返回空列表"""
        self.assertEqual(self.db.get_event_roles("novel-test", 9999), [])

    # ═══════════════════════════════════════════════════════════════
    # update_after_god_intervention 测试
    # ═══════════════════════════════════════════════════════════════

    def test_god_intervention_basic(self):
        """老天爷介入直接改Y值"""
        char_id = self._char_id("反派")

        result = self.db.update_after_god_intervention(
            "novel-test", char_id, delta_y=-20.0,
            reason="反派需要更黑暗的转折",
        )

        self.assertEqual(result["char_id"], char_id)
        # 反派 Y_base=45, delta_y=-20, Y=25
        self.assertAlmostEqual(result["y_current"], 25.0)

        # 验证审计信息写入 emotions
        state = self.db.get_character_state("novel-test", char_id)
        self.assertIn("_god_intervention", state["emotions"])
        self.assertEqual(
            state["emotions"]["_god_intervention"],
            "反派需要更黑暗的转折",
        )

    def test_god_intervention_clamp_to_range(self):
        """老天爷介入仍保持在[0,100]范围内"""
        char_id = self._char_id("主角")

        # 大幅下降
        r1 = self.db.update_after_god_intervention(
            "novel-test", char_id, delta_y=-200.0, reason="深渊",
        )
        self.assertEqual(r1["y_current"], 0.0)

        # 大幅上升
        r2 = self.db.update_after_god_intervention(
            "novel-test", char_id, delta_y=500.0, reason="神迹",
        )
        self.assertEqual(r2["y_current"], 100.0)


class TestGodInterventionNoLimit(unittest.TestCase):
    """验证老天爷介入不受±20限制（独立数据库）"""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "rnd_tiandao.db")
        build_test_db(self.db_path)
        self.db = TiandaoDB(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _char_id(self, name):
        conn = self.db._connect()
        try:
            return conn.execute(
                "SELECT id FROM tiandao_characters WHERE name=?",
                (name,),
            ).fetchone()["id"]
        finally:
            conn.close()

    def test_god_can_exceed_20(self):
        """老天爷的 delta_y 允许大于±20"""
        char_id = self._char_id("龙套")

        # 设置 -60, 常规事件最大±20但老天爷可以
        result = self.db.update_after_god_intervention(
            "novel-test", char_id, delta_y=-60.0,
            reason="剧情杀",
        )

        # 龙套 Y_base=50, delta_y=-60, 应到0 (clamp到0)
        self.assertEqual(result["y_current"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
