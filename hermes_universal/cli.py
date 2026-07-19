"""
Monkey Harness Agent (弼马温 Agent) - CLI 命令行
支持: run / chat / desktop / mcp / task / config 子命令
"""

import sys
import os
import argparse
import json
from pathlib import Path
from typing import Optional


def main():
    """CLI入口"""
    parser = argparse.ArgumentParser(
        description="Monkey Harness Agent / 弼马温 Agent — 猴驭多源，AI自治巡逻",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  monkey-harness run "今天AI有什么新闻"     # 运行一次
  monkey-harness chat                       # 交互式对话
  monkey-harness desktop                    # 启动Web UI
  monkey-harness mcp                        # 启动MCP服务器
  monkey-harness task list                  # 查看任务

兼容命令:
  hermes run "你好"                         # 旧名也支持
  bimawen run "你好"                        # 中文名也支持

环境变量:
  HERMES_MONKEY_KEY      灵猴API Key
  HERMES_HORSE_KEY       骏马API Key
        """
    )

    sub = parser.add_subparsers(dest="command", help="子命令")

    # run
    p_run = sub.add_parser("run", help="运行一次对话")
    p_run.add_argument("message", nargs="?", default="你好", help="输入消息")
    p_run.add_argument("--images", nargs="*", help="图片路径列表")
    p_run.add_argument("--stream", action="store_true", help="流式输出")

    # chat
    sub.add_parser("chat", help="交互式对话")

    # desktop
    p_desk = sub.add_parser("desktop", help="启动桌面版Web UI")
    p_desk.add_argument("--port", type=int, default=9090, help="端口号")
    p_desk.add_argument("--host", default="127.0.0.1", help="监听地址")

    # task
    p_task = sub.add_parser("task", help="任务管理")
    p_task.add_argument("action", choices=["list", "get"], default="list", nargs="?")
    p_task.add_argument("task_id", nargs="?", help="任务ID")

    # config
    p_config = sub.add_parser("config", help="配置管理")
    p_config.add_argument("action", choices=["show", "set"], default="show", nargs="?")
    p_config.add_argument("key", nargs="?", help="配置项")
    p_config.add_argument("value", nargs="?", help="配置值")

    # mcp
    p_mcp = sub.add_parser("mcp", help="启动MCP服务器")
    p_mcp.add_argument("--transport", "-t", choices=["stdio", "http", "sse"], default="stdio",
                       help="传输协议")
    p_mcp.add_argument("--host", default="127.0.0.1", help="HTTP监听地址")
    p_mcp.add_argument("--port", "-p", type=int, default=8000, help="HTTP端口")

    # version
    sub.add_parser("version", help="显示版本")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "version":
        from . import __version__
        print(f"Monkey Harness Agent v{__version__} / 弼马温 Agent")
        return

    if args.command == "mcp":
        run_mcp(args)
        return

    if args.command == "mcp":
        run_mcp(args)
        return

    if args.command == "desktop":
        run_desktop(args.host, args.port)
        return

    if args.command == "config":
        run_config(args)
        return

    if args.command == "task":
        run_task(args)
        return

    # run / chat 需要Agent
    from .agent import HermesAgent
    agent = HermesAgent()

    if args.command == "run":
        run_once(agent, args)
    elif args.command == "chat":
        run_interactive(agent)


def handle_aileran_command(cmd: str, agent) -> bool:
    """处理 /aileran on|off 命令, 返回 True 表示已处理"""
    parts = cmd.strip().lower().split()
    if len(parts) < 2 or parts[0] != "/aileran":
        return False
    if parts[1] in ("on", "1", "true", "开启", "开"):
        agent.db.set_aileran_mode(True)
        print("🧊 冷监督模式已开启 → 跳过验证链，降低 token 消耗")
    elif parts[1] in ("off", "0", "false", "关闭", "关"):
        agent.db.set_aileran_mode(False)
        print("🔥 冷监督模式已关闭 → 恢复完整验证链")
    elif parts[1] in ("show", "status", "?"):
        enabled = agent.db.get_aileran_mode()
        status = "🧊 开启" if enabled else "🔥 关闭"
        print(f"冷监督模式当前: {status}")
    else:
        print("用法: /aileran on | off | status")
    return True


def run_once(agent, args):
    """单次运行"""
    # 处理 /aileran 命令
    message = args.message or ""
    if message.startswith("/aileran"):
        handle_aileran_command(message, agent)
        return

    images = None
    if args.images:
        from .messages.content import load_image
        images = []
        for path in args.images:
            img = load_image(path)
            if img:
                images.append(img.data)

    if args.stream:
        result = agent.run(args.message, images=images, stream=True)
        if hasattr(result, '__iter__'):
            for chunk in result:
                print(chunk, end="", flush=True)
        print()
    else:
        result = agent.run(args.message, images=images)
        if isinstance(result, dict):
            output = result.get("final_output", "")
            route = result.get("route", {})
            review = result.get("review", {})

            print(f"\n[领域] {route.get('domain_name', '?')} "
                  f"({route.get('confidence', 0)*100:.0f}%) "
                  f"[路由] {route.get('route_type', '?')}")
            print("-" * 40)
            print(output)
            print("-" * 40)
            if review:
                status = "\u2713" if review.get("pass") else "\u2717"
                print(f"[审核] {status} {review.get('conclusion', '')}")
            print(f"[任务] {result.get('task_id', '')}")
        else:
            print(result)


def run_interactive(agent):
    """交互式对话"""
    print("=" * 50)
    print(" Monkey Harness Agent / 弼马温 Agent — 交互式对话")
    mode_hint = "🧊 冷监督" if agent.db.get_aileran_mode() else "🔥 完整验证"
    print(f" 输入 'exit' 退出, 'clear' 清屏, '/aileran on|off' 切换{mode_hint}")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n>>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("再见！")
            break
        if user_input.lower() == "clear":
            os.system("cls" if os.name == "nt" else "clear")
            continue
        if user_input.startswith("/aileran"):
            handle_aileran_command(user_input, agent)
            continue

        result = agent.run(user_input)
        if isinstance(result, dict):
            print(f"\n{result.get('final_output', '')}")
        else:
            print(f"\n{result}")


def run_mcp(args):
    """启动MCP服务器"""
    from .mcp_server import main as mcp_main
    import sys
    sys.argv = [sys.argv[0], "--transport", args.transport]
    if args.transport in ("http", "sse"):
        sys.argv += ["--host", args.host, "--port", str(args.port)]
    mcp_main()


def run_desktop(host: str, port: int):
    """启动桌面版"""
    try:
        from .desktop.app import create_app
        import uvicorn
    except ImportError:
        print("需要安装依赖: pip install fastapi uvicorn")
        sys.exit(1)

    app = create_app()
    print(f"\n Hermes Agent Desktop")
    print(f" 打开浏览器: http://{host}:{port}")
    print(f" 按 Ctrl+C 停止\n")
    uvicorn.run(app, host=host, port=port)


def run_config(args):
    """配置管理"""
    from .config import load_config

    if args.action == "show":
        config = load_config()
        cfg = config.to_dict()

        # 隐藏敏感信息
        for role in ("monkey", "horse"):
            if role in cfg:
                key = cfg[role].get("api_key", "")
                if key and len(key) > 8:
                    cfg[role]["api_key"] = key[:4] + "****" + key[-4:]
                elif key:
                    cfg[role]["api_key"] = "****"

        print(json.dumps(cfg, ensure_ascii=False, indent=2))

    elif args.action == "set":
        if not args.key or not args.value:
            print("用法: hermes config set <key> <value>")
            return
        # 设置环境变量（当前会话有效）
        env_key = {
            "monkey_key": "HERMES_MONKEY_KEY",
            "horse_key": "HERMES_HORSE_KEY",
            "monkey_provider": "HERMES_MONKEY_PROVIDER",
            "horse_provider": "HERMES_HORSE_PROVIDER",
            "monkey_model": "HERMES_MONKEY_MODEL",
            "horse_model": "HERMES_HORSE_MODEL",
        }.get(args.key)
        if env_key:
            os.environ[env_key] = args.value
            print(f"设置 {env_key}={args.value}")
        else:
            print(f"未知配置项: {args.key}")


def run_task(args):
    """任务管理"""
    from .engine import EngineDB

    db = EngineDB()

    if args.action == "list":
        tasks = db.list_tasks(limit=20)
        if not tasks:
            print("暂无任务")
            return
        print(f"{'任务ID':24s} {'名称':30s} {'状态':16s} {'迭代'}")
        print("-" * 80)
        for t in tasks:
            name = (t.get("name") or "")[:28]
            print(f"{t['task_id'][:22]:22s} {name:30s} {t['status']:16s} v{t.get('iteration_count',0)}")

    elif args.action == "get":
        if not args.task_id:
            print("请指定任务ID")
            return
        task = db.get_task(args.task_id)
        if task:
            print(json.dumps(task, ensure_ascii=False, indent=2))
        else:
            print(f"任务不存在: {args.task_id}")


if __name__ == "__main__":
    main()
