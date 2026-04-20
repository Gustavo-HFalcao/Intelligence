"""
Email Integration — Gmail SMTP.
Usado por: reset de senha, alertas proativos, RDO submetido.
Config: GMAIL_USER, GMAIL_APP_PASSWORD (App Password, não senha normal).
"""

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from backend.core.logging import get_logger

logger = get_logger(__name__)

GMAIL_USER     = os.getenv("GMAIL_USER") or os.getenv("RDO_EMAIL_USER", "")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("RDO_EMAIL_PASSWORD", "")
FROM_NAME      = os.getenv("EMAIL_FROM_NAME", "Bomtempo Intelligence")
SMTP_HOST      = "smtp.gmail.com"
SMTP_PORT      = 587


def send_email(
    to: List[str],
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """Envia email via Gmail SMTP. Retorna True se bem-sucedido."""
    if not GMAIL_USER or not GMAIL_PASSWORD:
        logger.warning("GMAIL_USER / GMAIL_APP_PASSWORD não configurados — email não enviado")
        return False
    if not to:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{FROM_NAME} <{GMAIL_USER}>"
        msg["To"]      = ", ".join(to)

        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, to, msg.as_string())

        logger.info(f"Email enviado para {to}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Falha ao enviar email: {e}")
        return False


# ── Templates ─────────────────────────────────────────────────────────────────

def send_reset_password(to_email: str, reset_token: str, base_url: str = "") -> bool:
    reset_url = f"{base_url}/reset-password?token={reset_token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
      <h2 style="color:#C98B2A">Redefinição de Senha — Bomtempo Intelligence</h2>
      <p>Você solicitou a redefinição de senha. Clique no link abaixo:</p>
      <a href="{reset_url}" style="display:inline-block;margin:16px 0;padding:12px 24px;background:#C98B2A;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold">
        Redefinir Senha
      </a>
      <p style="color:#888;font-size:12px">Link válido por 1 hora. Se não foi você, ignore este email.</p>
    </div>
    """
    return send_email([to_email], "Redefinição de Senha — Bomtempo", html)


def send_alert_notification(to_emails: List[str], alert_type: str, alert_label: str, contrato: str, message: str) -> bool:
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:32px">
      <div style="border-left:4px solid #C98B2A;padding-left:16px;margin-bottom:24px">
        <h2 style="color:#C98B2A;margin:0">{alert_label}</h2>
        <p style="color:#888;margin:4px 0">Contrato: <strong>{contrato}</strong></p>
      </div>
      <p>{message}</p>
      <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
      <p style="color:#aaa;font-size:11px">Bomtempo Intelligence · Alerta automático</p>
    </div>
    """
    return send_email(to_emails, f"[Alerta] {alert_label} — {contrato}", html)


def send_rdo_submitted(to_emails: List[str], contrato: str, data: str, view_token: str, base_url: str = "") -> bool:
    view_url = f"{base_url}/rdo/{view_token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:32px">
      <h2 style="color:#C98B2A">RDO Submetido — {contrato}</h2>
      <p>O Relatório Diário de Obra de <strong>{data}</strong> foi submetido.</p>
      <a href="{view_url}" style="display:inline-block;margin:16px 0;padding:12px 24px;background:#2A9D8F;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold">
        Visualizar RDO
      </a>
      <p style="color:#aaa;font-size:11px">Bomtempo Intelligence</p>
    </div>
    """
    return send_email(to_emails, f"RDO Submetido — {contrato} · {data}", html)
