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

        html = _build_html(report, data)

        # Convert HTML → PDF via WeasyPrint (best-effort)
        pdf_bytes: Optional[bytes] = None
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html).write_pdf()
        except Exception as e:
            logger.warning(f"WeasyPrint não disponível: {e} — salvando HTML como fallback")

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


def _brl(v: float) -> str:
    return f"R$ {v:_.2f}".replace(".", "DECPT").replace("_", ".").replace("DECPT", ",")


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
        nome = _html.escape(str(at.get("nome_atividade") or at.get("descricao") or "—"))
        pct  = at.get("pct_executado") or 0
        efet = at.get("efetivo") or "—"
        st   = _html.escape(str(at.get("status_atividade") or ""))
        at_rows += f"<tr><td>{nome}</td><td style='text-align:center'>{pct}%</td><td style='text-align:center'>{efet}</td><td>{st}</td></tr>"

    ev_rows = ""
    for ev in evidencias[:20]:
        url = ev.get("url_foto") or ev.get("url") or ""
        tip = _html.escape(str(ev.get("tipo") or ""))
        cap = _html.escape(str(ev.get("caption") or ""))
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
        evidencias = sb_select("rdo_evidencias", filters={"rdo_id": rdo_id}, limit=100) or []

        html_str = _build_rdo_html(rdo, atividades, evidencias)

        pdf_bytes = None
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html_str).write_pdf()
        except Exception as e:
            logger.warning(f"WeasyPrint error: {e}")
            return {"ok": False, "error": f"WeasyPrint: {e}"}

        contrato = str(rdo.get("contrato") or "rdo")
        data_str = str(rdo.get("data") or rdo.get("data_rdo") or "")[:10].replace("-", "")
        filename = f"RDO-{contrato}-{data_str}-{rdo_id[:8]}.pdf"
        path     = f"rdo-pdfs/{filename}"

        pdf_url = ""
        try:
            pdf_url = sb_storage_upload("rdo-pdfs", path, pdf_bytes, "application/pdf") or ""
        except Exception as e:
            logger.warning(f"PDF upload failed: {e}")

        if pdf_url:
            sb_update("rdo_master", {"id": rdo_id}, {"pdf_url": pdf_url})

        return {"ok": bool(pdf_url), "pdf_url": pdf_url}

    except Exception as e:
        logger.error(f"generate_rdo_pdf error: {e}")
        return {"ok": False, "error": str(e)}
