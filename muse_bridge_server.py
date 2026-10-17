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
    if not page:
        return {"count": 0, "lastText": ""}
    return await page.evaluate("""() => {
        const result = { count: 0, lastText: "" };

        // 1. Meta Muse 2026 messages: container with group/msg
        const msgs = Array.from(document.querySelectorAll('[class*="group/msg"]'));
        const assistantMsgs = msgs.filter(el => {
            const cls = typeof el.className === 'string' ? el.className : '';
            return !cls.includes('ms-auto') && !el.closest('.ms-auto');
        });

        if (assistantMsgs.length > 0) {
            result.count = assistantMsgs.length;
            const last = assistantMsgs[assistantMsgs.length - 1];
            const clone = last.cloneNode(true);
            clone.querySelectorAll('button, svg, [role="toolbar"], [class*="opacity-0"]').forEach(b => b.remove());
            const clean = (clone.innerText || clone.textContent || '').trim();
            if (clean) {
                result.lastText = clean;
                return result;
            }
        }

        // 2. Meta Muse AI uses 'Copy response' buttons on every assistant answer
        const copyBtns = Array.from(
            document.querySelectorAll('button[aria-label*="Copy" i], button[aria-label*="copy" i], button[aria-label*="Копировать" i]')
        );
        if (copyBtns.length > 0) {
            result.count = copyBtns.length;
            const lastBtn = copyBtns[copyBtns.length - 1];

            // Traverse up to find the message bubble containing this copy button
            let cur = lastBtn.parentElement;
            let targetContainer = cur;
            while (cur && cur !== document.body) {
                // If container contains more than 1 copy button, we went too far up
                const nested = cur.querySelectorAll('button[aria-label*="Copy" i], button[aria-label*="copy" i], button[aria-label*="Копировать" i]');
                if (nested.length > 1) {
                    break;
                }
                targetContainer = cur;
                cur = cur.parentElement;
            }

            if (targetContainer) {
                const clone = targetContainer.cloneNode(true);
                clone.querySelectorAll('button, svg, [role="toolbar"], [aria-label*="Copy" i], [aria-label*="React" i], [aria-label*="Reply" i], [aria-label*="options" i]').forEach(el => el.remove());
                const cleanText = (clone.innerText || clone.textContent || "").trim();
                if (cleanText) {
                    result.lastText = cleanText;
                    return result;
                }
            }
        }

        // 2. Match Muse AI Hatch bubbles
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

        // 3. Try role-based selectors
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

        // 4. Try class-based selectors
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

        // 5. Fallback: all message-like containers
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
    if not page:
        return False
    return await page.evaluate("""() => {
        const indicators = [
            'button[aria-label*="Stop" i]',
            'button[aria-label*="stop" i]',
            'button[aria-label*="Cancel" i]',
            '[class*="stop-button"]',
            '[data-testid*="stop"]',
            '[class*="loading"]',
            '[class*="spinner"]',
            '[class*="generating"]',
            '[class*="streaming"]',
            '[class*="typing"]',
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
    if not page:
        raise Exception("No active page")

    textarea = page.locator('textarea, [placeholder*="Message" i], [role="textbox"], [contenteditable="true"]').first
    if await textarea.count() > 0:
        try:
            await textarea.click()
            await textarea.fill(message)
            await asyncio.sleep(0.3)
        except Exception:
            await page.keyboard.type(message)
            await asyncio.sleep(0.3)

    # Ensure React/DOM input events fire
    await page.evaluate("""(msg) => {
        const ta = document.querySelector('textarea, [placeholder*="Message" i], [role="textbox"]');
        if (ta) {
            if (!ta.value || ta.value !== msg) {
                ta.value = msg;
            }
            ta.dispatchEvent(new Event('input', { bubbles: true }));
            ta.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }""", message)
    await asyncio.sleep(0.4)

    # Find and click Send button in the composer pill
    clicked = await page.evaluate("""() => {
        const ta = document.querySelector('textarea, [placeholder*="Message" i], [role="textbox"]');
        if (!ta) return false;

        const container = ta.closest('form') ||
                          ta.closest('div[class*="rounded"]') ||
                          ta.parentElement?.parentElement ||
                          ta.parentElement;

        if (container) {
            const btns = Array.from(container.querySelectorAll('button')).filter(b => !b.disabled);
            // 1. Explicit send label
            for (const b of btns) {
                const label = (b.getAttribute('aria-label') || '').toLowerCase();
                if (label.includes('send') || label.includes('отправить') || label.includes('submit')) {
                    b.click();
                    return true;
                }
            }
            // 2. Button with SVG (the round arrow up button in Meta/Muse AI)
            const svgBtns = btns.filter(b => b.querySelector('svg'));
            if (svgBtns.length > 0) {
                svgBtns[svgBtns.length - 1].click();
                return true;
            }
            // 3. Last enabled button in composer
            if (btns.length > 0) {
                btns[btns.length - 1].click();
                return true;
            }
        }
        return false;
    }""")

    if not clicked:
        try:
            await textarea.press("Enter")
        except Exception:
            await page.keyboard.press("Enter")
    else:
        # Also send Enter as backup if input not cleared
        await asyncio.sleep(0.5)
        is_cleared = await page.evaluate("""() => {
            const ta = document.querySelector('textarea, [placeholder*="Message" i]');
            return !ta || !ta.value || ta.value.trim().length === 0;
        }""")
        if not is_cleared:
            try:
                await textarea.press("Enter")
            except Exception:
                await page.keyboard.press("Enter")

    await asyncio.sleep(1.0)


async def _wait_for_response(before_snapshot: Dict, timeout: int = 300) -> str:
    """Wait for a new response and return its text once generation is complete.
    Actively tracks whether Muse is typing, extends timeout dynamically, and returns the full output.
    """
    start = time.time()
    before_count = before_snapshot.get("count", 0)
    before_text = before_snapshot.get("lastText", "")
    before_len = len(before_text)

    # Phase 1: Wait for Muse to start responding (first characters or bubble appears)
    first_detected_time = None
    last_text = ""
    last_len = 0
    last_activity_time = time.time()

    # Wait up to 60s for Muse to begin output
    while (time.time() - start) < 60:
        await asyncio.sleep(1.5)
        current = await _get_response_snapshot()
        curr_text = current.get("lastText", "")
        curr_len = len(curr_text)
        curr_count = current.get("count", 0)

        is_new = (
            curr_count > before_count
            or (curr_len > before_len and curr_text != before_text)
            or (curr_len > 0 and before_len == 0)
        )

        if is_new:
            first_detected_time = time.time()
            last_text = curr_text
            last_len = curr_len
            last_activity_time = time.time()
            break

        if await _is_generating():
            first_detected_time = time.time()
            last_activity_time = time.time()
            break

    if not first_detected_time:
        # Check one final time before giving up
        snap = await _get_response_snapshot()
        if snap.get("lastText") and snap.get("lastText") != before_text:
            return snap.get("lastText")
        return "[NO RESPONSE — TIMEOUT]"

    # Phase 2: Active Streaming Monitoring
    # While Muse is typing (length is growing) or generating spinner is active, keep waiting up to 360s!
    stable_checks = 0

    while (time.time() - start) < 360:
        await asyncio.sleep(1.5)
        generating = await _is_generating()
        snap = await _get_response_snapshot()
        curr_text = snap.get("lastText", "")
        curr_len = len(curr_text)

        if curr_len > last_len:
            # Text is actively streaming!
            last_len = curr_len
            last_text = curr_text
            last_activity_time = time.time()
            stable_checks = 0
            continue

        idle_time = time.time() - last_activity_time

        if not generating:
            if curr_len > 0 and curr_len == last_len:
                stable_checks += 1
                if stable_checks >= 2 and idle_time >= 3.0:
                    # Generation complete and text is stable
                    return curr_text
        else:
            stable_checks = 0

        # If text hasn't grown for 35 seconds and generation spinner is gone, conclude
        if idle_time > 35:
            if curr_len > 0:
                return curr_text
            break

    final_snap = await _get_response_snapshot()
    return final_snap.get("lastText") or last_text or "[PARTIAL RESPONSE — TIMEOUT]"


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


@router.get("/last-response")
async def muse_last_response():
    """Get the latest completed response directly from the Muse chat page."""
    try:
        await _ensure_muse_session()
        page = _muse_state["page"]
        if not page:
            return {"success": False, "error": "No active page"}

        snap = await _get_response_snapshot()
        text = snap.get("lastText", "")
        generating = await _is_generating()
        code_blocks = extract_code_blocks(text)

        return {
            "success": bool(text),
            "response": text,
            "generating": generating,
            "code_blocks": code_blocks,
            "code_blocks_count": len(code_blocks),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


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


class MuseEvalRequest(BaseModel):
    expression: str

@router.post("/eval")
async def muse_eval(req: MuseEvalRequest):
    """Evaluate arbitrary JavaScript on the active Muse page."""
    try:
        await _ensure_muse_session()
        page = _muse_state["page"]
        if not page:
            return {"success": False, "error": "No active page"}
        res = await page.evaluate(req.expression)
        return {"success": True, "result": res}
    except Exception as e:
        return {"success": False, "error": str(e)}

