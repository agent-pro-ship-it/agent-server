"""
Muse AI Bridge — серверный модуль для Agent-Master.
Держит persistent Playwright-сессию к muse.ai в cloud Chromium.
Экспонирует FastAPI-эндпоинты для отправки сообщений и получения ответов.
"""

import os
import re
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("MuseBridge")

router = APIRouter(prefix="/api/muse", tags=["Muse AI Bridge"])

WORKSPACE_DIR = Path(__file__).resolve().parent / "workspace"
MUSE_PROFILE_DIR = WORKSPACE_DIR / "muse_browser_profile"
MUSE_URL = "https://muse.ai"
MAX_WAIT = 300


# ──────────────────────────────────────────────
# Persistent Muse session state
# ──────────────────────────────────────────────

_muse_state: Dict[str, Any] = {
    "playwright": None,
    "context": None,
    "page": None,
    "ready": False,
    "last_error": None,
}


def _get_chromium_executable() -> Optional[str]:
    """Find Chromium/Chrome binary on the system."""
    import shutil
    for path in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]:
        if os.path.exists(path):
            return path
    which = shutil.which("chromium") or shutil.which("google-chrome")
    if which:
        return which
    # Windows fallback
    win_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for wp in win_paths:
        if os.path.exists(wp):
            return wp
    return None


async def _ensure_muse_session():
    """Launch or reuse persistent Muse browser session."""
    if _muse_state["ready"] and _muse_state["page"]:
        try:
            # Quick health check — is the page still alive?
            await _muse_state["page"].evaluate("() => document.title")
            return
        except Exception:
            logger.warning("Muse page stale, restarting session...")
            _muse_state["ready"] = False

    await _close_muse_session()

    from playwright.async_api import async_playwright

    MUSE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    exe = _get_chromium_executable()

    pw = await async_playwright().start()

    launch_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-setuid-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--window-size=1280,800",
        "--js-flags=--max-old-space-size=128",
        "--renderer-process-limit=1",
        "--disable-extensions",
        "--disable-software-rasterizer",
    ]

    context = await pw.chromium.launch_persistent_context(
        user_data_dir=str(MUSE_PROFILE_DIR),
        executable_path=exe,
        headless=True,
        args=launch_args,
        ignore_default_args=["--enable-automation"],
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
    )

    # Block heavy media to save 350MB of RAM and prevent OOM crash
    try:
        await context.route("**/*.{png,jpg,jpeg,webp,gif,mp4,webm,woff,woff2,ttf,otf}", lambda route: route.abort())
    except Exception:
        pass

    # Anti-detection
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { runtime: {} };
    """)

    # Load saved cookies if available from multiple paths
    cookie_paths = [
        WORKSPACE_DIR / "muse_cookies.json",
        Path(__file__).resolve().parent / "muse_cookies.json",
        Path("muse_cookies.json")
    ]
    for cp in cookie_paths:
        if cp.exists():
            try:
                cookies = json.loads(cp.read_text(encoding="utf-8"))
                if isinstance(cookies, list) and cookies:
                    await context.add_cookies(cookies)
                    logger.info(f"Loaded {len(cookies)} Muse cookies from {cp}.")
                    break
            except Exception as e:
                logger.warning(f"Error loading Muse cookies from {cp}: {e}")

    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto(MUSE_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(5)

    _muse_state.update({
        "playwright": pw,
        "context": context,
        "page": page,
        "ready": True,
        "last_error": None,
    })

    logger.info("Muse browser session started.")


async def _close_muse_session():
    """Cleanly close Muse session."""
    try:
        if _muse_state["context"]:
            # Save cookies before closing
            try:
                cookies = await _muse_state["context"].cookies()
                cookies_file = WORKSPACE_DIR / "muse_cookies.json"
                cookies_file.write_text(json.dumps(cookies, indent=2), encoding="utf-8")

                # Sync to Storj if available
                try:
                    from main import s3_client, STORJ_BUCKET
                    if s3_client:
                        s3_client.put_object(
                            Bucket=STORJ_BUCKET,
                            Key="muse_cookies.json",
                            Body=cookies_file.read_bytes(),
                        )
                except Exception:
                    pass
            except Exception:
                pass

            await _muse_state["context"].close()
    except Exception:
        pass
    try:
        if _muse_state["playwright"]:
            await _muse_state["playwright"].stop()
    except Exception:
        pass

    _muse_state.update({
        "playwright": None,
        "context": None,
        "page": None,
        "ready": False,
    })


async def _is_logged_in() -> bool:
    """Check if user is logged in to Muse."""
    page = _muse_state["page"]
    if not page:
        return False
    return await page.evaluate("""() => {
        const indicators = [
            document.querySelector('[contenteditable="true"]'),
            document.querySelector('textarea'),
            document.querySelector('[data-testid*="input"]'),
            document.querySelector('[class*="chat-input"]'),
            document.querySelector('[class*="composer"]'),
            document.querySelector('[role="textbox"]'),
        ];
        return indicators.some(el => el !== null);
    }""")


async def _get_response_snapshot() -> Dict[str, Any]:
    """Get current state of responses on page."""
    page = _muse_state["page"]
    return await page.evaluate("""() => {
        const result = { count: 0, lastText: "" };

        // 1. Match Muse AI 2026 Hatch bubbles
        const hatchBubbles = document.querySelectorAll(
            '.hatch-chat-groupable-bubble, [class*="hatch-agent-bubble"], [class*="hatch-chat-groupable-bubble"]'
        );
        if (hatchBubbles.length > 0) {
            const agentBubbles = Array.from(hatchBubbles).filter(el => {
                const parent = el.closest('.ms-auto') || el.closest('[class*="ms-auto"]');
                return !parent && !el.className.includes('ms-auto');
            });
            if (agentBubbles.length > 0) {
                result.count = agentBubbles.length;
                result.lastText = agentBubbles[agentBubbles.length - 1].innerText.trim();
                return result;
            }
        }

        // 2. Try role-based selectors
        const roleSelectors = [
            '[data-message-author-role="assistant"]',
            '[data-message-role="assistant"]',
            '[data-testid*="assistant-message"]',
            '[data-testid*="response"]',
        ];
        for (const sel of roleSelectors) {
            const els = document.querySelectorAll(sel);
            if (els.length > 0) {
                result.count = els.length;
                result.lastText = els[els.length - 1].innerText.trim();
                return result;
            }
        }

        // 3. Try class-based selectors
        const classSelectors = [
            '[class*="assistant"]',
            '[class*="agent-message"]',
            '[class*="ai-message"]',
            '[class*="model-response"]',
            '[class*="response-content"]',
            '[class*="bot-message"]',
        ];
        for (const sel of classSelectors) {
            const els = document.querySelectorAll(sel);
            if (els.length > 0) {
                result.count = els.length;
                result.lastText = els[els.length - 1].innerText.trim();
                return result;
            }
        }

        // 4. Fallback: all message-like containers
        const allMsgs = document.querySelectorAll(
            '[class*="message"]:not([class*="input"]):not([class*="composer"])'
        );
        if (allMsgs.length > 0) {
            result.count = allMsgs.length;
            result.lastText = allMsgs[allMsgs.length - 1].innerText.trim();
        }

        return result;
    }""")


async def _is_generating() -> bool:
    """Check if Muse is still streaming a response."""
    page = _muse_state["page"]
    return await page.evaluate("""() => {
        const indicators = [
            '[class*="loading"]',
            '[class*="spinner"]',
            '[class*="generating"]',
            '[class*="streaming"]',
            '[class*="typing"]',
            '[class*="progress"]',
            'button[aria-label*="Stop"]',
            'button[aria-label*="stop"]',
            'button[aria-label*="Cancel"]',
            '[class*="stop-button"]',
            '[data-testid*="stop"]',
            '[class*="cursor"][class*="blink"]',
        ];
        for (const sel of indicators) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) return true;
        }
        return false;
    }""")


async def _type_and_send(message: str):
    """Type a message into Muse chat and send it."""
    page = _muse_state["page"]

    textarea = page.locator('textarea, [placeholder="Message"], [role="textbox"], [contenteditable="true"]').first
    if await textarea.count() > 0:
        try:
            await textarea.click()
            await textarea.fill(message)
            await asyncio.sleep(0.3)
            await textarea.press("Enter")
            await asyncio.sleep(0.5)
            return
        except Exception:
            pass

    # Fallback to keyboard
    await page.keyboard.type(message)
    await page.keyboard.press("Enter")
    await asyncio.sleep(0.5)


async def _wait_for_response(before_snapshot: Dict, timeout: int = MAX_WAIT) -> str:
    """Wait for a new response and return its text once generation is complete."""
    start = time.time()

    while time.time() - start < timeout:
        await asyncio.sleep(2)
        current = await _get_response_snapshot()

        new_appeared = (
            current["count"] > before_snapshot["count"]
            or (
                current["lastText"]
                and current["lastText"] != before_snapshot["lastText"]
                and len(current["lastText"]) > len(before_snapshot.get("lastText", ""))
            )
        )

        if new_appeared:
            # Wait for streaming to finish
            stable_text = ""
            stable_checks = 0

            while time.time() - start < timeout:
                await asyncio.sleep(2)
                generating = await _is_generating()
                snap = await _get_response_snapshot()
                latest = snap["lastText"]

                if not generating:
                    if latest == stable_text:
                        stable_checks += 1
                        if stable_checks >= 2:
                            return latest
                    else:
                        stable_text = latest
                        stable_checks = 0
                else:
                    stable_text = latest
                    stable_checks = 0

            # Timeout but got partial response
            snap = await _get_response_snapshot()
            return snap["lastText"] or "[PARTIAL RESPONSE — TIMEOUT]"

    return "[NO RESPONSE — TIMEOUT]"


def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    """Extract fenced code blocks from response text."""
    pattern = r'```(\w*)\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    return [{"language": lang or "text", "code": code.strip()} for lang, code in matches]


# ──────────────────────────────────────────────
# API Endpoints
# ──────────────────────────────────────────────

class MuseSendRequest(BaseModel):
    message: str
    timeout: Optional[int] = 300

class MuseCookieRequest(BaseModel):
    cookies: Any

class MuseStatusResponse(BaseModel):
    ready: bool
    logged_in: bool
    url: Optional[str] = None
    error: Optional[str] = None


@router.get("/status")
async def muse_status():
    """Check Muse bridge status — is browser running, is user logged in."""
    try:
        if not _muse_state["ready"]:
            return {"ready": False, "logged_in": False, "url": None, "error": "Session not started"}

        page = _muse_state["page"]
        url = page.url if page else None
        logged_in = await _is_logged_in() if page else False

        return {
            "ready": True,
            "logged_in": logged_in,
            "url": url,
            "error": _muse_state.get("last_error"),
        }
    except Exception as e:
        return {"ready": False, "logged_in": False, "url": None, "error": str(e)}


@router.post("/start")
async def muse_start():
    """Start or restart the Muse browser session."""
    try:
        await _ensure_muse_session()
        logged_in = await _is_logged_in()

        return {
            "success": True,
            "logged_in": logged_in,
            "url": _muse_state["page"].url if _muse_state["page"] else None,
            "message": "Muse session started." + (
                "" if logged_in else " NOT LOGGED IN — import cookies via POST /api/muse/cookies"
            ),
        }
    except Exception as e:
        _muse_state["last_error"] = str(e)
        logger.error(f"Muse session start error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/stop")
async def muse_stop():
    """Stop the Muse browser session and save cookies."""
    await _close_muse_session()
    return {"success": True, "message": "Muse session closed. Cookies saved."}


@router.post("/cookies")
async def muse_import_cookies(req: MuseCookieRequest):
    """Import cookies for Muse authentication."""
    try:
        raw = req.cookies
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, list):
            raise HTTPException(status_code=400, detail="Cookies must be a JSON array")

        valid = []
        for c in raw:
            if not isinstance(c, dict):
                continue
            name = c.get("name")
            value = c.get("value")
            if not name or value is None:
                continue
            cookie = {
                "name": str(name),
                "value": str(value),
                "domain": str(c.get("domain", ".muse.ai")),
                "path": c.get("path", "/"),
            }
            if "secure" in c:
                cookie["secure"] = bool(c["secure"])
            if "httpOnly" in c:
                cookie["httpOnly"] = bool(c["httpOnly"])
            same_site = str(c.get("sameSite", "")).lower()
            if same_site in ["strict"]:
                cookie["sameSite"] = "Strict"
            elif same_site in ["none", "no_restriction"]:
                cookie["sameSite"] = "None"
            else:
                cookie["sameSite"] = "Lax"
            valid.append(cookie)

        # Save cookies
        cookies_file = WORKSPACE_DIR / "muse_cookies.json"
        cookies_file.write_text(json.dumps(valid, indent=2), encoding="utf-8")

        # Sync to Storj
        try:
            from main import s3_client, STORJ_BUCKET
            if s3_client:
                s3_client.put_object(
                    Bucket=STORJ_BUCKET,
                    Key="muse_cookies.json",
                    Body=cookies_file.read_bytes(),
                )
        except Exception:
            pass

        # Apply to active session
        if _muse_state["context"]:
            await _muse_state["context"].add_cookies(valid)
            if _muse_state["page"]:
                await _muse_state["page"].reload()
                await asyncio.sleep(3)

        logged_in = await _is_logged_in() if _muse_state["page"] else False

        return {
            "success": True,
            "count": len(valid),
            "logged_in": logged_in,
            "message": f"Imported {len(valid)} cookies. Synced to Storj.",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/send")
async def muse_send(req: MuseSendRequest):
    """Send a message to Muse and return the response."""
    try:
        await _ensure_muse_session()

        if not await _is_logged_in():
            return {
                "success": False,
                "error": "Not logged in to Muse. Import cookies via POST /api/muse/cookies first.",
            }

        # Snapshot before sending
        before = await _get_response_snapshot()

        # Type and send
        await _type_and_send(req.message)

        # Wait for response
        response_text = await _wait_for_response(before, timeout=req.timeout or MAX_WAIT)

        # Extract code blocks
        code_blocks = extract_code_blocks(response_text)

        return {
            "success": True,
            "response": response_text,
            "code_blocks": code_blocks,
            "code_blocks_count": len(code_blocks),
        }

    except Exception as e:
        _muse_state["last_error"] = str(e)
        logger.error(f"Muse send error: {e}")
        return {"success": False, "error": str(e), "response": None}


@router.post("/screenshot")
async def muse_screenshot():
    """Take a screenshot of the current Muse page."""
    import base64

    try:
        await _ensure_muse_session()
        page = _muse_state["page"]
        if not page:
            raise HTTPException(status_code=500, detail="No active page")

        screenshot = await page.screenshot(type="jpeg", quality=75)
        b64 = base64.b64encode(screenshot).decode("utf-8")

        return {
            "success": True,
            "url": page.url,
            "screenshot_base64": b64,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/debug")
async def muse_debug():
    """Dump page DOM structure for debugging selectors."""
    try:
        await _ensure_muse_session()
        page = _muse_state["page"]
        if not page:
            return {"error": "No active page"}

        info = await page.evaluate("""() => {
            const dump = {};

            dump.title = document.title;
            dump.url = window.location.href;

            // Contenteditable
            dump.contenteditable = Array.from(
                document.querySelectorAll('[contenteditable="true"]')
            ).map(el => ({
                tag: el.tagName,
                classes: el.className.substring(0, 200),
                role: el.getAttribute('role'),
                testid: el.getAttribute('data-testid'),
            }));

            // Textareas
            dump.textareas = Array.from(
                document.querySelectorAll('textarea')
            ).map(el => ({
                classes: el.className.substring(0, 200),
                placeholder: el.placeholder,
                testid: el.getAttribute('data-testid'),
            }));

            // Buttons with aria-label
            dump.buttons = Array.from(
                document.querySelectorAll('button[aria-label]')
            ).slice(0, 30).map(el => ({
                label: el.getAttribute('aria-label'),
                testid: el.getAttribute('data-testid'),
                disabled: el.disabled,
            }));

            // Custom elements
            const custom = new Set();
            document.querySelectorAll('*').forEach(el => {
                if (el.tagName.includes('-')) custom.add(el.tagName.toLowerCase());
            });
            dump.custom_elements = Array.from(custom).sort();

            // Message elements
            const msgSels = [
                '[class*="message"]', '[class*="response"]', '[class*="assistant"]',
                '[class*="agent"]', '[data-message-role]', '[data-message-author-role]',
            ];
            const found = new Set();
            msgSels.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => found.add(el));
            });
            dump.message_elements = Array.from(found).slice(0, 20).map(el => ({
                tag: el.tagName,
                classes: el.className.substring(0, 200),
                role: el.getAttribute('data-message-role') ||
                      el.getAttribute('data-message-author-role'),
                testid: el.getAttribute('data-testid'),
                textLen: el.innerText.length,
            }));

            return dump;
        }""")

        return {"success": True, "dom": info}
    except Exception as e:
        return {"success": False, "error": str(e)}
