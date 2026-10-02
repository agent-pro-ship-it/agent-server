import os
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("AccountManager")

class GoogleAccountManager:
    def __init__(self):
        self.accounts: List[Dict[str, str]] = []
        self.current_index: int = 0
        self._load_from_env()

    def _load_from_env(self):
        raw = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
        if raw.startswith("["):
            try:
                self.accounts = json.loads(raw)
            except Exception as e:
                logger.error(f"Failed to parse GEMINI_API_KEYS: {e}")
        elif raw:
            keys = [k.strip() for k in raw.split(",") if k.strip()]
            for i, key in enumerate(keys):
                self.accounts.append({
                    "id": f"account-{i+1}",
                    "name": f"Google Account {i+1}",
                    "key": key,
                    "is_active": True,
                    "status": "ready"
                })

    def get_current_key(self) -> Optional[str]:
        if not self.accounts:
            return None
        return self.accounts[self.current_index]["key"]

    def get_current_account_info(self) -> Dict[str, str]:
        if not self.accounts:
            return {"id": "none", "name": "No accounts configured", "status": "empty"}
        acc = self.accounts[self.current_index]
        return {
            "id": acc.get("id", str(self.current_index)),
            "name": acc.get("name", f"Account {self.current_index+1}"),
            "status": acc.get("status", "ready"),
            "index": self.current_index,
            "total": len(self.accounts)
        }

    def rotate_on_quota_exhausted(self) -> Dict[str, str]:
        if len(self.accounts) <= 1:
            return self.get_current_account_info()
        old_acc = self.accounts[self.current_index]
        old_acc["status"] = "quota_exhausted"
        self.current_index = (self.current_index + 1) % len(self.accounts)
        new_acc = self.accounts[self.current_index]
        new_acc["status"] = "ready"
        logger.info(f"Rotated account to {new_acc.get('name')}")
        return self.get_current_account_info()

    def set_active_account(self, index: int) -> bool:
        if 0 <= index < len(self.accounts):
            self.current_index = index
            return True
        return False

    def add_account(self, name: str, key: str) -> Dict[str, str]:
        acc = {
            "id": f"account-{len(self.accounts)+1}",
            "name": name,
            "key": key.strip(),
            "is_active": True,
            "status": "ready"
        }
        self.accounts.append(acc)
        return acc

    def list_accounts_safe(self) -> List[Dict[str, str]]:
        safe = []
        for i, acc in enumerate(self.accounts):
            k = acc.get("key", "")
            masked = f"{k[:6]}...{k[-4:]}" if len(k) > 10 else "***"
            safe.append({
                "id": acc.get("id", str(i)),
                "name": acc.get("name", f"Account {i+1}"),
                "status": acc.get("status", "ready"),
                "is_current": (i == self.current_index),
                "masked_key": masked
            })
        return safe

account_manager = GoogleAccountManager()
