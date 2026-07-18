@echo off
REM Hermes Agent Universal - Windows 安装脚本
REM 用法: 以管理员身份运行 install.bat

set HERMES_VERSION=0.1.0

echo ================================================
echo  Hermes Agent Universal v%HERMES_VERSION% 安装程序
echo  支持: Windows 10 / 11
echo ================================================
echo.

REM 检测 Python
echo [检测] 检查 Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 未找到 Python，请先安装:
    echo   https://www.python.org/downloads/
    echo   安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

python --version
echo [检测] Python 已安装

REM 检查 Python 版本
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 需要 Python 3.11 或更高版本
    pause
    exit /b 1
)

echo.
echo [1/4] 升级 pip...
python -m pip install --upgrade pip

echo.
echo [2/4] 安装依赖...
pip install httpx pyyaml fastapi uvicorn jinja2 python-multipart pillow

echo.
echo [3/4] 安装 Hermes Agent Universal...
pip install hermes-agent-universal
if %ERRORLEVEL% NEQ 0 (
    echo   pip安装失败,尝试从本地安装...
    pip install .
    if %ERRORLEVEL% NEQ 0 (
        echo [错误] 安装失败
        pause
        exit /b 1
    )
)

echo.
echo [4/4] 验证安装...
where hermes >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   hermes CLI 可用
) else (
    echo   hermes CLI 可能不在 PATH 中
    echo   请运行: python -m hermes_universal
)

echo.
echo ================================================
echo  安装完成!
echo ================================================
echo.
echo 快速开始:
echo   hermes run "你好"            # 简单对话
echo   hermes chat                   # 交互模式
echo   hermes desktop                # 桌面Web UI
echo.
echo 配置API Key:
echo   设置环境变量或在 config.yaml 中配置
echo   set OPENAI_API_KEY=sk-xxx
echo.
echo 详细文档: https://github.com/hermes-agent/universal
echo ================================================

pause
