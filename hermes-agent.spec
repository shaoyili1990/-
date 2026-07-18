# -*- mode: python ; coding: utf-8 -*-
"""
Hermes Agent Universal - PyInstaller Spec
单 spec 文件驱动 Linux/macOS/Windows 三平台
"""
import os
import sys
import platform
from pathlib import Path

PROJECT_DIR = os.getcwd()
INSTALLER_DIR = os.path.join(PROJECT_DIR, "installer")
ASSETS = {
    "fingerprints": os.path.join(PROJECT_DIR, "fingerprints"),
    "subchains": os.path.join(PROJECT_DIR, "subchains"),
    "validations": os.path.join(PROJECT_DIR, "validations"),
    "store": os.path.join(PROJECT_DIR, "store"),
    "config.yaml": os.path.join(PROJECT_DIR, "config.yaml"),
    "SKILL.md": os.path.join(PROJECT_DIR, "SKILL.md"),
}

# 平台相关图标
SYSTEM = platform.system()
if SYSTEM == "Windows":
    icon_path = os.path.join(INSTALLER_DIR, "hermes.ico")
elif SYSTEM == "Darwin":
    icon_path = os.path.join(INSTALLER_DIR, "hermes-app.icns")
else:
    icon_path = None  # Linux 用 SVG

a = Analysis(
    ['hermes_universal/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        (ASSETS["fingerprints"], "fingerprints"),
        (ASSETS["subchains"], "subchains"),
        (ASSETS["validations"], "validations"),
        (ASSETS["store"], "store"),
        (ASSETS["config.yaml"], "."),
        (ASSETS["SKILL.md"], "."),
        (os.path.join(PROJECT_DIR, "hermes_universal", "desktop", "templates"),
         "hermes_universal/desktop/templates"),
    ],
    hiddenimports=[
        "uvicorn", "fastapi", "jinja2", "yaml",
        "python_multipart", "PIL", "httpx",
        "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
        "uvicorn.protocols", "uvicorn.protocols.http.auto",
        "uvicorn.middleware", "uvicorn.middleware.proxy_headers",
        "starlette", "starlette.routing", "starlette.middleware",
        "starlette.middleware.cors", "starlette.staticfiles",
        "starlette.templating",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "scipy", "numpy",
        "pandas", "notebook", "IPython", "setuptools", "pip",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

# macOS: 构建 .app bundle (带图标)
if SYSTEM == "Darwin":
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name='hermes-agent',
        debug=False, bootloader_ignore_signals=False,
        strip=False, upx=True, upx_exclude=[],
        runtime_tmpdir=None, console=True,
        disable_windowed_traceback=False, argv_emulation=False,
        target_arch=None, codesign_identity=None, entitlements_file=None,
        icon=icon_path,
    )
    app = BUNDLE(
        exe, a.binaries, a.datas, [],
        name='hermes-agent.app',
        icon=icon_path, bundle_identifier='io.hermes.agent',
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name='hermes-agent',
        debug=False, bootloader_ignore_signals=False,
        strip=False, upx=True, upx_exclude=[],
        runtime_tmpdir=None, console=True,
        disable_windowed_traceback=False, argv_emulation=False,
        target_arch=None, codesign_identity=None, entitlements_file=None,
        icon=icon_path,
    )
