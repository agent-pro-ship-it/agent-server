"""
Автоматический экстрактор cookies Muse AI прямо из Chrome на Windows.
Использует системный Windows DPAPI / CryptUnprotectData.
"""

import os
import json
import sqlite3
import shutil
import base64
import ctypes
import ctypes.wintypes
import urllib.request
import urllib.error

# Windows DPAPI structs
class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ('cbData', ctypes.wintypes.DWORD),
        ('pbData', ctypes.POINTER(ctypes.c_char))
    ]

CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
CryptUnprotectData.argtypes = [
    ctypes.POINTER(DATA_BLOB),
    ctypes.POINTER(ctypes.wintypes.LPWSTR),
    ctypes.POINTER(DATA_BLOB),
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB)
]
CryptUnprotectData.restype = ctypes.wintypes.BOOL


def dpapi_decrypt(encrypted_bytes: bytes) -> bytes:
    in_blob = DATA_BLOB(len(encrypted_bytes), ctypes.cast(ctypes.c_char_p(encrypted_bytes), ctypes.POINTER(ctypes.c_char)))
    out_blob = DATA_BLOB()
    if CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        res = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return res
    return b""


def get_encryption_key(local_state_path: str) -> bytes:
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    # Strip 'DPAPI' prefix (first 5 bytes)
    return dpapi_decrypt(encrypted_key[5:])


def decrypt_cookie_value(encrypted_val: bytes, key: bytes) -> str:
    if not encrypted_val:
        return ""
    # v10 prefix (AES-GCM)
    if encrypted_val.startswith(b"v10") or encrypted_val.startswith(b"v11"):
        try:
            # Need cryptography for AESGCM
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = encrypted_val[3:15]
            ciphertext = encrypted_val[15:]
            aesgcm = AESGCM(key)
            decrypted = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted.decode("utf-8", errors="replace")
        except Exception:
            pass
    # Older DPAPI
    try:
        dec = dpapi_decrypt(encrypted_val)
        return dec.decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_muse_cookies():
    user_data = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    local_state = os.path.join(user_data, "Local State")
    if not os.path.exists(local_state):
        print("Chrome Local State not found")
        return []

    enc_key = get_encryption_key(local_state)

    # Check profiles: Default, Profile 1, Profile 2...
    profiles = ["Default"] + [f"Profile {i}" for i in range(1, 10)]
    all_cookies = []

    for prof in profiles:
        cookie_db = os.path.join(user_data, prof, "Network", "Cookies")
        if not os.path.exists(cookie_db):
            cookie_db = os.path.join(user_data, prof, "Cookies")
        if not os.path.exists(cookie_db):
            continue

        temp_db = os.path.join(os.environ["TEMP"], f"chrome_cookies_{prof}.db")
        try:
            shutil.copyfile(cookie_db, temp_db)
        except Exception:
            continue

        try:
            conn = sqlite3.connect(temp_db)
            conn.text_factory = bytes
            cursor = conn.cursor()
            cursor.execute(b"""
                SELECT host_key, name, path, encrypted_value, is_secure, is_httponly, samesite
                FROM cookies
                WHERE host_key LIKE '%muse.ai%' OR host_key LIKE '%meta%' OR host_key LIKE '%metaaivm%'
            """)
            for host, name, path, enc_val, sec, http_only, samesite in cursor.fetchall():
                host_str = host.decode('utf-8', errors='replace')
                name_str = name.decode('utf-8', errors='replace')
                path_str = path.decode('utf-8', errors='replace')
                val = decrypt_cookie_value(enc_val, enc_key)
                if val:
                    same_site_str = "None" if samesite == 0 else ("Lax" if samesite == 1 else "Strict")
                    all_cookies.append({
                        "name": name_str,
                        "value": val,
                        "domain": host_str,
                        "path": path_str,
                        "secure": bool(sec),
                        "httpOnly": bool(http_only),
                        "sameSite": same_site_str
                    })
            conn.close()
            os.remove(temp_db)
        except Exception as e:
            try:
                os.remove(temp_db)
            except Exception:
                pass

    return all_cookies


def main():
    print("Extracting Muse cookies from Chrome...")
    cookies = extract_muse_cookies()
    print(f"Found {len(cookies)} cookies for Muse/Meta!")

    if not cookies:
        print("No cookies found. Make sure you are logged in to muse.ai in Chrome.")
        return

    out_file = os.path.join(os.path.dirname(__file__), "muse_cookies.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)
    print(f"Saved locally to {out_file}")

    # Send to Render
    render_url = os.getenv("RENDER_URL", "https://agent-master-backend.onrender.com").rstrip("/")
    endpoint = f"{render_url}/api/muse/cookies"
    print(f"Uploading to {endpoint}...")

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps({"cookies": cookies}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode("utf-8"))
            print("SUCCESS! Render response:", res)
    except Exception as e:
        print("Error sending to Render:", e)


if __name__ == "__main__":
    main()
