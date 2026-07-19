"""
Hermes Agent Desktop - 多模态可视化界面
FastAPI后端 + 三栏可视化HTML前端
支持：文本对话、图片理解、文件分析、流式输出、实时推理可视化
新增：多Key管理体系、提供商预设、连接测试、图谱数据API
"""

import os
import json
import uuid
import base64
import time
import mimetypes
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

import logging
logger = logging.getLogger("desktop.graph")

from ..agent import HermesAgent
from ..config import DEFAULT_CONFIG
from ..core.scheduler import IdleScheduler
from ..engine.subchain import SubchainScheduler

_agent: Optional[HermesAgent] = None


def get_agent() -> HermesAgent:
    global _agent
    if _agent is None:
        _agent = HermesAgent()
    return _agent


def get_db() -> sqlite3.Connection:
    """获取引擎数据库连接"""
    agent = get_agent()
    return agent.db.engine_conn()


def get_cognition_db() -> sqlite3.Connection:
    """获取认知数据库连接"""
    try:
        agent = get_agent()
        return agent.db.cognition_conn()
    except Exception:
        return None


def get_cognition_db():
    """获取认知数据库连接"""
    try:
        agent = get_agent()
        return agent.db.cognition_conn()
    except Exception:
        return None


# ===== 提供商预设（PromptX风格，用户选厂商→选模型→填Key→测试→保存） =====
VENDOR_PRESETS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash"],
        "docs": "https://platform.deepseek.com/api_keys",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini", "o1"],
        "docs": "https://platform.openai.com/api-keys",
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-latest", "claude-3-opus-latest"],
        "docs": "https://console.anthropic.com/",
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["openrouter/auto", "anthropic/claude-sonnet-4", "openai/gpt-4o"],
        "docs": "https://openrouter.ai/keys",
    },
    "google": {
        "name": "Google AI",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": ["gemini-2.0-flash", "gemini-2.0-pro", "gemini-1.5-pro"],
        "docs": "https://aistudio.google.com/apikey",
    },
    "ollama": {
        "name": "Ollama（本地）",
        "base_url": "http://localhost:11434",
        "models": ["llama3", "qwen2.5", "mistral", "deepseek-r1", "qwen2.5-coder"],
        "local": True,
        "docs": "https://ollama.com/download",
    },
    "vllm": {
        "name": "vLLM（本地）",
        "base_url": "http://localhost:8000/v1",
        "models": [],
        "local": True,
        "docs": "https://docs.vllm.ai/",
    },
}


def test_api_connection(vendor: str, api_key: str, base_url: str, model: str) -> Dict:
    """测试API连接 - 发送一条简单消息验证Key是否有效"""
    import httpx

    # 构建OpenAI兼容请求
    headers = {
        "Content-Type": "application/json",
    }
    
    # 不同厂商的认证头不同
    if vendor == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        url = f"{base_url.rstrip('/')}/messages"
        payload = {
            "model": model,
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "ping"}],
        }
    elif vendor == "google":
        url = f"{base_url.rstrip('/')}/models/{model}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": "ping"}]}]}
    elif vendor in ("ollama",):
        url = f"{base_url.rstrip('/')}/api/generate"
        payload = {"model": model, "prompt": "ping", "stream": False}
    else:
        # OpenAI兼容 (openai, deepseek, openrouter, vllm)
        headers["Authorization"] = f"Bearer {api_key}"
        url = f"{base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Say OK"}],
            "max_tokens": 5,
        }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            return {"ok": True, "message": "✅ 连接成功", "status": resp.status_code}
        else:
            body = resp.text[:200]
            return {"ok": False, "message": f"❌ {resp.status_code}: {body}", "status": resp.status_code}
    except Exception as e:
        return {"ok": False, "message": f"❌ 连接失败: {str(e)[:200]}", "status": 0}


def create_app(agent: Optional[HermesAgent] = None) -> FastAPI:
    global _agent
    if agent:
        _agent = agent

    app = FastAPI(title="Hermes Agent Desktop", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    agent_ref = get_agent

    # =================== 页面 ===================

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = Path(__file__).parent / "templates" / "index.html"
        if html_path.exists():
            return HTMLResponse(html_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Hermes Agent</h1><p>Loading...</p>")

    # =================== 系统状态 ===================

    @app.get("/api/status")
    async def status():
        """系统状态 + 心跳触发"""
        return agent_ref().get_status()

    @app.get("/api/status/roles")
    async def status_roles():
        return {
            "roles": [
                {"name": "Monkey", "title": "灵猴", "desc": "路由与判断", "icon": "🐵"},
                {"name": "Review", "title": "质检官", "desc": "安全与合规审查", "icon": "🔍"},
                {"name": "Horse", "title": "骏马", "desc": "推理与执行", "icon": "🐴"},
                {"name": "Purchaser", "title": "采购员", "desc": "采买与巡检", "icon": "🛒"},
                {"name": "Keeper", "title": "司库", "desc": "状态与流程管理", "icon": "💾"},
                {"name": "Scribe", "title": "书童", "desc": "认知与记忆", "icon": "📝"},
            ],
            "stats": {
                "chains": 136, "validations": 4,
                "knowledge_bases": 10, "storage": "SQLite多维表格",
            },
        }

    # =================== 提供商预设（PromptX风格） ===================

    @app.get("/api/vendors")
    async def list_vendors():
        """列出所有预设厂商及其模型"""
        return {"vendors": VENDOR_PRESETS}

    # =================== Key凭证管理 ===================

    @app.get("/api/credentials")
    async def list_credentials():
        """列出所有已保存的API Key（脱敏）"""
        conn = get_db()
        try:
            cur = conn.execute("SELECT * FROM api_credentials ORDER BY service, id")
            rows = []
            for r in cur.fetchall():
                key = r["key_value"] or ""
                masked = key[:6] + "****" + key[-4:] if len(key) > 12 else "****"
                rows.append({
                    "id": r["id"],
                    "service": r["service"],
                    "vendor": r["vendor"] or "",
                    "base_url": r["base_url"] or "",
                    "model": r["model"] or "",
                    "key_masked": masked,
                    "key_prefix": key[:8] if key else "",
                    "has_key": bool(key),
                    "is_test": bool(r["is_test"]),
                })
            return {"credentials": rows}
        finally:
            conn.close()

    @app.post("/api/credentials")
    async def add_credential(data: dict):
        """添加/更新API Key"""
        conn = get_db()
        try:
            service = data.get("service", "default")
            vendor = data.get("vendor", "")
            base_url = data.get("base_url", "")
            model = data.get("model", "")
            key_value = data.get("key_value", "")

            if not key_value:
                raise HTTPException(400, "API Key不能为空")

            # 检查是否已存在相同service+vendor的凭证
            existing = conn.execute(
                "SELECT id FROM api_credentials WHERE service=? AND vendor=? AND base_url=?",
                (service, vendor, base_url)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE api_credentials SET model=?, key_value=? WHERE id=?",
                    (model, key_value, existing["id"])
                )
                msg = "已更新"
                new_id = existing["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO api_credentials (service, vendor, base_url, model, key_value) VALUES (?,?,?,?,?)",
                    (service, vendor, base_url, model, key_value)
                )
                new_id = cur.lastrowid
                msg = "已保存"

            conn.commit()
            return {"ok": True, "id": new_id, "message": msg}
        finally:
            conn.close()

    @app.delete("/api/credentials/{cred_id}")
    async def delete_credential(cred_id: int):
        """删除Key"""
        conn = get_db()
        try:
            conn.execute("DELETE FROM api_credentials WHERE id=?", (cred_id,))
            conn.commit()
            return {"ok": True, "message": "已删除"}
        finally:
            conn.close()

    @app.post("/api/credentials/test")
    async def test_credential(data: dict):
        """测试API连接"""
        vendor = data.get("vendor", "")
        api_key = data.get("key_value", "")
        base_url = data.get("base_url", "")
        model = data.get("model", "")

        if not api_key:
            # 从已保存的凭证中读取
            cred_id = data.get("cred_id")
            if cred_id:
                conn = get_db()
                try:
                    row = conn.execute(
                        "SELECT * FROM api_credentials WHERE id=?", (cred_id,)
                    ).fetchone()
                    if row:
                        vendor = row["vendor"]
                        api_key = row["key_value"]
                        base_url = row["base_url"]
                        model = row["model"]
                finally:
                    conn.close()

        if not api_key:
            raise HTTPException(400, "缺少API Key")

        return test_api_connection(vendor, api_key, base_url, model)

    # =================== 角色-Key 分配管理 ===================

    @app.get("/api/assignments")
    async def get_assignments():
        """获取角色-Key分配关系"""
        conn = get_db()
        try:
            # 从env_config读取分配
            cur = conn.execute(
                "SELECT key, value FROM env_config WHERE key LIKE 'role_key_%'"
            )
            assignments = {}
            for r in cur.fetchall():
                role = r["key"].replace("role_key_", "")
                try:
                    assignments[role] = json.loads(r["value"])
                except:
                    assignments[role] = {"cred_id": r["value"]}

            # 读取所有角色列表
            roles = ["monkey", "horse", "purchaser"]

            result = {}
            for role in roles:
                if role in assignments:
                    cred_id = assignments[role].get("cred_id")
                    if cred_id:
                        row = conn.execute(
                            "SELECT * FROM api_credentials WHERE id=?", (cred_id,)
                        ).fetchone()
                        if row:
                            key = row["key_value"] or ""
                            masked = key[:6] + "****" + key[-4:] if len(key) > 12 else "****"
                            result[role] = {
                                "cred_id": row["id"],
                                "vendor": row["vendor"],
                                "model": row["model"],
                                "base_url": row["base_url"],
                                "key_masked": masked,
                                "has_key": True,
                            }
                            continue
                    result[role] = {"has_key": False, "vendor": "", "model": ""}
                else:
                    result[role] = {"has_key": False, "vendor": "", "model": ""}
            return {"assignments": result}
        finally:
            conn.close()

    @app.post("/api/assignments")
    async def set_assignment(data: dict):
        """设置角色-Key分配"""
        role = data.get("role", "")
        cred_id = data.get("cred_id")

        valid_roles = ["monkey", "horse", "purchaser"]
        if role not in valid_roles:
            raise HTTPException(400, f"无效角色: {role}，可选: {valid_roles}")

        conn = get_db()
        try:
            if cred_id:
                # 验证cred_id存在
                row = conn.execute(
                    "SELECT id FROM api_credentials WHERE id=?", (cred_id,)
                ).fetchone()
                if not row:
                    raise HTTPException(404, f"凭证不存在: {cred_id}")

            value = json.dumps({"cred_id": cred_id} if cred_id else {})
            conn.execute(
                "INSERT OR REPLACE INTO env_config (key, value, platform) VALUES (?, ?, 'desktop')",
                (f"role_key_{role}", value)
            )
            conn.commit()
            return {"ok": True, "message": f"已分配 {role} → credential #{cred_id}" if cred_id else f"已清除 {role} 的分配"}
        finally:
            conn.close()

    @app.post("/api/assignments/auto")
    async def auto_assign(data: dict):
        """一键分配三个Key到三个角色"""
        conn = get_db()
        try:
            cred_ids = data.get("cred_ids", {})
            results = {}
            for role in ["monkey", "horse", "purchaser"]:
                cid = cred_ids.get(role)
                if cid:
                    value = json.dumps({"cred_id": cid})
                    conn.execute(
                        "INSERT OR REPLACE INTO env_config (key, value, platform) VALUES (?, ?, 'desktop')",
                        (f"role_key_{role}", value)
                    )
                    results[role] = cid
            conn.commit()
            return {"ok": True, "assigned": results, "message": f"已分配 {len(results)} 个角色"}
        finally:
            conn.close()

    # =================== Skill桌面（动态桌面图标） ===================

    @app.get("/api/skills")
    async def list_skills():
        """列出所有已安装的Skill（含内置）"""
        built_ins = [
            {"id": "chat", "name": "对话", "icon": "💬", "desc": "多模态对话", "builtin": True, "color": "#7c6ff0"},
            {"id": "code", "name": "代码", "icon": "💻", "desc": "代码生成与审查", "builtin": True, "color": "#4ade80"},
            {"id": "image", "name": "图片", "icon": "🖼️", "desc": "图片理解与生成", "builtin": True, "color": "#f472b6"},
            {"id": "file", "name": "文件", "icon": "📎", "desc": "文件分析与处理", "builtin": True, "color": "#60a5fa"},
            {"id": "search", "name": "搜索", "icon": "🔍", "desc": "网页搜索与抓取", "builtin": True, "color": "#fbbf24"},
            {"id": "brain", "name": "认知库", "icon": "🧠", "desc": "记忆与经验管理", "builtin": True, "color": "#f87171"},
            {"id": "market", "name": "Skill市场", "icon": "🏪", "desc": "发现更多技能", "builtin": True, "color": "#a78bfa"},
        ]
        conn = get_db()
        try:
            extra = conn.execute(
                "SELECT id, name, icon, description, color, source FROM installed_skills ORDER BY installed_at"
            ).fetchall()
        except:
            extra = []
        finally:
            conn.close()
        skills = list(built_ins)
        for e in extra:
            skills.append({
                "id": e["id"], "name": e["name"], "icon": e.get("icon", "📦"),
                "desc": e.get("description", ""), "color": e.get("color", "#555"),
                "builtin": False, "source": e.get("source", ""),
            })
        return {"skills": skills, "total": len(skills)}

    # =================== 采购员 - 市场与安装管理 ===================

    def get_purchaser():
        """获取采购员实例"""
        return agent_ref().purchaser

    @app.get("/api/market/categories")
    async def market_categories():
        """市场分类"""
        p = get_purchaser()
        return {"categories": p.get_market_categories()}

    @app.get("/api/market/search")
    async def market_search(query: str = "", category: str = "", limit: int = 50):
        """搜索Skill市场"""
        p = get_purchaser()
        results = p.search_market(query=query, category=category, limit=limit)
        return {"skills": results, "total": len(results)}

    @app.post("/api/market/install")
    async def market_install(data: dict):
        """安装Skill"""
        skill_id = data.get("skill_id", "")
        if not skill_id:
            raise HTTPException(400, "缺少 skill_id")
        p = get_purchaser()
        result = p.install(skill_id)
        if result.get("ok"):
            return result
        raise HTTPException(400, result.get("message", "安装失败"))

    @app.post("/api/market/uninstall")
    async def market_uninstall(data: dict):
        """卸载Skill"""
        skill_id = data.get("skill_id", "")
        if not skill_id:
            raise HTTPException(400, "缺少 skill_id")
        p = get_purchaser()
        return p.uninstall(skill_id)

    @app.get("/api/market/installed")
    async def market_installed():
        """已安装Skill"""
        p = get_purchaser()
        skills = p.list_installed()
        return {"skills": skills, "total": len(skills)}

    @app.get("/api/market/inspect")
    async def market_inspect():
        """巡检市场更新"""
        p = get_purchaser()
        updates = p.inspect_updates()
        return {"updates": updates, "total": len(updates)}

    @app.get("/api/market/health")
    async def market_health():
        """采购员健康状态"""
        p = get_purchaser()
        return p.health_check()

    @app.post("/api/market/search-by-need")
    async def market_search_by_need(data: dict):
        """根据需求（来自猴子）搜索Skill"""
        requirement = data.get("requirement", "")
        use_ai = data.get("use_ai", True)
        if not requirement:
            raise HTTPException(400, "缺少需求描述")
        p = get_purchaser()
        results = p.search_by_requirement(requirement, use_ai=use_ai)
        return {"skills": results, "total": len(results)}

    # =================== 空闲调度器 ===================

    @app.get("/api/scheduler/status")
    async def scheduler_status():
        """调度器状态 + 心跳"""
        agent = agent_ref()
        agent.scheduler.tick(has_active_task=False)
        return agent.scheduler.get_status()

    @app.post("/api/scheduler/mark-activity")
    async def mark_activity():
        """标记用户活动(重置空闲计时)"""
        agent_ref().scheduler.tick(has_active_task=True)
        return {"ok": True}

    @app.post("/api/purchaser/organize")
    async def trigger_organize():
        """手动触发整理"""
        p = get_purchaser()
        return p.organize()

    @app.post("/api/purchaser/inspect")
    async def trigger_inspect():
        """手动触发巡检"""
        p = get_purchaser()
        return {"updates": p.inspect_updates()}

    @app.post("/api/purchaser/community-search")
    async def community_search(data: dict):
        """社区Skill搜索(智柴网等)"""
        query = data.get("query", "")
        source = data.get("source", "zhichai.net")
        if not query:
            raise HTTPException(400, "缺少搜索词")
        p = get_purchaser()
        return {"results": p.community_search(query, source=source)}

    # =================== 多门类巡逻系统 ===================

    @app.get("/api/patrol/status")
    async def patrol_status():
        """巡逻系统状态"""
        return agent_ref().patrol.get_status()

    @app.post("/api/patrol/trigger")
    async def patrol_trigger():
        """手动触发完整一轮巡逻（逐分类执行）"""
        patrol = agent_ref().patrol
        # 强制启动
        start = patrol.tick(force_patrol=True)
        results = [start]
        # 持续巡逻直到全部分类完成
        max_iter = 50
        for _ in range(max_iter):
            r = patrol.tick()
            results.append(r)
            if r.get("action") in ("scoring_complete", "idle"):
                break
        patrol._set("patrol_state", "idle")  # 完成后回到空闲
        return {"round": results, "total": len(results)}

    # =================== 图谱数据API（Obsidian风格知识图谱 v2） ===================

    @app.get("/api/graph")
    async def get_graph():
        """获取知识图谱节点和关系（全量）"""
        conn = get_db()
        try:
            nodes = []
            edges = []
            seen_ids = set()

            def add_node(nid: str, label: str, ntype: str,
                         color: str = "#7c6ff0", size: int = 1,
                         status: str = "", score: int = 0,
                         url: str = "", detail: str = ""):
                if nid not in seen_ids:
                    seen_ids.add(nid)
                    nodes.append({
                        "id": nid, "label": (label or "?")[:25],
                        "type": ntype, "color": color,
                        "size": max(5, min(30, size)),
                        "status": status, "score": score,
                        "url": url, "detail": detail,
                    })

            # ── 1. 任务节点 ──
            status_colors = {
                "待构思": "#94a3b8", "待执行": "#f59e0b",
                "执行完成待验证": "#3b82f6", "验证中": "#8b5cf6",
                "通过(验证)": "#22c55e", "失败(验证)": "#ef4444",
            }
            try:
                tasks = conn.execute(
                    "SELECT task_id, name, status FROM rnd_tasks ORDER BY created_at DESC LIMIT 30"
                ).fetchall()
                for t in tasks:
                    add_node(
                        nid=t["task_id"], label=t["name"] or "未命名",
                        ntype="task",
                        color=status_colors.get(t["status"], "#94a3b8"),
                        size=5, status=t["status"] or "?",
                    )
                # 任务间边（通过子链依赖）
                deps = conn.execute(
                    "SELECT parent_task_id, child_task_id FROM rnd_dependencies LIMIT 50"
                ).fetchall()
                for d in deps:
                    edges.append({
                        "source": d["parent_task_id"], "target": d["child_task_id"],
                        "label": "depends", "style": "dashed",
                    })
            except Exception:
                pass

            # ── 2. 角色节点（猴/马/采购/司库/书童） ──
            role_meta = {
                "monkey": {"label": "🐵 灵猴", "color": "#f59e0b"},
                "horse": {"label": "🐴 骏马", "color": "#22c55e"},
                "purchaser": {"label": "🛒 采购员", "color": "#a855f7"},
                "keeper": {"label": "🗂️ 司库", "color": "#3b82f6"},
                "scribe": {"label": "📝 书童", "color": "#06b6d4"},
                "verifier": {"label": "🔍 质检官", "color": "#ec4899"},
            }
            for key, meta in role_meta.items():
                add_node(f"role_{key}", meta["label"], "role",
                         color=meta["color"], size=8)

            # ── 3. API/供应商节点 ──
            try:
                creds = conn.execute(
                    "SELECT id, vendor, model, service FROM api_credentials"
                ).fetchall()
                vendor_colors = {
                    "openai": "#10a37f", "deepseek": "#4f46e5",
                    "anthropic": "#d97706", "google": "#4285f4",
                }
                for c in creds:
                    cdict = dict(c)
                    cid = f"cred_{cdict['id']}"
                    vendor = cdict.get("vendor", "unknown")
                    label = f"{vendor}:{cdict.get('model','?')}" if cdict.get("model") else vendor
                    add_node(cid, label, "api",
                             color=vendor_colors.get(vendor.lower(), "#60a5fa"), size=4)
                # API→角色分配边
                for c in creds:
                    cdict = dict(c)
                    assignments = conn.execute(
                        "SELECT key, value FROM env_config WHERE key LIKE 'role_key_%'"
                    ).fetchall()
                    for a in assignments:
                        ad = dict(a)
                        role = ad["key"].replace("role_key_", "")
                        try:
                            val = json.loads(ad["value"])
                            if val.get("cred_id") == cdict["id"]:
                                edges.append({
                                    "source": f"cred_{cdict['id']}",
                                    "target": f"role_{role}",
                                    "label": "uses", "style": "solid",
                                })
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"API节点加载: {e}")

            # ── 4. Skill节点（从认知DB读取） ──
            skill_count = 0
            try:
                from hermes_universal.engine import EngineDB as _EDB
                _cconn = _EDB().cognition_conn()
                if _cconn:
                    srows = _cconn.execute(
                        "SELECT id, name, icon, category, description FROM installed_skills WHERE enabled=1 LIMIT 20"
                    ).fetchall()
                    # sqlite3.Row doesn't support .get() — convert to dict
                    cat_colors = {"通用": "#6b7280", "编程": "#3b82f6", "AI": "#8b5cf6",
                                  "工具": "#f59e0b", "数据": "#22c55e", "社区": "#ec4899"}
                    for sr in srows:
                        s = dict(sr)
                        cat = s.get("category") or "通用"
                        label = f"{s.get('icon','')} {s['name']}" if s.get('icon') else s["name"]
                        add_node(f"skill_{s['id']}", label,
                                 "skill", color=cat_colors.get(cat, "#6b7280"),
                                 size=6, detail=s.get("description","")[:80])
                        skill_count += 1
                    _cconn.close()
            except Exception as e:
                logger.warning(f"Skill加载: {e}")

            # ── 5. 巡逻门类节点（11个） ──
            try:
                from hermes_universal.core.patrol import PatrolSystem, CATEGORIES
                from hermes_universal.engine import EngineDB as _EDBp
                ps = PatrolSystem(_EDBp())
                patrol_status = ps.get_status() if ps else {}
                for cat in patrol_status.get("categories", []):
                    score = cat.get("score", 0) or 0
                    tier = cat.get("current_tier", "T5")
                    heat = "ff4444" if score > 100 else ("ff8800" if score > 50 else "44aa44")
                    add_node(
                        nid=f"patrol_{cat['id']}",
                        label=f"{cat['name']} [{tier}]",
                        ntype="patrol",
                        color=f"#{heat}",
                        size=max(5, score // 5),
                        score=score,
                    )
            except Exception as e:
                logger.warning(f"图谱: 巡逻数据未加载 ({e})")

            # ── 6. Ticket/工单节点 ──
            try:
                tkts = conn.execute(
                    "SELECT number, title, status FROM tickets ORDER BY number DESC LIMIT 10"
                ).fetchall()
                for t_data in tkts:
                    tdict = dict(t_data)
                    tn = tdict["number"]
                    add_node(f"ticket_{tn}", f"#{tn} {tdict.get('title','')[:20]}",
                             "ticket",
                             color="#22d3ee" if tdict.get("status") == "open" else "#78716c",
                             size=3, status=tdict.get("status",""))
            except Exception as e:
                if "no such table" not in str(e).lower():
                    logger.warning(f"Ticket节点: {e}")

            # ── 7. 图谱关联边（智能连接 — 8种边类型） ──
            try:
                # 7a. 角色流水线边（猴→质检→马→司库→书童→采购）
                pipe = ["role_monkey", "role_verifier", "role_horse",
                        "role_keeper", "role_scribe", "role_purchaser"]
                for i in range(len(pipe)-1):
                    if pipe[i] in seen_ids and pipe[i+1] in seen_ids:
                        edges.append({"source": pipe[i], "target": pipe[i+1],
                                      "label": "→", "style": "dashed"})

                # 7b. 任务→巡逻门类（任务名匹配巡逻分类）
                #   任务名如"搜索 AI领域 最新动态: AI, 人工智能" → 映射到 patrol_ai
                patrol_cat_names = {
                    "ai": "AI领域", "current_affairs": "时事新闻",
                    "national_affairs": "国家大事", "gossip": "八卦新闻",
                    "entertainment": "综艺娱乐", "showbiz": "演艺圈",
                    "tech": "科技发展", "digital_humanities": "数字人文",
                    "history": "人文历史", "archaeology": "人文考古",
                    "skill_community": "技能社区",
                }
                task_rows = conn.execute(
                    "SELECT task_id, name FROM rnd_tasks WHERE name LIKE '%搜索%' LIMIT 30"
                ).fetchall()
                for t in task_rows:
                    tname = t["name"] or ""
                    for cid, cname in patrol_cat_names.items():
                        if cname in tname and f"patrol_{cid}" in seen_ids:
                            edges.append({
                                "source": t["task_id"],
                                "target": f"patrol_{cid}",
                                "label": "monitors", "style": "dashed",
                            })
                            break  # one task → one primary category

                # 7c. 审核→任务（rnd_reviews 关联的任务）
                revs = conn.execute(
                    "SELECT DISTINCT target_id FROM rnd_reviews LIMIT 50"
                ).fetchall()
                for r in revs:
                    tid = r["target_id"]
                    if tid in seen_ids:
                        edges.append({
                            "source": f"role_verifier",
                            "target": tid,
                            "label": "reviewed", "style": "dotted",
                        })

                # 7d. 步骤→任务（rnd_steps 的执行步骤）
                steps_data = conn.execute(
                    "SELECT DISTINCT task_id FROM rnd_steps LIMIT 50"
                ).fetchall()
                for s in steps_data:
                    tid = s["task_id"]
                    if tid in seen_ids:
                        edges.append({
                            "source": tid,
                            "target": f"role_horse",
                            "label": "executed_by", "style": "dotted",
                        })

                # 7e. 认知记忆→任务（cognition DB memories）
                try:
                    from hermes_universal.engine import EngineDB as _EDB2
                    _cc2 = _EDB2()
                    mconn = _cc2.cognition_conn()
                    if mconn:
                        mems = mconn.execute(
                            "SELECT combo_id, task FROM memories LIMIT 30"
                        ).fetchall()
                        for m in mems:
                            cid = m["combo_id"] or ""
                            # combo_id = "session-task-<task_id>" pattern
                            for tid in seen_ids:
                                if tid in cid:
                                    edges.append({
                                        "source": tid,
                                        "target": f"role_scribe",
                                        "label": "remembered_by", "style": "dotted",
                                    })
                                    break
                        mconn.close()
                except Exception:
                    pass

                # 7f. Skill→角色（每个角色使用的Skill）
                skill_role_map = {
                    "translate": ["role_scribe", "role_purchaser"],
                    "web-search": ["role_horse", "role_monkey", "role_purchaser"],
                    "image-gen": ["role_horse"],
                    "file-parse": ["role_scribe", "role_keeper"],
                    "summarize": ["role_horse", "role_scribe", "role_monkey"],
                    "data-chart": ["role_keeper", "role_horse"],
                }
                for skid, roles in skill_role_map.items():
                    sk_node = f"skill_{skid}"
                    if sk_node in seen_ids:
                        for r in roles:
                            if r in seen_ids:
                                edges.append({
                                    "source": sk_node,
                                    "target": r,
                                    "label": "serves", "style": "solid",
                                })

                # 7g. 任务→任务（同巡逻分类的搜索任务互为关联）
                task_ids_by_cat = {}
                for t in task_rows:
                    tname = t["name"] or ""
                    for cid, cname in patrol_cat_names.items():
                        if cname in tname:
                            task_ids_by_cat.setdefault(cid, []).append(t["task_id"])
                for cid, tids in task_ids_by_cat.items():
                    for i in range(len(tids)-1):
                        if tids[i] in seen_ids and tids[i+1] in seen_ids:
                            edges.append({
                                "source": tids[i], "target": tids[i+1],
                                "label": "same_category", "style": "dashed",
                            })

                # 7h. 巡逻门类→API（热度高的巡逻关联到使用的搜索API）
                if "cred_1" in seen_ids:
                    high_cats = [
                        "patrol_ai", "patrol_current_affairs",
                        "patrol_tech", "patrol_national_affairs"
                    ]
                    for pc in high_cats:
                        if pc in seen_ids:
                            edges.append({
                                "source": pc,
                                "target": "cred_1",
                                "label": "uses_search", "style": "dotted",
                            })

            except Exception as e:
                logger.warning(f"图谱关联边: {e}")

            return {"nodes": nodes, "edges": edges, "total_nodes": len(nodes), "total_edges": len(edges)}
        except Exception as e:
            logger.error(f"图谱API错误: {e}")
            return {"nodes": [], "edges": [], "error": str(e)[:100]}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @app.get("/api/graph/patrol")
    async def get_patrol_graph():
        """巡逻热度图 — 11门类关注度评分可视化"""
        try:
            from hermes_universal.core.patrol import PatrolSystem
            from hermes_universal.engine import EngineDB
            from hermes_universal.config import load_config
            cfg = load_config()
            patrol = PatrolSystem(EngineDB(
                engine_path=cfg.get("keeper", "db_path", default=""),
                cognition_path=cfg.get("scribe", "db_path", default=""),
            ))
            status = patrol.get_status()
            categories = sorted(status.get("categories", []),
                                key=lambda x: x["score"], reverse=True)
            return {
                "categories": categories,
                "tier_distribution": status.get("tier_distribution", {}),
                "total_categories": status.get("total_categories", 0),
                "scored_categories": status.get("scored_categories", 0),
            }
        except Exception as e:
            return {"error": str(e)[:100]}

    @app.get("/api/graph/skills")
    async def get_skill_graph():
        """Skill 依赖关系图（从认知DB读取）"""
        conn = get_cognition_db()
        if conn is None:
            from hermes_universal.engine import EngineDB
            conn = EngineDB().cognition_conn()
        try:
            nodes = []
            edges = []
            skills = conn.execute(
                "SELECT id, name, icon, category, description FROM installed_skills WHERE enabled=1"
            ).fetchall()
            for s in skills:
                nodes.append({
                    "id": f"skill_{s['id']}", "label": s["name"],
                    "type": "skill", "category": s["category"] or "通用",
                })
            # 市场Skill（未安装的）
            market = conn.execute(
                "SELECT id, name, category FROM skill_market WHERE id NOT IN "
                "(SELECT id FROM installed_skills WHERE enabled=1) LIMIT 10"
            ).fetchall()
            for m in market:
                nodes.append({
                    "id": f"market_{m['id']}", "label": f"📦 {m['name']}",
                    "type": "market_skill", "category": m["category"] or "通用",
                })
            return {"nodes": nodes, "edges": edges,
                    "total": len(nodes), "market_count": len(market)}
        except Exception as e:
            return {"error": str(e)[:100]}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @app.get("/api/graph/search")
    async def search_graph(q: str = ""):
        """搜索图谱节点"""
        if not q or len(q) < 2:
            return {"results": []}
        conn = get_db()
        try:
            results = []
            for table, id_col, name_col, ntype in [
                ("rnd_tasks", "task_id", "name", "task"),
                ("installed_skills", "id", "name", "skill"),
            ]:
                try:
                    rows = conn.execute(
                        f"SELECT {id_col}, {name_col} FROM {table} WHERE {name_col} LIKE ? LIMIT 5",
                        (f"%{q}%",)
                    ).fetchall()
                    for r in rows:
                        results.append({
                            "id": r[id_col], "label": r[name_col], "type": ntype,
                        })
                except Exception:
                    pass
            return {"query": q, "results": results}
        finally:
            conn.close()

    # =================== 对话接口 ===================

    @app.post("/api/chat")
    async def chat(
        message: str = Form(...),
        images: Optional[str] = Form(None),
        files_data: Optional[str] = Form(None),
    ):
        start_time = time.time()
        image_list = None
        if images:
            try:
                image_list = json.loads(images)
            except:
                pass
        file_list = None
        if files_data:
            try:
                file_list = json.loads(files_data)
            except:
                pass

        result = agent_ref().run(message, images=image_list)
        elapsed = time.time() - start_time

        if isinstance(result, dict):
            route_info = result.get("route", {})
            review_info = result.get("review", {})
            return {
                "task_id": result.get("task_id", str(uuid.uuid4())),
                "response": result.get("final_output", ""),
                "route": route_info.get("domain_name", "通用") if isinstance(route_info, dict) else str(route_info),
                "route_type": route_info.get("route_type", "") if isinstance(route_info, dict) else "",
                "route_confidence": route_info.get("confidence", 0) if isinstance(route_info, dict) else 0,
                "chain": result.get("subchain", ""),
                "chain_category": result.get("chain_category", ""),
                "review": review_info.get("conclusion", "") if isinstance(review_info, dict) else "",
                "review_pass": review_info.get("pass", True) if isinstance(review_info, dict) else True,
                "status": result.get("status", "completed"),
                "elapsed": f"{elapsed:.1f}s",
            }
        return {"response": str(result), "elapsed": f"{elapsed:.1f}s"}

    @app.post("/api/chat/stream")
    async def chat_stream(message: str = Form(...), images: Optional[str] = Form(None)):
        async def generate():
            input_data = {"text": message}
            if images:
                try:
                    input_data["images"] = json.loads(images)
                except:
                    pass

            yield f"data: {json.dumps({'type':'stage','role':'monkey','status':'busy','label':'灵猴 — 路由分析'})}\n\n"
            yield f"data: {json.dumps({'type':'think','title':'🐵 灵猴 — 路由分析','sub':'判断任务类型与领域','dot':'yellow'})}\n\n"

            result = agent_ref().run(input_data, stream=True)

            yield f"data: {json.dumps({'type':'stage','role':'monkey','status':'done'})}\n\n"
            yield f"data: {json.dumps({'type':'stage','role':'review','status':'busy','label':'质检官 — 合规审查'})}\n\n"
            yield f"data: {json.dumps({'type':'think','title':'🔍 质检官 — 合规审查','sub':'安全与质量检查','dot':'purple'})}\n\n"

            yield f"data: {json.dumps({'type':'stage','role':'review','status':'done'})}\n\n"
            yield f"data: {json.dumps({'type':'stage','role':'horse','status':'busy','label':'骏马 — 推理执行'})}\n\n"
            yield f"data: {json.dumps({'type':'think','title':'🐴 骏马 — 推理执行','sub':'执行推理子链','dot':'green'})}\n\n"

            if hasattr(result, "__iter__"):
                for chunk in result:
                    if isinstance(chunk, str):
                        yield f"data: {json.dumps({'type':'chunk','content':chunk})}\n\n"

            yield f"data: {json.dumps({'type':'stage','role':'horse','status':'done'})}\n\n"
            yield f"data: {json.dumps({'type':'stage','role':'keeper','status':'busy','label':'司库 — 状态存储'})}\n\n"
            yield f"data: {json.dumps({'type':'stage','role':'keeper','status':'done'})}\n\n"
            yield f"data: {json.dumps({'type':'stage','role':'scribe','status':'busy','label':'书童 — 记忆更新'})}\n\n"
            yield f"data: {json.dumps({'type':'stage','role':'scribe','status':'done'})}\n\n"
            yield f"data: {json.dumps({'type':'stage','role':'purchaser','status':'busy','label':'采购员 — 资源检查'})}\n\n"
            yield f"data: {json.dumps({'type':'stage','role':'purchaser','status':'done'})}\n\n"
            yield f"data: {json.dumps({'type':'think','title':'✅ 全流程完成','sub':'六角色流水线通过','dot':'green'})}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    # =================== 上传 ===================

    @app.post("/api/upload")
    async def upload(file: UploadFile = File(...)):
        contents = await file.read()
        b64 = base64.b64encode(contents).decode("ascii")
        mime = file.content_type or "application/octet-stream"
        is_image = mime.startswith("image/")
        return {
            "filename": file.filename,
            "mime_type": mime,
            "size": len(contents),
            "data": b64,
            "data_uri": f"data:{mime};base64,{b64}",
            "type": "image" if is_image else "file",
        }

    @app.post("/api/upload/multi")
    async def upload_multi(files: List[UploadFile] = File(...)):
        results = []
        for f in files:
            contents = await f.read()
            b64 = base64.b64encode(contents).decode("ascii")
            mime = f.content_type or "application/octet-stream"
            results.append({"filename": f.filename, "mime_type": mime, "size": len(contents), "data_uri": f"data:{mime};base64,{b64}"})
        return {"files": results, "count": len(results)}

    @app.get("/api/tasks")
    async def list_tasks(status: Optional[str] = None, limit: int = 20):
        try:
            tasks = agent_ref().db.list_tasks(status=status, limit=limit)
            return {"tasks": tasks, "total": len(tasks)}
        except:
            return {"tasks": [], "total": 0}

    @app.get("/api/config")
    async def get_config():
        try:
            cfg = agent_ref().config.to_dict()
            for role in ("monkey", "horse"):
                key = cfg[role].get("api_key", "")
                if key and len(key) > 8:
                    cfg[role]["api_key"] = key[:4] + "****" + key[-4:]
                elif key:
                    cfg[role]["api_key"] = "****"
            return cfg
        except:
            return {"error": "配置不可用"}

    return app




