"""
PDF Tasks — Celery tasks para geração de PDF de relatórios.
Roda em worker isolado (max_tasks_per_child=1) para evitar leak de RAM.
"""

import io
from datetime import datetime
from typing import Any, Dict, Optional

from backend.workers.celery_app import celery_app
from backend.core.logging import get_logger
from backend.integrations.supabase import sb_select, sb_update

logger = get_logger(__name__)


def _build_html(report: Dict, data: Dict) -> str:
    """Monta HTML do relatório para conversão PDF."""
    tipo    = report.get("tipo","executive")
    titulo  = report.get("titulo","Relatório")
    contrato = report.get("contrato","")
    now     = datetime.now().strftime("%d/%m/%Y %H:%M")

    style = """
    <style>
      body { font-family: 'Segoe UI', sans-serif; color: #1a1a2e; margin: 40px; }
      h1   { color: #C98B2A; border-bottom: 3px solid #C98B2A; padding-bottom: 8px; }
      h2   { color: #444; margin-top: 24px; font-size: 14px; text-transform: uppercase; }
      table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 12px; }
      th    { background: #C98B2A; color: white; padding: 6px 10px; text-align: left; }
      td    { padding: 6px 10px; border-bottom: 1px solid #eee; }
      tr:nth-child(even) { background: #f9f9f9; }
      .kpi  { display: inline-block; margin: 8px 16px 8px 0; }
      .kpi-val { font-size: 24px; font-weight: bold; color: #C98B2A; }
      .kpi-lbl { font-size: 11px; color: #888; text-transform: uppercase; }
      .footer { margin-top: 40px; font-size: 10px; color: #aaa; text-align: center; }
    </style>
    """

    kpis = data.get("kpis", {})
    kpi_html = ""
    for label, value in [
        ("Previsto",   kpis.get("total_previsto","—")),
        ("Executado",  kpis.get("total_executado","—")),
        ("Saldo",      kpis.get("saldo","—")),
        ("% Executado", f'{kpis.get("pct_executado",0)}%'),
    ]:
        kpi_html += f'<div class="kpi"><div class="kpi-val">{value}</div><div class="kpi-lbl">{label}</div></div>'

    custos_rows = ""
    for c in data.get("custos", [])[:50]:
        custos_rows += f"<tr><td>{c.get('categoria_nome','')}</td><td>{c.get('descricao','')}</td><td>{c.get('valor_previsto_fmt','')}</td><td>{c.get('valor_executado_fmt','')}</td><td>{c.get('status','')}</td></tr>"

    custos_table = f"""
    <h2>Custos por Categoria</h2>
    <table>
      <tr><th>Categoria</th><th>Descrição</th><th>Previsto</th><th>Executado</th><th>Status</th></tr>
      {custos_rows}
    </table>
    """ if custos_rows else ""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{style}</head><body>
    <h1>{titulo}</h1>
    <p style="color:#888;font-size:12px">Contrato: <strong>{contrato}</strong> · Gerado em: {now}</p>
    <h2>KPIs Financeiros</h2>
    {kpi_html}
    {custos_table}
    <div class="footer">Bomtempo Intelligence · Relatório gerado automaticamente</div>
    </body></html>"""


@celery_app.task(name="backend.workers.tasks.pdf_tasks.generate_pdf", bind=True, max_retries=1)
def generate_pdf(self, report_id: str, client_id: str = "", params: Dict = None) -> None:
    """Gera PDF do relatório e atualiza registro com pdf_url."""
    params = params or {}
    try:
        # Load report record
        rows = sb_select("relatorios", filters={"id": report_id}, limit=1) or []
        if not rows:
            logger.error(f"Report {report_id} não encontrado")
            return
        report = rows[0]
        contrato = report.get("contrato","")

        # Gather data for this report type
        data: Dict[str, Any] = {}
        if contrato:
            filters: Dict[str, Any] = {"contrato": contrato}
            if client_id:
                filters["client_id"] = client_id
            custos = sb_select("fin_custos", filters=filters, limit=500) or []

            # compute basic kpis
            total_prev = sum(float(c.get("valor_previsto",0) or 0) for c in custos)
            total_exec = sum(float(c.get("valor_executado",0) or 0) for c in custos)
            saldo      = total_prev - total_exec
            pct        = round(total_exec/total_prev*100, 1) if total_prev > 0 else 0.0

            def _brl(v: float) -> str:
                return f"R$ {v:_.2f}".replace(".", "DECPT").replace("_", ".").replace("DECPT", ",")

            data["kpis"] = {
                "total_previsto":   _brl(total_prev),
                "total_executado":  _brl(total_exec),
                "saldo":            _brl(saldo),
                "pct_executado":    pct,
            }
            data["custos"] = [
                {
                    "categoria_nome":     str(c.get("categoria_nome","")  or "—"),
                    "descricao":          str(c.get("descricao","")        or "—"),
                    "valor_previsto_fmt": _brl(float(c.get("valor_previsto",0) or 0)),
                    "valor_executado_fmt":_brl(float(c.get("valor_executado",0) or 0)),
                    "status":             str(c.get("status","")           or "—"),
                }
                for c in custos[:50]
            ]

        pdf_bytes = _build_fin_pdf_fpdf(report, data)

        # Upload to Supabase storage
        pdf_url = ""
        if pdf_bytes:
            try:
                from backend.integrations.supabase import sb_storage_upload
                path    = f"relatorios/{report_id}.pdf"
                pdf_url = sb_storage_upload("rdo-pdfs", path, pdf_bytes, "application/pdf") or ""
            except Exception as e:
                logger.warning(f"Upload PDF falhou: {e}")

        sb_update("relatorios", filters={"id": report_id}, data={
            "status":  "Concluído" if pdf_url else "Erro",
            "pdf_url": pdf_url,
        })

    except Exception as e:
        logger.error(f"generate_pdf error: {e}")
        try:
            sb_update("relatorios", filters={"id": report_id}, data={"status": "Erro"})
        except Exception:
            pass


def _build_fin_pdf_fpdf(report: Dict, data: Dict) -> Optional[bytes]:
    """Gera PDF de relatório financeiro usando fpdf2."""
    try:
        from fpdf import FPDF, XPos, YPos

        COPPER_RGB = (201, 139, 42)
        DARK_RGB   = (26, 26, 46)

        pdf = FPDF()
        pdf.set_margins(15, 15, 15)
        pdf.add_page()

        # Cabeçalho
        pdf.set_fill_color(*DARK_RGB)
        pdf.rect(0, 0, 210, 28, "F")
        pdf.set_text_color(201, 139, 42)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_xy(15, 7)
        pdf.cell(0, 7, "RELATÓRIO FINANCEIRO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(180, 180, 180)
        pdf.set_xy(15, 16)
        contrato = str(report.get("contrato") or "—")
        now      = datetime.now().strftime("%d/%m/%Y %H:%M")
        pdf.cell(0, 5, f"Contrato: {contrato}   |   Gerado em: {now}")

        pdf.set_y(34)
        pdf.set_text_color(*DARK_RGB)

        # KPIs
        kpis = data.get("kpis", {})
        kpi_items = [
            ("Previsto",   kpis.get("total_previsto", "—")),
            ("Executado",  kpis.get("total_executado", "—")),
            ("Saldo",      kpis.get("saldo", "—")),
            ("% Exec.",    f"{kpis.get('pct_executado', 0)}%"),
        ]
        for i, (lbl, val) in enumerate(kpi_items):
            x = 15 + i * 45
            pdf.set_fill_color(245, 243, 238)
            pdf.rect(x, 34, 41, 16, "F")
            pdf.set_xy(x + 2, 36)
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_text_color(150, 130, 80)
            pdf.cell(37, 4, lbl.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_xy(x + 2, 41)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*DARK_RGB)
            pdf.cell(37, 4, str(val)[:16])

        pdf.set_y(56)

        # Tabela de custos
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(*COPPER_RGB)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(60, 7, "CATEGORIA", fill=True)
        pdf.cell(65, 7, "DESCRIÇÃO", fill=True)
        pdf.cell(28, 7, "PREVISTO", fill=True, align="R")
        pdf.cell(28, 7, "EXECUTADO", fill=True, align="R")
        pdf.cell(0,  7, "STATUS", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*DARK_RGB)
        custos_list = data.get("custos", [])[:50]
        for idx, c in enumerate(custos_list):
            if pdf.get_y() > 260:
                pdf.add_page()
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_fill_color(*COPPER_RGB)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(60, 7, "CATEGORIA", fill=True)
                pdf.cell(65, 7, "DESCRIÇÃO", fill=True)
                pdf.cell(28, 7, "PREVISTO", fill=True, align="R")
                pdf.cell(28, 7, "EXECUTADO", fill=True, align="R")
                pdf.cell(0,  7, "STATUS", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font("Helvetica", "", 7)
                pdf.set_text_color(*DARK_RGB)
            fill = idx % 2 == 0
            pdf.set_fill_color(250, 248, 243) if fill else pdf.set_fill_color(255, 255, 255)
            pdf.cell(60, 5, str(c.get("categoria_nome", "—"))[:28], fill=fill)
            pdf.cell(65, 5, str(c.get("descricao", "—"))[:32], fill=fill)
            pdf.cell(28, 5, str(c.get("valor_previsto_fmt", "—"))[:14], fill=fill, align="R")
            pdf.cell(28, 5, str(c.get("valor_executado_fmt", "—"))[:14], fill=fill, align="R")
            pdf.cell(0,  5, str(c.get("status", "—"))[:12], fill=fill, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if len(data.get("custos", [])) > 50:
            pdf.cell(0, 5, f"... {len(data['custos']) - 50} itens omitidos. Ver relatório completo no sistema.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Rodapé
        pdf.set_y(-15)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(170, 170, 170)
        pdf.cell(0, 5, f"Bomtempo Intelligence  |  {now}  |  {contrato}", align="C")

        return bytes(pdf.output())

    except Exception as e:
        logger.error(f"_build_fin_pdf_fpdf error: {e}")
        return None


def _build_rdo_pdf_fpdf(rdo: Dict, atividades: list) -> Optional[bytes]:
    """Gera PDF de RDO usando fpdf2 (pure Python — sem dependências nativas).
    Layout executivo: cabeçalho, KPIs, tabela de atividades, observações, AI summary."""
    try:
        from fpdf import FPDF, XPos, YPos

        COPPER_RGB = (201, 139, 42)
        TEAL_RGB   = (42, 157, 143)
        DARK_RGB   = (26, 26, 46)

        pdf = FPDF()
        pdf.set_margins(15, 15, 15)
        pdf.add_page()

        # ── Cabeçalho ────────────────────────────────────────────────────────────
        pdf.set_fill_color(*DARK_RGB)
        pdf.rect(0, 0, 210, 30, "F")
        pdf.set_text_color(201, 139, 42)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_xy(15, 8)
        pdf.cell(0, 8, "RELATÓRIO DIÁRIO DE OBRA", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(180, 180, 180)
        pdf.set_xy(15, 18)
        contrato = str(rdo.get("contrato") or "—")
        data_rdo = str(rdo.get("data") or rdo.get("data_rdo") or "—")[:10]
        pdf.cell(0, 6, f"Contrato: {contrato}   |   Data: {data_rdo}   |   Status: {rdo.get('status','')}")

        pdf.set_y(36)
        pdf.set_text_color(*DARK_RGB)

        # ── KPIs ─────────────────────────────────────────────────────────────────
        equipe  = str(rdo.get("equipe_alocada") or "—")
        clima   = str(rdo.get("condicao_climatica") or rdo.get("clima") or "—")
        turno   = str(rdo.get("turno") or "—")
        kpis    = [("Equipe", equipe + " pess."), ("Clima", clima), ("Turno", turno)]

        for i, (lbl, val) in enumerate(kpis):
            x = 15 + i * 60
            pdf.set_fill_color(245, 243, 238)
            pdf.rect(x, 36, 56, 18, "F")
            pdf.set_xy(x + 2, 38)
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_text_color(150, 130, 80)
            pdf.cell(52, 4, lbl.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_xy(x + 2, 43)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*DARK_RGB)
            pdf.cell(52, 5, val[:20])

        pdf.set_y(60)

        # ── Atividades ────────────────────────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(*COPPER_RGB)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(95, 7, "ATIVIDADE", fill=True)
        pdf.cell(25, 7, "QTD / PCT", fill=True, align="C")
        pdf.cell(20, 7, "EFETIVO", fill=True, align="C")
        pdf.cell(0,  7, "OBS", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*DARK_RGB)
        for idx, at in enumerate(atividades[:30]):
            nome    = str(at.get("atividade") or at.get("descricao") or "—")[:55]
            unidade = str(at.get("unidade") or "")
            qty     = at.get("quantidade") or 0
            efet    = str(at.get("efetivo") or "—")
            obs_v   = str(at.get("observacao") or "")[:30]
            is_m    = bool(at.get("is_marco"))
            if is_m:
                qty_str = "✓ Concluído" if at.get("marco_concluido") else "Pendente"
            elif unidade == "%":
                qty_str = f"{int(qty)}%"
            else:
                qty_str = f"{qty} {unidade}"
            fill = idx % 2 == 0
            if fill:
                pdf.set_fill_color(250, 248, 243)
            else:
                pdf.set_fill_color(255, 255, 255)
            pdf.cell(95, 6, nome,    fill=fill)
            pdf.cell(25, 6, qty_str, fill=fill, align="C")
            pdf.cell(20, 6, efet,    fill=fill, align="C")
            pdf.cell(0,  6, obs_v,   fill=fill, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # ── Alertas / Obs / AI — nova página se necessário ───────────────────────
        if pdf.get_y() > 230:
            pdf.add_page()

        if rdo.get("houve_interrupcao") or rdo.get("houve_chuva") or rdo.get("houve_acidente"):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*COPPER_RGB)
            pdf.cell(0, 6, "OCORRÊNCIAS", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*DARK_RGB)
            if rdo.get("houve_interrupcao"):
                mot = str(rdo.get("motivo_interrupcao") or "Não especificado")[:80]
                pdf.cell(0, 5, f"  Interrupcao: {mot}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            if rdo.get("houve_chuva"):
                pdf.cell(0, 5, f"  Chuva registrada", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            if rdo.get("houve_acidente"):
                pdf.cell(0, 5, "  ACIDENTE REGISTRADO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # ── Observações ───────────────────────────────────────────────────────────
        obs = str(rdo.get("observacoes") or "")
        if obs:
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*COPPER_RGB)
            pdf.cell(0, 6, "OBSERVAÇÕES", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*DARK_RGB)
            pdf.multi_cell(0, 5, obs[:400])

        # ── Orientação p/ amanhã ──────────────────────────────────────────────────
        ori = str(rdo.get("orientacao") or "")
        if ori:
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*TEAL_RGB)
            pdf.cell(0, 6, "ORIENTAÇÃO PARA AMANHÃ", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*DARK_RGB)
            pdf.multi_cell(0, 5, ori[:400])

        # ── AI Summary ────────────────────────────────────────────────────────────
        ai = str(rdo.get("ai_summary") or "")
        if ai:
            pdf.ln(4)
            pdf.set_fill_color(240, 250, 248)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*TEAL_RGB)
            pdf.cell(0, 6, "ANÁLISE DE INTELIGÊNCIA ARTIFICIAL", fill=False, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*DARK_RGB)
            pdf.multi_cell(0, 5, ai[:800])

        # ── Rodapé ────────────────────────────────────────────────────────────────
        pdf.set_y(-15)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(170, 170, 170)
        pdf.cell(0, 5, f"Bomtempo Intelligence  |  Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  {contrato}", align="C")

        return bytes(pdf.output())

    except Exception as e:
        logger.error(f"_build_rdo_pdf_fpdf error: {e}")
        return None


def _build_rdo_html(rdo: Dict, atividades: list, evidencias: list) -> str:
    import html as _html
    contrato   = _html.escape(str(rdo.get("contrato", "")))
    data_rdo   = _html.escape(str(rdo.get("data") or rdo.get("data_rdo") or "")[:10])
    clima      = _html.escape(str(rdo.get("clima") or rdo.get("condicao_climatica") or "—"))
    turno      = _html.escape(str(rdo.get("turno") or "—"))
    equipe     = str(rdo.get("equipe_alocada") or 0)
    obs        = _html.escape(str(rdo.get("observacoes") or "")).replace("\n", "<br>")
    orientacao = _html.escape(str(rdo.get("orientacao") or "")).replace("\n", "<br>")
    ai_sum     = str(rdo.get("ai_summary") or "").replace("\n", "<br>")
    status     = _html.escape(str(rdo.get("status") or ""))
    now        = datetime.now().strftime("%d/%m/%Y %H:%M")

    at_rows = ""
    for at in atividades:
        nome = _html.escape(str(at.get("atividade") or at.get("nome_atividade") or at.get("descricao") or "—"))
        # quantidade armazena pct (quando unidade=%) ou qty física
        unidade_at = str(at.get("unidade") or "")
        qty = float(at.get("quantidade") or 0)
        if unidade_at in ("%", ""):
            pct_str = f"{int(qty)}%"
        else:
            pct_str = f"{qty} {unidade_at}"
        efet = at.get("efetivo") or "—"
        st   = _html.escape(str(at.get("observacao") or at.get("status_atividade") or ""))
        at_rows += f"<tr><td>{nome}</td><td style='text-align:center'>{pct_str}</td><td style='text-align:center'>{efet}</td><td>{st}</td></tr>"

    ev_rows = ""
    for ev in evidencias[:20]:
        url = ev.get("foto_url") or ev.get("url_foto") or ev.get("url") or ""
        tip = _html.escape(str(ev.get("tipo") or ""))
        cap = _html.escape(str(ev.get("legenda") or ev.get("caption") or ""))
        if url:
            ev_rows += f'<div style="display:inline-block;margin:6px;vertical-align:top;text-align:center"><img src="{url}" style="max-width:180px;max-height:140px;border-radius:4px;border:1px solid #ddd"><br><span style="font-size:9px;color:#888">{tip} {cap}</span></div>'

    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<style>
body {{font-family:'Segoe UI',Arial,sans-serif;color:#1a1a1a;margin:32px;font-size:12px}}
h1 {{color:#C98B2A;font-size:18px;border-bottom:2px solid #C98B2A;padding-bottom:6px}}
h2 {{color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.08em;margin-top:20px;margin-bottom:6px}}
.meta-grid {{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:14px 0}}
.meta-box {{background:#f7f4ee;border-radius:4px;padding:8px 12px}}
.meta-lbl {{font-size:9px;font-weight:700;color:#999;text-transform:uppercase}}
.meta-val {{font-size:14px;font-weight:700;color:#333;margin-top:2px}}
table {{width:100%;border-collapse:collapse;margin-top:8px;font-size:11px}}
th {{background:#C98B2A;color:white;padding:5px 8px;text-align:left;font-size:10px;text-transform:uppercase}}
td {{padding:5px 8px;border-bottom:1px solid #eee}}
tr:nth-child(even){{background:#fafafa}}
.obs {{background:#f7f4ee;border-left:3px solid #C98B2A;padding:10px 14px;border-radius:0 4px 4px 0;margin-top:8px;line-height:1.6}}
.footer {{margin-top:32px;font-size:9px;color:#bbb;text-align:center;border-top:1px solid #eee;padding-top:10px}}
</style></head><body>
<h1>Relatório Diário de Obra</h1>
<p style="color:#888;font-size:11px">Contrato <strong>{contrato}</strong> &mdash; Data: <strong>{data_rdo}</strong> &mdash; Status: <strong>{status}</strong></p>
<div class="meta-grid">
  <div class="meta-box"><div class="meta-lbl">Clima</div><div class="meta-val">{clima}</div></div>
  <div class="meta-box"><div class="meta-lbl">Turno</div><div class="meta-val">{turno}</div></div>
  <div class="meta-box"><div class="meta-lbl">Equipe Alocada</div><div class="meta-val">{equipe} pessoas</div></div>
</div>
<h2>Atividades Executadas</h2>
<table>
  <tr><th>Atividade</th><th style="text-align:center;width:70px">% Exec.</th><th style="text-align:center;width:70px">Efetivo</th><th style="width:110px">Status</th></tr>
  {at_rows or '<tr><td colspan="4" style="color:#aaa;text-align:center">Nenhuma atividade registrada</td></tr>'}
</table>
{'<h2>Observações</h2><div class="obs">' + obs + '</div>' if obs else ''}
{'<h2>Orientação para Amanhã</h2><div class="obs">' + orientacao + '</div>' if orientacao else ''}
{'<h2>Evidências Fotográficas</h2><div>' + ev_rows + '</div>' if ev_rows else ''}
{'<h2>Análise de Inteligência Artificial</h2><div style="background:#f0faf8;border-left:3px solid #2A9D8F;padding:10px 14px;border-radius:0 4px 4px 0;line-height:1.6;font-size:11px;color:#1a1a2e">' + ai_sum + '</div>' if ai_sum else ''}
<div class="footer">Bomtempo Intelligence &middot; Gerado em {now} &middot; RDO: {_html.escape(str(rdo.get("id",""))[:36])}</div>
</body></html>"""


@celery_app.task(
    name="backend.workers.tasks.pdf_tasks.generate_rdo_pdf",
    bind=True,
    max_retries=1,
    queue="pdf",
)
def generate_rdo_pdf(self, rdo_id: str, client_id: str = "") -> Dict[str, Any]:
    """Gera PDF de um RDO e atualiza rdo_master.pdf_url."""
    from backend.integrations.supabase import sb_select, sb_update, sb_storage_upload

    try:
        rows = sb_select("rdo_master", filters={"id": rdo_id}, limit=1) or []
        if not rows:
            return {"ok": False, "error": "RDO não encontrado"}
        rdo = rows[0]

        atividades = sb_select("rdo_atividades", filters={"rdo_id": rdo_id}, limit=200) or []

        pdf_bytes = _build_rdo_pdf_fpdf(rdo, atividades)
        if not pdf_bytes:
            return {"ok": False, "error": "PDF generation failed"}

        from backend.core.config import Config as _Cfg
        contrato = str(rdo.get("contrato") or "rdo").replace("/", "-").replace(" ", "_")
        data_str = str(rdo.get("data") or rdo.get("data_rdo") or "")[:10].replace("-", "")
        filename = f"RDO-{contrato}-{data_str}-{rdo_id[:8]}.pdf"
        storage_path = f"rdo-pdfs/{filename}"

        # Salva localmente primeiro (para anexar no email)
        local_dir = _Cfg.RDO_PDF_DIR
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = str(local_dir / filename)
        try:
            with open(local_path, "wb") as f:
                f.write(pdf_bytes)
        except Exception as e:
            logger.warning(f"PDF local save failed: {e}")
            local_path = ""

        # Upload para Supabase Storage
        pdf_url = ""
        try:
            pdf_url = sb_storage_upload("rdo-pdfs", storage_path, pdf_bytes, "application/pdf") or ""
        except Exception as e:
            logger.warning(f"PDF upload failed: {e}")

        if pdf_url:
            sb_update("rdo_master", {"id": rdo_id}, {"pdf_url": pdf_url})
        elif local_path:
            logger.warning(f"PDF storage upload falhou — PDF disponível localmente: {local_path}")

        return {"ok": bool(pdf_bytes), "pdf_url": pdf_url, "pdf_path": local_path, "pdf_bytes": pdf_bytes}

    except Exception as e:
        logger.error(f"generate_rdo_pdf error: {e}")
        return {"ok": False, "error": str(e)}
