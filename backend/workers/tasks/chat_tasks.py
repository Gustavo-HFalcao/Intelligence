"""
Chat Tasks — Celery tasks para o loop agentic do Chat IA.
Resultado gravado em Redis com TTL 10min para polling SSE.
"""

import json
from typing import Any, Dict, List, Optional

from backend.workers.celery_app import celery_app
from backend.core.logging import get_logger

logger = get_logger(__name__)

_RESULT_TTL = 600  # 10 min


def _store_result(session_id: str, result: Dict[str, Any]) -> None:
    try:
        from backend.core.redis_cache import _get_client
        r = _get_client()
        if r:
            r.setex(f"chat_result:{session_id}", _RESULT_TTL, json.dumps(result, ensure_ascii=False))
    except Exception as e:
        logger.debug(f"store_result failed: {e}")


def get_result(session_id: str) -> Optional[Dict]:
    try:
        from backend.core.redis_cache import _get_client
        r = _get_client()
        if r:
            raw = r.get(f"chat_result:{session_id}")
            if raw:
                return json.loads(raw)
    except Exception as e:
        logger.debug(f"get_result failed: {e}")
    return None


@celery_app.task(name="backend.workers.tasks.chat_tasks.run_agentic_chat", bind=True, max_retries=0)
def run_agentic_chat(
    self,
    session_id: str,
    messages: List[Dict[str, Any]],
    client_id: str = "",
    user_login: str = "system",
    system_prompt: str = "",
) -> None:
    """Executa query_agentic com ferramentas. Resultado gravado em Redis."""
    try:
        from backend.integrations.ai import query_agentic, OPENAI_CHAT_MODEL
        from backend.integrations.ai_tools import TOOL_SCHEMAS, make_executor

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        executor = make_executor(client_id)
        content  = query_agentic(
            messages=full_messages,
            tools=TOOL_SCHEMAS,
            model=OPENAI_CHAT_MODEL,
            user_login=user_login,
            client_id=client_id,
            tool_executor=executor,
        )
        _store_result(session_id, {"status": "done", "content": content})
    except Exception as e:
        logger.error(f"run_agentic_chat error: {e}")
        _store_result(session_id, {"status": "error", "content": f"Erro interno: {e}"})
