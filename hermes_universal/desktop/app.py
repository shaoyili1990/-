"""
Hermes Agent Desktop - Web可视化界面
FastAPI后端 + HTML/CSS/JS前端
"""

import os
import json
import uuid
import base64
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from ..agent import HermesAgent

# 全局Agent实例
_agent: Optional[HermesAgent] = None


def get_agent() -> HermesAgent:
    global _agent
    if _agent is None:
        _agent = HermesAgent()
    return _agent


def create_app(agent: Optional[HermesAgent] = None) -> FastAPI:
    """创建FastAPI应用"""
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

    # 静态文件目录
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    agent_ref = get_agent

    # ========== API路由 ==========

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """主页面"""
        html_path = Path(__file__).parent / "templates" / "index.html"
        if html_path.exists():
            return HTMLResponse(html_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Hermes Agent Desktop</h1><p>Loading...</p>")

    @app.get("/api/status")
    async def status():
        """系统状态"""
        return agent_ref().get_status()

    @app.post("/api/chat")
    async def chat(message: str = Form(...), images: Optional[str] = Form(None)):
        """对话接口"""
        image_list = None
        if images:
            try:
                image_list = json.loads(images)
            except:
                pass

        result = agent_ref().run(message, images=image_list)
        if isinstance(result, dict):
            return {
                "task_id": result.get("task_id"),
                "response": result.get("final_output", ""),
                "route": result.get("route"),
                "review": result.get("review"),
                "status": result.get("status"),
            }
        return {"response": str(result)}

    @app.post("/api/chat/stream")
    async def chat_stream(message: str = Form(...)):
        """流式对话(SSE)"""
        from fastapi.responses import StreamingResponse

        async def generate():
            result = agent_ref().run(message, stream=True)
            if hasattr(result, '__iter__'):
                for chunk in result:
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post("/api/upload")
    async def upload(file: UploadFile = File(...)):
        """上传文件(图像等)"""
        contents = await file.read()
        b64 = base64.b64encode(contents).decode("ascii")
        mime = file.content_type or "image/png"
        return {
            "filename": file.filename,
            "mime_type": mime,
            "data": b64,
            "data_uri": f"data:{mime};base64,{b64}",
        }

    @app.get("/api/tasks")
    async def list_tasks(status: Optional[str] = None, limit: int = 20):
        """任务列表"""
        tasks = agent_ref().db.list_tasks(status=status, limit=limit)
        return {"tasks": tasks, "total": len(tasks)}

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str):
        """任务详情"""
        info = agent_ref().get_task_status(task_id)
        if not info:
            raise HTTPException(404, "任务不存在")
        return info

    @app.post("/api/tasks")
    async def create_task(name: str = Form(...), level: str = Form("unit")):
        """创建任务"""
        task = agent_ref().keeper.create_task(name, level)
        return task

    @app.post("/api/tasks/{task_id}/transition")
    async def transition_task(task_id: str, to_state: str = Form(...)):
        """状态转换"""
        result = agent_ref().keeper.transition(task_id, to_state)
        return result

    @app.get("/api/constitution")
    async def get_constitution():
        """获取宪法"""
        return {"constitution": agent_ref().keeper.get_constitution()}

    @app.get("/api/chains")
    async def get_chains():
        """获取子链统计"""
        return agent_ref().subchain.get_statistics()

    @app.get("/api/states")
    async def get_states():
        """获取状态定义"""
        return {"states": agent_ref().state_machine.get_all_states()}

    @app.get("/api/config")
    async def get_config():
        """获取配置(不含敏感信息)"""
        cfg = agent_ref().config.to_dict()
        # 隐藏API Key
        for role in ("monkey", "horse"):
            if role in cfg:
                key = cfg[role].get("api_key", "")
                if key and len(key) > 8:
                    cfg[role]["api_key"] = key[:4] + "****" + key[-4:]
        return cfg

    @app.post("/api/config/update")
    async def update_config(
        monkey_provider: str = Form(None),
        monkey_model: str = Form(None),
        monkey_key: str = Form(None),
        horse_provider: str = Form(None),
        horse_model: str = Form(None),
        horse_key: str = Form(None),
    ):
        """更新配置"""
        updates = {}
        if monkey_provider:
            updates["monkey"] = {"provider": monkey_provider}
        if monkey_model:
            updates.setdefault("monkey", {})["model"] = monkey_model
        if monkey_key:
            updates.setdefault("monkey", {})["api_key"] = monkey_key
        if horse_provider:
            updates["horse"] = {"provider": horse_provider}
        if horse_model:
            updates.setdefault("horse", {})["model"] = horse_model
        if horse_key:
            updates.setdefault("horse", {})["api_key"] = horse_key

        # 重新初始化Agent
        global _agent
        _agent = HermesAgent(**updates)
        return {"status": "ok", "updated": list(updates.keys())}

    return app


# 直接运行入口
if __name__ == "__main__":
    import uvicorn
    app = create_app()
    print("=" * 60)
    print(" Hermes Agent Desktop")
    print(" 打开浏览器访问: http://localhost:8080")
    print("=" * 60)
    uvicorn.run(app, host="127.0.0.1", port=8080)
