"""
Muse Agent Bridge — task queue that lets another agent use the real Muse
agent as a subagent (coding tasks).

How it works:
  1. Client (other agent)  -> POST /api/agent/tasks  (Antigravity master key)
  2. Muse's worker (outbound polling, every ~2 min)
     -> POST /api/agent/worker/claim  (X-Worker-Key: MUSE_WORKER_KEY)
     executes the task on its own machine, then
     -> POST /api/agent/worker/tasks/{id}/result
  3. Client -> GET /api/agent/tasks/{id}  (poll until done/failed),
     downloads result files via /files/{name}.

This module is purely additive: it only registers routes under /api/agent
and does not touch any existing endpoint or behaviour.
"""

import base64
import binascii
import hmac
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

logger = logging.getLogger("MuseAgentBridge")

router = APIRouter(prefix="/api/agent", tags=["Muse Agent Bridge"])

# Reuse the gateway's master-key check so clients use the same credential.
try:
    from antigravity_gateway import verify_auth as verify_master
except Exception as exc:  # pragma: no cover - gateway is always present in prod
    logger.warning("Could not import verify_auth: %s", exc)
    verify_master = None

TASK_PREFIX = "agent-tasks/"
ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")
# local-fallback filenames are key.replace("/", "_"); task JSONs look like
# "agent-tasks_<tid>.json" — this reconstructs the key from such a filename.
_LOCAL_TASK_RE = re.compile(r"^agent-tasks_([A-Za-z0-9_-]{8,64})$")
MAX_PROMPT = 60000
MAX_FILES = 20
MAX_FILE_BYTES = 5 * 1024 * 1024


# ── storage: Storj S3 primary, local workspace fallback ──────────────

class TaskStore:
    def __init__(self) -> None:
        self.s3 = None
        self.bucket = os.getenv("STORJ_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME", "agent-vault")
        endpoint = os.getenv("STORJ_ENDPOINT_URL") or os.getenv("S3_ENDPOINT_URL",
                                                                "https://gateway.storjshare.io")
        ak = os.getenv("STORJ_ACCESS_KEY_ID") or os.getenv("S3_ACCESS_KEY_ID")
        sk = os.getenv("STORJ_SECRET_ACCESS_KEY") or os.getenv("S3_SECRET_ACCESS_KEY")
        if ak and sk:
            try:
                import boto3
                from botocore.config import Config
                # NOTE: same client config as main.py — Storj's gateway rejects
                # PUTs without a Content-Length header, which happens when
                # payload signing is off. Keep in sync with main.py.
                self.s3 = boto3.client(
                    "s3", endpoint_url=endpoint,
                    aws_access_key_id=ak, aws_secret_access_key=sk,
                    config=Config(
                        signature_version="s3v4",
                        s3={"payload_signing_enabled": True,
                            "addressing_style": "path"},
                        request_checksum_calculation="when_required",
                        response_checksum_validation="when_required",
                    ),
                    verify=False,
                )
                logger.info("MuseAgentBridge: S3 task store ready (bucket=%s)", self.bucket)
            except Exception as exc:
                logger.warning("MuseAgentBridge: S3 init failed, using local store: %s", exc)
                self.s3 = None
        self.local_dir = Path(__file__).resolve().parent / "workspace" / "agent_tasks"
        self.local_dir.mkdir(parents=True, exist_ok=True)

    # -- low level -----------------------------------------------------
    def _key(self, *parts: str) -> str:
        return TASK_PREFIX + "/".join(parts)

    def put_bytes(self, key: str, data: bytes) -> None:
        if self.s3:
            try:
                self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)
                return
            except Exception as exc:
                logger.warning("S3 put failed (%s), falling back to local", exc)
        p = self.local_dir / key.replace("/", "_")
        p.write_bytes(data)

    def get_bytes(self, key: str) -> Optional[bytes]:
        if self.s3:
            try:
                r = self.s3.get_object(Bucket=self.bucket, Key=key)
                return r["Body"].read()
            except Exception:
                pass
        p = self.local_dir / key.replace("/", "_")
        return p.read_bytes() if p.is_file() else None

    def delete_key(self, key: str) -> None:
        if self.s3:
            try:
                self.s3.delete_object(Bucket=self.bucket, Key=key)
            except Exception:
                pass
        p = self.local_dir / key.replace("/", "_")
        try:
            p.unlink()
        except FileNotFoundError:
            pass

    def list_task_keys(self) -> List[str]:
        # Merge S3 and local listings (dedup by key): the local dir is a
        # fallback when S3 writes fail, so a task must never become invisible
        # just because it landed in the other store.
        seen: Dict[str, None] = {}
        if self.s3:
            try:
                paginator = self.s3.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=self.bucket, Prefix=TASK_PREFIX):
                    for obj in page.get("Contents", []):
                        k = obj["Key"]
                        if k.count("/") == 1 and k.endswith(".json"):
                            seen[k] = None
            except Exception as exc:
                logger.warning("S3 list failed, using local: %s", exc)
        for p in self.local_dir.glob("*.json"):
            m = _LOCAL_TASK_RE.match(p.stem)
            if m:
                seen.setdefault(TASK_PREFIX + m.group(1) + ".json", None)
        return sorted(seen.keys())


store = TaskStore()


def _task_key(tid: str) -> str:
    return store._key(tid + ".json")


def load_task(tid: str) -> Optional[Dict[str, Any]]:
    raw = store.get_bytes(_task_key(tid))
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        return None


def save_task(task: Dict[str, Any]) -> None:
    store.put_bytes(_task_key(task["id"]),
                    json.dumps(task, ensure_ascii=False).encode("utf-8"))


def check_id(tid: str) -> str:
    if not ID_RE.match(tid or ""):
        raise HTTPException(400, "bad task id")
    return tid


def safe_name(name: str) -> str:
    base = os.path.basename((name or "").strip())
    if not base or base in (".", "..") or not re.match(r"^[\w.\- ]{1,128}$", base):
        raise HTTPException(400, f"bad file name: {name!r}")
    return base


def decode_files(files: Optional[Dict[str, str]]) -> Dict[str, bytes]:
    out: Dict[str, bytes] = {}
    if not files:
        return out
    if not isinstance(files, dict) or len(files) > MAX_FILES:
        raise HTTPException(400, f"files must be an object with <= {MAX_FILES} entries")
    for name, b64 in files.items():
        sname = safe_name(name)
        if not isinstance(b64, str):
            raise HTTPException(400, f"bad payload for file: {sname}")
        try:
            blob = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(400, f"bad base64 for file: {sname}")
        if len(blob) > MAX_FILE_BYTES:
            raise HTTPException(400, f"file too big (5MB max): {sname}")
        out[sname] = blob
    return out


# ── auth ─────────────────────────────────────────────────────────────

def verify_worker(request: Request,
                  x_worker_key: Optional[str] = Header(None, alias="X-Worker-Key"),
                  authorization: Optional[str] = Header(None)):
    """Worker auth: dedicated MUSE_WORKER_KEY when configured, otherwise the
    same master key the clients use (so the bridge works with zero extra setup)."""
    want = os.getenv("MUSE_WORKER_KEY", "")
    if want and x_worker_key and hmac.compare_digest(x_worker_key, want):
        return True
    try:
        from antigravity_gateway import ANTIGRAVITY_MASTER_KEY
    except Exception:
        ANTIGRAVITY_MASTER_KEY = ""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif x_worker_key:
        token = x_worker_key
    if token and ANTIGRAVITY_MASTER_KEY and hmac.compare_digest(token, ANTIGRAVITY_MASTER_KEY):
        return True
    raise HTTPException(401, "invalid worker credentials")


def _master_dep():
    # verify_auth is a plain function usable as a dependency
    if verify_master is None:
        raise HTTPException(500, "master auth unavailable")
    return Depends(verify_master)


# ── models ───────────────────────────────────────────────────────────

class TaskSubmit(BaseModel):
    prompt: str
    files: Optional[Dict[str, str]] = None
    timeout_secs: Optional[int] = 1800


class TaskResult(BaseModel):
    output: str = ""
    files: Optional[Dict[str, str]] = None
    error: Optional[str] = None


# ── client endpoints (master key) ────────────────────────────────────

def _create_task(prompt: str, files: Optional[Dict[str, str]], timeout_secs: int) -> Dict[str, Any]:
    prompt = (prompt or "").strip()
    if not prompt:
        raise HTTPException(400, "prompt required")
    if len(prompt) > MAX_PROMPT:
        raise HTTPException(400, f"prompt too long ({MAX_PROMPT} max)")
    blobs = decode_files(files)
    tid = uuid.uuid4().hex[:16]
    for name, blob in blobs.items():
        store.put_bytes(store._key(tid, "in", name), blob)
    task = {
        "id": tid,
        "prompt": prompt,
        "files_in": sorted(blobs.keys()),
        "timeout_secs": min(max(int(timeout_secs or 1800), 60), 7200),
        "received_at": int(time.time()),
        "attempts": 0,
        "status": "pending",
        "result": None,
    }
    save_task(task)
    logger.info("agent task %s submitted (%d input files)", tid, len(blobs))
    return task


@router.post("/tasks", status_code=202)
def submit_task(body: TaskSubmit, _ok=Depends(verify_master)):
    task = _create_task(body.prompt, body.files, body.timeout_secs)
    return {"id": task["id"], "status": "pending"}


class AskRequest(BaseModel):
    prompt: str
    files: Optional[Dict[str, str]] = None
    timeout_secs: Optional[int] = 1800
    wait_secs: Optional[int] = 90


@router.post("/ask")
def ask_sync(body: AskRequest, _ok=Depends(verify_master)):
    """Synchronous convenience endpoint for skills: creates the task and holds
    the request (up to wait_secs, max 100s) until the worker finishes it.
    On timeout returns 202 with the task id — keep polling GET /tasks/{id}."""
    wait = min(max(int(body.wait_secs or 90), 10), 100)
    task = _create_task(body.prompt, body.files, body.timeout_secs)
    tid = task["id"]
    deadline = time.time() + wait
    while time.time() < deadline:
        t = load_task(tid)
        if t and t.get("status") in ("done", "failed"):
            return t
        time.sleep(3)
    t = load_task(tid) or task
    return JSONResponse(
        status_code=202,
        content={"id": tid, "status": t.get("status"),
                 "note": "still running; poll GET /api/agent/tasks/{id}"},
    )


@router.get("/tasks")
def list_tasks(_ok=Depends(verify_master)):
    items = []
    for key in store.list_task_keys():
        raw = store.get_bytes(key)
        if not raw:
            continue
        try:
            t = json.loads(raw.decode("utf-8"))
        except ValueError:
            continue
        items.append({
            "id": t.get("id"),
            "status": t.get("status"),
            "received_at": t.get("received_at"),
            "prompt_preview": (t.get("prompt") or "")[:120],
        })
    items.sort(key=lambda x: x.get("received_at") or 0, reverse=True)
    return {"tasks": items[:50]}


@router.get("/tasks/{tid}")
def get_task(tid: str, _ok=Depends(verify_master)):
    t = load_task(check_id(tid))
    if t is None:
        raise HTTPException(404, "task not found")
    return t


@router.get("/tasks/{tid}/files/{name}")
def download_result_file(tid: str, name: str, _ok=Depends(verify_master)):
    t = load_task(check_id(tid))
    sname = safe_name(name)
    if t is None or sname not in ((t.get("result") or {}).get("files") or []):
        raise HTTPException(404, "file not found")
    blob = store.get_bytes(store._key(tid, "out", sname))
    if blob is None:
        raise HTTPException(404, "file gone")
    return Response(content=blob, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{sname}"'})


@router.delete("/tasks/{tid}")
def delete_task(tid: str, _ok=Depends(verify_master)):
    t = load_task(check_id(tid))
    if t is None:
        raise HTTPException(404, "task not found")
    if t.get("status") in ("pending", "running"):
        raise HTTPException(409, "task in progress")
    store.delete_key(_task_key(tid))
    for sub in ("in", "out"):
        for name in (t.get("files_in") if sub == "in" else (t.get("result") or {}).get("files") or []):
            store.delete_key(store._key(tid, sub, name))
    return {"deleted": True}


@router.get("/health")
def health(_ok=Depends(verify_master)):
    pending = 0
    for key in store.list_task_keys():
        raw = store.get_bytes(key)
        if not raw:
            continue
        try:
            if json.loads(raw.decode("utf-8")).get("status") == "pending":
                pending += 1
        except ValueError:
            pass
    return {"ok": True, "pending": pending, "time": int(time.time())}


# ── worker endpoints (MUSE_WORKER_KEY) ───────────────────────────────
# NOTE: single worker by design; no distributed locking needed.

@router.post("/worker/claim")
def claim_task(_ok=Depends(verify_worker)):
    now = int(time.time())
    oldest = None
    for key in store.list_task_keys():
        raw = store.get_bytes(key)
        if not raw:
            continue
        try:
            t = json.loads(raw.decode("utf-8"))
        except ValueError:
            continue
        st = t.get("status")
        # pending always claimable; running only if stale (>30 min without result)
        # so a crashed worker never leaves a task stuck forever
        if st == "pending":
            eligible = True
        elif st == "running" and (now - int(t.get("claimed_at") or 0)) > 1800:
            eligible = True
        else:
            continue
        if oldest is None or (t.get("received_at") or 0) < (oldest.get("received_at") or 0):
            oldest = t
    if oldest is None:
        return Response(status_code=204)
    oldest["status"] = "running"
    oldest["claimed_at"] = now
    oldest["attempts"] = int(oldest.get("attempts") or 0) + 1
    save_task(oldest)
    # bundle input files as base64 for the worker
    bundle = {}
    for name in oldest.get("files_in") or []:
        blob = store.get_bytes(store._key(oldest["id"], "in", name))
        if blob is not None:
            bundle[name] = base64.b64encode(blob).decode()
    oldest["files_bundle"] = bundle
    logger.info("agent task %s claimed (attempt %d)", oldest["id"], oldest["attempts"])
    return oldest


@router.post("/worker/tasks/{tid}/result")
def post_result(tid: str, body: TaskResult, _ok=Depends(verify_worker)):
    t = load_task(check_id(tid))
    if t is None:
        raise HTTPException(404, "task not found")
    blobs = decode_files(body.files)
    for name, blob in blobs.items():
        store.put_bytes(store._key(tid, "out", name), blob)
    failed = bool(body.error)
    t["status"] = "failed" if failed else "done"
    t["result"] = {
        "output": body.output or "",
        "files": sorted(blobs.keys()),
        "error": body.error,
    }
    t["completed_at"] = int(time.time())
    save_task(t)
    logger.info("agent task %s %s (%d files)", tid, t["status"], len(blobs))
    return {"id": tid, "status": t["status"]}
