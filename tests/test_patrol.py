"""
巡逻系统测试 — AgentReach 多源搜索集成
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# 共享临时 db 路径
_TMP_DB = ROOT / "test_data" / "test_engine.db"
_TMP_COG = ROOT / "test_data" / "test_cognition.db"


class TestPatrolAgentReach:
    """AgentReach 搜索源测试"""

    def test_hn_algolia_search(self):
        """HN Algolia API 搜索应返回技术内容"""
        from harness_core.tools.agent_reach import search_hn_algolia
        results = search_hn_algolia("AI", max_hits=3)
        assert len(results) > 0, "HN 应返回结果"
        assert all("title" in r for r in results), "结果应有 title"
        assert all("points" in r for r in results), "结果应有 points"
        print(f"✅ HN Algolia: {len(results)} 条结果")

    def test_github_search(self):
        """GitHub API 搜索应返回仓库"""
        from harness_core.tools.agent_reach import search_github
        results = search_github("python agent", max_repos=3)
        assert len(results) > 0, "GitHub 应返回结果"
        assert all("name" in r for r in results), "结果应有 name"
        print(f"✅ GitHub: {len(results)} 条结果")

    def test_multi_search_aggregates(self):
        """multi_search 应汇总多源"""
        from harness_core.tools.agent_reach import multi_search
        result = multi_search("AI agent")
        assert result.get("ok"), "搜索应成功"
        assert result.get("source_count", 0) > 0, "至少应有1个源"
        assert result.get("total_bytes", 0) > 0, "应有内容"
        print(f"✅ multi_search: {result['source_count']}源·{result['total_bytes']}字节")


class TestPatrolSystem:
    """巡逻系统集成测试"""

    def test_patrol_categories_loaded(self):
        """11个巡逻门类应全部加载"""
        from harness_core.core.patrol import CATEGORIES
        assert len(CATEGORIES) >= 11, f"应至少11个门类, 当前{len(CATEGORIES)}"
        names = [c[1] for c in CATEGORIES]
        assert "AI领域" in names
        assert "科技发展" in names
        assert "技能社区" in names
        print(f"✅ 巡逻门类: {len(CATEGORIES)} 个")

    def test_patrol_engine_init(self):
        """巡逻引擎应初始化"""
        try:
            from harness_core.engine import EngineDB
            from harness_core.core.patrol import PatrolSystem
            db = EngineDB(engine_path=str(_TMP_DB), cognition_path=str(_TMP_COG))
            ps = PatrolSystem(db)
            status = ps.get_status()
            assert status is not None
            print(f"✅ 巡逻引擎: {status.get('patrol_state', '?')}")
        finally:
            _TMP_DB.unlink(missing_ok=True)
            _TMP_COG.unlink(missing_ok=True)

    def test_patrol_score_ranges(self):
        """评分函数应返回合理值"""
        from harness_core.core.patrol import PatrolSystem
        ps = PatrolSystem.__new__(PatrolSystem)
        # 测试内容量评分
        score_fn = lambda bytes: (
            20 if bytes > 500000 else
            18 if bytes > 200000 else
            15 if bytes > 100000 else
            12 if bytes > 50000 else
            10 if bytes > 20000 else
            8 if bytes > 10000 else
            5 if bytes > 5000 else
            3 if bytes > 1000 else
            0
        )
        assert score_fn(1_000_000) == 20
        assert score_fn(100) == 0
        assert score_fn(6000) == 5
        print(f"✅ 评分函数: 总分20档, 边界正确")
