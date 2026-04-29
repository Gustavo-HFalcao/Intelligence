"""
Email Integration — Gmail SMTP.
Usado por: reset de senha, alertas proativos, RDO executivo.
Config: GMAIL_USER, GMAIL_APP_PASSWORD (App Password, não senha normal).
"""

import os
import re
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional, Any

from backend.core.logging import get_logger

logger = get_logger(__name__)

GMAIL_USER     = os.getenv("GMAIL_USER") or os.getenv("RDO_EMAIL_USER", "")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("RDO_EMAIL_PASSWORD", "")
FROM_NAME      = os.getenv("EMAIL_FROM_NAME", "Bomtempo Intelligence")
SMTP_HOST      = "smtp.gmail.com"
SMTP_PORT      = 587

COPPER = "#C98B2A"
TEAL   = "#2A9D8F"
RED    = "#EF4444"
BG     = "#081210"


def _smtp_send(msg: MIMEMultipart) -> bool:
    """Envia mensagem MIME via Gmail SMTP. Retorna True se bem-sucedido."""
    if not GMAIL_USER or not GMAIL_PASSWORD:
        logger.warning("GMAIL_USER / GMAIL_APP_PASSWORD não configurados — email não enviado")
        return False
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email enviado: {msg.get('Subject', '')[:80]} → {msg.get('To', '')}")
        return True
    except Exception as e:
        logger.error(f"Falha ao enviar email: {e}")
        return False


def send_email(
    to: List[str],
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """Envia email simples (sem anexos)."""
    if not to:
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{FROM_NAME} <{GMAIL_USER}>"
    msg["To"]      = ", ".join(to)
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return _smtp_send(msg)


def _md_to_html(text: str) -> str:
    """Converte markdown simples para HTML (sem dependência de biblioteca)."""
    if not text:
        return ""
    lines = text.split("\n")
    out = []
    for line in lines:
        # Headers
        if line.startswith("### "):
            out.append(f'<h4 style="margin:8px 0 4px;color:{TEAL};font-size:12px">{line[4:]}</h4>')
        elif line.startswith("## "):
            out.append(f'<h3 style="margin:10px 0 4px;color:{COPPER};font-size:13px">{line[3:]}</h3>')
        elif line.startswith("# "):
            out.append(f'<h2 style="margin:12px 0 6px;color:{COPPER};font-size:14px">{line[2:]}</h2>')
        # Bold
        elif re.match(r"^\*\*(.+)\*\*$", line.strip()):
            out.append(f'<p style="margin:4px 0;font-weight:700;color:#e2c87a">{line.strip()[2:-2]}</p>')
        # Bullet list
        elif line.startswith("- ") or line.startswith("* "):
            out.append(f'<li style="margin:3px 0;color:#ccc;font-size:12px">{line[2:]}</li>')
        elif line.strip() == "":
            out.append('<br>')
        else:
            # inline bold
            processed = re.sub(r"\*\*(.+?)\*\*", r'<strong>\1</strong>', line)
            out.append(f'<p style="margin:4px 0;font-size:12px;color:#ccc;line-height:1.6">{processed}</p>')
    return "\n".join(out)


def _esc(v: Any) -> str:
    import html
    return html.escape(str(v or ""))


# ── Templates ─────────────────────────────────────────────────────────────────

def send_reset_password(to_email: str, reset_token: str, base_url: str = "") -> bool:
    reset_url = f"{base_url}/reset-password?token={reset_token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
      <h2 style="color:{COPPER}">Redefinição de Senha — Bomtempo Intelligence</h2>
      <p>Você solicitou a redefinição de senha. Clique no link abaixo:</p>
      <a href="{reset_url}" style="display:inline-block;margin:16px 0;padding:12px 24px;background:{COPPER};color:#fff;text-decoration:none;border-radius:8px;font-weight:bold">
        Redefinir Senha
      </a>
      <p style="color:#888;font-size:12px">Link válido por 1 hora. Se não foi você, ignore este email.</p>
    </div>
    """
    return send_email([to_email], "Redefinição de Senha — Bomtempo", html)


def send_alert_notification(to_emails: List[str], alert_type: str, alert_label: str, contrato: str, message: str) -> bool:
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:32px">
      <div style="border-left:4px solid {COPPER};padding-left:16px;margin-bottom:24px">
        <h2 style="color:{COPPER};margin:0">{_esc(alert_label)}</h2>
        <p style="color:#888;margin:4px 0">Contrato: <strong>{_esc(contrato)}</strong></p>
      </div>
      <p>{_esc(message)}</p>
      <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
      <p style="color:#aaa;font-size:11px">Bomtempo Intelligence · Alerta automático</p>
    </div>
    """
    return send_email(to_emails, f"[Alerta] {alert_label} — {contrato}", html)


def send_rdo_submitted(to_emails: List[str], contrato: str, data: str, view_token: str, base_url: str = "") -> bool:
    """Compatibilidade retroativa — redireciona para send_rdo_executivo sem dados extras."""
    view_url = f"{base_url}/rdo/{view_token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:32px;background:#0d1117;color:#e2c87a">
      <h2 style="color:{COPPER}">RDO Submetido — {_esc(contrato)}</h2>
      <p style="color:#ccc">O Relatório Diário de Obra de <strong>{_esc(data)}</strong> foi submetido com sucesso.</p>
      <a href="{view_url}" style="display:inline-block;margin:16px 0;padding:12px 24px;background:{TEAL};color:#fff;text-decoration:none;border-radius:8px;font-weight:bold">
        Visualizar RDO Online
      </a>
      <p style="color:#555;font-size:11px">Bomtempo Intelligence</p>
    </div>
    """
    return send_email(to_emails, f"RDO Submetido — {contrato} · {data}", html)


def send_rdo_executivo(
    to_emails: List[str],
    rdo: Dict[str, Any],
    atividades: List[Dict[str, Any]],
    ai_summary: str = "",
    view_url: str = "",
    pdf_path: str = "",
) -> bool:
    """
    Email executivo RDO — KPIs, tabela de atividades, alertas, análise IA, link online, PDF anexo.
    Fiel ao template do projeto Reflex original (EmailService.send_rdo2_email).
    """
    if not to_emails:
        return False

    contrato    = _esc(rdo.get("contrato") or "—")
    data_rdo    = _esc(str(rdo.get("data") or rdo.get("data_rdo") or "—")[:10])
    projeto     = _esc(rdo.get("projeto") or "—")
    cliente     = _esc(rdo.get("cliente") or "—")
    localizacao = _esc(rdo.get("localizacao") or "—")
    clima       = _esc(rdo.get("condicao_climatica") or rdo.get("clima") or "—")
    turno       = _esc(rdo.get("turno") or "—")
    hora_i      = _esc(str(rdo.get("hora_inicio") or "")[:5])
    hora_f      = _esc(str(rdo.get("hora_termino") or "")[:5])
    equipe_tot  = int(rdo.get("equipe_alocada") or 0)
    observacoes = _esc(rdo.get("observacoes") or "")
    orientacao  = _esc(rdo.get("orientacao") or "")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    n_ativs = len(atividades)
    n_conc  = sum(
        1 for a in atividades
        if (bool(a.get("marco_concluido")) and bool(a.get("is_marco")))
        or int(a.get("quantidade") or 0) >= 100
        or str(a.get("observacao") or "").lower() in ("concluída", "concluido", "concluída", "100%")
    )
    prod_pct   = round(n_conc / n_ativs * 100) if n_ativs else 0
    prod_color = TEAL if prod_pct >= 80 else COPPER if prod_pct >= 50 else RED
    prod_label = "Produtivo" if prod_pct >= 80 else "Parcial" if prod_pct >= 50 else "Abaixo do esperado"

    kpi_card = lambda emoji, val, lbl, color: f"""
      <td style="width:33%;padding:12px 8px;text-align:center;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:8px">
        <div style="font-size:20px;margin-bottom:4px">{emoji}</div>
        <div style="font-size:26px;font-weight:800;color:{color};line-height:1">{val}</div>
        <div style="font-size:10px;color:#667788;text-transform:uppercase;letter-spacing:.08em;margin-top:4px">{lbl}</div>
      </td>"""

    kpi_html = f"""
    <table style="width:100%;border-collapse:separate;border-spacing:8px">
      <tr>
        {kpi_card('👷', equipe_tot, 'Pessoas em Campo', COPPER)}
        {kpi_card('📋', n_ativs, 'Atividades', TEAL)}
        {kpi_card('✅', f'{prod_pct}%', f'Dia {prod_label}', prod_color)}
      </tr>
    </table>"""

    # ── Info rápida (clima / turno / horário) ─────────────────────────────────
    info_cells = ""
    if clima and clima != "—":
        icon = "⛅" if "nub" in clima.lower() else "🌧️" if "chuv" in clima.lower() or "temp" in clima.lower() else "☀️"
        info_cells += f'<td style="padding:8px 14px;color:#aaa;font-size:12px;white-space:nowrap">{icon} {clima}</td>'
    if hora_i or hora_f:
        info_cells += f'<td style="padding:8px 14px;color:#aaa;font-size:12px;white-space:nowrap">⏱️ {hora_i}–{hora_f}</td>'
    if turno and turno != "—":
        info_cells += f'<td style="padding:8px 14px;color:#aaa;font-size:12px;white-space:nowrap">🔄 Turno {turno}</td>'
    if localizacao and localizacao != "—":
        info_cells += f'<td style="padding:8px 14px;color:#aaa;font-size:12px;white-space:nowrap">📍 {localizacao}</td>'
    info_row = f'<table style="width:100%;border-collapse:collapse"><tr>{info_cells}</tr></table>' if info_cells else ""

    # ── Alertas ───────────────────────────────────────────────────────────────
    alertas_html = ""
    if rdo.get("houve_interrupcao"):
        mot = _esc(rdo.get("motivo_interrupcao") or "Não especificado")
        alertas_html += f'<div style="background:rgba(239,68,68,.07);border:1px solid rgba(239,68,68,.25);border-radius:8px;padding:10px 14px;margin-bottom:8px"><span style="color:{RED};font-weight:700;font-size:11px">⏸️ INTERRUPÇÃO</span><p style="margin:4px 0 0;color:#ccc;font-size:12px">{mot}</p></div>'
    if rdo.get("houve_chuva"):
        qty = _esc(rdo.get("quantidade_chuva") or "")
        alertas_html += f'<div style="background:rgba(59,130,246,.07);border:1px solid rgba(59,130,246,.2);border-radius:8px;padding:10px 14px;margin-bottom:8px"><span style="color:#3B82F6;font-weight:700;font-size:11px">🌧️ CHUVA REGISTRADA</span>{f"""<p style="margin:4px 0 0;color:#ccc;font-size:12px">{qty}</p>""" if qty else ""}</div>'
    if rdo.get("houve_acidente"):
        desc = _esc(rdo.get("descricao_acidente") or "")
        alertas_html += f'<div style="background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.4);border-radius:8px;padding:10px 14px;margin-bottom:8px"><span style="color:{RED};font-weight:700;font-size:11px">🚨 ACIDENTE REGISTRADO</span>{f"""<p style="margin:4px 0 0;color:#ccc;font-size:12px">{desc}</p>""" if desc else ""}</div>'

    # ── Tabela de atividades ──────────────────────────────────────────────────
    at_rows = ""
    for at in atividades:
        nome     = _esc(at.get("atividade") or at.get("descricao") or "—")
        unidade  = str(at.get("unidade") or "")
        qty      = at.get("quantidade") or 0
        efet     = int(at.get("efetivo") or 0)
        is_marco = bool(at.get("is_marco"))
        marco_c  = bool(at.get("marco_concluido"))
        obs_val  = str(at.get("observacao") or "")

        if is_marco:
            prog_str = "✓ Concluído" if marco_c else "Pendente"
            prog_color = TEAL if marco_c else COPPER
            badge_txt = "MARCO"
            badge_bg  = f"{COPPER}22"
            badge_color = COPPER
        elif unidade == "%":
            pct_val = int(float(qty))
            prog_str = f"{pct_val}%"
            prog_color = TEAL if pct_val >= 80 else COPPER if pct_val >= 40 else RED
            badge_txt = obs_val or "Em andamento"
            badge_bg  = f"{prog_color}18"
            badge_color = prog_color
        else:
            prog_str = f"{qty} {unidade}"
            prog_color = TEAL
            badge_txt = obs_val or "Executado"
            badge_bg  = f"{TEAL}18"
            badge_color = TEAL

        efet_str = f'<span style="color:#667788;font-size:10px">{efet}p</span>' if efet else ""

        at_rows += f"""
        <tr>
          <td style="padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.05);color:#e2c87a;font-size:12px">{nome}</td>
          <td style="padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.05);text-align:center">
            <span style="background:{badge_bg};color:{badge_color};padding:2px 7px;border-radius:10px;font-size:10px;font-weight:700;white-space:nowrap">{_esc(badge_txt)}</span>
          </td>
          <td style="padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.05);text-align:right;font-weight:700;color:{prog_color};font-size:13px">{_esc(prog_str)}</td>
          <td style="padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.05);text-align:center">{efet_str}</td>
        </tr>"""

    if not at_rows:
        at_rows = '<tr><td colspan="4" style="padding:12px;color:#555;text-align:center;font-size:12px">Nenhuma atividade registrada</td></tr>'

    ativ_table = f"""
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead>
        <tr style="background:rgba(201,139,42,.1)">
          <th style="padding:7px 10px;text-align:left;color:{COPPER};font-size:10px;text-transform:uppercase;letter-spacing:.08em;font-weight:700">Atividade</th>
          <th style="padding:7px 10px;text-align:center;color:{COPPER};font-size:10px;text-transform:uppercase;letter-spacing:.08em;font-weight:700">Status</th>
          <th style="padding:7px 10px;text-align:right;color:{COPPER};font-size:10px;text-transform:uppercase;letter-spacing:.08em;font-weight:700">Progresso</th>
          <th style="padding:7px 10px;text-align:center;color:{COPPER};font-size:10px;text-transform:uppercase;letter-spacing:.08em;font-weight:700">Efetivo</th>
        </tr>
      </thead>
      <tbody>{at_rows}</tbody>
    </table>"""

    # ── Observações e orientação ──────────────────────────────────────────────
    obs_section = ""
    if observacoes:
        obs_section = f"""
        <div style="background:rgba(255,255,255,.03);border-left:3px solid {COPPER};padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:16px">
          <div style="font-size:10px;color:#667788;text-transform:uppercase;letter-spacing:.12em;margin-bottom:6px">Observações do dia</div>
          <p style="font-size:12px;color:#ccc;line-height:1.7;margin:0">{observacoes}</p>
        </div>"""
    orient_section = ""
    if orientacao:
        orient_section = f"""
        <div style="background:rgba(42,157,143,.05);border-left:3px solid {TEAL};padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:16px">
          <div style="font-size:10px;color:#667788;text-transform:uppercase;letter-spacing:.12em;margin-bottom:6px">🔭 Orientação para amanhã</div>
          <p style="font-size:12px;color:#ccc;line-height:1.7;margin:0">{orientacao}</p>
        </div>"""

    # ── Análise IA ────────────────────────────────────────────────────────────
    ai_section = ""
    if ai_summary:
        ai_html = _md_to_html(ai_summary)
        ai_section = f"""
        <div style="background:rgba(42,157,143,.05);border:1px solid rgba(42,157,143,.2);border-radius:10px;padding:16px 18px;margin-bottom:16px">
          <div style="font-size:10px;color:{TEAL};text-transform:uppercase;letter-spacing:.15em;font-weight:800;margin-bottom:10px">🤖 Análise BOMTEMPO Intelligence</div>
          <div style="font-size:12px;color:#bbb;line-height:1.7">{ai_html}</div>
        </div>"""

    # ── CTA: botão View Online ────────────────────────────────────────────────
    cta_html = ""
    if view_url:
        cta_html = f"""
        <div style="text-align:center;margin:24px 0 16px">
          <a href="{view_url}" style="display:inline-block;padding:13px 32px;background:linear-gradient(135deg,{COPPER},{TEAL});color:#fff;text-decoration:none;border-radius:8px;font-weight:800;font-size:13px;letter-spacing:.05em">
            Ver RDO Completo Online →
          </a>
        </div>"""
        if pdf_path and Path(pdf_path).exists():
            cta_html += f'<p style="text-align:center;font-size:11px;color:#555;margin:6px 0">📎 PDF do RDO anexado a este email</p>'

    # ── Resumo do dia (intro) ─────────────────────────────────────────────────
    resumo = (
        f"Hoje o contrato <strong style='color:{COPPER}'>{contrato}</strong> registrou "
        f"<strong>{equipe_tot}</strong> profissional(is) em campo com "
        f"<strong>{n_ativs}</strong> atividade(s) executada(s)."
    )
    if n_conc:
        resumo += f" <strong style='color:{TEAL}'>{n_conc} atividade(s) concluída(s)</strong>."

    # ── HTML final ────────────────────────────────────────────────────────────
    html_body = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0a0e13;font-family:'Segoe UI',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0e13;padding:24px 12px">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;background:#0d1117;border-radius:14px;overflow:hidden;border:1px solid rgba(201,139,42,.18)">

  <!-- HEADER -->
  <tr><td style="background:linear-gradient(135deg,#1a0e02,#0d1117 40%,#061a14);padding:28px 32px 20px">
    <div style="font-size:11px;color:#667788;text-transform:uppercase;letter-spacing:.25em;margin-bottom:6px">Bomtempo Intelligence</div>
    <div style="font-size:22px;font-weight:800;color:#e2c87a;letter-spacing:.04em">Relatório Diário de Obra</div>
    <div style="font-size:13px;color:#667788;margin-top:6px">{contrato} · {data_rdo}</div>
    <div style="margin-top:10px;display:inline-block;font-size:11px;background:rgba(201,139,42,.15);color:{COPPER};border:1px solid rgba(201,139,42,.3);padding:3px 10px;border-radius:5px;font-weight:700">
      {projeto} · {cliente}
    </div>
  </td></tr>

  <!-- RESUMO -->
  <tr><td style="padding:20px 32px 8px">
    <p style="font-size:13px;color:#ccc;line-height:1.7;margin:0">{resumo}</p>
  </td></tr>

  <!-- KPIs -->
  <tr><td style="padding:12px 32px 16px">{kpi_html}</td></tr>

  <!-- INFO BAR -->
  {'<tr><td style="padding:4px 32px 16px">' + info_row + '</td></tr>' if info_row else ''}

  <!-- ALERTAS -->
  {'<tr><td style="padding:0 32px 8px">' + alertas_html + '</td></tr>' if alertas_html else ''}

  <!-- ATIVIDADES -->
  <tr><td style="padding:8px 32px 16px">
    <div style="font-size:10px;color:#667788;text-transform:uppercase;letter-spacing:.18em;font-weight:700;margin-bottom:10px">Atividades Executadas</div>
    {ativ_table}
  </td></tr>

  <!-- OBS E ORIENTAÇÃO -->
  {'<tr><td style="padding:0 32px 8px">' + obs_section + orient_section + '</td></tr>' if obs_section or orient_section else ''}

  <!-- ANÁLISE IA -->
  {'<tr><td style="padding:0 32px 8px">' + ai_section + '</td></tr>' if ai_section else ''}

  <!-- CTA -->
  {'<tr><td style="padding:0 32px 24px">' + cta_html + '</td></tr>' if cta_html else ''}

  <!-- FOOTER -->
  <tr><td style="background:#030504;padding:16px 32px;text-align:center">
    <p style="font-size:10px;color:#333;margin:0">Bomtempo Intelligence · Relatório gerado automaticamente · Não responda este email</p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    # ── Monta MIME com anexo opcional ─────────────────────────────────────────
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"📋 RDO | {contrato} | {data_rdo} | {prod_label} | Bomtempo"
    msg["From"]    = f"{FROM_NAME} <{GMAIL_USER}>"
    msg["To"]      = ", ".join(to_emails)

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    if pdf_path:
        try:
            p = Path(pdf_path)
            if p.exists():
                with open(p, "rb") as f:
                    att = MIMEApplication(f.read(), _subtype="pdf")
                    att.add_header("Content-Disposition", "attachment", filename=p.name)
                    msg.attach(att)
        except Exception as e:
            logger.warning(f"PDF anexo falhou: {e}")

    return _smtp_send(msg)
