import os
import sys
import json
import time
import uuid
import ssl
import logging
import asyncio
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, Header, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse

logger = logging.getLogger("AntigravityGateway")

router = APIRouter(prefix="/v1", tags=["Antigravity API Gateway"])

from dotenv import load_dotenv
load_dotenv()

FALLBACK_THOUGHT_SIGNATURE = "EnMKcQFpFH0THGK4maCY0L0/hcIL8KCaU7AvaZucmekD54tt6ei57DUe7QUcDSdoxvHo/nT0AyiEZpTtyUxpO8hdpGRQnV6DnROv0ll7eS+cCFYmSxDcelly7P6ITpkz/NX5eJS4TeDhRdKfhgOopt/asQ/D"
THOUGHT_SIG_CACHE: Dict[str, str] = {}

# Master Token configuration
ANTIGRAVITY_MASTER_KEY = os.getenv("ANTIGRAVITY_MASTER_KEY", "sk-antigravity-master-roman")

# Antigravity Pro Session Credentials (Roman Aleksieiev)
OAUTH_CLIENT_ID = os.getenv("ANTIGRAVITY_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.getenv("ANTIGRAVITY_CLIENT_SECRET", "")
OAUTH_REFRESH_TOKEN = os.getenv("ANTIGRAVITY_REFRESH_TOKEN", "")

CASCADE_MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    "gemini-3.5-flash",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview"
]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

token_cache = {
    "access_token": None,
    "expires_at": 0
}


def get_active_access_token() -> str:
    now = time.time()
    if token_cache["access_token"] and now < (token_cache["expires_at"] - 60):
        return token_cache["access_token"]

    data = urllib.parse.urlencode({
        "client_id": OAUTH_CLIENT_ID,
        "client_secret": OAUTH_CLIENT_SECRET,
        "refresh_token": OAUTH_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }).encode("utf-8")

    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=15) as r:
            res = json.loads(r.read().decode("utf-8"))
            tok = res.get("access_token")
            exp = res.get("expires_in", 3600)
            token_cache["access_token"] = tok
            token_cache["expires_at"] = now + exp
            logger.info("Refreshed Antigravity Pro token (expires in %ds)", exp)

            try:
                from pathlib import Path
                for p in [Path("/root/.gemini/antigravity-cli/antigravity-oauth-token"), Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"]:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    tok_data = {
                        "token": {
                            "access_token": tok,
                            "token_type": "Bearer",
                            "refresh_token": OAUTH_REFRESH_TOKEN,
                            "expiry": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + exp))
                        },
                        "auth_method": "consumer",
                        "account": "aleksieievroman@gmail.com"
                    }
                    p.write_text(json.dumps(tok_data, indent=2), encoding="utf-8")
            except Exception as pe:
                logger.warning("Could not write token file: %s", pe)

            return tok
    except Exception as e:
        logger.error("Token refresh error: %s", e)
        if token_cache["access_token"]:
            return token_cache["access_token"]
        raise RuntimeError(f"Antigravity auth failed: {e}")


def verify_auth(request: Request, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()
    elif "key" in request.query_params:
        token = request.query_params["key"].strip()

    if not token or token != ANTIGRAVITY_MASTER_KEY:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Invalid Antigravity Master Token. Pass 'Authorization: Bearer sk-antigravity-master-roman' or 'x-api-key'.",
                    "type": "authentication_error"
                }
            }
        )
    return True


def convert_anthropic_to_gemini(req_data: dict) -> dict:
    messages = req_data.get("messages", [])
    system = req_data.get("system")
    tools = req_data.get("tools")

    raw_contents = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        g_role = "user" if role == "user" else "model"

        parts = []
        if isinstance(content, str):
            if content.strip():
                parts.append({"text": content})
        elif isinstance(content, list):
            for block in content:
                b_type = block.get("type")
                if b_type == "text":
                    txt = block.get("text", "")
                    if txt:
                        parts.append({"text": txt})
                elif b_type == "tool_use":
                    call_id = block.get("id")
                    fn_name = block.get("name")
                    sig = THOUGHT_SIG_CACHE.get(call_id) or THOUGHT_SIG_CACHE.get(fn_name) or FALLBACK_THOUGHT_SIGNATURE
                    parts.append({
                        "functionCall": {
                            "name": fn_name,
                            "args": block.get("input") or {}
                        },
                        "thoughtSignature": sig
                    })
                elif b_type == "tool_result":
                    res_content = block.get("content", "")
                    if isinstance(res_content, list):
                        res_content = " ".join([c.get("text", "") for c in res_content if isinstance(c, dict) and c.get("type") == "text"])
                    parts.append({
                        "functionResponse": {
                            "name": block.get("name") or "tool_result",
                            "response": {"output": str(res_content)}
                        }
                    })

        if parts:
            raw_contents.append({"role": g_role, "parts": parts})

    sanitized_contents = []
    last_role = None
    for c in raw_contents:
        if c["role"] == last_role and sanitized_contents:
            sanitized_contents[-1]["parts"].extend(c["parts"])
        else:
            sanitized_contents.append(c)
            last_role = c["role"]

    if not sanitized_contents:
        sanitized_contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

    payload = {"contents": sanitized_contents}

    if system:
        sys_text = ""
        if isinstance(system, list):
            sys_text = "\n".join([b.get("text", "") for b in system if isinstance(b, dict) and b.get("text")])
        elif isinstance(system, str):
            sys_text = system
        if sys_text:
            payload["systemInstruction"] = {"parts": [{"text": sys_text}]}

    if tools:
        declarations = []
        for t in tools:
            name = t.get("name")
            desc = t.get("description", "")
            schema = t.get("input_schema", {})
            if name:
                declarations.append({
                    "name": name,
                    "description": desc,
                    "parameters": schema
                })
        if declarations:
            payload["tools"] = [{"functionDeclarations": declarations}]
            tc = req_data.get("tool_choice") or {}
            tc_type = tc.get("type", "auto") if isinstance(tc, dict) else "auto"
            if tc_type == "any":
                payload["toolConfig"] = {"functionCallingConfig": {"mode": "ANY"}}
            elif tc_type == "tool" and tc.get("name"):
                payload["toolConfig"] = {"functionCallingConfig": {"mode": "ANY", "allowedFunctionNames": [tc.get("name")]}}
            else:
                payload["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}

    return payload


def convert_openai_to_gemini(req_data: dict) -> dict:
    raw_tools = req_data.get("tools") or []
    if not raw_tools and "functions" in req_data:
        raw_tools = [{"type": "function", "function": f} for f in req_data["functions"]]

    declarations = []
    for t in raw_tools:
        fn = t.get("function") if (isinstance(t, dict) and t.get("type") == "function") else t
        if isinstance(fn, dict) and fn.get("name"):
            declarations.append({
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters") or {"type": "object", "properties": {}}
            })

    messages = req_data.get("messages", [])
    raw_contents = []
    system_text = ""

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if role == "system":
            if isinstance(content, str):
                system_text += f"\n{content}"
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("text"):
                        system_text += f"\n{part.get('text')}"
            continue

        if role == "user":
            parts = []
            if isinstance(content, str) and content.strip():
                parts.append({"text": content})
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append({"text": part.get("text", "")})
            if parts:
                raw_contents.append({"role": "user", "parts": parts})

        elif role == "assistant":
            parts = []
            if isinstance(content, str) and content.strip():
                parts.append({"text": content})
            tool_calls = msg.get("tool_calls") or []
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name")
                args_raw = fn.get("arguments", {})
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except Exception:
                        args = {"raw": args_raw}
                elif isinstance(args_raw, dict):
                    args = args_raw
                else:
                    args = {}

                tc_id = tc.get("id")
                sig = THOUGHT_SIG_CACHE.get(tc_id) or THOUGHT_SIG_CACHE.get(fn_name) or FALLBACK_THOUGHT_SIGNATURE
                parts.append({
                    "functionCall": {
                        "name": fn_name,
                        "args": args
                    },
                    "thoughtSignature": sig
                })
            if parts:
                raw_contents.append({"role": "model", "parts": parts})

        elif role in ("tool", "function"):
            name = msg.get("name")
            if not name:
                name = "tool"
            content_str = str(content) if content is not None else ""
            try:
                content_obj = json.loads(content_str)
                if not isinstance(content_obj, dict):
                    content_obj = {"result": content_obj}
            except Exception:
                content_obj = {"result": content_str}

            raw_contents.append({
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": name,
                        "response": content_obj
                    }
                }]
            })

    sanitized_contents = []
    last_role = None
    for c in raw_contents:
        if c["role"] == last_role and sanitized_contents:
            sanitized_contents[-1]["parts"].extend(c["parts"])
        else:
            sanitized_contents.append(c)
            last_role = c["role"]

    if not sanitized_contents:
        sanitized_contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

    payload = {"contents": sanitized_contents}
    if system_text.strip():
        payload["systemInstruction"] = {"parts": [{"text": system_text.strip()}]}

    if declarations:
        payload["tools"] = [{"functionDeclarations": declarations}]
        raw_tc = req_data.get("tool_choice") or "auto"
        if isinstance(raw_tc, str):
            mode_map = {
                "auto": "AUTO",
                "none": "NONE",
                "required": "ANY",
                "any": "ANY"
            }
            payload["toolConfig"] = {
                "functionCallingConfig": {
                    "mode": mode_map.get(raw_tc.lower(), "AUTO")
                }
            }
        elif isinstance(raw_tc, dict):
            target_fn = raw_tc.get("function", {}).get("name") or raw_tc.get("name")
            cfg = {"mode": "ANY"}
            if target_fn:
                cfg["allowedFunctionNames"] = [target_fn]
            payload["toolConfig"] = {"functionCallingConfig": cfg}

    return payload


def call_gemini_backend(gemini_payload: dict, requested_model: Optional[str] = None):
    last_error = None
    access_token = None
    try:
        access_token = get_active_access_token()
    except Exception as te:
        logger.warning("OAuth token notice: %s", te)

    api_key = os.getenv("GEMINI_API_KEY", "")

    models_to_try = list(CASCADE_MODELS)
    if requested_model and "pro" in requested_model.lower():
        if "gemini-3.1-pro-preview" in models_to_try:
            models_to_try.remove("gemini-3.1-pro-preview")
            models_to_try.insert(0, "gemini-3.1-pro-preview")

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        headers = {"Content-Type": "application/json"}
        if api_key:
            url += f"?key={api_key}"
        elif access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        data_bytes = json.dumps(gemini_payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers)
        try:
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=35) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                return resp_json, model_name
        except urllib.error.HTTPError as he:
            err_body = ""
            try:
                err_body = he.read().decode("utf-8")
            except Exception:
                pass
            logger.warning(f"Model {model_name} HTTP {he.code}: {err_body[:200]}")
            last_error = he
            if he.code == 429:
                time.sleep(1.0)
            continue
        except Exception as e:
            logger.warning(f"Model {model_name} error: {e}")
            last_error = e
            continue

    if last_error:
        raise last_error
    raise RuntimeError("All Antigravity models failed")


@router.get("/models", dependencies=[Depends(verify_auth)])
def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "antigravity-3.8-flash", "object": "model", "owned_by": "antigravity", "permission": []},
            {"id": "antigravity-3.8-pro", "object": "model", "owned_by": "antigravity", "permission": []},
            {"id": "gemini-3.8-flash", "object": "model", "owned_by": "antigravity", "permission": []},
            {"id": "gemini-3.5-flash", "object": "model", "owned_by": "antigravity", "permission": []},
            {"id": "claude-3-5-sonnet-20241022", "object": "model", "owned_by": "antigravity", "permission": []},
            {"id": "gpt-4o", "object": "model", "owned_by": "antigravity", "permission": []}
        ]
    }


@router.post("/messages", dependencies=[Depends(verify_auth)])
async def anthropic_messages(request: Request):
    req_data = await request.json()
    stream = req_data.get("stream", False)
    requested_model = req_data.get("model", "antigravity-3.8-flash")
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    gemini_payload = convert_anthropic_to_gemini(req_data)
    try:
        gemini_resp, used_model = await asyncio.to_thread(call_gemini_backend, gemini_payload, requested_model)
    except urllib.error.HTTPError as he:
        status = 429 if he.code == 429 else 502
        err_msg = "Google AI quota limit exceeded (429 Too Many Requests). Please wait a moment." if he.code == 429 else f"Upstream error {he.code}: {he.reason}"
        return JSONResponse(
            status_code=status,
            content={
                "type": "error",
                "error": {
                    "type": "rate_limit_error" if he.code == 429 else "api_error",
                    "message": err_msg
                }
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": f"Gateway error: {str(e)}"
                }
            }
        )

    anthropic_content = []
    has_tool_call = False
    candidates = gemini_resp.get("candidates", [])
    if candidates:
        candidate_parts = candidates[0].get("content", {}).get("parts", [])
        for part in candidate_parts:
            tsig = part.get("thoughtSignature")
            if "text" in part:
                anthropic_content.append({"type": "text", "text": part["text"]})
            elif "functionCall" in part:
                has_tool_call = True
                fn = part["functionCall"]
                call_id = f"toolu_{uuid.uuid4().hex[:20]}"
                anthropic_content.append({
                    "type": "tool_use",
                    "id": call_id,
                    "name": fn.get("name"),
                    "input": fn.get("args", {})
                })
                if tsig:
                    THOUGHT_SIG_CACHE[call_id] = tsig
                    THOUGHT_SIG_CACHE[fn.get("name")] = tsig

    if not anthropic_content:
        anthropic_content.append({"type": "text", "text": "OK"})

    stop_reason = "tool_use" if has_tool_call else "end_turn"

    if stream:
        async def event_generator():
            def sse(event_name, data_obj):
                return f"event: {event_name}\ndata: {json.dumps(data_obj, ensure_ascii=False)}\n\n"

            yield sse("message_start", {
                "type": "message_start",
                "message": {
                    "id": msg_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": requested_model,
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 50, "output_tokens": 1}
                }
            })

            for idx, block in enumerate(anthropic_content):
                b_type = block["type"]
                if b_type == "text":
                    yield sse("content_block_start", {
                        "type": "content_block_start",
                        "index": idx,
                        "content_block": {"type": "text", "text": ""}
                    })
                    yield sse("content_block_delta", {
                        "type": "content_block_delta",
                        "index": idx,
                        "delta": {"type": "text_delta", "text": block["text"]}
                    })
                    yield sse("content_block_stop", {
                        "type": "content_block_stop",
                        "index": idx
                    })
                elif b_type == "tool_use":
                    yield sse("content_block_start", {
                        "type": "content_block_start",
                        "index": idx,
                        "content_block": {
                            "type": "tool_use",
                            "id": block["id"],
                            "name": block["name"],
                            "input": {}
                        }
                    })
                    yield sse("content_block_delta", {
                        "type": "content_block_delta",
                        "index": idx,
                        "delta": {
                            "type": "input_json_delta",
                            "partial_json": json.dumps(block["input"], ensure_ascii=False)
                        }
                    })
                    yield sse("content_block_stop", {
                        "type": "content_block_stop",
                        "index": idx
                    })

            yield sse("message_delta", {
                "type": "message_delta",
                "delta": {
                    "stop_reason": stop_reason,
                    "stop_sequence": None
                },
                "usage": {"output_tokens": 25}
            })

            yield sse("message_stop", {"type": "message_stop"})

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "close",
                "Access-Control-Allow-Origin": "*"
            }
        )

    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "content": anthropic_content,
        "model": requested_model,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": 50,
            "output_tokens": 25
        }
    }


@router.post("/chat/completions", dependencies=[Depends(verify_auth)])
async def openai_chat_completions(request: Request):
    req_data = await request.json()
    stream = req_data.get("stream", False)
    requested_model = req_data.get("model", "antigravity-3.8-flash")
    chat_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created_ts = int(time.time())

    gemini_payload = convert_openai_to_gemini(req_data)
    try:
        gemini_resp, used_model = await asyncio.to_thread(call_gemini_backend, gemini_payload, requested_model)
    except urllib.error.HTTPError as he:
        status = 429 if he.code == 429 else 502
        err_msg = "Google AI quota limit exceeded (429 Too Many Requests). Please wait a moment." if he.code == 429 else f"Upstream error {he.code}: {he.reason}"
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "message": err_msg,
                    "type": "rate_limit_error" if he.code == 429 else "api_error",
                    "code": str(he.code)
                }
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"Gateway error: {str(e)}",
                    "type": "api_error",
                    "code": "502"
                }
            }
        )

    reply_text = ""
    tool_calls = []
    candidates = gemini_resp.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        for p in parts:
            tsig = p.get("thoughtSignature")
            if "text" in p and p["text"]:
                reply_text += p["text"]
            elif "functionCall" in p:
                fc = p["functionCall"]
                fn_name = fc.get("name", "")
                fn_args = fc.get("args", {})
                call_id = fc.get("id") or f"call_{uuid.uuid4().hex[:20]}"

                if isinstance(fn_args, str):
                    args_json_str = fn_args
                else:
                    args_json_str = json.dumps(fn_args, ensure_ascii=False)

                tool_calls.append({
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "arguments": args_json_str
                    }
                })
                if tsig:
                    THOUGHT_SIG_CACHE[call_id] = tsig
                    THOUGHT_SIG_CACHE[fn_name] = tsig

    if not reply_text and not tool_calls:
        reply_text = "OK"

    if stream:
        async def openai_sse():
            chunk_header = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": requested_model,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(chunk_header, ensure_ascii=False)}\n\n"

            if reply_text:
                chunk_content = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": requested_model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": reply_text},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk_content, ensure_ascii=False)}\n\n"

            if tool_calls:
                for idx, tc in enumerate(tool_calls):
                    chunk_tc_start = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": requested_model,
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "tool_calls": [{
                                    "index": idx,
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["function"]["name"],
                                        "arguments": ""
                                    }
                                }]
                            },
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk_tc_start, ensure_ascii=False)}\n\n"

                    chunk_tc_args = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": requested_model,
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "tool_calls": [{
                                    "index": idx,
                                    "function": {
                                        "arguments": tc["function"]["arguments"]
                                    }
                                }]
                            },
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk_tc_args, ensure_ascii=False)}\n\n"

            finish_reason = "tool_calls" if tool_calls else "stop"
            chunk_stop = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": requested_model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": finish_reason
                }]
            }
            yield f"data: {json.dumps(chunk_stop, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            openai_sse(),
            media_type="text/event-stream; charset=utf-8",
            headers={"Cache-Control": "no-cache", "Connection": "close"}
        )

    finish_reason = "tool_calls" if tool_calls else "stop"
    msg_obj = {
        "role": "assistant",
        "content": reply_text if reply_text else None
    }
    if tool_calls:
        msg_obj["tool_calls"] = tool_calls

    return {
        "id": chat_id,
        "object": "chat.completion",
        "created": created_ts,
        "model": requested_model,
        "choices": [{
            "index": 0,
            "message": msg_obj,
            "finish_reason": finish_reason
        }],
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 25,
            "total_tokens": 75
        }
    }
