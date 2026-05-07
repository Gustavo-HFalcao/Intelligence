"""
AI router — /api/ai
Chat SSE streaming, agentic (Celery async), whisper, vision.
O endpoint /chat suporta dois modos:
  - streaming direto (quando Redis disponível: stream inline)
  - Celery async (enfileira task, cliente pollers /stream/{session_id})
"""

import asyncio
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse

from backend.integrations.supabase import sb_select
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant
from backend.core.logging import get_logger
from backend.core.audit import audit_log, AuditCategory

router = APIRouter(prefix="/api/ai", tags=["ai"])
logger = get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)

SYSTEM_PROMPT = """Você é o Agente Bomtempo Intelligence — IA especializada em gestão de obras, contratos EPC/O&M e análise de performance operacional.

Você tem acesso completo aos dados reais do tenant via 8 ferramentas:
1. list_contracts        — todos os contratos com dias restantes, valor contratado, gestor, prioridade
2. get_contract_kpis     — KPIs detalhados: SPI, CPI, lista de atividades atrasadas, chuvas/interrupções dos RDOs
3. get_activities        — atividades filtradas (todas/atrasadas/críticas/em_andamento/pendentes/concluídas) + busca por palavra-chave
4. get_financial_summary — visão financeira previsto×executado por categoria, desvio percentual
5. get_rdo_history       — histórico de RDOs com atividades executadas, clima, interrupções
6. get_om_data           — geração de energia (kWh), Performance Ratio, disponibilidade da planta
7. get_alerts            — alertas ativos do sistema
8. get_timeline          — linha do tempo de eventos e marcos por contrato

Regras:
- Sempre responda em português do Brasil.
- Use ferramentas ANTES de afirmar qualquer dado — nunca invente números.
- Cite os valores consultados com contexto (ex: "SPI 0.87 → cronograma 13% atrasado").
- Para análises amplas, combine múltiplas ferramentas.
- Seja objetivo e técnico: o usuário é engenheiro de obras."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_messages(history: List[Dict], user_message: str) -> List[Dict]:
    msgs = []
    for h in (history or []):
        role    = h.get("role","user")
        content = h.get("content","")
        if role in ("user","assistant") and content:
            msgs.append({"role":role, "content":content})
    msgs.append({"role":"user", "content":user_message})
    return msgs


async def _stream_generator(
    messages: List[Dict],
    model: str,
    user_login: str,
    client_id: str,
) -> AsyncGenerator[str, None]:
    loop = asyncio.get_event_loop()
    from backend.integrations.ai import stream as ai_stream

    def _gen():
        return list(ai_stream(messages, model=model, user_login=user_login, client_id=client_id))

    try:
        tokens = await loop.run_in_executor(_executor, _gen)
        for token in tokens:
            data = json.dumps({"choices":[{"delta":{"content":token}}]})
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/chat")
async def chat(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> StreamingResponse:
    """
    Chat SSE endpoint. Suporta streaming direto.
    Body: { message: str, history: [...], session_id: str }
    """
    from backend.integrations.ai import OPENAI_CHAT_MODEL

    user_message = str(body.get("message","")).strip()
    history      = body.get("history", [])
    model        = body.get("model", OPENAI_CHAT_MODEL)
    user_login   = user.get("login","system")

    if not user_message:
        return JSONResponse(status_code=400, content={"error":"Mensagem vazia"})

    messages = _build_messages(history, user_message)

    # Prepend system prompt
    full_messages = [{"role":"system","content":SYSTEM_PROMPT}] + messages

    audit_log(
        category=AuditCategory.AI_CHAT,
        action=f"Chat: {user_message[:120]}",
        username=user_login,
        client_id=client_id or "",
        metadata={"model": model, "history_len": len(history)},
    )

    return StreamingResponse(
        _stream_generator(full_messages, model, user_login, client_id or ""),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering":"no",
        },
    )


@router.post("/chat/agentic")
async def chat_agentic(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """
    Chat agentic via Celery (async). Retorna session_id para polling.
    Polling: GET /api/ai/stream/{session_id}
    """
    user_message = str(body.get("message","")).strip()
    history      = body.get("history", [])
    session_id   = body.get("session_id") or str(uuid.uuid4())
    user_login   = user.get("login","system")

    if not user_message:
        return {"error":"Mensagem vazia"}

    messages = _build_messages(history, user_message)

    from backend.core.redis_cache import is_redis_available

    async def _run_inline() -> Dict[str, Any]:
        from backend.integrations.ai import query_agentic, OPENAI_CHAT_MODEL
        from backend.integrations.ai_tools import TOOL_SCHEMAS, make_executor
        loop = asyncio.get_event_loop()
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        executor_fn   = make_executor(client_id or "")
        content = await loop.run_in_executor(
            _executor,
            lambda: query_agentic(
                messages=full_messages,
                tools=TOOL_SCHEMAS,
                model=OPENAI_CHAT_MODEL,
                user_login=user_login,
                client_id=client_id or "",
                tool_executor=executor_fn,
            ),
        )
        return {"status": "done", "session_id": session_id, "content": content}

    # Se Redis não disponível, não há como retornar resultado via polling — executar inline
    if not is_redis_available():
        logger.info("Redis indisponível — executando agentic inline")
        try:
            result = await _run_inline()
            audit_log(
                category=AuditCategory.AI_CHAT,
                action=f"Agentic chat inline: {user_message[:120]}",
                username=user_login,
                client_id=client_id or "",
                metadata={"session_id": session_id, "mode": "inline"},
            )
            return result
        except Exception as e:
            return {"status": "error", "session_id": session_id, "content": f"Erro: {e}"}

    try:
        from backend.workers.celery_app import celery_app
        celery_app.send_task(
            "backend.workers.tasks.chat_tasks.run_agentic_chat",
            kwargs={
                "session_id":    session_id,
                "messages":      messages,
                "client_id":     client_id or "",
                "user_login":    user_login,
                "system_prompt": SYSTEM_PROMPT,
            },
        )
        audit_log(
            category=AuditCategory.AI_CHAT,
            action=f"Agentic chat queued: {user_message[:120]}",
            username=user_login,
            client_id=client_id or "",
            metadata={"session_id": session_id, "history_len": len(history)},
        )
        return {"status": "queued", "session_id": session_id}
    except Exception as e:
        logger.warning(f"Celery não disponível: {e} — executando inline")
        try:
            return await _run_inline()
        except Exception as e2:
            return {"status": "error", "session_id": session_id, "content": f"Erro: {e2}"}


@router.get("/stream/{sid}")
async def poll_stream(sid: str, user=Depends(get_current_user)) -> Dict[str, Any]:
    """Polling endpoint para resultado do chat agentic."""
    from backend.workers.tasks.chat_tasks import get_result
    result = get_result(sid)
    if result is None:
        return {"status":"pending", "session_id":sid}
    return {**result, "session_id":sid}


@router.post("/whisper")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("pt"),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Transcrição de áudio via Whisper."""
    audio_bytes = await file.read()
    loop = asyncio.get_event_loop()
    from backend.integrations.ai import transcribe_audio
    try:
        text = await loop.run_in_executor(
            _executor,
            lambda: transcribe_audio(audio_bytes, file.filename or "audio.webm", language),
        )
        return {"ok":True, "text":text}
    except Exception as e:
        return {"ok":False, "error":str(e)}


@router.post("/vision")
async def vision_analyze(
    file: UploadFile = File(...),
    prompt: str = Form("Descreva o que você vê nesta imagem."),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Análise de imagem via GPT-4o Vision."""
    img_bytes    = await file.read()
    content_type = file.content_type or "image/jpeg"
    loop = asyncio.get_event_loop()
    from backend.integrations.ai import analyze_image
    try:
        result = await loop.run_in_executor(
            _executor,
            lambda: analyze_image(img_bytes, prompt, content_type),
        )
        return {"ok":True, "result":result}
    except Exception as e:
        return {"ok":False, "error":str(e)}


@router.get("/tools")
async def list_tools(user=Depends(get_current_user)) -> Dict[str, Any]:
    """Lista as ferramentas disponíveis para o agentic loop."""
    from backend.integrations.ai_tools import TOOL_SCHEMAS
    return {"tools":[t["function"]["name"] for t in TOOL_SCHEMAS], "total":len(TOOL_SCHEMAS)}
