"""
Email Service - Envio SMTP com anexos e HTML formatado
"""

import re
import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List

from bomtempo.core.config import Config
from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)


def _generate_personalized_intro(
    doc_label: str,
    recipient_name: str = "",
    sender_name: str = "",
    context_hint: str = "",
) -> str:
    """
    Gera um parágrafo de abertura personalizado para o email via LLM.
    Retorna string vazia em caso de falha (email segue com template padrão).
    Máximo 2 frases, tom profissional e direto.
    """
    try:
        from bomtempo.core.ai_client import ai_client
        recipient_part = f"para {recipient_name}" if recipient_name else ""
        sender_part = f"enviado por {sender_name}" if sender_name else ""
        extra = f"\nContexto adicional: {context_hint}" if context_hint else ""
        prompt = (
            f"Escreva exatamente 1 ou 2 frases de abertura personalizadas para um email profissional "
            f"enviando o documento '{doc_label}' {recipient_part} {sender_part}. "
            f"Tom: profissional, objetivo, caloroso. Não mencione IA. "
            f"Responda APENAS o texto do parágrafo, sem saudação, sem aspas.{extra}"
        )
        result = ai_client.query([{"role": "user", "content": prompt}])
        return (result or "").strip()[:500]
    except Exception as e:
        logger.warning(f"[PersonalizedEmail] Falha ao gerar intro: {e}")
        return ""


def _md_to_html(text: str) -> str:
    """Converte Markdown simples para HTML formatado"""
    if not text:
        return ""

    lines = text.split("\n")
    html_lines = []
    in_ul = False

    for line in lines:
        # Headings
        if line.startswith("## "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            content = line[3:].strip()
            html_lines.append(
                f'<h3 style="color:#C98B2A;margin-top:20px;margin-bottom:8px;font-size:15px;border-bottom:1px solid rgba(201,139,42,0.3);padding-bottom:6px;">{content}</h3>'
            )
        elif line.startswith("# "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            content = line[2:].strip()
            html_lines.append(f'<h2 style="color:#C98B2A;margin-top:24px;">{content}</h2>')
        # List items
        elif line.startswith("- ") or line.startswith("* "):
            if not in_ul:
                html_lines.append('<ul style="margin:8px 0;padding-left:20px;">')
                in_ul = True
            content = line[2:].strip()
            # Bold dentro do item
            content = re.sub(
                r"\*\*(.+?)\*\*", r'<strong style="color:#E0E0E0;">\1</strong>', content
            )
            html_lines.append(f'<li style="margin:4px 0;color:#C8D8D4;">{content}</li>')
        # Numbered list
        elif re.match(r"^\d+\.\s", line):
            if not in_ul:
                html_lines.append('<ol style="margin:8px 0;padding-left:20px;">')
                in_ul = True
            content = re.sub(r"^\d+\.\s", "", line).strip()
            content = re.sub(
                r"\*\*(.+?)\*\*", r'<strong style="color:#E0E0E0;">\1</strong>', content
            )
            html_lines.append(f'<li style="margin:4px 0;color:#C8D8D4;">{content}</li>')
        # Empty line
        elif line.strip() == "":
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append("<br>")
        # Normal paragraph
        else:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            content = line.strip()
            # Bold
            content = re.sub(
                r"\*\*(.+?)\*\*", r'<strong style="color:#E0E0E0;">\1</strong>', content
            )
            if content:
                html_lines.append(f'<p style="margin:6px 0;color:#C8D8D4;">{content}</p>')

    if in_ul:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def _build_data_table(rdo_data: dict) -> str:
    """Gera tabela HTML com os dados principais do RDO"""
    rows = [
        ("Data", rdo_data.get("data", "—")),
        ("Contrato", rdo_data.get("contrato", "—")),
        ("Projeto", rdo_data.get("projeto", "—") or "—"),
        ("Cliente", rdo_data.get("cliente", "—") or "—"),
        ("Localização", rdo_data.get("localizacao", "—") or "—"),
        ("Condição Climática", rdo_data.get("clima", "—")),
        ("Turno", rdo_data.get("turno", "—")),
        ("Horário", f"{rdo_data.get('hora_inicio','—')} → {rdo_data.get('hora_termino','—')}"),
        ("Mão de Obra", f"{len(rdo_data.get('mao_obra', []))} profissional(is)"),
        ("Equipamentos", f"{len(rdo_data.get('equipamentos', []))} unidade(s)"),
        ("Atividades", f"{len(rdo_data.get('atividades', []))} atividade(s)"),
        ("Houve Interrupção", "Sim" if rdo_data.get("houve_interrupcao") else "Não"),
    ]

    table_rows = ""
    for i, (label, value) in enumerate(rows):
        bg = "rgba(201,139,42,0.05)" if i % 2 == 0 else "transparent"
        table_rows += f"""
        <tr style="background:{bg};">
            <td style="padding:10px 14px;font-weight:600;color:#889999;font-size:13px;width:40%;border-bottom:1px solid rgba(255,255,255,0.05);">{label}</td>
            <td style="padding:10px 14px;color:#E0E0E0;font-size:13px;border-bottom:1px solid rgba(255,255,255,0.05);">{value}</td>
        </tr>"""

    return f"""
    <table style="width:100%;border-collapse:collapse;border-radius:8px;overflow:hidden;">
        <thead>
            <tr style="background:rgba(201,139,42,0.15);">
                <th colspan="2" style="padding:12px 14px;text-align:left;color:#C98B2A;font-size:13px;text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid rgba(201,139,42,0.3);">
                    📋 Dados do Relatório
                </th>
            </tr>
        </thead>
        <tbody>{table_rows}</tbody>
    </table>"""


class EmailService:
    """Serviço de envio de emails via SMTP"""

    @staticmethod
    def send_rdo_email(
        recipients: List[str], rdo_data: dict, pdf_path: str, ai_insights: str
    ) -> bool:
        """
        Envia RDO por email com PDF anexo + análise IA formatada

        Args:
            recipients: Lista de emails destinatários
            rdo_data: Dados do RDO
            pdf_path: Caminho do PDF a anexar
            ai_insights: Análise IA em markdown

        Returns:
            True se enviado com sucesso
        """
        try:
            if not recipients:
                logger.warning("Nenhum destinatário fornecido")
                return False

            if not Config.RDO_EMAIL_PASSWORD:
                logger.error("❌ RDO_EMAIL_PASSWORD não configurado no .env")
                return False

            if not Path(pdf_path).exists():
                logger.error(f"❌ PDF não encontrado: {pdf_path}")
                return False

            msg = MIMEMultipart("alternative")
            msg["From"] = Config.RDO_EMAIL_USER
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = (
                f"📋 RDO | {rdo_data.get('contrato','?')} | "
                f"{rdo_data.get('data','?')} | BOMTEMPO Engenharia"
            )

            data_table = _build_data_table(rdo_data)
            ai_html = _md_to_html(ai_insights)

            contrato = rdo_data.get("contrato", "N/A")
            data_rdo = rdo_data.get("data", "N/A")
            observacoes = (
                rdo_data.get("observacoes", "").strip() or "Nenhuma observação registrada."
            )

            body_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#030504;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#030504;">
  <tr>
    <td align="center" style="padding:32px 16px;">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#0e1a17;border-radius:16px;overflow:hidden;border:1px solid rgba(201,139,42,0.2);">

        <!-- HEADER -->
        <tr>
          <td style="background:linear-gradient(135deg,#1a0e00 0%,#C98B2A 50%,#2A9D8F 100%);padding:32px 32px 24px;text-align:center;">
            <p style="margin:0 0 4px;color:rgba(255,255,255,0.7);font-size:11px;letter-spacing:0.15em;text-transform:uppercase;">BOMTEMPO INTELLIGENCE</p>
            <h1 style="margin:0 0 8px;color:#fff;font-size:22px;font-weight:700;letter-spacing:0.02em;">Relatório Diário de Obra</h1>
            <p style="margin:0;background:rgba(0,0,0,0.25);display:inline-block;padding:6px 16px;border-radius:20px;color:#fff;font-size:14px;">
              {contrato} &nbsp;·&nbsp; {data_rdo}
            </p>
          </td>
        </tr>

        <!-- INTRO -->
        <tr>
          <td style="padding:28px 32px 0;">
            <p style="margin:0 0 12px;color:#C8D8D4;font-size:14px;line-height:1.7;">
              Olá! Segue abaixo o <strong style="color:#E0E0E0;">Relatório Diário de Obra</strong> referente ao contrato
              <strong style="color:#C98B2A;">{contrato}</strong> do dia <strong style="color:#C98B2A;">{data_rdo}</strong>.
              O relatório completo em PDF está anexado a este email para registro e archivamento.
            </p>
          </td>
        </tr>

        <!-- TABELA DE DADOS -->
        <tr>
          <td style="padding:20px 32px;">
            {data_table}
          </td>
        </tr>

        <!-- OBSERVAÇÕES (se houver) -->
        {'<tr><td style="padding:0 32px 20px;"><div style="background:rgba(42,157,143,0.08);border-left:3px solid #2A9D8F;padding:14px 18px;border-radius:0 8px 8px 0;"><p style="margin:0 0 6px;color:#2A9D8F;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">📝 Observações do Dia</p><p style="margin:0;color:#C8D8D4;font-size:13px;line-height:1.6;">' + observacoes + '</p></div></td></tr>' if observacoes and observacoes != "Nenhuma observação registrada." else ''}

        <!-- DIVISOR IA -->
        <tr>
          <td style="padding:0 32px;">
            <div style="border-top:1px solid rgba(42,157,143,0.2);margin:8px 0;"></div>
          </td>
        </tr>

        <!-- ANÁLISE IA -->
        <tr>
          <td style="padding:20px 32px 28px;">
            <div style="background:rgba(42,157,143,0.05);border:1px solid rgba(42,157,143,0.15);border-radius:12px;padding:24px;">
              <div style="display:flex;align-items:center;margin-bottom:16px;">
                <span style="font-size:20px;margin-right:10px;">🤖</span>
                <div>
                  <p style="margin:0;color:#2A9D8F;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">Análise Automatizada · BOMTEMPO Intelligence</p>
                  <p style="margin:0;color:#889999;font-size:11px;">Gerada por IA com base nos dados deste RDO</p>
                </div>
              </div>
              <div style="color:#C8D8D4;font-size:13px;line-height:1.7;">
                {ai_html}
              </div>
            </div>
          </td>
        </tr>

        <!-- ANEXO INFO -->
        <tr>
          <td style="padding:0 32px 28px;">
            <div style="background:rgba(201,139,42,0.06);border:1px solid rgba(201,139,42,0.15);border-radius:8px;padding:14px 18px;">
              <p style="margin:0;color:#C98B2A;font-size:13px;">
                <strong>📎 Anexo:</strong>&nbsp; O PDF completo do RDO está anexado a este email.
              </p>
            </div>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:#081210;padding:20px 32px;text-align:center;border-top:1px solid rgba(255,255,255,0.06);">
            <p style="margin:0 0 4px;color:#889999;font-size:12px;">🚀 Gerado automaticamente pelo <strong style="color:#C98B2A;">BOMTEMPO Dashboard</strong></p>
            <p style="margin:0;color:#4a5a58;font-size:11px;">Este é um email automático — não responda diretamente.</p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

            msg.attach(MIMEText(body_html, "html", "utf-8"))

            # Anexar PDF
            pdf_filename = Path(pdf_path).name
            with open(pdf_path, "rb") as f:
                pdf_attach = MIMEApplication(f.read(), _subtype="pdf")
                pdf_attach.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=pdf_filename,
                )
                msg.attach(pdf_attach)

            logger.info(f"Conectando ao SMTP: {Config.RDO_SMTP_SERVER}:{Config.RDO_SMTP_PORT}")

            with smtplib.SMTP(Config.RDO_SMTP_SERVER, Config.RDO_SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(Config.RDO_EMAIL_USER, Config.RDO_EMAIL_PASSWORD)
                server.send_message(msg)

            logger.info(
                f"✅ Email enviado para {len(recipients)} destinatário(s): {', '.join(recipients)}"
            )
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("❌ Falha de autenticação SMTP. Verifique RDO_EMAIL_PASSWORD no .env")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ Erro SMTP: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao enviar email: {e}")
            return False

    @staticmethod
    def send_reembolso_email(
        recipients: List[str],
        data: dict,
        pdf_path: str,
    ) -> bool:
        """
        Envia notificação de reembolso de combustível por email.
        PDF anexado se disponível. Padrão visual idêntico ao send_rdo_email.
        """
        try:
            if not recipients:
                logger.warning("Nenhum destinatário fornecido para reembolso email")
                return False

            if not Config.RDO_EMAIL_PASSWORD:
                logger.error("❌ RDO_EMAIL_PASSWORD não configurado no .env")
                return False

            submitted_by = str(data.get("submitted_by", "—") or "—")
            combustivel = str(data.get("combustivel", "—") or "—")
            valor_total = str(data.get("valor_total", "—") or "—")
            data_abast = str(data.get("data_abastecimento", "—") or "—")
            cidade = str(data.get("cidade", "—") or "—")
            estado = str(data.get("estado", "—") or "—")
            finalidade = str(data.get("finalidade", "—") or "—")
            litros = str(data.get("litros", "—") or "—")
            rota = str(data.get("rota", "—") or "—")[:100]
            ai_verified = bool(data.get("ai_verified", False))
            ai_insight = str(data.get("ai_insight_text", "") or "")

            ai_badge = "✅ NF Verificada pela IA" if ai_verified else "⚠️ NF não verificada pela IA"
            ai_badge_color = "#27AE60" if ai_verified else "#C0392B"

            rows = [
                ("Solicitante", submitted_by),
                ("Combustível", combustivel),
                ("Litros", f"{litros}L"),
                ("Valor Total", f"R$ {valor_total}"),
                ("Data", data_abast),
                ("Cidade/Estado", f"{cidade}/{estado}"),
                ("Finalidade", finalidade),
                ("Rota", rota),
            ]
            table_rows_html = ""
            for i, (label, value) in enumerate(rows):
                bg = "rgba(201,139,42,0.05)" if i % 2 == 0 else "transparent"
                table_rows_html += (
                    f'<tr style="background:{bg};">'
                    f'<td style="padding:10px 14px;font-weight:600;color:#889999;font-size:13px;'
                    f'width:40%;border-bottom:1px solid rgba(255,255,255,0.05);">{label}</td>'
                    f'<td style="padding:10px 14px;color:#E0E0E0;font-size:13px;'
                    f'border-bottom:1px solid rgba(255,255,255,0.05);">{value}</td>'
                    f"</tr>"
                )

            pdf_exists = pdf_path and Path(pdf_path).exists()
            pdf_section = ""
            if pdf_exists:
                pdf_section = (
                    '<tr><td style="padding:0 32px 20px;">'
                    '<div style="background:rgba(201,139,42,0.06);border:1px solid rgba(201,139,42,0.15);'
                    'border-radius:8px;padding:14px 18px;">'
                    '<p style="margin:0;color:#C98B2A;font-size:13px;">'
                    "<strong>📎 Anexo:</strong>&nbsp;O comprovante PDF está anexado a este email.</p>"
                    "</div></td></tr>"
                )
            ai_section = ""
            if ai_insight:
                ai_section = (
                    '<tr><td style="padding:0 32px 20px;">'
                    '<div style="background:rgba(42,157,143,0.06);border:1px solid rgba(42,157,143,0.15);'
                    'border-radius:8px;padding:14px 18px;">'
                    '<p style="margin:0 0 6px;color:#2A9D8F;font-size:12px;font-weight:600;'
                    'text-transform:uppercase;letter-spacing:0.05em;">🤖 Análise IA</p>'
                    f'<p style="margin:0;color:#C8D8D4;font-size:13px;line-height:1.6;">{ai_insight}</p>'
                    "</div></td></tr>"
                )

            body_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#030504;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#030504;">
  <tr>
    <td align="center" style="padding:32px 16px;">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#0e1a17;border-radius:16px;overflow:hidden;border:1px solid rgba(201,139,42,0.2);">

        <tr>
          <td style="background:linear-gradient(135deg,#1a0e00 0%,#C98B2A 50%,#2A9D8F 100%);padding:32px 32px 24px;text-align:center;">
            <p style="margin:0 0 4px;color:rgba(255,255,255,0.7);font-size:11px;letter-spacing:0.15em;text-transform:uppercase;">BOMTEMPO INTELLIGENCE</p>
            <h1 style="margin:0 0 8px;color:#fff;font-size:22px;font-weight:700;">⛽ Reembolso de Combustível</h1>
            <p style="margin:0;background:rgba(0,0,0,0.25);display:inline-block;padding:6px 16px;border-radius:20px;color:#fff;font-size:14px;">
              {submitted_by} &nbsp;·&nbsp; {data_abast}
            </p>
          </td>
        </tr>

        <tr>
          <td style="padding:20px 32px 0;">
            <div style="background:{ai_badge_color}20;border:1px solid {ai_badge_color};border-radius:8px;padding:10px 16px;text-align:center;">
              <p style="margin:0;color:{ai_badge_color};font-size:13px;font-weight:600;">{ai_badge}</p>
            </div>
          </td>
        </tr>

        <tr>
          <td style="padding:20px 32px;">
            <table style="width:100%;border-collapse:collapse;border-radius:8px;overflow:hidden;">
              <thead>
                <tr style="background:rgba(201,139,42,0.15);">
                  <th colspan="2" style="padding:12px 14px;text-align:left;color:#C98B2A;font-size:13px;text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid rgba(201,139,42,0.3);">
                    ⛽ Dados do Abastecimento
                  </th>
                </tr>
              </thead>
              <tbody>{table_rows_html}</tbody>
            </table>
          </td>
        </tr>

        {ai_section}
        {pdf_section}

        <tr>
          <td style="background:#081210;padding:20px 32px;text-align:center;border-top:1px solid rgba(255,255,255,0.06);">
            <p style="margin:0 0 4px;color:#889999;font-size:12px;">🚀 Gerado automaticamente pelo <strong style="color:#C98B2A;">BOMTEMPO Dashboard</strong></p>
            <p style="margin:0;color:#4a5a58;font-size:11px;">Este é um email automático — não responda diretamente.</p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

            msg = MIMEMultipart("alternative")
            msg["From"] = Config.RDO_EMAIL_USER
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = f"⛽ Reembolso Combustível | {submitted_by} | {data_abast} | BOMTEMPO"

            msg.attach(MIMEText(body_html, "html", "utf-8"))

            if pdf_exists:
                pdf_filename = Path(pdf_path).name
                with open(pdf_path, "rb") as f:
                    pdf_attach = MIMEApplication(f.read(), _subtype="pdf")
                    pdf_attach.add_header(
                        "Content-Disposition", "attachment", filename=pdf_filename
                    )
                    msg.attach(pdf_attach)

            with smtplib.SMTP(Config.RDO_SMTP_SERVER, Config.RDO_SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(Config.RDO_EMAIL_USER, Config.RDO_EMAIL_PASSWORD)
                server.send_message(msg)

            logger.info(
                f"✅ Reembolso email enviado para {len(recipients)} destinatário(s): {', '.join(recipients)}"
            )
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("❌ Falha de autenticação SMTP para reembolso email")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao enviar email de reembolso: {e}")
            return False

    @staticmethod
    def send_alert_email(
        recipients: List[str],
        contract: str,
        alert_label: str,
        alert_color: str,
        obra_data: dict,
    ) -> bool:
        """
        Envia email de alerta proativo.

        Args:
            recipients: Lista de emails destinatários
            contract: Código do contrato
            alert_type: Chave do tipo de alerta (daily/weekly/risk_high/etc.)
            alert_label: Label legível do alerta
            alert_color: Cor hex do alerta
            obra_data: Dados da obra do Supabase

        Returns:
            True se enviado com sucesso
        """
        try:
            if not recipients:
                logger.warning("[AlertEmail] Nenhum destinatário.")
                return False
            if not Config.RDO_EMAIL_PASSWORD:
                logger.error("[AlertEmail] RDO_EMAIL_PASSWORD não configurado.")
                return False

            avanco = (obra_data.get("avanco_realizado_pct") or obra_data.get("realizado_pct") or
                      obra_data.get("Realizado (%)") or obra_data.get("avanco_fisico") or "—")
            risco_val = obra_data.get("risco_geral_score") or "—"
            budget_p = obra_data.get("budget_planejado") or "—"
            budget_r = obra_data.get("budget_realizado") or "—"
            projeto = obra_data.get("projeto") or "—"
            cliente = obra_data.get("cliente") or "—"
            localizacao = obra_data.get("localizacao") or "—"

            try:
                risco_num = float(str(risco_val).replace(",", "."))
                risco_color = "#EF4444" if risco_num >= 70 else "#F59E0B" if risco_num >= 40 else "#2A9D8F"
                risco_label = "ALTO" if risco_num >= 70 else "MODERADO" if risco_num >= 40 else "BAIXO"
            except (ValueError, TypeError):
                risco_color = "#889999"
                risco_label = str(risco_val)

            now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

            kpi_rows = ""
            kpis = [
                ("Projeto", projeto, "#E0E0E0"),
                ("Avanço Físico", f"{avanco}%" if avanco != "—" else "—", "#2A9D8F" if avanco != "—" else "#889999"),
                ("Score de Risco", f"{risco_val} — {risco_label}", risco_color),
                ("Budget Planejado", str(budget_p), "#C98B2A"),
                ("Budget Realizado", str(budget_r), "#E0E0E0"),
                ("Localização", str(localizacao), "#889999"),
            ]
            for i, (label, value, col) in enumerate(kpis):
                bg = "rgba(201,139,42,0.05)" if i % 2 == 0 else "transparent"
                kpi_rows += f"""
                <tr style="background:{bg};">
                  <td style="padding:10px 14px;font-weight:600;color:#A8BCC0;font-size:13px;width:42%;border-bottom:1px solid rgba(255,255,255,0.08);">{label}</td>
                  <td style="padding:10px 14px;color:{col};font-size:13px;font-weight:700;border-bottom:1px solid rgba(255,255,255,0.08);">{value}</td>
                </tr>"""

            body_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#030504;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#030504;">
  <tr>
    <td align="center" style="padding:32px 16px;">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#0e1a17;border-radius:16px;overflow:hidden;border:1px solid {alert_color}40;">

        <!-- HEADER -->
        <tr>
          <td style="background:linear-gradient(135deg,#0B1A14 0%,#0E2B22 60%,#071D15 100%);padding:32px 32px 24px;text-align:center;border-bottom:2px solid {alert_color};">
            <p style="margin:0 0 8px;color:rgba(255,255,255,0.5);font-size:10px;letter-spacing:0.2em;text-transform:uppercase;">BOMTEMPO INTELLIGENCE — ALERTA PROATIVO</p>
            <div style="display:inline-block;background:{alert_color}22;border:1px solid {alert_color};border-radius:8px;padding:8px 20px;margin-bottom:12px;">
              <p style="margin:0;color:{alert_color};font-size:13px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;">{alert_label}</p>
            </div>
            <h1 style="margin:0 0 8px;color:#fff;font-size:22px;font-weight:700;letter-spacing:0.02em;">{contract}</h1>
            <p style="margin:0;color:rgba(255,255,255,0.6);font-size:13px;">{cliente} &nbsp;·&nbsp; {now_str}</p>
          </td>
        </tr>

        <!-- KPI TABLE -->
        <tr>
          <td style="padding:28px 32px;">
            <p style="margin:0 0 16px;color:{alert_color};font-size:11px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;">Snapshot do Contrato</p>
            <table style="width:100%;border-collapse:collapse;border-radius:8px;overflow:hidden;background:#081210;">
              <tbody>{kpi_rows}</tbody>
            </table>
          </td>
        </tr>

        <!-- CTA -->
        <tr>
          <td style="padding:0 32px 28px;text-align:center;">
            <p style="margin:0 0 16px;color:#889999;font-size:12px;line-height:1.6;">
              Este alerta foi gerado automaticamente pelo Bomtempo Intelligence.<br>
              Acesse o dashboard para análise completa e tomada de decisão.
            </p>
            <a href="https://bomtempo-gold-moon.reflex.run/" style="display:inline-block;background:linear-gradient(135deg,{alert_color},#C98B2A);color:#000;font-weight:700;font-size:13px;text-decoration:none;padding:12px 28px;border-radius:8px;letter-spacing:0.05em;text-transform:uppercase;">
              Acessar Dashboard
            </a>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:#081210;padding:16px 32px;border-top:1px solid rgba(255,255,255,0.06);">
            <p style="margin:0;color:#7A9A98;font-size:11px;text-align:center;">
              BOMTEMPO Intelligence · Alertas Proativos · Gerado em {now_str}<br>
              Para gerenciar suas notificações, acesse as configurações de alertas.
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

            msg = MIMEMultipart("alternative")
            msg["From"] = Config.RDO_EMAIL_USER
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = f"[{alert_label}] {contract} — BOMTEMPO Alertas"
            msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(Config.RDO_SMTP_SERVER, Config.RDO_SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(Config.RDO_EMAIL_USER, Config.RDO_EMAIL_PASSWORD)
                server.send_message(msg)

            logger.info(f"[AlertEmail] Enviado '{alert_label}' / {contract} para {len(recipients)} destinatário(s).")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("[AlertEmail] Falha de autenticação SMTP.")
            return False
        except Exception as exc:
            logger.error(f"[AlertEmail] Erro: {exc}")
            return False

    @staticmethod
    def send_rdo2_email(
        recipients: List[str],
        rdo_data: dict,
        pdf_path: str,
        view_url: str,
        ai_text: str = "",
    ) -> bool:
        """Email RDO v2 com link de visualização online + PDF anexado."""
        try:
            if not recipients:
                return False
            if not Config.RDO_EMAIL_PASSWORD:
                logger.error("❌ RDO_EMAIL_PASSWORD não configurado")
                return False

            contrato = rdo_data.get("contrato", "—")
            data_rdo = rdo_data.get("data", "—")
            projeto  = rdo_data.get("projeto", "—") or "—"
            clima    = rdo_data.get("condicao_climatica", rdo_data.get("clima", "—"))
            mestre   = rdo_data.get("mestre_id", "—") or "—"
            n_labor  = len(rdo_data.get("mao_obra", []))
            n_acts   = len(rdo_data.get("atividades", []))

            # Build absolute URL for the email link
            from bomtempo.core.config import Config as _Cfg
            abs_view_url = (
                view_url if view_url.startswith("http")
                else f"{_Cfg.APP_URL.rstrip('/')}{view_url}"
            ) if view_url else ""
            view_btn = (
                f'<a href="{abs_view_url}" style="display:inline-block;background:linear-gradient(135deg,#C98B2A,#9B6820);'
                f'color:#fff;font-weight:700;font-size:13px;text-decoration:none;padding:12px 28px;'
                f'border-radius:8px;letter-spacing:0.05em;text-transform:uppercase;margin-top:8px;">Ver RDO Online</a>'
                if abs_view_url else ""
            )

            ai_section = (
                f'<div style="background:rgba(42,157,143,0.07);border-left:3px solid #2A9D8F;'
                f'padding:16px 20px;border-radius:0 8px 8px 0;margin:0 32px 28px;">'
                f'<p style="margin:0 0 8px;color:#2A9D8F;font-size:12px;font-weight:700;text-transform:uppercase;">🤖 Análise BTP Intelligence</p>'
                f'<div style="color:#C8D8D4;font-size:13px;line-height:1.7;">{_md_to_html(ai_text)}</div>'
                f'</div>'
                if ai_text else ""
            )

            # Personalized intro para o RDO
            doc_label_rdo = f"RDO do contrato {contrato} de {data_rdo}"
            personalized_intro = _generate_personalized_intro(
                doc_label=doc_label_rdo,
                context_hint=f"Projeto: {projeto}. Clima: {clima}. {n_acts} atividade(s) registrada(s).",
            )
            intro_text = personalized_intro or f"Segue o Relatório Diário de Obra do contrato <strong style='color:#C98B2A;'>{contrato}</strong> de <strong style='color:#C98B2A;'>{data_rdo}</strong>."

            body_html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#030504;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#030504;">
  <tr><td align="center" style="padding:32px 16px;">
    <table width="600" cellpadding="0" cellspacing="0"
      style="max-width:600px;width:100%;background:#0e1a17;border-radius:16px;overflow:hidden;border:1px solid rgba(201,139,42,0.2);">
      <tr><td style="background:linear-gradient(135deg,#1a0e00,#C98B2A 60%,#2A9D8F);padding:28px 32px;text-align:center;">
        <p style="margin:0 0 4px;color:rgba(255,255,255,0.7);font-size:11px;letter-spacing:0.15em;text-transform:uppercase;">BOMTEMPO INTELLIGENCE</p>
        <h1 style="margin:0 0 8px;color:#fff;font-size:22px;font-weight:700;">Relatório Diário de Obra — v2</h1>
        <p style="margin:0;background:rgba(0,0,0,0.25);display:inline-block;padding:6px 16px;border-radius:20px;color:#fff;font-size:14px;">{contrato} &nbsp;·&nbsp; {data_rdo}</p>
      </td></tr>
      <tr><td style="padding:20px 32px 4px;">
        <p style="margin:0;color:#C8D8D4;font-size:14px;line-height:1.7;">{intro_text}</p>
      </td></tr>
      <tr><td style="padding:12px 32px 0;">
        <table style="width:100%;border-collapse:collapse;">
          <tr style="background:rgba(201,139,42,0.06);">
            <td style="padding:9px 12px;color:#889999;font-size:13px;width:40%;">Projeto</td>
            <td style="padding:9px 12px;color:#E0E0E0;font-size:13px;">{projeto}</td>
          </tr>
          <tr><td style="padding:9px 12px;color:#889999;font-size:13px;">Clima</td>
              <td style="padding:9px 12px;color:#E0E0E0;font-size:13px;">{clima}</td></tr>
          <tr style="background:rgba(201,139,42,0.06);">
            <td style="padding:9px 12px;color:#889999;font-size:13px;">Mestre</td>
            <td style="padding:9px 12px;color:#E0E0E0;font-size:13px;">{mestre}</td>
          </tr>
          <tr><td style="padding:9px 12px;color:#889999;font-size:13px;">Equipe</td>
              <td style="padding:9px 12px;color:#C98B2A;font-size:13px;font-weight:700;">{n_labor} tipo(s) · {n_acts} atividade(s)</td></tr>
        </table>
      </td></tr>
      <tr><td style="padding:24px 32px;text-align:center;">
        {view_btn}
        {"<p style='margin:12px 0 0;color:#889999;font-size:12px;'>📎 O PDF completo está anexado a este email.</p>" if pdf_path else "<p style='margin:12px 0 0;background:rgba(249,115,22,0.08);border:1px solid rgba(249,115,22,0.3);border-radius:8px;padding:10px 16px;color:#F97316;font-size:12px;display:inline-block;'>⚠️ O PDF não pôde ser gerado automaticamente. Acesse a plataforma pelo link acima para gerar o arquivo novamente.</p>"}
      </td></tr>
      {f'<tr><td>{ai_section}</td></tr>' if ai_section else ''}
      <tr><td style="background:#081210;padding:16px 32px;border-top:1px solid rgba(255,255,255,0.06);text-align:center;">
        <p style="margin:0;color:#4a5a58;font-size:11px;">Gerado automaticamente · BOMTEMPO Dashboard · Não responda este email.</p>
      </td></tr>
    </table>
  </td></tr>
</table></body></html>"""

            msg = MIMEMultipart("mixed")
            msg["From"]    = Config.RDO_EMAIL_USER
            msg["To"]      = ", ".join(recipients)
            msg["Subject"] = f"📋 RDO v2 | {contrato} | {data_rdo} | BOMTEMPO"
            msg.attach(MIMEText(body_html, "html", "utf-8"))

            if pdf_path and Path(pdf_path).exists():
                with open(pdf_path, "rb") as f:
                    att = MIMEApplication(f.read(), _subtype="pdf")
                    att.add_header("Content-Disposition", "attachment", filename=Path(pdf_path).name)
                    msg.attach(att)

            with smtplib.SMTP(Config.RDO_SMTP_SERVER, Config.RDO_SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(Config.RDO_EMAIL_USER, Config.RDO_EMAIL_PASSWORD)
                server.send_message(msg)

            logger.info(f"✅ RDO2 email enviado → {recipients}")
            return True
        except Exception as e:
            logger.error(f"❌ send_rdo2_email: {e}")
            return False

    @staticmethod
    def test_connection() -> bool:
        """Testa conexão SMTP"""
        try:
            if not Config.RDO_EMAIL_PASSWORD:
                logger.error("❌ RDO_EMAIL_PASSWORD não configurado")
                return False

            with smtplib.SMTP(Config.RDO_SMTP_SERVER, Config.RDO_SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(Config.RDO_EMAIL_USER, Config.RDO_EMAIL_PASSWORD)

            logger.info("✅ Conexão SMTP OK")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao testar SMTP: {e}")
            return False

    @staticmethod
    def send_password_reset_email(recipient: str, reset_link: str) -> bool:
        """Envia email com link de redefinição de senha."""
        try:
            if not recipient:
                return False
            if not Config.RDO_EMAIL_PASSWORD:
                logger.error("❌ RDO_EMAIL_PASSWORD não configurado")
                return False

            msg = MIMEMultipart("alternative")
            msg["From"] = Config.RDO_EMAIL_USER
            msg["To"] = recipient
            msg["Subject"] = "🔐 Redefinição de Senha | BOMTEMPO Intelligence"

            body_html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#030504;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#030504;">
  <tr><td align="center" style="padding:48px 16px;">
    <table width="500" cellpadding="0" cellspacing="0"
      style="max-width:500px;width:100%;background:#0e1a17;border-radius:16px;overflow:hidden;border:1px solid rgba(201,139,42,0.2);">
      <tr><td style="background:linear-gradient(135deg,#1a0e00,#C98B2A);padding:32px;text-align:center;">
        <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;">Recuperação de Acesso</h1>
      </tr></td>
      <tr><td style="padding:32px;">
        <p style="margin:0 0 16px;color:#C8D8D4;font-size:15px;line-height:1.6;">
          Olá, recebemos uma solicitação para redefinir a senha da sua conta no <strong style="color:#C98B2A;">BOMTEMPO Dashboard</strong>.
        </p>
        <p style="margin:0 0 24px;color:#889999;font-size:14px;line-height:1.6;">
          Clique no botão abaixo para escolher uma nova senha. Este link expira em 1 hora.
        </p>
        <div style="text-align:center;margin-bottom:24px;">
          <a href="{reset_link}" style="display:inline-block;background:#C98B2A;color:#000;font-weight:700;font-size:14px;text-decoration:none;padding:14px 32px;border-radius:8px;text-transform:uppercase;letter-spacing:0.05em;">Redefinir Senha</a>
        </div>
        <p style="margin:0;color:#4a5a58;font-size:12px;text-align:center;">
          Se você não solicitou esta alteração, pode ignorar este email com segurança.
        </p>
      </td></tr>
      <tr><td style="background:#081210;padding:16px;text-align:center;border-top:1px solid rgba(255,255,255,0.06);">
        <p style="margin:0;color:#4a5a58;font-size:11px;">BOMTEMPO Intelligence · Sistema de Segurança</p>
      </td></tr>
    </table>
  </td></tr>
</table></body></html>"""

            msg.attach(MIMEText(body_html, "html", "utf-8"))

            with smtplib.SMTP(Config.RDO_SMTP_SERVER, Config.RDO_SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(Config.RDO_EMAIL_USER, Config.RDO_EMAIL_PASSWORD)
                server.send_message(msg)

            logger.info(f"✅ Reset email enviado para {recipient}")
            return True
        except Exception as e:
            logger.error(f"❌ send_password_reset_email: {e}")
            return False

    @staticmethod
    def send_document_email(
        recipients: List[str],
        doc_label: str,
        doc_url: str,
        sender_username: str = "Action AI",
        message_extra: str = "",
        recipient_name: str = "",
    ) -> bool:
        """
        Envia email com link para um documento (RDO, relatório) solicitado via Action AI.
        Não anexa o PDF — apenas envia link para evitar bloqueios de tamanho.
        Gera intro personalizada via IA quando message_extra ou recipient_name disponíveis.
        """
        try:
            if not recipients:
                logger.warning("[DocEmail] Nenhum destinatário.")
                return False
            if not Config.RDO_EMAIL_PASSWORD:
                logger.error("[DocEmail] RDO_EMAIL_PASSWORD não configurado.")
                return False

            now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

            # Personalized intro via AI (runs synchronously, <2s, failure-safe)
            personalized = _generate_personalized_intro(
                doc_label=doc_label,
                recipient_name=recipient_name,
                sender_name=sender_username,
                context_hint=message_extra,
            )
            display_text = personalized or message_extra or f"Segue o documento solicitado: {doc_label}."
            message_block = (
                f'<p style="color:#C8D8D4;font-size:14px;line-height:1.6;margin:0 0 16px;">'
                f'{display_text}</p>'
            )

            body_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0a1f1a;font-family:'Segoe UI',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a1f1a;padding:32px 16px;">
  <tr><td>
    <table width="600" align="center" cellpadding="0" cellspacing="0"
           style="background:linear-gradient(180deg,#0d2b24,#0a1f1a);border:1px solid rgba(201,139,42,0.25);border-radius:12px;overflow:hidden;max-width:600px;">
      <tr>
        <td style="background:linear-gradient(135deg,#0d2b24,#1a3d35);padding:28px 32px;border-bottom:1px solid rgba(201,139,42,0.2);">
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="background:linear-gradient(135deg,#C98B2A,#9B6820);border-radius:8px;padding:8px;display:inline-block;">
              <span style="font-size:18px;">📄</span>
            </div>
            <div>
              <p style="margin:0;font-size:11px;color:#2A9D8F;letter-spacing:0.1em;text-transform:uppercase;font-weight:700;">Bomtempo Dashboard · Action AI</p>
              <h1 style="margin:4px 0 0;font-size:18px;color:#E0E0E0;font-weight:700;">Documento Solicitado</h1>
            </div>
          </div>
        </td>
      </tr>
      <tr>
        <td style="padding:28px 32px;">
          <p style="color:#889999;font-size:12px;margin:0 0 20px;">Enviado em {now_str} por {sender_username}</p>
          {message_block}
          <div style="background:rgba(201,139,42,0.06);border:1px solid rgba(201,139,42,0.2);border-radius:10px;padding:20px;margin-bottom:24px;">
            <p style="margin:0 0 8px;font-size:12px;color:#889999;text-transform:uppercase;letter-spacing:0.08em;">Documento</p>
            <p style="margin:0;font-size:16px;font-weight:700;color:#E0E0E0;">{doc_label}</p>
          </div>
          <div style="text-align:center;margin-bottom:24px;">
            <a href="{doc_url}"
               style="display:inline-block;background:linear-gradient(135deg,#C98B2A,#9B6820);color:#fff;font-weight:700;
                      font-size:13px;text-decoration:none;padding:14px 32px;border-radius:8px;
                      letter-spacing:0.05em;text-transform:uppercase;">
              Acessar Documento PDF
            </a>
          </div>
          <p style="color:#556666;font-size:11px;text-align:center;margin:0;">
            Este e-mail foi gerado automaticamente pelo Bomtempo Dashboard.<br>
            O link é público e pode ser acessado diretamente.
          </p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>"""

            msg = MIMEMultipart("alternative")
            msg["From"] = Config.RDO_EMAIL_USER
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = f"[Bomtempo] {doc_label}"
            msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(Config.RDO_SMTP_SERVER, Config.RDO_SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(Config.RDO_EMAIL_USER, Config.RDO_EMAIL_PASSWORD)
                server.send_message(msg)

            logger.info(f"[DocEmail] '{doc_label}' enviado para {recipients}.")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("[DocEmail] Falha de autenticação SMTP.")
            return False
        except Exception as exc:
            logger.error(f"[DocEmail] Erro: {exc}")
            return False
