"""
AlertEmailService — Bomtempo Intelligence
Template HTML rico para emails de alerta.

Substitui o email de texto simples por um email enterprise:
- Header com badge de criticidade e ícone
- Seção "O que aconteceu" com valor atual vs threshold
- Contexto do contrato (últimos RDOs, tendência)
- Recomendação IA (2-3 linhas)
- CTA com link direto para o dashboard
"""
from __future__ import annotations

import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from bomtempo.core.config import Config
from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)

_BRT = timezone(timedelta(hours=-3))

# Mapa de métricas para labels PT-BR
_METRIC_LABELS: Dict[str, str] = {
    "desvio_prazo_pct": "Desvio de Prazo",
    "budget_overage_pct": "Estouro Orçamentário",
    "risk_score": "Score de Risco",
    "rdo_horas_sem_submit": "Horas sem RDO",
    "producao_queda_pct": "Queda de Produção",
}

_METRIC_UNITS: Dict[str, str] = {
    "desvio_prazo_pct": "%",
    "budget_overage_pct": "%",
    "risk_score": "/100",
    "rdo_horas_sem_submit": "h",
    "producao_queda_pct": "%",
}

# Cores de criticidade
_CRITICIDADE_COLORS: Dict[str, str] = {
    "alto": "#EF4444",
    "medio": "#F59E0B",
    "baixo": "#2A9D8F",
    "info": "#3B82F6",
}


def _get_ai_recommendation(rule_name: str, contrato: str, trigger_value: str, trigger_config: Dict) -> str:
    """Gera recomendação IA de 2-3 linhas para o email. Fallback vazio."""
    try:
        from bomtempo.core.ai_client import ai_client
        metric = trigger_config.get("metric", "")
        metric_label = _METRIC_LABELS.get(metric, metric)
        prompt = (
            f"Você é consultor de gestão de obras. "
            f"O alerta '{rule_name}' foi disparado para o contrato {contrato}. "
            f"Métrica: {metric_label} atingiu {trigger_value}. "
            f"Escreva exatamente 2 frases de recomendação prática e objetiva para o gestor. "
            f"Não mencione IA. Responda APENAS o texto, sem introdução."
        )
        resp = ai_client.query([{"role": "user", "content": prompt}], max_tokens=200)
        return (resp or "").strip()[:400]
    except Exception:
        return ""


def _build_html(data: Dict[str, Any], ai_recommendation: str = "") -> str:
    """Monta o HTML rico do email de alerta."""
    rule_name = data.get("rule_name", "Alerta")
    rule_description = data.get("rule_description", "")
    contrato = data.get("contrato", "—")
    trigger_value = data.get("trigger_value", "—")
    trigger_config = data.get("trigger_config") or {}
    category = data.get("category", "reativo")
    color = data.get("color", "#C98B2A")
    generated_at = data.get("generated_at", datetime.now(_BRT).strftime("%d/%m/%Y %H:%M BRT"))
    metadata = data.get("metadata") or {}
    app_url = Config.APP_URL

    metric = trigger_config.get("metric", "")
    metric_label = _METRIC_LABELS.get(metric, metric or "Evento")
    metric_unit = _METRIC_UNITS.get(metric, "")
    threshold = trigger_config.get("value", "")

    category_label = {"reativo": "Reativo", "cronologico": "Cronológico", "ia_personalizado": "IA Personalizado"}.get(
        category, category.title()
    )

    # Blocos de alertas de documento (metadata pode conter lista de alertas)
    doc_alertas_html = ""
    if metadata.get("alertas"):
        rows_html = ""
        for alerta in metadata["alertas"][:5]:
            crit = alerta.get("criticidade", "medio")
            crit_color = _CRITICIDADE_COLORS.get(crit, "#F59E0B")
            rows_html += f"""
            <tr>
              <td style="padding:8px 12px;border-bottom:1px solid #2a3a34;">
                <span style="background:{crit_color};color:#fff;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:700;">
                  {crit.upper()}
                </span>
              </td>
              <td style="padding:8px 12px;border-bottom:1px solid #2a3a34;color:#e0e8e4;">
                {alerta.get('descricao','—')}
              </td>
              <td style="padding:8px 12px;border-bottom:1px solid #2a3a34;color:#C98B2A;font-family:monospace;">
                {alerta.get('valor','') or '—'}
              </td>
            </tr>"""
        doc_alertas_html = f"""
        <div style="margin:20px 0;">
          <h3 style="color:#C98B2A;font-family:'Rajdhani',sans-serif;font-size:15px;margin:0 0 10px;">
            📋 ALERTAS IDENTIFICADOS NO DOCUMENTO
          </h3>
          <table style="width:100%;border-collapse:collapse;background:#0e2b22;border-radius:8px;overflow:hidden;">
            <thead>
              <tr style="background:#0a1e17;">
                <th style="padding:8px 12px;text-align:left;color:#C98B2A;font-size:12px;font-family:monospace;">CRITICIDADE</th>
                <th style="padding:8px 12px;text-align:left;color:#C98B2A;font-size:12px;font-family:monospace;">DESCRIÇÃO</th>
                <th style="padding:8px 12px;text-align:left;color:#C98B2A;font-size:12px;font-family:monospace;">VALOR</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>"""

    # Bloco de recomendação IA
    ai_block = ""
    if ai_recommendation:
        ai_block = f"""
        <div style="margin:20px 0;padding:16px;background:linear-gradient(135deg,rgba(42,157,143,0.15),rgba(201,139,42,0.1));
             border:1px solid rgba(42,157,143,0.4);border-radius:8px;">
          <p style="color:#2A9D8F;font-size:12px;font-weight:700;letter-spacing:0.1em;margin:0 0 8px;">
            ⚡ RECOMENDAÇÃO
          </p>
          <p style="color:#e0e8e4;font-size:14px;line-height:1.6;margin:0;">{ai_recommendation}</p>
        </div>"""

    # Bloco de valor atual vs threshold
    value_block = ""
    if metric and trigger_value not in ("", "—"):
        value_block = f"""
        <div style="display:flex;gap:20px;margin:16px 0;">
          <div style="flex:1;background:#0a1e17;border-radius:8px;padding:14px;text-align:center;border:1px solid #1e3a2e;">
            <p style="color:#6b8c7a;font-size:11px;margin:0 0 4px;letter-spacing:0.1em;">VALOR ATUAL</p>
            <p style="color:{color};font-size:24px;font-weight:700;font-family:monospace;margin:0;">
              {trigger_value}{metric_unit}
            </p>
            <p style="color:#6b8c7a;font-size:11px;margin:4px 0 0;">{metric_label}</p>
          </div>
          <div style="flex:1;background:#0a1e17;border-radius:8px;padding:14px;text-align:center;border:1px solid #1e3a2e;">
            <p style="color:#6b8c7a;font-size:11px;margin:0 0 4px;letter-spacing:0.1em;">THRESHOLD</p>
            <p style="color:#6b8c7a;font-size:24px;font-weight:700;font-family:monospace;margin:0;">
              {threshold}{metric_unit}
            </p>
            <p style="color:#6b8c7a;font-size:11px;margin:4px 0 0;">Limite configurado</p>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{rule_name}</title>
</head>
<body style="margin:0;padding:0;background:#071D15;font-family:'Outfit',Arial,sans-serif;">
<div style="max-width:620px;margin:0 auto;padding:24px 16px;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#0B1A14 0%,#0E2B22 50%,#071D15 100%);
       border-radius:12px 12px 0 0;padding:32px;border-bottom:1px solid {color}40;">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
      <div style="background:{color}22;border:1px solid {color};border-radius:8px;padding:8px 14px;
           color:{color};font-size:11px;font-weight:700;letter-spacing:0.15em;">
        {category_label.upper()}
      </div>
    </div>
    <h1 style="color:#fff;font-size:22px;font-weight:700;margin:0 0 6px;letter-spacing:0.05em;">
      {rule_name}
    </h1>
    <p style="color:rgba(255,255,255,0.6);font-size:14px;margin:0 0 16px;">{rule_description or "Condição de alerta detectada"}</p>
    <div style="display:flex;gap:12px;flex-wrap:wrap;">
      <span style="background:rgba(201,139,42,0.15);border:1px solid #C98B2A;border-radius:6px;
           padding:4px 12px;color:#C98B2A;font-size:12px;font-family:monospace;">
        📋 {contrato}
      </span>
      <span style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:6px;
           padding:4px 12px;color:rgba(255,255,255,0.5);font-size:12px;">
        🕐 {generated_at}
      </span>
    </div>
  </div>

  <!-- Body -->
  <div style="background:#0d2319;padding:28px 32px;">

    {value_block}

    {doc_alertas_html}

    {ai_block}

    <!-- CTA -->
    <div style="text-align:center;margin:28px 0 0;">
      <a href="{app_url}/hub-operacoes"
         style="display:inline-block;background:linear-gradient(135deg,{color},{color}cc);
                color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;
                font-weight:700;font-size:14px;letter-spacing:0.05em;">
        VER NO DASHBOARD →
      </a>
    </div>
  </div>

  <!-- Footer -->
  <div style="background:#071D15;border-radius:0 0 12px 12px;padding:16px 32px;
       border-top:1px solid rgba(255,255,255,0.05);text-align:center;">
    <p style="color:rgba(255,255,255,0.3);font-size:11px;margin:0;">
      Bomtempo Dashboard · Alerta automático · Para configurar, acesse Alertas no painel
    </p>
  </div>

</div>
</body>
</html>"""


def _send_via_smtp(recipients: List[str], subject: str, html_body: str) -> bool:
    """Envia via SMTP reutilizando a configuração existente do projeto."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = Config.RDO_EMAIL_USER
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(Config.RDO_SMTP_SERVER, Config.RDO_SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(Config.RDO_EMAIL_USER, Config.RDO_EMAIL_PASSWORD)
            server.sendmail(Config.RDO_EMAIL_USER, recipients, msg.as_string())
        return True
    except Exception as exc:
        logger.error(f"[AlertEmailService] SMTP error: {exc}")
        return False


class AlertEmailService:
    """Serviço de envio de emails ricos de alerta."""

    @staticmethod
    def send_alert_email(recipients: List[str], data: Dict[str, Any]) -> bool:
        """
        Monta e envia o email de alerta.
        Gera recomendação IA em background antes de enviar.
        """
        if not recipients:
            return False

        # Gera recomendação IA (best-effort, não bloqueia envio)
        ai_rec = ""
        try:
            trigger_config = data.get("trigger_config") or {}
            if trigger_config.get("metric"):
                ai_rec = _get_ai_recommendation(
                    rule_name=data.get("rule_name", ""),
                    contrato=data.get("contrato", ""),
                    trigger_value=data.get("trigger_value", ""),
                    trigger_config=trigger_config,
                )
        except Exception:
            pass

        html_body = _build_html(data, ai_rec)
        subject = f"[Bomtempo] {data.get('rule_name', 'Alerta')} — {data.get('contrato', '')}"
        ok = _send_via_smtp(recipients, subject, html_body)
        if ok:
            logger.info(f"[AlertEmailService] ✅ Email enviado para {len(recipients)} destinatários")
        return ok
