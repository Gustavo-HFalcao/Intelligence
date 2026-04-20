"""
Email Celery tasks — placeholder para Fase D.5
"""
from backend.workers.celery_app import celery_app


@celery_app.task(name="backend.workers.tasks.email_tasks.send_password_reset")
def send_password_reset(email: str, reset_link: str) -> bool:
    """Envia email de reset de senha. Implementado na Fase D.5."""
    raise NotImplementedError("Implementar na Fase D.5")


@celery_app.task(name="backend.workers.tasks.email_tasks.send_alert_notification")
def send_alert_notification(email: str, rule_name: str, details: dict) -> bool:
    """Envia notificação de alerta. Implementado na Fase D.5."""
    raise NotImplementedError("Implementar na Fase D.5")
