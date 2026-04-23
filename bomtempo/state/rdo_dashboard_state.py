"""
RDO Dashboard State — KPIs, filtros e dados para Admin/Gestor
Carrega dados das tabelas: rdo_master, rdo_atividades, rdo_evidencias
"""

from datetime import datetime, timedelta

import reflex as rx

from bomtempo.core.logging_utils import get_logger
from bomtempo.core.rdo_service import RDOService
from bomtempo.core.supabase_client import sb_select

logger = get_logger(__name__)


class RDODashboardState(rx.State):
    """Estado do Dashboard 360° de RDOs"""

    # Dados brutos
    rdos: list[dict] = []

    # Filtros
    filtro_contrato: str = "Todos"
    filtro_periodo: str = "30"  # dias

    # KPIs — cabeçalho
    kpi_total: int = 0
    kpi_obras_ativas: int = 0
    kpi_ultima_data: str = "—"
    kpi_hoje: int = 0

    # KPIs — detalhes
    kpi_atividades: int = 0
    kpi_fotos: int = 0
    kpi_checkins: int = 0

    # Gráfico: RDOs por dia (últimos N dias)
    grafico_por_dia: list[dict] = []

    # Gráfico: Distribuição climática
    grafico_clima: list[dict] = []

    # Gráfico: Atividades por status
    grafico_atividades_status: list[dict] = []

    # Gráfico: Atividades por contrato (bar)
    grafico_atividades_por_contrato: list[dict] = []

    # Lista de contratos disponíveis para filtro
    contratos_disponiveis: list[str] = ["Todos"]

    # Loading — default True prevents flash before on_mount fires
    is_loading: bool = True

    # Cache TTL — evita recarregar se usuário volta à página em menos de 5 min
    _cache_ts: float = 0.0  # timestamp da última carga (não serializado ao frontend)
    _CACHE_TTL: float = 300.0  # 5 minutos

    async def load_dashboard(self):
        """Carrega e calcula todos os dados do dashboard (com cache TTL de 5 min)."""
        import time as _time
        now = _time.monotonic()
        # Usa cache se ainda válido e não houver mudança de filtro forçada pelo usuário
        if self.rdos and (now - self._cache_ts) < self._CACHE_TTL:
            self.is_loading = False
            return

        self.is_loading = True
        yield

        try:
            # ── Captura client_id do tenant logado ────────────────
            _client_id = ""
            try:
                from bomtempo.state.global_state import GlobalState
                _gs = await self.get_state(GlobalState)
                _client_id = str(_gs.current_client_id or "")
            except Exception:
                pass

            # ── 1. rdo_master ─────────────────────────────────────
            all_rdos = RDOService.get_all_rdos(limit=500, client_id=_client_id)
            logger.info(f"📊 Dashboard: {len(all_rdos)} RDOs")

            # Contratos disponíveis (normalise key — DB returns lowercase)
            def _contrato(r: dict) -> str:
                return r.get("contrato") or r.get("Contrato") or ""

            contratos = sorted(set(_contrato(r) for r in all_rdos if _contrato(r)))
            self.contratos_disponiveis = ["Todos"] + contratos

            # Filtrar por período
            dias = int(self.filtro_periodo) if self.filtro_periodo.isdigit() else 30
            cutoff = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
            filtro_ctr = self.filtro_contrato

            def _data(r: dict) -> str:
                return (r.get("data") or r.get("Data") or "0")[:10]

            def _match(r: dict) -> bool:
                d = _data(r)
                ctr = _contrato(r)
                return d >= cutoff and (filtro_ctr == "Todos" or ctr == filtro_ctr)

            filtered = [r for r in all_rdos if _match(r)]
            self.rdos = filtered

            # KPIs — cabeçalho
            self.kpi_total = len(filtered)
            self.kpi_obras_ativas = len(set(_contrato(r) for r in filtered if _contrato(r)))
            today_str = datetime.now().strftime("%Y-%m-%d")
            self.kpi_hoje = len([r for r in filtered if _data(r) == today_str])
            if filtered:
                datas = sorted(_data(r) for r in filtered if _data(r) and _data(r) != "0")
                self.kpi_ultima_data = datas[-1] if datas else "—"
            else:
                self.kpi_ultima_data = "—"

            # KPI: checkins (RDOs with checkin_lat != 0)
            self.kpi_checkins = len([
                r for r in filtered
                if float(r.get("checkin_lat") or 0.0) != 0.0
            ])

            # Gráfico: RDOs por dia
            day_counts: dict[str, int] = {}
            for r in filtered:
                d = _data(r)
                if d:
                    day_counts[d] = day_counts.get(d, 0) + 1
            self.grafico_por_dia = [
                {"data": k, "rdos": v} for k, v in sorted(day_counts.items())
            ][-30:]

            # Gráfico: Clima
            clima_counts: dict[str, int] = {}
            for r in filtered:
                clima = r.get("condicao_climatica") or r.get("Condicao_Climatica") or "Não informado"
                if clima in ("None", "nan", ""):
                    clima = "Não informado"
                clima_counts[clima] = clima_counts.get(clima, 0) + 1
            self.grafico_clima = [{"name": k, "value": v} for k, v in clima_counts.items()]

            # IDs filtrados para join com sub-tabelas
            filtered_ids = set(r.get("id_rdo") or r.get("ID_RDO") or "" for r in filtered)

            # ── 2. rdo_atividades ─────────────────────────────────
            try:
                at_rows = sb_select("rdo_atividades", limit=3000) or []
                at_filtered = [r for r in at_rows if (r.get("id_rdo") or "") in filtered_ids]
                self.kpi_atividades = len(at_filtered)

                # Por status
                status_map: dict[str, int] = {}
                for r in at_filtered:
                    st = r.get("status") or r.get("Status") or "Sem status"
                    status_map[st] = status_map.get(st, 0) + 1
                self.grafico_atividades_status = [
                    {"name": k, "value": v} for k, v in status_map.items()
                ]

                # Por contrato (join back to rdo_master)
                id_to_contrato = {
                    (r.get("id_rdo") or r.get("ID_RDO") or ""): _contrato(r)
                    for r in filtered
                }
                ctr_map: dict[str, int] = {}
                for r in at_filtered:
                    ctr = id_to_contrato.get(r.get("id_rdo") or "", "?")
                    ctr_map[ctr] = ctr_map.get(ctr, 0) + 1
                self.grafico_atividades_por_contrato = [
                    {"contrato": k, "atividades": v}
                    for k, v in sorted(ctr_map.items(), key=lambda x: -x[1])
                ][:10]
            except Exception as e:
                logger.warning(f"⚠️ rdo_atividades: {e}")

            # ── 3. rdo_evidencias (fotos) ─────────────────────────
            try:
                ev_rows = sb_select("rdo_evidencias", limit=3000) or []
                ev_filtered = [r for r in ev_rows if (r.get("id_rdo") or "") in filtered_ids]
                self.kpi_fotos = len(ev_filtered)
            except Exception as e:
                logger.warning(f"⚠️ rdo_evidencias: {e}")

            import time as _time
            self._cache_ts = _time.monotonic()
            logger.info(
                f"📊 Dashboard completo: {self.kpi_total} RDOs, "
                f"{self.kpi_atividades} atividades, {self.kpi_fotos} fotos, "
                f"{self.kpi_checkins} check-ins"
            )

        except Exception as e:
            logger.error(f"❌ Erro ao carregar dashboard RDO: {e}", exc_info=True)
        finally:
            self.is_loading = False

    def set_filtro_contrato(self, value: str):
        self.filtro_contrato = value
        self._cache_ts = 0.0  # invalida cache para forçar recarga com novo filtro
        return RDODashboardState.load_dashboard

    def set_filtro_periodo(self, value: str):
        self.filtro_periodo = value
        self._cache_ts = 0.0  # invalida cache
        return RDODashboardState.load_dashboard
