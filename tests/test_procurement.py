"""
采购流测试 — 测试采购请求的完整生命周期
"""
import os
import sys
import json
import unittest
import tempfile
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harness_core.config import Config
from harness_core.engine import EngineDB
from harness_core.core.keeper import Keeper
from harness_core.core.purchaser import Purchaser


class FakeConfig:
    """假Config，只提供需要的配置接口"""
    def get_provider_config(self, role: str) -> dict:
        return {"name": "mock", "api_key": "", "model": "mock", "base_url": ""}

    def get(self, section: str, key: str, default=None):
        return default


class FakeProvider:
    """假Provider，返回固定的搜索结果"""
    class FakeResp:
        content = json.dumps([
            {"id": "web-search", "reason": "适合搜索"},
            {"id": "translate", "reason": "翻译需求"},
        ])
    def generate(self, msgs):
        return self.FakeResp()


# Patch get_provider
import harness_core.providers as providers_mod
_orig_get_provider = providers_mod.get_provider
def _mock_get_provider(name, config):
    return FakeProvider()
providers_mod.get_provider = _mock_get_provider


class FakeEngineDB:
    """假EngineDB，使用临时SQLite数据库"""
    def __init__(self, db_path):
        self.db_path = db_path
        # 创建必要的表
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rnd_tasks (
                task_id TEXT PRIMARY KEY,
                name TEXT,
                status TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rnd_constitution (
                id INTEGER PRIMARY KEY,
                name TEXT,
                content TEXT,
                version INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skill_market (
                id TEXT PRIMARY KEY,
                name TEXT, icon TEXT, description TEXT,
                category TEXT, author TEXT, tags TEXT,
                downloads INTEGER DEFAULT 0, rating REAL DEFAULT 0.0,
                version TEXT DEFAULT '1.0.0', source_url TEXT DEFAULT '',
                color TEXT DEFAULT '#7c6ff0'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS installed_skills (
                id TEXT PRIMARY KEY, name TEXT, icon TEXT,
                description TEXT, version TEXT, color TEXT,
                source_url TEXT, category TEXT, author TEXT,
                installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                enabled INTEGER DEFAULT 1, updated_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS web_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, content TEXT, source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS error_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT, error_type TEXT, detail TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rnd_state_def (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state_name TEXT,
                state_order INTEGER,
                description TEXT,
                allowed_transitions TEXT DEFAULT '[]'
            )
        """)
        import json as _json
        for name, order, desc in [
            ("待构思", 1, "任务初始状态"),
            ("构思完成待执行", 2, "构思完成等待执行"),
            ("待执行", 3, "执行中"),
            ("执行完成待验证", 4, "等待验证"),
            ("验证中", 5, "验证进行中"),
            ("验证通过", 6, "验证通过"),
            ("验证未通过", 7, "验证未通过"),
            ("待复审", 8, "等待复审"),
            ("待复查", 9, "等待复查"),
        ]:
            allowed = _json.dumps({
                "待构思": ["构思完成待执行"],
                "构思完成待执行": ["待执行"],
                "待执行": ["执行完成待验证"],
                "执行完成待验证": ["验证中"],
                "验证中": ["验证通过", "验证未通过"],
                "验证通过": ["构思完成待执行", "待执行", "已验证"],
                "验证未通过": ["待执行", "待复审"],
                "待复审": ["待执行", "验证通过", "待复查"],
                "待复查": ["待执行", "验证通过"],
            }.get(name, []), ensure_ascii=False)
            conn.execute(
                "INSERT OR IGNORE INTO rnd_state_def (state_name, state_order, description, allowed_transitions) VALUES (?, ?, ?, ?)",
                (name, order, desc, allowed)
            )
        conn.commit()
        conn.close()

    def engine_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def cognition_conn(self):
        return self.engine_conn()

    def record_chat(self, *args):
        pass

    def save_memory(self, *args):
        pass

    def get_task(self, task_id):
        conn = self.engine_conn()
        try:
            row = conn.execute("SELECT * FROM rnd_tasks WHERE task_id=?", (task_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_tasks(self, status=None, limit=20):
        conn = self.engine_conn()
        try:
            if status:
                rows = conn.execute("SELECT * FROM rnd_tasks WHERE status=? LIMIT ?", (status, limit)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM rnd_tasks LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def create_task(self, task_id, name, level, parent_id, status):
        conn = self.engine_conn()
        try:
            conn.execute(
                "INSERT INTO rnd_tasks (task_id, name, status) VALUES (?, ?, ?)",
                (task_id, name, status)
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()


class TestProcurementFlow(unittest.TestCase):
    """采购流单元测试"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "test.db")
        cls.db = FakeEngineDB(cls.db_path)
        cls.config = FakeConfig()
        cls.keeper = Keeper(cls.config, cls.db)
        cls.purchaser = Purchaser(cls.config, cls.db)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        """每个测试前清理procurement_requests表"""
        conn = self.db.cognition_conn()
        try:
            conn.execute("DELETE FROM procurement_requests")
            conn.execute("DELETE FROM rnd_tasks")
            conn.commit()
        finally:
            conn.close()

    # ─── 闸门测试 ───

    def test_gate_closed_no_task(self):
        """无活跃任务时采购闸门关闭"""
        gate = self.keeper.check_procurement_gate(is_user_request=False)
        self.assertFalse(gate["ok"])
        self.assertIn("关闭", gate["reason"])

    def test_gate_open_with_task(self):
        """有活跃任务时采购闸门开放"""
        self.keeper.create_task("测试任务", "unit")
        gate = self.keeper.check_procurement_gate(is_user_request=False)
        self.assertTrue(gate["ok"])

    def test_gate_open_user_request(self):
        """用户显式请求时闸门开放"""
        gate = self.keeper.check_procurement_gate(is_user_request=True)
        self.assertTrue(gate["ok"])

    # ─── 采购请求提交测试 ───

    def test_submit_request_horse(self):
        """马提交采购请求→应进入monkey审批"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="horse",
            procurement_type="web_search",
            requirement="查询AI最新进展",
            keeper=self.keeper
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["reviewer"], "monkey")
        self.assertIn("request_id", r)

    def test_submit_request_patrol(self):
        """巡检者提交采购请求→应进入monkey审批"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="patrol",
            procurement_type="knowledge",
            requirement="查找知识库中关于LLM的内容",
            keeper=self.keeper
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["reviewer"], "monkey")

    def test_submit_request_monkey(self):
        """猴子提交采购请求→应进入horse+patrol审批"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="monkey",
            procurement_type="skill",
            requirement="需要安装代码审查Skill",
            keeper=self.keeper
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["reviewer"], "horse+patrol")

    def test_submit_request_no_task_rejected(self):
        """无活跃任务时提交采购请求应被拒绝"""
        r = self.purchaser.submit_request(
            requester_role="horse",
            procurement_type="web_search",
            requirement="查询",
            keeper=self.keeper
        )
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("gate_closed", False))

    def test_submit_invalid_role(self):
        """非法角色提交应被拒绝"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="keeper",
            procurement_type="web_search",
            requirement="查询",
            keeper=self.keeper
        )
        self.assertFalse(r["ok"])
        self.assertIn("不允许的角色", r["error"])

    def test_submit_invalid_type(self):
        """非法采购类型应被拒绝"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="horse",
            procurement_type="illegal_type",
            requirement="查询",
            keeper=self.keeper
        )
        self.assertFalse(r["ok"])

    # ─── 审批测试 ───

    def test_monkey_approve(self):
        """猴子审批通过马的需求"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="horse",
            procurement_type="web_search",
            requirement="搜索最新AI新闻",
            keeper=self.keeper
        )
        rid = r["request_id"]

        # 猴子审批通过
        review = self.purchaser.review_request(rid, "monkey", "approve", "同意搜索")
        self.assertTrue(review["ok"])
        self.assertEqual(review["status"], "approved")

    def test_monkey_reject(self):
        """猴子审批拒绝马的需求"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="horse",
            procurement_type="web_search",
            requirement="搜索",
            keeper=self.keeper
        )
        rid = r["request_id"]

        review = self.purchaser.review_request(rid, "monkey", "reject", "不需要")
        self.assertTrue(review["ok"])
        self.assertEqual(review["status"], "rejected")

    def test_horse_patrol_review_monkey_request(self):
        """猴子自己的需求: 马+巡检者都需要审批"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="monkey",
            procurement_type="skill",
            requirement="需要安装代码审查工具",
            keeper=self.keeper
        )
        rid = r["request_id"]

        # 马先批
        r1 = self.purchaser.review_request(rid, "horse", "approve", "同意")
        self.assertTrue(r1["ok"])
        # 应仍在hp_review,等待巡检者
        self.assertEqual(r1["status"], "hp_review")

        # 巡检者批
        r2 = self.purchaser.review_request(rid, "patrol", "approve", "同意")
        self.assertTrue(r2["ok"])
        # 两人都同意→approved
        self.assertEqual(r2["status"], "approved")

    def test_horse_patrol_reject_monkey_request(self):
        """猴子自己的需求: 一人拒绝即驳回"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="monkey",
            procurement_type="skill",
            requirement="安装工具",
            keeper=self.keeper
        )
        rid = r["request_id"]

        r1 = self.purchaser.review_request(rid, "horse", "reject", "不需要")
        self.assertTrue(r1["ok"])
        self.assertEqual(r1["status"], "rejected")

    def test_wrong_reviewer(self):
        """错误审批者应被拒绝"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="horse",
            procurement_type="web_search",
            requirement="搜索",
            keeper=self.keeper
        )
        rid = r["request_id"]

        # 马不能审批自己的请求(需要猴子)
        r1 = self.purchaser.review_request(rid, "horse", "approve", "自己批自己")
        self.assertFalse(r1["ok"])
        self.assertIn("需要猴子审批", r1["error"])

    # ─── 执行测试 ───

    def test_execute_search(self):
        """审批通过后执行采购"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="horse",
            procurement_type="web_search",
            requirement="最新AI论文",
            keeper=self.keeper
        )
        rid = r["request_id"]

        # 审批通过
        self.purchaser.review_request(rid, "monkey", "approve", "同意")

        # 执行
        result = self.purchaser.execute_request(rid)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "completed")
        self.assertIn("data", result)

    def test_execute_not_approved(self):
        """未审批通过不能执行"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="horse",
            procurement_type="web_search",
            requirement="搜索",
            keeper=self.keeper
        )
        rid = r["request_id"]

        result = self.purchaser.execute_request(rid)
        self.assertFalse(result["ok"])
        self.assertIn("不允许执行", result["error"])

    # ─── 查询测试 ───

    def test_get_request_status(self):
        """查询采购请求状态"""
        self.keeper.create_task("测试", "unit")
        r = self.purchaser.submit_request(
            requester_role="horse",
            procurement_type="skill",
            requirement="安装翻译工具",
            keeper=self.keeper
        )
        rid = r["request_id"]

        status = self.purchaser.get_request_status(rid)
        self.assertTrue(status["ok"])
        self.assertEqual(status["request"]["requester_role"], "horse")
        self.assertEqual(status["request"]["procurement_type"], "skill")

    def test_list_requests(self):
        """按角色列出请求"""
        self.keeper.create_task("测试", "unit")
        self.purchaser.submit_request(
            requester_role="horse", procurement_type="web_search",
            requirement="搜索", keeper=self.keeper
        )
        self.purchaser.submit_request(
            requester_role="patrol", procurement_type="knowledge",
            requirement="查询", keeper=self.keeper
        )

        horse_reqs = self.purchaser.list_my_requests(role="horse")
        self.assertEqual(horse_reqs["count"], 1)

        all_reqs = self.purchaser.list_my_requests()
        self.assertEqual(all_reqs["count"], 2)


class TestProcurementDB(unittest.TestCase):
    """采购数据库表结构测试"""

    def test_procurement_table_exists(self):
        """procurement_requests表应自动创建"""
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test.db")
        db = FakeEngineDB(db_path)
        config = FakeConfig()
        p = Purchaser(config, db)

        conn = db.cognition_conn()
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='procurement_requests'"
            ).fetchall()
            self.assertEqual(len(rows), 1)
        finally:
            conn.close()

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_procurement_table_schema(self):
        """验证表结构包含必要的列"""
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test.db")
        db = FakeEngineDB(db_path)
        config = FakeConfig()
        p = Purchaser(config, db)

        conn = db.cognition_conn()
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(procurement_requests)").fetchall()]
            required = ["id", "requester_role", "procurement_type", "requirement",
                        "status", "reviewer", "review_comment", "result", "task_id"]
            for c in required:
                self.assertIn(c, cols, f"缺少列: {c}")
        finally:
            conn.close()

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
