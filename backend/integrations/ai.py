"""
AI Integration — OpenAI-compatible client.
Suporta: query, stream, agentic tool-use, whisper (audio), vision (imagem).
Observabilidade: insere em llm_observability após cada chamada (fire-and-forget).
"""

import os
import threading
import time
from typing import Any, Dict, Generator, List, Optional

from backend.core.logging import get_logger
from backend.integrations.supabase import sb_insert

logger = get_logger(__name__)

OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL  = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

_COST_TABLE: Dict[str, Dict[str, float]] = {
    "gpt-4o":        {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":   {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":   {"input": 10.00, "output": 30.00},
    "gpt-4":         {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50,  "output": 1.50},
    "whisper-1":     {"input": 0.006, "output": 0.0},
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    costs = _COST_TABLE.get(model, {"input": 0.002, "output": 0.008})
    return (prompt_tokens * costs["input"] + completion_tokens * costs["output"]) / 1_000_000


def _log_obs(record: Dict[str, Any]) -> None:
    def _insert():
        try:
            sb_insert("llm_observability", record)
        except Exception as e:
            logger.debug(f"obs log failed: {e}")
    threading.Thread(target=_insert, daemon=True).start()


def _get_client():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY não configurada")
    from openai import OpenAI
    return OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


# ── Simples: query síncrona ───────────────────────────────────────────────────

def query(
    messages: List[Dict[str, Any]],
    model: str = OPENAI_CHAT_MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    user_login: str = "system",
    client_id: str = "",
    prompt_preview: str = "",
) -> str:
    client = _get_client()
    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, temperature=temperature,
        )
        content = resp.choices[0].message.content or ""
        usage = resp.usage
        cost  = _estimate_cost(model, usage.prompt_tokens, usage.completion_tokens)
        _log_obs({
            "model":             model,
            "endpoint":          "chat",
            "prompt_tokens":     usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens":      usage.total_tokens,
            "cost_usd":          cost,
            "latency_ms":        (time.time() - t0) * 1000,
            "success":           True,
            "user_login":        user_login,
            "client_id":         client_id,
            "prompt_preview":    prompt_preview[:200],
        })
        return content
    except Exception as e:
        _log_obs({ "model":model, "endpoint":"chat", "success":False, "error_msg":str(e)[:200],
                   "latency_ms":(time.time()-t0)*1000, "user_login":user_login, "client_id":client_id })
        raise


# ── Stream: gerador de tokens ────────────────────────────────────────────────

def stream(
    messages: List[Dict[str, Any]],
    model: str = OPENAI_CHAT_MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    user_login: str = "system",
    client_id: str = "",
) -> Generator[str, None, None]:
    client = _get_client()
    t0 = time.time()
    prompt_tokens = 0
    completion_tokens = 0
    try:
        with client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, temperature=temperature, stream=True,
        ) as resp_stream:
            for chunk in resp_stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    completion_tokens += 1
                    yield delta
        _log_obs({
            "model":model, "endpoint":"chat_stream", "success":True,
            "prompt_tokens":prompt_tokens, "completion_tokens":completion_tokens,
            "total_tokens":prompt_tokens+completion_tokens,
            "cost_usd":_estimate_cost(model, prompt_tokens, completion_tokens),
            "latency_ms":(time.time()-t0)*1000, "user_login":user_login, "client_id":client_id,
        })
    except Exception as e:
        _log_obs({ "model":model, "endpoint":"chat_stream", "success":False, "error_msg":str(e)[:200],
                   "latency_ms":(time.time()-t0)*1000, "user_login":user_login, "client_id":client_id })
        raise


# ── Agentic: tool-use loop ────────────────────────────────────────────────────

def query_agentic(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict]] = None,
    model: str = OPENAI_CHAT_MODEL,
    max_tokens: int = 4096,
    user_login: str = "system",
    client_id: str = "",
    tool_executor: Optional[Any] = None,
    max_iterations: int = 8,
) -> str:
    client = _get_client()
    t0 = time.time()
    msgs = list(messages)
    total_prompt = 0
    total_compl  = 0

    for _ in range(max_iterations):
        kwargs: Dict[str, Any] = dict(model=model, messages=msgs, max_tokens=max_tokens)
        if tools:
            kwargs["tools"]      = tools
            kwargs["tool_choice"] = "auto"

        resp = client.chat.completions.create(**kwargs)
        msg  = resp.choices[0].message
        usage = resp.usage
        total_prompt += usage.prompt_tokens
        total_compl  += usage.completion_tokens

        if not msg.tool_calls:
            content = msg.content or ""
            cost = _estimate_cost(model, total_prompt, total_compl)
            _log_obs({
                "model":model, "endpoint":"chat_agentic", "success":True,
                "prompt_tokens":total_prompt, "completion_tokens":total_compl,
                "total_tokens":total_prompt+total_compl, "cost_usd":cost,
                "latency_ms":(time.time()-t0)*1000, "user_login":user_login, "client_id":client_id,
            })
            return content

        # Execute tool calls
        msgs.append(msg.model_dump(exclude_unset=True))
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            import json
            try:
                fn_args = json.loads(tc.function.arguments)
            except Exception:
                fn_args = {}

            result = ""
            if tool_executor:
                try:
                    result = tool_executor(fn_name, fn_args)
                except Exception as e:
                    result = f"Erro: {e}"

            msgs.append({
                "role":        "tool",
                "tool_call_id": tc.id,
                "content":     str(result)[:4000],
            })

    return "Limite de iterações atingido."


# ── Whisper: transcrição de áudio ─────────────────────────────────────────────

def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm", language: str = "pt") -> str:
    client = _get_client()
    t0 = time.time()
    import io
    try:
        resp = client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, io.BytesIO(audio_bytes)),
            language=language,
        )
        _log_obs({ "model":"whisper-1", "endpoint":"transcription", "success":True,
                   "latency_ms":(time.time()-t0)*1000 })
        return resp.text or ""
    except Exception as e:
        _log_obs({ "model":"whisper-1", "endpoint":"transcription", "success":False, "error_msg":str(e)[:200],
                   "latency_ms":(time.time()-t0)*1000 })
        raise


# ── Vision: análise de imagem ─────────────────────────────────────────────────

def analyze_image(image_bytes: bytes, prompt: str, content_type: str = "image/jpeg", model: str = "gpt-4o-mini") -> str:
    import base64
    client = _get_client()
    b64 = base64.b64encode(image_bytes).decode()
    messages = [{
        "role": "user",
        "content": [
            {"type":"text", "text":prompt},
            {"type":"image_url", "image_url":{"url":f"data:{content_type};base64,{b64}"}},
        ],
    }]
    return query(messages, model=model, max_tokens=512)
