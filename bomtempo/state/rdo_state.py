"""
RDO v2 State — Formulário unificado (sem wizard), com draft auto-save e GPS.
"""

import asyncio
import math
from datetime import datetime
from typing import Any, Dict, List

import reflex as rx

from bomtempo.core.logging_utils import get_logger
from bomtempo.core.rdo_service import RDOService, _haversine, _reverse_geocode
from bomtempo.core.executors import (
    get_ai_executor,
    get_db_executor,
    get_http_executor,
    get_heavy_executor,
    get_image_executor,
)

logger = get_logger(__name__)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine distance in km between two GPS points."""
    R = 6_371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


class RDOState(rx.State):
    # ── Tenant isolation ──────────────────────────────────────
    _rdo_client_id: str = ""        # client_id do tenant logado (populado em init_page)

    # ── Draft / session ────────────────────────────────────────
    draft_id_rdo: str = ""          # ID do rascunho ativo
    draft_saved_at: str = ""        # "hh:mm" — última vez salvo
    is_draft_saving: bool = False
    draft_resumed: bool = False     # mostra banner "rascunho retomado"
    has_draft_to_resume: bool = False  # banner de oferta de retomar
    pending_draft_id: str = ""      # ID do rascunho pendente de retomada

    # ── Seleção de contrato (admin/gestor) ────────────────────
    # True quando o usuário logado pode escolher qualquer contrato
    can_choose_contrato: bool = False

    # ── Cabeçalho ─────────────────────────────────────────────
    rdo_data: str = ""
    rdo_contrato: str = ""
    rdo_projeto: str = ""
    rdo_cliente: str = ""
    rdo_localizacao: str = ""
    rdo_clima: str = "Ensolarado"
    rdo_turno: str = "Diurno"
    rdo_tipo_tarefa: str = "Diário de Obra"
    rdo_orientacao: str = ""
    rdo_km_percorrido: str = ""       # manual override; auto-calc shown as badge
    rdo_houve_interrupcao: bool = False
    rdo_motivo_interrupcao: str = ""
    rdo_equipe_alocada: str = ""          # number of team members on site today
    rdo_observacoes: str = ""

    # ── GPS Check-in ──────────────────────────────────────────
    checkin_lat: float = 0.0
    checkin_lng: float = 0.0
    checkin_endereco: str = ""
    checkin_timestamp: str = ""
    checkin_distancia_obra: float = 0.0   # metros até a obra
    is_getting_checkin: bool = False

    # ── GPS Check-out ─────────────────────────────────────────
    checkout_lat: float = 0.0
    checkout_lng: float = 0.0
    checkout_endereco: str = ""
    checkout_timestamp: str = ""
    is_getting_checkout: bool = False

    # ── Evidências (fotos do dia) ─────────────────────────────
    evidencias_items: List[Dict[str, str]] = []
    ev_legenda: str = ""
    is_uploading_evidence: bool = False
    # Client-side EXIF metadata (extracted by exifr.js before upload)
    ev_exif_datetime: str = ""    # ISO string from EXIF DateTimeOriginal
    ev_exif_lat: float = 0.0      # GPS latitude from EXIF
    ev_exif_lng: float = 0.0      # GPS longitude from EXIF
    ev_last_modified: str = ""    # File.lastModified as fallback
    # Lightbox
    photo_lightbox_url: str = ""   # URL da foto em fullscreen ("" = fechado)
    # Inline caption editor
    ev_editing_url: str = ""       # foto_url being edited ("" = none)
    ev_editing_draft: str = ""     # draft text while editing

    # ── Foto EPIs ─────────────────────────────────────────────
    epi_foto_items: List[Dict[str, str]] = []
    is_uploading_epi: bool = False

    # ── Foto Ferramentas ──────────────────────────────────────
    ferramentas_foto_items: List[Dict[str, str]] = []
    is_uploading_ferramentas: bool = False

    # ── Atividades ────────────────────────────────────────────
    atividades_items: List[Dict[str, Any]] = []

    # ── Temp inputs: Atividades ───────────────────────────────
    at_desc: str = ""
    at_pct: str = "100"
    at_status: str = "Em andamento"

    # ── Assinatura ────────────────────────────────────────────
    signatory_name: str = ""
    signatory_doc: str = ""
    signatory_sig_b64: str = ""

    # ── Submit ────────────────────────────────────────────────
    is_submitting: bool = False
    submit_error: str = ""
    submit_status: str = ""
    show_confirm_dialog: bool = False

    # ── Campos condicionais: Chuva ─────────────────────────────
    rdo_houve_chuva: bool = False
    rdo_quantidade_chuva: str = "Leve"      # "Leve", "Moderada", "Forte"

    # ── Campos condicionais: Acidente ──────────────────────────
    rdo_houve_acidente: bool = False
    rdo_descricao_acidente: str = ""

    # ── Feature Flags ──────────────────────────────────────────
    rdo_active_features: List[str] = []

    # ── UI toggles ────────────────────────────────────────────
    section_atividades_open: bool = True
    section_observacoes_open: bool = True

    # ── Cronograma integration (feature #20) ──────────────────
    # Loaded activities from hub_atividades for the selected contract
    hub_atividades_options: List[Dict[str, str]] = []   # [{id, label}]
    hub_atividades_loading: bool = False
    # Primary activity to update
    rdo_atividade_id: str = ""
    rdo_atividade_nome: str = ""
    rdo_progresso_atividade: str = "0"
    # Quantity-based production tracking (#17)
    rdo_producao_dia: str = ""       # units produced today (input by worker)
    rdo_ativ_total_qty: str = "0"    # informativo: total_qty from hub_atividades
    rdo_ativ_exec_qty: str = "0"     # informativo: exec_qty accumulated so far
    rdo_ativ_unidade: str = ""       # informativo: unit name
    rdo_ativ_nivel: str = "micro"    # nivel da atividade selecionada (macro/micro/sub)
    rdo_ativ_parent_id: str = ""     # parent_id da atividade (para cascata de progresso)
    rdo_efetivo_primaria: str = ""   # pessoas alocadas na atividade primária hoje
    # Two-step macro → activity selection
    rdo_fase_macro_sel: str = ""     # selected macro phase (step 1)

    @rx.var
    def hub_atividades_macros(self) -> List[str]:
        """Unique macro phases from loaded activities, sorted."""
        seen = []
        for o in self.hub_atividades_options:
            m = o.get("fase_macro", "") or o.get("label", "").split(" — ")[0]
            if m and m not in seen:
                seen.append(m)
        return sorted(seen)

    @rx.var
    def hub_atividades_filtradas(self) -> List[Dict[str, str]]:
        """Activities filtered by selected macro phase (primary activity)."""
        if not self.rdo_fase_macro_sel:
            return []
        return [
            o for o in self.hub_atividades_options
            if o.get("fase_macro", "") == self.rdo_fase_macro_sel
        ]

    @rx.var
    def hub_atividades_por_fase(self) -> Dict[str, List[Dict[str, str]]]:
        """All activities grouped by fase_macro — used by extra activity dropdowns."""
        result: Dict[str, List[Dict[str, str]]] = {}
        for o in self.hub_atividades_options:
            fase = o.get("fase_macro", "Geral")
            if fase not in result:
                result[fase] = []
            result[fase].append(o)
        return result

    @rx.var
    def today_planned_atividades(self) -> List[Dict[str, str]]:
        """Activities planned for today (inicio_previsto <= today <= termino_previsto, pct < 100)."""
        today = self.rdo_data or datetime.now().strftime("%Y-%m-%d")
        result = []
        for o in self.hub_atividades_options:
            inicio = o.get("inicio_previsto", "")[:10]
            termino = o.get("termino_previsto", "")[:10]
            pct_str = o.get("pct", "0")
            nivel = o.get("nivel", "micro")
            # Only micro/sub activities (macros are driven by children)
            if nivel not in ("micro", "sub"):
                continue
            try:
                pct = int(pct_str or "0")
            except Exception:
                pct = 0
            if pct >= 100:
                continue
            if inicio and termino and inicio <= today <= termino:
                result.append({
                    "id": o.get("id", ""),
                    "label": o.get("label", ""),
                    "fase_macro": o.get("fase_macro", ""),
                    "pct": pct_str,
                    "termino": termino,
                    "status": o.get("status_atividade", ""),
                })
        return result

    @rx.var
    def overdue_atividades(self) -> List[Dict[str, str]]:
        """Activities past their termino_previsto with pct < 100 — overdue."""
        today = self.rdo_data or datetime.now().strftime("%Y-%m-%d")
        result = []
        for o in self.hub_atividades_options:
            termino = o.get("termino_previsto", "")[:10]
            pct_str = o.get("pct", "0")
            nivel = o.get("nivel", "micro")
            if nivel not in ("micro", "sub"):
                continue
            try:
                pct = int(pct_str or "0")
            except Exception:
                pct = 0
            if pct >= 100:
                continue
            if termino and termino < today:
                result.append({
                    "id": o.get("id", ""),
                    "label": o.get("label", ""),
                    "fase_macro": o.get("fase_macro", ""),
                    "pct": pct_str,
                    "termino": termino,
                    "status": o.get("status_atividade", ""),
                })
        return result

    @rx.var
    def equipe_allocation_text(self) -> str:
        """Shows X/Y alocados, Z disponíveis based on extras + primary efetivo vs total equipe."""
        total_str = str(self.rdo_equipe_alocada or "").strip()
        try:
            total = int(total_str)
        except Exception:
            return ""
        allocated = 0
        # Primary activity
        try:
            allocated += int(str(self.rdo_efetivo_primaria or "").strip() or "0")
        except Exception:
            pass
        # Extra activities
        for ex in self.rdo_extra_atividades:
            try:
                allocated += int(str(ex.get("efetivo_alocado", "") or "").strip() or "0")
            except Exception:
                pass
        if allocated == 0:
            return ""
        disponivel = total - allocated
        if disponivel < 0:
            return f"{allocated}/{total} alocados (⚠️ excede equipe)"
        return f"{allocated}/{total} alocados · {disponivel} disponível{'is' if disponivel != 1 else ''}"

    @rx.var
    def macro_has_pending_micros(self) -> bool:
        """True if the selected primary activity is a macro with micro children not at 100%."""
        if self.rdo_ativ_nivel != "macro" or not self.rdo_atividade_id:
            return False
        ativ_id = self.rdo_atividade_id
        # Check if any micro in hub_atividades_options has this as parent with pct < 100
        for o in self.hub_atividades_options:
            if o.get("parent_id", "") == ativ_id and o.get("nivel", "") in ("micro", "sub"):
                try:
                    pct = int(o.get("pct", "0") or "0")
                except Exception:
                    pct = 0
                if pct < 100:
                    return True
        return False

    # If no existing activity: create a pending one (legacy single — kept for reset compat)
    rdo_nova_atividade: bool = False
    rdo_nova_atividade_nome: str = ""
    rdo_nova_atividade_fase: str = ""
    # List of unmapped activities to create as pending {_key, nome, fase, progresso}
    rdo_novas_atividades: List[Dict[str, str]] = []
    # Extra activities (list of {id, nome, progresso, _key})
    rdo_extra_atividades: List[Dict[str, str]] = []

    # ── Options ───────────────────────────────────────────────
    clima_options: List[str] = ["Ensolarado", "Parcialmente Nublado", "Nublado", "Chuvoso", "Chuvoso Forte", "Nevando"]
    turno_options: List[str] = ["Diurno", "Noturno", "Integral"]
    at_status_options: List[str] = ["Não iniciado", "Em andamento", "Concluído", "Bloqueado"]
    chuva_options: List[str] = ["Leve", "Moderada", "Forte"]

    # ── Feature computed vars ──────────────────────────────────

    @rx.var
    def feat_conditional_fields(self) -> bool:
        return "conditional_fields" in self.rdo_active_features

    @rx.var
    def feat_auto_weather(self) -> bool:
        return "auto_weather" in self.rdo_active_features

    # ── Computed ──────────────────────────────────────────────

    @rx.var
    def rdo_data_display(self) -> str:
        """Data formatada para exibição: DD/MM/YYYY."""
        v = str(self.rdo_data or "")
        if len(v) == 10 and v[4] == "-":
            try:
                p = v.split("-")
                return f"{p[2]}/{p[1]}/{p[0]}"
            except Exception:
                pass
        return v

    @rx.var
    def checkin_done(self) -> bool:
        return self.checkin_lat != 0.0 or bool(self.checkin_endereco)

    @rx.var
    def checkout_done(self) -> bool:
        return self.checkout_lat != 0.0 or bool(self.checkout_endereco)

    @rx.var
    def form_valid(self) -> bool:
        return bool(self.rdo_contrato.strip()) and bool(self.rdo_data)

    @rx.var
    def checkin_distancia_str(self) -> str:
        d = self.checkin_distancia_obra
        if d <= 0:
            return ""
        if d < 1000:
            return f"{d:.0f}m da obra"
        return f"{d / 1000:.1f}km da obra"

    @rx.var
    def checkin_distancia_color(self) -> str:
        """Color code: green ≤100m, amber ≤300m, red >300m."""
        d = self.checkin_distancia_obra
        if d <= 0:
            return "#6B9090"
        if d <= 100:
            return "#2A9D8F"
        if d <= 300:
            return "#C98B2A"
        return "#E05252"

    @rx.var
    def checkin_hora_str(self) -> str:
        """Extract HH:MM from checkin_timestamp ISO string."""
        ts = self.checkin_timestamp
        if not ts:
            return ""
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            return dt.strftime("%H:%M")
        except Exception:
            return ts[:5] if len(ts) >= 5 else ts

    @rx.var
    def checkout_hora_str(self) -> str:
        """Extract HH:MM from checkout_timestamp ISO string."""
        ts = self.checkout_timestamp
        if not ts:
            return ""
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            return dt.strftime("%H:%M")
        except Exception:
            return ts[:5] if len(ts) >= 5 else ts

    @rx.var
    def km_percorrido_calc(self) -> str:
        """Auto-calculate km from GPS checkin/checkout using haversine. Returns formatted string."""
        if self.checkin_lat and self.checkout_lat and self.checkin_lng and self.checkout_lng:
            km = _haversine_km(
                self.checkin_lat, self.checkin_lng,
                self.checkout_lat, self.checkout_lng,
            )
            if km > 0:
                return f"{km:.1f} km"
        return ""

    @rx.var
    def epi_foto_url(self) -> str:
        """URL of the first EPI photo (stored in bucket)."""
        if self.epi_foto_items:
            return self.epi_foto_items[0].get("foto_url", "")
        return ""

    @rx.var
    def ferramentas_foto_url(self) -> str:
        """URL of the first ferramentas photo (stored in bucket)."""
        if self.ferramentas_foto_items:
            return self.ferramentas_foto_items[0].get("foto_url", "")
        return ""

    # ── Page Init ─────────────────────────────────────────────

    async def init_page(self):
        """Chamado no on_load de /rdo-form."""
        # Re-trigger signature canvas binding after SPA navigation.
        # force=true clears WeakMap so React-reused DOM nodes get rebound correctly.
        yield rx.call_script(
            "[500,1000,2000,4000].forEach(function(ms){"
            "setTimeout(function(){"
            "if(window.sigCanvasRebind) window.sigCanvasRebind(true);"
            "},ms);"
            "});"
        )
        from bomtempo.state.global_state import GlobalState
        gs = await self.get_state(GlobalState)
        user = str(gs.current_user_name)
        role = str(gs.current_user_role or "")
        contrato = str(gs.current_user_contrato).strip()
        self._rdo_client_id = str(gs.current_client_id or "")

        # Admin/Gestor podem escolher qualquer contrato
        _free_roles = {"Administrador", "admin", "Gestão-Mobile"}
        _free_by_project = contrato in ("", "nan", "None", "Todos")
        self.can_choose_contrato = role in _free_roles or _free_by_project

        # Carregar feature flags direto do banco (sempre fresco, nunca stale do login)
        # Usa run_in_executor para não bloquear o event loop (chamada síncrona ao Supabase)
        try:
            import asyncio as _asyncio
            from bomtempo.core.feature_flags import FeatureFlagsService
            _contrato_val = contrato or str(gs.current_user_contrato or "")
            if _contrato_val and _contrato_val not in ("nan", "None", ""):
                _loop = _asyncio.get_running_loop()
                self.rdo_active_features = await _loop.run_in_executor(
                    get_db_executor(),
                    lambda: FeatureFlagsService.get_features_for_contract(_contrato_val),
                )
            else:
                self.rdo_active_features = list(gs.active_features or [])
        except Exception:
            self.rdo_active_features = list(gs.active_features or [])

        # Defaults
        if not self.rdo_data:
            self.rdo_data = datetime.now().strftime("%Y-%m-%d")
        # Só pre-preenche contrato se o usuário não pode escolher (peão vinculado)
        if not self.can_choose_contrato and not self.rdo_contrato and contrato not in ("nan", "None", ""):
            self.rdo_contrato = contrato

        # Pre-fill projeto/cliente/localizacao do GlobalState
        if self.rdo_contrato and not self.rdo_projeto:
            for c in (gs.contratos_list or []):
                if str(c.get("contrato", "")).strip() == self.rdo_contrato:
                    self.rdo_projeto   = str(c.get("projeto", "") or c.get("nome_projeto", "") or "")
                    self.rdo_cliente   = str(c.get("cliente", "") or c.get("nome_cliente", "") or "")
                    self.rdo_localizacao = str(c.get("cidade", "") or c.get("localizacao", "") or "")
                    break

        # Load hub atividades for cronograma integration if contrato already set
        if self.rdo_contrato and not self.can_choose_contrato:
            yield RDOState.load_hub_atividades(self.rdo_contrato)

        # Verificar rascunho ativo — skip if already tracking a draft in this session
        if user and not self.draft_id_rdo:
            self.has_draft_to_resume = False  # reset; check_for_draft vai verificar
            # check_for_draft is called via on_load in app.add_page

    @rx.event(background=True)
    async def check_for_draft(self):
        """Verifica se há rascunho ativo no banco para este mestre.
        Se o formulário estiver vazio, carrega o rascunho automaticamente.
        Caso contrário, exibe o banner de retomada."""
        from bomtempo.state.global_state import GlobalState
        async with self:
            # get_state deve estar DENTRO do async with self (exigido pelo StateProxy)
            # mas extraímos os valores imediatamente e saímos do lock antes de qualquer I/O pesado
            gs = await self.get_state(GlobalState)
            user = str(gs.current_user_name)
            contrato = str(gs.current_user_contrato).strip()
            current_draft_id = str(self.draft_id_rdo)
            form_has_data = bool(self.rdo_contrato.strip())

        if not user:
            return

        loop = asyncio.get_running_loop()
        draft = await loop.run_in_executor(
            get_db_executor(),
            lambda: RDOService.get_active_draft(user, contrato if contrato not in ("nan","None","") else "", client_id=self._rdo_client_id),
        )
        if not draft:
            return

        draft_id = draft.get("id_rdo", "")
        if not draft_id:
            return

        if not form_has_data and not current_draft_id:
            # Form vazio e sem rascunho ativo — auto-carrega silenciosamente
            async with self:
                yield RDOState.load_draft_by_id(draft_id)
        elif not current_draft_id:
            # Form tem dados mas sem ID de rascunho — mostra banner
            async with self:
                self.has_draft_to_resume = True
                self.pending_draft_id = draft_id

    async def resume_draft(self):
        """Chamado quando usuário clica em 'Retomar Rascunho'."""
        draft_id = self.pending_draft_id
        if not draft_id:
            return
        yield RDOState.load_draft_by_id(draft_id)

    @rx.event(background=True)
    async def load_draft_by_id(self, id_rdo: str):
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(get_db_executor(), lambda: RDOService.get_full_rdo(id_rdo))
        if not data:
            return
        async with self:
            self.draft_id_rdo         = data.get("id_rdo", "")
            self.rdo_data             = str(data.get("data") or "")
            self.rdo_contrato         = data.get("contrato") or ""
            self.rdo_projeto          = data.get("projeto") or ""
            self.rdo_cliente          = data.get("cliente") or ""
            self.rdo_localizacao      = data.get("localizacao") or ""
            self.rdo_tipo_tarefa      = data.get("tipo_tarefa") or "Diário de Obra"
            self.rdo_orientacao       = data.get("orientacao") or ""
            self.rdo_km_percorrido    = str(data.get("km_percorrido") or "")
            self.rdo_clima            = data.get("condicao_climatica") or "Ensolarado"
            self.rdo_turno            = data.get("turno") or "Diurno"
            self.rdo_houve_interrupcao = bool(data.get("houve_interrupcao"))
            self.rdo_motivo_interrupcao = data.get("motivo_interrupcao") or ""
            self.rdo_equipe_alocada   = str(data.get("equipe_alocada") or "")
            self.rdo_observacoes      = data.get("observacoes") or ""
            # GPS
            self.checkin_lat          = float(data.get("checkin_lat") or 0.0)
            self.checkin_lng          = float(data.get("checkin_lng") or 0.0)
            self.checkin_endereco     = data.get("checkin_endereco") or ""
            self.checkin_timestamp    = data.get("checkin_timestamp") or ""
            self.checkout_lat         = float(data.get("checkout_lat") or 0.0)
            self.checkout_lng         = float(data.get("checkout_lng") or 0.0)
            self.checkout_endereco    = data.get("checkout_endereco") or ""
            self.checkout_timestamp   = data.get("checkout_timestamp") or ""
            # Signatory
            self.signatory_name       = data.get("signatory_name") or ""
            self.signatory_doc        = data.get("signatory_doc") or ""
            self.signatory_sig_b64    = data.get("signatory_sig_b64") or ""
            # Sub-items
            self.atividades_items     = list(data.get("atividades", []))
            self.evidencias_items     = list(data.get("evidencias", []))
            # EPI / ferramentas — try to restore from url stored in master
            epi_url = data.get("epi_foto_url") or ""
            ferramentas_url = data.get("ferramentas_foto_url") or ""
            self.epi_foto_items = [{"foto_url": epi_url}] if epi_url else []
            self.ferramentas_foto_items = [{"foto_url": ferramentas_url}] if ferramentas_url else []
            self.has_draft_to_resume  = False
            self.draft_resumed        = True
            self.draft_saved_at       = datetime.now().strftime("%H:%M")
            loaded_contrato           = data.get("contrato") or ""
        # Load activities for the restored contract (so dropdowns work without re-selecting)
        if loaded_contrato:
            yield RDOState.load_hub_atividades(loaded_contrato)
        yield rx.toast("📂 Rascunho retomado!", position="top-center")

    def discard_draft_offer(self):
        self.has_draft_to_resume = False
        self.pending_draft_id = ""

    def reset_for_new(self):
        """Limpa todo o state do formulário para criar um RDO novo do zero.
        Deve ser chamado antes de navegar para /rdo-form quando NÃO se quer retomar rascunho."""
        self.draft_id_rdo = ""
        self.draft_saved_at = ""
        self.draft_resumed = False
        self.has_draft_to_resume = False
        self.pending_draft_id = ""
        self.rdo_data = ""
        self.rdo_contrato = ""
        self.rdo_projeto = ""
        self.rdo_cliente = ""
        self.rdo_localizacao = ""
        self.rdo_clima = "Ensolarado"
        self.rdo_turno = "Diurno"
        self.rdo_tipo_tarefa = "Diário de Obra"
        self.rdo_orientacao = ""
        self.rdo_km_percorrido = ""
        self.rdo_houve_interrupcao = False
        self.rdo_motivo_interrupcao = ""
        self.rdo_equipe_alocada = ""
        self.rdo_observacoes = ""
        self.rdo_houve_chuva = False
        self.rdo_houve_acidente = False
        self.rdo_descricao_acidente = ""
        self.atividades_items = []
        self.evidencias_items = []
        self.epi_foto_items = []
        self.ferramentas_foto_items = []
        self.checkin_lat = 0.0
        self.checkin_lng = 0.0
        self.checkin_endereco = ""
        self.checkin_timestamp = ""
        self.checkout_lat = 0.0
        self.checkout_lng = 0.0
        self.checkout_endereco = ""
        self.checkout_timestamp = ""
        self.signatory_name = ""
        self.signatory_doc = ""
        self.signatory_sig_b64 = ""
        self.submit_error = ""
        self.submit_status = ""
        self.rdo_extra_atividades = []
        self.rdo_novas_atividades = []
        self.rdo_efetivo_primaria = ""
        self.rdo_ativ_nivel = "micro"
        self.rdo_ativ_parent_id = ""

    async def select_rdo_contrato(self, value: str):
        """Admin/gestor escolhe o contrato — auto-preenche projeto, cliente, localização."""
        if value == "__none__":
            self.rdo_contrato = ""
            self.rdo_projeto = ""
            self.rdo_cliente = ""
            self.rdo_localizacao = ""
            return
        self.rdo_contrato = value
        from bomtempo.state.global_state import GlobalState
        gs = await self.get_state(GlobalState)
        for c in (gs.contratos_list or []):
            if str(c.get("contrato", "")).strip() == value:
                self.rdo_projeto = str(c.get("projeto", "") or c.get("nome_projeto", "") or "")
                self.rdo_cliente = str(c.get("cliente", "") or c.get("nome_cliente", "") or "")
                self.rdo_localizacao = str(c.get("cidade", "") or c.get("localizacao", "") or "")
                break
        yield RDOState.load_hub_atividades(value)

    @rx.event(background=True)
    async def delete_current_draft(self):
        """Exclui o rascunho ativo (status=rascunho). Não exclui RDOs finalizados."""
        async with self:
            draft_id = str(self.draft_id_rdo)
        if not draft_id:
            async with self:
                yield rx.toast("Nenhum rascunho ativo para excluir.", position="top-center")
            return
        loop = asyncio.get_running_loop()
        ok = await loop.run_in_executor(get_db_executor(), lambda: RDOService.delete_draft(draft_id))
        async with self:
            if ok:
                # Reset all form state
                self.draft_id_rdo = ""
                self.draft_saved_at = ""
                self.draft_resumed = False
                self.rdo_contrato = ""
                self.rdo_data = ""
                self.rdo_projeto = ""
                self.rdo_cliente = ""
                self.rdo_localizacao = ""
                self.rdo_clima = "Ensolarado"
                self.rdo_observacoes = ""
                self.rdo_orientacao = ""
                self.atividades_items = []
                self.evidencias_items = []
                self.checkin_timestamp = ""
                self.checkin_lat = 0.0
                self.checkin_lng = 0.0
                self.checkin_endereco = ""
                self.checkout_timestamp = ""
                self.checkout_lat = 0.0
                self.checkout_lng = 0.0
                self.checkout_endereco = ""
                yield rx.toast("🗑️ Rascunho excluído.", position="top-center")
            else:
                yield rx.toast("❌ Falha ao excluir rascunho.", position="top-center")

    # ── GPS ───────────────────────────────────────────────────

    def do_checkin(self):
        """Dispara JS para capturar GPS de check-in."""
        self.is_getting_checkin = True
        return rx.call_script(
            """
            new Promise(resolve => {
                if (!navigator.geolocation) { resolve({lat:0,lng:0,ok:false}); return; }
                navigator.geolocation.getCurrentPosition(
                    p => resolve({lat:p.coords.latitude, lng:p.coords.longitude, ok:true}),
                    () => resolve({lat:0,lng:0,ok:false}),
                    {enableHighAccuracy:true,timeout:10000}
                );
            })
            """,
            callback=RDOState.receive_checkin_gps,
        )

    def do_checkout(self):
        """Dispara JS para capturar GPS de check-out."""
        self.is_getting_checkout = True
        return rx.call_script(
            """
            new Promise(resolve => {
                if (!navigator.geolocation) { resolve({lat:0,lng:0,ok:false}); return; }
                navigator.geolocation.getCurrentPosition(
                    p => resolve({lat:p.coords.latitude, lng:p.coords.longitude, ok:true}),
                    () => resolve({lat:0,lng:0,ok:false}),
                    {enableHighAccuracy:true,timeout:10000}
                );
            })
            """,
            callback=RDOState.receive_checkout_gps,
        )

    @rx.event(background=True)
    async def receive_checkin_gps(self, result: dict):
        lat = float(result.get("lat") or 0.0)
        lng = float(result.get("lng") or 0.0)
        ok  = bool(result.get("ok"))
        endereco = ""
        distancia = 0.0

        # Read contrato before I/O
        async with self:
            contrato = str(self.rdo_contrato)

        if ok and lat:
            loop = asyncio.get_running_loop()
            endereco = await loop.run_in_executor(get_http_executor(), lambda: _reverse_geocode(lat, lng))
            # Haversine distance to obra
            obra_lat, obra_lng = await loop.run_in_executor(
                get_db_executor(), lambda: RDOService.get_obra_coords(contrato)
            )
            if obra_lat and obra_lng:
                distancia = _haversine(lat, lng, obra_lat, obra_lng)

        # Auto weather (se feature ativa)
        auto_clima = ""
        async with self:
            _feat_weather = self.feat_auto_weather
        if ok and lat and _feat_weather:
            try:
                from bomtempo.core import weather_api
                forecast = await weather_api.get_forecast(lat, lng)
                if forecast:
                    code = int(forecast.get("code", 0))
                    rain = float(forecast.get("rain", 0))
                    if rain > 5 or code in range(61, 82):
                        auto_clima = "Chuvoso Forte" if rain > 10 else "Chuvoso"
                    elif rain > 0 or code in range(51, 61):
                        auto_clima = "Nublado"
                    elif code in range(1, 4):
                        auto_clima = "Parcialmente Nublado"
                    else:
                        auto_clima = "Ensolarado"
            except Exception as e:
                logger.warning(f"auto_weather: {e}")

        async with self:
            self.checkin_lat             = lat
            self.checkin_lng             = lng
            self.checkin_endereco        = endereco
            self.checkin_timestamp       = datetime.now().isoformat()
            self.checkin_distancia_obra  = distancia
            self.is_getting_checkin      = False
            if auto_clima:
                self.rdo_clima = auto_clima

        if ok and lat:
            dist_str = f" · {distancia:.0f}m da obra" if distancia > 0 else ""
            clima_str = f" · Clima: {auto_clima}" if auto_clima else ""
            yield rx.toast(
                f"📍 Check-in: {endereco or f'{lat:.4f}, {lng:.4f}'}{dist_str}{clima_str}",
                position="top-center",
            )
        else:
            yield rx.toast("⚠️ Não foi possível obter localização", position="top-center")

    @rx.event(background=True)
    async def receive_checkout_gps(self, result: dict):
        lat = float(result.get("lat") or 0.0)
        lng = float(result.get("lng") or 0.0)
        ok  = bool(result.get("ok"))
        endereco = ""

        if ok and lat:
            loop = asyncio.get_running_loop()
            endereco = await loop.run_in_executor(get_http_executor(), lambda: _reverse_geocode(lat, lng))

        async with self:
            self.checkout_lat       = lat
            self.checkout_lng       = lng
            self.checkout_endereco  = endereco
            self.checkout_timestamp = datetime.now().isoformat()
            self.is_getting_checkout = False

        if ok and lat:
            yield rx.toast(f"📍 Check-out registrado: {endereco or f'{lat:.4f}, {lng:.4f}'}", position="top-center")
        else:
            yield rx.toast("⚠️ Não foi possível obter localização", position="top-center")

    def clear_checkin(self):
        self.checkin_lat = 0.0
        self.checkin_lng = 0.0
        self.checkin_endereco = ""
        self.checkin_timestamp = ""
        self.checkin_distancia_obra = 0.0

    # ── Evidências ────────────────────────────────────────────
    # NOTE: upload handlers CANNOT be @rx.event(background=True) — Reflex restriction.

    def receive_exif_meta(self, data: dict):
        """Called from JS (exifr) before upload fires — stores client-extracted EXIF."""
        self.ev_exif_datetime = str(data.get("datetime", "") or "")
        self.ev_exif_lat      = float(data.get("lat", 0.0) or 0.0)
        self.ev_exif_lng      = float(data.get("lng", 0.0) or 0.0)
        self.ev_last_modified = str(data.get("lastModified", "") or "")

    def receive_exif_json(self, json_str: str):
        """Bridge: hidden input on_change fires with JSON string from exifr JS."""
        import json as _json
        try:
            data = _json.loads(json_str)
            self.ev_exif_datetime = str(data.get("datetime", "") or "")
            self.ev_exif_lat      = float(data.get("lat", 0.0) or 0.0)
            self.ev_exif_lng      = float(data.get("lng", 0.0) or 0.0)
            self.ev_last_modified = str(data.get("lastModified", "") or "")
        except Exception:
            pass

    # NOTE: upload handlers CANNOT be @rx.event(background=True) — Reflex restriction.
    # They are regular async handlers; blocking I/O runs via run_in_executor.

    async def upload_evidence_files(self, files: List[rx.UploadFile]):
        """Recebe arquivos do rx.upload, aplica EXIF + watermark + upload + DB."""
        if not files:
            return

        self.is_uploading_evidence = True
        yield

        try:
            # Wait for receive_exif_json WebSocket round-trip to complete before reading
            # ev_exif_* vars. exifr async parse + WS round-trip can take up to ~1s on mobile.
            await asyncio.sleep(1.2)

            from bomtempo.state.global_state import GlobalState
            gs = await self.get_state(GlobalState)
            user     = str(gs.current_user_name)
            contrato = str(self.rdo_contrato)
            data     = str(self.rdo_data)
            legenda  = str(self.ev_legenda)
            id_rdo   = str(self.draft_id_rdo)

            loop = asyncio.get_running_loop()

            # Auto-save to get an id_rdo if form not yet persisted
            if not id_rdo and contrato.strip():
                rdo_data = self._build_rdo_data()
                id_rdo = await loop.run_in_executor(
                    get_db_executor(),
                    lambda: RDOService.upsert_draft(rdo_data, mestre_id=user),
                )
                self.draft_id_rdo = id_rdo

            if not id_rdo:
                self.is_uploading_evidence = False
                yield rx.toast("⚠️ Preencha o contrato antes de adicionar fotos", position="top-center")
                return

            new_items = []
            for f in files:
                try:
                    file_bytes = await f.read()
                    # Guard: rejeita arquivos muito grandes antes de processar (evita timeout WebSocket)
                    _MAX_BYTES = 50 * 1024 * 1024  # 50 MB
                    if len(file_bytes) > _MAX_BYTES:
                        yield rx.toast(
                            f"⚠️ Foto muito grande ({len(file_bytes)//1024//1024}MB). Use uma foto de até 50MB.",
                            position="top-center", duration=8000,
                        )
                        continue
                    _name = getattr(f, "filename", "foto.jpg")
                    _ct   = getattr(f, "content_type", None) or "image/jpeg"
                    _b, _n, _c = file_bytes, _name, _ct
                    _ci_lat    = float(self.checkin_lat or 0.0)
                    _ci_lng    = float(self.checkin_lng or 0.0)
                    _ci_end    = str(self.checkin_endereco or "")
                    _ex_lat    = float(self.ev_exif_lat or 0.0)
                    _ex_lng    = float(self.ev_exif_lng or 0.0)
                    _ex_dt     = str(self.ev_exif_datetime or "")
                    _ex_lm     = str(self.ev_last_modified or "")
                    result = await loop.run_in_executor(
                        get_image_executor(),
                        lambda: RDOService.process_evidence(
                            id_rdo=id_rdo,
                            file_bytes=_b,
                            filename=_n,
                            content_type=_c,
                            legenda=legenda,
                            mestre=user,
                            contrato=contrato,
                            data=data,
                            checkin_lat=_ci_lat,
                            checkin_lng=_ci_lng,
                            checkin_endereco=_ci_end,
                            client_exif_lat=_ex_lat,
                            client_exif_lng=_ex_lng,
                            client_exif_datetime=_ex_dt,
                            client_last_modified=_ex_lm,
                        ),
                    )
                    if result.get("foto_url"):
                        new_items.append(result)
                except Exception as e:
                    logger.error(f"upload_evidence_files: {e}", exc_info=True)
                    yield rx.toast(f"❌ Erro no upload: {e}", position="top-center", duration=8000)
                    continue

            self.evidencias_items     = [*self.evidencias_items, *new_items]
            self.ev_legenda           = ""
            self.ev_exif_datetime     = ""
            self.ev_exif_lat          = 0.0
            self.ev_exif_lng          = 0.0
            self.ev_last_modified     = ""

            if new_items:
                yield rx.toast(f"✅ {len(new_items)} foto(s) adicionada(s)", position="top-center")
            else:
                yield rx.toast("⚠️ Nenhuma foto foi processada", position="top-center")
        except Exception as e:
            logger.error(f"upload_evidence_files (outer): {e}", exc_info=True)
            yield rx.toast(f"❌ Erro inesperado no upload: {str(e)[:100]}", position="top-center", duration=8000)
        finally:
            self.is_uploading_evidence = False

    def remove_evidence(self, foto_url: str):
        """Remove foto da lista local (estado draft)."""
        self.evidencias_items = [
            e for e in self.evidencias_items if e.get("foto_url", "") != foto_url
        ]

    def remove_epi_photo(self):
        self.epi_foto_items = []

    def remove_ferramentas_photo(self):
        self.ferramentas_foto_items = []

    def open_lightbox(self, url: str):
        self.photo_lightbox_url = url

    def close_lightbox(self):
        self.photo_lightbox_url = ""

    def start_edit_caption(self, foto_url: str):
        """Start inline caption editing for a specific photo."""
        current = next(
            (e.get("legenda", "") for e in self.evidencias_items if e.get("foto_url") == foto_url),
            "",
        )
        self.ev_editing_url   = foto_url
        self.ev_editing_draft = current

    def cancel_edit_caption(self):
        self.ev_editing_url   = ""
        self.ev_editing_draft = ""

    def save_edit_caption(self):
        """Commit ev_editing_draft caption to evidencias_items (on_click)."""
        url   = self.ev_editing_url
        draft = self.ev_editing_draft.strip()
        if url:
            self.evidencias_items = [
                {**e, "legenda": draft} if e.get("foto_url") == url else e
                for e in self.evidencias_items
            ]
        self.ev_editing_url   = ""
        self.ev_editing_draft = ""

    def save_edit_caption_blur(self, value: str):
        """Commit caption value received directly from on_blur event."""
        self.ev_editing_draft = value
        self.save_edit_caption()

    async def upload_epi_files(self, files: List[rx.UploadFile]):
        """Upload EPI photo — watermark + Supabase Storage.

        Handler regular (sem background=True) — upload handlers têm essa restrição no Reflex.
        I/O pesado roda via run_in_executor para não bloquear o event loop.
        get_state() sem async with self: é válido aqui (self é instância real, não StateProxy).
        """
        if not files:
            return

        loop = asyncio.get_running_loop()

        # 1. Read file bytes — WebSocket I/O
        _MAX_BYTES = 50 * 1024 * 1024
        raw_bytes = None
        raw_name = "epi.jpg"
        raw_ct = "image/jpeg"
        try:
            f = files[0]
            raw_bytes = await f.read()
            raw_name = getattr(f, "filename", "epi.jpg")
            raw_ct   = getattr(f, "content_type", None) or "image/jpeg"
        except Exception as e:
            yield rx.toast(f"❌ Erro ao ler arquivo: {str(e)[:80]}", position="top-center", duration=8000)
            return

        if len(raw_bytes) > _MAX_BYTES:
            yield rx.toast(
                f"⚠️ Foto muito grande ({len(raw_bytes)//1024//1024}MB). Use uma foto de até 50MB.",
                position="top-center", duration=8000,
            )
            return

        # 2. Snapshot state — get_state OK em handler regular (self é instância real)
        from bomtempo.state.global_state import GlobalState
        self.is_uploading_epi = True
        yield rx.toast("⏳ Processando foto com watermark…", position="top-center", duration=4000)
        try:
            gs = await self.get_state(GlobalState)
            user     = str(gs.current_user_name)
            contrato = str(self.rdo_contrato)
            data     = str(self.rdo_data)
            id_rdo   = str(self.draft_id_rdo)
            ci_lat   = float(self.checkin_lat or 0.0)
            ci_lng   = float(self.checkin_lng or 0.0)
            ci_end   = str(self.checkin_endereco or "")
            rdo_snap = self._build_rdo_data() if not id_rdo and contrato.strip() else None
        except Exception as e:
            logger.error(f"upload_epi_files: erro ao ler state: {e}")
            self.is_uploading_epi = False
            yield rx.toast("❌ Erro interno ao iniciar upload. Tente novamente.", position="top-center")
            return

        try:
            # 3. Create draft if needed — DB I/O via executor
            if not id_rdo and contrato.strip() and rdo_snap:
                id_rdo = await loop.run_in_executor(
                    get_db_executor(),
                    lambda: RDOService.upsert_draft(rdo_snap, mestre_id=user),
                )
                self.draft_id_rdo = id_rdo

            if not id_rdo:
                self.is_uploading_epi = False
                yield rx.toast("⚠️ Preencha o contrato antes de adicionar fotos", position="top-center")
                return

            # 4. Process image — watermark + resize + Supabase upload via executor
            _b, _n, _c = raw_bytes, raw_name, raw_ct
            result = await loop.run_in_executor(
                get_image_executor(),
                lambda: RDOService.process_evidence(
                    id_rdo=id_rdo, file_bytes=_b,
                    filename=f"epi_{_n}", content_type=_c,
                    legenda="Equipe com EPIs", mestre=user,
                    contrato=contrato, data=data,
                    checkin_lat=ci_lat, checkin_lng=ci_lng, checkin_endereco=ci_end,
                ),
            )

            if result.get("foto_url"):
                self.epi_foto_items = [result]
                yield rx.toast("✅ Foto EPI adicionada", position="top-center")
            else:
                yield rx.toast("⚠️ Nenhuma foto foi processada", position="top-center")

        except Exception as e:
            logger.error(f"upload_epi_files: {e}", exc_info=True)
            yield rx.toast(f"❌ Erro no upload EPI: {str(e)[:100]}", position="top-center", duration=8000)
        finally:
            self.is_uploading_epi = False

    async def upload_ferramentas_files(self, files: List[rx.UploadFile]):
        """Upload ferramentas photo — watermark + Supabase Storage.

        Handler regular (sem background=True) — upload handlers têm essa restrição no Reflex.
        I/O pesado roda via run_in_executor para não bloquear o event loop.
        get_state() sem async with self: é válido aqui (self é instância real, não StateProxy).
        """
        if not files:
            return

        loop = asyncio.get_running_loop()

        # 1. Read file bytes — WebSocket I/O
        _MAX_BYTES = 50 * 1024 * 1024
        raw_bytes = None
        raw_name = "ferramentas.jpg"
        raw_ct = "image/jpeg"
        try:
            f = files[0]
            raw_bytes = await f.read()
            raw_name = getattr(f, "filename", "ferramentas.jpg")
            raw_ct   = getattr(f, "content_type", None) or "image/jpeg"
        except Exception as e:
            yield rx.toast(f"❌ Erro ao ler arquivo: {str(e)[:80]}", position="top-center", duration=8000)
            return

        if len(raw_bytes) > _MAX_BYTES:
            yield rx.toast(
                f"⚠️ Foto muito grande ({len(raw_bytes)//1024//1024}MB). Use uma foto de até 50MB.",
                position="top-center", duration=8000,
            )
            return

        # 2. Snapshot state — get_state OK em handler regular (self é instância real)
        from bomtempo.state.global_state import GlobalState
        self.is_uploading_ferramentas = True
        yield rx.toast("⏳ Processando foto com watermark…", position="top-center", duration=4000)
        try:
            gs = await self.get_state(GlobalState)
            user     = str(gs.current_user_name)
            contrato = str(self.rdo_contrato)
            data     = str(self.rdo_data)
            id_rdo   = str(self.draft_id_rdo)
            ci_lat   = float(self.checkin_lat or 0.0)
            ci_lng   = float(self.checkin_lng or 0.0)
            ci_end   = str(self.checkin_endereco or "")
            rdo_snap = self._build_rdo_data() if not id_rdo and contrato.strip() else None
        except Exception as e:
            logger.error(f"upload_ferramentas_files: erro ao ler state: {e}")
            self.is_uploading_ferramentas = False
            yield rx.toast("❌ Erro interno ao iniciar upload. Tente novamente.", position="top-center")
            return

        try:
            # 3. Create draft if needed — DB I/O via executor
            if not id_rdo and contrato.strip() and rdo_snap:
                id_rdo = await loop.run_in_executor(
                    get_db_executor(),
                    lambda: RDOService.upsert_draft(rdo_snap, mestre_id=user),
                )
                self.draft_id_rdo = id_rdo

            if not id_rdo:
                self.is_uploading_ferramentas = False
                yield rx.toast("⚠️ Preencha o contrato antes de adicionar fotos", position="top-center")
                return

            # 4. Process image — watermark + resize + Supabase upload via executor
            _b, _n, _c = raw_bytes, raw_name, raw_ct
            result = await loop.run_in_executor(
                get_image_executor(),
                lambda: RDOService.process_evidence(
                    id_rdo=id_rdo, file_bytes=_b,
                    filename=f"ferramentas_{_n}", content_type=_c,
                    legenda="Ferramentas Limpas e Organizadas", mestre=user,
                    contrato=contrato, data=data,
                    checkin_lat=ci_lat, checkin_lng=ci_lng, checkin_endereco=ci_end,
                ),
            )

            if result.get("foto_url"):
                self.ferramentas_foto_items = [result]
                yield rx.toast("✅ Foto de ferramentas adicionada", position="top-center")
            else:
                yield rx.toast("⚠️ Nenhuma foto foi processada", position="top-center")

        except Exception as e:
            logger.error(f"upload_ferramentas_files: {e}", exc_info=True)
            yield rx.toast(f"❌ Erro no upload ferramentas: {str(e)[:100]}", position="top-center", duration=8000)
        finally:
            self.is_uploading_ferramentas = False

    # ── Assinatura ────────────────────────────────────────────

    def receive_sig_b64(self, data):
        """Callback from rx.call_script — receives canvas toDataURL."""
        if isinstance(data, dict):
            self.signatory_sig_b64 = data.get("sig", "")
        elif isinstance(data, str) and data.startswith("data:"):
            self.signatory_sig_b64 = data

    def clear_signature_canvas(self):
        """Limpa o canvas de assinatura via JS e reseta o state."""
        self.signatory_sig_b64 = ""
        return rx.call_script(
            "var c=document.getElementById('sig-canvas');if(c){var ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);}"
        )

    def capture_signature(self):
        """Captura assinatura do canvas como JPEG 70% (payload reduzido ~10x vs PNG)."""
        return rx.call_script(
            """(function(){
              var c=document.getElementById('sig-canvas');
              if(!c) return {sig:''};
              // Flatten transparent bg to white before JPEG encoding
              var tmp=document.createElement('canvas');
              tmp.width=c.width; tmp.height=c.height;
              var ctx=tmp.getContext('2d');
              ctx.fillStyle='#ffffff';
              ctx.fillRect(0,0,tmp.width,tmp.height);
              ctx.drawImage(c,0,0);
              return {sig: tmp.toDataURL('image/jpeg', 0.70)};
            })()""",
            callback=RDOState.receive_sig_b64,
        )

    # ── Atividades ────────────────────────────────────────────

    def add_at(self):
        if self.at_desc.strip():
            self.atividades_items = [*self.atividades_items, {
                "atividade":            self.at_desc.strip(),
                "progresso_percentual": self.at_pct.strip() or "0",
                "status":               self.at_status,
            }]
            self.at_desc = ""
            self.at_pct = "100"
            self.at_status = "Em andamento"

    def remove_at(self, index: int):
        self.atividades_items = [it for i, it in enumerate(self.atividades_items) if i != index]

    # ── Cronograma integration setters ────────────────────────

    def set_rdo_fase_macro(self, v: str):
        """Select macro phase and reset the activity selection."""
        self.rdo_fase_macro_sel = "" if v == "__none__" else v
        self.rdo_atividade_id = ""
        self.rdo_atividade_nome = ""
        self.rdo_producao_dia = ""
        self.rdo_ativ_total_qty = "0"
        self.rdo_ativ_exec_qty = "0"
        self.rdo_ativ_unidade = ""
        self.rdo_ativ_nivel = "micro"
        self.rdo_ativ_parent_id = ""
        self.rdo_efetivo_primaria = ""

    def set_rdo_efetivo_primaria(self, v: str): self.rdo_efetivo_primaria = str(v) if v is not None else ""

    def set_rdo_atividade_id(self, v: str):
        real_v = "" if v == "__none__" else v
        self.rdo_atividade_id = real_v
        self.rdo_producao_dia = ""
        self.rdo_efetivo_primaria = ""
        opt = next((o for o in self.hub_atividades_options if o.get("id") == real_v), None)
        # Strip prefix from label for display name
        raw_label = opt["label"] if opt else ""
        self.rdo_atividade_nome = raw_label.lstrip("↳ ").strip()
        # Pre-fill with current DB progress so user continues from where it left off
        if opt:
            current_pct = opt.get("pct", "0")
            self.rdo_progresso_atividade = current_pct
            # Load qty info for informative display
            self.rdo_ativ_total_qty = opt.get("total_qty", "0")
            self.rdo_ativ_exec_qty = opt.get("exec_qty", "0")
            self.rdo_ativ_unidade = opt.get("unidade", "")
            # Hierarchy info for cascading progress update on submit
            self.rdo_ativ_nivel = opt.get("nivel", "micro")
            self.rdo_ativ_parent_id = opt.get("parent_id", "")
        else:
            self.rdo_ativ_total_qty = "0"
            self.rdo_ativ_exec_qty = "0"
            self.rdo_ativ_unidade = ""
            self.rdo_ativ_nivel = "micro"
            self.rdo_ativ_parent_id = ""

    def set_rdo_progresso_atividade(self, v): self.rdo_progresso_atividade = str(v)
    def set_rdo_producao_dia(self, v): self.rdo_producao_dia = str(v) if v is not None else ""
    def toggle_rdo_nova_atividade(self): self.rdo_nova_atividade = not self.rdo_nova_atividade
    def set_rdo_nova_atividade_nome(self, v: str): self.rdo_nova_atividade_nome = v
    def set_rdo_nova_atividade_fase(self, v: str): self.rdo_nova_atividade_fase = v

    def add_nova_atividade_nao_mapeada(self):
        """Add a new unmapped activity slot."""
        import time
        new_list = list(self.rdo_novas_atividades)
        new_list.append({"_key": str(int(time.time() * 1000) + len(new_list)), "nome": "", "fase": "", "progresso": "0"})
        self.rdo_novas_atividades = new_list

    def remove_nova_atividade(self, key: str):
        self.rdo_novas_atividades = [r for r in self.rdo_novas_atividades if r.get("_key", "") != key]

    def set_nova_atividade_nome(self, key: str, v: str):
        self.rdo_novas_atividades = [
            {**r, "nome": v} if r.get("_key") == key else r
            for r in self.rdo_novas_atividades
        ]

    def set_nova_atividade_fase(self, key: str, v: str):
        self.rdo_novas_atividades = [
            {**r, "fase": v} if r.get("_key") == key else r
            for r in self.rdo_novas_atividades
        ]

    def set_nova_atividade_progresso(self, key: str, v: str):
        self.rdo_novas_atividades = [
            {**r, "progresso": str(v)} if r.get("_key") == key else r
            for r in self.rdo_novas_atividades
        ]

    def add_extra_atividade(self):
        """Add a new blank extra activity slot with a unique key."""
        import time
        new_list = list(self.rdo_extra_atividades)
        new_list.append({
            "id": "", "nome": "", "progresso": "0", "_key": str(int(time.time() * 1000) + len(new_list)),
            "total_qty": "0", "exec_qty": "0", "unidade": "", "producao_dia": "",
            "fase_macro_sel": "",  # two-step: phase selection before activity
            "efetivo_alocado": "",  # quantas pessoas trabalharam nesta atividade hoje
        })
        self.rdo_extra_atividades = new_list

    def set_extra_fase_macro(self, key: str, v: str):
        """Select macro phase for an extra activity, resetting the activity selection."""
        real_v = "" if v == "__none__" else v
        self.rdo_extra_atividades = [
            {**r, "fase_macro_sel": real_v, "id": "", "nome": "", "progresso": "0",
             "total_qty": "0", "exec_qty": "0", "unidade": "", "producao_dia": ""}
            if r.get("_key", "") == key else r
            for r in self.rdo_extra_atividades
        ]

    def remove_extra_atividade(self, key: str):
        """Remove extra activity by its _key."""
        new_list = [r for r in self.rdo_extra_atividades if r.get("_key", "") != key]
        self.rdo_extra_atividades = new_list

    def set_extra_atividade_id(self, key: str, v: str):
        """Set activity id + carry qty metadata by _key."""
        real_v = "" if v == "__none__" else v
        opt = next((o for o in self.hub_atividades_options if o.get("id") == real_v), None)
        nome = opt["label"] if opt else ""
        pct = opt.get("pct", "0") if opt else None
        total_qty = opt.get("total_qty", "0") if opt else "0"
        exec_qty = opt.get("exec_qty", "0") if opt else "0"
        unidade = opt.get("unidade", "") if opt else ""
        self.rdo_extra_atividades = [
            {**r, "id": real_v, "nome": nome,
             "total_qty": total_qty, "exec_qty": exec_qty, "unidade": unidade, "producao_dia": "",
             **({"progresso": pct} if pct is not None else {})}
            if r.get("_key", "") == key else r
            for r in self.rdo_extra_atividades
        ]

    def set_extra_atividade_progresso(self, key: str, v: str):
        """Set manual progress % by _key (only used when total_qty == 0)."""
        self.rdo_extra_atividades = [
            {**r, "progresso": str(v)} if r.get("_key", "") == key else r
            for r in self.rdo_extra_atividades
        ]

    def set_extra_atividade_producao(self, key: str, v: str):
        """Set daily production quantity by _key."""
        self.rdo_extra_atividades = [
            {**r, "producao_dia": str(v)} if r.get("_key", "") == key else r
            for r in self.rdo_extra_atividades
        ]

    def set_extra_atividade_efetivo(self, key: str, v: str):
        """Set team size allocated to this activity today by _key."""
        self.rdo_extra_atividades = [
            {**r, "efetivo_alocado": str(v)} if r.get("_key", "") == key else r
            for r in self.rdo_extra_atividades
        ]

    @rx.event(background=True)
    async def load_hub_atividades(self, contrato: str):
        """Load available activities from hub_atividades for the given contract."""
        if not contrato:
            return
        async with self:
            self.hub_atividades_loading = True
            self.hub_atividades_options = []

        from bomtempo.core.supabase_client import sb_select as _sb_select
        try:
            rows = _sb_select(
                "hub_atividades",
                filters={"contrato": contrato},
                limit=300,
            )

            def _fase_sort_key(r: dict) -> tuple:
                fase = str(r.get("fase", "") or "")
                parts = []
                for seg in fase.split("."):
                    try:
                        parts.append(int(seg))
                    except ValueError:
                        parts.append(0)
                return tuple(parts) if parts else (9999,)

            # Filter first
            filtered = [
                r for r in (rows or [])
                if r.get("id") and r.get("atividade")
                and not str(r.get("pendente_aprovacao", "")).upper() in ("TRUE", "1")
                and str(r.get("status_atividade", "") or "") not in ("cancelada", "bloqueada")
            ]

            # Build hierarchy: macros → micros → subs, each sorted by fase
            macros = sorted([r for r in filtered if r.get("nivel", "macro") in ("macro", "")], key=_fase_sort_key)
            micros_all = sorted([r for r in filtered if r.get("nivel") == "micro"], key=_fase_sort_key)
            subs_all = sorted([r for r in filtered if r.get("nivel") == "sub"], key=_fase_sort_key)

            micros_by_parent: dict = {}
            for m in micros_all:
                pid = str(m.get("parent_id", "") or "")
                micros_by_parent.setdefault(pid, []).append(m)

            subs_by_parent: dict = {}
            for s in subs_all:
                pid = str(s.get("parent_id", "") or "")
                subs_by_parent.setdefault(pid, []).append(s)

            def _build_opt(r: dict, prefix: str) -> dict:
                fase = str(r.get("fase", "") or "")
                nome = str(r.get("atividade", ""))
                return {
                    "id":               str(r.get("id", "")),
                    "label":            f"{prefix}{fase} {nome}".strip(),
                    "fase_macro":       str(r.get("fase_macro", "") or "Geral"),
                    "nivel":            str(r.get("nivel", "macro") or "macro"),
                    "parent_id":        str(r.get("parent_id", "") or ""),
                    "pct":              str(int(r.get("conclusao_pct", 0) or 0)),
                    "total_qty":        str(r.get("total_qty", 0) or 0),
                    "exec_qty":         str(r.get("exec_qty", 0) or 0),
                    "unidade":          str(r.get("unidade", "") or ""),
                    "status_atividade": str(r.get("status_atividade", "") or "nao_iniciada"),
                    "tipo_medicao":     str(r.get("tipo_medicao", "") or "quantidade"),
                    "efetivo_alocado":  str(r.get("efetivo_alocado", 0) or 0),
                    "inicio_previsto":  str(r.get("inicio_previsto", "") or ""),
                    "termino_previsto": str(r.get("termino_previsto", "") or ""),
                }

            opts: list = []
            for macro in macros:
                macro_id = str(macro.get("id", ""))
                opts.append(_build_opt(macro, ""))
                for micro in micros_by_parent.get(macro_id, []):
                    micro_id = str(micro.get("id", ""))
                    opts.append(_build_opt(micro, "  ↳ "))
                    for sub in subs_by_parent.get(micro_id, []):
                        opts.append(_build_opt(sub, "    ↳↳ "))

        except Exception as e:
            logger.error(f"load_hub_atividades error: {e}")
            opts = []

        async with self:
            self.hub_atividades_options = opts
            self.hub_atividades_loading = False

    # ── Draft Save ────────────────────────────────────────────

    @rx.event(background=True)
    async def save_draft(self):
        """Salva rascunho manualmente (botão) ou acionado por mudanças."""
        async with self:
            if self.is_draft_saving:
                return
            if not self.rdo_contrato.strip():
                return
            self.is_draft_saving = True

        from bomtempo.state.global_state import GlobalState
        async with self:
            # get_state dentro do async with self (exigido pelo StateProxy)
            gs = await self.get_state(GlobalState)
            user = str(gs.current_user_name)
            rdo_data = self._build_rdo_data()

        loop = asyncio.get_running_loop()
        try:
            id_rdo = await loop.run_in_executor(
                get_db_executor(),
                lambda: RDOService.upsert_draft(rdo_data, mestre_id=user),
            )
            async with self:
                self.draft_id_rdo   = id_rdo
                self.draft_saved_at = datetime.now().strftime("%H:%M")
                self.is_draft_saving = False
        except Exception as e:
            logger.error(f"❌ save_draft: {e}")
            async with self:
                self.is_draft_saving = False
            yield rx.toast("⚠️ Erro ao salvar rascunho", position="top-center")

    # ── Submit ────────────────────────────────────────────────

    def open_confirm(self):
        if not self.rdo_contrato.strip():
            return rx.toast("⚠️ Informe o Contrato antes de enviar", position="top-center")
        if not self.rdo_data:
            return rx.toast("⚠️ Informe a Data antes de enviar", position="top-center")
        if not self.checkin_done:
            return rx.toast("⚠️ Registre o Check-in GPS antes de enviar o RDO", position="top-center", duration=4000)
        if not self.checkout_done:
            return rx.toast("⚠️ Registre o Check-out GPS antes de enviar o RDO", position="top-center", duration=4000)
        # Captura assinatura do canvas ANTES de abrir dialog (JPEG 70% — sem erro de WS)
        return rx.call_script(
            """(function(){
              var c=document.getElementById('sig-canvas');
              if(!c) return {sig:'',open:true};
              var tmp=document.createElement('canvas');
              tmp.width=c.width;tmp.height=c.height;
              var ctx=tmp.getContext('2d');
              ctx.fillStyle='#ffffff';ctx.fillRect(0,0,tmp.width,tmp.height);
              ctx.drawImage(c,0,0);
              return {sig:tmp.toDataURL('image/jpeg',0.70),open:true};
            })()""",
            callback=RDOState.receive_sig_and_open,
        )

    def receive_sig_and_open(self, data):
        """Callback do rx.call_script: salva assinatura e abre dialog de confirmação."""
        if isinstance(data, dict):
            sig = str(data.get("sig", ""))
            if sig.startswith("data:image"):
                self.signatory_sig_b64 = sig
        self.show_confirm_dialog = True

    def close_confirm(self):
        self.show_confirm_dialog = False

    async def submit_rdo(self):
        if self.is_submitting:
            return
        self.is_submitting = True
        self.show_confirm_dialog = False
        # Libera a tela imediatamente — limpa o overlay antes do redirect
        self.submit_status = ""
        self.is_submitting = False
        yield rx.toast(
            "⏳ RDO enviado! Processando PDF e análise IA em background. Você receberá o email em breve.",
            position="top-center",
            duration=8000,
        )
        yield rx.redirect("/rdo-historico")
        yield RDOState.execute_submit

    @rx.event(background=True)
    async def execute_submit(self):
        from bomtempo.core.audit_logger import audit_log, AuditCategory
        from bomtempo.core.executors import get_ai_executor, get_heavy_executor, get_db_executor, get_http_executor
        from bomtempo.core.circuit_breaker import ia_breaker, pdf_breaker

        loop = asyncio.get_running_loop()

        try:
            # ── Snapshot state variables — get_state MUST be OUTSIDE async with self:
            from bomtempo.state.global_state import GlobalState
            async with self:
                # get_state de outro estado (GlobalState) usa lock Redis DIFERENTE do RDOState —
                # sem deadlock. O LockExpiredError era causado por I/O lento (httpx/SMTP) dentro
                # do lock, não pelo get_state. Aqui só lemos state e fazemos operações síncronas rápidas.
                gs = await self.get_state(GlobalState)
                user_name = str(gs.current_user_name)
                rdo_data  = self._build_rdo_data()
                contrato  = rdo_data.get("contrato", "")
                _submit_client_id = rdo_data.get("client_id") or ""
                self.submit_status = "💾 Salvando RDO…"
                # Clear large ephemeral state immediately so all subsequent
                # async with self: blocks serialize a smaller state to Redis.
                # signatory_sig_b64 = base64 JPEG (10–100KB); hub_atividades_options
                # = potentially hundreds of items — both safe to clear now.
                self.signatory_sig_b64 = ""
                self.hub_atividades_options = []

            if not _submit_client_id:
                async with self:
                    self.submit_error = "Erro: tenant não identificado. Faça logout e login novamente."
                    self.is_submitting = False
                    self.submit_status = ""
                return

            # 1. Upsert draft / save to DB
            id_rdo = await loop.run_in_executor(
                get_db_executor(),
                lambda: RDOService.upsert_draft(rdo_data, mestre_id=user_name),
            )
            logger.info(f"💾 RDO2 salvo: {id_rdo}")

            # Status updates are best-effort — don't block on failures
            try:
                async with self:
                    self.submit_status = "🤖 Análise IA…"
            except Exception:
                pass

            # ── Feature flags — resolve uma vez, usa em todo o fluxo ───────────
            from bomtempo.core.feature_flags import (
                FeatureFlagsService as _FFS,
                FEATURE_PDF_GENERATION, FEATURE_EMAIL_SEND,
                FEATURE_AI_INSIGHT, FEATURE_RDO_VIEW,
            )
            _ff_contract = str(contrato)
            _flag_ai     = await loop.run_in_executor(get_db_executor(), lambda: _FFS.is_enabled(FEATURE_AI_INSIGHT,     _ff_contract))
            _flag_pdf    = await loop.run_in_executor(get_db_executor(), lambda: _FFS.is_enabled(FEATURE_PDF_GENERATION,  _ff_contract))
            _flag_email  = await loop.run_in_executor(get_db_executor(), lambda: _FFS.is_enabled(FEATURE_EMAIL_SEND,      _ff_contract))
            _flag_view   = await loop.run_in_executor(get_db_executor(), lambda: _FFS.is_enabled(FEATURE_RDO_VIEW,        _ff_contract))
            logger.info(f"🚩 Feature flags [{_ff_contract}]: ai={_flag_ai} pdf={_flag_pdf} email={_flag_email} view={_flag_view}")

            # 2. Run AI analysis BEFORE PDF so the PDF contains the real analysis text
            ai_summary = ""
            if not _flag_ai:
                logger.info("🚩 AI insight desabilitado via feature flag — pulando")
            elif not ia_breaker.is_open():
                try:
                    _d_for_ai = dict(rdo_data)
                    _id_for_ai = str(id_rdo)
                    ai_summary = await asyncio.wait_for(
                        loop.run_in_executor(
                            get_ai_executor(),
                            lambda: RDOService.analyze_now(_d_for_ai, _id_for_ai),
                        ),
                        timeout=70.0,
                    )
                    ia_breaker.record_success()
                except asyncio.TimeoutError:
                    ia_breaker.record_failure()
                    logger.warning("⚠️ AI analysis timeout após 70s — continuando sem resumo IA")
                except Exception as e:
                    ia_breaker.record_failure(e)
                    logger.error(f"⚠️ AI: {e}")
            else:
                logger.warning("⚠️ Circuit breaker IA aberto — pulando análise para este RDO")

            # Inject ai_summary into rdo_data so build_html renders it in PDF
            rdo_data_with_ai = {**rdo_data, "ai_summary": ai_summary}

            # 3. Generate PDF (feature flag + circuit breaker + backpressure)
            pdf_path = ""
            _pdf_skipped_reason = ""

            if not _flag_pdf:
                _pdf_skipped_reason = "desabilitado via feature flag (servidor 1GB)"
                logger.info("🚩 PDF desabilitado via feature flag — pulando geração")
            else:
                try:
                    async with self:
                        self.submit_status = "📄 Gerando PDF…"
                except Exception:
                    pass

                # 3a. Marca status=processando_pdf antes de iniciar — rastreável se crashar
                await loop.run_in_executor(
                    get_db_executor(),
                    lambda: RDOService.mark_processing(id_rdo),
                )

                if pdf_breaker.is_open():
                    _pdf_skipped_reason = "circuit breaker PDF aberto (falhas recentes)"
                    logger.warning(f"⚠️ Pulando geração de PDF: {_pdf_skipped_reason}")
                else:
                    try:
                        _pending = get_heavy_executor()._work_queue.qsize()
                    except Exception:
                        _pending = 0

                    if _pending >= 3:
                        _pdf_skipped_reason = f"fila PDF cheia ({_pending} jobs pendentes)"
                        logger.warning(f"⚠️ Backpressure PDF: {_pdf_skipped_reason}")
                        pdf_breaker.record_failure(Exception(_pdf_skipped_reason))
                    else:
                        try:
                            pdf_result = await asyncio.wait_for(
                                loop.run_in_executor(
                                    get_heavy_executor(),
                                    lambda: RDOService.generate_pdf(rdo_data_with_ai, is_preview=False, id_rdo=id_rdo),
                                ),
                                timeout=400.0,
                            )
                            pdf_path = pdf_result[0] if pdf_result else ""
                            if pdf_path:
                                pdf_breaker.record_success()
                            else:
                                pdf_breaker.record_failure(Exception("generate_pdf returned empty path"))
                        except asyncio.TimeoutError:
                            pdf_breaker.record_failure(Exception("timeout 400s"))
                            logger.error("⚠️ PDF generation timeout total — continuando sem PDF")
                        except Exception as e:
                            pdf_breaker.record_failure(e)
                            logger.error(f"⚠️ PDF: {e}")

            try:
                async with self:
                    self.submit_status = "☁️ Enviando PDF…"
            except Exception:
                pass

            # 4. Upload PDF
            # Use get_http_executor() — upload is just HTTP to Supabase, not CPU/memory heavy.
            # Using get_heavy_executor() here was wrong: it caused upload to queue behind OTHER
            # users' PDF generation (1-worker pool), delaying completion by 30-90s unnecessarily.
            pdf_url = ""
            if pdf_path:
                try:
                    pdf_url = await loop.run_in_executor(
                        get_http_executor(),
                        lambda: RDOService.upload_pdf(pdf_path, id_rdo),
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Upload PDF: {e}")

            try:
                async with self:
                    self.submit_status = "✅ Finalizando…"
            except Exception:
                pass

            # 5. Finalize in DB (status: processando_pdf → finalizado)
            await loop.run_in_executor(
                get_db_executor(),
                lambda: RDOService.finalize_rdo(id_rdo, pdf_path, pdf_url, rdo_data_with_ai),
            )

            # 5b-pre. Propagate equipe_alocada → contratos.equipe_presente_hoje
            _equipe_val = rdo_data.get("equipe_alocada")
            if _equipe_val is not None:
                try:
                    from bomtempo.core.supabase_client import sb_update as _sb_upd_eq
                    await loop.run_in_executor(
                        get_db_executor(),
                        lambda: _sb_upd_eq(
                            "contratos",
                            filters={"contrato": contrato, "client_id": _submit_client_id},
                            data={"equipe_presente_hoje": int(_equipe_val)},
                        ),
                    )
                    logger.info(f"✅ equipe_presente_hoje atualizado: {_equipe_val} — contrato {contrato}")
                except Exception as _eq_err:
                    logger.warning(f"⚠️ Falha ao propagar equipe_alocada: {_eq_err}")

            # 5b. Cronograma integration: update activity progress or create pending
            async with self:
                _ativ_id = str(self.rdo_atividade_id)
                _progresso = int(self.rdo_progresso_atividade or "0")
                _producao_dia_str = str(self.rdo_producao_dia or "").strip()
                _nova_ativ = bool(self.rdo_nova_atividade)
                _nova_nome = str(self.rdo_nova_atividade_nome)
                _nova_fase = str(self.rdo_nova_atividade_fase)
                _extra_ativs = [dict(r) for r in self.rdo_extra_atividades]
                _novas_ativs = [dict(r) for r in self.rdo_novas_atividades]
                try:
                    _efetivo_primaria = int(str(self.rdo_efetivo_primaria or "").strip() or "0")
                except Exception:
                    _efetivo_primaria = 0

            if _ativ_id:
                try:
                    from bomtempo.core.supabase_client import sb_update as _sb_upd, sb_select as _sb_sel2, sb_insert as _sb_ins2
                    # Fetch current state for history
                    cur_rows = await loop.run_in_executor(get_db_executor(), lambda: _sb_sel2("hub_atividades", filters={"id": _ativ_id}))
                    # If this activity has sub-children, direct % update from RDO is skipped —
                    # the % is driven by subs' weighted average instead.
                    # Only exec_qty accumulation and history are recorded.
                    _has_subs = await loop.run_in_executor(
                        get_db_executor(), lambda: bool(_sb_sel2("hub_atividades", filters={"parent_id": _ativ_id, "nivel": "sub"}, limit=1))
                    )
                    cur_pct = int((cur_rows[0].get("conclusao_pct", 0) or 0) if cur_rows else 0)
                    # If activity has subs, conclusao_pct is driven by subs' weighted avg — don't overwrite
                    upd_data: dict = {} if _has_subs else {"conclusao_pct": _progresso}
                    # Accumulate exec_qty if daily production was informed
                    if _producao_dia_str:
                        try:
                            producao_dia = float(_producao_dia_str.replace(",", "."))
                            cur_exec = float((cur_rows[0].get("exec_qty", 0) or 0) if cur_rows else 0)
                            total_qty = float((cur_rows[0].get("total_qty", 0) or 0) if cur_rows else 0)
                            new_exec = cur_exec + producao_dia
                            upd_data["exec_qty"] = new_exec
                            # Auto-calc % only if activity has no subs (subs drive the % instead)
                            if total_qty > 0 and not _has_subs:
                                new_pct = min(100, int((new_exec / total_qty) * 100))
                                upd_data["conclusao_pct"] = new_pct
                                _progresso = new_pct
                        except Exception:
                            pass
                    # Auto-update status_atividade based on progress (always, even for activities with subs)
                    cur_status = (cur_rows[0].get("status_atividade", "") or "") if cur_rows else ""
                    if _progresso >= 100 and not _has_subs:
                        upd_data["status_atividade"] = "concluida"
                    elif _progresso > 0 and cur_status in ("nao_iniciada", "pronta_iniciar", "") and not _has_subs:
                        upd_data["status_atividade"] = "em_execucao"
                    # Propagar data de referência do RDO como âncora temporal do cronograma
                    # Isso permite que _compute_forecast_rows use min(today, last_rdo_date)
                    # evitando que preenchimento retroativo avance dias além da data do RDO
                    _rdo_ref_date = rdo_data.get("data", "")  # formato YYYY-MM-DD
                    if _rdo_ref_date:
                        upd_data["last_rdo_date"] = _rdo_ref_date
                    # Registra efetivo alocado nesta atividade (pessoas hoje)
                    if _efetivo_primaria > 0:
                        upd_data["efetivo_alocado"] = _efetivo_primaria

                    # Update progress + qty + status + last_rdo_date + efetivo
                    if upd_data:
                        await loop.run_in_executor(get_db_executor(), lambda: _sb_upd("hub_atividades", filters={"id": _ativ_id}, data=upd_data))

                    # ── Cascade: recalculate parent(s) weighted progress ──────────
                    # If we updated a sub → recalculate micro parent
                    # If we updated a micro → recalculate macro parent
                    # Both are handled by the same recursive helper
                    _upd_row = cur_rows[0] if cur_rows else {}
                    _direct_parent_id = str(_upd_row.get("parent_id", "") or "")

                    async def _recalc_parent_progress(parent_id: str):
                        """Recalculate a parent's conclusao_pct from its children's weighted avg."""
                        if not parent_id:
                            return
                        try:
                            children = await loop.run_in_executor(
                                get_db_executor(), lambda: _sb_sel2("hub_atividades", filters={"parent_id": parent_id}, limit=200)
                            )
                            if not children:
                                return
                            total_peso = sum(float(c.get("peso_pct", 0) or 0) for c in children)
                            if total_peso <= 0:
                                # Fall back to simple average
                                avg_pct = sum(float(c.get("conclusao_pct", 0) or 0) for c in children) / len(children)
                            else:
                                avg_pct = sum(
                                    float(c.get("conclusao_pct", 0) or 0) * float(c.get("peso_pct", 0) or 0)
                                    for c in children
                                ) / total_peso
                            new_parent_pct = min(100, int(round(avg_pct)))
                            # Auto status
                            p_rows = await loop.run_in_executor(
                                get_db_executor(), lambda: _sb_sel2("hub_atividades", filters={"id": parent_id}, limit=1)
                            )
                            p_status = str((p_rows[0].get("status_atividade", "") or "") if p_rows else "")
                            p_update: dict = {"conclusao_pct": new_parent_pct}
                            if new_parent_pct >= 100:
                                p_update["status_atividade"] = "concluida"
                            elif new_parent_pct > 0 and p_status in ("nao_iniciada", "pronta_iniciar", ""):
                                p_update["status_atividade"] = "em_execucao"
                            await loop.run_in_executor(
                                get_db_executor(), lambda: _sb_upd("hub_atividades", filters={"id": parent_id}, data=p_update)
                            )
                            logger.info(f"✅ Cascata: parent {parent_id} → {new_parent_pct}%")
                            # Recurse: recalculate grandparent if parent has a parent
                            grand_parent_id = str((p_rows[0].get("parent_id", "") or "") if p_rows else "")
                            if grand_parent_id:
                                await _recalc_parent_progress(grand_parent_id)
                        except Exception as _ce:
                            logger.warning(f"⚠️ Cascata recalc parent {parent_id}: {_ce}")

                    if _direct_parent_id:
                        await _recalc_parent_progress(_direct_parent_id)
                    # Insert history record (full production snapshot)
                    _cid = rdo_data.get("client_id") or None
                    _hist_prod = float(_producao_dia_str.replace(",", ".")) if _producao_dia_str else None
                    _hist_exec = upd_data.get("exec_qty")
                    _hist_total = float((cur_rows[0].get("total_qty", 0) or 0) if cur_rows else 0) or None
                    _hist_unidade = str((cur_rows[0].get("unidade", "") or "") if cur_rows else "")
                    _hist_data = rdo_data.get("data") or None
                    await loop.run_in_executor(get_db_executor(), lambda: _sb_ins2("hub_atividade_historico", {
                        "atividade_id":         _ativ_id,
                        "contrato":             contrato,
                        "rdo_id":               id_rdo,
                        "data":                 _hist_data,
                        "conclusao_pct_anterior": cur_pct,
                        "conclusao_pct_novo":   _progresso,
                        "producao_dia":         _hist_prod,
                        "exec_qty_novo":        _hist_exec,
                        "total_qty":            _hist_total,
                        "unidade":              _hist_unidade or None,
                        "registrado_por":       user_name,
                        "client_id":            _cid,
                    }))
                    logger.info(f"✅ Cronograma atualizado: atividade {_ativ_id} → {_progresso}%")
                except Exception as e:
                    logger.warning(f"⚠️ Cronograma update: {e}")
            elif _nova_ativ and _nova_nome:
                try:
                    from bomtempo.core.supabase_client import sb_insert as _sb_ins3
                    _cid3 = rdo_data.get("client_id") or None
                    await loop.run_in_executor(get_db_executor(), lambda: _sb_ins3("hub_atividades", {
                        "contrato": contrato,
                        "atividade": _nova_nome,
                        "fase_macro": _nova_fase or "Geral",
                        "conclusao_pct": _progresso,
                        "critico": False,
                        "nivel": "macro",
                        "pendente_aprovacao": True,
                        "created_by": user_name,
                        "client_id": _cid3,
                    }))
                    logger.info(f"✅ Atividade pendente criada: '{_nova_nome}'")
                except Exception as e:
                    logger.warning(f"⚠️ Create pending activity: {e}")

            # 5b-novas. Create unmapped (pending) activities
            for _na in _novas_ativs:
                _na_nome = _na.get("nome", "").strip()
                _na_fase = _na.get("fase", "").strip() or "Geral"
                _na_pct = int(_na.get("progresso", "0") or "0")
                if not _na_nome:
                    continue
                try:
                    from bomtempo.core.supabase_client import sb_insert as _sb_ins_na
                    _cid_na = rdo_data.get("client_id") or None
                    await loop.run_in_executor(get_db_executor(), lambda n=_na_nome, f=_na_fase, p=_na_pct: _sb_ins_na("hub_atividades", {
                        "contrato": contrato,
                        "atividade": n,
                        "fase_macro": f,
                        "conclusao_pct": p,
                        "critico": False,
                        "nivel": "macro",
                        "pendente_aprovacao": True,
                        "created_by": user_name,
                        "client_id": _cid_na,
                    }))
                    logger.info(f"✅ Atividade não mapeada criada: '{_na_nome}'")
                except Exception as e:
                    logger.warning(f"⚠️ Create unmapped activity: {e}")

            # 5b-extra. Process additional activity updates
            for _extra in _extra_ativs:
                _ex_id = _extra.get("id", "")
                _ex_pct = int(_extra.get("progresso", "0") or "0")
                _ex_prod_str = str(_extra.get("producao_dia", "") or "").strip()
                if not _ex_id:
                    continue
                try:
                    from bomtempo.core.supabase_client import sb_update as _sb_upd_ex, sb_select as _sb_sel_ex, sb_insert as _sb_ins_ex
                    _cur = await loop.run_in_executor(get_db_executor(), lambda i=_ex_id: _sb_sel_ex("hub_atividades", filters={"id": i}))
                    _cur_pct = int((_cur[0].get("conclusao_pct", 0) or 0) if _cur else 0)
                    _ex_upd: dict = {"conclusao_pct": _ex_pct}
                    _ex_hist_prod = None
                    _ex_hist_exec = None
                    _ex_hist_total = None
                    _ex_hist_unidade = str((_cur[0].get("unidade", "") or "") if _cur else "")
                    # Accumulate exec_qty if daily production was informed
                    if _ex_prod_str:
                        try:
                            _ex_prod_f = float(_ex_prod_str.replace(",", "."))
                            _ex_cur_exec = float((_cur[0].get("exec_qty", 0) or 0) if _cur else 0)
                            _ex_total = float((_cur[0].get("total_qty", 0) or 0) if _cur else 0)
                            _ex_new_exec = _ex_cur_exec + _ex_prod_f
                            _ex_upd["exec_qty"] = _ex_new_exec
                            if _ex_total > 0:
                                _ex_pct = min(100, int((_ex_new_exec / _ex_total) * 100))
                                _ex_upd["conclusao_pct"] = _ex_pct
                            _ex_hist_prod = _ex_prod_f
                            _ex_hist_exec = _ex_new_exec
                            _ex_hist_total = _ex_total or None
                        except Exception:
                            pass
                    # Auto-update status
                    _ex_cur_status = ((_cur[0].get("status_atividade", "") or "") if _cur else "")
                    if _ex_pct >= 100:
                        _ex_upd["status_atividade"] = "concluida"
                    elif _ex_pct > 0 and _ex_cur_status in ("nao_iniciada", "pronta_iniciar", ""):
                        _ex_upd["status_atividade"] = "em_execucao"
                    # Propagar data de referência do RDO como âncora temporal
                    _ex_rdo_date = rdo_data.get("data", "")
                    if _ex_rdo_date:
                        _ex_upd["last_rdo_date"] = _ex_rdo_date
                    await loop.run_in_executor(get_db_executor(), lambda i=_ex_id, d=_ex_upd: _sb_upd_ex("hub_atividades", filters={"id": i}, data=d))
                    _cid_ex = rdo_data.get("client_id") or None
                    _ex_data = rdo_data.get("data") or None
                    await loop.run_in_executor(get_db_executor(), lambda i=_ex_id, p=_ex_pct, cp=_cur_pct, hp=_ex_hist_prod, he=_ex_hist_exec, ht=_ex_hist_total, hu=_ex_hist_unidade, dd=_ex_data: _sb_ins_ex("hub_atividade_historico", {
                        "atividade_id": i,
                        "contrato": contrato,
                        "rdo_id": id_rdo,
                        "data": dd,
                        "conclusao_pct_anterior": cp,
                        "conclusao_pct_novo": p,
                        "producao_dia": hp,
                        "exec_qty_novo": he,
                        "total_qty": ht,
                        "unidade": hu or None,
                        "registrado_por": user_name,
                        "client_id": _cid_ex,
                    }))
                    logger.info(f"✅ Extra atividade {_ex_id} → {_ex_pct}%")
                    # Cascade: recalculate parent(s) weighted progress
                    _ex_parent_id = str((_cur[0].get("parent_id", "") or "") if _cur else "")
                    if _ex_parent_id:
                        await _recalc_parent_progress(_ex_parent_id)
                except Exception as e:
                    logger.warning(f"⚠️ Extra atividade update: {e}")

            # 5c. Sync photos to hub_auditoria_imgs (galeria de campo)
            try:
                from bomtempo.core.supabase_client import sb_insert as _sb_ins_aud
                from datetime import date as _date_aud
                _today = _date_aud.today().isoformat()
                _sync_photos = []
                if epi_url := rdo_data_with_ai.get("epi_foto_url", ""):
                    _sync_photos.append({"categoria": "equipe", "url": epi_url, "legenda": "Equipe com EPIs"})
                if ferr_url := rdo_data_with_ai.get("ferramentas_foto_url", ""):
                    _sync_photos.append({"categoria": "ferramentas", "url": ferr_url, "legenda": "Ferramentas Limpas"})
                _evidencias = rdo_data_with_ai.get("evidencias") or []
                logger.info(f"📸 Sync galeria: {len(_evidencias)} evidências gerais, epi={bool(rdo_data_with_ai.get('epi_foto_url'))}, ferr={bool(rdo_data_with_ai.get('ferramentas_foto_url'))}")
                for ev in _evidencias:
                    ev_url = ev.get("foto_url", "") or ev.get("url", "")
                    if ev_url:
                        _sync_photos.append({"categoria": "gerais", "url": ev_url, "legenda": ev.get("legenda", "Imagem geral")})
                for _ph in _sync_photos:
                    try:
                        _cid_aud = rdo_data.get("client_id") or None
                        await loop.run_in_executor(get_db_executor(), lambda ph=_ph, c=_cid_aud: _sb_ins_aud("hub_auditoria_imgs", {
                            "contrato": contrato,
                            "categoria": ph["categoria"],
                            "url": ph["url"],
                            "legenda": ph["legenda"],
                            "autor": user_name,
                            "data_captura": _today,
                            "client_id": c,
                        }))
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"⚠️ hub_auditoria_imgs sync: {e}")

            # 5d. Build view URL (feature flag: rdo_view)
            view_url = ""
            if _flag_view:
                from bomtempo.core.supabase_client import sb_select
                master_rows = await loop.run_in_executor(
                    get_db_executor(),
                    lambda: sb_select("rdo_master", filters={"id_rdo": id_rdo}),
                )
                view_token = (master_rows[0].get("view_token") or "") if master_rows else ""
                view_url = f"/rdo-view/{view_token}" if view_token else f"/rdo-view/{id_rdo}"
            else:
                logger.info("🚩 RDO view desabilitado via feature flag")

            # 6. Get email recipients + send (feature flag: email_send)
            from bomtempo.core.supabase_client import sb_select as _sb_select
            recipients = []
            if not _flag_email:
                logger.info("🚩 Email desabilitado via feature flag — pulando envio")
            else:
                try:
                    rows = await loop.run_in_executor(
                        get_db_executor(),
                        lambda: _sb_select("email_sender", filters={"module": "rdo"}),
                    )
                    recipients = [r.get("email", "").strip() for r in (rows or []) if r.get("email", "").strip()]
                except Exception:
                    pass

                # Fire-and-forget via http_executor — sem PDF mas com link online
                _d, _p, _r, _vu, _ai = dict(rdo_data_with_ai), str(pdf_path), list(recipients), str(view_url), str(ai_summary)

                def _send_email_task():
                    if not _r:
                        return
                    try:
                        RDOService.send_email(_r, _d, _p, _vu, _ai)
                    except Exception as e:
                        logger.error(f"Email: {e}")

                asyncio.ensure_future(loop.run_in_executor(get_http_executor(), _send_email_task))

            # Audit
            audit_log(
                category=AuditCategory.RDO_CREATE,
                action=f"RDO2 criado — contrato '{contrato}'",
                username=user_name,
                entity_type="rdo2",
                entity_id=id_rdo,
                metadata={"contrato": contrato, "data": rdo_data.get("data", "")},
                status="success",
            )

            # Invalidate data cache so hub/financeiro reload fresh data next visit
            try:
                from bomtempo.core.data_loader import DataLoader as _DL
                _DL.invalidate_cache()
            except Exception:
                pass

            # Invalida cache do cronograma no Hub e recarrega se estava aberto
            try:
                from bomtempo.state.hub_state import HubState as _HS
                yield _HS.reload_after_rdo(contrato)
            except Exception:
                pass

            # Trigger Agente de Atividades com o novo RDO como chave de cache
            try:
                from bomtempo.state.hub_state import HubState as _HS
                yield _HS.run_agente_atividades(contrato, rdo_id=str(id_rdo))
            except Exception:
                pass

            # AlertEngine: verifica regras de evento "rdo_submitted" em background
            try:
                from bomtempo.core.alert_engine import AlertEngine
                AlertEngine.check_event(
                    event_type="rdo_submitted",
                    contrato=contrato,
                    client_id=_submit_client_id,
                    metadata={"rdo_id": str(id_rdo)},
                )
            except Exception:
                pass

            parts = ["✅ RDO finalizado com sucesso!"]
            if not _flag_pdf:
                parts.append("📄 PDF desabilitado — disponível após upgrade do servidor.")
            elif pdf_url:
                parts.append("PDF gerado.")
            elif _pdf_skipped_reason:
                parts.append(f"⚠️ PDF não gerado ({_pdf_skipped_reason}) — use 'Gerar PDF' no histórico.")
            else:
                parts.append("⚠️ PDF pendente — use 'Gerar PDF' no histórico.")
            if view_url:
                parts.append("🔗 Link de visualização disponível.")
            if _flag_email and recipients:
                parts.append(f"📧 Email enviado para {len(recipients)} destinatário(s).")
            toast_msg = " ".join(parts)
            # Wrap in try/except — if Redis is slow and lock expires, we still want to
            # log success and not leave the UI in a broken state.
            try:
                async with self:
                    self._reset_form()
                    self.is_submitting = False
                    self.submit_status = ""
                    yield rx.toast(toast_msg, position="top-center", duration=8000)
            except Exception as _final_err:
                logger.error(f"⚠️ execute_submit final state update failed: {_final_err}")
                # RDO was successfully saved/emailed — just state update failed.
                # Attempt minimal reset without yield
                try:
                    async with self:
                        self.is_submitting = False
                        self.submit_status = ""
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"❌ execute_submit: {e}", exc_info=True)
            try:
                async with self:
                    self.submit_error = str(e)[:100]
                    yield rx.toast(f"❌ Erro no processamento do RDO: {str(e)[:80]}", position="top-center", duration=8000)
            except Exception:
                pass

        finally:
            # Garante que is_submitting SEMPRE volta pra False — mesmo em crash/CancelledError/OOM
            try:
                async with self:
                    if self.is_submitting:
                        self.is_submitting = False
                        self.submit_status = ""
            except Exception:
                pass

    # ── Helpers ───────────────────────────────────────────────

    def _build_atividades_list(self) -> List[Dict[str, Any]]:
        """Build deduplicated atividades list. Cronograma entry takes priority over manual items with same name."""
        seen: set = set()
        result: List[Dict[str, Any]] = []

        def _add(item: Dict[str, Any]) -> None:
            nome = (item.get("atividade") or "").strip()
            if not nome:
                return
            key = nome.lower()
            if key in seen:
                return
            seen.add(key)
            result.append(item)

        # 1. Primary cronograma activity (highest priority)
        if self.rdo_atividade_id and self.rdo_atividade_nome:
            _primary: Dict[str, Any] = {
                "atividade": self.rdo_atividade_nome,
                "progresso_percentual": str(self.rdo_progresso_atividade),
                "status": "Em andamento",
            }
            try:
                _ef = int(str(self.rdo_efetivo_primaria or "").strip() or "0")
                if _ef > 0:
                    _primary["efetivo"] = _ef
            except Exception:
                pass
            _add(_primary)

        # 2. Extra cronograma activities with efetivo
        for r in self.rdo_extra_atividades:
            if r.get("id", "") and r.get("nome", ""):
                _add({
                    "atividade": r.get("nome", ""),
                    "progresso_percentual": str(r.get("progresso", "0")),
                    "status": "Em andamento",
                    "efetivo": int(r.get("efetivo_alocado", "") or 0),
                })

        # 3. Manual atividades_items
        for item in self.atividades_items:
            _add(dict(item))

        # 4. New manual activities
        for r in self.rdo_novas_atividades:
            if r.get("nome", "").strip():
                _add({
                    "atividade": r.get("nome", "").strip(),
                    "progresso_percentual": str(r.get("progresso", "0")),
                    "status": "Em andamento",
                })

        return result

    def _build_rdo_data(self) -> Dict[str, Any]:
        return {
            "id_rdo":               str(self.draft_id_rdo),
            "data":                 str(self.rdo_data),
            "contrato":             str(self.rdo_contrato),
            "projeto":              str(self.rdo_projeto),
            "cliente":              str(self.rdo_cliente),
            "localizacao":          str(self.rdo_localizacao),
            "condicao_climatica":   str(self.rdo_clima),
            "turno":                str(self.rdo_turno),
            "houve_interrupcao":    bool(self.rdo_houve_interrupcao),
            "motivo_interrupcao":   str(self.rdo_motivo_interrupcao),
            "equipe_alocada":       int(self.rdo_equipe_alocada) if self.rdo_equipe_alocada else None,
            "tipo_tarefa":          str(self.rdo_tipo_tarefa),
            "orientacao":           str(self.rdo_orientacao),
            "km_percorrido":        float(self.rdo_km_percorrido) if self.rdo_km_percorrido else (
                round(_haversine_km(self.checkin_lat, self.checkin_lng, self.checkout_lat, self.checkout_lng), 2)
                if (self.checkin_lat and self.checkout_lat and self.checkin_lng and self.checkout_lng) else 0.0
            ),
            "observacoes":          str(self.rdo_observacoes),
            # Campos condicionais
            "houve_chuva":          bool(self.rdo_houve_chuva),
            "quantidade_chuva":     str(self.rdo_quantidade_chuva) if self.rdo_houve_chuva else None,
            "houve_acidente":       bool(self.rdo_houve_acidente),
            "descricao_acidente":   str(self.rdo_descricao_acidente) if self.rdo_houve_acidente else None,
            # GPS
            "checkin_lat":          float(self.checkin_lat),
            "checkin_lng":          float(self.checkin_lng),
            "checkin_endereco":     str(self.checkin_endereco),
            "checkin_timestamp":    str(self.checkin_timestamp) if self.checkin_timestamp else None,
            "checkout_lat":         float(self.checkout_lat),
            "checkout_lng":         float(self.checkout_lng),
            "checkout_endereco":    str(self.checkout_endereco),
            "checkout_timestamp":   str(self.checkout_timestamp) if self.checkout_timestamp else None,
            # Signatory
            "signatory_name":       str(self.signatory_name),
            "signatory_doc":        str(self.signatory_doc),
            "signatory_sig_b64":    str(self.signatory_sig_b64),
            # Photos
            "epi_foto_url":         self.epi_foto_items[0].get("foto_url", "") if self.epi_foto_items else "",
            "ferramentas_foto_url": self.ferramentas_foto_items[0].get("foto_url", "") if self.ferramentas_foto_items else "",
            # Lists — include selected cronograma activity + extra activities if set
            # Dedup by name: cronograma entry takes priority; manual items with same name are skipped
            "atividades":   self._build_atividades_list(),
            "evidencias":   list(self.evidencias_items),
            # Tenant isolation
            "client_id":    self._rdo_client_id or None,
        }

    def _reset_form(self):
        self.draft_id_rdo          = ""
        self.draft_saved_at        = ""
        self.draft_resumed         = False
        self.rdo_data              = datetime.now().strftime("%Y-%m-%d")
        self.rdo_contrato          = ""
        self.rdo_projeto           = ""
        self.rdo_cliente           = ""
        self.rdo_localizacao       = ""
        self.rdo_tipo_tarefa       = "Diário de Obra"
        self.rdo_orientacao        = ""
        self.rdo_km_percorrido     = ""
        self.rdo_clima             = "Ensolarado"
        self.rdo_turno             = "Diurno"
        self.rdo_houve_interrupcao = False
        self.rdo_motivo_interrupcao= ""
        self.rdo_equipe_alocada    = ""
        self.rdo_observacoes       = ""
        self.rdo_houve_chuva       = False
        self.rdo_quantidade_chuva  = "Leve"
        self.rdo_houve_acidente    = False
        self.rdo_descricao_acidente = ""
        self.checkin_lat           = 0.0
        self.checkin_lng           = 0.0
        self.checkin_endereco      = ""
        self.checkin_timestamp     = ""
        self.checkout_lat          = 0.0
        self.checkout_lng          = 0.0
        self.checkout_endereco     = ""
        self.checkout_timestamp    = ""
        self.atividades_items      = []
        self.at_desc = ""
        self.at_pct = "100"
        self.at_status = "Em andamento"
        self.evidencias_items      = []
        self.ev_legenda            = ""
        self.is_uploading_evidence = False
        self.epi_foto_items        = []
        self.is_uploading_epi      = False
        self.ferramentas_foto_items = []
        self.is_uploading_ferramentas = False
        # Cronograma integration
        self.rdo_fase_macro_sel = ""
        self.rdo_atividade_id = ""
        self.rdo_atividade_nome = ""
        self.rdo_progresso_atividade = "0"
        self.rdo_producao_dia = ""
        self.rdo_ativ_total_qty = "0"
        self.rdo_ativ_exec_qty = "0"
        self.rdo_ativ_unidade = ""
        self.rdo_nova_atividade = False
        self.rdo_nova_atividade_nome = ""
        self.rdo_nova_atividade_fase = ""
        self.rdo_extra_atividades = []
        self.rdo_novas_atividades = []
        self.hub_atividades_options = []
        self.signatory_name        = ""
        self.signatory_doc         = ""
        self.signatory_sig_b64     = ""
        self.checkin_distancia_obra = 0.0
        self.show_confirm_dialog   = False
        self.submit_error          = ""
        self.submit_status         = ""
        self.pending_draft_id      = ""
        self.has_draft_to_resume   = False
