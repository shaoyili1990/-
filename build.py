"""
Hermes Agent — Windows 安装包构建脚本
用于通过 SignPath Foundation 签名
"""
import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"


def clean():
    """清理旧的构建输出"""
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)


def build():
    """使用 PyInstaller 打包为单文件 exe"""
    clean()
    print("📦 Hermes Agent Windows 构建中…")

    # 确保依赖
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyinstaller"],
        check=True, capture_output=True
    )

    # 入口
    entry = PROJECT_ROOT / "hermes_universal" / "__main__.py"

    pyinstaller_args = [
        "pyinstaller",
        "--onefile",                    # 单文件 exe
        "--name", "hermes-agent",
        "--distpath", str(DIST_DIR),
        "--workpath", str(PROJECT_ROOT / "build" / "pyi"),
        "--specpath", str(PROJECT_ROOT / "build"),
        "--console",                   # 控制台窗口（调试用，可改为 --windowed）
        "--add-data", f"{PROJECT_ROOT / 'hermes_universal' / 'desktop' / 'templates'}{os.pathsep}templates",
        "--add-data", f"{PROJECT_ROOT / 'hermes_universal' / 'desktop' / 'static'}{os.pathsep}static",
        "--hidden-import", "hermes_universal",
        "--hidden-import", "hermes_universal.engine",
        "--hidden-import", "hermes_universal.core.patrol",
        "--hidden-import", "hermes_universal.tools.agent_reach",
        "--hidden-import", "agent_reach",
        "--collect-all", "hermes_universal",
        str(entry),
    ]

    result = subprocess.run(pyinstaller_args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ 构建失败: {result.stderr}")
        sys.exit(1)

    # 输出
    exe_path = DIST_DIR / "hermes-agent.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"✅ 构建成功: {exe_path} ({size_mb:.1f} MB)")
    else:
        print("❌ 未找到输出文件")
        sys.exit(1)

    return exe_path


if __name__ == "__main__":
    build()
