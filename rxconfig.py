import os
import reflex as rx
from dotenv import load_dotenv

load_dotenv()  # garante que REDIS_URL e outras vars do .env sejam carregadas antes do rx.Config

# ── Redis session state ────────────────────────────────────────────────────────
# Quando REDIS_URL está configurado no .env, o Reflex usa Redis para persistir
# o estado de sessão de cada usuário.
#
# Benefício para 1 worker / 1 CPU (NÃO usar múltiplos workers nesse ambiente):
#   - Restarts e deploys não derrubam as sessões ativas dos usuários
#   - Zero cold-start: estado não se perde ao fazer `reflex run` de novo
#
# Para ativar: adicione REDIS_URL=redis://localhost:6379/0 ao .env
# Sem REDIS_URL: Reflex usa in-memory state (comportamento padrão atual)
#
# IMPORTANTE — workers com 1 CPU + 1GB RAM:
#   NÃO use múltiplos workers nesse ambiente.
#   - Cada worker Python consome ~150-200MB RAM → 4 workers = OOM garantido
#   - 1 CPU: workers disputam o mesmo núcleo sem ganho real
#   - Nosso async I/O (run_in_executor, background tasks) já garante
#     concorrência adequada para múltiplos usuários com 1 worker
#   - Se o servidor escalar para 2+ CPUs e 4GB+, revisite a Fase 4 do Architecture-boost.md

_redis_url = os.getenv("REDIS_URL", "")

config = rx.Config(
    app_name="bomtempo",
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
    uploads_dir="uploaded_files",
    # Redis para state persistence — ativo automaticamente quando REDIS_URL está no .env
    **({ "redis_url": _redis_url } if _redis_url else {}),
    # Aumentado de 10s para 60s: background tasks com PDF/AI podem ter async with self:
    # demorado quando Redis está sob carga. 60s dá margem sem risco de lock zombie
    # (background tasks em execução normal completam async with self: em <1s).
    state_manager_lock_expiration=60000,
)
