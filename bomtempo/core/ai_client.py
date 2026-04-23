import json
import os
import threading
import time

from dotenv import load_dotenv
from openai import OpenAI

from bomtempo.core.logging_utils import get_logger

load_dotenv()
logger = get_logger(__name__)

# Chat AI Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
API_KEY = OPENAI_API_KEY
BASE_URL = "https://api.openai.com/v1"

# Vision API key (for fuel receipt analysis)
OPENAI_VISION_KEY = os.environ.get("OPENAI_VISION_KEY", OPENAI_API_KEY)

# ── Token Cost Table (USD per 1M tokens) ───────────────────────────────────────
_COST_TABLE = {
    "gpt-4o":              {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":         {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":         {"input": 10.00, "output": 30.00},
    "gpt-4":               {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo":       {"input": 0.50,  "output": 1.50},
    "whisper-1":           {"input": 0.006, "output": 0.0},   # per minute, not token
    "tts-1":               {"input": 0.015, "output": 0.0},   # per 1K chars
    "tts-1-hd":            {"input": 0.030, "output": 0.0},
}

def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost in USD based on token counts and model pricing."""
    costs = _COST_TABLE.get(model, {"input": 0.002, "output": 0.008})
    return (prompt_tokens * costs["input"] + completion_tokens * costs["output"]) / 1_000_000


def _log_observability(record: dict):
    """Fire-and-forget: insert record into llm_observability table."""
    def _insert():
        try:
            from bomtempo.core.supabase_client import sb_insert
            sb_insert("llm_observability", record)
        except Exception as e:
            logger.warning(f"Observability log failed (non-critical): {e}")
    threading.Thread(target=_insert, daemon=True).start()


class AIClient:
    """Client for interacting with AI via OpenAI-compatible API with Agentic Tool Support."""

    def __init__(self):
        # 1. Chat Client (OpenAI/Kimi)
        self.client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL,
        )

        # 2. Audio Client (OpenAI Standard)
        if OPENAI_API_KEY:
            self.audio_client = OpenAI(api_key=OPENAI_API_KEY)
        else:
            self.audio_client = None

        # 3. Vision Client (OpenAI gpt-4o)
        if OPENAI_VISION_KEY:
            self.vision_client = OpenAI(api_key=OPENAI_VISION_KEY)
        else:
            self.vision_client = None

    def query_agentic(
        self,
        messages: list[dict],
        tools: list[dict] = None,
        model: str = "gpt-4o",
        force_tool: bool = False,
        username: str = "system",
        session_id: str = "",
        tool_names_used: list[str] = None,
    ):
        """
        Executes one turn of the agentic loop with tool calling support.

        Returns:
            str  — final text response when the model has no tool calls.
            ChatCompletionMessage — the raw message object when tool_calls are present.
                The caller is responsible for serializing it to dict and appending to messages.
        """
        t0 = time.time()
        try:
            logger.info(f"Agentic Query → {model} | msgs={len(messages)}")
            # Na primeira iteração (sem histórico de tool results), força o uso de tools
            # para evitar que a IA "anuncie" antes de agir.
            has_tool_results = any(m.get("role") == "tool" for m in messages)
            if tools and force_tool and not has_tool_results:
                tool_choice = "required"
            elif tools:
                tool_choice = "auto"
            else:
                tool_choice = "none"
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools or [],
                tool_choice=tool_choice,
                temperature=0.3,
                # Parallel tool calls desabilitado: garante ordem determinística
                # (executa get_schema_info antes de execute_sql antes de generate_chart_data)
                parallel_tool_calls=False,
            )
            response_message = response.choices[0].message
            usage = response.usage

            # ── Observability logging ─────────────────────────────────────────
            duration_ms = int((time.time() - t0) * 1000)
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0
            cost_usd = _estimate_cost(model, prompt_tokens, completion_tokens)

            called_tools = []
            if response_message.tool_calls:
                called_tools = [tc.function.name for tc in response_message.tool_calls]
            if tool_names_used:
                called_tools = list(set(called_tools + tool_names_used))

            _log_observability({
                "model": model,
                "username": username,
                "session_id": session_id or "",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": round(cost_usd, 8),
                "tool_names": called_tools,
                "duration_ms": duration_ms,
                "call_type": "agentic",
                "error": None,
            })
            # ─────────────────────────────────────────────────────────────────

            if response_message.tool_calls:
                # Retorna o objeto bruto — o caller serializa e appenda ao histórico
                return response_message

            return response_message.content or ""

        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)
            _log_observability({
                "model": model,
                "username": username,
                "session_id": session_id or "",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "tool_names": [],
                "duration_ms": duration_ms,
                "call_type": "agentic",
                "error": str(e)[:500],
            })
            logger.error(f"Error in Agentic Query: {e}")
            return "Desculpe, falhei ao processar como agente. Tente novamente."

    def query_stream(self, messages: list[dict], model: str = "gpt-4o", max_tokens: int = 8192, username: str = "system", session_id: str = ""):
        """
        Streams a query, yielding text chunks as they arrive.
        """
        t0 = time.time()
        total_chars = 0
        try:
            logger.info(f"Streaming request to AI (model: {model})...")
            stream = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
            prompt_tokens = 0
            completion_tokens = 0
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_chars += len(content)
                    yield content
                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
            duration_ms = int((time.time() - t0) * 1000)
            _log_observability({
                "model": model,
                "username": username,
                "session_id": session_id or "",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "cost_usd": round(_estimate_cost(model, prompt_tokens, completion_tokens), 8),
                "tool_names": [],
                "duration_ms": duration_ms,
                "call_type": "stream",
                "error": None,
            })
        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)
            _log_observability({
                "model": model,
                "username": username,
                "session_id": session_id or "",
                "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                "cost_usd": 0.0, "tool_names": [], "duration_ms": duration_ms,
                "call_type": "stream", "error": str(e)[:500],
            })
            logger.error(f"Error streaming from AI: {e}")
            raise

    def query(self, messages: list[dict], model: str = "gpt-4o", username: str = "system", session_id: str = "", system_prompt: str = "", max_tokens: int = 0) -> str:
        """Standard non-streaming completion."""
        t0 = time.time()
        try:
            # Inject system_prompt as first message if provided and not already present
            effective_messages = list(messages)
            if system_prompt and (not effective_messages or effective_messages[0].get("role") != "system"):
                effective_messages = [{"role": "system", "content": system_prompt}] + effective_messages
            create_kwargs: dict = {
                "model": model,
                "messages": effective_messages,
                "temperature": 0.3,
            }
            if max_tokens > 0:
                create_kwargs["max_tokens"] = max_tokens
            response = self.client.chat.completions.create(**create_kwargs)
            usage = response.usage
            duration_ms = int((time.time() - t0) * 1000)
            _log_observability({
                "model": model,
                "username": username,
                "session_id": session_id or "",
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
                "cost_usd": round(_estimate_cost(model, usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0), 8),
                "tool_names": [],
                "duration_ms": duration_ms,
                "call_type": "query",
                "error": None,
            })
            return response.choices[0].message.content
        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)
            _log_observability({
                "model": model, "username": username, "session_id": session_id or "",
                "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                "cost_usd": 0.0, "tool_names": [], "duration_ms": duration_ms,
                "call_type": "query", "error": str(e)[:500],
            })
            logger.error(f"Error querying AI: {e}")
            return "Erro ao processar solicitação."

    def transcribe_audio(self, file_path: str) -> str:
        """Transcribes audio file using Whisper."""
        if not self.audio_client: return "[ERRO] Configuração incompleta."
        try:
            with open(file_path, "rb") as audio_file:
                transcription = self.audio_client.audio.transcriptions.create(
                    model="whisper-1", file=audio_file, response_format="text"
                )
            return str(transcription)
        except Exception as e:
            logger.error(f"Error transcribing: {e}")
            return f"[ERRO] {str(e)}"

    def analyze_receipt_image(self, image_b64: str, mime: str = "image/jpeg") -> dict:
        """Analyzes receipt using Vision API."""
        if not self.vision_client: return {}
        prompt = """Analise este cupom e retorne um JSON com: fuel_type, liters, price_per_liter, total, date, station, confidence."""
        try:
            response = self.vision_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}}]}],
                max_tokens=400,
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
            if "```" in raw: raw = raw.split("```")[1].replace("json", "")
            return json.loads(raw)
        except Exception: return {}


# Singleton instance
ai_client = AIClient()
