#!/usr/bin/env python3
"""Hermes Agent — Windows 打包脚本
用法:
    python build.py                          # 默认版本
    python build.py --version 0.2.0          # 指定版本
    python build.py --onefile                # 单文件exe
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def clean():
    """清理旧的构建产物"""
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
    (ROOT / "hermes_agent.spec").unlink(missing_ok=True)


def build_exe(version: str, onefile: bool):
    """用 PyInstaller 打包 Hermes Agent"""
    print(f"🔨 构建 Windows 可执行文件 v{version} (onefile={onefile})")

    # 构建入口
    entry = str(ROOT / "hermes_universal/desktop/__main__.py")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", f"hermes-agent-v{version}",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--add-data", f"{ROOT / 'hermes_universal/desktop/templates'}{os.pathsep}desktop/templates",
        "--hidden-import", "hermes_universal",
        "--hidden-import", "hermes_universal.core",
        "--hidden-import", "hermes_universal.core.patrol",
        "--hidden-import", "hermes_universal.core.scheduler",
        "--hidden-import", "hermes_universal.core.purchaser",
        "--hidden-import", "hermes_universal.core.monkey",
        "--hidden-import", "hermes_universal.core.agent",
        "--hidden-import", "flask",
        "--hidden-import", "flask_cors",
        "--collect-submodules", "hermes_universal",
        "--collect-data", "hermes_universal",
        "--noconfirm",
        entry,
    ]

    if onefile:
        cmd.insert(cmd.index("--name"), "--onefile")
    else:
        cmd.insert(cmd.index("--name"), "--onedir")

    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ 构建失败:\n{result.stderr}")
        sys.exit(1)

    print(f"✅ 构建完成: {DIST}")


def create_installer(version: str):
    """（选）后续可用 NSIS/Inno Setup 创建安装包"""
    pass


def main():
    parser = argparse.ArgumentParser(description="Hermes Agent 构建脚本")
    parser.add_argument("--version", default="0.1.0", help="版本号")
    parser.add_argument("--onefile", action="store_true", help="单文件模式")
    args = parser.parse_args()

    print(f"🚀 Hermes Agent Windows 打包 v{args.version}")
    clean()
    build_exe(args.version, args.onefile)

    # 列出产物
    for f in DIST.rglob("*"):
        if f.is_file() and f.suffix in (".exe", ".pdb"):
            mb = f.stat().st_size / (1024 * 1024)
            print(f"   📦 {f.name} ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
