"""
Hermes Agent CLI - 命令行界面
支持: run / chat / desktop / task / config 子命令
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
        description="Hermes Agent Universal - 通用可移植AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  hermes run "今天天气怎么样"           # 运行一次对话
  hermes chat                            # 交互式对话
  hermes desktop                         # 启动桌面版Web UI
  hermes task list                       # 查看任务列表
  hermes config show                     # 查看配置

环境变量:
  HERMES_MONKEY_KEY      灵猴API Key
  HERMES_HORSE_KEY       骏马API Key
  HERMES_MONKEY_PROVIDER 灵猴厂商 (openai/anthropic/deepseek/ollama)
  HERMES_HORSE_PROVIDER  骏马厂商
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
    p_desk.add_argument("--port", type=int, default=8080, help="端口号")
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

    # version
    sub.add_parser("version", help="显示版本")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "version":
        from . import __version__
        print(f"Hermes Agent Universal v{__version__}")
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


def run_once(agent, args):
    """单次运行"""
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
    print(" Hermes Agent Interactive Chat")
    print(" 输入 'exit' 退出, 'clear' 清屏")
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

        result = agent.run(user_input)
        if isinstance(result, dict):
            print(f"\n{result.get('final_output', '')}")
        else:
            print(f"\n{result}")


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
