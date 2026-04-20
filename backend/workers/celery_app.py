"""
Celery app — Bomtempo Backend
Broker: Redis (REDIS_URL do .env)
Workers:
  - pdf      : 1 worker concurrency (alto RAM — ReportLab + Pillow)
  - ai       : 2 workers (OpenAI calls, agentic loop)
  - default  : 3 workers (misc tasks, email, etc.)

Para rodar em dev:
  celery -A backend.workers.celery_app worker --loglevel=info
"""

from celery import Celery

from backend.core.config import Config

celery_app = Celery(
    "bomtempo",
    broker=Config.REDIS_URL,
    backend=Config.REDIS_URL,
    include=[
        "backend.workers.tasks.pdf_tasks",
        "backend.workers.tasks.chat_tasks",
        "backend.workers.tasks.email_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    # Previne picos de memória no worker de PDF (1GB RAM do container)
    worker_max_tasks_per_child=50,
    # Filas separadas por criticidade de RAM
    task_routes={
        "backend.workers.tasks.pdf_tasks.*": {"queue": "pdf"},
        "backend.workers.tasks.chat_tasks.*": {"queue": "ai"},
        "backend.workers.tasks.email_tasks.*": {"queue": "default"},
    },
    # Timeouts
    task_soft_time_limit=120,   # 2 min soft (SIGTERM)
    task_time_limit=180,        # 3 min hard (SIGKILL)
    # Resultado expira após 1 hora (PDF gerado pode ser buscado pelo frontend)
    result_expires=3600,
)
