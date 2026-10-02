import os
import json
import logging
from typing import AsyncGenerator, Dict, Any, List
from google import genai
from google.genai import types
from account_manager import account_manager
from skills_manager import skills_manager

logger = logging.getLogger("AgentEngine")

class AgentEngine:
    def __init__(self):
        self.default_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def _get_client(self, api_key: str) -> genai.Client:
        return genai.Client(api_key=api_key)

    async def stream_chat(self, user_message: str, history: List[Dict[str, str]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        history = history or []
        max_attempts = max(1, len(account_manager.accounts))
        attempts = 0

        while attempts < max_attempts:
            api_key = account_manager.get_current_key()
            if not api_key:
                yield {
                    "type": "error",
                    "text": "Google API key is not configured. Please add one in settings or log in."
                }
                return

            try:
                client = self._get_client(api_key)
                system_instruction = (
                    "You are an autonomous AI coding assistant with Apple Human Interface Guidelines "
                    "mobile frontend, Supabase database, and Storj S3 storage. "
                    "Answer clearly, concisely, and provide code blocks when requested."
                    + skills_manager.get_system_prompt_additions()
                )

                contents = []
                for msg in history:
                    contents.append(types.Content(
                        role=msg.get("role", "user"),
                        parts=[types.Part.from_text(text=msg.get("content", ""))]
                    ))
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_message)]
                ))

                response = client.models.generate_content_stream(
                    model=self.default_model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                    )
                )

                for chunk in response:
                    if chunk.text:
                        yield {"type": "chunk", "text": chunk.text}
                return

            except Exception as e:
                err_str = str(e)
                logger.error(f"Gemini API Error: {err_str}")
                if "429" in err_str or "quota" in err_str.lower() or "resource_exhausted" in err_str.lower():
                    new_acc = account_manager.rotate_on_quota_exhausted()
                    yield {
                        "type": "account_switch",
                        "notice": f"Account quota reached. Switched automatically to {new_acc.get('name')}.",
                        "new_account": new_acc
                    }
                    attempts += 1
                else:
                    yield {"type": "error", "text": f"Error: {err_str}"}
                    return

        yield {"type": "error", "text": "All accounts reached quota limit."}

agent_engine = AgentEngine()
