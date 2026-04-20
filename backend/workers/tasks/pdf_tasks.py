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
