import os
import json
import logging
import base64
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger("AccountManager")

TOKEN_PATHS = [
    Path("/root/.gemini/antigravity-cli/antigravity-oauth-token"),
    Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"
]

class AccountManager:
    def __init__(self, workspace_dir: Path, s3_client=None, bucket_name: str = "agent-vault"):
        self.workspace_dir = workspace_dir
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.accounts_file = workspace_dir / "accounts.json"
        self.accounts: List[Dict[str, Any]] = []
        self.active_account_id: Optional[str] = None

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

        # 3. Default fallback: build from existing token
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
                    email = self._extract_email_from_token(tok) or "recruiterclub.bot@gmail.com"
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

    def get_active_account(self) -> Optional[Dict[str, Any]]:
        for acc in self.accounts:
            if acc.get("id") == self.active_account_id or acc.get("active"):
                return acc
        return self.accounts[0] if self.accounts else None

    def switch_account(self, account_id: str) -> Dict[str, Any]:
        target = None
        for acc in self.accounts:
            if acc.get("id") == account_id:
                acc["active"] = True
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

    def add_account(self, token_data: Dict[str, Any], custom_email: Optional[str] = None) -> Dict[str, Any]:
        email = custom_email or self._extract_email_from_token(token_data) or f"account_{len(self.accounts)+1}@google.com"
        acc_id = f"acc-{abs(hash(email)) % 1000000}"

        existing = next((a for a in self.accounts if a.get("email") == email or a.get("id") == acc_id), None)
        if existing:
            existing["token_data"] = token_data
            existing["active"] = True
            existing["status"] = "ready"
            self.active_account_id = existing["id"]
            for a in self.accounts:
                if a["id"] != existing["id"]:
                    a["active"] = False
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

    def auto_failover_quota(self) -> Optional[Dict[str, Any]]:
        active = self.get_active_account()
        if active:
            active["status"] = "quota_exhausted"
        ready_acc = next((a for a in self.accounts if a.get("status") == "ready" and not a.get("active")), None)
        if ready_acc:
            logger.info(f"Auto-failing over to {ready_acc.get('email')}")
            return self.switch_account(ready_acc["id"])
        return None
