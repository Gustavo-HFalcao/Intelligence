"""
Circuit Breaker — proteção para APIs externas (IA, Nominatim, Email, etc.)

Estados:
  CLOSED    — operação normal, falhas são contadas
  OPEN      — circuito aberto, chamadas retornam fallback imediatamente (fail-fast)
  HALF_OPEN — após reset_timeout, tenta UMA chamada de teste; se passar → CLOSED

Thread-safe via threading.Lock. In-process por agora — quando tivermos Redis
(Fase 4), substituir por circuit breaker distribuído com state no Redis.

Uso:
    from bomtempo.core.circuit_breaker import ia_breaker, nominatim_breaker

    # Síncrono (em background tasks):
    result = ia_breaker.call(lambda: ai_client.query(msgs), fallback="")

    # Assíncrono (em handlers async):
    result = await ia_breaker.async_call(coro_or_awaitable, fallback="")
"""
import asyncio
import threading
import time
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class _CBState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker simples, thread-safe, com suporte sync e async."""

    def __init__(self, name: str, fail_max: int = 5, reset_timeout: float = 60.0):
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self._state = _CBState.CLOSED
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

    # ── Estado ────────────────────────────────────────────────────────────────

    @property
    def state(self) -> _CBState:
        with self._lock:
            if self._state == _CBState.OPEN:
                if time.monotonic() - (self._opened_at or 0) >= self.reset_timeout:
                    self._state = _CBState.HALF_OPEN
                    logger.info(f"[CB:{self.name}] HALF_OPEN — tentando recuperar")
            return self._state

    def is_open(self) -> bool:
        return self.state == _CBState.OPEN

    def record_success(self):
        with self._lock:
            if self._state in (_CBState.HALF_OPEN, _CBState.OPEN):
                logger.info(f"[CB:{self.name}] CLOSED — serviço recuperado")
            self._state = _CBState.CLOSED
            self._failures = 0
            self._opened_at = None

    def record_failure(self, exc: Exception = None):
        with self._lock:
            self._failures += 1
            if self._state == _CBState.HALF_OPEN or self._failures >= self.fail_max:
                self._state = _CBState.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    f"[CB:{self.name}] OPEN — {self._failures} falha(s) "
                    f"(cooldown {self.reset_timeout}s)"
                    + (f" | último erro: {exc}" if exc else "")
                )

    # ── Chamadas síncronas ────────────────────────────────────────────────────

    def call(self, func: Callable[[], T], fallback: T = None) -> T:
        """Executa func com proteção. Retorna fallback se circuito estiver aberto."""
        if self.is_open():
            logger.debug(f"[CB:{self.name}] bloqueado — circuito aberto, retornando fallback")
            return fallback
        try:
            result = func()
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure(exc)
            return fallback

    # ── Chamadas assíncronas ──────────────────────────────────────────────────

    async def async_call(self, coro, fallback: Any = None) -> Any:
        """Versão async: await async_call(coro_func(), fallback=...)"""
        if self.is_open():
            logger.debug(f"[CB:{self.name}] bloqueado (async) — retornando fallback")
            return fallback
        try:
            result = await coro
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure(exc)
            return fallback

    # ── Diagnóstico ───────────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self._failures,
            "fail_max": self.fail_max,
            "opened_at": self._opened_at,
            "reset_timeout": self.reset_timeout,
        }


# ── Breakers globais — importar diretamente nos módulos que precisam ──────────

# IA (OpenAI / Claude): 3 falhas consecutivas → 60s de cooldown
ia_breaker = CircuitBreaker("ia_client", fail_max=3, reset_timeout=60.0)

# Nominatim geocoding: latência alta e rate-limit — 3 falhas → 30s
nominatim_breaker = CircuitBreaker("nominatim", fail_max=3, reset_timeout=30.0)

# Email (SMTP / Twilio / SendGrid): 5 falhas → 120s
email_breaker = CircuitBreaker("email", fail_max=5, reset_timeout=120.0)

# Supabase Storage: uploads — 5 falhas → 60s
storage_breaker = CircuitBreaker("storage", fail_max=5, reset_timeout=60.0)

# PDF (Playwright subprocess): 3 falhas consecutivas → 5 min de cooldown.
# Quando aberto, RDOs são salvos e enviados por email sem PDF anexo.
# O usuário pode gerar o PDF manualmente no histórico quando o sistema se recuperar.
# reset_timeout=300 é conservador — evita tentar logo após OOM (sistema pode estar
# em processo de liberar memória antes de tentar de novo).
pdf_breaker = CircuitBreaker("pdf_playwright", fail_max=3, reset_timeout=300.0)
