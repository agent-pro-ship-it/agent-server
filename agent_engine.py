import os
import json
import logging
from typing import AsyncGenerator, Dict, Any, List
from google import genai
from google.genai import types
from account_manager import account_manager
from skills_manager import skills_manager
from storage_router import storage_router

logger = logging.getLogger(AgentEngine)

class AgentEngine:
    "
    Core Autonomous Agent Engine with Gemini 3.8 / 2.5,
    auto-failover key rotation, tool executions, and streaming.
    "
    def __init__(self):
        # Preferred models in priority order
        self.default_model = os.getenv(GEMINI_MODEL, gemini-2.5-flash)

    def _get_client(self, api_key: str) -> genai.Client:
        return genai.Client(api_key=api_key)

    async def stream_chat(self, user_message: str, history: List[Dict[str, str]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        "
        Streams response chunks with auto-failover on quota exhaustion.
        Yields events: {type: chunk, text: ...}, {type: account_switch, ...}, etc.
        "
        history = history or []
        max_attempts = max(1, len(account_manager.accounts))
        attempts = 0

        while attempts < max_attempts:
            api_key = account_manager.get_current_key()
            if not api_key:
                yield {
                    type: error,
                    text: Google API key is not configured. Please add one in settings or provide in .env.
                }
                return

            try:
                client = self._get_client(api_key)
                system_instruction = (
                    You are an autonomous AI coding assistant running with Apple Human Interface Guidelines 
                    mobile frontend and multi-cloud infrastructure. You have access to Supabase database, 
                    Cloudflare R2 storage, GitHub repositories, and dynamic Antigravity skills. 
                    Answer clearly, concisely, and provide code blocks when requested.
                    + skills_manager.get_system_prompt_additions()
                )

                # Format contents
                contents = []
                for msg in history:
                    contents.append(types.Content(
                        role=msg.get(role, user),
                        parts=[types.Part.from_text(text=msg.get(content, "))]
 ))
 contents.append(types.Content(
 role=user,
 parts=[types.Part.from_text(text=user_message)]
 ))

 # Stream from Gemini
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
 yield {type: chunk, text: chunk.text}
 
 # Successful response
 return

 except Exception as e:
 err_str = str(e)
 logger.error(fGemini API Error with current account: {err_str})
 
 # Check for rate limit / quota exhaustion (HTTP 429)
 if 429 in err_str or quota in err_str.lower() or resource_exhausted in err_str.lower():
 logger.warning(Quota exhausted on current account. Triggering auto-failover...)
 new_acc = account_manager.rotate_on_quota_exhausted()
 yield {
 type: account_switch,
 notice: fAccount quota reached. Switched automatically to {new_acc.get('name')}.,
 new_account: new_acc
 }
 attempts += 1
 else:
 # Non-quota error
 yield {type: error, text: fError: {err_str}}
 return

 yield {
 type: error,
 text: All available Google accounts have reached their rate limits or quotas. Please try again later or add another key.
 }

agent_engine = AgentEngine()
