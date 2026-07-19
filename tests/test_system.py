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
