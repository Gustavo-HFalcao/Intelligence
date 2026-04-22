"""
Celery app — Bomtempo Backend
Broker: Redis (REDIS_URL do .env)
Workers:
  - pdf      : 1 worker concurrency (alto RAM — ReportLab + Pillow)
  - ai       : 2 workers (OpenAI calls, agentic loop)
  - default  : 3 workers (misc tasks, email, alerts)

Para rodar em dev:
  celery -A backend.workers.celery_app worker --loglevel=info
Para beat (alertas periódicos):
  celery -A backend.workers.celery_app beat --loglevel=info
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
        "backend.workers.tasks.alert_tasks",
        "backend.workers.tasks.insight_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    worker_max_tasks_per_child=50,
    task_routes={
        "backend.workers.tasks.pdf_tasks.*":     {"queue": "pdf"},
        "backend.workers.tasks.chat_tasks.*":    {"queue": "ai"},
        "backend.workers.tasks.email_tasks.*":   {"queue": "default"},
        "backend.workers.tasks.alert_tasks.*":   {"queue": "default"},
        "backend.workers.tasks.insight_tasks.*": {"queue": "default"},
    },
    task_soft_time_limit=120,
    task_time_limit=180,
    result_expires=3600,
    beat_schedule={
        "alert-sweep-hourly": {
            "task":     "backend.workers.tasks.alert_tasks.run_alert_sweep",
            "schedule": 3600,  # every 1 hour
        },
    },
)
