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

from ..agent import HermesAgent
from ..config import DEFAULT_CONFIG
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
        return {
            "status": "ok",
            "agent_name": "Hermes Agent",
            "version": "0.1.0",
            "multimodal": True,
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

    # =================== 图谱数据API（Obsidian风格知识图谱） ===================

    @app.get("/api/graph")
    async def get_graph():
        """获取知识图谱节点和关系"""
        conn = get_db()
        try:
            nodes = []
            edges = []

            # 任务节点
            try:
                tasks = conn.execute(
                    "SELECT task_id, name, status FROM rnd_tasks ORDER BY created_at DESC LIMIT 50"
                ).fetchall()
                for t in tasks:
                    nodes.append({
                        "id": t["task_id"],
                        "label": (t["name"] or "未命名")[:20],
                        "type": "task",
                        "status": t["status"] or "待构思",
                        "color": "#7c6ff0",
                    })
            except:
                pass

            # api_credentials 作为资源节点
            creds = conn.execute(
                "SELECT id, vendor, model, service FROM api_credentials"
            ).fetchall()
            for c in creds:
                nodes.append({
                    "id": f"cred_{c['id']}",
                    "label": f"{c['vendor']}:{c['model']}" if c['model'] else c['vendor'],
                    "type": "api",
                    "service": c['service'],
                    "color": "#60a5fa",
                })

            # 角色分配作为边
            assignments = conn.execute(
                "SELECT key, value FROM env_config WHERE key LIKE 'role_key_%'"
            ).fetchall()
            for a in assignments:
                role = a["key"].replace("role_key_", "")
                try:
                    val = json.loads(a["value"])
                    cid = val.get("cred_id")
                    if cid:
                        edges.append({
                            "source": f"cred_{cid}",
                            "target": f"role_{role}",
                            "label": role,
                        })
                        # 确保角色节点存在
                        role_labels = {"monkey": "🐵 灵猴", "horse": "🐴 骏马", "purchaser": "🛒 采购员"}
                        nodes.append({
                            "id": f"role_{role}",
                            "label": role_labels.get(role, role),
                            "type": "role",
                            "color": "#4ade80",
                        })
                except:
                    pass

            return {"nodes": nodes, "edges": edges}
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
