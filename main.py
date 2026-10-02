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
from fastapi import FastAPI, Request, Form, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
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
        config=Config(signature_version="s3v4")
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
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            raw = resp.text.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            data = json.loads(raw.strip())

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
                            s3_client.upload_file(str(local_f), STORJ_BUCKET, rel_name)
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
