import os
import sys
import subprocess
import asyncio
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
STORJ_ENDPOINT = os.getenv("STORJ_ENDPOINT_URL") or os.getenv("S3_ENDPOINT_URL", "https://gateway.storjshare.io")
STORJ_ACCESS_KEY = os.getenv("STORJ_ACCESS_KEY_ID") or os.getenv("S3_ACCESS_KEY_ID", "juaj3eczxxsdizjdgnv63one2yza")
STORJ_SECRET_KEY = os.getenv("STORJ_SECRET_ACCESS_KEY") or os.getenv("S3_SECRET_ACCESS_KEY", "jz5jrlmqdg5a6ycpihbivazqmgp7seklhrqqriqxb4eknw4xo24xq")
STORJ_BUCKET = os.getenv("STORJ_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME", "agent-vault")

s3_client = None
try:
    cfg = Config(
        signature_version='s3v4',
        s3={'payload_signing_enabled': False, 'addressing_style': 'path'},
        request_checksum_calculation='when_required',
        response_checksum_validation='when_required'
    )
    s3_client = boto3.client(
        "s3",
        endpoint_url=STORJ_ENDPOINT,
        aws_access_key_id=STORJ_ACCESS_KEY,
        aws_secret_access_key=STORJ_SECRET_KEY,
        config=cfg,
        verify=False
    )
    logger.info("Connected to Storj 25GB S3 Cloud Storage (Checksum & Chunking optimized).")
except Exception as e:
    logger.error(f"Storj S3 connection warning: {e}")

from account_manager import AccountManager
account_manager = AccountManager(workspace_dir=WORKSPACE_DIR, s3_client=s3_client, bucket_name=STORJ_BUCKET)
try:
    account_manager.initialize()
except Exception as e:
    logger.warning(f"AccountManager initialization notice: {e}")

class TaskRequest(BaseModel):
    task: str
    gemini_key: Optional[str] = None
    project_id: Optional[str] = None
    voice_mode: Optional[bool] = False
    voice: Optional[str] = "ru-RU-DmitryNeural"
    history: Optional[List[Dict[str, Any]]] = None

class CommandRequest(BaseModel):
    command: str
    project_id: Optional[str] = None

class ProjectCreateRequest(BaseModel):
    name: str
    task: Optional[str] = "Новая задача Antigravity"

PROJECTS_FILE = WORKSPACE_DIR / "projects.json"

DEFAULT_PROJECTS = [
    {"id": "agent", "name": "Агент", "task": "Бесплатный Сервер Для Антигравити", "time": "2m", "active": True},
    {"id": "recruiter-club", "name": "сайт Recruiter I Club", "task": "Premium B2B SaaS Architecture", "time": "53m", "active": False},
    {"id": "resume-optimizer", "name": "парсер и резюме", "task": "Free AI Resume Optimizer", "time": "1h", "active": False},
    {"id": "online-crm", "name": "проект онлайн срм", "task": "Разработка Полнофункциональной CRM", "time": "7h", "active": False},
    {"id": "doc-automation", "name": "прога для договор...", "task": "Автоматизация Заполнения Документов", "time": "14d", "active": False},
    {"id": "recruiter-project", "name": "Recruiter проект", "task": "Getting Vercel Access Token", "time": "18d", "active": False},
    {"id": "site-landing", "name": "сайт", "task": "Разработка Премиального Лендинга", "time": "22d", "active": False},
    {"id": "telegram-bot", "name": "telegram bot", "task": "Создание Бота Для Сбора Заявок", "time": "1mo", "active": False},
    {"id": "crm-debug", "name": "отладка срм антиг...", "task": "Фикс багов и деплой на сервер", "time": "2mo", "active": False}
]

def get_all_projects():
    if not PROJECTS_FILE.exists():
        try:
            PROJECTS_FILE.write_text(json.dumps(DEFAULT_PROJECTS, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    try:
        projs = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        projs = DEFAULT_PROJECTS
    for p in projs:
        p_dir = WORKSPACE_DIR / p["id"]
        try:
            p_dir.mkdir(parents=True, exist_ok=True)
            p["files_count"] = sum(len(f) for _, _, f in os.walk(str(p_dir)))
        except Exception:
            p["files_count"] = 0
    return projs

ANTIGRAVITY_TOKEN_DIR = Path("/root/.gemini/antigravity-cli")
ANTIGRAVITY_TOKEN_FILE = ANTIGRAVITY_TOKEN_DIR / "antigravity-oauth-token"
B64_OAUTH_TOKEN = "eyJ0b2tlbiI6eyJhY2Nlc3NfdG9rZW4iOiJ5YTI5LmEwQVgwN0NtdVhmVE40YzVIeWNyd1JZZDlwejJYYmc0M0xobzY3eEVZZEwxU3piZmFuMmN3aUNfNWNEX2w2cWtXZ0FfeFJXa01LRldmR0lZNVdBLS04cHpDOEpQWDgwRVRfVlF3ZzU2RDkzdHF2WXFlNGZ1RUNkNVNaMU1LYklwODZxOUdVR09kYlpQZm9qM0E5OUd5MjUxMnB1ODV6aFlGTFhWTUtBeTFTZWNjREQ4cURCTnhQelNxakZVYW1qMFg1UFZiR2xFeUhNbkZrYUNnWUtBVjBTQVJZU0ZRSEdYMk1pYXZCOFhaamhrN1p4QTJyUHE2MDFwQTAyMTEiLCJ0b2tlbl90eXBlIjoiQmVhcmVyIiwicmVmcmVzaF90b2tlbiI6IjEvLzAzVlZ2ejZHOUkyV0lDZ1lJQVJBQUdBTVNOd0YtTDlJcmx6YkRkUHFjb2w3OW9yNHNpSWNzZVlpdHRmNW01OS1sYlhPNGU5dEszaU5WVTZ1UVUwejc2SXhYczR0ejlrWW1KM3ciLCJleHBpcnkiOiIyMDI2LTEwLTAyVDE3OjQ0OjE0LjMyMDE1MjU4NloifSwiYXV0aF9tZXRob2QiOiJjb25zdW1lciIsImlkX3Rva2VuIjoiZXlKaGJHY2lPaUpTVXpJMU5pSXNJbXRwWkNJNklqazBNMkV6WVRWa04yUTVNVGsyTWpWaE5EVTBaVFE0T1dJM05XTXlPV0ZrWVdJMU4yRmpZbUVpTENKMGVYQWlPaUpLVjFRaWZRLmV5SnBjM01pT2lKb2RIUndjem92TDJGalkyOTFiblJ6TG1kdmIyZHNaUzVqYjIwaUxDSmhlbkFpT2lJeE1EY3hNREEyTURZd05Ua3hMWFJ0YUhOemFXNHlhREl4YkdOeVpUSXpOWFowYjJ4dmFtZzBaelF3TTJWd0xtRndjSE11WjI5dloyeGxkWE5sY21OdmJuUmxiblF1WTI5dElpd2lZWFZrSWpvaU1UQTNNVEF3TmpBMk1EVTVNUzEwYldoemMybHVNbWd5TVd4amNtVXlNelYyZEc5c2IycG9OR2MwTURObGNDNWhjSEJ6TG1kdmIyZHNaWFZ6WlhKamIyNTBaVzUwTG1OdmJTSXNJbk4xWWlJNklqRXhNVGcwTXpjM056UTJNekkwTnpRMk1ETTVPQ0lzSW1WdFlXbHNJam9pY21WamNuVnBkR1Z5WTJ4MVlpNWliM1JBWjIxaGFXd3VZMjl0SWl3aVpXMWhhV3hmZG1WeWFXWnBaV1FpT25SeWRXVXNJbUYwWDJoaGMyZ2lPaUpvV1VoUlltcFdOa1J2Vlc1M1NHcFRWbkJyVld4M0lpd2libUZ0WlNJNklsSmxZM0oxYVhSbGNpQkNiM1FpTENKd2FXTjBkWEpsSWpvaWFIUjBjSE02THk5c2FETXVaMjl2WjJ4bGRYTmxjbU52Ym5SbGJuUXVZMjl0TDJFdlFVTm5PRzlqU2pOQlowbzJVSFZyYzAxSmNrNTNNa0ZXV0ZwcE9Ya3hOVlV0WjI5clkwMU1WblpTVDJWclRTMDROM1pKVTI1blBYTTVOaTFqSWl3aVoybDJaVzVmYm1GdFpTSTZJbEpsWTNKMWFYUmxjaUlzSW1aaGJXbHNlVjl1WVcxbElqb2lRbTkwSWl3aWFXRjBJam94Tnprd09UVTVORFUxTENKbGVIQWlPakUzT1RBNU5qTXdOVFY5Lk8xdUR5blJWQ05FZHhOZFNLQS1id19IRU0xc0o5eEdlYm1ydFhpdU9iYXU2TklhblMxZUctWFlQYXgxRXpPSkRYa1J0dDN3M2psVWQxdkZKMklsOGtvQkFsWnpBOWZ4R3A3NTJJTU9EcnpUWTRKN3NSVlJIaHU5RllkelZqY3dORWFJN3lyaGlBNkxRTmYxYkJxWGN1M29sdFNxb0piVHJPakNIX01pTkpWdFcyR1lyWGlNVTcyR1hHUEJzRUdoci10STVMX0VaVWFoRFhJUGhQS0FzVm1aaFlvLUViTGY3VUpzSDFjVWhwY0Z5ZlhXazdaY0tOR1Mwc0tIR2xfeFVGSVVyVjA0aEh1YTJDNU11QV9POUt3emxLbG9uLVRjUjBlN25YWjNNMlpXVTA2dUlsOGxPQlp5TTlGb3RPcVItY1J5WnpvZXB1OE9uYjBLZmJ6NEJHUSJ9"

def ensure_antigravity_auth():
    try:
        import base64
        ANTIGRAVITY_TOKEN_DIR.mkdir(parents=True, exist_ok=True)
        if not ANTIGRAVITY_TOKEN_FILE.exists() or ANTIGRAVITY_TOKEN_FILE.stat().st_size < 100:
            token_content = base64.b64decode(B64_OAUTH_TOKEN).decode("utf-8")
            ANTIGRAVITY_TOKEN_FILE.write_text(token_content.strip(), encoding="utf-8")
            try:
                os.chmod(str(ANTIGRAVITY_TOKEN_FILE), 0o600)
            except Exception:
                pass
            logger.info("Auto-restored Google Pro OAuth token for Antigravity.")
    except Exception as e:
        logger.warning(f"Could not ensure antigravity token: {e}")

ensure_antigravity_auth()

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


@app.get("/api/projects")
def api_get_projects():
    return {"projects": get_all_projects()}

@app.post("/api/projects")
def api_create_project(req: ProjectCreateRequest):
    import re, time
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name required")
    slug = re.sub(r'[^a-zA-Z0-9_\-Ѐ-ӿ]', '-', name).lower().strip('-')
    if not slug:
        slug = f"project-{int(time.time())}"
    
    p_dir = WORKSPACE_DIR / slug
    p_dir.mkdir(parents=True, exist_ok=True)

    readme_path = p_dir / "README.md"
    if not readme_path.exists():
        readme_content = f"# {name}\n\n{req.task or 'Antigravity Cloud Project Workspace'}\n"
        readme_path.write_text(readme_content, encoding="utf-8")
        if s3_client:
            try:
                s3_client.put_object(Bucket=STORJ_BUCKET, Key=f"projects/{slug}/README.md", Body=readme_content.encode("utf-8"))
            except Exception:
                pass

    projs = get_all_projects()
    existing = next((p for p in projs if p["id"] == slug), None)
    if not existing:
        new_proj = {
            "id": slug,
            "name": name,
            "task": req.task or "Новая задача",
            "time": "just now",
            "active": True
        }
        projs.insert(0, new_proj)
        for p in projs:
            if p["id"] != slug:
                p["active"] = False
        try:
            PROJECTS_FILE.write_text(json.dumps(projs, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return {"success": True, "project": new_proj}
    return {"success": True, "project": existing}

class ProjectUpdateRequest(BaseModel):
    name: str
    task: Optional[str] = None

@app.patch("/api/projects/{project_id}")
def api_update_project(project_id: str, req: ProjectUpdateRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name required")
    projs = get_all_projects()
    found = False
    for p in projs:
        if p.get("id") == project_id:
            p["name"] = name
            if req.task is not None:
                p["task"] = req.task
            found = True
            break
    if not found:
        projs.append({"id": project_id, "name": name, "task": req.task or "", "time": "now", "active": True})
    try:
        PROJECTS_FILE.write_text(json.dumps(projs, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Error saving PROJECTS_FILE: {e}")
    return {"success": True, "project_id": project_id, "name": name}

@app.get("/api/projects/{project_id}/files")
def api_get_project_files(project_id: str):
    p_dir = WORKSPACE_DIR / project_id
    if not p_dir.exists():
        return {"files": []}
    files_list = []
    for root, _, files in os.walk(str(p_dir)):
        for f in files:
            fp = Path(root) / f
            rel = fp.relative_to(p_dir).as_posix()
            files_list.append({
                "path": rel,
                "name": f,
                "size_bytes": fp.stat().st_size,
                "modified": fp.stat().st_mtime
            })
    return {"project_id": project_id, "files": sorted(files_list, key=lambda x: x["path"])}

@app.get("/api/projects/{project_id}/file")
def api_get_file_content(project_id: str, path: str):
    p_dir = WORKSPACE_DIR / project_id
    fp = (p_dir / path).resolve()
    if not str(fp).startswith(str(p_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    if not fp.exists() or not fp.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = fp.read_text(encoding="utf-8")
        return {"path": path, "content": content}
    except Exception as e:
        return {"path": path, "error": f"Cannot read as text: {e}"}


class SwitchAccountRequest(BaseModel):
    account_id: str

class AddAccountRequest(BaseModel):
    token_json: Optional[str] = None
    email: Optional[str] = None

class FileSaveRequest(BaseModel):
    project_id: Optional[str] = None
    path: str
    content: str

class EnvUpdateRequest(BaseModel):
    env_content: str

@app.get("/api/auth/accounts")
def api_get_accounts():
    """Returns all Google Pro accounts and active account info."""
    return {
        "accounts": account_manager.get_accounts_safe(),
        "active": account_manager.get_active_account()
    }

@app.post("/api/auth/switch")
def api_switch_account(req: SwitchAccountRequest):
    """Switches active Google account seamlessly."""
    res = account_manager.switch_account(req.account_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to switch"))
    # Also attempt to reload daemon
    try:
        subprocess.run(["agy", "remote-control", "start"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
    except Exception:
        pass
    return res

@app.post("/api/auth/add")
def api_add_account(req: AddAccountRequest):
    """Adds a new Google Pro token to the pool."""
    import json
    if not req.token_json:
        raise HTTPException(status_code=400, detail="token_json required")
    try:
        tok_data = json.loads(req.token_json)
        return account_manager.add_account(tok_data, custom_email=req.email)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

@app.post("/api/auth/logout")
def api_logout():
    """Logs out active Google Pro session."""
    return account_manager.logout_active()

# IMPROVEMENT 2: One-click Full Project Backup & Restore to Storj S3
@app.post("/api/projects/{project_id}/backup")
def api_backup_project(project_id: str):
    """Creates a zip snapshot of the project and uploads to Storj 25GB S3."""
    import zipfile, io, time
    p_dir = WORKSPACE_DIR / project_id
    if not p_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(str(p_dir)):
            for f in files:
                fp = Path(root) / f
                arc_name = fp.relative_to(p_dir).as_posix()
                zip_file.write(fp, arcname=arc_name)
    
    zip_bytes = zip_buffer.getvalue()
    timestamp = int(time.time())
    s3_key = f"backups/{project_id}-{timestamp}.zip"
    
    if s3_client:
        try:
            s3_client.put_object(Bucket=STORJ_BUCKET, Key=s3_key, Body=zip_bytes)
            return {"success": True, "key": s3_key, "size_bytes": len(zip_bytes), "timestamp": timestamp}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": True, "key": "local_only", "size_bytes": len(zip_bytes)}

# IMPROVEMENT 3: Interactive Code Editor Save Endpoint
@app.post("/api/projects/save-file")
def api_save_project_file(req: FileSaveRequest):
    """Saves edited code directly from the UI editor."""
    p_dir = WORKSPACE_DIR / (req.project_id or "")
    fp = (p_dir / req.path).resolve()
    if not str(fp).startswith(str(p_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(req.content, encoding="utf-8")
    
    # Sync to Storj
    if s3_client:
        try:
            s3_key = f"projects/{req.project_id}/{req.path}" if req.project_id else f"workspace/{req.path}"
            s3_client.put_object(Bucket=STORJ_BUCKET, Key=s3_key, Body=req.content.encode("utf-8"))
        except Exception:
            pass
            
    return {"success": True, "path": req.path, "size_bytes": len(req.content.encode("utf-8"))}

# IMPROVEMENT 4: Git Branch & Commit Status in Toolbar
@app.get("/api/git/status")
def api_git_status():
    """Returns branch name and pending changes count."""
    try:
        branch_res = subprocess.run("git rev-parse --abbrev-ref HEAD", shell=True, cwd=str(WORKSPACE_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        status_res = subprocess.run("git status --short", shell=True, cwd=str(WORKSPACE_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        branch = branch_res.stdout.strip() or "main"
        modified_count = len([line for line in status_res.stdout.splitlines() if line.strip()])
        return {"branch": branch, "modified_count": modified_count, "clean": (modified_count == 0)}
    except Exception as e:
        return {"branch": "main", "modified_count": 0, "clean": True, "error": str(e)}

# IMPROVEMENT 5: Real-time Live Server Metrics & Latency Heartbeat
@app.get("/api/system/metrics")
def api_system_metrics():
    """Returns live CPU, RAM, Disk, S3 status, and system latency."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_used_mb": round(mem.used / (1024 * 1024), 1),
        "ram_total_mb": round(mem.total / (1024 * 1024), 1),
        "ram_percent": mem.percent,
        "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 1),
        "storj_connected": s3_client is not None,
        "active_account": account_manager.get_active_account()
    }

# IMPROVEMENT 6: Task Execution History Log
TASK_HISTORY_FILE = WORKSPACE_DIR / "task_history.json"
def append_task_history(entry: dict):
    try:
        hist = []
        if TASK_HISTORY_FILE.exists():
            hist = json.loads(TASK_HISTORY_FILE.read_text(encoding="utf-8"))
        hist.insert(0, entry)
        TASK_HISTORY_FILE.write_text(json.dumps(hist[:50], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

@app.get("/api/history")
def api_get_history():
    if TASK_HISTORY_FILE.exists():
        try:
            return {"history": json.loads(TASK_HISTORY_FILE.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return {"history": []}

# IMPROVEMENT 10: Environment Variables & Secrets Manager in Settings
@app.get("/api/env")
def api_get_env():
    """Returns sanitized list of environment keys."""
    safe_keys = ["PORT", "STORJ_BUCKET_NAME", "S3_BUCKET_NAME", "STORJ_ENDPOINT_URL", "S3_ENDPOINT_URL"]
    all_keys = [k for k in os.environ.keys() if not k.startswith("_")]
    return {"configured_keys": sorted(all_keys), "safe_keys": safe_keys}


@app.get("/api/git/diff")
def api_get_git_diff():
    """Returns detailed git diff for the Files Changed tab."""
    try:
        res = subprocess.run("git diff HEAD", shell=True, cwd=str(WORKSPACE_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        raw_diff = res.stdout
        
        # Parse diff into files
        files_diff = []
        current_file = None
        current_lines = []
        
        for line in raw_diff.splitlines():
            if line.startswith("diff --git"):
                if current_file:
                    files_diff.append({"file": current_file, "diff": "\n".join(current_lines)})
                parts = line.split(" ")
                current_file = parts[-1].replace("b/", "") if len(parts) >= 4 else "unknown"
                current_lines = [line]
            else:
                if current_file:
                    current_lines.append(line)
                    
        if current_file and current_lines:
            files_diff.append({"file": current_file, "diff": "\n".join(current_lines)})
            
        return {"has_changes": len(files_diff) > 0, "files": files_diff, "raw": raw_diff}
    except Exception as e:
        return {"has_changes": False, "files": [], "error": str(e)}

@app.get("/api/artifacts")
def api_get_artifacts():
    """Returns list of markdown artifacts for the Artifacts tab."""
    artifacts = []
    # Check workspace for plans, walkthroughs, and markdown reports
    for root, _, files in os.walk(str(WORKSPACE_DIR)):
        for f in files:
            if f.endswith(".md"):
                fp = Path(root) / f
                rel = fp.relative_to(WORKSPACE_DIR).as_posix()
                try:
                    text = fp.read_text(encoding="utf-8")
                    artifacts.append({
                        "name": f,
                        "path": rel,
                        "size": fp.stat().st_size,
                        "preview": text[:200]
                    })
                except Exception:
                    pass
    return {"artifacts": artifacts}


# ========================================================
# GEMINI CASCADE ENGINE & LIVE BRAINSTORM BACKEND
# ========================================================
import time

CASCADE_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview"
]

model_quota_status = {}  # {model_name: blocked_until_timestamp}

def get_active_gemini_model():
    now = time.time()
    for m in CASCADE_MODELS:
        blocked_until = model_quota_status.get(m, 0)
        if now > blocked_until:
            return m
    # If all blocked, reset and retry from start
    model_quota_status.clear()
    return CASCADE_MODELS[0]

class LiveChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []
    gemini_key: Optional[str] = None
    voice: Optional[str] = "ru-RU-DmitryNeural"

class SummarizeTaskRequest(BaseModel):
    history: List[Dict[str, str]]
    gemini_key: Optional[str] = None

class EdgeTTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "ru-RU-DmitryNeural"

async def synthesize_edge_studio_voice(text: str, voice: str = "ru-RU-DmitryNeural", retries: int = 3) -> Optional[str]:
    """Synthesizes crystal-clear Microsoft Edge studio voice and returns base64 MP3."""
    import asyncio
    import ssl
    import base64
    import re
    import edge_tts
    import edge_tts.communicate

    try:
        edge_tts.communicate._SSL_CTX = ssl._create_unverified_context()
    except Exception:
        pass

    clean = re.sub(r'[*#_`~>\[\]\(\)]', '', text)
    clean = clean.replace('—', '-').replace('–', '-').strip()
    if not clean:
        return None

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            c = edge_tts.Communicate(clean, voice)
            chunks = []
            async for chunk in c.stream():
                if chunk.get("type") == "audio":
                    chunks.append(chunk["data"])
            if chunks:
                raw = b"".join(chunks)
                return base64.b64encode(raw).decode("utf-8")
        except Exception as err:
            last_err = err
            logger.warning(f"Edge TTS attempt {attempt} failed: {err}")
            await asyncio.sleep(0.2)

    logger.error(f"synthesize_edge_studio_voice all {retries} attempts failed: {last_err}")
    return None

@app.post("/api/edge-tts")
async def api_edge_tts(req: EdgeTTSRequest):
    """Generates crystal-clear Microsoft Edge studio voice audio."""
    audio_b64 = await synthesize_edge_studio_voice(req.text, voice=req.voice or "ru-RU-DmitryNeural")
    if not audio_b64:
        raise HTTPException(status_code=500, detail="Failed to synthesize Edge studio audio")
    return {"success": True, "audio_base64": audio_b64, "voice": req.voice or "ru-RU-DmitryNeural"}

@app.post("/api/gemini/cascade-chat")
async def api_gemini_cascade_chat(req: LiveChatRequest):
    """Ultra-fast brainstorming chat with automatic 24h model cascade failover and Edge Studio TTS."""
    import httpx
    api_key = req.gemini_key or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key required")

    system_instruction = (
        "Ты — умный и дружелюбный голосовой напарник для брейншторма идей перед кодингом. "
        "Отвечай КРАТКО (1-2 емких предложения на чистом русском языке), живым человеческим языком без списков и markdown. "
        "Помогай пользователю развить идею и довести её до четкой технической задачи."
    )

    # Strictly alternate user and model roles to comply with Google Gemini API
    sanitized_contents = []
    last_role = None
    for h in (req.history or [])[-8:]:
        role = "user" if h.get("role") == "user" else "model"
        text = (h.get("text") or "").strip()
        if not text:
            continue
        if role == last_role:
            sanitized_contents[-1]["parts"][0]["text"] += f"\n{text}"
        else:
            sanitized_contents.append({"role": role, "parts": [{"text": text}]})
            last_role = role

    user_msg = (req.message or "").strip()
    if not user_msg:
        user_msg = "Привет"

    if last_role == "user":
        sanitized_contents[-1]["parts"][0]["text"] += f"\n{user_msg}"
    else:
        sanitized_contents.append({"role": "user", "parts": [{"text": user_msg}]})

    contents = sanitized_contents

    now = time.time()
    last_error = None

    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        for model_name in CASCADE_MODELS:
            blocked_until = model_quota_status.get(model_name, 0)
            if now < blocked_until:
                continue

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": contents,
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 300
                }
            }
            try:
                r = await client.post(url, json=payload)
                if r.status_code == 200:
                    data = r.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        reply = candidates[0]["content"]["parts"][0]["text"].strip()
                        audio_b64 = None
                        try:
                            audio_b64 = await synthesize_edge_studio_voice(reply, voice=req.voice or "ru-RU-DmitryNeural")
                        except Exception as tts_err:
                            logger.warning(f"Edge TTS error in cascade: {tts_err}")

                        return {
                            "success": True,
                            "reply": reply,
                            "model_used": model_name,
                            "audio_base64": audio_b64,
                            "voice": req.voice or "ru-RU-DmitryNeural"
                        }
                elif r.status_code == 429:
                    logger.warning(f"Model {model_name} quota 429 hit. Blocking for 6 hours in cascade.")
                    model_quota_status[model_name] = now + 21600  # 6h block
                    last_error = f"Quota 429 on {model_name}"
                else:
                    logger.warning(f"Model {model_name} returned {r.status_code}: {r.text[:80]}")
                    last_error = f"Error {r.status_code} on {model_name}"
            except Exception as e:
                logger.warning(f"Model {model_name} exception: {e}")
                last_error = str(e)

    # Fallback to direct simple reply
    fallback_reply = "Отличная идея! Можем сразу приступать к её реализации или уточнить детали."
    fallback_audio = await synthesize_edge_studio_voice(fallback_reply, voice=req.voice or "ru-RU-DmitryNeural")
    return {
        "success": False,
        "reply": fallback_reply,
        "model_used": "offline_fallback",
        "audio_base64": fallback_audio,
        "voice": req.voice or "ru-RU-DmitryNeural",
        "error": last_error
    }

@app.post("/api/voice-transcribe")
async def api_voice_transcribe(
    file: UploadFile = File(...),
    gemini_key: Optional[str] = Form(None)
):
    """Transcribes user speech audio directly via Gemini 3.1 Flash-Lite / 3.5 Flash."""
    import httpx
    import base64

    api_key = gemini_key or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key required")

    audio_bytes = await file.read()
    if not audio_bytes or len(audio_bytes) < 100:
        return {"success": False, "text": "NONE", "detail": "Audio too short"}

    raw_mime = file.content_type or "audio/webm"
    if "webm" in raw_mime:
        mime_type = "audio/webm"
    elif "mp4" in raw_mime:
        mime_type = "audio/mp4"
    elif "wav" in raw_mime:
        mime_type = "audio/wav"
    elif "mp3" in raw_mime or "mpeg" in raw_mime:
        mime_type = "audio/mp3"
    elif "ogg" in raw_mime:
        mime_type = "audio/ogg"
    else:
        mime_type = "audio/webm"

    b64_data = base64.b64encode(audio_bytes).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": b64_data
                        }
                    },
                    {
                        "text": "Транскрибируй то, что сказано в этой аудиозаписи на русском языке. "
                                "Выведи ТОЛЬКО распознанный текст без лишних слов, без кавычек и пояснений. "
                                "Если не слышно членораздельной речи, звучит только шум, покашливание или тишина, выведи ровно одно слово: NONE"
                    }
                ]
            }
        ]
    }

    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        for model_name in CASCADE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                r = await client.post(url, json=payload)
                if r.status_code == 200:
                    data = r.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        text = candidates[0]["content"]["parts"][0]["text"].strip()
                        return {"success": True, "text": text, "model": model_name}
            except Exception as e:
                logger.warning(f"Voice transcribe error with {model_name}: {e}")

    return {"success": False, "text": "NONE", "error": "All transcribe models failed"}

@app.post("/api/gemini/summarize-task")
def api_gemini_summarize_task(req: SummarizeTaskRequest):
    """Summarizes live voice brainstorming conversation into a structured Antigravity prompt."""
    import httpx
    api_key = req.gemini_key or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key required")

    transcript = "\n".join([f"{h.get('role', 'user')}: {h.get('text', '')}" for h in req.history])
    prompt = (
        "Ниже приведен голосовой диалог брейншторма идеи с пользователем:\n"
        f"{transcript}\n\n"
        "Сформируй из этого четкий, профессиональный и подробный промпт (техническое задание) для автономного агента Antigravity. "
        "Опиши цель проекта, архитектуру, стек и ключевые шаги реализации на русском языке. "
        "Верни ИСКЛЮЧИТЕЛЬНО готовый текст промпта без лишних вступлений."
    )

    with httpx.Client(timeout=20.0, verify=False) as client:
        for model_name in CASCADE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                r = client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
                if r.status_code == 200:
                    data = r.json()
                    res_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return {"success": True, "prompt": res_text, "model": model_name}
            except Exception:
                continue

    # Fallback prompt summary
    last_user_msg = next((h.get('text') for h in reversed(req.history) if h.get('role') == 'user'), 'Новая задача')
    return {"success": True, "prompt": f"Реализуй проект на основе идеи: {last_user_msg}", "model": "fallback"}

@app.post("/api/terminal")
def execute_command(req: CommandRequest):
    """Executes bash commands directly on the server."""
    cmd = req.command.strip()
    target_dir = WORKSPACE_DIR
    if req.project_id:
        target_dir = WORKSPACE_DIR / req.project_id.strip()
        target_dir.mkdir(parents=True, exist_ok=True)
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            cwd=str(target_dir),
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

class BrowserNavigateRequest(BaseModel):
    url: str
    action: Optional[str] = "navigate"
    selector: Optional[str] = None
    text: Optional[str] = None

@app.post("/api/browser/navigate")
async def api_browser_navigate(req: BrowserNavigateRequest):
    """Automated browser agent: navigates to URL, captures page metadata & screenshot."""
    url = req.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)

            title = await page.title()
            screenshot_bytes = await page.screenshot(type="jpeg", quality=75)
            import base64
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            current_url = page.url
            await browser.close()

            return {
                "success": True,
                "url": current_url,
                "title": title,
                "screenshot_base64": screenshot_b64
            }
    except Exception as e:
        logger.warning(f"Playwright navigation notice: {e}")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, verify=False) as client:
                r = await client.get(url)
                return {
                    "success": True,
                    "url": str(r.url),
                    "title": f"HTTP {r.status_code}",
                    "screenshot_base64": None,
                    "text_preview": r.text[:2000]
                }
        except Exception as e2:
            return {"success": False, "error": f"Browser error: {e} / {e2}"}

@app.get("/api/browser/proxy")
async def api_browser_proxy(url: str):
    """Secure proxy for in-app browser modal: strips X-Frame-Options & CSP so sites can render inside iframe."""
    target_url = url.strip()
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
            resp = await client.get(target_url, headers=headers)
            content_type = resp.headers.get("content-type", "text/html")

            # Non-HTML content (images, css, js, fonts)
            if "text/html" not in content_type:
                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    media_type=content_type,
                    headers={"Access-Control-Allow-Origin": "*"}
                )

            html_text = resp.text
            final_url = str(resp.url)

            # Injected script: keep links within proxy, notify parent window of navigation
            injected_head = (
                f'<base href="{final_url}">\n'
                '<script>\n'
                'try {\n'
                '  if (window.parent && window.parent !== window) {\n'
                f'    window.parent.postMessage({{ type: "ANTIGRAVITY_BROWSER_NAVIGATED", url: "{final_url}" }}, "*");\n'
                '  }\n'
                '} catch(e) {}\n'
                'document.addEventListener("click", function(e) {\n'
                '  var a = e.target.closest("a");\n'
                '  if (a && a.href && !a.href.startsWith("javascript:") && !a.href.startsWith("#")) {\n'
                '    e.preventDefault();\n'
                '    window.location.href = "/api/browser/proxy?url=" + encodeURIComponent(a.href);\n'
                '  }\n'
                '}, true);\n'
                'document.addEventListener("submit", function(e) {\n'
                '  var form = e.target;\n'
                '  if (form && form.action) {\n'
                '    var method = (form.method || "GET").toUpperCase();\n'
                '    if (method === "GET") {\n'
                '      e.preventDefault();\n'
                '      var formData = new FormData(form);\n'
                '      var params = new URLSearchParams(formData).toString();\n'
                '      var targetAction = form.action;\n'
                '      var sep = targetAction.indexOf("?") !== -1 ? "&" : "?";\n'
                '      window.location.href = "/api/browser/proxy?url=" + encodeURIComponent(targetAction + sep + params);\n'
                '    }\n'
                '  }\n'
                '}, true);\n'
                '</script>\n'
            )

            # Inject into <head> or prepend
            import re
            if re.search(r'<head[^>]*>', html_text, re.IGNORECASE):
                html_text = re.sub(r'(<head[^>]*>)', r'\1\n' + injected_head, html_text, count=1, flags=re.IGNORECASE)
            else:
                html_text = injected_head + html_text

            return HTMLResponse(
                content=html_text,
                status_code=resp.status_code,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "X-Robots-Tag": "noindex, nofollow"
                }
            )
    except Exception as e:
        logger.error(f"Browser proxy error for {target_url}: {e}")
        error_html = (
            '<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<title>Ошибка загрузки страницы</title>'
            '<style>'
            'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #0f172a; color: #f8fafc; }'
            '.err-box { background: #1e293b; padding: 32px; border-radius: 12px; border: 1px solid #334155; max-width: 500px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }'
            'h2 { margin-top: 0; color: #ef4444; font-size: 20px; }'
            'p { color: #94a3b8; font-size: 14px; line-height: 1.5; }'
            '.btn-row { display: flex; gap: 12px; justify-content: center; margin-top: 20px; }'
            'a.btn, button.btn { background: #2563eb; color: #fff; text-decoration: none; padding: 8px 16px; border-radius: 6px; font-weight: 500; font-size: 13px; border: none; cursor: pointer; }'
            'a.btn-sec { background: #334155; }'
            '</style></head>'
            '<body><div class="err-box">'
            f'<h2>Не удалось загрузить страницу</h2>'
            f'<p>Адрес: <b>{target_url}</b><br>Причина: {str(e)}</p>'
            '<div class="btn-row">'
            '<button class="btn" onclick="location.reload()">↻ Повторить</button>'
            f'<a class="btn btn-sec" href="{target_url}" target="_blank">Открыть во вкладке ↗</a>'
            '</div></div></body></html>'
        )
        return HTMLResponse(content=error_html, status_code=502)

async def synthesize_speech_for_reply(text: str, voice: str = "ru-RU-DmitryNeural") -> Optional[str]:
    if not text:
        return None
    try:
        import re
        clean = re.sub(r'[*`#_\[\]\(\)>~]', ' ', text)
        clean = re.sub(r'https?://\S+', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        if len(clean) > 400:
            clean = clean[:380].rsplit(' ', 1)[0] + "..."
        if clean:
            return await synthesize_edge_studio_voice(clean, voice=voice)
    except Exception as e:
        logger.warning(f"Voice synthesis for reply error: {e}")
    return None

@app.post("/api/task")
async def run_autonomous_task(req: TaskRequest):
    """
    Autonomous AI developer engine:
    Receives user goal, plans actions, writes files, executes code, saves to Storj S3.
    Supports voice_mode with concise conversational style and Dmitry Studio Neural voice.
    """
    task = req.task.strip()
    api_key = req.gemini_key or os.getenv("GEMINI_API_KEY")

    target_dir = WORKSPACE_DIR
    if req.project_id:
        target_dir = WORKSPACE_DIR / req.project_id.strip()
        target_dir.mkdir(parents=True, exist_ok=True)

    # If it's a direct terminal command
    if task.startswith("$ ") or task.startswith("bash:"):
        cmd = task.replace("bash:", "").replace("$ ", "").strip()
        return execute_command(CommandRequest(command=cmd, project_id=req.project_id))

    # Direct browser open requests (e.g., "Ты можешь открыть браузер сейчас?")
    lower_task = task.lower()
    if any(q in lower_task for q in ["открой браузер", "открыть браузер", "можешь открыть браузер", "запусти браузер", "покажи браузер", "open browser"]):
        target_url = "https://accounts.google.com"
        import re
        url_match = re.search(r'https?://\S+', task)
        if url_match:
            target_url = url_match.group(0)
        elif "github" in lower_task:
            target_url = "https://github.com/login"
        elif "telegram" in lower_task:
            target_url = "https://web.telegram.org"
        elif "render" in lower_task:
            target_url = "https://dashboard.render.com"
        elif "google" in lower_task:
            target_url = "https://accounts.google.com"

        explanation = (
            f"Да, конечно! Открываю встроенный визуальный браузер прямо сейчас:\n\n"
            f"[OPEN_BROWSER: {target_url}]\n\n"
            f"Окно браузера открыто прямо на экране. Вы можете войти в свой аккаунт, просмотреть веб-страницы или поручить мне веб-автоматизацию."
        )
        audio_b64 = None
        if req.voice_mode:
            audio_b64 = await synthesize_speech_for_reply("Да, конечно! Открываю встроенный визуальный браузер на экране.", req.voice or "ru-RU-DmitryNeural")

        return {
            "success": True,
            "project_id": req.project_id,
            "task": task,
            "explanation": explanation,
            "voice_mode": req.voice_mode,
            "voice_audio_base64": audio_b64,
            "model": "Antigravity Browser Controller"
        }

    ensure_antigravity_auth()

    # FAST-PATH FOR LIVE VOICE CONVERSATION (0.8 - 1.5s RESPONSE TIME)
    if req.voice_mode:
        try:
            logger.info("⚡ Executing Fast-Path Live Voice Response via Gemini Flash...")
            live_system_instruction = (
                "Ты — Antigravity Voice, голосовой ассистент и ведущий архитектор проекта. "
                "Ты общаешься с пользователем в живом интерактивном диалоге вслух. "
                "Твой ответ СРАЗУ озвучивается студийным голосом Дмитрия, поэтому строго соблюдай правила:\n"
                "1. Отвечай кратко, ёмко, живо и по делу (1-3 коротких предложения).\n"
                "2. НЕ используй списки, markdown, символы *, #, `, таблички и программный код (так как ответ читается голосом).\n"
                "3. Отвечай на чистом русском языке, дружелюбно, уверенно и профессионально.\n"
                "4. Если пользователь просит выполнить действие (создать файл, запустить скрипт, установить библиотеку, выполнить команду) — "
                "скажи кратко голосом 'Принято, создаю файл и запускаю в терминале' и в самом конце сообщения добавь скрытый тег [EXEC_COMMAND: bash-команда] или [EXEC_TASK: описание задачи]."
            )

            history_contents = []
            if req.history and len(req.history) > 0:
                for h in req.history[-6:]:
                    r = "user" if h.get("role") == "user" else "model"
                    t = h.get("text", "")
                    if t:
                        history_contents.append({"role": r, "parts": [{"text": t}]})
            history_contents.append({"role": "user", "parts": [{"text": task}]})

            payload = {
                "system_instruction": {"parts": [{"text": live_system_instruction}]},
                "contents": history_contents,
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 200
                }
            }

            fast_api_key = api_key or os.getenv("GEMINI_API_KEY", "")
            fast_reply_text = ""
            async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                for f_model in ["gemini-2.5-flash", "gemini-3.1-flash-lite", "gemini-2.0-flash"]:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{f_model}:generateContent?key={fast_api_key}"
                    try:
                        r = await client.post(url, json=payload)
                        if r.status_code == 200:
                            data = r.json()
                            cands = data.get("candidates", [])
                            if cands and "content" in cands[0]:
                                fast_reply_text = cands[0]["content"]["parts"][0]["text"].strip()
                                break
                    except Exception as fe:
                        logger.warning(f"Fast voice model {f_model} failed: {fe}")

            if not fast_reply_text:
                fast_reply_text = "Я на связи и готов помочь. Какую задачу решим?"

            # Extract any [EXEC_COMMAND: ...] or [EXEC_TASK: ...] to run in background
            import re
            exec_match = re.search(r'\[(EXEC_COMMAND|EXEC_TASK):\s*(.*?)\]', fast_reply_text)
            bg_action = None
            if exec_match:
                bg_action = (exec_match.group(1), exec_match.group(2).strip())
                fast_reply_text = re.sub(r'\[(EXEC_COMMAND|EXEC_TASK):.*?\]', '', fast_reply_text).strip()

            # Fast speech synthesis with Dmitry Studio (~300ms)
            audio_b64 = await synthesize_speech_for_reply(fast_reply_text, req.voice or "ru-RU-DmitryNeural")

            # Asynchronous background action if requested
            if bg_action:
                act_type, act_val = bg_action
                if act_type == "EXEC_COMMAND":
                    asyncio.create_task(asyncio.to_thread(subprocess.run, act_val, shell=True, cwd=str(target_dir)))
                else:
                    asyncio.create_task(asyncio.to_thread(subprocess.run, ["agy", "--dangerously-skip-permissions", "-p", act_val], cwd=str(target_dir)))

            return {
                "success": True,
                "project_id": req.project_id,
                "task": task,
                "explanation": fast_reply_text,
                "voice_mode": True,
                "voice_audio_base64": audio_b64,
                "model": "Gemini Live Fast Voice (1.1s)"
            }
        except Exception as fast_err:
            logger.warning(f"Fast voice path error, falling back to full agent: {fast_err}")

    # Standard Autonomous Agent Path (Antigravity CLI)
    task_prompt = task
    if req.history and len(req.history) > 0:
        recent = [f"{h.get('role','user')}: {h.get('text','')}" for h in req.history[-6:] if h.get('text')]
        if recent:
            task_prompt = "Контекст недавнего диалога в проекте:\n" + "\n".join(recent) + f"\n\n{task_prompt}"

    # Priority 1: Official Google Antigravity CLI Engine with Google Pro
    if ANTIGRAVITY_TOKEN_FILE.exists():
        try:
            logger.info(f"Executing task via official Google Antigravity CLI (Google Pro) in {target_dir}...")
            cmd = ["agy", "--dangerously-skip-permissions", "-c", "-p", task_prompt]
            res = await asyncio.to_thread(
                subprocess.run,
                cmd,
                cwd=str(target_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60
            )
            if res.returncode != 0 and "no previous conversation" in (res.stderr or "").lower():
                cmd = ["agy", "--dangerously-skip-permissions", "-p", task_prompt]
                res = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    cwd=str(target_dir),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=60
                )

            synced_to_cloud = []
            if s3_client:
                for root, _, files in os.walk(str(target_dir)):
                    for f in files:
                        local_f = Path(root) / f
                        rel_name = local_f.relative_to(target_dir).as_posix()
                        s3_key = f"projects/{req.project_id}/{rel_name}" if req.project_id else f"workspace/{rel_name}"
                        try:
                            s3_client.put_object(Bucket=STORJ_BUCKET, Key=s3_key, Body=local_f.read_bytes())
                            synced_to_cloud.append(s3_key)
                        except Exception:
                            pass

            output_text = res.stdout if res.stdout else res.stderr
            explanation_str = output_text.strip() if output_text else "Задача успешно выполнена агентом Antigravity."

            voice_audio = None
            if req.voice_mode:
                voice_audio = await synthesize_speech_for_reply(explanation_str, req.voice or "ru-RU-DmitryNeural")

            return {
                "success": (res.returncode == 0),
                "engine": "Google Antigravity CLI (Google Pro)",
                "explanation": explanation_str,
                "voice_audio_base64": voice_audio,
                "stdout": "",
                "terminal_log": (res.stdout or "") + ("\n" + res.stderr if res.stderr else ""),
                "stderr": res.stderr,
                "exit_code": res.returncode,
                "cloud_synced_files": synced_to_cloud,
                "steps": [
                    {"icon": "💭", "title": "Анализ задачи Antigravity", "status": "done"},
                    {"icon": "⚡", "title": "Выполнение в рабочем пространстве", "status": "done"},
                    {"icon": "☁️", "title": f"Синхронизация Storj S3 ({len(synced_to_cloud)} файлов)", "status": "done"} if synced_to_cloud else {"icon": "✓", "title": "Готово", "status": "done"}
                ]
            }
        except Exception as agy_err:
            logger.warning(f"Antigravity CLI execution fallback: {agy_err}")

    # Autonomous execution with Gemini AI fallback
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
            models_to_try = CASCADE_MODELS
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

            expl = data.get("explanation") or "Задача выполнена."
            cmd_stdout = res.stdout if (res.stdout and res.stdout.strip() != expl.strip()) else ""
            voice_audio = None
            if req.voice_mode:
                voice_audio = await synthesize_speech_for_reply(expl, req.voice or "ru-RU-DmitryNeural")
            return {
                "success": (res.returncode == 0),
                "engine": "Gemini 3.1 Autonomous Engine",
                "explanation": expl,
                "voice_audio_base64": voice_audio,
                "stdout": cmd_stdout,
                "terminal_log": (res.stdout or "") + ("\n" + res.stderr if res.stderr else ""),
                "stderr": res.stderr,
                "exit_code": res.returncode,
                "files_created": data.get("files_created", []),
                "cloud_synced_files": synced_to_cloud,
                "steps": [
                    {"icon": "💭", "title": "Формирование плана действий", "status": "done"},
                    {"icon": "⚡", "title": "Выполнение сценария в контейнере", "status": "done"},
                    {"icon": "📁", "title": f"Создано/обновлено файлов: {len(data.get('files_created', []))}", "status": "done"} if data.get("files_created") else {"icon": "✓", "title": "Задача завершена", "status": "done"}
                ]
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
      display: flex; flex-direction: column;
    }
    .auth-banner {
      background: rgba(28,28,30,0.95);
      border-bottom: 1px solid rgba(255,255,255,0.15);
      padding: 10px 14px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      z-index: 100;
    }
    .auth-btn-blue {
      background: #0071e3; color: #fff; border: none; padding: 8px 14px;
      border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer;
    }
    .auth-btn-green {
      background: #30d158; color: #000; border: none; padding: 8px 14px;
      border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer;
    }
    .auth-input {
      background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
      color: #fff; padding: 7px 10px; border-radius: 8px; font-size: 13px; outline: none; width: 200px;
    }
    #terminal-container { flex: 1; width: 100%; height: 100%; padding: 4px; }
  </style>
</head>
<body>
  <div class="auth-banner">
    <div style="display: flex; align-items: center; gap: 8px;">
      <span style="font-weight: 700; color: #fff; font-size: 14px;">Antigravity Cloud</span>
      <span style="width: 8px; height: 8px; border-radius: 50%; background: #30d158;"></span>
    </div>

    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
      <button class="auth-btn-blue" id="btnGetOAuth">1. 🔗 Войти через Google Pro</button>
      <input class="auth-input" id="authCodeInput" type="text" placeholder="Код авторизации..." />
      <button class="auth-btn-green" id="btnSubmitOAuth">2. ✅ Активировать</button>
    </div>

    <div id="authStatusMsg" style="width: 100%; font-size: 12px; color: #8e8e93; display: none;"></div>
  </div>

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

    setTimeout(() => {
      fitAddon.fit();
    }, 100);
    window.addEventListener('resize', () => {
      fitAddon.fit();
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
      }
    });

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/terminal/ws`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      term.write('\\r\\n\\x1b[32m✔ Подключено к терминалу сервера Antigravity!\\x1b[0m\\r\\n\\r\\n');
      setTimeout(() => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
        }
      }, 300);
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

    // Google Auth Quick-Bar
    const btnGetOAuth = document.getElementById("btnGetOAuth");
    const btnSubmitOAuth = document.getElementById("btnSubmitOAuth");
    const authCodeInput = document.getElementById("authCodeInput");
    const authStatusMsg = document.getElementById("authStatusMsg");

    btnGetOAuth.addEventListener("click", async () => {
      authStatusMsg.style.display = "block";
      authStatusMsg.style.color = "#0a84ff";
      authStatusMsg.innerText = "Генерирую ссылку на вход в Google Pro...";
      try {
        const res = await fetch("/api/antigravity/oauth-url");
        const data = await res.json();
        if (data.url) {
          window.open(data.url, "_blank");
          authStatusMsg.innerText = "Ссылка открыта в новой вкладке. Войдите под Google Pro, скопируйте код и вставьте в поле выше.";
        } else {
          authStatusMsg.innerText = "Ошибка получения ссылки: " + (data.message || "Попробуйте еще раз.");
        }
      } catch (err) {
        authStatusMsg.innerText = "Ошибка связи с сервером.";
      }
    });

    btnSubmitOAuth.addEventListener("click", async () => {
      const code = authCodeInput.value.trim();
      if (!code) {
        alert("Вставьте код авторизации, полученный от Google.");
        return;
      }
      authStatusMsg.style.display = "block";
      authStatusMsg.style.color = "#ff9f0a";
      authStatusMsg.innerText = "Отправляю код авторизации в Antigravity...";
      try {
        const res = await fetch("/api/antigravity/submit-code", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code: code })
        });
        const data = await res.json();
        if (data.success) {
          authStatusMsg.style.color = "#30d158";
          authStatusMsg.innerText = "✔ Antigravity успешно авторизован под вашей подпиской Google Pro!";
          term.write("\\r\\n\\x1b[32m✔ Antigravity успешно авторизован под Google Pro!\\x1b[0m\\r\\n");
        } else {
          authStatusMsg.style.color = "#ff453a";
          authStatusMsg.innerText = "Ошибка: " + (data.error || "Неверный код.");
        }
      } catch (err) {
        authStatusMsg.innerText = "Ошибка отправки кода.";
      }
    });
  </script>
</body>
</html>
"""

auth_process = None
auth_url_cache = None

@app.get("/api/antigravity/oauth-url")
def get_oauth_url():
    global auth_process, auth_url_cache
    import time
    import re
    import select

    if auth_process and auth_process.poll() is None and auth_url_cache:
        return {"status": "ready", "url": auth_url_cache}

    if auth_process and auth_process.poll() is None:
        try:
            auth_process.kill()
        except Exception:
            pass

    auth_process = subprocess.Popen(
        ["agy", "-p", "auth_check"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    auth_url_cache = None
    start = time.time()
    while time.time() - start < 10:
        r, _, _ = select.select([auth_process.stderr], [], [], 0.3)
        if r:
            line = auth_process.stderr.readline()
            if "https://accounts.google.com/o/oauth2/auth" in line:
                m = re.search(r'(https://accounts\.google\.com/o/oauth2/auth\S+)', line)
                if m:
                    auth_url_cache = m.group(1).strip()
                    return {"status": "ready", "url": auth_url_cache}
        if auth_process.poll() is not None:
            break

    return {"status": "error", "message": "Failed to start auth process"}

class AuthCodeRequest(BaseModel):
    code: str

@app.post("/api/antigravity/submit-code")
def submit_auth_code(req: AuthCodeRequest):
    global auth_process, auth_url_cache
    if not auth_process or auth_process.poll() is not None:
        return {"success": False, "error": "Сессия авторизации истекла. Нажмите '1. Войти через Google Pro' еще раз."}

    try:
        auth_process.stdin.write(req.code.strip() + "\n")
        auth_process.stdin.flush()
        
        try:
            stdout, stderr = auth_process.communicate(timeout=10)
            output = stdout + "\n" + stderr
            # Automatically parse token and register into AccountManager
            for p in [Path("/root/.gemini/antigravity-cli/antigravity-oauth-token"), Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"]:
                if p.exists() and p.stat().st_size > 50:
                    try:
                        tok_data = json.loads(p.read_text(encoding="utf-8"))
                        account_manager.add_account(tok_data)
                        break
                    except Exception:
                        pass
            return {"success": (auth_process.returncode == 0), "output": output, "accounts": account_manager.get_accounts_safe()}
        except subprocess.TimeoutExpired:
            return {"success": True, "output": "Код принят, авторизация сохранена!", "accounts": account_manager.get_accounts_safe()}
    except Exception as e:
        return {"success": False, "error": str(e)}

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
    import struct
    import termios

    master, slave = pty.openpty()

    # Set non-blocking on master
    flags = fcntl.fcntl(master, fcntl.F_GETFL)
    fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    # Set initial standard window size (35 rows, 120 cols) so TUI programs never render black screen
    winsize = struct.pack("HHHH", 35, 120, 0, 0)
    fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)

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
                    if msg.startswith('{"type":"resize"'):
                        try:
                            r_data = json.loads(msg)
                            r_cols = int(r_data.get("cols", 120))
                            r_rows = int(r_data.get("rows", 35))
                            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", r_rows, r_cols, 0, 0))
                            continue
                        except Exception:
                            pass
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

# ========================================================
# CLOUD CHROMIUM STREAMING WEBSOCKET (REAL-TIME CDP ENGINE)
# ========================================================
def get_chromium_executable():
    import shutil
    for path in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]:
        if os.path.exists(path):
            return path
    which_path = shutil.which("chromium") or shutil.which("google-chrome")
    if which_path:
        return which_path
    win_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for wp in win_paths:
        if os.path.exists(wp):
            return wp
    return None

active_cloud_browser = {
    "context": None,
    "page": None,
    "playwright": None
}

@app.websocket("/browser/ws")
async def cloud_browser_websocket(websocket: WebSocket):
    await websocket.accept()
    from starlette.websockets import WebSocketDisconnect
    from playwright.async_api import async_playwright

    exe = get_chromium_executable()
    logger.info(f"Cloud browser session starting with binary: {exe}")

    playwright_instance = None
    browser_context = None
    page = None
    cdp = None

    profile_dir = WORKSPACE_DIR / "chrome_user_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    try:
        playwright_instance = await async_playwright().start()
        launch_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-setuid-sandbox",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1280,800"
        ]

        browser_context = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            executable_path=exe,
            headless=True,
            args=launch_args,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        page = browser_context.pages[0] if browser_context.pages else await browser_context.new_page()
        active_cloud_browser["context"] = browser_context
        active_cloud_browser["page"] = page
        active_cloud_browser["playwright"] = playwright_instance

        cdp = await browser_context.new_cdp_session(page)

        async def on_screencast_frame(event):
            try:
                sid = event.get("sessionId")
                data = event.get("data")
                await websocket.send_json({
                    "type": "frame",
                    "data": data,
                    "url": page.url
                })
                await cdp.send("Page.screencastFrameAck", {"sessionId": sid})
            except Exception:
                pass

        cdp.on("Page.screencastFrame", lambda ev: asyncio.create_task(on_screencast_frame(ev)))

        await cdp.send("Page.startScreencast", {
            "format": "jpeg",
            "quality": 70,
            "maxWidth": 1280,
            "maxHeight": 800,
            "everyNthFrame": 1
        })

        if page.url == "about:blank":
            try:
                await page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=25000)
            except Exception as e:
                logger.warning(f"Initial navigation notice: {e}")

        await websocket.send_json({
            "type": "navigated",
            "url": page.url,
            "title": await page.title()
        })

        while True:
            msg = await websocket.receive_json()
            mtype = msg.get("type")

            if mtype == "click":
                x = int(msg.get("x", 0))
                y = int(msg.get("y", 0))
                await page.mouse.click(x, y)

            elif mtype == "type":
                text = msg.get("text", "")
                if text:
                    await page.keyboard.type(text)

            elif mtype == "press":
                key = msg.get("key", "")
                if key:
                    await page.keyboard.press(key)

            elif mtype == "scroll":
                dx = int(msg.get("deltaX", 0))
                dy = int(msg.get("deltaY", 0))
                await page.mouse.wheel(dx, dy)

            elif mtype == "navigate":
                target = msg.get("url", "").strip()
                if target:
                    if not target.startswith("http://") and not target.startswith("https://"):
                        target = "https://" + target
                    try:
                        await page.goto(target, wait_until="domcontentloaded", timeout=25000)
                    except Exception as ge:
                        logger.warning(f"Goto notice: {ge}")
                    await websocket.send_json({
                        "type": "navigated",
                        "url": page.url,
                        "title": await page.title()
                    })

            elif mtype == "back":
                try:
                    await page.go_back(timeout=15000)
                except Exception:
                    pass
                await websocket.send_json({
                    "type": "navigated",
                    "url": page.url,
                    "title": await page.title()
                })

            elif mtype == "forward":
                try:
                    await page.go_forward(timeout=15000)
                except Exception:
                    pass
                await websocket.send_json({
                    "type": "navigated",
                    "url": page.url,
                    "title": await page.title()
                })

            elif mtype == "reload":
                try:
                    await page.reload(timeout=15000)
                except Exception:
                    pass

    except WebSocketDisconnect:
        logger.info("Cloud browser WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"Cloud browser runtime error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            if browser_context:
                await browser_context.close()
            if playwright_instance:
                await playwright_instance.stop()
        except Exception:
            pass
        active_cloud_browser["context"] = None
        active_cloud_browser["page"] = None
        active_cloud_browser["playwright"] = None

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
