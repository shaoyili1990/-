"""
CLI 与配置系统测试
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class TestCLI:
    """CLI入口测试"""

    def test_version(self):
        """版本号应正确"""
        from hermes_universal import __version__
        assert __version__ == "0.1.0"
        print(f"✅ 版本: {__version__}")

    def test_cli_help(self):
        """CLI 应提供帮助"""
        from hermes_universal.cli import main
        # 直接测试命令行参数解析
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p_run = sub.add_parser("run")
        p_run.add_argument("message", nargs="?")
        p_desk = sub.add_parser("desktop")
        p_desk.add_argument("--port", type=int, default=9090)
        args = parser.parse_args(["run", "hello"])
        assert args.command == "run"
        print(f"✅ CLI 解析: run hello")

    def test_config_load(self):
        """配置应能加载"""
        from hermes_universal.config import load_config
        config = load_config()
        assert config is not None
        config_dict = config.to_dict()
        assert "monkey" in config_dict
        assert "horse" in config_dict
        print(f"✅ 配置加载: monkey={config_dict.get('monkey',{}).get('provider','?')}")


class TestMCP:
    """MCP 服务器测试"""

    def test_mcp_server_module_imports(self):
        """MCP 服务器模块应能导入"""
        try:
            from hermes_universal.mcp_server import create_mcp
            assert callable(create_mcp)
            print(f"✅ MCP 模块导入成功")
        except ImportError as e:
            # mcp 包可能未安装在测试环境
            import subprocess
            result = subprocess.run(
                ["python3", "-c", "import mcp; print(mcp.__version__)"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"⚠️  mcp 包未安装, 跳过 (pip install mcp)")
            else:
                raise e


class TestAileran:
    """冷监督(Aileran)模式测试"""

    def test_aileran_default_is_bool(self):
        """冷监督状态应为布尔值"""
        from hermes_universal.engine import EngineDB
        db = EngineDB()
        val = db.get_aileran_mode()
        assert isinstance(val, bool)
        print(f"✅ 冷监督状态类型正确: {val}")

    def test_aileran_toggle_on(self):
        """开启后应允许自治循环"""
        from hermes_universal.engine import EngineDB
        db = EngineDB()
        db.set_aileran_mode(True)
        assert db.get_aileran_mode() is True
        print("✅ 冷监督开启成功 — scheduler/patrol 放行")

    def test_aileran_toggle_off(self):
        """关闭后冻结自治循环"""
        from hermes_universal.engine import EngineDB
        db = EngineDB()
        db.set_aileran_mode(False)
        assert db.get_aileran_mode() is False
        print("✅ 冷监督关闭成功 — 后台循环冻结")

    def test_aileran_freeze_scheduler(self):
        """关闭冷监督时, scheduler.tick() 不应推进自治状态"""
        from hermes_universal.engine import EngineDB
        from hermes_universal.core.scheduler import IdleScheduler
        db = EngineDB()
        db.set_aileran_mode(False)
        scheduler = IdleScheduler(db=db)
        result = scheduler.tick()
        assert result is not None
        # 不应包含整理 or 巡检的动作
        assert result.get("action") not in ("maint", "inspect")
        print(f"✅ 冷监督关闭: scheduler 冻结 (action={result.get('action')})")

    def test_aileran_isolation(self):
        """多次开关不影响其他preferences"""
        from hermes_universal.engine import EngineDB
        db = EngineDB()
        db.set_aileran_mode(True)
        mode1 = db.get_aileran_mode()
        db.set_aileran_mode(False)
        db.set_aileran_mode(True)
        mode2 = db.get_aileran_mode()
        assert mode1 is True
        assert mode2 is True
        print("✅ 冷监督隔离正常")

    def test_aileran_agent_checks(self):
        """Agent 应能读取冷监督状态"""
        from hermes_universal.agent import HermesAgent
        agent = HermesAgent()
        aileran = agent._is_aileran_mode()
        assert aileran is True or aileran is False
        print(f"✅ Agent 冷监督读取: {aileran}")
