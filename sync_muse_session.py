"""
Muse Session Sync Tool
Без блокирующих консольных вопросов: сразу открывает реальный Chrome на muse.ai,
создает кнопку/окно или ждет появления маркера сессии, сохраняет куки и отправляет на Render.
"""

import asyncio
import json
import os
import sys
import urllib.request
import urllib.error

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright не установлен.")
    sys.exit(1)

LOCAL_PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".muse_google_profile")
MUSE_URL = "https://muse.ai"
RENDER_URL = os.getenv("RENDER_URL", "https://agent-master-backend.onrender.com").rstrip("/")


def find_system_chrome():
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


async def main():
    print("=" * 60)
    print("  MUSE SESSION SYNC — ЗАПУСК БРАУЗЕРА")
    print("=" * 60)
    print(f"Целевой сервер: {RENDER_URL}")

    chrome_exe = find_system_chrome()
    if chrome_exe:
        print(f"Найден Chrome: {chrome_exe}")

    pw = await async_playwright().start()

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        "--start-maximized"
    ]

    context = await pw.chromium.launch_persistent_context(
        user_data_dir=LOCAL_PROFILE,
        executable_path=chrome_exe,
        headless=False,
        args=launch_args,
        ignore_default_args=["--enable-automation"],
        viewport=None,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto(MUSE_URL)

    # Добавляем плавающую визуальную плашку с кнопкой прямо на страницу Muse!
    await page.add_init_script("""
        window.addEventListener('DOMContentLoaded', () => {
            const bar = document.createElement('div');
            bar.id = 'muse-sync-helper';
            bar.style.cssText = `
                position: fixed;
                bottom: 24px;
                right: 24px;
                z-index: 9999999;
                background: #111;
                border: 2px solid #00E5FF;
                border-radius: 12px;
                padding: 16px 20px;
                color: #fff;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                box-shadow: 0 10px 30px rgba(0,0,0,0.8);
                display: flex;
                flex-direction: column;
                gap: 10px;
                max-width: 340px;
            `;
            bar.innerHTML = `
                <div style="font-weight: bold; font-size: 14px; color: #00E5FF;">⚡ Antigravity Muse Sync</div>
                <div style="font-size: 12px; color: #ccc;">Войдите в свой аккаунт Muse через Google. Когда вход завершится, нажмите кнопку ниже:</div>
                <button id="btn-sync-done" style="
                    background: #00E5FF;
                    color: #000;
                    border: none;
                    padding: 10px 16px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 13px;
                    cursor: pointer;
                    transition: transform 0.1s;
                ">✅ Я вошел — Синхронизировать с Render</button>
            `;
            document.body.appendChild(bar);

            document.getElementById('btn-sync-done').addEventListener('click', () => {
                document.getElementById('btn-sync-done').innerText = 'Синхронизация...';
                document.getElementById('btn-sync-done').disabled = true;
                window._antigravity_sync_confirmed = true;
            });
        });
    """)

    print("\n[OK] Okno Google Chrome otkryto na vashem ekrane!")
    print("1. V okne brauzera voydite cherez Google v Muse.")
    print("2. V pravom nizhnem uglu stranicy nazhmite knopku: 'Ya voshel - Sinhronizirovat s Render'.")
    print("3. Zhdu nazhatiya knopki v brauzere...")

    # Ожидаем нажатия кнопки прямо в окне браузера
    confirmed = False
    while not confirmed:
        await asyncio.sleep(1)
        try:
            confirmed = await page.evaluate("() => !!window._antigravity_sync_confirmed")
        except Exception:
            pass

    print("\nКнопка нажата! Собираем cookies...")
    cookies = await context.cookies()
    print(f"Собрано {len(cookies)} параметров сессии.")

    local_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muse_cookies.json")
    with open(local_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)
    print(f"Файл сохранен: {local_file}")

    target_endpoint = f"{RENDER_URL}/api/muse/cookies"
    print(f"Отправляем на Render: {target_endpoint}...")

    payload = json.dumps({"cookies": cookies}).encode("utf-8")
    req = urllib.request.Request(
        target_endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"Успех! Ответ сервера: {data}")
            await page.evaluate("""() => {
                const el = document.getElementById('btn-sync-done');
                if (el) {
                    el.innerText = '🎉 Успешно передано на Render!';
                    el.style.background = '#4CAF50';
                    el.style.color = '#fff';
                }
            }""")
    except Exception as e:
        print(f"Замечание при отправке на сервер: {e}")

    await asyncio.sleep(4)
    await context.close()
    await pw.stop()
    print("Готово!")


if __name__ == "__main__":
    asyncio.run(main())
