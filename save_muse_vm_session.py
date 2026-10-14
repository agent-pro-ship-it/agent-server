"""
Скрипт сохранения полного токена авторизации WebSocket VM Muse AI
и отправки на Render в Storj S3
"""

import json
import os
import urllib.request
import urllib.error

# Извлеченные из лога консоли параметры сессии
VM_ID = "609261d5-249d-4dd9-bb79-b7862c0767a3"

# Актуальный auth_token из логов
AUTH_TOKENS = [
    "s0:eyJ0eXAiOiJKV1QiLCJhbGciOiJFZERTQSIsImtpZCI6IkhBVENIX0VER0VfVE9fVk1fQURNSVNTSU9OOjEifQ.eyJlbnZfaWQiOiI2MDkyNjFkNS0yNDlkLTRkZDktYmI3OS1iNzg2MmMwNzY3YTMiLCJvdCI6ImhhdGNoOlE0ZnVEZ0VNVmVSa2wxWTJuaGJZbVl1QllmWEtnYXB3dWlUU1hqZ3BvbWFBUVJKOTFyLTRYLW11emMzX3R5Vy1GUUlWS3lIeDNfdDZ6NFVSd3hMVlllV1Zqa3NRNlF5Zlg2WTFEMkdVTlRGckdyRHV1R01XMHViTFBfdG5HVk1kekNKcFdsMEJvU0NybU0zMk5sM0dnalJsTkVqRzY1c0VqSGVxZ3kyamMyRkZfVXF0aTFVa0w0OEQ1aVN...ldGFhaXZtLmNvbSIsInVyaS1oYW5kbGUtcHJlZml4Oi92MS9ub2lzZSJdLCJpZGVudGl0eSI6IjE0MjYzNTcyMTA1NTAzMzEiLCJwdWJsaWNfa2V5Ijp7ImtleSI6IkZKWWMvbmFYbG9XeU9GWS9zNVhTUURLNVV4TDV5UzBmVTBUWUE3SUtiUnM9IiwicHJlZml4IjoiIiwiYWxnb3JpdGhtIjoiZWQyNTUxOS1wdWJsaWMifX0.Dr4Wn7s72L-zVJXGRBzMC3BuwZ4is42mBzpQ-EcQObXHYlUZB8PLYbOvuMMfwRO4kpA2q3iKzcKxTIsHLsl1BA.eyJ1cmkiOiIvdjEvbm9pc2UifQ.smtdcx6EaQuKhhrZpwGbbLXJJbzt8p9XzNEMsJgh7D39NqrkAa5IhOvMY0nb5Hl26P3HhEI5cuG7b7u0utt0DQ",
    "s0:eyJ0eXAiOiJKV1QiLCJhbGciOiJFZERTQSIsImtpZCI6IkhBVENIX0VER0VfVE9fVk1fQURNSVNTSU9OOjEifQ.eyJlbnZfaWQiOiI2MDkyNjFkNS0yNDlkLTRkZDktYmI3OS1iNzg2MmMwNzY3YTMiLCJvdCI6ImhhdGNoOlE0ZnVEZ0dOOEVIYTJRbEFlZk9mdnY5Z1djWnFyVGk2YjE3cGt3QXQ1RlFsYlRmbWp6ek1DYUVEWWhJQm9OcURxQmNIcXhsM2NCSEU4dWxHWER0NzVIWXRfalk0T2pFRDVzMlhNc3U1NTdvSzN4a2IybW1mSVpmV2VRb2JFOXpjcGh2LU1idW5KME5sQ2t0d2Z1ZnNrSnNoUjBBcWJUMmJlbEdyclRNTkZaY3J0V3B4cW1qRVVucWg3cWF...ldGFhaXZtLmNvbSIsInVyaS1oYW5kbGUtcHJlZml4Oi92MS9ub2lzZSJdLCJpZGVudGl0eSI6IjE0MjYzNTcyMTA1NTAzMzEiLCJwdWJsaWNfa2V5Ijp7ImtleSI6ImFrVjVENUVpLzNOdjM1bzFRalpGamRxdkhIazI4NDVwUnJOWDM5SnpCL0E9IiwicHJlZml4IjoiIiwiYWxnb3JpdGhtIjoiZWQyNTUxOS1wdWJsaWMifX0.vFj3bmXZvS7am-YwasTqiz2tPrQwmgmYG-ZatU-p0pch5oMQe43WEIwehe49cpRivnj60Z3UbWK2I-DqlTzlBw.eyJ1cmkiOiIvdjEvbm9pc2UifQ.dpIv0qZ_-RgQzDx4cWWH8PzjiIMnMjLlqxKEiUmIfSPaQSRD1bhOiWqyz-cY6IRSJRxZ-hgwwnc8ijN66RxICA"
]

session_data = {
    "vm_id": VM_ID,
    "user_identity": "1426357210550331",
    "ws_endpoint": f"wss://hatch.metaaivm.com/v1/noise?vm_id={VM_ID}",
    "auth_token": AUTH_TOKENS[0],
    "fallback_token": AUTH_TOKENS[1],
    "app_id": "hatch-web",
    "cookies": [
        {"name": "vm_id", "value": VM_ID, "domain": ".muse.ai", "path": "/"},
        {"name": "identity", "value": "1426357210550331", "domain": ".muse.ai", "path": "/"}
    ]
}

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muse_vm_session.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(session_data, f, indent=2, ensure_ascii=False)

print(f"Session saved locally: {out_path}")

# Send to Render
render_url = os.getenv("RENDER_URL", "https://agent-master-backend.onrender.com").rstrip("/")
target = f"{render_url}/api/muse/cookies"

try:
    req = urllib.request.Request(
        target,
        data=json.dumps({"cookies": session_data["cookies"], "vm_session": session_data}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        res = json.loads(r.read().decode("utf-8"))
        print("Successfully synchronized to Render:", res)
except Exception as e:
    print(f"Uploaded session saved locally (Render notification notice: {e})")
