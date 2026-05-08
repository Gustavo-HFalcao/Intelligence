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


def _safe(text: str) -> str:
    """Substitui caracteres fora do Latin-1 por equivalentes ASCII para fpdf2/Helvetica."""
    replacements = {
        '—': '-', '–': '-',   # em dash, en dash
        '‘': "'", '’': "'",   # aspas simples curvas
        '“': '"', '”': '"',   # aspas duplas curvas
        '…': '...', '•': '*', # reticências, bullet
        '°': 'o', '·': '.',   # grau, ponto médio
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode('latin-1', errors='replace').decode('latin-1')


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


def _build_rdo_pdf_fpdf(rdo: Dict, atividades: list, evidencias: list | None = None) -> Optional[bytes]:  # noqa: C901
    """Gera PDF executivo de RDO — layout profissional para entrega ao cliente."""
    try:
        from fpdf import FPDF, XPos, YPos

        # ── Paleta ───────────────────────────────────────────────────────────────
        COPPER  = (201, 139,  42)   # dourado
        TEAL    = ( 42, 157, 143)   # verde-azulado
        DARK    = ( 26,  26,  46)   # header escuro
        NAVY    = ( 38,  38,  62)   # faixa secundária
        LIGHT   = (250, 248, 243)   # zebra claro
        WHITE   = (255, 255, 255)
        GRAY    = (120, 120, 120)
        MIDGRAY = (200, 200, 200)
        RED     = (220,  53,  69)
        GREEN   = ( 40, 167,  69)

        # ── Extração de dados ─────────────────────────────────────────────────────
        contrato  = _safe(str(rdo.get("contrato") or ""))
        data_raw  = str(rdo.get("data") or rdo.get("data_rdo") or "")[:10]
        try:
            from datetime import date as _d
            data_fmt = _d.fromisoformat(data_raw).strftime("%d/%m/%Y")
        except Exception:
            data_fmt = data_raw
        status    = _safe(str(rdo.get("status") or ""))
        turno     = _safe(str(rdo.get("turno") or ""))
        equipe    = _safe(str(rdo.get("equipe_alocada") or ""))
        clima     = _safe(str(rdo.get("condicao_climatica") or rdo.get("clima") or ""))
        h_ini     = _safe(str(rdo.get("hora_inicio") or "")[:5])
        h_fim     = _safe(str(rdo.get("hora_termino") or "")[:5])
        local_    = _safe(str(rdo.get("localizacao") or ""))
        km        = _safe(str(rdo.get("km_percorrido") or ""))
        obs       = _safe(str(rdo.get("observacoes") or ""))
        ori       = _safe(str(rdo.get("orientacao") or ""))
        ai        = _safe(str(rdo.get("ai_summary") or ""))
        sig_name  = _safe(str(rdo.get("signatory_name") or ""))
        sig_doc   = _safe(str(rdo.get("signatory_doc") or ""))
        sig_b64   = str(rdo.get("signatory_sig_b64") or "")
        chuva     = bool(rdo.get("houve_chuva"))
        interr    = bool(rdo.get("houve_interrupcao"))
        acidente  = bool(rdo.get("houve_acidente"))
        mot_interr = _safe(str(rdo.get("motivo_interrupcao") or ""))
        desc_acid  = _safe(str(rdo.get("descricao_acidente") or ""))

        # ── Classe PDF com header/footer automático ───────────────────────────────
        class RDO_PDF(FPDF):
            def header(self):
                # Barra topo escura
                self.set_fill_color(*DARK)
                self.rect(0, 0, 210, 22, "F")
                # Linha dourada embaixo do header
                self.set_fill_color(*COPPER)
                self.rect(0, 22, 210, 1.2, "F")
                # Título
                self.set_xy(12, 5)
                self.set_font("Helvetica", "B", 13)
                self.set_text_color(*COPPER)
                self.cell(120, 8, "RELAT\xd3RIO DI\xc1RIO DE OBRA")
                # Contrato + data (direita)
                self.set_font("Helvetica", "", 8)
                self.set_text_color(*MIDGRAY)
                self.set_xy(130, 5)
                self.cell(0, 5, contrato, align="R")
                self.set_xy(130, 11)
                self.cell(0, 5, f"{data_fmt}  |  {status}", align="R")
                self.set_y(28)

            def footer(self):
                self.set_y(-12)
                self.set_fill_color(*DARK)
                self.rect(0, self.get_y() - 2, 210, 16, "F")
                self.set_font("Helvetica", "I", 7)
                self.set_text_color(*GRAY)
                self.cell(0, 8,
                    f"Bomtempo Intelligence  |  {contrato}  |  {data_fmt}  |  "
                    f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  "
                    f"Pag. {self.page_no()}",
                    align="C")

        pdf = RDO_PDF()
        pdf.set_margins(12, 30, 12)
        pdf.set_auto_page_break(auto=True, margin=16)
        pdf.add_page()

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 1 — IDENTIFICAÇÃO (faixa azul escura sob o header)
        # ════════════════════════════════════════════════════════════════════════
        pdf.set_fill_color(*NAVY)
        pdf.rect(0, 23.2, 210, 0, "F")  # já coberto pelo header

        # ── KPI cards: 6 colunas ──────────────────────────────────────────────
        def kpi_card(x, y, w, label, value, color=None):
            pdf.set_fill_color(248, 246, 240)
            pdf.set_draw_color(*COPPER)
            pdf.rect(x, y, w, 16, "FD")
            # Linha dourada no topo do card
            pdf.set_fill_color(*COPPER)
            pdf.rect(x, y, w, 1, "F")
            pdf.set_xy(x + 2, y + 2.5)
            pdf.set_font("Helvetica", "B", 6.5)
            pdf.set_text_color(*GRAY)
            pdf.cell(w - 4, 4, label.upper())
            pdf.set_xy(x + 2, y + 7)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*(color or DARK))
            pdf.cell(w - 4, 6, value[:22] if value else "-")

        horario = f"{h_ini}-{h_fim}" if h_ini and h_fim else (h_ini or h_fim or "-")
        kpi_y = 29
        card_w = 30.5
        gap = 1.2
        kpi_card(12,              kpi_y, card_w, "Data",    data_fmt)
        kpi_card(12+card_w+gap,   kpi_y, card_w, "Turno",   turno)
        kpi_card(12+2*(card_w+gap), kpi_y, card_w, "Hor\xe1rio", horario)
        kpi_card(12+3*(card_w+gap), kpi_y, card_w, "Equipe",  f"{equipe} pessoas" if equipe else "-")
        kpi_card(12+4*(card_w+gap), kpi_y, card_w, "Clima",   clima)
        kpi_card(12+5*(card_w+gap), kpi_y, card_w, "Status",  status,
                 GREEN if status == "Submetido" else COPPER)

        pdf.set_y(kpi_y + 19)

        # Localização + KM (linha fina)
        if local_ or km:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*GRAY)
            loc_line = []
            if local_: loc_line.append(f"Local: {local_}")
            if km:     loc_line.append(f"KM: {km}")
            pdf.cell(0, 5, "  ".join(loc_line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 2 — ATIVIDADES DO DIA
        # ════════════════════════════════════════════════════════════════════════
        def section_title(title, color=COPPER):
            pdf.ln(2)
            pdf.set_fill_color(*color)
            pdf.rect(12, pdf.get_y(), 186, 7, "F")
            pdf.set_xy(14, pdf.get_y() + 0.8)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(*WHITE)
            pdf.cell(0, 5.5, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)

        section_title("ATIVIDADES EXECUTADAS NO DIA")  # Latin-1: sem acento necessário

        # Cabeçalho da tabela
        pdf.set_fill_color(*DARK)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 7.5)
        col_nome = 82
        col_qty  = 22
        col_und  = 14
        col_pct  = 14
        col_ef   = 15
        col_obs  = 186 - col_nome - col_qty - col_und - col_pct - col_ef  # resto

        def th(w, txt, align="L", last=False):
            pdf.cell(w, 6, txt, fill=True, align=align,
                     new_x=XPos.LMARGIN if last else XPos.RIGHT,
                     new_y=YPos.NEXT    if last else YPos.TOP)

        th(col_nome, "  ATIVIDADE")
        th(col_qty,  "QUANTIDADE", "C")
        th(col_und,  "UNIDADE",    "C")
        th(col_pct,  "% ACUM",     "C")
        th(col_ef,   "EFETIVO",    "C")
        th(col_obs,  "OBSERVACAO", last=True)

        pdf.set_font("Helvetica", "", 8)
        for idx, at in enumerate(atividades):
            nome    = _safe(str(at.get("atividade") or at.get("descricao") or "-"))
            unidade = str(at.get("unidade") or "")
            qty     = at.get("quantidade") or 0
            efet_val = at.get("efetivo")
            efet    = str(efet_val) if efet_val is not None else "-"
            obs_v   = _safe(str(at.get("observacao") or ""))
            is_m    = bool(at.get("is_marco"))
            pct_at  = at.get("pct") or at.get("conclusao_pct") or 0

            if is_m:
                qty_disp = "Marco"
                pct_disp = "100%" if at.get("marco_concluido") else "Pend."
            elif unidade == "%":
                qty_disp = f"{int(float(qty))}%"
                pct_disp = f"{int(float(qty))}%"
            else:
                qty_disp = f"{qty:.0f}" if isinstance(qty, float) else str(qty)
                pct_disp = f"{int(float(pct_at))}%" if pct_at else "-"

            fill_bg = LIGHT if idx % 2 == 0 else WHITE
            pdf.set_fill_color(*fill_bg)
            pdf.set_text_color(*DARK)

            row_y = pdf.get_y()
            ROW_H = 6.5  # altura fixa por linha

            # Calcula quantas linhas o nome ocupa na largura disponível
            pdf.set_font("Helvetica", "B" if is_m else "", 7.5)
            nome_disp = "  " + nome[:80]
            sw = pdf.get_string_width(nome_disp)
            n_lines = max(1, int(sw / (col_nome - 1)) + 1) if sw > col_nome - 1 else 1
            row_h = ROW_H * n_lines

            pdf.set_fill_color(*fill_bg)
            pdf.rect(12, row_y, 186, row_h, "F")

            # Nome — multi_cell alinhado ao topo
            pdf.set_xy(12, row_y)
            pdf.set_text_color(*(COPPER if is_m else DARK))
            pdf.multi_cell(col_nome, ROW_H, nome_disp, new_x=XPos.RIGHT, new_y=YPos.TOP)

            # Demais colunas centralizadas verticalmente na linha
            mid_y = row_y + (row_h - ROW_H) / 2
            pdf.set_xy(12 + col_nome, mid_y)
            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(*DARK)
            pdf.cell(col_qty, ROW_H, qty_disp,   align="C")
            pdf.cell(col_und, ROW_H, unidade[:8], align="C")
            pdf.cell(col_pct, ROW_H, pct_disp,   align="C")
            pdf.cell(col_ef,  ROW_H, efet,        align="C")
            pdf.set_font("Helvetica", "I", 7)
            pdf.set_text_color(*GRAY)
            pdf.cell(col_obs, ROW_H, obs_v[:35])

            pdf.set_xy(12, row_y + row_h)

        # Linha de total
        total_efetivo = sum(int(a.get("efetivo") or 0) for a in atividades)
        pdf.set_fill_color(*DARK)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.cell(col_nome + col_qty + col_und + col_pct, 5.5,
                 f"  {len(atividades)} atividade(s) registrada(s)", fill=True)
        pdf.cell(col_ef,  5.5, str(total_efetivo), fill=True, align="C")
        pdf.cell(col_obs, 5.5, "pessoas total", fill=True,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 3 — OCORRÊNCIAS (só se houver)
        # ════════════════════════════════════════════════════════════════════════
        if chuva or interr or acidente:
            section_title("OCORR\xcaNCIAS E INTERCORR\xcaNCIAS", RED)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*DARK)
            if chuva:
                pdf.set_fill_color(230, 240, 255)
                pdf.rect(12, pdf.get_y(), 186, 6, "F")
                pdf.set_xy(14, pdf.get_y())
                pdf.set_text_color(30, 80, 180)
                pdf.cell(0, 6, "Chuva registrada no periodo", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(*DARK)
            if interr:
                pdf.set_fill_color(255, 243, 220)
                pdf.rect(12, pdf.get_y(), 186, 6 if not mot_interr else 11, "F")
                pdf.set_xy(14, pdf.get_y())
                pdf.set_text_color(160, 80, 0)
                pdf.set_font("Helvetica", "B", 8)
                pdf.cell(0, 6, "Interrup\xe7\xe3o de servi\xe7o", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                if mot_interr:
                    pdf.set_xy(14, pdf.get_y())
                    pdf.set_font("Helvetica", "", 7.5)
                    pdf.set_text_color(*DARK)
                    pdf.multi_cell(180, 5, mot_interr[:200])
                pdf.set_text_color(*DARK)
            if acidente:
                pdf.set_fill_color(255, 220, 220)
                pdf.rect(12, pdf.get_y(), 186, 6 if not desc_acid else 11, "F")
                pdf.set_xy(14, pdf.get_y())
                pdf.set_text_color(*RED)
                pdf.set_font("Helvetica", "B", 8)
                pdf.cell(0, 6, "ACIDENTE REGISTRADO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                if desc_acid:
                    pdf.set_xy(14, pdf.get_y())
                    pdf.set_font("Helvetica", "", 7.5)
                    pdf.set_text_color(*DARK)
                    pdf.multi_cell(180, 5, desc_acid[:200])
            pdf.ln(2)

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 4 — OBSERVAÇÕES + ORIENTAÇÃO (lado a lado se couberem)
        # ════════════════════════════════════════════════════════════════════════
        if obs or ori:
            section_title("OBSERVA\xc7\xd5ES E ORIENTA\xc7\xd5ES")
            if obs:
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_text_color(*COPPER)
                pdf.cell(0, 5, "Observa\xe7\xf5es gerais:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*DARK)
                pdf.set_x(12)
                pdf.multi_cell(186, 5, obs[:800])
                pdf.ln(1)
            if ori:
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_text_color(*TEAL)
                pdf.cell(0, 5, "Orienta\xe7\xe3o para amanh\xe3:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*DARK)
                pdf.set_x(12)
                pdf.multi_cell(186, 5, ori[:800])
            pdf.ln(2)

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 5 — EVIDÊNCIAS FOTOGRÁFICAS
        # ════════════════════════════════════════════════════════════════════════
        ev_list = evidencias or []
        if ev_list:
            import httpx as _httpx
            section_title("EVID\xcaNCIAS FOTOGR\xc1FICAS")
            IMG_W = 58
            IMG_H = 44
            GAP   = 4
            per_row = 3
            x_starts = [12, 12 + IMG_W + GAP, 12 + 2 * (IMG_W + GAP)]
            col_idx = 0
            row_y = pdf.get_y() + 1
            for ev in ev_list[:9]:
                url = str(ev.get("foto_url") or ev.get("url_foto") or ev.get("url") or "")
                cap = _safe(str(ev.get("legenda") or ev.get("caption") or ev.get("tipo") or ""))
                if not url:
                    continue
                try:
                    resp = _httpx.get(url, timeout=8.0, follow_redirects=True)
                    if resp.status_code == 200:
                        img_bytes = io.BytesIO(resp.content)
                        ct = resp.headers.get("content-type", "")
                        img_type = "JPEG" if "jpeg" in ct or "jpg" in ct else "PNG" if "png" in ct else "JPEG"
                        x_img = x_starts[col_idx]
                        if row_y + IMG_H + 10 > 270:
                            pdf.add_page()
                            row_y = pdf.get_y() + 1
                            col_idx = 0
                        pdf.image(img_bytes, x=x_img, y=row_y, w=IMG_W, h=IMG_H, type=img_type)
                        if cap:
                            pdf.set_xy(x_img, row_y + IMG_H + 0.5)
                            pdf.set_font("Helvetica", "I", 6.5)
                            pdf.set_text_color(*GRAY)
                            pdf.cell(IMG_W, 4, cap[:40], align="C")
                        col_idx += 1
                        if col_idx >= per_row:
                            col_idx = 0
                            row_y += IMG_H + 6
                            pdf.set_y(row_y)
                except Exception:
                    continue
            if col_idx > 0:
                pdf.set_y(row_y + IMG_H + 6)
            pdf.ln(2)

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 7 — ANÁLISE DE IA
        # ════════════════════════════════════════════════════════════════════════
        if ai:
            # Nova página se restar menos de 60mm
            if pdf.get_y() > 195:
                pdf.add_page()
            section_title("AN\xc1LISE DE INTELIG\xcaNCIA ARTIFICIAL", TEAL)
            ai_y = pdf.get_y()
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*DARK)
            pdf.set_fill_color(242, 250, 248)
            # Conteúdo com recuo de 4mm para deixar espaço para a borda esquerda
            pdf.set_x(16)
            pdf.multi_cell(182, 5, ai, fill=True)
            # Borda esquerda teal (desenhada depois, sem sobrepor texto)
            ai_h = pdf.get_y() - ai_y
            pdf.set_fill_color(*TEAL)
            pdf.rect(12, ai_y, 3, ai_h, "F")
            pdf.ln(3)

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 8 — ASSINATURA
        # ════════════════════════════════════════════════════════════════════════
        if sig_name or sig_doc or sig_b64:
            if pdf.get_y() > 220:
                pdf.add_page()
            section_title("RESPONS\xc1VEL T\xc9CNICO PELA APROVA\xc7\xc3O")
            y_sig = pdf.get_y() + 2

            # Imagem da assinatura digital (base64 JPEG)
            if sig_b64:
                try:
                    import base64
                    raw = sig_b64.split(",", 1)[1] if "," in sig_b64 else sig_b64
                    sig_bytes = base64.b64decode(raw)
                    sig_img = io.BytesIO(sig_bytes)
                    pdf.image(sig_img, x=12, y=y_sig, w=80, h=18, type="JPEG")
                except Exception:
                    pass

            # Linha dourada de assinatura (abaixo da imagem)
            pdf.set_draw_color(*COPPER)
            pdf.line(12, y_sig + 20, 95, y_sig + 20)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*DARK)
            pdf.set_xy(12, y_sig + 22)
            if sig_name: pdf.cell(85, 5, sig_name)
            pdf.set_xy(12, y_sig + 27)
            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(*GRAY)
            if sig_doc:  pdf.cell(85, 4, f"Registro: {sig_doc}")
            pdf.set_xy(12, y_sig + 32)
            pdf.cell(85, 4, f"Data: {data_fmt}")
            pdf.ln(14)

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

        atividades  = sb_select("rdo_atividades",  filters={"rdo_id": rdo_id}, limit=200) or []
        evidencias  = sb_select("rdo_evidencias",  filters={"rdo_id": rdo_id}, limit=30)  or []

        pdf_bytes = _build_rdo_pdf_fpdf(rdo, atividades, evidencias)
        if not pdf_bytes:
            return {"ok": False, "error": "PDF generation failed"}

        from backend.core.config import Config as _Cfg
        contrato = str(rdo.get("contrato") or "rdo").replace("/", "-").replace(" ", "_")
        data_str = str(rdo.get("data") or rdo.get("data_rdo") or "")[:10].replace("-", "")
        filename = f"RDO-{contrato}-{data_str}-{rdo_id[:8]}.pdf"
        storage_path = filename  # path inside bucket, no bucket prefix

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
