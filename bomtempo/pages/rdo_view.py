"""
RDO Public View — Visualização interativa e rica do RDO (sem login).
Rota: /rdo-view/[token]

Mostra todas as seções do formulário: GPS, equipe, EPI, ferramentas,
fotos do dia, atividades, materiais, observações, AI summary.
"""

import asyncio
from typing import Any, Dict, List

import reflex as rx

from bomtempo.core.logging_utils import get_logger
from bomtempo.core.rdo_service import RDOService

logger = get_logger(__name__)

_BG      = "#0B1A15"
_SURFACE = "#0E2118"
_CARD    = "rgba(255,255,255,0.04)"
_CARD2   = "rgba(255,255,255,0.06)"
_COPPER  = "#C98B2A"
_COPPER2 = "rgba(201,139,42,0.15)"
_PATINA  = "#2A9D8F"
_TEXT    = "#E8F0EE"
_MUTED   = "#6B9090"
_BORDER  = "rgba(255,255,255,0.08)"
_BORDER2 = "rgba(201,139,42,0.25)"


# ── State ────────────────────────────────────────────────────────────────────

class RDOViewState(rx.State):
    rdo_html: str = ""
    rdo_id: str = ""
    rdo_contrato: str = ""
    rdo_data: str = ""
    rdo_status: str = ""
    rdo_projeto: str = ""
    rdo_cliente: str = ""
    rdo_clima: str = ""
    rdo_turno: str = ""
    rdo_mestre: str = ""
    rdo_observacoes: str = ""
    rdo_orientacao: str = ""
    rdo_houve_chuva: str = ""
    # GPS
    rdo_checkin_endereco: str = ""
    rdo_checkin_timestamp: str = ""
    rdo_checkin_lat: str = ""
    rdo_checkin_lng: str = ""
    rdo_checkout_endereco: str = ""
    rdo_checkout_timestamp: str = ""
    # Fotos especiais
    rdo_epi_foto_url: str = ""
    rdo_ferramentas_foto_url: str = ""
    # PDF
    pdf_url: str = ""
    ai_summary: str = ""
    is_loading: bool = True
    not_found: bool = False
    # Listas
    evidencias: List[Dict[str, str]] = []
    atividades: List[Dict[str, str]] = []
    # Cronograma activities enriched with desvio/EAC context
    cronograma_entries: List[Dict[str, str]] = []
    # Lightbox
    lightbox_url: str = ""
    lightbox_label: str = ""

    def open_lightbox(self, url: str):
        self.lightbox_url = url
        self.lightbox_label = ""

    def open_lightbox_labeled(self, data: Dict[str, str]):
        self.lightbox_url = data.get("url", "")
        self.lightbox_label = data.get("label", "")

    def close_lightbox(self):
        self.lightbox_url = ""
        self.lightbox_label = ""

    @rx.event(background=True)
    async def load_rdo(self):
        async with self:
            self.is_loading = True
            self.not_found = False
            token = str(self.router.page.params.get("token", ""))

        loop = asyncio.get_running_loop()
        data: Dict[str, Any] = await loop.run_in_executor(
            None,
            lambda: RDOService.get_by_token(token),
        )

        if not data:
            async with self:
                self.is_loading = False
                self.not_found = True
            return

        # Evidence list (fotos do dia genéricas)
        evidencias_raw = data.get("evidencias") or []
        ev_list = []
        for e in evidencias_raw:
            url = str(e.get("foto_url") or e.get("url") or "")
            legenda = str(e.get("legenda") or "")
            if url:
                ev_list.append({"url": url, "legenda": legenda})

        # Atividades (legacy manual list — kept for display)
        atividades_raw = data.get("atividades") or []
        at_list = []
        at_names_seen: set = set()
        for a in atividades_raw:
            desc = str(a.get("atividade") or a.get("descricao") or a.get("description") or "")
            if not desc:
                continue
            key = desc.lower().strip()
            if key in at_names_seen:
                continue  # deduplicate — same activity stored multiple times
            at_names_seen.add(key)
            pct_raw = str(a.get("progresso_percentual") or a.get("percentual_conclusao") or a.get("pct") or "")
            pct = pct_raw.strip().rstrip("%")
            efetivo = str(a.get("efetivo") or a.get("efetivo_alocado") or "")
            at_list.append({
                "descricao": desc,
                "status": str(a.get("status") or ""),
                "percentual": pct,
                "efetivo": efetivo,
            })

        def _fmt_date_inner(v: str) -> str:
            if len(v) == 10 and v[4] == "-":
                try:
                    p = v.split("-")
                    return f"{p[2]}/{p[1]}/{p[0]}"
                except Exception:
                    pass
            return v

        # Load cronograma context from hub_atividades for the contract
        contrato_for_cron = str(data.get("contrato", "") or "")
        # Names of activities reported in this RDO (for smart filtering)
        rdo_ativ_names = {a["descricao"].lower().strip() for a in at_list if a["descricao"]}
        cron_list: list = []
        if contrato_for_cron:
            try:
                from bomtempo.core.supabase_client import sb_select as _sb_sel
                from datetime import date as _date, timedelta as _td_inner
                hub_rows = await loop.run_in_executor(
                    None,
                    lambda: _sb_sel(
                        "hub_atividades",
                        filters={"contrato": contrato_for_cron},
                        order="fase_macro.asc,atividade.asc",
                        limit=200,
                    ),
                )
                # Âncora temporal = data do RDO, não date.today()
                # Evita que RDOs retroativos ou antigos mostrem EAC distorcido
                _rdo_date_str = str(data.get("data", "") or "")[:10]
                try:
                    today = _date.fromisoformat(_rdo_date_str) if _rdo_date_str else _date.today()
                except ValueError:
                    today = _date.today()

                def _build_cron_entry(r: dict) -> dict:
                    nivel = str(r.get("nivel", "macro") or "macro")
                    pct_val = int(r.get("conclusao_pct", 0) or 0)
                    total_qty = float(r.get("total_qty", 0) or 0)
                    exec_qty = float(r.get("exec_qty", 0) or 0)
                    dias_plan = int(r.get("dias_planejados", 0) or 0)
                    t_iso = str(r.get("termino_previsto", "") or "")[:10]
                    s_iso = str(r.get("inicio_previsto", "") or "")[:10]
                    unidade = str(r.get("unidade", "") or "")
                    eac_str = desvio_str = tendencia = ""
                    if exec_qty > 0 and total_qty > 0 and dias_plan > 0 and s_iso:
                        try:
                            d_inicio = _date.fromisoformat(s_iso)
                            dias_dec = max(0, (today - d_inicio).days) if d_inicio <= today else 0
                            if dias_dec >= 1:
                                prod_plan = total_qty / dias_plan
                                prod_real = exec_qty / max(1, dias_dec)
                                desvio_raw = (prod_real - prod_plan) / prod_plan * 100 if prod_plan > 0 else 0.0
                                desvio_str = f"{desvio_raw:+.1f}%"
                                if desvio_raw >= 5:
                                    tendencia = "acima"
                                elif desvio_raw <= -10:
                                    tendencia = "abaixo"
                                else:
                                    tendencia = "no_ritmo"
                                saldo_qty = max(0.0, total_qty - exec_qty)
                                if prod_real > 0 and saldo_qty > 0:
                                    dias_restantes = int(saldo_qty / prod_real * 1.4)
                                    eac_date = today + _td_inner(days=int(dias_restantes * 7 / 5))
                                    eac_str = eac_date.strftime("%d/%m/%Y")
                                elif pct_val >= 100:
                                    tendencia = "concluida"
                                    eac_str = _fmt_date_inner(t_iso) if t_iso else ""
                        except Exception:
                            pass
                    return {
                        "atividade": str(r.get("atividade", "") or ""),
                        "fase_macro": str(r.get("fase_macro", "") or ""),
                        "responsavel": str(r.get("responsavel", "") or ""),
                        "nivel": nivel,
                        "conclusao_pct": str(pct_val),
                        "desvio": desvio_str,
                        "tendencia": tendencia,
                        "eac": eac_str,
                        "termino_previsto": _fmt_date_inner(t_iso) if t_iso else "",
                        "exec_label": f"{exec_qty:.1f}/{total_qty:.1f} {unidade}".strip() if total_qty > 0 else "",
                    }

                all_entries = [_build_cron_entry(r) for r in (hub_rows or [])]

                # Mostrar APENAS atividades que foram relatadas neste RDO específico.
                # Se o mestre não registrou nenhuma atividade (rdo_ativ_names vazio),
                # fallback para atividades com exec_qty > 0 (algo já foi produzido).
                # Nunca mostrar TODAS as atividades do cronograma — seria ruído enorme.
                if rdo_ativ_names:
                    matched = [e for e in all_entries if e["atividade"].lower().strip() in rdo_ativ_names]
                    cron_list = matched  # pode ser vazio se nomes não baterem exatamente
                else:
                    # Fallback: só atividades com produção registrada (exec_qty > 0)
                    cron_list = [
                        e for e in all_entries
                        if e.get("exec_label", "").strip() and not e["exec_label"].startswith("0.0/")
                    ]
            except Exception:
                pass

        def _fmt_date(val: str) -> str:
            v = str(val or "")[:10]
            if len(v) == 10 and v[4] == "-":
                try:
                    p = v.split("-")
                    return f"{p[2]}/{p[1]}/{p[0]}"
                except Exception:
                    pass
            return v

        def _fmt_ts(val: str) -> str:
            """Converte ISO UTC timestamp → DD/MM/YYYY HH:MM (BRT, UTC-3)."""
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            v = str(val or "")
            if not v or len(v) < 16:
                return v
            try:
                dt = _dt.fromisoformat(v.replace("Z", "+00:00")[:32])
                brt = dt.astimezone(_tz(_td(hours=-3)))
                return brt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                return v[:16].replace("T", " ")

        async with self:
            self.rdo_id                = str(data.get("id_rdo", ""))
            self.rdo_contrato          = str(data.get("contrato", ""))
            self.rdo_data              = _fmt_date(str(data.get("data", "")))
            self.rdo_status            = str(data.get("status", ""))
            self.rdo_projeto           = str(data.get("projeto") or "")
            self.rdo_cliente           = str(data.get("cliente") or "")
            self.rdo_clima             = str(data.get("condicao_climatica") or data.get("clima") or "")
            self.rdo_turno             = str(data.get("turno") or "")
            self.rdo_mestre            = str(data.get("mestre_id") or "")
            self.rdo_observacoes       = str(data.get("observacoes") or "")
            self.rdo_orientacao        = str(data.get("orientacao") or "")
            self.rdo_houve_chuva       = "Sim" if data.get("houve_chuva") else "Não"
            self.rdo_checkin_endereco  = str(data.get("checkin_endereco") or "")
            self.rdo_checkin_timestamp = _fmt_ts(str(data.get("checkin_timestamp") or ""))
            self.rdo_checkin_lat       = str(data.get("checkin_lat") or "")
            self.rdo_checkin_lng       = str(data.get("checkin_lng") or "")
            self.rdo_checkout_endereco = str(data.get("checkout_endereco") or "")
            self.rdo_checkout_timestamp = _fmt_ts(str(data.get("checkout_timestamp") or ""))
            self.rdo_epi_foto_url      = str(data.get("epi_foto_url") or "")
            self.rdo_ferramentas_foto_url = str(data.get("ferramentas_foto_url") or "")
            self.pdf_url               = str(data.get("pdf_url") or "")
            self.ai_summary            = str(data.get("ai_summary") or "")
            self.evidencias            = ev_list
            self.atividades            = at_list
            self.cronograma_entries    = cron_list
            self.is_loading            = False


# ── Helpers ──────────────────────────────────────────────────────────────────

def _section_header(title: str, icon: str, color: str = _COPPER) -> rx.Component:
    bg_map = {_COPPER: "rgba(201,139,42,0.10)", _PATINA: "rgba(42,157,143,0.10)"}
    icon_bg = bg_map.get(color, "rgba(201,139,42,0.10)")
    return rx.hstack(
        rx.box(
            rx.icon(icon, size=15, color=color),
            width="32px", height="32px",
            border_radius="8px",
            background=icon_bg,
            border=f"1px solid {color}30",
            display="flex", align_items="center", justify_content="center",
            flex_shrink="0",
        ),
        rx.text(
            title,
            font_size="11px",
            font_weight="800",
            letter_spacing="0.12em",
            text_transform="uppercase",
            color=color,
            font_family="'Rajdhani', sans-serif",
        ),
        spacing="2", align="center",
        margin_bottom="14px",
    )


def _kv(label: str, value, muted: bool = False) -> rx.Component:
    return rx.hstack(
        rx.text(label, size="1", color=_MUTED, width="120px", flex_shrink="0", white_space="nowrap"),
        rx.text(value, size="2", color=_MUTED if muted else _TEXT, weight="medium", flex="1") if isinstance(value, str) else value,
        spacing="2", align="start", width="100%",
    )


def _card(*children, accent: bool = False) -> rx.Component:
    return rx.box(
        *children,
        padding="18px 20px",
        background=_CARD,
        border=f"1px solid {_BORDER2 if accent else _BORDER}",
        border_radius="6px",
        width="100%",
    )


def _badge_status() -> rx.Component:
    return rx.cond(
        RDOViewState.rdo_status == "finalizado",
        rx.badge("✓ Finalizado", color_scheme="teal", variant="soft", size="2"),
        rx.badge("● Rascunho", color_scheme="amber", variant="outline", size="2"),
    )


def _clima_icon(clima: rx.Var) -> rx.Component:
    return rx.cond(
        clima.contains("chuv") | clima.contains("Chuv"),
        rx.icon("cloud-rain", size=14, color="#60A5FA"),
        rx.cond(
            clima.contains("nub") | clima.contains("Nub"),
            rx.icon("cloud", size=14, color=_MUTED),
            rx.icon("sun", size=14, color="#FBBF24"),
        ),
    )


# ── Photo card with click-to-lightbox ────────────────────────────────────────

def _photo_card(url: str, label: str) -> rx.Component:
    """Static photo card — used for EPI and ferramentas."""
    return rx.box(
        rx.image(
            src=url,
            width="100%",
            height="180px",
            object_fit="cover",
            border_radius="8px 8px 0 0",
            cursor="zoom-in",
            on_click=RDOViewState.open_lightbox(url),
        ),
        rx.box(
            rx.text(label, size="1", color=_MUTED, font_weight="500"),
            padding="6px 10px",
            background="rgba(0,0,0,0.4)",
            border_radius="0 0 8px 8px",
        ),
        border_radius="8px",
        border=f"1px solid {_BORDER}",
        overflow="hidden",
        cursor="zoom-in",
        transition="border-color 0.15s",
        style={"_hover": {"border_color": _BORDER2}},
    )


def _ev_card(ev: Dict[str, str]) -> rx.Component:
    return rx.box(
        rx.image(
            src=ev["url"],
            width="100%",
            height="180px",
            object_fit="cover",
            border_radius="8px 8px 0 0",
            cursor="zoom-in",
            on_click=RDOViewState.open_lightbox_labeled({"url": ev["url"], "label": ev["legenda"]}),
        ),
        rx.cond(
            ev["legenda"] != "",
            rx.box(
                rx.text(ev["legenda"], size="1", color=_MUTED),
                padding="6px 10px",
                background="rgba(0,0,0,0.4)",
                border_radius="0 0 8px 8px",
            ),
            rx.box(height="0px"),
        ),
        border_radius="8px",
        border=f"1px solid {_BORDER}",
        overflow="hidden",
        cursor="zoom-in",
        transition="border-color 0.15s",
        style={"_hover": {"border_color": _BORDER2}},
    )


def _at_row(at: Dict[str, str]) -> rx.Component:
    status_color = rx.cond(
        at["status"] == "Concluído",
        _PATINA,
        rx.cond(at["status"] == "Em andamento", _COPPER, _MUTED),
    )
    bar_color = rx.cond(
        at["status"] == "Concluído",
        _PATINA,
        _COPPER,
    )
    status_icon = rx.cond(
        at["status"] == "Concluído",
        "check-circle-2",
        rx.cond(at["status"] == "Em andamento", "activity", "clock"),
    )
    return rx.box(
        rx.vstack(
            # Row 1: header with status badge
            rx.hstack(
                rx.hstack(
                    rx.icon(tag=status_icon, size=12, color=status_color),
                    rx.text(
                        at["status"],
                        size="1",
                        color=status_color,
                        font_weight="600",
                        letter_spacing="0.03em",
                    ),
                    spacing="1",
                    align="center",
                    padding="2px 7px",
                    border_radius="4px",
                    background=rx.cond(
                        at["status"] == "Concluído",
                        "rgba(42,157,143,0.12)",
                        rx.cond(at["status"] == "Em andamento", "rgba(201,139,42,0.12)", "rgba(107,144,144,0.10)"),
                    ),
                ),
                rx.spacer(),
                rx.cond(
                    at["percentual"] != "",
                    rx.text(
                        at["percentual"] + "%",
                        size="2",
                        color=bar_color,
                        font_family="'JetBrains Mono', monospace",
                        font_weight="700",
                    ),
                    rx.fragment(),
                ),
                spacing="2", align="center", width="100%",
            ),
            # Row 2: activity name
            rx.text(at["descricao"], size="2", color=_TEXT, weight="medium",
                    white_space="normal", word_break="break-word", line_height="1.4"),
            # Row 3: progress bar
            rx.cond(
                at["percentual"] != "",
                rx.box(
                    rx.box(
                        width=at["percentual"] + "%",
                        height="100%",
                        background=bar_color,
                        border_radius="2px",
                        transition="width 0.3s ease",
                    ),
                    width="100%", height="4px",
                    background="rgba(255,255,255,0.07)",
                    border_radius="2px",
                    overflow="hidden",
                ),
                rx.fragment(),
            ),
            # Row 4: meta info (efetivo alocado)
            rx.cond(
                at["efetivo"] != "",
                rx.hstack(
                    rx.icon("users", size=10, color=_MUTED),
                    rx.text(at["efetivo"] + " pessoa(s) alocada(s)", size="1", color=_MUTED),
                    spacing="1", align="center",
                ),
                rx.fragment(),
            ),
            spacing="2", width="100%",
        ),
        padding="12px 14px",
        background="rgba(255,255,255,0.02)",
        border=f"1px solid {_BORDER}",
        border_left=rx.cond(
            at["status"] == "Concluído",
            f"3px solid {_PATINA}",
            f"3px solid {_COPPER}",
        ),
        border_radius="8px",
        width="100%",
    )




def _cron_entry_row(r: Dict[str, str]) -> rx.Component:
    """Cronograma activity row with desvio/EAC/tendencia context."""
    pct_int = r["conclusao_pct"].to(int)
    tendencia = r["tendencia"]
    tend_color = rx.cond(
        tendencia == "concluida", _PATINA,
        rx.cond(tendencia == "acima", _PATINA,
        rx.cond(tendencia == "no_ritmo", _COPPER, "#F97316")),
    )
    tend_icon = rx.cond(
        tendencia == "concluida", "check-circle",
        rx.cond(tendencia == "acima", "trending-up",
        rx.cond(tendencia == "no_ritmo", "minus", "trending-down")),
    )
    tend_label = rx.cond(
        tendencia == "concluida", "Concluída",
        rx.cond(tendencia == "acima", "Acima do ritmo",
        rx.cond(tendencia == "no_ritmo", "No ritmo", "Abaixo do ritmo")),
    )
    nivel_tag = rx.cond(
        r["nivel"] == "micro",
        rx.text("MICRO", font_size="8px", color="#8B5CF6", font_family="'JetBrains Mono', monospace",
                letter_spacing="0.06em", font_weight="700"),
        rx.cond(
            r["nivel"] == "sub",
            rx.text("SUB", font_size="8px", color="#6366F1", font_family="'JetBrains Mono', monospace",
                    letter_spacing="0.06em", font_weight="700"),
            rx.fragment(),
        ),
    )
    bar_color = rx.cond(
        pct_int >= 100, _PATINA,
        rx.cond(tendencia == "abaixo", "#F97316", _COPPER),
    )
    return rx.box(
        rx.vstack(
            # Row 1: fase + tendencia badge + %
            rx.hstack(
                rx.hstack(
                    rx.box(width="5px", height="5px", border_radius="50%", background=_COPPER, flex_shrink="0"),
                    rx.text(r["fase_macro"], size="1", color=_COPPER, weight="bold",
                            text_transform="uppercase", letter_spacing="0.06em"),
                    nivel_tag,
                    spacing="1", align="center",
                ),
                rx.spacer(),
                rx.cond(
                    tendencia != "",
                    rx.hstack(
                        rx.icon(tag=tend_icon, size=11, color=tend_color),
                        rx.text(tend_label, size="1", color=tend_color, font_weight="600"),
                        spacing="1", align="center",
                        padding="2px 7px",
                        border_radius="4px",
                        bg=rx.cond(
                            tendencia == "abaixo", "rgba(249,115,22,0.1)",
                            rx.cond(tendencia == "concluida", "rgba(42,157,143,0.1)", "rgba(201,139,42,0.1)"),
                        ),
                    ),
                ),
                rx.text(r["conclusao_pct"] + "%", size="2", color=bar_color,
                        font_family="'JetBrains Mono', monospace", weight="bold"),
                spacing="2", align="center", width="100%",
            ),
            # Row 2: activity name
            rx.text(r["atividade"], size="2", color=_TEXT, weight="medium",
                    white_space="normal", word_break="break-word", line_height="1.3"),
            # Row 3: progress bar
            rx.box(
                rx.box(
                    width=r["conclusao_pct"] + "%",
                    height="100%",
                    background=bar_color,
                    border_radius="2px",
                    transition="width 0.3s ease",
                ),
                width="100%", height="4px",
                background="rgba(255,255,255,0.07)",
                border_radius="2px",
                overflow="hidden",
            ),
            # Row 4: responsável + exec label + desvio + EAC
            rx.hstack(
                rx.cond(
                    r["responsavel"] != "",
                    rx.hstack(
                        rx.icon("user", size=10, color=_MUTED),
                        rx.text(r["responsavel"], size="1", color=_MUTED),
                        spacing="1", align="center",
                    ),
                    rx.fragment(),
                ),
                rx.spacer(),
                rx.cond(
                    r["exec_label"] != "",
                    rx.text(r["exec_label"], size="1", color=_MUTED,
                            font_family="'JetBrains Mono', monospace"),
                ),
                rx.cond(
                    r["desvio"] != "",
                    rx.box(
                        rx.text(r["desvio"], size="1", color=tend_color,
                                font_family="'JetBrains Mono', monospace", weight="bold"),
                        padding="1px 6px",
                        border_radius="4px",
                        bg=rx.cond(
                            tendencia == "abaixo", "rgba(249,115,22,0.1)",
                            "rgba(42,157,143,0.1)",
                        ),
                    ),
                ),
                rx.cond(
                    r["eac"] != "",
                    rx.hstack(
                        rx.icon("calendar-check", size=10, color=_MUTED),
                        rx.text("EAC: " + r["eac"], size="1", color=_MUTED,
                                font_family="'JetBrains Mono', monospace"),
                        spacing="1", align="center",
                    ),
                ),
                spacing="2", align="center", width="100%", flex_wrap="wrap",
            ),
            spacing="2", width="100%",
        ),
        padding="12px 14px",
        background="rgba(255,255,255,0.02)",
        border=f"1px solid {_BORDER}",
        border_left=rx.cond(
            pct_int >= 100, f"3px solid {_PATINA}",
            rx.cond(tendencia == "abaixo", "3px solid #F97316", f"3px solid {_COPPER}"),
        ),
        border_radius="8px",
        width="100%",
    )


# ── Lightbox ─────────────────────────────────────────────────────────────────

def _lightbox() -> rx.Component:
    return rx.cond(
        RDOViewState.lightbox_url != "",
        rx.box(
            rx.box(
                # Image — constrained to viewport
                rx.image(
                    src=RDOViewState.lightbox_url,
                    max_width="92vw",
                    max_height="80vh",
                    object_fit="contain",
                    border_radius="10px",
                    box_shadow="0 32px 80px rgba(0,0,0,0.95)",
                    display="block",
                ),
                # Label below image
                rx.cond(
                    RDOViewState.lightbox_label != "",
                    rx.box(
                        rx.text(RDOViewState.lightbox_label, size="2", color=_MUTED, text_align="center"),
                        padding="8px 0 0 0",
                    ),
                    rx.fragment(),
                ),
                # Close button
                rx.button(
                    rx.icon("x", size=16),
                    on_click=RDOViewState.close_lightbox,
                    position="absolute",
                    top="-14px",
                    right="-14px",
                    style={
                        "background": "rgba(14,26,23,0.95)",
                        "border": f"1px solid {_BORDER2}",
                        "color": _COPPER,
                        "borderRadius": "50%",
                        "width": "32px",
                        "height": "32px",
                        "cursor": "pointer",
                        "display": "flex",
                        "alignItems": "center",
                        "justifyContent": "center",
                        "flexShrink": "0",
                    },
                ),
                # Download
                rx.link(
                    rx.button(
                        rx.icon("download", size=12),
                        "Baixar",
                        size="1",
                        style={
                            "background": f"linear-gradient(135deg,{_COPPER},#9B6820)",
                            "color": "#fff",
                            "borderRadius": "6px",
                            "fontSize": "11px",
                        },
                    ),
                    href=RDOViewState.lightbox_url,
                    is_external=True,
                    position="absolute",
                    bottom="-12px",
                    right="-12px",
                ),
                position="relative",
                display="inline-flex",
                flex_direction="column",
                align_items="center",
            ),
            position="fixed",
            top="0", left="0", right="0", bottom="0",
            background="rgba(0,0,0,0.94)",
            display="flex",
            align_items="center",
            justify_content="center",
            z_index="99999",
            on_click=RDOViewState.close_lightbox,
            style={"backdropFilter": "blur(8px)", "cursor": "zoom-out"},
        ),
    )


# ── Page ─────────────────────────────────────────────────────────────────────

def rdo_view_page() -> rx.Component:
    return rx.box(
        _lightbox(),
        # ── Top bar ──────────────────────────────────────────────────────────
        rx.box(
            rx.hstack(
                rx.hstack(
                    rx.image(src="/icon.png", width="28px", height="28px",
                             border_radius="6px", object_fit="cover"),
                    rx.vstack(
                        rx.hstack(
                            rx.text("BOMTEMPO", weight="bold", size="2", color="#fff",
                                    font_family="'Rajdhani', sans-serif",
                                    letter_spacing="0.08em", line_height="1"),
                            rx.text("INTELLIGENCE", size="1", color=_COPPER,
                                    font_family="'Rajdhani', sans-serif",
                                    letter_spacing="0.08em", display=["none", "inline"]),
                            spacing="2", align="center",
                        ),
                        rx.text("Relatório Diário de Obra", size="1", color=_MUTED, line_height="1"),
                        spacing="0",
                    ),
                    spacing="3", align="center",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.cond(
                        RDOViewState.pdf_url != "",
                        rx.link(
                            rx.button(
                                rx.icon("download", size=14),
                                rx.text("Baixar PDF", display=["none", "inline"]),
                                size="2",
                                style={
                                    "background": f"linear-gradient(135deg,{_COPPER},#9B6820)",
                                    "color": "#fff",
                                    "borderRadius": "7px",
                                    "fontWeight": "700",
                                    "fontFamily": "'Rajdhani', sans-serif",
                                    "letterSpacing": "0.06em",
                                    "textTransform": "uppercase",
                                    "boxShadow": "0 3px 14px rgba(201,139,42,0.35)",
                                },
                            ),
                            href=RDOViewState.pdf_url,
                            is_external=True,
                        ),
                        rx.fragment(),
                    ),
                    spacing="2", align="center",
                ),
                align="center", width="100%",
            ),
            padding=["10px 16px", "12px 24px"],
            background="rgba(8,18,16,0.97)",
            border_bottom=f"1px solid rgba(201,139,42,0.12)",
            style={"backdropFilter": "blur(16px)", "-webkit-backdrop-filter": "blur(16px)"},
            position="sticky",
            top="0",
            z_index="50",
            width="100%",
        ),

        # ── Content ──────────────────────────────────────────────────────────
        rx.cond(
            RDOViewState.is_loading,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3", color_scheme="amber"),
                    rx.text("Carregando relatório…", size="3", color=_MUTED),
                    spacing="3", align="center",
                ),
                min_height="70vh",
            ),
            rx.cond(
                RDOViewState.not_found,
                rx.center(
                    rx.vstack(
                        rx.icon("file-x", size=48, color=_MUTED),
                        rx.text("Relatório não encontrado", size="5", weight="bold", color=_TEXT),
                        rx.text("O link pode ter expirado ou o RDO não existe.", size="2", color=_MUTED),
                        rx.link(
                            rx.button(
                                "Ir para o Dashboard", size="2",
                                style={"background": f"linear-gradient(135deg,{_COPPER},#9B6820)", "color": "#fff", "borderRadius": "6px"},
                            ),
                            href="/",
                        ),
                        spacing="3", align="center",
                    ),
                    min_height="70vh",
                ),
                # ── Main content ─────────────────────────────────────────────
                rx.vstack(

                    # ── 1. Header card ─────────────────────────────────────
                    rx.box(
                        # Gradient overlays
                        rx.box(
                            position="absolute", top="0", left="0", right="0", bottom="0",
                            background="linear-gradient(135deg, rgba(201,139,42,0.07) 0%, transparent 55%)",
                            border_radius="16px",
                            pointer_events="none",
                        ),
                        # Left accent bar
                        rx.box(
                            position="absolute", left="0", top="0", bottom="0",
                            width="3px",
                            background=f"linear-gradient(180deg, {_COPPER} 0%, {_PATINA} 100%)",
                            border_radius="3px 0 0 3px",
                        ),
                        rx.vstack(
                            # Top row: contract + date
                            rx.hstack(
                                rx.vstack(
                                    rx.hstack(
                                        rx.text(
                                            RDOViewState.rdo_contrato,
                                            font_size="1.5rem",
                                            weight="bold",
                                            color=_COPPER,
                                            font_family="'Rajdhani', sans-serif",
                                            letter_spacing="-0.01em",
                                            line_height="1.1",
                                        ),
                                        _badge_status(),
                                        spacing="3", align="center", flex_wrap="wrap",
                                    ),
                                    rx.text(RDOViewState.rdo_projeto, size="2", color=_MUTED),
                                    spacing="1", align="start",
                                ),
                                rx.spacer(),
                                rx.vstack(
                                    rx.box(
                                        rx.hstack(
                                            rx.icon("calendar", size=12, color=_COPPER),
                                            rx.text(RDOViewState.rdo_data, size="2",
                                                    weight="bold", color=_TEXT,
                                                    font_family="'JetBrains Mono', monospace"),
                                            spacing="2", align="center",
                                        ),
                                        padding="7px 14px",
                                        background=_COPPER2,
                                        border=f"1px solid {_BORDER2}",
                                        border_radius="8px",
                                    ),
                                    spacing="0", align="end",
                                ),
                                align="start", width="100%",
                            ),
                            # Divider
                            rx.box(height="1px", width="100%", background="rgba(255,255,255,0.06)"),
                            # Meta grid
                            rx.grid(
                                _kv("Cliente", RDOViewState.rdo_cliente),
                                _kv("Mestre de Obras", RDOViewState.rdo_mestre),
                                _kv("Turno", RDOViewState.rdo_turno),
                                rx.hstack(
                                    rx.text("Clima", size="1", color=_MUTED, width="120px", flex_shrink="0"),
                                    _clima_icon(RDOViewState.rdo_clima),
                                    rx.text(RDOViewState.rdo_clima, size="2", color=_TEXT, weight="medium"),
                                    spacing="2", align="center",
                                ),
                                _kv("Chuva no dia", RDOViewState.rdo_houve_chuva),
                                _kv("ID RDO", RDOViewState.rdo_id, muted=True),
                                columns=rx.breakpoints(initial="1", md="2"),
                                gap="8px",
                                width="100%",
                            ),
                            spacing="3",
                        ),
                        padding="22px 24px 22px 28px",
                        background=_CARD,
                        border=f"1px solid rgba(201,139,42,0.2)",
                        border_radius="8px",
                        width="100%",
                        position="relative",
                        overflow="hidden",
                        style={"backdropFilter": "blur(8px)"},
                    ),

                    # ── 2. GPS Check-in / Check-out ───────────────────────
                    rx.cond(
                        RDOViewState.rdo_checkin_endereco != "",
                        _card(
                            _section_header("GPS — Presença em Campo", "map-pin"),
                            rx.grid(
                                # Check-in
                                rx.vstack(
                                    rx.hstack(
                                        rx.box(width="8px", height="8px", border_radius="50%", bg=_PATINA, flex_shrink="0"),
                                        rx.text("Check-in", size="1", color=_PATINA, weight="bold", text_transform="uppercase", letter_spacing="0.06em"),
                                        spacing="2", align="center",
                                    ),
                                    rx.text(RDOViewState.rdo_checkin_endereco, size="2", color=_TEXT),
                                    rx.text(RDOViewState.rdo_checkin_timestamp, size="1", color=_MUTED, font_family="'JetBrains Mono', monospace"),
                                    # Map link
                                    rx.cond(
                                        RDOViewState.rdo_checkin_lat != "",
                                        rx.link(
                                            rx.hstack(
                                                rx.icon("external-link", size=11, color=_COPPER),
                                                rx.text("Ver no mapa", size="1", color=_COPPER),
                                                spacing="1", align="center",
                                            ),
                                            href="https://www.openstreetmap.org/?mlat=" + RDOViewState.rdo_checkin_lat + "&mlon=" + RDOViewState.rdo_checkin_lng,
                                            is_external=True,
                                        ),
                                        rx.fragment(),
                                    ),
                                    spacing="1", align="start",
                                    padding="12px",
                                    background="rgba(42,157,143,0.06)",
                                    border=f"1px solid rgba(42,157,143,0.2)",
                                    border_radius="8px",
                                    width="100%",
                                ),
                                # Check-out
                                rx.cond(
                                    RDOViewState.rdo_checkout_endereco != "",
                                    rx.vstack(
                                        rx.hstack(
                                            rx.box(width="8px", height="8px", border_radius="50%", bg=_COPPER, flex_shrink="0"),
                                            rx.text("Check-out", size="1", color=_COPPER, weight="bold", text_transform="uppercase", letter_spacing="0.06em"),
                                            spacing="2", align="center",
                                        ),
                                        rx.text(RDOViewState.rdo_checkout_endereco, size="2", color=_TEXT),
                                        rx.text(RDOViewState.rdo_checkout_timestamp, size="1", color=_MUTED, font_family="'JetBrains Mono', monospace"),
                                        spacing="1", align="start",
                                        padding="12px",
                                        background=_COPPER2,
                                        border=f"1px solid {_BORDER2}",
                                        border_radius="8px",
                                        width="100%",
                                    ),
                                    rx.fragment(),
                                ),
                                columns=rx.breakpoints(initial="1", sm="2"),
                                gap="10px",
                                width="100%",
                            ),
                        ),
                        rx.fragment(),
                    ),

                    # ── 3. Atividades Executadas (cronograma + fallback manual) ──
                    rx.cond(
                        RDOViewState.cronograma_entries.length() > 0,
                        _card(
                            rx.hstack(
                                _section_header("Atividades Executadas", "git-branch"),
                                rx.spacer(),
                                rx.box(
                                    rx.text("Cronograma Integrado", size="1", color=_COPPER,
                                            font_family="'JetBrains Mono', monospace",
                                            letter_spacing="0.05em"),
                                    padding="2px 8px",
                                    border_radius="4px",
                                    background="rgba(201,139,42,0.08)",
                                    border=f"1px solid {_BORDER2}",
                                    margin_bottom="14px",
                                ),
                                align="start", width="100%",
                            ),
                            rx.vstack(
                                rx.foreach(RDOViewState.cronograma_entries, _cron_entry_row),
                                spacing="2", width="100%",
                            ),
                        ),
                        rx.cond(
                            RDOViewState.atividades.length() > 0,
                            _card(
                                _section_header("Atividades Executadas", "clipboard-check"),
                                rx.vstack(
                                    rx.foreach(RDOViewState.atividades, _at_row),
                                    spacing="2", width="100%",
                                ),
                            ),
                            rx.fragment(),
                        ),
                    ),

                    # ── 4. EPI + Ferramentas ──────────────────────────────
                    rx.cond(
                        (RDOViewState.rdo_epi_foto_url != "") | (RDOViewState.rdo_ferramentas_foto_url != ""),
                        _card(
                            _section_header("Segurança e Equipamentos", "shield-check"),
                            rx.grid(
                                rx.cond(
                                    RDOViewState.rdo_epi_foto_url != "",
                                    _photo_card(RDOViewState.rdo_epi_foto_url, "Equipe com EPIs"),
                                    rx.fragment(),
                                ),
                                rx.cond(
                                    RDOViewState.rdo_ferramentas_foto_url != "",
                                    _photo_card(RDOViewState.rdo_ferramentas_foto_url, "Ferramentas Limpas e Organizadas"),
                                    rx.fragment(),
                                ),
                                columns=rx.breakpoints(initial="1", sm="2"),
                                gap="12px",
                                width="100%",
                            ),
                        ),
                        rx.fragment(),
                    ),

                    # ── 6. Fotos do dia ───────────────────────────────────
                    rx.cond(
                        RDOViewState.evidencias.length() > 0,
                        _card(
                            rx.hstack(
                                _section_header("Evidências de Campo", "camera"),
                                rx.spacer(),
                                rx.text(
                                    RDOViewState.evidencias.length().to_string() + " foto(s)",
                                    size="1", color=_MUTED,
                                ),
                                margin_bottom="14px",
                                width="100%",
                                align="center",
                            ),
                            rx.grid(
                                rx.foreach(RDOViewState.evidencias, _ev_card),
                                columns=rx.breakpoints(initial="2", md="3"),
                                gap="10px",
                                width="100%",
                            ),
                        ),
                        rx.fragment(),
                    ),

                    # ── 7. Observações ────────────────────────────────────
                    rx.cond(
                        RDOViewState.rdo_observacoes != "",
                        _card(
                            _section_header("Observações", "message-square"),
                            rx.box(
                                rx.text(
                                    RDOViewState.rdo_observacoes,
                                    size="2", color=_TEXT,
                                    line_height="1.75",
                                    white_space="pre-wrap",
                                ),
                                padding="12px 14px",
                                background="rgba(255,255,255,0.02)",
                                border=f"1px solid {_BORDER}",
                                border_radius="8px",
                            ),
                        ),
                        rx.fragment(),
                    ),

                    # ── 8. Orientações ────────────────────────────────────
                    rx.cond(
                        RDOViewState.rdo_orientacao != "",
                        _card(
                            _section_header("Orientações / Pendências", "lightbulb", color=_PATINA),
                            rx.box(
                                rx.text(
                                    RDOViewState.rdo_orientacao,
                                    size="2", color=_TEXT,
                                    line_height="1.75",
                                    white_space="pre-wrap",
                                ),
                                padding="12px 14px",
                                background="rgba(42,157,143,0.04)",
                                border=f"1px solid rgba(42,157,143,0.15)",
                                border_radius="8px",
                            ),
                        ),
                        rx.fragment(),
                    ),

                    # ── 9. AI Summary ─────────────────────────────────────
                    rx.cond(
                        RDOViewState.ai_summary != "",
                        rx.box(
                            # AI header
                            rx.hstack(
                                rx.box(
                                    rx.icon("bot", size=16, color=_PATINA),
                                    width="36px", height="36px",
                                    border_radius="10px",
                                    background="rgba(42,157,143,0.12)",
                                    border=f"1px solid rgba(42,157,143,0.25)",
                                    display="flex", align_items="center", justify_content="center",
                                    flex_shrink="0",
                                ),
                                rx.vstack(
                                    rx.text(
                                        "Análise BTP Intelligence",
                                        size="2", weight="bold", color=_PATINA,
                                        font_family="'Rajdhani', sans-serif",
                                        letter_spacing="0.04em",
                                        text_transform="uppercase",
                                    ),
                                    rx.text("Gerado automaticamente por IA · Uso interno", size="1", color=_MUTED),
                                    spacing="0", align="start",
                                ),
                                spacing="3", align="center",
                                margin_bottom="14px",
                                width="100%",
                            ),
                            rx.box(height="1px", width="100%", background="rgba(42,157,143,0.12)", margin_bottom="14px"),
                            rx.box(
                                rx.markdown(RDOViewState.ai_summary),
                                style={
                                    "color": _TEXT,
                                    "fontSize": "14px",
                                    "lineHeight": "1.75",
                                    "fontFamily": "'Outfit', sans-serif",
                                },
                                class_name="analysis-markdown",
                            ),
                            padding="20px 22px",
                            background="rgba(42,157,143,0.04)",
                            border=f"1px solid rgba(42,157,143,0.15)",
                            border_left=f"3px solid {_PATINA}",
                            border_radius="6px",
                            width="100%",
                            style={"backdropFilter": "blur(6px)"},
                        ),
                        rx.fragment(),
                    ),

                    # ── Footer ────────────────────────────────────────────
                    rx.box(
                        rx.box(height="1px", background=f"rgba(201,139,42,0.12)", margin_bottom="20px"),
                        rx.flex(
                            rx.hstack(
                                rx.image(src="/icon.png", width="18px", height="18px",
                                         border_radius="4px", object_fit="cover"),
                                rx.vstack(
                                    rx.text("BTP Intelligence · Bomtempo Engenharia",
                                            size="1", color=_MUTED, weight="medium"),
                                    rx.text("Documento gerado automaticamente", size="1", color=_MUTED, opacity="0.6"),
                                    spacing="0",
                                ),
                                spacing="2", align="center",
                            ),
                            rx.hstack(
                                rx.icon("shield-check", size=12, color=_PATINA),
                                rx.text("Registro verificado", size="1", color=_PATINA),
                                spacing="1", align="center",
                            ),
                            justify="between",
                            align="center",
                            flex_wrap="wrap",
                            gap="12px",
                        ),
                        padding_y="20px",
                        padding_x="4px",
                        width="100%",
                    ),

                    spacing="4",
                    width="100%",
                    padding=["16px", "24px 28px"],
                    max_width="920px",
                    margin="0 auto",
                ),
            ),
        ),
        min_height="100vh",
        background=_BG,
    )
