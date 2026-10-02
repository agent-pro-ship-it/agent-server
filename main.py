import os
import sys
import subprocess
import json
import logging
import psutil
from pathlib import Path
from typing import Optional, List, Dict, Any

import boto3
from botocore.config import Config
from fastapi import FastAPI, Request, Form, Header, HTTPException, UploadFile, File, WebSocket, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgentMasterExecutor")

app = FastAPI(title="Autonomous Cloud Agent Executor", version="2.0.0")

# Enable CORS for the separate control UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# Storj 25GB S3 configuration
STORJ_ENDPOINT = os.getenv("S3_ENDPOINT_URL", "https://gateway.storjshare.io")
STORJ_ACCESS_KEY = os.getenv("S3_ACCESS_KEY_ID", "juaj3eczxxsdizjdgnv63one2yza")
STORJ_SECRET_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "jz5jrlmqdg5a6ycpihbivazqmgp7seklhrqqriqxb4eknw4xo24xq")
STORJ_BUCKET = os.getenv("S3_BUCKET_NAME", "agent-vault")

s3_client = None
try:
    s3_client = boto3.client(
        "s3",
        endpoint_url=STORJ_ENDPOINT,
        aws_access_key_id=STORJ_ACCESS_KEY,
        aws_secret_access_key=STORJ_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        verify=False
    )
    logger.info("Connected to Storj 25GB S3 Cloud Storage.")
except Exception as e:
    logger.error(f"Storj S3 connection warning: {e}")

class TaskRequest(BaseModel):
    task: str
    gemini_key: Optional[str] = None

class CommandRequest(BaseModel):
    command: str

@app.get("/ping")
def ping():
    """Keep-alive endpoint for GitHub Actions robot (24/7 uptime without sleep)."""
    return {"status": "alive", "executor": "agent-master", "uptime": "24/7"}

@app.get("/api/status")
def get_status():
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    storj_ok = False
    storj_buckets = []
    if s3_client:
        try:
            res = s3_client.list_buckets()
            storj_buckets = [b["Name"] for b in res.get("Buckets", [])]
            storj_ok = True
        except Exception:
            pass

    return {
        "status": "online",
        "system": {
            "ram_used_mb": round(mem.used / (1024 * 1024), 1),
            "ram_total_mb": round(mem.total / (1024 * 1024), 1),
            "ram_percent": mem.percent,
            "cpu_percent": psutil.cpu_percent(interval=None)
        },
        "storage": {
            "storj_connected": storj_ok,
            "bucket": STORJ_BUCKET,
            "buckets_list": storj_buckets,
            "capacity": "25 GB Free"
        }
    }

@app.post("/api/terminal")
def execute_command(req: CommandRequest):
    """Executes bash commands directly on the server."""
    cmd = req.command.strip()
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            cwd=str(WORKSPACE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120
        )
        return {
            "exit_code": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "Error: Command timed out after 120 seconds."}
    except Exception as e:
        return {"exit_code": 1, "stdout": "", "stderr": str(e)}

@app.post("/api/task")
def run_autonomous_task(req: TaskRequest):
    """
    Autonomous AI developer engine:
    Receives user goal, plans actions, writes files, executes code, saves to Storj S3.
    """
    task = req.task.strip()
    api_key = req.gemini_key or os.getenv("GEMINI_API_KEY")

    # If it's a direct terminal command
    if task.startswith("$ ") or task.startswith("bash:"):
        cmd = task.replace("bash:", "").replace("$ ", "").strip()
        return execute_command(CommandRequest(command=cmd))

    # Autonomous execution with Gemini AI
    if api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            prompt = f"""You are an autonomous AI coding assistant running on a 24/7 cloud server.
You have access to:
- Linux bash workspace at: {WORKSPACE_DIR}
- Cloud storage (Storj S3 25GB)
- Python 3.11 environment

User Task:
"{task}"

Respond in JSON format:
{{
  "explanation": "Brief explanation in Russian of what will be done",
  "script": "Executable bash/python script to execute in workspace",
  "files_created": ["list", "of", "files"]
}}
Return ONLY valid JSON.
"""
            # Call Gemini models with auto-failover
            raw = None
            models_to_try = [
                "gemini-3.8-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-flash-latest",
                "gemini-3.1-flash-lite"
            ]
            import httpx
            with httpx.Client(timeout=60.0) as http_client:
                for target_model in models_to_try:
                    try:
                        rest_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
                        rest_payload = {
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "response_mime_type": "application/json"
                            }
                        }
                        r = http_client.post(rest_url, json=rest_payload)
                        if r.status_code == 200:
                            res_json = r.json()
                            raw = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                            logger.info(f"Successfully generated with {target_model}")
                            break
                        else:
                            logger.warning(f"Model {target_model} returned {r.status_code}: {r.text[:100]}")
                    except Exception as err:
                        logger.warning(f"Error calling {target_model}: {err}")

            if not raw:
                raise RuntimeError("Failed to generate response across all models.")

            import re
            raw_clean = raw.strip()
            if raw_clean.startswith("```"):
                raw_clean = re.sub(r"^```(?:json)?\s*", "", raw_clean)
                raw_clean = re.sub(r"\s*```$", "", raw_clean)

            match = re.search(r"\{.*\}", raw_clean, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
            else:
                data = json.loads(raw_clean)

            script = data.get("script", "")
            res = subprocess.run(
                script,
                shell=True,
                cwd=str(WORKSPACE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180
            )

            # Automatically upload created files to Storj 25GB S3
            synced_to_cloud = []
            if s3_client:
                for root, _, files in os.walk(str(WORKSPACE_DIR)):
                    for f in files:
                        local_f = Path(root) / f
                        rel_name = local_f.relative_to(WORKSPACE_DIR).as_posix()
                        try:
                            s3_client.put_object(Bucket=STORJ_BUCKET, Key=rel_name, Body=local_f.read_bytes())
                            synced_to_cloud.append(rel_name)
                        except Exception as up_err:
                            logger.warning(f"Failed to sync {rel_name} to Storj: {up_err}")

            return {
                "success": (res.returncode == 0),
                "explanation": data.get("explanation"),
                "stdout": res.stdout,
                "stderr": res.stderr,
                "exit_code": res.returncode,
                "cloud_synced_files": synced_to_cloud
            }
        except Exception as e:
            logger.error(f"Task AI error: {e}")
            return {"success": False, "error": f"AI Engine error: {str(e)}"}

    # Default fallback: direct shell execution
    res = subprocess.run(task, shell=True, cwd=str(WORKSPACE_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
    return {
        "success": (res.returncode == 0),
        "explanation": "Executed directly via system shell.",
        "stdout": res.stdout,
        "stderr": res.stderr,
        "exit_code": res.returncode
    }

@app.get("/api/files")
def list_workspace_and_cloud_files():
    """Lists both local workspace files and Storj 25GB cloud files."""
    local_files = []
    for root, _, files in os.walk(str(WORKSPACE_DIR)):
        for f in files:
            p = Path(root) / f
            local_files.append({
                "name": p.relative_to(WORKSPACE_DIR).as_posix(),
                "size": p.stat().st_size,
                "location": "local_workspace"
            })

    cloud_files = []
    if s3_client:
        try:
            res = s3_client.list_objects_v2(Bucket=STORJ_BUCKET)
            for item in res.get("Contents", []):
                cloud_files.append({
                    "name": item.get("Key"),
                    "size": item.get("Size"),
                    "location": "storj_25gb"
                })
        except Exception:
            pass

    return {
        "local_workspace": local_files,
        "storj_cloud_25gb": cloud_files
    }

@app.post("/api/git-sync")
def git_sync(msg: str = Form("Autonomous Agent Workspace Sync")):
    """Commits and pushes workspace code to GitHub."""
    cmd = f'git add . && git commit -m "{msg}" && git push'
    res = subprocess.run(cmd, shell=True, cwd=str(WORKSPACE_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return {"exit_code": res.returncode, "stdout": res.stdout, "stderr": res.stderr}

@app.get("/api/antigravity/status")
def antigravity_status():
    """Checks Antigravity CLI installation and version."""
    try:
        res = subprocess.run(["agy", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        return {
            "installed": (res.returncode == 0),
            "version": res.stdout.strip() if res.returncode == 0 else "not_found",
            "output": res.stdout.strip() or res.stderr.strip()
        }
    except Exception as e:
        return {"installed": False, "error": str(e)}

active_auth_process = None

@app.post("/api/antigravity/start-auth")
def start_auth():
    global active_auth_process
    if active_auth_process and active_auth_process.poll() is None:
        try:
            active_auth_process.terminate()
        except Exception:
            pass

    active_auth_process = subprocess.Popen(
        ["agy", "-p", "auth_check"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    auth_url = ""
    import time
    import re
    start_time = time.time()
    while time.time() - start_time < 15:
        line = active_auth_process.stdout.readline()
        if not line and active_auth_process.poll() is not None:
            break
        if "https://accounts.google.com/o/oauth2/auth" in line:
            m = re.search(r'(https://accounts\.google\.com/o/oauth2/auth[^\s]+)', line)
            if m:
                auth_url = m.group(1).strip()
                break

    if auth_url:
        return {"status": "waiting_for_code", "auth_url": auth_url}
    return {"status": "error", "message": "Could not capture authentication URL"}

class CodeSubmit(BaseModel):
    code: str

@app.post("/api/antigravity/submit-auth")
def submit_auth(req: CodeSubmit):
    global active_auth_process
    if not active_auth_process or active_auth_process.poll() is not None:
        return {"success": False, "error": "Сессия авторизации не найдена. Нажмите 'Войти через Google' заново."}

    try:
        active_auth_process.stdin.write(req.code.strip() + "\n")
        active_auth_process.stdin.flush()
        
        import time
        start_time = time.time()
        output = ""
        while time.time() - start_time < 15:
            line = active_auth_process.stdout.readline()
            if not line and active_auth_process.poll() is not None:
                break
            output += line
            if "success" in line.lower() or "logged in" in line.lower() or "welcome" in line.lower() or "authenticated" in line.lower():
                break

        return {"success": True, "output": output}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/antigravity/remote-control")
def start_remote_control():
    """Starts Antigravity remote control daemon for official web dashboard access."""
    try:
        res = subprocess.run(["agy", "remote-control", "start"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        return {
            "success": (res.returncode == 0),
            "stdout": res.stdout,
            "stderr": res.stderr
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

TERMINAL_PAGE_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>Antigravity Cloud Terminal</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
  <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.min.js"></script>
  <style>
    * { box-sizing: border-box; }
    html, body {
      margin: 0; padding: 0; width: 100%; height: 100%;
      background: #000; overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro", "SF Mono", Menlo, monospace;
    }
    #terminal-container { width: 100%; height: 100%; padding: 6px; }
  </style>
</head>
<body>
  <div id="terminal-container"></div>
  <script>
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 15,
      fontFamily: 'SF Mono, Menlo, Monaco, Consolas, "Courier New", monospace',
      theme: {
        background: '#000000',
        foreground: '#f5f5f7',
        cursor: '#30d158'
      }
    });
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(document.getElementById('terminal-container'));
    fitAddon.fit();
    window.addEventListener('resize', () => fitAddon.fit());

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/terminal/ws`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      term.write('\\r\\n\\x1b[32m✔ Подключено к облачному серверу Antigravity!\\x1b[0m\\r\\n');
      term.write('\\x1b[90mНапишите agy и нажмите Enter для запуска агента.\\x1b[0m\\r\\n\\r\\n');
    };

    socket.onmessage = (event) => {
      term.write(event.data);
    };

    term.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(data);
      }
    });

    socket.onclose = () => {
      term.write('\\r\\n\\x1b[31m[Сессия завершена. Обновите страницу]\\x1b[0m\\r\\n');
    };
  </script>
</body>
</html>
"""

@app.get("/terminal", response_class=HTMLResponse)
@app.get("/terminal/", response_class=HTMLResponse)
def get_terminal_page():
    return HTMLResponse(content=TERMINAL_PAGE_HTML)

@app.websocket("/terminal/ws")
async def terminal_websocket(websocket: WebSocket):
    await websocket.accept()
    import pty
    import fcntl
    import asyncio

    master, slave = pty.openpty()

    # Set non-blocking on master
    flags = fcntl.fcntl(master, fcntl.F_GETFL)
    fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    env = dict(os.environ)
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"

    proc = subprocess.Popen(
        ["/bin/bash"],
        preexec_fn=os.setsid,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        cwd=str(WORKSPACE_DIR),
        env=env
    )
    os.close(slave)

    async def pty_read_loop():
        try:
            while True:
                await asyncio.sleep(0.015)
                try:
                    data = os.read(master, 8192)
                    if data:
                        await websocket.send_text(data.decode("utf-8", errors="replace"))
                except (BlockingIOError, InterruptedError):
                    continue
                except Exception:
                    break
        except Exception:
            pass

    async def ws_read_loop():
        try:
            while True:
                msg = await websocket.receive_text()
                if msg:
                    os.write(master, msg.encode("utf-8"))
        except Exception:
            pass

    try:
        await asyncio.gather(pty_read_loop(), ws_read_loop())
    finally:
        try:
            proc.terminate()
            os.close(master)
        except Exception:
            pass

# Standalone UI endpoint if accessed directly
@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/manifest.json")
def manifest():
    return FileResponse("static/manifest.json")

@app.get("/sw.js")
def service_worker():
    return FileResponse("static/sw.js")

@app.get("/style.css")
def css():
    return FileResponse("static/style.css")

@app.get("/app.js")
def js():
    return FileResponse("static/app.js")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
