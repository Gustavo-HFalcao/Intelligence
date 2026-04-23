"""
ReportService — Bomtempo Intelligence
Handles HTML template generation, PDF creation, Supabase CRUD, and AI prompt building
for the Relatórios module.
"""

from __future__ import annotations

import html as _html_lib
import re
from datetime import datetime

from bomtempo.core.config import Config
from bomtempo.core.logging_utils import get_logger
from bomtempo.core.supabase_client import sb_insert, sb_select, sb_storage_upload

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HTML TEMPLATE (inline, no Jinja2 dependency)
# Placeholders use ___KEY___ format to avoid f-string / CSS brace conflicts.
# ─────────────────────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

  :root {
    --copper: #C98B2A;
    --patina: #2A9D8F;
    --danger: #EF4444;
    --warning: #F59E0B;
    --text-dark: #1A1A2E;
    --text-mid: #374151;
    --text-light: #6B7280;
    --bg-page: #F8F9FA;
    --bg-card: #FFFFFF;
    --bg-accent: #F3F4F6;
    --border: #E5E7EB;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Outfit', sans-serif;
    background: var(--bg-page);
    color: var(--text-dark);
    font-size: 13px;
    line-height: 1.5;
  }

  /* ── Cover Page ── */
  .cover {
    background: linear-gradient(135deg, #0B1A14 0%, #0E2B22 50%, #071D15 100%);
    color: white;
    padding: 60px 50px;
    min-height: 230mm;
    position: relative;
  }
  .cover::before {
    content: '';
    position: absolute; top: 0; right: 0;
    width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(201,139,42,0.15) 0%, transparent 70%);
  }
  .cover-tag {
    font-family: 'Rajdhani', sans-serif;
    font-size: 11px; font-weight: 700;
    letter-spacing: 0.25em; text-transform: uppercase;
    color: var(--patina); margin-bottom: 16px;
  }
  .cover-title {
    font-family: 'Rajdhani', sans-serif;
    font-size: 32px; font-weight: 700;
    letter-spacing: 0.08em; line-height: 1.1;
    color: var(--copper); margin-bottom: 8px;
  }
  .cover-subtitle {
    font-size: 16px; color: rgba(255,255,255,0.75);
    margin-bottom: 24px; font-weight: 300;
  }
  .cover-meta {
    display: flex; gap: 24px; flex-wrap: wrap;
  }
  .cover-badge {
    background: rgba(201,139,42,0.2);
    border: 1px solid var(--copper);
    border-radius: 6px;
    padding: 6px 14px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; color: var(--copper);
  }
  .cover-badge.green {
    background: rgba(42,157,143,0.2);
    border-color: var(--patina);
    color: var(--patina);
  }

  /* ── Sections ── */
  .content { padding: 32px 40px; }

  .section { margin-bottom: 32px; }
  .section-header {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 16px; padding-bottom: 8px;
    border-bottom: 2px solid var(--copper);
  }
  .section-number {
    background: var(--copper); color: white;
    font-family: 'Rajdhani', sans-serif;
    font-size: 11px; font-weight: 700;
    width: 24px; height: 24px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
  }
  .section-title {
    font-family: 'Rajdhani', sans-serif;
    font-size: 15px; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--text-dark);
  }

  /* ── KPI Cards ── */
  .kpi-grid {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 12px; margin-bottom: 16px;
  }
  .kpi-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    border-top: 3px solid var(--copper);
  }
  .kpi-card.green { border-top-color: var(--patina); }
  .kpi-card.red { border-top-color: var(--danger); }
  .kpi-card.yellow { border-top-color: var(--warning); }
  .kpi-label {
    font-size: 10px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.1em;
    color: var(--text-light); margin-bottom: 6px;
  }
  .kpi-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 18px; font-weight: 700;
    color: var(--text-dark);
  }
  .kpi-sub {
    font-size: 10px; color: var(--text-light);
    margin-top: 3px;
  }

  /* ── Table ── */
  table {
    width: 100%; border-collapse: collapse;
    font-size: 12px; background: var(--bg-card);
    border-radius: 8px; overflow: hidden;
    border: 1px solid var(--border);
  }
  thead tr { background: var(--bg-accent); }
  th {
    font-family: 'Rajdhani', sans-serif;
    font-weight: 700; font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.08em;
    color: var(--text-light); padding: 10px 14px; text-align: left;
    border-bottom: 1px solid var(--border);
  }
  td {
    padding: 10px 14px; border-bottom: 1px solid var(--border);
    color: var(--text-mid);
  }
  tr:last-child td { border-bottom: none; }
  tr:hover { background: #FAFAFA; }

  /* ── Progress bar ── */
  .progress-wrap {
    background: var(--border); border-radius: 99px;
    height: 6px; width: 100%; overflow: hidden;
  }
  .progress-fill {
    height: 100%; border-radius: 99px;
    background: var(--patina);
    transition: width 0.3s;
  }
  .progress-fill.over { background: var(--danger); }
  .progress-fill.warn { background: var(--warning); }

  /* ── Badge ── */
  .badge {
    display: inline-block; padding: 2px 10px; border-radius: 99px;
    font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.05em;
  }
  .badge-green { background: rgba(42,157,143,0.15); color: var(--patina); }
  .badge-yellow { background: rgba(245,158,11,0.15); color: var(--warning); }
  .badge-red { background: rgba(239,68,68,0.15); color: var(--danger); }

  /* ── Summary rows ── */
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .info-block {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px 20px;
  }
  .info-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid var(--border); }
  .info-row:last-child { border-bottom: none; }
  .info-key { color: var(--text-light); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
  .info-val { font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 700; color: var(--text-dark); }

  /* ── Footer ── */
  .footer {
    background: linear-gradient(135deg, #0B1A14, #071D15);
    color: rgba(255,255,255,0.5);
    padding: 20px 40px;
    display: flex; justify-content: space-between; align-items: center;
    font-size: 10px; letter-spacing: 0.05em;
  }
  .footer-brand {
    font-family: 'Rajdhani', sans-serif;
    font-weight: 700; font-size: 14px;
    color: var(--copper); letter-spacing: 0.15em;
  }
  .footer-conf {
    background: rgba(239,68,68,0.2);
    border: 1px solid rgba(239,68,68,0.4);
    color: rgba(239,68,68,0.8);
    padding: 3px 10px; border-radius: 4px;
    font-size: 9px; text-transform: uppercase; letter-spacing: 0.15em;
  }

  /* ── Print / PDF rules ── */
  @media print {
    body { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
  }

  /* ── Page-break control ── */
  /* Content starts on page 2 — avoids Chromium blank-first-page bug with page-break-after on first element */
  .content { page-break-before: always; }

  /* Keep section headers with their content — but allow breaks inside long sections */
  .section-header { page-break-after: avoid; }

  /* KPI grid and cards must never split across pages */
  .kpi-grid { page-break-inside: avoid; }
  .kpi-card { page-break-inside: avoid; }

  /* Two-column info blocks */
  .two-col { page-break-inside: avoid; }
  .info-block { page-break-inside: avoid; }

  /* Tables: prevent orphan header rows */
  table { page-break-inside: auto; }
  thead { display: table-header-group; }
  tr { page-break-inside: avoid; }
  td, th { orphans: 3; widows: 3; }

  /* Footer always at bottom of last page */
  .footer { page-break-before: avoid; }
</style>
</head>
<body>

<!-- ── COVER ── -->
<div class="cover">
  <div class="cover-tag">BOMTEMPO INTELLIGENCE · RELATÓRIO EXECUTIVO</div>
  <div class="cover-title">RELATÓRIO DE OBRA</div>
  <div class="cover-subtitle">___CONTRATO___ · ___CLIENTE___</div>
  <div class="cover-meta">
    <span class="cover-badge">DATA: ___DATA_GERACAO___</span>
    <span class="cover-badge green">STATUS: ___STATUS___</span>
    <span class="cover-badge">GERADO POR: ___GERADO_POR___</span>
  </div>
</div>

<div class="content">

  <!-- ── SECTION 1: Resumo Executivo ── -->
  <div class="section">
    <div class="section-header">
      <span class="section-number">1</span>
      <span class="section-title">Resumo Executivo</span>
    </div>
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Orçamento Planejado</div>
        <div class="kpi-value">___BUDGET_PLAN___</div>
        <div class="kpi-sub">Budget contratado</div>
      </div>
      <div class="kpi-card ___BUDGET_CARD_CLASS___">
        <div class="kpi-label">Realizado</div>
        <div class="kpi-value">___BUDGET_REAL___</div>
        <div class="kpi-sub">Variação: ___BUDGET_VAR___</div>
      </div>
      <div class="kpi-card green">
        <div class="kpi-label">% Execução</div>
        <div class="kpi-value">___EXEC_PCT___</div>
        <div class="kpi-sub">Avanço físico médio</div>
      </div>
      <div class="kpi-card ___RISCO_CARD_CLASS___">
        <div class="kpi-label">Score de Risco</div>
        <div class="kpi-value">___RISCO_VAL___</div>
        <div class="kpi-sub">___RISCO_LABEL___</div>
      </div>
    </div>
  </div>

  <!-- ── SECTION 2: Progresso por Disciplina ── -->
  <div class="section">
    <div class="section-header">
      <span class="section-number">2</span>
      <span class="section-title">Progresso por Disciplina</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>Disciplina</th>
          <th>% Previsto</th>
          <th>% Realizado</th>
          <th>Status</th>
          <th>Progresso Visual</th>
        </tr>
      </thead>
      <tbody>
        ___DISCIPLINAS_ROWS___
      </tbody>
    </table>
    <div style="margin-top:16px; overflow-x:auto;">___DISC_SVG_CHART___</div>
  </div>

  <!-- ── SECTION 3: Desempenho Orçamentário ── -->
  <div class="section">
    <div class="section-header">
      <span class="section-number">3</span>
      <span class="section-title">Desempenho Orçamentário</span>
    </div>
    <div class="info-block">
      <div class="info-row">
        <span class="info-key">Valor Planejado</span>
        <span class="info-val">___BUDGET_PLAN___</span>
      </div>
      <div class="info-row">
        <span class="info-key">Valor Realizado</span>
        <span class="info-val">___BUDGET_REAL___</span>
      </div>
      <div class="info-row">
        <span class="info-key">Variação</span>
        <span class="info-val">___BUDGET_VAR___</span>
      </div>
      <div class="info-row">
        <span class="info-key">Taxa de Execução</span>
        <span class="info-val">___EXEC_RATE___</span>
      </div>
      <div style="margin-top:12px; margin-bottom:4px; font-size:11px; color:var(--text-light);">
        Utilização do orçamento: ___BUDGET_BAR_PCT___%
      </div>
      <div class="progress-wrap">
        <div class="progress-fill ___BUDGET_BAR_CLASS___" style="width: ___BUDGET_BAR_PCT___%"></div>
      </div>
    </div>
    <div style="margin-top:16px; overflow-x:auto;">___BUDGET_SVG_CHART___</div>
  </div>

  <!-- ── SECTION 4: Equipe de Campo ── -->
  <div class="section">
    <div class="section-header">
      <span class="section-number">4</span>
      <span class="section-title">Equipe de Campo</span>
    </div>
    <div class="two-col">
      <div class="info-block">
        <div class="info-row">
          <span class="info-key">Efetivo Hoje</span>
          <span class="info-val">___EQUIPE_VAL___</span>
        </div>
        <div class="info-row">
          <span class="info-key">Situação</span>
          <span class="info-val">___EQUIPE_SUB___</span>
        </div>
      </div>
      <div class="info-block">
        <div class="info-row">
          <span class="info-key">Disciplinas em Risco</span>
          <span class="info-val">___DISC_VAL___</span>
        </div>
        <div class="info-row">
          <span class="info-key">Avaliação</span>
          <span class="info-val">___DISC_SUB___</span>
        </div>
      </div>
    </div>
  </div>

  <!-- ── SECTION 5: Cronograma ── -->
  <div class="section">
    <div class="section-header">
      <span class="section-number">5</span>
      <span class="section-title">Cronograma</span>
    </div>
    <div class="info-block">
      <div class="info-row">
        <span class="info-key">Contrato</span>
        <span class="info-val">___CONTRATO___</span>
      </div>
      <div class="info-row">
        <span class="info-key">Cliente</span>
        <span class="info-val">___CLIENTE___</span>
      </div>
      <div class="info-row">
        <span class="info-key">Início</span>
        <span class="info-val">___DATA_INICIO___</span>
      </div>
      <div class="info-row">
        <span class="info-key">Previsão de Término</span>
        <span class="info-val">___DATA_FIM___</span>
      </div>
      <div class="info-row">
        <span class="info-key">Localização</span>
        <span class="info-val">___LOCALIZACAO___</span>
      </div>
    </div>
  </div>

</div><!-- /content -->

<!-- ── FOOTER ── -->
<div class="footer">
  <span class="footer-brand">BOMTEMPO INTELLIGENCE</span>
  <span>Gerado em ___DATA_GERACAO___ · ___GERADO_POR___</span>
  <span class="footer-conf">DOCUMENTO CONFIDENCIAL</span>
</div>

</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# MARKDOWN → HTML (for AI report PDF rendering)
# ─────────────────────────────────────────────────────────────────────────────

def _apply_inline_md(text: str) -> str:
    """Apply inline markdown: bold, italic, code — HTML-escaped first."""
    text = _html_lib.escape(text)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


def _md_to_html(text: str) -> str:
    """Convert a subset of Markdown to styled HTML for PDF embedding."""
    if not text:
        return ""
    lines = text.split('\n')
    result: list[str] = []
    in_ul = in_ol = in_table = False
    t_headers: list[str] = []
    t_body: list[list[str]] = []
    t_sep_seen = False

    def _row_cells(s: str) -> list[str]:
        return [c.strip() for c in s.strip().strip('|').split('|') if c.strip()]

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            result.append('</ul>')
            in_ul = False
        if in_ol:
            result.append('</ol>')
            in_ol = False

    def close_table() -> None:
        nonlocal in_table, t_sep_seen
        if not in_table:
            return
        in_table = False
        ths = "".join(
            f'<th style="font:700 9px \'Rajdhani\',sans-serif;text-transform:uppercase;'
            f'letter-spacing:0.08em;color:#6B7280;padding:7px 12px;border-bottom:2px solid #E5E7EB;'
            f'text-align:left;background:#F3F4F6;">{_apply_inline_md(h)}</th>'
            for h in t_headers
        )
        thead = f'<thead><tr>{ths}</tr></thead>' if t_headers else ''
        rows_html = ""
        for i, row in enumerate(t_body):
            bg = '#FAFAFA' if i % 2 == 0 else '#FFFFFF'
            tds = "".join(
                f'<td style="font:400 12px \'Outfit\',sans-serif;color:#374151;padding:7px 12px;'
                f'border-bottom:1px solid #F0F0F0;">{_apply_inline_md(c)}</td>'
                for c in row
            )
            rows_html += f'<tr style="background:{bg};">{tds}</tr>'
        result.append(
            f'<table style="width:100%;border-collapse:collapse;margin:12px 0 16px;'
            f'border:1px solid #E5E7EB;border-radius:6px;overflow:hidden;font-size:12px;">'
            f'{thead}<tbody>{rows_html}</tbody></table>'
        )
        t_headers.clear()
        t_body.clear()
        t_sep_seen = False

    for line in lines:
        s = line.strip()

        # ── Table row detection ──────────────────────────────────────────────
        if s.startswith('|') and s.count('|') >= 2:
            cells = _row_cells(s)
            if cells and all(re.match(r'^[-:\s]+$', c) for c in cells):
                # Separator row → end of header, start of body
                t_sep_seen = True
            elif not t_sep_seen:
                # Pre-separator → treat as header row
                if not in_table:
                    close_lists()
                    in_table = True
                t_headers = cells
            else:
                # Post-separator → body row
                t_body.append(cells)
            continue

        # Non-table line → flush pending table first
        if in_table:
            close_table()

        # ── Other block types ────────────────────────────────────────────────
        if s.startswith('# ') or s.startswith('## ') or s.startswith('### '):
            close_lists()
            if s.startswith('### '):
                result.append(f'<h3 class="ai-h3">{_apply_inline_md(s[4:])}</h3>')
            elif s.startswith('## '):
                result.append(f'<h2 class="ai-h2">{_apply_inline_md(s[3:])}</h2>')
            else:
                result.append(f'<h1 class="ai-h1">{_apply_inline_md(s[2:])}</h1>')
        elif s.startswith('---') and all(c == '-' for c in s):
            close_lists()
            result.append('<hr class="ai-hr"/>')
        elif s.startswith('> '):
            close_lists()
            result.append(f'<blockquote class="ai-bq">{_apply_inline_md(s[2:])}</blockquote>')
        elif s.startswith('- ') or s.startswith('* '):
            if not in_ul:
                if in_ol:
                    result.append('</ol>')
                    in_ol = False
                result.append('<ul class="ai-ul">')
                in_ul = True
            result.append(f'<li>{_apply_inline_md(s[2:])}</li>')
        elif re.match(r'^\d+\. ', s):
            if not in_ol:
                if in_ul:
                    result.append('</ul>')
                    in_ul = False
                result.append('<ol class="ai-ol">')
                in_ol = True
            result.append(f'<li>{_apply_inline_md(re.sub(r"^\d+\. ", "", s))}</li>')
        elif s == '':
            close_lists()
            result.append('<div class="ai-gap"></div>')
        else:
            close_lists()
            result.append(f'<p class="ai-p">{_apply_inline_md(s)}</p>')

    close_lists()
    if in_table:
        close_table()
    return '\n'.join(result)


# ─────────────────────────────────────────────────────────────────────────────
# HTML/CSS CHART GENERATORS (WeasyPrint-compatible — no SVG)
# ─────────────────────────────────────────────────────────────────────────────

def _build_s_curve_svg(planned_series: list, actual_series: list) -> str:
    """
    Gera SVG puro da curva S (avanço planejado vs realizado ao longo do tempo).
    planned_series: [{label, value}] — valores cumulativos %
    actual_series:  [{label, value}] — valores cumulativos %
    Funciona 100% no Playwright/Chromium sem dependência de JS ou Recharts.
    """
    if not planned_series and not actual_series:
        return ""

    W, H = 520, 180
    PAD_L, PAD_R, PAD_T, PAD_B = 40, 16, 12, 32

    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    # Normaliza para max 100
    all_labels = [p["label"] for p in (planned_series or actual_series)]
    n = len(all_labels)
    if n < 2:
        return ""

    def to_xy(series: list) -> list:
        pts = []
        for i, item in enumerate(series):
            x = PAD_L + (i / (n - 1)) * plot_w
            y = PAD_T + (1 - min(100, max(0, float(item.get("value", 0)))) / 100) * plot_h
            pts.append((x, y))
        return pts

    def pts_to_path(pts: list) -> str:
        if not pts:
            return ""
        cmds = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
        for px, py in pts[1:]:
            cmds.append(f"L {px:.1f} {py:.1f}")
        return " ".join(cmds)

    plan_pts = to_xy(planned_series) if planned_series else []
    actual_pts = to_xy(actual_series) if actual_series else []

    # Grid lines horizontais em 0, 25, 50, 75, 100%
    grid_lines = ""
    for pct in (0, 25, 50, 75, 100):
        y = PAD_T + (1 - pct / 100) * plot_h
        label_x = PAD_L - 6
        grid_lines += (
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L + plot_w}" y2="{y:.1f}" '
            f'stroke="#E5E7EB" stroke-width="1"/>'
            f'<text x="{label_x}" y="{y + 4:.1f}" font-size="8" fill="#9CA3AF" '
            f'text-anchor="end" font-family="JetBrains Mono, monospace">{pct}%</text>'
        )

    # Labels do eixo X
    x_labels = ""
    step = max(1, n // 6)
    for i in range(0, n, step):
        x = PAD_L + (i / (n - 1)) * plot_w
        label = all_labels[i][:8]
        x_labels += (
            f'<text x="{x:.1f}" y="{H - PAD_B + 14}" font-size="7" fill="#9CA3AF" '
            f'text-anchor="middle" font-family="Outfit, sans-serif">{_html_lib.escape(label)}</text>'
        )

    # Paths
    plan_path = pts_to_path(plan_pts)
    actual_path = pts_to_path(actual_pts)

    plan_elem = (
        f'<path d="{plan_path}" fill="none" stroke="rgba(201,139,42,0.6)" '
        f'stroke-width="1.5" stroke-dasharray="4 3"/>'
    ) if plan_path else ""

    actual_elem = (
        f'<path d="{actual_path}" fill="none" stroke="#2A9D8F" stroke-width="2"/>'
    ) if actual_path else ""

    # Pontos finais com valor
    dot_elems = ""
    if actual_pts:
        lx, ly = actual_pts[-1]
        val = actual_series[-1].get("value", 0)
        dot_elems += (
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="#2A9D8F"/>'
            f'<text x="{lx + 6:.1f}" y="{ly - 4:.1f}" font-size="8" fill="#2A9D8F" '
            f'font-weight="700" font-family="JetBrains Mono, monospace">{val:.0f}%</text>'
        )

    legend = (
        f'<line x1="{PAD_L}" y1="{H - 4}" x2="{PAD_L + 20}" y2="{H - 4}" '
        f'stroke="rgba(201,139,42,0.6)" stroke-width="1.5" stroke-dasharray="4 3"/>'
        f'<text x="{PAD_L + 24}" y="{H}" font-size="8" fill="#9CA3AF" '
        f'font-family="Outfit, sans-serif">Planejado</text>'
        f'<line x1="{PAD_L + 80}" y1="{H - 4}" x2="{PAD_L + 100}" y2="{H - 4}" '
        f'stroke="#2A9D8F" stroke-width="2"/>'
        f'<text x="{PAD_L + 104}" y="{H}" font-size="8" fill="#9CA3AF" '
        f'font-family="Outfit, sans-serif">Realizado</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H + 14}" width="100%" height="{H + 14}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block;margin:10px 0;">'
        f'<rect width="{W}" height="{H}" fill="white" rx="6"/>'
        f'{grid_lines}'
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T + plot_h}" '
        f'stroke="#D1D5DB" stroke-width="1"/>'
        f'{plan_elem}{actual_elem}{dot_elems}{x_labels}{legend}'
        f'</svg>'
    )


def _md_to_html_sections(md_text: str) -> str:
    """
    Converte Markdown com marcadores ---PAGE--- para HTML com page-break semântico.
    A IA deve usar '---PAGE---' em linha isolada antes de cada seção principal.
    Garante que nenhuma seção seja cortada no meio — cada ## vira uma div protegida.
    """
    if not md_text:
        return ""

    # Divide em segmentos por ---PAGE---
    segments = md_text.split("\n---PAGE---\n")
    html_parts = []

    for i, segment in enumerate(segments):
        segment = segment.strip()
        if not segment:
            continue
        page_break = ' style="page-break-before:always;"' if i > 0 else ""
        inner_html = _md_to_html(segment)
        html_parts.append(
            f'<div class="report-page-section avoid-break"{page_break}>'
            f'{inner_html}'
            f'</div>'
        )

    return "\n".join(html_parts)


def _build_discipline_svg(disciplinas: list) -> str:
    """HTML/CSS horizontal dual-bar chart per discipline (previsto + realizado)."""
    if not disciplinas:
        return '<p style="color:#9CA3AF;font-size:12px;text-align:center;padding:20px 0;font-family:Outfit,sans-serif;">Sem dados de disciplina disponíveis</p>'

    rows_html = ""
    for d in disciplinas:
        name = str(d.get("categoria", d.get("name", d.get("disciplina", "—"))))
        name_esc = _html_lib.escape(name[:28])
        prev = min(100.0, max(0.0, float(d.get("previsto_pct", 0) or 0)))
        real = min(100.0, max(0.0, float(d.get("realizado_pct", 0) or 0)))
        diff = real - prev
        color = "#2A9D8F" if diff >= 0 else ("#F59E0B" if diff >= -10 else "#EF4444")
        status = "Em Dia" if diff >= 0 else ("Atenção" if diff >= -10 else "Atrasado")
        status_color = "#2A9D8F" if diff >= 0 else ("#F59E0B" if diff >= -10 else "#EF4444")

        rows_html += f"""
        <tr>
          <td style="font:600 11px/1.4 'Outfit',sans-serif;color:#374151;padding:7px 10px 7px 0;width:160px;vertical-align:middle;">{name_esc}</td>
          <td style="padding:7px 8px;vertical-align:middle;">
            <div style="background:#E5E7EB;border-radius:3px;height:7px;overflow:hidden;margin-bottom:3px;">
              <div style="background:rgba(201,139,42,0.45);height:7px;width:{prev:.0f}%;"></div>
            </div>
            <div style="background:#E5E7EB;border-radius:3px;height:7px;overflow:hidden;">
              <div style="background:{color};height:7px;width:{real:.0f}%;"></div>
            </div>
          </td>
          <td style="font:700 10px/1 'JetBrains Mono',monospace;color:{color};text-align:right;padding:7px 0 7px 8px;width:80px;white-space:nowrap;vertical-align:middle;">
            {real:.0f}%<br><span style="font:400 9px 'Outfit',sans-serif;color:#9CA3AF;">meta {prev:.0f}%</span>
          </td>
          <td style="font:700 9px 'Outfit',sans-serif;color:{status_color};text-align:right;padding:7px 0 7px 8px;width:60px;vertical-align:middle;">{status}</td>
        </tr>"""

    return f"""
<div style="margin-top:16px;padding:16px 20px;background:#F8F9FA;border-radius:10px;border:1px solid #E5E7EB;">
  <table style="width:100%;border-collapse:collapse;">
    <thead>
      <tr style="border-bottom:2px solid #E5E7EB;">
        <th style="font:700 9px 'Rajdhani',sans-serif;letter-spacing:0.1em;color:#9CA3AF;text-align:left;padding:0 10px 8px 0;text-transform:uppercase;">Disciplina</th>
        <th style="font:700 9px 'Rajdhani',sans-serif;letter-spacing:0.1em;color:#9CA3AF;text-align:left;padding:0 8px 8px;text-transform:uppercase;">
          <span style="color:rgba(201,139,42,0.8);">&#9632;</span> Previsto &nbsp;
          <span style="color:#2A9D8F;">&#9632;</span> Realizado
        </th>
        <th style="font:700 9px 'Rajdhani',sans-serif;letter-spacing:0.1em;color:#9CA3AF;text-align:right;padding:0 0 8px 8px;text-transform:uppercase;">%</th>
        <th style="font:700 9px 'Rajdhani',sans-serif;letter-spacing:0.1em;color:#9CA3AF;text-align:right;padding:0 0 8px 8px;text-transform:uppercase;">Status</th>
      </tr>
    </thead>
    <tbody>{rows_html}
    </tbody>
  </table>
</div>"""


def _build_budget_svg(fmt: dict) -> str:
    """HTML/CSS budget utilization gauge with KPI summary table."""
    pct  = min(100.0, max(0.0, float(fmt.get("budget_bar_pct", 0) or 0)))
    over = bool(fmt.get("budget_over", False))
    color = "#EF4444" if over else ("#F59E0B" if pct > 80 else "#2A9D8F")

    def _v(key: str) -> str:
        v = fmt.get(key)
        if v is None or str(v).strip() in ("", "None", "—"):
            return "—"
        s = str(v)
        return _html_lib.escape(s[:20] + ("…" if len(s) > 20 else ""))

    plan = _v("budget_planejado_fmt")
    real = _v("budget_realizado_fmt")
    var_ = _v("budget_variacao_fmt")
    rate = _v("budget_exec_rate_fmt")

    # Bar fill background with gradient stripe for over-budget
    fill_bg = f"linear-gradient(90deg, {color} 0%, {color}CC {100}%)" if not over else f"repeating-linear-gradient(45deg, {color} 0px, {color} 8px, #C0392B 8px, #C0392B 16px)"

    return f"""
<div style="margin-top:16px;padding:16px 20px;background:#F8F9FA;border-radius:10px;border:1px solid #E5E7EB;">
  <p style="font:700 9px 'Rajdhani',sans-serif;letter-spacing:0.12em;color:#6B7280;text-transform:uppercase;margin:0 0 10px 0;">EXECU&#199;&#195;O OR&#199;AMENT&#193;RIA</p>
  <div style="background:#E5E7EB;border-radius:6px;height:24px;overflow:hidden;margin-bottom:6px;">
    <div style="background:{fill_bg};height:24px;width:{pct:.0f}%;border-radius:6px;"></div>
  </div>
  <p style="text-align:center;font:700 15px 'JetBrains Mono',monospace;color:{color};margin:0 0 14px 0;">{pct:.0f}% utilizado</p>
  <table style="width:100%;border-collapse:collapse;border-top:1px solid #E5E7EB;">
    <tr>
      <td style="text-align:center;border-right:1px solid #E5E7EB;padding:10px 8px;">
        <p style="font:400 9px 'Outfit',sans-serif;color:#9CA3AF;margin:0 0 4px 0;text-transform:uppercase;letter-spacing:0.08em;">Planejado</p>
        <p style="font:700 13px 'JetBrains Mono',monospace;color:#C98B2A;margin:0;">{plan}</p>
      </td>
      <td style="text-align:center;border-right:1px solid #E5E7EB;padding:10px 8px;">
        <p style="font:400 9px 'Outfit',sans-serif;color:#9CA3AF;margin:0 0 4px 0;text-transform:uppercase;letter-spacing:0.08em;">Realizado</p>
        <p style="font:700 13px 'JetBrains Mono',monospace;color:{color};margin:0;">{real}</p>
      </td>
      <td style="text-align:center;border-right:1px solid #E5E7EB;padding:10px 8px;">
        <p style="font:400 9px 'Outfit',sans-serif;color:#9CA3AF;margin:0 0 4px 0;text-transform:uppercase;letter-spacing:0.08em;">Varia&#231;&#227;o</p>
        <p style="font:700 13px 'JetBrains Mono',monospace;color:{color};margin:0;">{var_}</p>
      </td>
      <td style="text-align:center;padding:10px 8px;">
        <p style="font:400 9px 'Outfit',sans-serif;color:#9CA3AF;margin:0 0 4px 0;text-transform:uppercase;letter-spacing:0.08em;">Taxa Exec.</p>
        <p style="font:700 13px 'JetBrains Mono',monospace;color:{color};margin:0;">{rate}</p>
      </td>
    </tr>
  </table>
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# AI HTML TEMPLATE (for AI/Custom report PDF)
# ─────────────────────────────────────────────────────────────────────────────

_AI_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;700&display=swap');
  :root { --copper:#C98B2A; --patina:#2A9D8F; --danger:#EF4444; --warning:#F59E0B; --text:#1A1A2E; --mid:#374151; --light:#6B7280; --border:#E5E7EB; --bg:#F8F9FA; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:'Outfit',sans-serif; background:var(--bg); color:var(--text); font-size:13px; line-height:1.6; }
  .cover { background:linear-gradient(135deg,#0B1A14 0%,#0E2B22 50%,#071D15 100%); color:#fff; padding:48px 40px; position:relative; overflow:hidden; }
  .cover::before { content:''; position:absolute; top:0; right:0; width:280px; height:280px; background:radial-gradient(circle,rgba(201,139,42,.18) 0%,transparent 70%); }
  .cover-tag { font-family:'Rajdhani',sans-serif; font-size:11px; font-weight:700; letter-spacing:.25em; text-transform:uppercase; color:var(--patina); margin-bottom:12px; }
  .cover-title { font-family:'Rajdhani',sans-serif; font-size:28px; font-weight:700; letter-spacing:.08em; color:var(--copper); margin-bottom:6px; }
  .cover-sub { font-size:15px; color:rgba(255,255,255,.7); margin-bottom:20px; font-weight:300; }
  .cover-meta { display:flex; gap:16px; flex-wrap:wrap; }
  .badge { background:rgba(201,139,42,.2); border:1px solid var(--copper); border-radius:6px; padding:5px 12px; font-family:'JetBrains Mono',monospace; font-size:10px; color:var(--copper); }
  .badge.teal { background:rgba(42,157,143,.2); border-color:var(--patina); color:var(--patina); }
  .content { padding:28px 36px; }
  .section { margin-bottom:28px; }
  .sec-hdr { display:flex; align-items:center; gap:8px; margin-bottom:14px; padding-bottom:6px; border-bottom:2px solid var(--copper); }
  .sec-num { background:var(--copper); color:#fff; font-family:'Rajdhani',sans-serif; font-size:11px; font-weight:700; width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
  .sec-title { font-family:'Rajdhani',sans-serif; font-size:14px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:var(--text); }
  /* AI Content */
  .ai-h1 { font-family:'Rajdhani',sans-serif; font-size:20px; font-weight:700; color:var(--copper); letter-spacing:.05em; margin:18px 0 10px; page-break-after:avoid; }
  .ai-h2 { font-family:'Rajdhani',sans-serif; font-size:16px; font-weight:700; color:var(--text); letter-spacing:.08em; text-transform:uppercase; border-bottom:1px solid rgba(201,139,42,.35); padding-bottom:5px; margin:16px 0 8px; page-break-after:avoid; }
  .ai-h3 { font-size:14px; font-weight:600; color:var(--patina); margin:12px 0 6px; page-break-after:avoid; }
  .ai-p { font-size:13px; color:var(--mid); line-height:1.7; margin-bottom:8px; orphans:3; widows:3; }
  .ai-gap { height:10px; }
  .ai-hr { border:none; border-top:1px solid var(--border); margin:14px 0; }
  .ai-ul,.ai-ol { margin:6px 0 10px 20px; page-break-inside:avoid; }
  .ai-ul li,.ai-ol li { font-size:12px; color:var(--mid); margin-bottom:4px; line-height:1.6; }
  .ai-bq { border-left:3px solid var(--copper); padding:6px 14px; margin:10px 0; background:rgba(201,139,42,.06); color:var(--mid); font-style:italic; font-size:12px; page-break-inside:avoid; }
  code { font-family:'JetBrains Mono',monospace; font-size:11px; background:#F3F4F6; padding:1px 5px; border-radius:3px; color:var(--patina); }
  strong { font-weight:700; color:var(--text); }
  em { font-style:italic; color:var(--light); }
  table { page-break-inside:auto; }
  thead { display:table-header-group; }
  tr { page-break-inside:avoid; }
  td,th { orphans:3; widows:3; }
  .section { page-break-inside:avoid; }
  .sec-hdr { page-break-after:avoid; }
  .cover { page-break-after:always; }
  /* Enterprise page-break semântico — seções nunca cortadas no meio */
  .report-page-section { page-break-before:always; }
  .report-page-section:first-child { page-break-before:auto; }
  .avoid-break { page-break-inside:avoid; break-inside:avoid; }
  .footer { background:linear-gradient(135deg,#0B1A14,#071D15); color:rgba(255,255,255,.5); padding:16px 36px; display:flex; justify-content:space-between; align-items:center; font-size:10px; letter-spacing:.04em; page-break-before:avoid; }
  .footer-brand { font-family:'Rajdhani',sans-serif; font-weight:700; font-size:14px; color:var(--copper); letter-spacing:.15em; }
  .footer-conf { background:rgba(239,68,68,.2); border:1px solid rgba(239,68,68,.4); color:rgba(239,68,68,.8); padding:2px 8px; border-radius:4px; font-size:9px; text-transform:uppercase; letter-spacing:.15em; }
  @media print { body { print-color-adjust:exact; -webkit-print-color-adjust:exact; } }
</style>
</head>
<body>
<div class="cover">
  <div class="cover-tag">BOMTEMPO INTELLIGENCE · ANÁLISE IA GENERATIVA</div>
  <div class="cover-title">___APPROACH_LABEL___</div>
  <div class="cover-sub">___CONTRATO___ · ___CLIENTE___</div>
  <div class="cover-meta">
    <span class="badge">DATA: ___DATA___</span>
    <span class="badge teal">ABORDAGEM: ___ABORDAGEM___</span>
    <span class="badge">GERADO POR: ___GERADO_POR___</span>
  </div>
</div>
<div class="content">
  <div class="section">
    <div class="sec-hdr"><span class="sec-num">1</span><span class="sec-title">Progresso por Disciplina</span></div>
    ___DISC_CHART___
  </div>
  <div class="section">
    <div class="sec-hdr"><span class="sec-num">2</span><span class="sec-title">Desempenho Orçamentário</span></div>
    ___BUDGET_CHART___
  </div>
  <div class="section">
    <div class="sec-hdr"><span class="sec-num">3</span><span class="sec-title">Análise Gerada por IA</span></div>
    <div class="ai-content">___AI_BODY___</div>
  </div>
</div>
<div class="footer">
  <span class="footer-brand">BOMTEMPO INTELLIGENCE</span>
  <span>Gerado em ___DATA___ · ___GERADO_POR___</span>
  <span class="footer-conf">DOCUMENTO CONFIDENCIAL</span>
</div>
</body></html>
"""

# ─────────────────────────────────────────────────────────────────────────────
# AI PROMPT PERSONAS
# ─────────────────────────────────────────────────────────────────────────────

_PERSONAS: dict[str, str] = {
    "estrategica": (
        "Você é um consultor estratégico sênior de infraestrutura preparando um brief executivo "
        "para a diretoria e investidores. Escreva em tom assertivo, orientado a decisão e alto nível. "
        "OBRIGATÓRIO: logo após o título principal (# Título), insira um 'Bottom Line' em uma única frase "
        "dentro de um blockquote markdown (> Frase de impacto aqui.), sintetizando a situação em uma linha "
        "executiva incisiva com base nos dados fornecidos. "
        "Desenvolva: riscos estratégicos, pontos de atenção e recomendações de ação prioritária. "
        "Use linguagem corporativa refinada. Cite KPIs com contexto APENAS os números do bloco de dados. "
        "PROIBIDO: inventar benchmarks, médias de mercado ou indicadores não fornecidos."
    ),
    "analitica": (
        "Você é um analista financeiro sênior em uma firma de consultoria. "
        "Produza uma análise quantitativa detalhada com foco em variações orçamentárias, "
        "eficiência de execução e desvios observados. "
        "Cite APENAS os números presentes no bloco de dados — NUNCA estime, projete ou extrapole valores. "
        "NÃO mencione TIR, VPL, EVA, WCN, DMC, LOC, CPI, SPI, WACC ou qualquer índice financeiro "
        "que não esteja explicitamente nos dados fornecidos. "
        "NÃO crie cenários probabilísticos, simulações Monte Carlo ou projeções especulativas. "
        "Se um dado não estiver disponível, escreva 'Dado não disponível no sistema'. "
        "Use estrutura: Situação Atual → Análise de Desvios → Risco Identificado → Recomendação."
    ),
    "descritiva": (
        "Você é um auditor técnico rigoroso produzindo um laudo técnico formal para fins de auditoria. "
        "Use frases curtas: máximo 15 palavras por frase. Prefira bullet points a parágrafos corridos. "
        "Cite TODOS os dados fornecidos de forma explícita e objetiva. "
        "Onde não houver dado, escreva 'Dado não disponível no sistema' — NUNCA invente ou estime. "
        "PROIBIDO: benchmarks, comparativos com outros projetos, métricas não fornecidas. "
        "Estrutura: Estado Atual → Dados Verificados → Conformidade → Pendências → Conclusão."
    ),
    "operacional": (
        "Você é um gerente de obras experiente escrevendo para a equipe de campo e coordenação técnica. "
        "Foque em disciplinas atrasadas, efetivo e ações práticas no canteiro com base nos dados disponíveis. "
        "NÃO invente dados climáticos, logísticos ou de fornecedores — use apenas o que está no contexto. "
        "PROIBIDO ABSOLUTO: inventar nomes de elementos estruturais (vigas, sapatas, painéis, blocos, pilares), "
        "referências de desenho técnico, quantitativos de material (toneladas, metros, m²), "
        "especificações técnicas (bitolas, tipos de solda, equipamentos), horários de campo ou nomes de equipes. "
        "Ações do plano devem ser genéricas e baseadas APENAS nos desvios de % reportados nas disciplinas. "
        "Organize ações por urgência (URGENTE / CURTO PRAZO / PRÓXIMA SEMANA) — NÃO crie horários fixos "
        "(08:00, 09:30, etc.) nem cronogramas com horas específicas — isso é informação não disponível. "
        "Baseado EXCLUSIVAMENTE nos desvios de % reportados e no efetivo informado. "
        "Linguagem direta, técnica e pragmática. Use bullets para listar ações."
    ),
    "custom": (
        "Você é um gerador de relatórios executivos corporativos especializado em obras e infraestrutura. "
        "Retorne EXCLUSIVAMENTE conteúdo em Markdown estruturado com seções claras. "
        "Use APENAS os dados fornecidos no contexto — NÃO invente números, eventos ou métricas. "
        "Se um campo estiver ausente ou marcado como '—', informe 'Dado não disponível'. "
        "Adapte o tom e foco ao pedido específico do usuário, mas mantenha rigor factual absoluto."
    ),
}

_GUARDRAIL = """
════════════════════════════════════════════════════════════
POLÍTICA ZERO-TOLERÂNCIA — ANTI-ALUCINAÇÃO (NÍVEL ENTERPRISE)
════════════════════════════════════════════════════════════
REGRA ABSOLUTA: Você é um NARRADOR DE DADOS. Seu papel é interpretar e comunicar
os dados fornecidos — NÃO gerar insights baseados em suposições ou conhecimento externo.

▶ PERMITIDO — USE APENAS:
  • Números, percentuais e valores EXPLICITAMENTE listados no bloco [DADOS DO PROJETO]
  • Interpretações qualitativas dos dados fornecidos (ex: "o avanço de X% está Y pp abaixo da meta")
  • Recomendações de ação baseadas em desvios OBSERVADOS nos dados
  • A frase "Dado não disponível no sistema" quando um campo é '—' ou ausente

▶ PROIBIDO ABSOLUTO — NUNCA FAÇA:
  • Inventar ou estimar qualquer valor numérico não presente no contexto
  • Citar TIR, VPL, EVA, WCN, DMC, LOC, CPI, SPI, WACC ou qualquer índice não fornecido
  • Referenciar benchmarks de mercado, médias do setor ou medianas históricas
  • Criar cenários probabilísticos (P10/P50/P90, Monte Carlo, simulações, análise de sensibilidade)
  • Fabricar detalhamento de custos (% equipamentos, % mão de obra, % materiais)
  • Inventar recebíveis, faturamento futuro, fluxo de caixa projetado, contas a pagar
  • Criar cronogramas detalhados ou marcos não presentes nos dados
  • Usar frases como "estima-se que", "historicamente", "tipicamente neste setor", "provavelmente"
  • Adicionar qualquer número com decimais que não esteja explicitamente no contexto
  • Inventar nomes de elementos estruturais: vigas (ex: V-15), sapatas (ex: SP-17), painéis, blocos, pilares
  • Inventar referências de desenho técnico, plantas, revisões (ex: "desenho 123-REV-03")
  • Fabricar quantitativos de material: toneladas de aço, metros de tubo, m² de forma, volumes de concreto
  • Criar especificações de campo: bitolas, diâmetros, revestimentos, espessuras, tipos de solda, equipamentos
  • Inventar horários de atividade de campo: "equipe chega às 08:00", "concretagem prevista sexta"
  • Criar nomes de subcontratados, fornecedores, responsáveis técnicos ou equipes específicas

▶ QUANDO DADOS SÃO INSUFICIENTES:
  Escreva: "Dado não disponível no sistema — análise limitada às informações registradas."
  NUNCA preencha lacunas com estimativas, suposições ou dados típicos do setor.

▶ FORMATO OBRIGATÓRIO:
  • Markdown com seções ## e ###
  • Números sempre com a unidade do contexto (%, R$, dias, pessoas)
  • Ao citar um KPI, referencie o valor exato do contexto
  • ANTES de cada seção principal (## Título), escreva exatamente:
      ---PAGE---
    em linha isolada — isso cria quebra de página correta no PDF
  • A primeira seção NÃO precisa de ---PAGE--- antes dela
  • Conclua cada seção COMPLETAMENTE antes de escrever ---PAGE---

VIOLAÇÃO DESTA POLÍTICA = RELATÓRIO INVÁLIDO PARA USO CORPORATIVO.
════════════════════════════════════════════════════════════
"""


# ─────────────────────────────────────────────────────────────────────────────
# SERVICE CLASS
# ─────────────────────────────────────────────────────────────────────────────

class ReportService:

    # ── HTML Template ────────────────────────────────────────────────────────

    @staticmethod
    def build_static_html(data: dict) -> str:
        """Fill the HTML template with real data from GlobalState snapshots."""
        fmt = data.get("fmt", {})
        obra = data.get("obra", {})
        disciplinas = data.get("disciplinas", [])
        contrato = data.get("contrato", "—")
        cliente = data.get("cliente", "—")
        gerado_por = data.get("gerado_por", "Sistema")
        data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")

        # Budget card class
        budget_over = fmt.get("budget_over", False)
        budget_bar_pct = fmt.get("budget_bar_pct", 0)
        budget_card_class = "red" if budget_over else "green"
        budget_bar_class = "over" if budget_over else ("warn" if budget_bar_pct > 80 else "")

        # Risco card class
        risco_label = fmt.get("risco_label", "—")
        risco_card_class = "red" if "Alto" in risco_label else ("yellow" if "Médio" in risco_label else "green")

        # Status
        avanco = fmt.get("avanco_fmt", "—")
        status_str = "EM ANDAMENTO"
        if avanco != "—":
            try:
                pct = float(avanco.replace("%", ""))
                if pct >= 99:
                    status_str = "CONCLUÍDA"
                elif pct < 10:
                    status_str = "INICIANDO"
            except Exception:
                pass

        # Disciplinas rows
        rows_html = ""
        for d in disciplinas:
            name = d.get("categoria", d.get("name", d.get("disciplina", "—")))
            prev = float(d.get("previsto_pct", 0))
            real = float(d.get("realizado_pct", 0))
            diff = real - prev
            if diff >= 0:
                badge = '<span class="badge badge-green">Em Dia</span>'
            elif diff >= -10:
                badge = '<span class="badge badge-yellow">Atenção</span>'
            else:
                badge = '<span class="badge badge-red">Atrasado</span>'
            bar_pct = min(100, max(0, real))
            bar_class = "over" if diff < -10 else ("warn" if diff < 0 else "")
            rows_html += f"""
            <tr>
              <td><strong>{name}</strong></td>
              <td>{prev:.0f}%</td>
              <td>{real:.0f}%</td>
              <td>{badge}</td>
              <td>
                <div class="progress-wrap">
                  <div class="progress-fill {bar_class}" style="width:{bar_pct}%"></div>
                </div>
              </td>
            </tr>"""

        if not rows_html:
            rows_html = '<tr><td colspan="5" style="text-align:center;color:#999">Sem dados de disciplina</td></tr>'

        html = _HTML_TEMPLATE
        replacements = {
            "___CONTRATO___": contrato,
            "___CLIENTE___": cliente,
            "___DATA_GERACAO___": data_geracao,
            "___STATUS___": status_str,
            "___GERADO_POR___": gerado_por,
            "___BUDGET_PLAN___": fmt.get("budget_planejado_fmt", "—"),
            "___BUDGET_REAL___": fmt.get("budget_realizado_fmt", "—"),
            "___BUDGET_VAR___": fmt.get("budget_variacao_fmt", "—"),
            "___EXEC_PCT___": avanco,
            "___EXEC_RATE___": fmt.get("budget_exec_rate_fmt", "—"),
            "___RISCO_VAL___": fmt.get("risco_val", "—"),
            "___RISCO_LABEL___": risco_label,
            "___BUDGET_CARD_CLASS___": budget_card_class,
            "___RISCO_CARD_CLASS___": risco_card_class,
            "___BUDGET_BAR_PCT___": str(min(100, int(budget_bar_pct))),
            "___BUDGET_BAR_CLASS___": budget_bar_class,
            "___EQUIPE_VAL___": fmt.get("equipe_val", "—"),
            "___EQUIPE_SUB___": fmt.get("equipe_sub", "—"),
            "___DISC_VAL___": fmt.get("disc_val", "—"),
            "___DISC_SUB___": fmt.get("disc_sub", "—"),
            "___DATA_INICIO___": str(obra.get("inicio", "—")),
            "___DATA_FIM___": str(obra.get("termino", "—")),
            "___LOCALIZACAO___": str(obra.get("localizacao", "—")),
            "___DISCIPLINAS_ROWS___": rows_html,
            "___DISC_SVG_CHART___": _build_discipline_svg(disciplinas),
            "___BUDGET_SVG_CHART___": _build_budget_svg(fmt),
        }
        for key, val in replacements.items():
            html = html.replace(key, "—" if (val is None or str(val).strip() in ("", "None")) else str(val))
        return html

    # ── PDF Generation ───────────────────────────────────────────────────────

    @staticmethod
    def generate_pdf(html: str, filename: str) -> tuple[str, str]:
        """
        Generate a PDF from HTML, upload to Supabase Storage.
        Returns (local_path_str, public_url).
        Raises RuntimeError on failure.
        """
        from bomtempo.core.pdf_utils import html_to_pdf

        Config.REPORTS_PDF_DIR.mkdir(parents=True, exist_ok=True)
        pdf_path = Config.REPORTS_PDF_DIR / filename

        html_to_pdf(html, pdf_path)
        logger.info(f"PDF generated: {pdf_path}")

        # Upload to Supabase Storage
        pdf_bytes = pdf_path.read_bytes()
        url = sb_storage_upload(
            Config.REPORTS_BUCKET,
            filename,
            pdf_bytes,
            "application/pdf",
        )
        if not url:
            raise RuntimeError(f"Falha no upload do PDF para Supabase Storage ({filename})")
        return str(pdf_path), url

    # ── Supabase CRUD ─────────────────────────────────────────────────────────

    @staticmethod
    def save_report(record: dict) -> str:
        """Insert record into relatorios table. Returns inserted id."""
        result = sb_insert("relatorios", record)
        if result:
            return result.get("id", "")
        return ""

    @staticmethod
    def load_history(limit: int = 30, client_id: str = "") -> list[dict]:
        """Load recent report history from Supabase."""
        filters = {"client_id": client_id} if client_id else None
        rows = sb_select("relatorios", order="created_at.desc", limit=limit, filters=filters)
        out = []
        for r in rows:
            out.append({
                "id": r.get("id", ""),
                "created_at": r.get("created_at", "")[:16].replace("T", " "),
                "contrato": r.get("contrato", "—"),
                "cliente": r.get("cliente", "—"),
                "tipo": r.get("tipo", "—"),
                "abordagem": r.get("abordagem") or "—",
                "titulo": r.get("titulo", "—"),
                "pdf_url": r.get("pdf_url", ""),
                "created_by": r.get("created_by", "—"),
            })
        return out

    # ── AI HTML Builder (for PDF from streaming text) ─────────────────────────

    @staticmethod
    def build_ai_html(ai_text: str, data: dict, approach: str) -> str:
        """Convert AI markdown text + data into PDF-ready HTML using _AI_HTML_TEMPLATE."""
        approach_labels = {
            "estrategica": "ANÁLISE ESTRATÉGICA",
            "analitica": "ANÁLISE FINANCEIRA DETALHADA",
            "descritiva": "RELATÓRIO DE AUDITORIA TÉCNICA",
            "operacional": "RELATÓRIO OPERACIONAL DE CAMPO",
            "custom": "RELATÓRIO PERSONALIZADO",
        }
        label = approach_labels.get(approach, "ANÁLISE IA GENERATIVA")
        contrato = data.get("contrato", "—")
        cliente = data.get("cliente", "—")
        gerado_por = data.get("gerado_por", "Sistema")
        fmt = data.get("fmt", {})
        disciplinas = data.get("disciplinas", [])
        data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")

        disc_chart = _build_discipline_svg(disciplinas)
        budget_chart = _build_budget_svg(fmt)
        # Usa _md_to_html_sections para respeitar ---PAGE--- e gerar page-breaks corretos
        ai_body = _md_to_html_sections(ai_text) if "---PAGE---" in (ai_text or "") else _md_to_html(ai_text)

        html = _AI_HTML_TEMPLATE
        replacements = {
            "___APPROACH_LABEL___": label,
            "___CONTRATO___": contrato,
            "___CLIENTE___": cliente,
            "___DATA___": data_geracao,
            "___ABORDAGEM___": approach.replace("_", " ").title(),
            "___GERADO_POR___": gerado_por,
            "___DISC_CHART___": disc_chart,
            "___BUDGET_CHART___": budget_chart,
            "___AI_BODY___": ai_body,
        }
        for key, val in replacements.items():
            html = html.replace(key, "—" if (val is None or str(val).strip() in ("", "None")) else str(val))
        return html

    # ── AI Prompt Builder ─────────────────────────────────────────────────────

    @staticmethod
    def build_ai_prompt(approach: str, data: dict, custom_instruction: str = "") -> list[dict]:
        """
        Build the messages list for AI streaming.
        approach: 'estrategica' | 'analitica' | 'descritiva' | 'operacional' | 'custom'
        data: dict with obra/fmt/disciplinas snapshots
        custom_instruction: user's free-text request (only used for 'custom' approach)
        """
        persona = _PERSONAS.get(approach, _PERSONAS["estrategica"])
        system_msg = f"{persona}\n\n{_GUARDRAIL}"

        fmt = data.get("fmt", {})
        obra = data.get("obra", {})
        disciplinas = data.get("disciplinas", [])
        contrato = data.get("contrato", "—")
        cliente = data.get("cliente", "—")

        # Build data context block
        disc_lines_list = []
        disc_at_risk = []
        for d in disciplinas:
            name = d.get('categoria', d.get('name', d.get('disciplina', '?')))
            prev = float(d.get('previsto_pct', 0))
            real = float(d.get('realizado_pct', 0))
            diff = real - prev
            status = "Em Dia" if diff >= 0 else ("Atenção" if diff >= -10 else "ATRASADO")
            disc_lines_list.append(
                f"  - {name}: Previsto {prev:.0f}% / Realizado {real:.0f}% → {status} ({diff:+.0f}pp)"
            )
            if diff < -5:
                disc_at_risk.append(f"{name} ({diff:+.0f}pp)")
        disc_lines = "\n".join(disc_lines_list) or "  (sem dados de disciplina)"
        risk_summary = ", ".join(disc_at_risk) or "Nenhuma disciplina crítica identificada"

        budget_pct = float(fmt.get('budget_bar_pct', 0) or 0)
        budget_over = fmt.get('budget_over', False)
        budget_health = "CRÍTICO - ESTOURO ORÇAMENTÁRIO" if budget_over else (
            "ATENÇÃO - Próximo do limite" if budget_pct > 85 else
            "SAUDÁVEL - Dentro do orçamento"
        )

        is_portfolio = contrato in ("Geral / Portfólio", "Geral", "")
        portfolio_note = (
            "\n\n⚠️ ESCOPO: Visão geral do portfólio de obras — os dados abaixo representam o estado "
            "agregado disponível no sistema. Estruture o relatório como análise de portfólio, "
            "não de obra individual."
        ) if is_portfolio else ""

        # Explicit data inventory — prevents model from inventing missing fields
        not_available_note = (
            "\n\n## ⛔ DADOS NÃO DISPONÍVEIS NO SISTEMA (NÃO INVENTE)\n"
            "Os seguintes dados NÃO existem no sistema e NÃO devem ser mencionados ou estimados:\n"
            "- Recebíveis, contas a pagar, faturamento, fluxo de caixa\n"
            "- TIR, VPL, EVA, WACC, WCN, DMC, LOC, CPI, SPI ou qualquer índice financeiro derivado\n"
            "- Detalhamento de custos por categoria (equipamentos, mão de obra, materiais, subcontratados)\n"
            "- Benchmarks de mercado, médias do setor, comparativos históricos\n"
            "- Dados climáticos, logísticos ou de fornecedores além do que está listado acima\n"
            "- Cronogramas detalhados, marcos, milestones além das datas de início/término\n"
            "- Qualquer número com precisão decimal que não esteja explicitamente listado acima\n"
            "- Nomes de elementos estruturais: vigas (ex: V-15), sapatas (ex: SP-17), painéis, blocos\n"
            "- Referências de desenho técnico, plantas ou revisões (ex: 'desenho 123-REV-03')\n"
            "- Quantitativos de material (aço, concreto, tubo, forma) não presentes nos dados\n"
            "- Especificações técnicas de campo (bitolas, espessuras, tipos de equipamento)\n"
            "- Horários ou datas de atividades específicas de campo além das datas fornecidas\n"
        )

        context = f"""
## ✅ DADOS DISPONÍVEIS NO SISTEMA — USE APENAS ESTES

### IDENTIFICAÇÃO DO PROJETO
- **Contrato:** {contrato}
- **Cliente:** {cliente}
- **Localização:** {obra.get('localizacao', '—')}
- **Status Atual:** {obra.get('status', '—')}
- **Data de Início:** {obra.get('inicio', '—')}
- **Término Previsto:** {obra.get('termino', '—')}
- **Data deste Relatório:** {datetime.now().strftime('%d/%m/%Y %H:%M')}{portfolio_note}

### SITUAÇÃO ORÇAMENTÁRIA
- **Saúde Financeira:** {budget_health}
- **Orçamento Contratado (Planejado):** {fmt.get('budget_planejado_fmt', '—')}
- **Valor Executado (Realizado):** {fmt.get('budget_realizado_fmt', '—')}
- **Variação Orçamentária:** {fmt.get('budget_variacao_fmt', '—')}
- **Taxa de Execução:** {fmt.get('budget_exec_rate_fmt', '—')}
- **Utilização do Orçamento:** {budget_pct:.0f}%
- **Estouro de Budget:** {'SIM ⚠️' if budget_over else 'Não'}

### AVANÇO FÍSICO E RISCO
- **Avanço Físico Médio:** {fmt.get('avanco_fmt', '—')}
- **Score de Risco:** {fmt.get('risco_val', '—')} — {fmt.get('risco_label', '—')}
- **Disciplinas em Risco/Atraso:** {risk_summary}

### EFETIVO DE CAMPO
- **Efetivo Atual:** {fmt.get('equipe_val', '—')}
- **Situação da Equipe:** {fmt.get('equipe_sub', '—')}
- **Disciplinas Críticas:** {fmt.get('disc_val', '—')} — {fmt.get('disc_sub', '—')}

### PROGRESSO DETALHADO POR DISCIPLINA (únicos dados de progresso existentes)
{disc_lines}
{not_available_note}
""".strip()

        approach_labels = {
            "estrategica": "Estratégica (para diretoria/investidores)",
            "analitica": "Analítica Financeira (detalhada, quantitativa)",
            "descritiva": "Descritiva de Auditoria (formal, completa)",
            "operacional": "Operacional de Campo (prática, técnica)",
        }
        approach_label = approach_labels.get(approach, approach)

        depth_instruction = (
            "\n\nREQUISITOS DE QUALIDADE — siga RIGOROSAMENTE:\n"
            "1. Produza um relatório EXTENSO e APROFUNDADO — equivalente a 4-5 páginas A4.\n"
            "2. Mínimo de 7 seções com ## Título, cada uma com pelo menos 4-6 parágrafos OU 8+ bullet points.\n"
            "3. Use ### para subseções dentro das seções principais para maior profundidade.\n"
            "4. Se incluir tabela markdown, use SOMENTE colunas e valores presentes nos dados fornecidos "
            "(ex: tabela de disciplinas com % Previsto / % Realizado / Status — dados já fornecidos). "
            "NUNCA crie colunas com dados que não existem no contexto.\n"
            "5. Cite os números EXATOS do contexto — nunca arredonde, estime ou adicione dados.\n"
            "6. Conclua TODOS os tópicos completamente antes de avançar — NUNCA corte uma seção no meio.\n"
            "7. Finalize com ## Conclusão e Recomendações com ações concretas baseadas nos desvios observados.\n"
            "8. LEMBRE: use ZERO dados externos — todos os números devem vir do bloco de dados fornecido."
        )

        if approach == "custom" and custom_instruction:
            user_content = (
                f"Com base nos dados do projeto abaixo, gere um relatório executivo profissional.\n\n"
                f"## PEDIDO ESPECÍFICO DO USUÁRIO\n{custom_instruction}\n\n"
                f"## DADOS DO PROJETO\n{context}"
                f"{depth_instruction}"
            )
        else:
            user_content = (
                f"Gere um relatório executivo completo com abordagem **{approach_label}** "
                f"com base nos dados reais do projeto abaixo.\n\n{context}"
                f"{depth_instruction}"
            )

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content},
        ]

    # ── AI Prompt com MCP (execute_sql direto no banco) ────────────────────────

    @staticmethod
    def build_ai_prompt_with_mcp(
        approach: str,
        contrato: str,
        client_id: str,
        periodo_inicio: str = "",
        periodo_fim: str = "",
        escopo: dict = None,
        etapa_especifica: str = "",
        custom_instruction: str = "",
        gerado_por: str = "Sistema",
    ) -> list[dict]:
        """
        Prompt enterprise para relatório IA com acesso direto ao banco via execute_sql.
        A IA consulta dados REAIS — sem snapshot estático.

        Diferença do build_ai_prompt clássico:
        - IA usa tools (execute_sql, search_documents, get_schema_info)
        - Dados em tempo real, não snapshot do GlobalState
        - LGPD: client_id obrigatório em todas as queries
        - IA instrui-se a usar ---PAGE--- entre seções

        escopo: {cronograma, financeiro, rdos, documentos, equipe, alertas}
        """
        from bomtempo.core.ai_context import AIContext

        escopo = escopo or {
            "cronograma": True, "financeiro": True, "rdos": True,
            "documentos": True, "equipe": True, "alertas": True,
        }

        persona = _PERSONAS.get(approach, _PERSONAS["estrategica"])

        periodo_str = ""
        if periodo_inicio and periodo_fim:
            periodo_str = f"Período de análise: {periodo_inicio} a {periodo_fim}"
        elif periodo_inicio:
            periodo_str = f"A partir de: {periodo_inicio}"

        etapa_str = f"\nEtapa específica a destacar: {etapa_especifica}" if etapa_especifica else ""
        custom_str = f"\nInstrução adicional do usuário: {custom_instruction}" if custom_instruction else ""

        # Monta a lista de seções esperadas baseada no escopo
        secoes_esperadas = []
        sec_n = 1
        secoes_esperadas.append(f"{sec_n}. Sumário Executivo (KPIs críticos em 1 parágrafo)")
        sec_n += 1
        if escopo.get("cronograma"):
            secoes_esperadas.append(f"{sec_n}. Cronograma — Avanço por Macro-Etapa (tabela previsto vs realizado, desvio)")
            sec_n += 1
        if escopo.get("financeiro"):
            secoes_esperadas.append(f"{sec_n}. Financeiro — Orçado vs Realizado, Saldo, Medições")
            sec_n += 1
        if escopo.get("rdos"):
            secoes_esperadas.append(f"{sec_n}. RDOs do Período — Atividades, Efetivo, Produtividade")
            sec_n += 1
        if escopo.get("documentos"):
            secoes_esperadas.append(f"{sec_n}. Documentos e Cláusulas Críticas")
            sec_n += 1
        if escopo.get("alertas"):
            secoes_esperadas.append(f"{sec_n}. Riscos e Alertas Ativos")
            sec_n += 1
        secoes_esperadas.append(f"{sec_n}. Conclusão e Recomendações")
        secoes_list = "\n".join(secoes_esperadas)

        system_msg = f"""{persona}

{_GUARDRAIL}

══════════════════════════════════════════════════════════════
ACESSO AO BANCO DE DADOS — PROTOCOLO MCP
══════════════════════════════════════════════════════════════
Você tem acesso às ferramentas execute_sql, search_documents e get_schema_info.

REGRAS ABSOLUTAS DE LGPD — ZERO TOLERÂNCIA:
1. TODA query execute_sql DEVE ter WHERE client_id = '{client_id}' OU WHERE contrato = '{contrato}'
2. NUNCA omita o filtro de tenant — isso é violação de LGPD
3. Use get_schema_info antes de qualquer query para conhecer as colunas exatas
4. Se client_id não puder ser adicionado (tabela sem coluna), use contrato como filtro

SEQUÊNCIA OBRIGATÓRIA antes de escrever o relatório:
1. get_schema_info — mapear tabelas e colunas disponíveis
2. Para cada seção, execute_sql com filtros de tenant
3. search_documents para cláusulas e alertas de documentos
4. Escrever o relatório APENAS com dados retornados pelas queries

SE UMA QUERY RETORNAR VAZIO:
- Escreva: "Dado não disponível para o período/contrato consultado."
- NUNCA invente ou estime valores

══════════════════════════════════════════════════════════════
FORMATO OBRIGATÓRIO DO RELATÓRIO
══════════════════════════════════════════════════════════════
- Use Markdown com ## para cada seção principal
- ANTES de cada seção principal (exceto a primeira), escreva exatamente:
  ---PAGE---
  (em linha isolada, sem nada antes ou depois)
- Isso garante quebra de página correta no PDF
- NUNCA corte uma seção no meio — conclua cada seção completamente
- Tabelas Markdown são permitidas e encorajadas para dados tabulares

SEÇÕES ESPERADAS (nesta ordem):
{secoes_list}
"""

        user_content = (
            f"Gere um relatório executivo completo para o contrato {contrato}.\n\n"
            f"Tenant/Client ID: {client_id}\n"
            f"Contrato: {contrato}\n"
            f"Gerado por: {gerado_por}\n"
            f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
            f"{periodo_str}"
            f"{etapa_str}"
            f"{custom_str}\n\n"
            f"Comece com get_schema_info para mapear as tabelas disponíveis, "
            f"depois execute as queries necessárias para cada seção, "
            f"e então escreva o relatório completo com os dados reais obtidos.\n\n"
            f"Lembre-se:\n"
            f"- Adicionar ---PAGE--- antes de cada seção (exceto a primeira)\n"
            f"- Filtrar SEMPRE por client_id = '{client_id}' ou contrato = '{contrato}'\n"
            f"- Nunca inventar dados — se não encontrar, declarar 'Dado não disponível'"
        )

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content},
        ]
