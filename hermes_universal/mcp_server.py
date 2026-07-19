"""
Monkey Harness Agent — MCP Server
===================================
Streamable HTTP + stdio 双模式 MCP 服务端

暴露能力:
  - patrol_status       巡逻系统状态
  - patrol_trigger      触发巡逻
  - patrol_categories   巡逻门类评分
  - skill_list          列出可用 Skill
  - skill_run           执行 Skill
  - graph_query         知识图谱查询
  - agent_status        系统整体状态

用法:
  # stdio 模式（Claude Desktop）
  python -m hermes_universal.mcp_server

  # Streamable HTTP 模式（OpenClaw/Hermes/远程）
  python -m hermes_universal.mcp_server --transport http --port 8000
"""
import argparse
import json
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp_server")


# ── 懒加载 ──
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        from hermes_universal.agent import HermesAgent
        _agent = HermesAgent()
    return _agent


def create_mcp(host: str = "127.0.0.1", port: int = 8000) -> FastMCP:
    """创建 FastMCP 实例并注册所有工具"""
    mcp = FastMCP(
        "Monkey Harness Agent",
        instructions="""
猿驭多源，AI自治巡逻 — 多模态智能体系统。

通过 MCP 协议暴露的核心能力：
• 巡逻系统：11门类自治联网搜索评分（AI前沿/科技/时事/人文等）
• 技能执行：翻译/搜索/图片/文件解析/摘要/图表
• 知识图谱：6种节点类型·9种边关系的力导向图
• 系统状态：子链调度器·状态机·记忆系统
        """,
        host=host,
        port=port,
    )

    # ── 巡逻工具 ──

    @mcp.tool()
    def patrol_status() -> str:
        """获取巡逻系统整体状态：门类总数、已评分数、Tier分布"""
        agent = _get_agent()
        status = agent.patrol.get_status()
        return json.dumps(status, ensure_ascii=False, indent=2)

    @mcp.tool()
    def patrol_trigger(force: bool = True) -> str:
        """触发完整一轮巡逻（11门类逐次执行+评分）

        Args:
            force: 是否强制跳过空闲检查（默认 True）
        """
        agent = _get_agent()
        results = []
        start = agent.patrol.tick(force_patrol=force)
        results.append(start)
        for _ in range(50):
            r = agent.patrol.tick()
            results.append(r)
            if r.get("action") in ("scoring_complete", "idle"):
                break
        return json.dumps(results, ensure_ascii=False, indent=2)

    @mcp.tool()
    def patrol_categories() -> str:
        """获取11个巡逻门类的评分、Tier、内容量等详细信息"""
        agent = _get_agent()
        status = agent.patrol.get_status()
        cats = sorted(
            status.get("categories", []),
            key=lambda x: x.get("score", 0), reverse=True
        )
        return json.dumps(cats, ensure_ascii=False, indent=2)

    # ── Skill 工具 ──

    @mcp.tool()
    def skill_list() -> str:
        """列出所有已安装的 Skill 及其描述"""
        conn = _get_agent().db.cognition_conn()
        if not conn:
            return "[]"
        rows = conn.execute(
            "SELECT id, name, icon, category, description FROM installed_skills WHERE enabled=1"
        ).fetchall()
        conn.close()
        skills = [dict(r) for r in rows]
        return json.dumps(skills, ensure_ascii=False, indent=2)

    @mcp.tool()
    def skill_run(skill_id: str, params: str = "{}") -> str:
        """执行一个 Skill

        Args:
            skill_id: Skill ID（使用 skill_list 获取）
            params: JSON 参数字符串
        """
        try:
            params_dict = json.loads(params)
        except json.JSONDecodeError:
            return f'{{"error": "参数不是有效 JSON", "params_received": "{params}"}}'

        agent = _get_agent()
        try:
            result = agent.run_skill(skill_id, **params_dict)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except AttributeError:
            return f'{{"error": "Agent 不支持 run_skill 方法", "skill_id": "{skill_id}"}}'

    # ── 知识图谱工具 ──

    @mcp.tool()
    def graph_query(type: Optional[str] = None, search: Optional[str] = None) -> str:
        """查询知识图谱节点和边

        Args:
            type: 节点类型过滤（task/skill/role/api/patrol/ticket），留空返回全部
            search: 节点名称搜索关键词
        """
        from hermes_universal.desktop.app import create_app
        from starlette.testclient import TestClient

        app = create_app(_get_agent())
        client = TestClient(app)
        resp = client.get("/api/graph")
        if resp.status_code != 200:
            return f'{{"error": "图谱API错误", "status": {resp.status_code}}}'

        data = resp.json()
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        if type:
            nodes = [n for n in nodes if n.get("type") == type]
        if search:
            search_lower = search.lower()
            nodes = [
                n for n in nodes
                if search_lower in n.get("label", "").lower()
                or search_lower in n.get("id", "").lower()
            ]

        node_ids = {n["id"] for n in nodes}
        edges = [e for e in edges if e["source"] in node_ids and e["target"] in node_ids]

        return json.dumps({
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "all_types": sorted(set(n.get("type") for n in data.get("nodes", []))),
        }, ensure_ascii=False, indent=2)

    # ── 系统工具 ──

    @mcp.tool()
    def agent_status() -> str:
        """获取系统整体状态：角色、子链数、任务数、调度器"""
        agent = _get_agent()
        try:
            status = agent.get_status()
            return json.dumps(status, ensure_ascii=False, indent=2)
        except AttributeError:
            return json.dumps({
                "info": "Monkey Harness Agent (弼马温 Agent)",
                "version": "0.1.0",
                "architecture": "灵猴→质检→骏马→司库→书童→采购",
            }, ensure_ascii=False, indent=2)

    @mcp.tool()
    def agent_config() -> str:
        """获取当前配置（脱敏 API Key）"""
        agent = _get_agent()
        cfg = agent.config.to_dict()
        for role in ("monkey", "horse"):
            key = cfg.get(role, {}).get("api_key", "")
            if key and len(key) > 8:
                cfg[role]["api_key"] = key[:4] + "****" + key[-4:]
            elif key:
                cfg[role]["api_key"] = "****"
        return json.dumps(cfg, ensure_ascii=False, indent=2)

    return mcp


def main():
    parser = argparse.ArgumentParser(
        description="Monkey Harness Agent — MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # Claude Desktop（stdio 模式，默认）
  monkey-harness-mcp

  # 远程 HTTP 服务（OpenClaw/Hermes 直连）
  monkey-harness-mcp --transport http --port 8000

  # 指定主机（需要外部访问时）
  monkey-harness-mcp --transport http --host 0.0.0.0 --port 8000

  # 测试连接
  curl -X POST http://localhost:8000/mcp \\
    -H "Content-Type: application/json" \\
    -d '{"jsonrpc":"2.0","method":"tools/list","id":"1"}'
        """,
    )
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="传输协议（默认 stdio，HTTP 模式需 --transport http）",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP 监听地址")
    parser.add_argument("--port", "-p", type=int, default=8000, help="HTTP 端口")
    parser.add_argument("--debug", action="store_true", help="调试模式")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 根据参数创建 MCP 实例
    mcp = create_mcp(host=args.host, port=args.port)

    if args.transport in ("http", "sse"):
        transport = "streamable-http" if args.transport == "http" else "sse"
        logger.info(
            f"🚀 Monkey Harness Agent MCP Server ({args.transport})\n"
            f"   监听: http://{args.host}:{args.port}/mcp\n"
            f"   测试: curl -X POST http://{args.host}:{args.port}/mcp "
            '-H "Content-Type: application/json" '
            '-d \'{"jsonrpc":"2.0","method":"tools/list","id":"1"}\''
        )
        mcp.run(transport=transport)
    else:
        logger.info("🚀 Monkey Harness Agent MCP Server (stdio) — Claude Desktop 模式")
        logger.info("   在 Claude Desktop 配置中添加:")
        logger.info('    {')
        logger.info('      "mcpServers": {')
        logger.info('        "monkey-harness-agent": {')
        logger.info('          "command": "monkey-harness-mcp"')
        logger.info('        }')
        logger.info('      }')
        logger.info('    }')
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
