import os
import asyncio
import subprocess
import logging
from typing import Optional, Dict, Any, Tuple
import httpx

logger = logging.getLogger("CodespacesOrchestrator")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN", "")
REPO_OWNER = "agent-pro-ship-it"
REPO_NAME = "agent-server"
CODESPACE_NAME = "curly-computing-machine-r76qg4p65jg7cpw49"

HEAVY_KEYWORDS = [
    "парсинг", "парсер", "спарси", "scrape", "scraping", "crawler", "beautifulsoup", "selenium", "playwright",
    "видео", "конвертируй видео", "ffmpeg", "нарезка", "render video", "cv2", "opencv",
    "тяжелый", "тяжелая", "массовый", "100 страниц", "сотни страниц", "тысяч",
    "pip install torch", "pip install pandas", "pip install scipy", "pip install tensorflow", "pip install transformers",
    "torch", "tensorflow", "keras", "transformers", "huggingface", "whisper",
    "machine learning", "датасет", "большой архив", "turbo", "турбо", "8gb", "codespace", "codespaces"
]

def is_heavy_task(task_text: str, command: Optional[str] = None) -> Tuple[bool, str]:
    combined = ((task_text or "") + " " + (command or "")).lower()
    for kw in HEAVY_KEYWORDS:
        if kw in combined:
            return True, f"Обнаружена ресурсоемкая операция ({kw})"
    return False, "Штатная задача узла Render"

async def ensure_codespace_ready() -> bool:
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
            r = await client.get(f"https://api.github.com/user/codespaces/{CODESPACE_NAME}", headers=headers)
            if r.status_code != 200:
                logger.warning(f"Could not check codespace status: {r.status_code}")
                return False
            data = r.json()
            state = data.get("state")
            if state == "Available":
                return True
            if state in ["Shutdown", "Stopped", "ShuttingDown"]:
                logger.info(f"Waking up Codespace {CODESPACE_NAME} on demand...")
                await client.post(f"https://api.github.com/user/codespaces/{CODESPACE_NAME}/start", headers=headers)
                
            for _ in range(15):
                await asyncio.sleep(2.5)
                check_r = await client.get(f"https://api.github.com/user/codespaces/{CODESPACE_NAME}", headers=headers)
                if check_r.status_code == 200 and check_r.json().get("state") == "Available":
                    logger.info("Codespace is now Available!")
                    return True
    except Exception as e:
        logger.error(f"Error checking/waking codespace: {e}")
    return False

async def execute_in_codespace(command: str) -> Dict[str, Any]:
    ready = await ensure_codespace_ready()
    if not ready:
        return {"success": False, "error": "Не удалось активировать узел GitHub Codespace", "node": "GitHub 8GB"}

    env = dict(os.environ)
    env["GH_TOKEN"] = GITHUB_TOKEN

    cmd_list = [
        "gh", "codespace", "ssh",
        "-c", CODESPACE_NAME,
        "--",
        command
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_list,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        stdout, stderr = await proc.communicate()
        exit_code = proc.returncode

        asyncio.create_task(schedule_codespace_sleep(180))

        return {
            "success": exit_code == 0,
            "exit_code": exit_code,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "node": "⚡ GitHub Codespaces (8 GB RAM, 2 CPU)"
        }
    except Exception as e:
        logger.error(f"Execution error in codespace: {e}")
        return {
            "success": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": str(e),
            "node": "⚡ GitHub Codespaces (8 GB RAM, 2 CPU)"
        }

async def schedule_codespace_sleep(delay_seconds: int = 180):
    await asyncio.sleep(delay_seconds)
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            await client.post(f"https://api.github.com/user/codespaces/{CODESPACE_NAME}/stop", headers=headers)
            logger.info("Codespace stopped after idle delay.")
    except Exception:
        pass
