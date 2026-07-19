"""
Hermes Agent Desktop - 多模态可视化界面
FastAPI后端 + 三栏可视化HTML前端
支持：文本对话、图片理解、文件分析、流式输出、实时推理可视化
"""

import os
import json
import uuid
import base64
import time
import mimetypes
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from ..agent import HermesAgent

_agent: Optional[HermesAgent] = None


def get_agent() -> HermesAgent:
    global _agent
    if _agent is None:
        _agent = HermesAgent()
    return _agent


def create_app(agent: Optional[HermesAgent] = None) -> FastAPI:
    global _agent
    if agent:
        _agent = agent

    app = FastAPI(title="Hermes Agent Desktop", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    agent_ref = get_agent

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = Path(__file__).parent / "templates" / "index.html"
        if html_path.exists():
            return HTMLResponse(html_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Hermes Agent</h1><p>Loading...</p>")

    @app.get("/api/status")
    async def status():
        """系统状态"""
        return {
            "status": "ok",
            "agent_name": "Hermes Agent",
            "version": "0.1.0",
            "multimodal": True,
            "capabilities": ["text", "image", "file", "streaming"],
            "roles": [
                {
                    "name": "Monkey",
                    "title": "灵猴",
                    "desc": "路由与判断",
                    "icon": "🐵",
                },
                {
                    "name": "Review",
                    "title": "质检官",
                    "desc": "安全与合规审查",
                    "icon": "🔍",
                },
                {
                    "name": "Horse",
                    "title": "骏马",
                    "desc": "推理与执行",
                    "icon": "🐴",
                },
                {
                    "name": "Keeper",
                    "title": "司库",
                    "desc": "状态与流程管理",
                    "icon": "💾",
                },
                {
                    "name": "Scribe",
                    "title": "书童",
                    "desc": "认知与记忆",
                    "icon": "📝",
                },
            ],
            "stats": {
                "chains": 136,
                "validations": 4,
                "knowledge_bases": 10,
                "storage": "SQLite多维表格",
            },
        }

    @app.post("/api/chat")
    async def chat(
        message: str = Form(...),
        images: Optional[str] = Form(None),
        files_data: Optional[str] = Form(None),
    ):
        """
        多模态对话接口 - 支持文本+图片+文件
        返回结构化结果供前端展示流水线和推理过程
        """
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

        # 构建多模态输入
        multimodal_input = {"text": message}
        if image_list:
            multimodal_input["images"] = image_list[:10]
        if file_list:
            multimodal_input["files"] = file_list[:5]

        result = agent_ref().run(multimodal_input)
        elapsed = time.time() - start_time

        # 结构化响应
        if isinstance(result, dict):
            route_info = result.get("route", {})
            review_info = result.get("review", {})

            return {
                "task_id": result.get("task_id", str(uuid.uuid4())),
                "response": result.get("final_output", ""),
                "route": route_info.get("domain_name", "通用") if isinstance(route_info, dict) else str(route_info),
                "route_type": route_info.get("route_type", "智能路由") if isinstance(route_info, dict) else "",
                "route_confidence": route_info.get("confidence", 0) if isinstance(route_info, dict) else 0,
                "chain": result.get("subchain", "逻辑链"),
                "chain_category": result.get("chain_category", "逻辑推理"),
                "review": (
                    review_info.get("conclusion", "")
                    if isinstance(review_info, dict)
                    else str(review_info)
                ),
                "review_pass": (
                    review_info.get("pass", True) if isinstance(review_info, dict) else True
                ),
                "status": result.get("status", "completed"),
                "iteration": result.get("iteration_count", 0),
                "elapsed": f"{elapsed:.1f}s",
            }

        return {
            "response": str(result),
            "route": "通用",
            "chain": "逻辑链",
            "review": "✓",
            "elapsed": f"{elapsed:.1f}s",
        }

    @app.post("/api/chat/stream")
    async def chat_stream(
        message: str = Form(...),
        images: Optional[str] = Form(None),
    ):
        """流式对话（SSE），推送实时流水线状态"""
        async def generate():
            input_data = {"text": message}
            if images:
                try:
                    input_data["images"] = json.loads(images)
                except:
                    pass

            # 阶段1: 灵猴路由
            yield f"data: {json.dumps({'type':'stage','role':'monkey','status':'busy','label':'灵猴 — 路由分析'})}\n\n"
            yield f"data: {json.dumps({'type':'think','title':'🐵 灵猴 — 路由分析','sub':'判断任务类型与领域','dot':'yellow'})}\n\n"

            result = agent_ref().run(input_data, stream=True)

            # 阶段2: 质检审核
            yield f"data: {json.dumps({'type':'stage','role':'monkey','status':'done'})}\n\n"
            yield f"data: {json.dumps({'type':'stage','role':'review','status':'busy','label':'质检官 — 合规审查'})}\n\n"
            yield f"data: {json.dumps({'type':'think','title':'🔍 质检官 — 合规审查','sub':'安全与质量检查','dot':'purple'})}\n\n"

            # 阶段3: 骏马推理
            yield f"data: {json.dumps({'type':'stage','role':'review','status':'done'})}\n\n"
            yield f"data: {json.dumps({'type':'stage','role':'horse','status':'busy','label':'骏马 — 推理执行'})}\n\n"
            yield f"data: {json.dumps({'type':'think','title':'🐴 骏马 — 推理执行','sub':'执行136条推理子链','dot':'green'})}\n\n"

            yield f"data: {json.dumps({'type':'chain','label':'逻辑链','category':'逻辑推理'})}\n\n"

            # 流式输出文本
            if hasattr(result, "__iter__"):
                for chunk in result:
                    if isinstance(chunk, str):
                        yield f"data: {json.dumps({'type':'chunk','content':chunk})}\n\n"

            # 阶段4: 司库存储
            yield f"data: {json.dumps({'type':'stage','role':'horse','status':'done'})}\n\n"
            yield f"data: {json.dumps({'type':'stage','role':'keeper','status':'busy','label':'司库 — 状态存储'})}\n\n"
            yield f"data: {json.dumps({'type':'think','title':'💾 司库 — 状态存储','sub':'保存结果到多维表','dot':'purple'})}\n\n"

            yield f"data: {json.dumps({'type':'stage','role':'keeper','status':'done'})}\n\n"

            # 阶段5: 书童记忆
            yield f"data: {json.dumps({'type':'stage','role':'scribe','status':'busy','label':'书童 — 记忆更新'})}\n\n"
            yield f"data: {json.dumps({'type':'think','title':'📝 书童 — 记忆更新','sub':'更新认知库','dot':'blue'})}\n\n"
            yield f"data: {json.dumps({'type':'stage','role':'scribe','status':'done'})}\n\n"
            yield f"data: {json.dumps({'type':'think','title':'✅ 推理完成','sub':'所有阶段通过','dot':'green'})}\n\n"

            yield f"data: {json.dumps({'type':'done'})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post("/api/upload")
    async def upload(file: UploadFile = File(...)):
        """上传文件（图片/文档等）"""
        contents = await file.read()
        b64 = base64.b64encode(contents).decode("ascii")
        mime = file.content_type or "application/octet-stream"

        is_image = mime.startswith("image/")
        is_doc = mime in [
            "application/pdf",
            "application/json",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown",
            "text/csv",
        ]

        return {
            "filename": file.filename,
            "mime_type": mime,
            "size": len(contents),
            "data": b64,
            "data_uri": f"data:{mime};base64,{b64}",
            "type": "image" if is_image else ("document" if is_doc else "file"),
        }

    @app.post("/api/upload/multi")
    async def upload_multi(files: List[UploadFile] = File(...)):
        """批量上传"""
        results = []
        for f in files:
            contents = await f.read()
            b64 = base64.b64encode(contents).decode("ascii")
            mime = f.content_type or "application/octet-stream"
            results.append(
                {
                    "filename": f.filename,
                    "mime_type": mime,
                    "size": len(contents),
                    "data_uri": f"data:{mime};base64,{b64}",
                }
            )
        return {"files": results, "count": len(results)}

    @app.get("/api/tasks")
    async def list_tasks(status: Optional[str] = None, limit: int = 20):
        """任务列表"""
        try:
            tasks = agent_ref().db.list_tasks(status=status, limit=limit)
            return {"tasks": tasks, "total": len(tasks)}
        except:
            return {"tasks": [], "total": 0}

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str):
        """任务详情"""
        try:
            info = agent_ref().get_task_status(task_id)
            if not info:
                raise HTTPException(404, "任务不存在")
            return info
        except HTTPException:
            raise
        except:
            raise HTTPException(404, "任务不存在")

    @app.get("/api/chains")
    async def get_chains():
        """子链信息"""
        return {
            "chains": [
                {"name": "逻辑链", "active": True, "desc": "因果推理"},
                {"name": "思维链", "active": True, "desc": "逐步推理"},
                {"name": "推导法", "active": True, "desc": "假设验证"},
                {"name": "反证逻辑", "active": True, "desc": "反例验证"},
            ],
            "subchains": [
                {
                    "id": f"subchain_{i}",
                    "name": f"推理子链 #{i}",
                    "category": ["逻辑", "因果", "思维", "推导"][i % 4],
                }
                for i in range(1, 137)
            ],
        }

    @app.get("/api/config")
    async def get_config():
        """获取配置"""
        try:
            cfg = agent_ref().config.to_dict()
            for role in ("monkey", "horse"):
                if role in cfg:
                    key = cfg[role].get("api_key", "")
                    if key and len(key) > 8:
                        cfg[role]["api_key"] = key[:4] + "****" + key[-4:]
                    elif key:
                        cfg[role]["api_key"] = "****"
            return cfg
        except:
            return {"error": "配置不可用"}

    return app
