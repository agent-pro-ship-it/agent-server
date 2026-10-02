import os
import json
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from account_manager import account_manager
from storage_router import storage_router
from skills_manager import skills_manager
from agent_engine import agent_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(AgentMasterServer)

app = FastAPI(title=Autonomous AI Agent Master Server, version=1.0.0)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*],
    allow_credentials=True,
    allow_methods=[*],
    allow_headers=[*],
)

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []

class AccountSwitchRequest(BaseModel):
    index: int

class AddAccountRequest(BaseModel):
    name: str
    key: str

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

@app.get("/manifest.json")
def serve_manifest():
    return FileResponse("static/manifest.json")

@app.get("/sw.js")
def serve_sw():
    return FileResponse("static/sw.js")

@app.get("/style.css")
def serve_css():
    return FileResponse("static/style.css")

@app.get("/app.js")
def serve_js():
    return FileResponse("static/app.js")

@app.get("/ping")
def ping():
    """Keep-alive ping endpoint for UptimeRobot (prevents Render from sleeping)."""
    return {"status": "alive", "server": "agent-master", "service": "render"}

@app.get(/health)
def health():
    return {
        status: ok,
        current_account: account_manager.get_current_account_info(),
        total_accounts: len(account_manager.accounts),
        skills_loaded: len(skills_manager.list_all_skills())
    }

# ----------------- ACCOUNT MANAGEMENT -----------------
@app.get(/api/accounts)
def get_accounts():
    return {accounts: account_manager.list_accounts_safe()}

@app.post(/api/accounts/switch)
def switch_account(req: AccountSwitchRequest):
    success = account_manager.set_active_account(req.index)
    if not success:
        raise HTTPException(status_code=400, detail=Invalid account index)
    return {status: switched, current: account_manager.get_current_account_info()}

@app.post(/api/accounts/add)
def add_account(req: AddAccountRequest):
    new_acc = account_manager.add_account(req.name, req.key)
    return {status: added, account: new_acc}

# ----------------- SKILLS & PLUGINS -----------------
@app.get(/api/skills)
def get_skills():
    return {skills: skills_manager.list_all_skills()}

# ----------------- MULTI-CLOUD STORAGE -----------------
@app.get(/api/files)
def list_files(provider: str = all):
    return {files: storage_router.list_files(provider=provider)}

@app.post(/api/files/upload)
async def upload_file(file: UploadFile = File(...), target: str = Form(auto)):
    content = await file.read()
    res = storage_router.upload_file(content, file.filename, target=target)
    return {status: uploaded, details: res}

# ----------------- CHAT & STREAMING -----------------
@app.post(/api/chat)
async def chat_endpoint(req: ChatRequest):
    async def event_generator():
        async for item in agent_engine.stream_chat(req.message, req.history):
            yield fdata: {json.dumps(item)}\n\n
    return StreamingResponse(event_generator(), media_type=text/event-stream)

@app.websocket(/ws/chat)
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    logger.info(WebSocket client connected.)
    try:
        while True:
            data_raw = await websocket.receive_text()
            data = json.loads(data_raw)
            user_msg = data.get(message, ")
 history = data.get(history, [])

 async for event in agent_engine.stream_chat(user_msg, history):
 await websocket.send_text(json.dumps(event))

 await websocket.send_text(json.dumps({type: done}))
 except WebSocketDisconnect:
 logger.info(WebSocket client disconnected.)
 except Exception as e:
 logger.error(fWebSocket error: {e})
 try:
 await websocket.send_text(json.dumps({type: error, text: str(e)}))
 except Exception:
 pass

if __name__ == __main__:
 import uvicorn
 uvicorn.run(main:app, host=0.0.0.0, port=int(os.getenv(PORT, 10000)), reload=True)
