"""
Thread Pool Executors dedicados — Bomtempo Platform

Problema com o pool default do Python:
  - min(32, cpu_count + 4) threads compartilhadas por TODO o processo
  - PDF + IA + uploads + queries DB disputam as mesmas threads
  - Se 4 PDFs são gerados, queries de login ficam na fila → latência visível

Solução: pools separados por CATEGORIA de trabalho com limites ajustados.

Uso em handlers async:
    from bomtempo.core.executors import get_ai_executor, get_heavy_executor, get_image_executor

    result = await loop.run_in_executor(get_ai_executor(), lambda: ai_call())
    pdf    = await loop.run_in_executor(get_heavy_executor(), lambda: generate_pdf())
    foto   = await loop.run_in_executor(get_image_executor(), lambda: process_image())

Regra: NUNCA use `loop.run_in_executor(None, ...)` — sempre especifique o executor
       correto para sua categoria de trabalho.
"""
from concurrent.futures import ThreadPoolExecutor

# ── Executor: IA ──────────────────────────────────────────────────────────────
# Chamadas para OpenAI, Claude, etc. — latência: 5–30s por chamada
# max_workers=2: no máximo 2 análises IA simultâneas — previne que 10 RDOs
# simultâneos saturem o sistema inteiro
_ai_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bt-ai")

# ── Executor: PDF (xhtml2pdf via subprocess) ──────────────────────────────────
# max_workers=1: cada geração spawna um multiprocessing.Process isolado.
# 1 worker garante fila sequencial — múltiplos envios de RDO não se sobrepõem.
# Se max_workers>1, dois subprocessos xhtml2pdf rodariam em paralelo (~40-80MB cada).
# Por precaução com o container Fly.io 1GB, mantemos 1.
# NOTA: upload_pdf e operações HTTP NÃO devem usar este executor — use get_http_executor().
_heavy_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bt-heavy")

# ── Executor: Imagem ──────────────────────────────────────────────────────────
# Watermark + EXIF + resize de fotos de celular (PIL, ~1–3s por foto após resize).
# Separado do _heavy_executor para não bloquear geração de PDFs.
# max_workers=3: 3 uploads simultâneos (EPI + evidência + ferramentas) sem disputar
# com Chromium.
_image_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="bt-img")

# ── Executor: HTTP externo ────────────────────────────────────────────────────
# Geocoding Nominatim, webhooks, APIs REST externas (sem ser o Supabase)
# max_workers=4: chamadas HTTP leves mas com latência de rede
_http_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bt-http")

# ── Executor: DB ─────────────────────────────────────────────────────────────
# Queries síncronas ao Supabase via httpx.Client que ainda precisam de executor
# max_workers=8: Supabase REST é rápido (< 500ms), pode ter mais parallelismo
# Note: prefira async_sb_* diretamente em handlers async — mais eficiente que executor
_db_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="bt-db")


def get_ai_executor() -> ThreadPoolExecutor:
    """Chamadas para APIs de IA (OpenAI, Claude, análise de texto)."""
    return _ai_executor


def get_heavy_executor() -> ThreadPoolExecutor:
    """PDF (xhtml2pdf em subprocess isolado). Fila de 1 — não usar para uploads/imagens."""
    return _heavy_executor


def get_image_executor() -> ThreadPoolExecutor:
    """Processamento de imagem: watermark, EXIF, resize (PIL). Separado do PDF."""
    return _image_executor


def get_http_executor() -> ThreadPoolExecutor:
    """Geocoding, webhooks, APIs HTTP externas sem ser o Supabase."""
    return _http_executor


def get_db_executor() -> ThreadPoolExecutor:
    """Queries síncronas ao Supabase. Prefira async_sb_* quando possível."""
    return _db_executor
