#!/usr/bin/env python3
"""
Monkey Harness Agent - Cross-Platform Build Script
Builds standalone executables for Windows, Linux
Usage:
  python build.py              # Build for current platform
  python build.py --all        # Build for all platforms (requires cross-compilation tools)
  python build.py --windows    # Build Windows .exe
  python build.py --linux      # Build Linux binary
"""
import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
BUILD_DIR = PROJECT_DIR / "build"
DIST_DIR = PROJECT_DIR / "dist"
INSTALLER_DIR = PROJECT_DIR / "installer"


def check_dependencies():
    """Check build dependencies"""
    try:
        import PyInstaller  # noqa
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller"]
        )


def build_windows():
    """Build Windows standalone executable"""
    print("=== Building Windows executable ===")
    check_dependencies()

    icon_path = str(INSTALLER_DIR / "monkey-harness.ico") if (INSTALLER_DIR / "hermes.ico").exists() else None

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "monkey-harness-agent",
        "--onefile",
        "--add-data", f"{PROJECT_DIR / 'hermes_universal'}{os.pathsep}hermes_universal",
        "--add-data", f"{PROJECT_DIR / 'fingerprints'}{os.pathsep}fingerprints",
        "--add-data", f"{PROJECT_DIR / 'subchains'}{os.pathsep}subchains",
        "--add-data", f"{PROJECT_DIR / 'config.yaml'}{os.pathsep}.",
        "--hidden-import", "uvicorn",
        "--hidden-import", "fastapi",
        "--hidden-import", "jinja2",
        "--hidden-import", "yaml",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        str(PROJECT_DIR / "hermes_universal" / "__main__.py"),
    ]
    if icon_path:
        cmd.extend(["--icon", icon_path])

    subprocess.check_call(cmd)
    print(f"Windows build complete: {DIST_DIR / 'monkey-harness-agent.exe'}")


def build_linux():
    """Build Linux standalone binary"""
    print("=== Building Linux binary ===")
    check_dependencies()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "monkey-harness-agent",
        "--onefile",
        "--add-data", f"{PROJECT_DIR / 'hermes_universal'}{os.pathsep}hermes_universal",
        "--add-data", f"{PROJECT_DIR / 'fingerprints'}{os.pathsep}fingerprints",
        "--add-data", f"{PROJECT_DIR / 'subchains'}{os.pathsep}subchains",
        "--add-data", f"{PROJECT_DIR / 'config.yaml'}{os.pathsep}.",
        "--hidden-import", "uvicorn",
        "--hidden-import", "fastapi",
        "--hidden-import", "jinja2",
        "--hidden-import", "yaml",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        str(PROJECT_DIR / "hermes_universal" / "__main__.py"),
    ]

    subprocess.check_call(cmd)

    # Optional: Create AppImage
    binary_path = DIST_DIR / "hermes-agent"
    if binary_path.exists():
        print(f"Linux build complete: {binary_path}")
        print("Tip: Use `appimagetool` to create an AppImage for distribution")
    else:
        print("Linux build may have failed - check output above")


def create_windows_installer():
    """Create Windows installer using NSIS or Inno Setup"""
    print("=== Creating Windows Installer ===")

    nsis_script = INSTALLER_DIR / "installer.nsi"
    if not nsis_script.exists():
        # Create NSIS script
        nsis_content = f"""!include "MUI2.nsh"

Name "Monkey Harness Agent"
OutFile "{DIST_DIR / 'MonkeyHarness-Setup.exe'}"
InstallDir "$PROGRAMFILES\\MonkeyHarness"
RequestExecutionLevel admin

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "{DIST_DIR}\\hermes-agent\\*.*"
  File "{PROJECT_DIR}\\SKILL.md"
  File "{PROJECT_DIR}\\config.yaml"

  CreateDirectory "$INSTDIR\\fingerprints"
  CreateDirectory "$INSTDIR\\subchains"
  CreateDirectory "$INSTDIR\\store"

  CreateShortCut "$DESKTOP\\Monkey Harness.lnk" "$INSTDIR\\monkey-harness-agent.exe"
  CreateDirectory "$SMPROGRAMS\\Monkey Harness"
  CreateShortCut "$SMPROGRAMS\\Monkey Harness\\Monkey Harness.lnk" "$INSTDIR\\monkey-harness-agent.exe"

  WriteUninstaller "$INSTDIR\\uninstall.exe"
SectionEnd

Section "Uninstall"
  RMDir /r "$INSTDIR"
  Delete "$DESKTOP\\Monkey Harness.lnk"
  RMDir /r "$SMPROGRAMS\\Monkey Harness"
SectionEnd
"""
        nsis_script.write_text(nsis_content, encoding="utf-8")

    try:
        subprocess.check_call(["makensis", str(nsis_script)])
        print(f"Windows installer created: {DIST_DIR / 'MonkeyHarness-Setup.exe'}")
    except FileNotFoundError:
        print("NSIS not found. Install NSIS from: https://nsis.sourceforge.io/")
        print("Or use the standalone executable directly.")


def create_linux_appimage():
    """Create Linux AppImage"""
    print("=== Creating Linux AppImage ===")
    appdir = BUILD_DIR / "MonkeyHarness.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)

    # Create AppDir structure
    (appdir / "usr" / "bin").mkdir(parents=True, exist_ok=True)
    (appdir / "usr" / "lib").mkdir(parents=True, exist_ok=True)

    # Copy binary
    binary_src = DIST_DIR / "monkey-harness-agent"
    if binary_src.exists():
        shutil.copy2(binary_src, appdir / "usr" / "bin" / "monkey-harness-agent")

    # Create desktop entry
    desktop_entry = """[Desktop Entry]
Name=Monkey Harness Agent
Comment=通用可移植AI Agent系统
Exec=monkey-harness-agent
Icon=monkey-harness
Terminal=true
Type=Application
Categories=Utility;Development;
"""
    (appdir / "monkey-harness-agent.desktop").write_text(desktop_entry, encoding="utf-8")
    (appdir / "usr" / "share" / "applications").mkdir(parents=True, exist_ok=True)
    shutil.copy2(appdir / "monkey-harness-agent.desktop", appdir / "usr" / "share" / "applications" / "hermes-agent.desktop")

    print(f"AppImage structure created at: {appdir}")
    print("Run `appimagetool` to create the final AppImage:")
    print(f"  appimagetool {appdir} {DIST_DIR / 'MonkeyHarness-x86_64.AppImage'}")


def create_android_install():
    """Create Android Termux install script"""
    print("=== Creating Android install script ===")
    termux_script = INSTALLER_DIR / "install_android.sh"
    termux_content = """#!/data/data/com.termux/files/usr/bin/bash
# Monkey Harness Agent - Android Termux Installer
# 在 Termux 中运行此脚本以安装 Monkey Harness Agent

echo "=== Monkey Harness Agent - Android Install ==="
echo ""

# 更新包管理器
echo "[1/5] 更新包管理器..."
pkg update -y

# 安装依赖
echo "[2/5] 安装依赖..."
pkg install -y python clang openssl git

# 升级pip
echo "[3/5] 升级pip..."
pip install --upgrade pip

# 安装Monkey Harness Agent
echo "[4/5] 安装Monkey Harness Agent..."
pip install monkey-harness-agent

# 验证安装
echo "[5/5] 验证安装..."
monkey-harness --version

echo ""
echo "=== 安装完成! ==="
echo "使用方法:"
echo "  hermes run \"你的问题\"    # 单次对话"
echo "  monkey-harness chat               # 交互模式"
echo "  monkey-harness desktop             # 桌面Web UI (需要安装Termux:X11)"
echo ""
echo "配置API Key:"
echo "  export OPENAI_API_KEY=sk-xxx"
echo "  export DEEPSEEK_API_KEY=sk-xxx"
echo "  hermes run \"Hello\""
"""
    termux_script.write_text(termux_content, encoding="utf-8")
    os.chmod(termux_script, 0o755)
    print(f"Android install script created: {termux_script}")


def build_pip_package():
    """Build pip installable package"""
    print("=== Building pip package ===")
    subprocess.check_call(
        [sys.executable, "-m", "build", str(PROJECT_DIR)],
        cwd=str(PROJECT_DIR)
    )
    print(f"Pip package built in: {PROJECT_DIR / 'dist'}")


def main():
    if "--all" in sys.argv:
        print("Building for all platforms...")
        if platform.system() == "Windows":
            build_windows()
            create_windows_installer()
        else:
            build_linux()
            create_linux_appimage()
        create_android_install()
        build_pip_package()
        return

    if "--windows" in sys.argv:
        build_windows()
        create_windows_installer()
        return

    if "--linux" in sys.argv:
        build_linux()
        create_linux_appimage()
        return

    if "--android" in sys.argv:
        create_android_install()
        return

    if "--pip" in sys.argv:
        build_pip_package()
        return

    # Default: build for current platform + android script
    print(f"Building for current platform: {platform.system()}")
    if platform.system() == "Windows":
        build_windows()
        create_windows_installer()
    else:
        build_linux()
        create_linux_appimage()

    create_android_install()
    print("\n=== All builds complete! ===")
    print(f"Output directory: {DIST_DIR}")


if __name__ == "__main__":
    main()
