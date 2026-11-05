import os
import json
import time
import logging
import base64
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

logger = logging.getLogger("AccountManager")

TOKEN_PATHS = [
    Path("/root/.gemini/antigravity-cli/antigravity-oauth-token"),
    Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"
]

EMBEDDED_POOL_B64 = """WwogIHsKICAgICJpZCI6ICJhY2MtaWNsdWJldXJvcGUiLAogICAgImVtYWlsIjogImljbHViZXVyb3BlQGdtYWlsLmNvbSIsCiAgICAibmFtZSI6ICJJY2x1YiBFdXJvcGUiLAogICAgInR5cGUiOiAiZ29vZ2xlX3BybyIsCiAgICAidGllciI6ICJHb29nbGUgUHJvIChHZW1pbmkgMy44IEZsYXNoIEhpZ2gpIiwKICAgICJhY3RpdmUiOiB0cnVlLAogICAgInN0YXR1cyI6ICJyZWFkeSIsCiAgICAidG9rZW5fZGF0YSI6IHsKICAgICAgInRva2VuIjogewogICAgICAgICJyZWZyZXNoX3Rva2VuIjogIjEvLzAzUjNoUWN1TFJRcTlDZ1lJQVJBQUdBTVNOd0YtTDlJcjZrSjNuenRCakxzUFFoMTBneXBTOS1TaWpSSFVCRnBpS2gyYkRNNktoVFVKS0w3V1RxbzY1T3VPRG13dWlULVg0RjAiLAogICAgICAgICJ0b2tlbl90eXBlIjogIkJlYXJlciIKICAgICAgfSwKICAgICAgImF1dGhfbWV0aG9kIjogImNvbnN1bWVyIiwKICAgICAgImFjY291bnQiOiAiaWNsdWJldXJvcGVAZ21haWwuY29tIgogICAgfQogIH0sCiAgewogICAgImlkIjogImFjYy1pY2x1YnJlY3J1aXRlciIsCiAgICAiZW1haWwiOiAiaWNsdWJyZWNydWl0ZXJAZ21haWwuY29tIiwKICAgICJuYW1lIjogIkljbHViIFJlY3J1aXRlciIsCiAgICAidHlwZSI6ICJnb29nbGVfcHJvIiwKICAgICJ0aWVyIjogIkdvb2dsZSBQcm8gKEdlbWluaSAzLjggRmxhc2ggSGlnaCkiLAogICAgImFjdGl2ZSI6IGZhbHNlLAogICAgInN0YXR1cyI6ICJyZWFkeSIsCiAgICAidG9rZW5fZGF0YSI6IHsKICAgICAgInRva2VuIjogewogICAgICAgICJyZWZyZXNoX3Rva2VuIjogIjEvLzAzalZfRU9pUk5HWWxDZ1lJQVJBQUdBTVNOd0YtTDlJcjBuMFBMVHJhTVVsTGUxVlRCUDJuZFctempPdjhTMy16R1NVREFKSk9nbU41YWlIV0pzZFIzcVpHc1dsWHE0NE9GaTgiLAogICAgICAgICJ0b2tlbl90eXBlIjogIkJlYXJlciIKICAgICAgfSwKICAgICAgImF1dGhfbWV0aG9kIjogImNvbnN1bWVyIiwKICAgICAgImFjY291bnQiOiAiaWNsdWJyZWNydWl0ZXJAZ21haWwuY29tIgogICAgfQogIH0sCiAgewogICAgImlkIjogImFjYy1hbGVrc2llaWV2cm9tYW4iLAogICAgImVtYWlsIjogImFsZWtzaWVpZXZyb21hbkBnbWFpbC5jb20iLAogICAgIm5hbWUiOiAiQWxla3NpZWlldiBSb21hbiIsCiAgICAidHlwZSI6ICJnb29nbGVfcHJvIiwKICAgICJ0aWVyIjogIkdvb2dsZSBQcm8gKEdlbWluaSAzLjggRmxhc2ggSGlnaCkiLAogICAgImFjdGl2ZSI6IGZhbHNlLAogICAgInN0YXR1cyI6ICJyZWFkeSIsCiAgICAidG9rZW5fZGF0YSI6IHsKICAgICAgInRva2VuIjogewogICAgICAgICJyZWZyZXNoX3Rva2VuIjogIjEvLzAzY2lPSkdwVlUzdHZDZ1lJQVJBQUdBTVNOd0YtTDlJcmR5djhaSkFwaDFhb2NkcjFRaFBlTURNcVBXMFdSMjl4SjlIdGpsb0hndkdYbEpoS2ZpNGxsMXVNR082M2dWWDdkaDAiLAogICAgICAgICJ0b2tlbl90eXBlIjogIkJlYXJlciIKICAgICAgfSwKICAgICAgImF1dGhfbWV0aG9kIjogImNvbnN1bWVyIiwKICAgICAgImFjY291bnQiOiAiYWxla3NpZWlldnJvbWFuQGdtYWlsLmNvbSIKICAgIH0KICB9LAogIHsKICAgICJpZCI6ICJhY2MtcmVjcnVpdGVyY2x1YiIsCiAgICAiZW1haWwiOiAicmVjcnVpdGVyY2x1Yi5ib3RAZ21haWwuY29tIiwKICAgICJuYW1lIjogIlJlY3J1aXRlciBDbHViIEJvdCIsCiAgICAidHlwZSI6ICJnb29nbGVfcHJvIiwKICAgICJ0aWVyIjogIkdvb2dsZSBQcm8gKEdlbWluaSAzLjggRmxhc2ggSGlnaCkiLAogICAgImFjdGl2ZSI6IGZhbHNlLAogICAgInN0YXR1cyI6ICJyZWFkeSIsCiAgICAidG9rZW5fZGF0YSI6IHsKICAgICAgInRva2VuIjogewogICAgICAgICJyZWZyZXNoX3Rva2VuIjogIjEvLzAzVlZ2ejZHOUkyV0lDZ1lJQVJBQUdBTVNOd0YtTDlJcmx6YkRkUHFjb2w3OW9yNHNpSWNzZVlpdHRmNW01OS1sYlhPNGU5dEszaU5WVTZ1UVUwejc2SXhYczR0ejlrWW1KM3ciLAogICAgICAgICJ0b2tlbl90eXBlIjogIkJlYXJlciIKICAgICAgfSwKICAgICAgImF1dGhfbWV0aG9kIjogImNvbnN1bWVyIiwKICAgICAgImFjY291bnQiOiAicmVjcnVpdGVyY2x1Yi5ib3RAZ21haWwuY29tIgogICAgfQogIH0KXQ=="""

class AccountManager:
    def __init__(self, workspace_dir: Path, s3_client=None, bucket_name: str = "agent-vault"):
        self.workspace_dir = workspace_dir
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.accounts_file = workspace_dir / "accounts.json"
        self.accounts: List[Dict[str, Any]] = []
        self.active_account_id: Optional[str] = None
        self._current_rr_index: int = 0

    def initialize(self):
        """Loads accounts from local disk or Storj S3, then ensures active token is installed."""
        self._load_accounts()
        self._ensure_active_token()

    def _load_accounts(self):
        # 1. Try to fetch from Storj S3
        if self.s3_client:
            try:
                res = self.s3_client.get_object(Bucket=self.bucket_name, Key="auth/accounts.json")
                data = json.loads(res["Body"].read().decode("utf-8"))
                if isinstance(data, list) and data:
                    self.accounts = data
                    logger.info(f"Loaded {len(self.accounts)} accounts from Storj S3.")
                    self._save_local_accounts()
                    self._detect_active()
                    return
            except Exception as e:
                logger.warning(f"Could not load accounts from Storj: {e}")

        # 2. Try to load from local file
        if self.accounts_file.exists():
            try:
                self.accounts = json.loads(self.accounts_file.read_text(encoding="utf-8"))
                logger.info(f"Loaded {len(self.accounts)} accounts from local accounts.json")
                self._detect_active()
                return
            except Exception as e:
                logger.warning(f"Could not load local accounts.json: {e}")

        # 3. Default fallback: load embedded multi-account pool
        try:
            pool = json.loads(base64.b64decode(EMBEDDED_POOL_B64).decode("utf-8"))
            if isinstance(pool, list) and pool:
                self.accounts = pool
                logger.info(f"Initialized {len(self.accounts)} accounts from embedded pool.")
                self._save_local_accounts()
                self._detect_active()
                return
        except Exception as e:
            logger.warning(f"Could not load embedded pool: {e}")

        # 4. Fallback: build from existing token on disk
        default_acc = self._build_default_account()
        if default_acc:
            self.accounts = [default_acc]
            self.active_account_id = default_acc["id"]
            self._save_local_accounts()
            self._sync_to_storj()

    def _build_default_account(self) -> Optional[Dict[str, Any]]:
        for p in TOKEN_PATHS:
            if p.exists() and p.stat().st_size > 50:
                try:
                    tok = json.loads(p.read_text(encoding="utf-8"))
                    email = self._extract_email_from_token(tok) or tok.get("account") or "recruiterclub.bot@gmail.com"
                    return {
                        "id": "acc-recruiterclub",
                        "email": email,
                        "name": email.split("@")[0].capitalize(),
                        "type": "google_pro",
                        "tier": "Google Pro (Gemini 3.8 Flash High)",
                        "active": True,
                        "status": "ready",
                        "token_data": tok,
                        "created_at": datetime.utcnow().isoformat()
                    }
                except Exception:
                    pass
        return None

    def _detect_active(self):
        for acc in self.accounts:
            if acc.get("active"):
                self.active_account_id = acc.get("id")
                return
        if self.accounts:
            self.accounts[0]["active"] = True
            self.active_account_id = self.accounts[0]["id"]

    def _extract_email_from_token(self, token_data: Dict[str, Any]) -> Optional[str]:
        if token_data.get("account"):
            return token_data["account"]
        id_tok = token_data.get("id_token")
        if id_tok and "." in id_tok:
            try:
                parts = id_tok.split(".")
                if len(parts) >= 2:
                    p = parts[1]
                    p += "=" * (-len(p) % 4)
                    payload = json.loads(base64.b64decode(p).decode("utf-8"))
                    return payload.get("email")
            except Exception:
                pass
        return None

    def _save_local_accounts(self):
        try:
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
            self.accounts_file.write_text(json.dumps(self.accounts, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to write local accounts.json: {e}")

    def _sync_to_storj(self):
        if not self.s3_client:
            return
        try:
            # Sync accounts.json
            body = json.dumps(self.accounts, ensure_ascii=False, indent=2).encode("utf-8")
            self.s3_client.put_object(Bucket=self.bucket_name, Key="auth/accounts.json", Body=body)
            
            # Sync active token
            active = self.get_active_account()
            if active and active.get("token_data"):
                tok_bytes = json.dumps(active["token_data"], ensure_ascii=False, indent=2).encode("utf-8")
                self.s3_client.put_object(Bucket=self.bucket_name, Key="auth/active-token.json", Body=tok_bytes)
            logger.info("Successfully backed up accounts & active token to Storj S3.")
        except Exception as e:
            logger.warning(f"Storj backup warning: {e}")

    def _ensure_active_token(self):
        active = self.get_active_account()
        if not active or not active.get("token_data"):
            if self.s3_client:
                try:
                    res = self.s3_client.get_object(Bucket=self.bucket_name, Key="auth/active-token.json")
                    tok_data = json.loads(res["Body"].read().decode("utf-8"))
                    if tok_data:
                        self.install_token_to_system(tok_data)
                        return
                except Exception:
                    pass
            return

        self.install_token_to_system(active["token_data"])

    def install_token_to_system(self, token_data: Dict[str, Any]):
        tok_str = json.dumps(token_data, ensure_ascii=False, indent=2)
        for p in TOKEN_PATHS:
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(tok_str, encoding="utf-8")
                try:
                    os.chmod(str(p), 0o600)
                except Exception:
                    pass
                logger.info(f"Installed Google Pro token to {p}")
            except Exception as e:
                logger.warning(f"Could not write token to {p}: {e}")

    def get_accounts_safe(self) -> List[Dict[str, Any]]:
        self._check_cooldowns()
        safe_list = []
        for acc in self.accounts:
            safe_list.append({
                "id": acc.get("id"),
                "email": acc.get("email", "Unknown"),
                "name": acc.get("name", "Google Account"),
                "type": acc.get("type", "google_pro"),
                "tier": acc.get("tier", "Google Pro"),
                "active": bool(acc.get("active")),
                "status": acc.get("status", "ready"),
                "created_at": acc.get("created_at")
            })
        return safe_list

    def _check_cooldowns(self):
        now = time.time()
        changed = False
        for acc in self.accounts:
            if acc.get("status") == "quota_exhausted":
                exhausted_at = acc.get("exhausted_at", 0)
                if now - exhausted_at > 180:  # 3 minutes cooldown
                    acc["status"] = "ready"
                    changed = True
                    logger.info(f"Quota cooldown ended for account {acc.get('email')}, status restored to ready.")
        if changed:
            self._save_local_accounts()

    def get_ready_accounts(self) -> List[Dict[str, Any]]:
        self._check_cooldowns()
        ready = [a for a in self.accounts if a.get("status") == "ready"]
        if not ready and self.accounts:
            # If all are exhausted, fallback to all accounts to allow soft retry
            return self.accounts
        return ready

    def get_active_account(self) -> Optional[Dict[str, Any]]:
        self._check_cooldowns()
        for acc in self.accounts:
            if acc.get("id") == self.active_account_id:
                return acc
        for acc in self.accounts:
            if acc.get("active"):
                return acc
        return self.accounts[0] if self.accounts else None

    def switch_account(self, account_id: str) -> Dict[str, Any]:
        target = None
        for acc in self.accounts:
            if acc.get("id") == account_id:
                acc["active"] = True
                if acc.get("status") != "quota_exhausted":
                    acc["status"] = "ready"
                target = acc
            else:
                acc["active"] = False

        if not target:
            return {"success": False, "error": f"Account {account_id} not found"}

        self.active_account_id = target["id"]
        if target.get("token_data"):
            self.install_token_to_system(target["token_data"])

        self._save_local_accounts()
        self._sync_to_storj()
        return {
            "success": True,
            "active_account": {
                "id": target["id"],
                "email": target.get("email"),
                "name": target.get("name"),
                "status": target.get("status")
            }
        }

    def mark_account_quota_exhausted(self, account_id: str):
        for acc in self.accounts:
            if acc.get("id") == account_id:
                acc["status"] = "quota_exhausted"
                acc["exhausted_at"] = time.time()
                logger.warning(f"Account {acc.get('email')} ({acc.get('id')}) marked as quota_exhausted.")
                break
        self._save_local_accounts()
        self._sync_to_storj()

    def auto_failover_quota(self, failed_account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if failed_account_id:
            self.mark_account_quota_exhausted(failed_account_id)
        ready_acc = next((a for a in self.accounts if a.get("status") == "ready" and a.get("id") != failed_account_id), None)
        if ready_acc:
            logger.info(f"Auto-failing over quota to {ready_acc.get('email')}")
            self.switch_account(ready_acc["id"])
            return ready_acc
        return None

    def get_access_token_for_account(self, account: Dict[str, Any], client_id: str, client_secret: str) -> Optional[str]:
        now = time.time()
        # 1. Check in-memory cached token
        if account.get("cached_access_token") and now < (account.get("token_expires_at", 0) - 60):
            return account["cached_access_token"]

        # 2. Extract refresh_token
        tok_data = account.get("token_data", {})
        token_info = tok_data.get("token", {}) if isinstance(tok_data.get("token"), dict) else tok_data
        refresh_tok = token_info.get("refresh_token") or tok_data.get("refresh_token")
        
        if not refresh_tok:
            logger.warning(f"No refresh_token found for account {account.get('email')}")
            return None

        # 3. Request fresh access token from Google
        data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_tok,
            "grant_type": "refresh_token"
        }).encode("utf-8")

        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                res = json.loads(r.read().decode("utf-8"))
                new_token = res.get("access_token")
                expires_in = res.get("expires_in", 3600)
                account["cached_access_token"] = new_token
                account["token_expires_at"] = now + expires_in
                return new_token
        except Exception as e:
            logger.error(f"Error refreshing access token for {account.get('email')}: {e}")
            return None

    def add_account(self, token_data: Dict[str, Any], custom_email: Optional[str] = None) -> Dict[str, Any]:
        email = custom_email or self._extract_email_from_token(token_data) or token_data.get("account") or f"account_{len(self.accounts)+1}@google.com"
        acc_id = f"acc-{abs(hash(email)) % 1000000}"

        existing = next((a for a in self.accounts if a.get("email") == email or a.get("id") == acc_id), None)
        if existing:
            existing["token_data"] = token_data
            existing["status"] = "ready"
            existing["cached_access_token"] = None  # Force refresh
            self.active_account_id = existing["id"]
            existing["active"] = True
            for a in self.accounts:
                if a["id"] != existing["id"]:
                    a["active"] = False
            logger.info(f"Updated existing Google account in pool: {email}")
        else:
            new_acc = {
                "id": acc_id,
                "email": email,
                "name": email.split("@")[0].capitalize(),
                "type": "google_pro",
                "tier": "Google Pro (Gemini 3.8 Flash High)",
                "active": True,
                "status": "ready",
                "token_data": token_data,
                "created_at": datetime.utcnow().isoformat()
            }
            for a in self.accounts:
                a["active"] = False
            self.accounts.append(new_acc)
            self.active_account_id = new_acc["id"]
            logger.info(f"Added new Google account to pool: {email}")

        self.install_token_to_system(token_data)
        self._save_local_accounts()
        self._sync_to_storj()

        return {"success": True, "account": self.get_active_account()}

    def logout_active(self) -> Dict[str, Any]:
        for acc in self.accounts:
            acc["active"] = False
        self.active_account_id = None
        for p in TOKEN_PATHS:
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        self._save_local_accounts()
        if self.s3_client:
            try:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key="auth/active-token.json")
            except Exception:
                pass
        return {"success": True}


# Module-level singleton
_instance: Optional[AccountManager] = None

def get_account_manager(workspace_dir: Optional[Path] = None, s3_client=None, bucket_name: str = "agent-vault") -> AccountManager:
    global _instance
    if _instance is None:
        ws = workspace_dir or Path("workspace")
        _instance = AccountManager(workspace_dir=ws, s3_client=s3_client, bucket_name=bucket_name)
    elif s3_client and not _instance.s3_client:
        _instance.s3_client = s3_client
        _instance.bucket_name = bucket_name
    return _instance
