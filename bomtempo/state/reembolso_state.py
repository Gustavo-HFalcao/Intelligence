"""
Reembolso State — Formulário + Análise IA + Submit
Padrão idêntico ao rdo_state.py (benchmark)
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

_BRT = timezone(timedelta(hours=-3))


def _fmt_date_br(ts: str) -> str:
    """ISO date or timestamp → DD/MM/YYYY. Handles UTC→BRT for full timestamps."""
    if not ts or ts in ("—", "None", ""):
        return "—"
    try:
        if "T" in ts or len(ts) > 10:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")[:32])
            return dt.astimezone(_BRT).strftime("%d/%m/%Y")
        parts = ts[:10].split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except Exception:
        pass
    return ts[:10]

import reflex as rx

from bomtempo.core.fuel_service import FuelService
from bomtempo.core.logging_utils import get_logger
from bomtempo.core.audit_logger import audit_log, audit_error, AuditCategory
from bomtempo.core.executors import (
    get_ai_executor,
    get_db_executor,
    get_http_executor,
    get_heavy_executor,
)

logger = get_logger(__name__)


class ReembolsoState(rx.State):
    """Estado do módulo de Reembolso de Combustível."""

    # ── Campos do formulário ───────────────────────────────────────────────────
    combustivel: str = "Gasolina"
    litros: str = ""
    valor_litro: str = ""
    valor_total: str = ""
    data_abastecimento: str = datetime.now().strftime("%Y-%m-%d")
    cidade: str = ""
    estado: str = ""
    km_inicial: str = ""
    km_final: str = ""
    rota: str = ""
    finalidade: str = ""

    # ── GPS Check-in ──────────────────────────────────────────────────────────
    checkin_lat: float = 0.0
    checkin_lng: float = 0.0
    checkin_endereco: str = ""
    checkin_timestamp: str = ""
    checkin_distancia_posto: float = 0.0  # distância (metros) entre GPS e cidade declarada
    is_getting_checkin: bool = False

    # ── Upload de imagem ───────────────────────────────────────────────────────
    # image_b64 é var PRIVADA (prefixo _) — não sincroniza via WebSocket.
    # Fotos de celular têm 8–12MB; colocar no state público causava crash de WS.
    _image_b64: str = ""  # base64 puro (sem prefixo data:) — só lido em handlers Python
    image_mime: str = "image/jpeg"
    image_filename: str = ""
    image_data_url: str = ""  # data:image/...;base64,... para preview (thumbnail 800px)
    image_hash: str = ""      # MD5 da imagem para detecção de duplicidade
    duplicate_warning: str = "" # ID do reembolso duplicado encontrado (vazio = sem duplicata)

    # ── Assinatura Digital ─────────────────────────────────────────────────────
    signature_b64: str = ""   # JPEG base64 capturado do canvas

    # ── IA ─────────────────────────────────────────────────────────────────────
    is_analyzing: bool = False
    analysis_done: bool = False
    ai_extracted: Dict[str, Any] = {}
    validation_errors: List[str] = []
    validation_warnings: List[str] = []
    ai_verified: bool = False
    ai_confidence: float = 0.0
    ai_insight_text: str = ""
    ai_score: int = 0          # Score de confiabilidade 0-100
    # IA retry — máximo 3 tentativas antes de liberar envio manual
    ai_attempt_count: int = 0  # quantas análises foram feitas
    ai_override: bool = False  # usuário decidiu enviar mesmo com divergência

    # ── Upload NF ──────────────────────────────────────────────────────────────
    is_uploading_nf: bool = False

    # ── Submit ─────────────────────────────────────────────────────────────────
    is_submitting: bool = False
    submit_success: bool = False

    # ── Email management (admin) ────────────────────────────────────────────────
    email_list: List[Dict[str, Any]] = []
    email_new_contract: str = ""
    email_new_address: str = ""
    email_is_loading: bool = False

    # ── Feature Flags (carregados no on_load) ─────────────────────────────────
    form_active_features: List[str] = []  # Features do contrato do usuário logado

    # ── Dashboard (lista para admin) ───────────────────────────────────────────
    reembolsos_list: List[Dict[str, Any]] = []
    dash_total_gasto: float = 0.0
    dash_media_kml: float = 0.0
    dash_media_custo_km: float = 0.0
    dash_total_registros: int = 0
    dash_is_loading: bool = True
    # Dados para gráficos
    dash_chart_mensal: List[Dict[str, Any]] = []  # [{mes, total}, ...]
    dash_chart_combustivel: List[Dict[str, Any]] = []  # [{name, value}, ...]
    dash_alertas: List[Dict[str, Any]] = []  # registros com desvio > 30%
    dash_filtro_projeto: str = "Todos os Motivos"
    dash_filtro_contrato: str = "Todos os Contratos"
    # Features do contrato filtrado no dashboard
    dash_active_features: List[str] = []

    # ── Dashboard: Score stats ─────────────────────────────────────────────────
    dash_chart_score: List[Dict[str, Any]] = []  # [{label, count}, ...]
    dash_chart_gps: List[Dict[str, Any]] = []    # [{name, value}, ...] GPS match stats

    def set_dash_filtro_projeto(self, val: str):
        self.dash_filtro_projeto = val

    def set_dash_filtro_contrato(self, val: str):
        self.dash_filtro_contrato = val
        return ReembolsoState.load_dash_features

    # ── Computed ──────────────────────────────────────────────────────────────

    @rx.var
    def checkin_done(self) -> bool:
        return self.checkin_lat != 0.0 or bool(self.checkin_endereco)

    @rx.var
    def checkin_distancia_str(self) -> str:
        d = self.checkin_distancia_posto
        if d <= 0:
            return ""
        if d < 1000:
            return f"{d:.0f}m da cidade"
        return f"{d / 1000:.1f}km da cidade"

    @rx.var
    def checkin_distancia_color(self) -> str:
        d = self.checkin_distancia_posto
        if d <= 0:
            return "#6B9090"
        if d <= 5000:
            return "#2A9D8F"
        if d <= 20000:
            return "#C98B2A"
        return "#E05252"

    @rx.var
    def ai_score_color(self) -> str:
        s = self.ai_score
        if s >= 80:
            return "#2A9D8F"  # verde
        if s >= 50:
            return "#C98B2A"  # âmbar
        return "#E05252"       # vermelho

    @rx.var
    def ai_score_label(self) -> str:
        s = self.ai_score
        if s >= 80:
            return "Alto"
        if s >= 50:
            return "Médio"
        if s > 0:
            return "Baixo"
        return ""

    @rx.var
    def litros_float(self) -> float:
        try:
            return float(str(self.litros).replace(",", ".").strip())
        except Exception:
            return 0.0

    # ── Feature helpers ───────────────────────────────────────────────────────

    @rx.var
    def feat_gps(self) -> bool:
        return "gps_validation" in self.form_active_features

    @rx.var
    def feat_duplicate(self) -> bool:
        return "duplicate_detection" in self.form_active_features

    @rx.var
    def feat_score(self) -> bool:
        return "ai_score" in self.form_active_features

    @rx.var
    def feat_signature(self) -> bool:
        return "digital_signature" in self.form_active_features

    # ── Page init ─────────────────────────────────────────────────────────────

    async def load_form_features(self):
        """Carrega feature flags direto do banco (sempre fresco)."""
        try:
            from bomtempo.state.global_state import GlobalState
            from bomtempo.core.feature_flags import FeatureFlagsService
            gs = await self.get_state(GlobalState)
            contrato = str(gs.current_user_contrato or "").strip()
            if contrato and contrato not in ("nan", "None", ""):
                self.form_active_features = FeatureFlagsService.get_features_for_contract(contrato)
            else:
                self.form_active_features = list(gs.active_features or [])
        except Exception as e:
            logger.warning(f"load_form_features: {e}")
            self.form_active_features = []

    async def load_dash_features(self):
        """Carrega feature flags do contrato selecionado no dashboard."""
        contract_filter = str(self.dash_filtro_contrato)
        if contract_filter in ("Todos os Contratos", "", "nan"):
            self.dash_active_features = []
            return
        loop = asyncio.get_running_loop()
        try:
            from bomtempo.core.feature_flags import FeatureFlagsService
            features = await loop.run_in_executor(
                get_db_executor(),
                lambda: FeatureFlagsService.get_features_for_contract(contract_filter),
            )
            self.dash_active_features = features
        except Exception as e:
            logger.warning(f"load_dash_features: {e}")
            self.dash_active_features = []

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _sanitize_money(self, val: str) -> str:
        if not val:
            return ""
        v = val.replace("R$", "").replace(" ", "").strip()
        if "," in v or "." in v:
            v = v.replace(",", ".")
            try:
                return f"{float(v):.2f}"
            except Exception:
                return v
        if v.isdigit() or (v.startswith("-") and v[1:].isdigit()):
            try:
                return f"{(float(v) / 100):.2f}"
            except Exception:
                return v
        return v

    def _sanitize_decimal(self, val: str) -> str:
        if not val:
            return ""
        v = val.strip()
        if "," in v or "." in v:
            v = v.replace(",", ".")
            try:
                return str(float(v))
            except Exception:
                return v
        return v

    def set_combustivel(self, v: str):
        self.combustivel = v

    def set_finalidade(self, v: str):
        self.finalidade = v

    def set_data_abastecimento(self, v: str):
        self.data_abastecimento = v

    def set_litros_and_calc(self, v: str):
        self.litros = self._sanitize_decimal(v)
        self.auto_calc_total()

    def set_valor_litro_and_calc(self, v: str):
        self.valor_litro = self._sanitize_money(v)
        self.auto_calc_total()

    def set_valor_total(self, v: str):
        self.valor_total = self._sanitize_money(v)

    def set_cidade(self, v: str):
        self.cidade = v

    def set_estado(self, v: str):
        self.estado = v

    def set_km_inicial(self, v: str):
        self.km_inicial = self._sanitize_decimal(v)

    def set_km_final(self, v: str):
        self.km_final = self._sanitize_decimal(v)

    def set_rota(self, v: str):
        self.rota = v

    def set_ai_override(self):
        """Marca que o usuário decidiu enviar mesmo com divergência da IA."""
        self.ai_override = True

    def submit_with_override(self):
        """Define ai_override e dispara submit (chamado pelo botão de override)."""
        self.ai_override = True
        return ReembolsoState.submit_reembolso

    def set_email_new_contract(self, v: str):
        self.email_new_contract = v

    def set_email_new_address(self, v: str):
        self.email_new_address = v

    def auto_calc_total(self):
        """Calcula valor total automaticamente quando litros/valor_litro mudam."""
        try:
            l_val = self.litros if self.litros else "0"
            vl_val = self.valor_litro if self.valor_litro else "0"
            litros_f = float(l_val.replace(",", "."))
            vlitro_f = float(vl_val.replace(",", "."))
            if litros_f > 0 and vlitro_f > 0:
                self.valor_total = f"{litros_f * vlitro_f:.2f}"
        except (ValueError, TypeError):
            pass

    def _build_data(self) -> Dict[str, Any]:
        """Compila dados do formulário + resultados IA + novos campos."""
        base_data = {
            "combustivel": str(self.combustivel),
            "litros": str(self.litros),
            "valor_litro": str(self.valor_litro),
            "valor_total": str(self.valor_total),
            "data_abastecimento": str(self.data_abastecimento),
            "cidade": str(self.cidade),
            "estado": str(self.estado),
            "km_inicial": str(self.km_inicial),
            "km_final": str(self.km_final),
            "rota": str(self.rota),
            "finalidade": str(self.finalidade),
            "ai_verified": bool(self.ai_verified),
            "ai_confidence_score": float(self.ai_confidence),
            "ai_extracted_value": float(self.ai_extracted.get("total", 0) or 0),
            "ai_insight_text": str(self.ai_insight_text),
            # Novos campos
            "ai_score":            int(self.ai_score),
            "image_hash":          str(self.image_hash),
            "signature_b64":       str(self.signature_b64),
            # GPS
            "checkin_lat":             float(self.checkin_lat) if self.checkin_lat else None,
            "checkin_lng":             float(self.checkin_lng) if self.checkin_lng else None,
            "checkin_endereco":        str(self.checkin_endereco),
            "checkin_timestamp":       str(self.checkin_timestamp) if self.checkin_timestamp else None,
            "checkin_distancia_posto": float(self.checkin_distancia_posto) if self.checkin_distancia_posto else None,
        }

        from bomtempo.core.fuel_service import FuelService

        metrics = FuelService.calculate_metrics(base_data)
        base_data.update(metrics)
        return base_data

    def reset_form(self):
        """Limpa o formulário após envio."""
        self.combustivel = "Gasolina"
        self.litros = ""
        self.valor_litro = ""
        self.valor_total = ""
        self.data_abastecimento = datetime.now().strftime("%Y-%m-%d")
        self.cidade = ""
        self.estado = ""
        self.km_inicial = ""
        self.km_final = ""
        self.rota = ""
        self.finalidade = ""
        # _image_b64 é var privada — limpa via evento síncrono separado (_clear_image_b64)
        # pois object.__setattr__ falha em StateProxy (chamado de async with self:)
        self.image_mime = "image/jpeg"
        self.image_filename = ""
        self.image_data_url = ""
        self.image_hash = ""
        self.duplicate_warning = ""
        self.signature_b64 = ""
        self.checkin_lat = 0.0
        self.checkin_lng = 0.0
        self.checkin_endereco = ""
        self.checkin_timestamp = ""
        self.checkin_distancia_posto = 0.0
        self.is_analyzing = False
        self.analysis_done = False
        self.ai_extracted = {}
        self.validation_errors = []
        self.validation_warnings = []
        self.ai_verified = False
        self.ai_confidence = 0.0
        self.ai_insight_text = ""
        self.ai_score = 0
        self.ai_attempt_count = 0
        self.ai_override = False
        self.submit_success = False

    def _clear_image_b64(self):
        """Limpa a var privada _image_b64 (não pode rodar dentro de async with self:)."""
        object.__setattr__(self, "_image_b64", "")

    # ── GPS Check-in ──────────────────────────────────────────────────────────

    def do_checkin(self):
        """Dispara JS para capturar GPS de check-in no reembolso."""
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
            callback=ReembolsoState.receive_checkin_gps,
        )

    @rx.event(background=True)
    async def receive_checkin_gps(self, result: dict):
        """Recebe GPS e faz reverse geocode + calcula distância à cidade declarada."""
        from bomtempo.core.rdo_service import _reverse_geocode
        import math

        lat = float(result.get("lat") or 0.0)
        lng = float(result.get("lng") or 0.0)
        ok  = bool(result.get("ok"))
        endereco = ""
        distancia = 0.0

        async with self:
            cidade_declarada = str(self.cidade)
            estado_declarado = str(self.estado)

        if ok and lat:
            loop = asyncio.get_running_loop()
            endereco = await loop.run_in_executor(get_http_executor(), lambda: _reverse_geocode(lat, lng))

            # Geocode cidade declarada para calcular distância
            if cidade_declarada:
                try:
                    from bomtempo.core import weather_api
                    coords = await weather_api.get_coordinates(f"{cidade_declarada}, {estado_declarado}")
                    if coords:
                        cidade_lat = float(coords["lat"])
                        cidade_lon = float(coords["lon"])
                        # Haversine
                        R = 6_371_000.0
                        phi1, phi2 = math.radians(lat), math.radians(cidade_lat)
                        dphi = math.radians(cidade_lat - lat)
                        dlam = math.radians(cidade_lon - lng)
                        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
                        distancia = 2 * R * math.asin(math.sqrt(a))
                except Exception as e:
                    logger.warning(f"GPS distância cidade: {e}")

        async with self:
            self.checkin_lat             = lat
            self.checkin_lng             = lng
            self.checkin_endereco        = endereco
            self.checkin_timestamp       = datetime.now().isoformat()
            self.checkin_distancia_posto = distancia
            self.is_getting_checkin      = False
            self._recalculate_score()

        if ok and lat:
            dist_str = f" · {distancia/1000:.1f}km da cidade" if distancia > 5000 else (f" · {distancia:.0f}m da cidade" if distancia > 0 else "")
            yield rx.toast(f"📍 Check-in registrado: {endereco or f'{lat:.4f}, {lng:.4f}'}{dist_str}", position="top-center")
        else:
            yield rx.toast("⚠️ Não foi possível obter localização", position="top-center")

    def clear_checkin(self):
        self.checkin_lat = 0.0
        self.checkin_lng = 0.0
        self.checkin_endereco = ""
        self.checkin_timestamp = ""
        self.checkin_distancia_posto = 0.0
        self._recalculate_score()

    # ── Assinatura Digital ─────────────────────────────────────────────────────

    def receive_signature(self, data):
        """Callback do rx.call_script — recebe canvas toDataURL."""
        if isinstance(data, dict):
            self.signature_b64 = data.get("sig", "")
        elif isinstance(data, str) and data.startswith("data:"):
            self.signature_b64 = data

    def capture_signature(self):
        """Captura assinatura do canvas como JPEG 70%."""
        return rx.call_script(
            """(function(){
              var c=document.getElementById('fr-sig-canvas');
              if(!c) return {sig:''};
              var tmp=document.createElement('canvas');
              tmp.width=c.width; tmp.height=c.height;
              var ctx=tmp.getContext('2d');
              ctx.fillStyle='#ffffff';
              ctx.fillRect(0,0,tmp.width,tmp.height);
              ctx.drawImage(c,0,0);
              return {sig: tmp.toDataURL('image/jpeg', 0.70)};
            })()""",
            callback=ReembolsoState.receive_signature,
        )

    def clear_signature(self):
        self.signature_b64 = ""
        return rx.call_script(
            """(function(){
              var c=document.getElementById('fr-sig-canvas');
              if(c){var ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);}
            })()"""
        )

    # ── Score de Confiabilidade ────────────────────────────────────────────────

    def _recalculate_score(self):
        """
        Score 0-100 baseado em:
        - GPS presente e distância < 5km da cidade: +30
        - NF verificada pela IA (ai_verified): +40
        - Sem desvio excessivo (histórico normal): +30
        Chamado sempre que GPS ou análise IA mudam.
        """
        score = 0
        # GPS: presente e próximo à cidade declarada
        if self.checkin_lat != 0.0:
            if self.checkin_distancia_posto < 5000 or self.checkin_distancia_posto == 0.0:
                score += 30
            else:
                score += 10  # GPS presente mas distante
        # IA: NF verificada
        if self.ai_verified:
            score += 40
        elif self.analysis_done:
            score += 10  # análise feita mas não verificada
        # Histórico: sem override forçado
        if not self.ai_override:
            score += 30
        self.ai_score = min(score, 100)

    # ── Upload de imagem ───────────────────────────────────────────────────────

    async def handle_nf_upload(self, files: list[rx.UploadFile]):
        """Recebe imagem da NF via rx.upload."""
        if not files:
            return
        # Mostra loading imediatamente antes de processar
        self.is_uploading_nf = True
        yield  # flush para o cliente mostrar o spinner

        import base64
        import hashlib
        import io as _io

        file = files[0]
        data = await file.read()

        ext = file.filename.split(".")[-1].lower() if "." in file.filename else "jpeg"
        mime_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "heic": "image/heic",
            "webp": "image/webp",
        }
        mime = mime_map.get(ext, "image/jpeg")

        img_hash = hashlib.md5(data).hexdigest()

        # Guarda bytes originais como var privada (não sincroniza WebSocket)
        b64_full = base64.b64encode(data).decode("utf-8")
        object.__setattr__(self, "_image_b64", b64_full)

        # Gera thumbnail comprimido para preview (max 800px, JPEG q=72)
        # Fotos de celular chegam com 8–12MB; enviar base64 completo via WebSocket
        # causa crash de conexão. O thumbnail é suficiente para o usuário conferir.
        try:
            from PIL import Image as _PILImg, ImageOps as _PILOps
            _pil = _PILImg.open(_io.BytesIO(data))
            _pil = _PILOps.exif_transpose(_pil)
            _pil.thumbnail((800, 800), _PILImg.LANCZOS)
            _buf = _io.BytesIO()
            _pil.convert("RGB").save(_buf, format="JPEG", quality=72, optimize=True)
            preview_b64 = base64.b64encode(_buf.getvalue()).decode("utf-8")
            preview_mime = "image/jpeg"
        except Exception:
            # fallback: usar original (pode ser lento mas não quebra)
            preview_b64 = b64_full
            preview_mime = mime

        self.image_mime = mime
        self.image_filename = file.filename
        self.image_data_url = f"data:{preview_mime};base64,{preview_b64}"
        self.image_hash = img_hash
        self.duplicate_warning = ""
        # Limpa análise anterior
        self.analysis_done = False
        self.ai_extracted = {}
        self.validation_errors = []
        self.validation_warnings = []
        self.ai_verified = False
        self.is_uploading_nf = False

        # Verificação de duplicidade (se feature ativa)
        if "duplicate_detection" in self.form_active_features:
            try:
                import asyncio as _aio
                _loop = _aio.get_running_loop()
                _hash = img_hash
                dup_id = await _loop.run_in_executor(get_db_executor(), lambda: FuelService.check_duplicate_hash(_hash))
                if dup_id:
                    self.duplicate_warning = dup_id
                    yield rx.toast(
                        f"⚠️ Imagem já utilizada em reembolso anterior (ID: {dup_id[:8]}…). Verifique antes de enviar.",
                        position="top-center",
                        duration=6000,
                    )
                    return
            except Exception as e:
                logger.warning(f"check_duplicate_hash: {e}")

        yield rx.toast("📎 Imagem carregada! Clique em 'Analisar com IA'.", position="top-center")

    # ── Análise IA ─────────────────────────────────────────────────────────────

    @rx.event(background=True)
    async def analyze_receipt(self):
        """
        Background event: envia imagem para Vision API e valida resultado.
        Fases separadas com async with self para flush imediato.
        """
        import asyncio

        loop = asyncio.get_running_loop()

        # FASE 1: mostrar loading
        async with self:
            self.is_analyzing = True
            self.analysis_done = False
            self.validation_errors = []
            self.validation_warnings = []
            self.ai_override = False  # reset override a cada nova tentativa

        try:
            # FASE 2: chamar Vision API em executor (não bloqueia event loop)
            ai_result = {}
            try:
                b64 = ""
                mime = "image/jpeg"
                async with self:
                    b64 = str(self._image_b64)
                    mime = str(self.image_mime)

                if not b64:
                    async with self:
                        yield rx.toast("⚠️ Nenhuma imagem carregada.", position="top-center")
                    return

                ai_result = await loop.run_in_executor(
                    get_ai_executor(), lambda: FuelService.analyze_receipt_image(b64, mime)
                )
                logger.info(f"✅ Vision API result: {ai_result}")
            except Exception as e:
                logger.error(f"❌ analyze_receipt error: {e}")

            # FASE 3: validar e preencher campos
            try:
                async with self:
                    self.ai_extracted = ai_result or {}
                    self.ai_confidence = float(ai_result.get("confidence", 0) or 0)

                    # Montar insight text para o PDF
                    if ai_result:
                        parts = []
                        if ai_result.get("fuel_type"):
                            parts.append(f"Combustível: {ai_result['fuel_type']}")
                        if ai_result.get("liters"):
                            parts.append(f"Litros: {ai_result['liters']:.3f}L")
                        if ai_result.get("price_per_liter"):
                            parts.append(f"Preço/L: R${ai_result['price_per_liter']:.3f}")
                        if ai_result.get("total"):
                            parts.append(f"Total NF: R${ai_result['total']:.2f}")
                        if ai_result.get("station"):
                            parts.append(f"Posto: {ai_result['station']}")
                        if ai_result.get("date"):
                            parts.append(f"Data NF: {ai_result['date']}")
                        conf = self.ai_confidence
                        parts.append(f"Confiança IA: {conf:.0%}")
                        self.ai_insight_text = " | ".join(parts)

                        # Pré-preencher campos se vazios
                        if not self.litros and ai_result.get("liters"):
                            self.litros = f"{ai_result['liters']:.3f}"
                        if not self.valor_litro and ai_result.get("price_per_liter"):
                            self.valor_litro = f"{ai_result['price_per_liter']:.3f}"
                        if not self.valor_total and ai_result.get("total"):
                            self.valor_total = f"{ai_result['total']:.2f}"
                        if not self.combustivel and ai_result.get("fuel_type"):
                            self.combustivel = ai_result["fuel_type"]
                        if not self.data_abastecimento and ai_result.get("date"):
                            self.data_abastecimento = ai_result["date"]

                    # Validar
                    user_data = self._build_data()
                    validation = FuelService.validate_data(user_data, ai_result)
                    self.validation_errors = validation["errors"]
                    self.validation_warnings = validation["warnings"]
                    self.ai_verified = validation["ai_verified"]
                    self.ai_attempt_count += 1
                    self.analysis_done = True
                    self._recalculate_score()

                    if validation["valid"] and ai_result:
                        yield rx.toast("✅ Nota fiscal verificada pela IA!", position="top-center")
                    elif not validation["valid"]:
                        yield rx.toast(
                            "⚠️ Divergência encontrada — verifique os campos.", position="top-center"
                        )
                    else:
                        yield rx.toast("ℹ️ Análise concluída. Verifique os avisos.", position="top-center")
            except Exception as e:
                logger.error(f"❌ analyze_receipt fase3 error: {e}", exc_info=True)
                async with self:
                    self.analysis_done = True
                    yield rx.toast("❌ Erro na análise. Tente novamente.", position="top-center")

        finally:
            # Garante que is_analyzing SEMPRE volta para False — mesmo em CancelledError/crash
            async with self:
                self.is_analyzing = False

    # ── Submit (com validação guiada) ──────────────────────────────────────────

    async def try_submit(self):
        """Valida pré-condições e guia o usuário, depois dispara submit."""
        if not self.image_data_url:
            yield rx.toast(
                "📎 Anexe a foto da nota fiscal antes de enviar.",
                position="top-center",
                duration=5000,
            )
            return
        if not self.analysis_done:
            yield rx.toast(
                "🤖 Clique em 'Extrair Dados com IA' para validar a nota antes de enviar.",
                position="top-center",
                duration=5000,
            )
            return
        if not (self.ai_verified or self.ai_override):
            yield rx.toast(
                "⚠️ Há divergências na nota. Corrija os dados ou aprove o envio com divergência (após 3 tentativas).",
                position="top-center",
                duration=6000,
            )
            return
        yield ReembolsoState.submit_reembolso

    @rx.event(background=True)
    async def submit_reembolso(self):
        """
        Background event: salva reembolso no Supabase, gera PDF, faz upload.
        Estrutura de fases idêntica ao submit_rdo (benchmark).
        try/finally garante que is_submitting sempre é limpo.
        """
        import asyncio
        import threading

        loop = asyncio.get_running_loop()

        # FASE 1: mostrar loading
        async with self:
            self.is_submitting = True

        try:
            # FASE 2: coletar dados + usuário
            data = {}
            current_user = ""
            image_b64 = ""
            image_mime = "image/jpeg"
            ai_override_flag = False
            from bomtempo.state.global_state import GlobalState
            async with self:
                gs = await self.get_state(GlobalState)
                current_user = str(gs.current_user_name)
                current_client_id = str(gs.current_client_id or "")
                data = self._build_data()
                data["submitted_by"] = current_user
                image_b64 = str(self._image_b64)
                image_mime = str(self.image_mime)
                ai_override_flag = bool(self.ai_override)

            # Adiciona nota de override no insight text
            if ai_override_flag:
                existing = data.get("ai_insight_text", "") or ""
                note = "NOTA: Usuário enviou com divergência IA (override manual)."
                data["ai_insight_text"] = f"{existing} | {note}".strip(" | ")

            # Validação básica
            if not data.get("valor_total") or not data.get("combustivel"):
                async with self:
                    yield rx.toast(
                        "⚠️ Preencha ao menos Combustível e Valor Total.", position="top-center"
                    )
                return

            # FASE 3: salvar no banco
            id_fr: str = ""
            try:
                id_fr = await loop.run_in_executor(
                    get_db_executor(), lambda: FuelService.save_to_database(data, submitted_by=current_user, client_id=current_client_id)
                )
                logger.info(f"✅ FR save_to_database: {id_fr}")
            except Exception as e:
                logger.error(f"❌ FR save_to_database: {e}", exc_info=True)

            if not id_fr:
                async with self:
                    yield rx.toast("❌ Erro ao salvar no banco de dados.", position="top-center")
                return

            # FASE 4: upload da imagem (se houver)
            if image_b64:
                try:
                    await loop.run_in_executor(
                        get_db_executor(),
                        lambda: FuelService.upload_image_to_storage(image_b64, id_fr, image_mime),
                    )
                    logger.info(f"✅ FR image uploaded for {id_fr}")
                except Exception as e:
                    logger.warning(f"⚠️ FR image upload: {e}")

            # FASE 5: gerar PDF
            pdf_path: str = ""
            try:
                result = await loop.run_in_executor(
                    get_heavy_executor(), lambda: FuelService.generate_pdf(data, id_fr=id_fr)
                )
                pdf_path = result[0] if result else ""
                logger.info(f"✅ FR generate_pdf: {pdf_path}")
            except Exception as e:
                logger.error(f"⚠️ FR generate_pdf: {e}")

            # FASE 6: upload PDF ao Storage
            if pdf_path:
                try:
                    await loop.run_in_executor(
                        get_heavy_executor(), lambda: FuelService.upload_pdf_to_storage(pdf_path, id_fr)
                    )
                    logger.info(f"✅ FR PDF uploaded for {id_fr}")
                except Exception as e:
                    logger.warning(f"⚠️ FR PDF upload: {e}")

            # FASE 6.5: email de notificação (fire-and-forget)
            final_pdf = str(pdf_path)
            final_data = dict(data)

            _email_client_id = str(current_client_id)

            def _send_email_fr():
                try:
                    from bomtempo.core.email_service import EmailService

                    recipients = FuelService.get_notification_emails(client_id=_email_client_id)
                    if recipients:
                        EmailService.send_reembolso_email(recipients, final_data, final_pdf)
                except Exception as ex:
                    logger.warning(f"⚠️ FR email send: {ex}")

            threading.Thread(target=_send_email_fr, daemon=True).start()

            # FASE 7: sucesso
            audit_log(
                category=AuditCategory.REEMBOLSO_CREATE,
                action=f"Reembolso submetido por '{current_user}' — {data.get('combustivel', '')} R$ {data.get('valor_total', '')}",
                username=current_user,
                entity_type="reembolso",
                entity_id=str(id_fr),
                metadata={
                    "combustivel": data.get("combustivel", ""),
                    "valor_total": data.get("valor_total", ""),
                    "rota": data.get("rota", ""),
                    "ai_override": ai_override_flag,
                },
                status="success",
            )
            async with self:
                self.reset_form()
                self.submit_success = True
                yield rx.toast("✅ Reembolso enviado com sucesso!", position="top-center")
                yield rx.redirect("/reembolso")

        except Exception as e:
            logger.error(f"❌ FR submit_reembolso inesperado: {e}", exc_info=True)
            audit_error(
                action="Falha inesperada ao submeter reembolso",
                username=current_user if "current_user" in dir() else "unknown",
                entity_type="reembolso",
                error=e,
            )
            async with self:
                yield rx.toast("❌ Erro inesperado. Tente novamente.", position="top-center")
        finally:
            async with self:
                self.is_submitting = False
            # Limpa _image_b64 FORA do async with self: (object.__setattr__ falha em StateProxy)
            yield ReembolsoState._clear_image_b64

    # ── Dashboard load ──────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_record(r: dict) -> dict:
        """
        Pré-formata campos para uso em rx.foreach (Vars não suportam slicing Python).
        Adiciona date_short, formata valores numéricos como strings.
        """
        raw_date = str(r.get("created_at") or "")
        total_v = r.get("total_value")
        kml_v = r.get("km_per_liter")
        ckm_v = r.get("cost_per_km")
        dev_v = r.get("deviation_from_fleet_avg")
        ai_score_v = r.get("ai_score")
        return {
            **r,
            "date_short": _fmt_date_br(raw_date),
            "total_value": f"{float(total_v):.2f}" if total_v is not None else "",
            "km_per_liter": f"{float(kml_v):.2f}" if kml_v is not None else "",
            "cost_per_km": f"{float(ckm_v):.4f}" if ckm_v is not None else "",
            "deviation_from_fleet_avg": f"{float(dev_v):.1f}" if dev_v is not None else "",
            "ai_score": str(int(ai_score_v)) if ai_score_v is not None else "—",
            "ai_verified": bool(r.get("ai_verified", False)),
            "pdf_report_url": str(r.get("pdf_report_url") or ""),
            "receipt_image_url": str(r.get("receipt_image_url") or ""),
            "id": str(r.get("id") or ""),
            "fuel_type": str(r.get("fuel_type") or ""),
            "purpose": str(r.get("purpose") or ""),
            "city": str(r.get("city") or ""),
            "centro_custo": str(r.get("centro_custo") or ""),
            "checkin_endereco": str(r.get("checkin_endereco") or ""),
            "has_gps": "true" if r.get("checkin_lat") else "false",
            "has_signature": "true" if r.get("signature_b64") else "false",
        }

    async def load_dashboard(self):
        """Carrega dados do dashboard admin."""
        self.dash_is_loading = True
        yield
        import asyncio

        await asyncio.sleep(1)  # Sincronismo visual forçado / UX
        loop = asyncio.get_running_loop()

        try:
            records = await loop.run_in_executor(get_db_executor(), FuelService.get_all_reimbursements)

            if self.dash_filtro_projeto != "Todos os Motivos":
                records = [
                    r
                    for r in (records or [])
                    if self.dash_filtro_projeto.lower() in str(r.get("purpose", "")).lower()
                ]

            if self.dash_filtro_contrato != "Todos os Contratos":
                records = [
                    r
                    for r in (records or [])
                    if self.dash_filtro_contrato.lower() in str(r.get("city", "")).lower()
                ]  # Adaptado pois Finalidade é City/Rotas/Purpose

            self.reembolsos_list = [self._normalize_record(r) for r in (records or [])]

            # KPIs
            total_gasto = sum(float(r.get("total_value") or 0) for r in records)
            kml_vals = [float(r.get("km_per_liter") or 0) for r in records if r.get("km_per_liter")]
            ckm_vals = [float(r.get("cost_per_km") or 0) for r in records if r.get("cost_per_km")]

            self.dash_total_gasto = round(total_gasto, 2)
            self.dash_media_kml = round(sum(kml_vals) / len(kml_vals), 2) if kml_vals else 0.0
            self.dash_media_custo_km = round(sum(ckm_vals) / len(ckm_vals), 4) if ckm_vals else 0.0
            self.dash_total_registros = len(records)

            # Gráfico mensal: agrupa por mês (YYYY-MM)
            from collections import defaultdict

            mensal: dict = defaultdict(float)
            combustivel_count: dict = defaultdict(float)
            alertas = []
            for r in records or []:
                raw_date = str(r.get("created_at") or "")
                mes = raw_date[:7] if len(raw_date) >= 7 else "?"
                mensal[mes] += float(r.get("total_value") or 0)
                fuel = str(r.get("fuel_type") or "Outro")
                combustivel_count[fuel] += 1
                dev = float(r.get("deviation_from_fleet_avg") or 0)
                if abs(dev) > 30:
                    alertas.append(self._normalize_record(r))

            self.dash_chart_mensal = [
                {"mes": k, "total": round(v, 2)} for k, v in sorted(mensal.items())
            ]
            fuel_colors = {
                "Gasolina": "#FACC15",  # Yellow distinct
                "Gasolina Aditivada": "#EF4444",  # Red
                "Etanol": "#10B981",  # Green
                "Diesel": "#8B5CF6",  # Purple
                "Diesel S10": "#3B82F6",  # Blue
                "GNV": "#F97316",  # Orange
            }
            self.dash_chart_combustivel = [
                {"name": k, "value": int(v), "fill": fuel_colors.get(k, "#94A3B8")}
                for k, v in combustivel_count.items()
            ]
            self.dash_alertas = alertas

            # Score distribution
            score_buckets = {"Alto (80-100)": 0, "Médio (50-79)": 0, "Baixo (0-49)": 0, "N/A": 0}
            gps_count = {"Com GPS": 0, "Sem GPS": 0}
            for r in records or []:
                sc = r.get("ai_score")
                if sc is None:
                    score_buckets["N/A"] += 1
                elif int(sc) >= 80:
                    score_buckets["Alto (80-100)"] += 1
                elif int(sc) >= 50:
                    score_buckets["Médio (50-79)"] += 1
                else:
                    score_buckets["Baixo (0-49)"] += 1
                if r.get("checkin_lat"):
                    gps_count["Com GPS"] += 1
                else:
                    gps_count["Sem GPS"] += 1
            score_colors = {"Alto (80-100)": "#2A9D8F", "Médio (50-79)": "#C98B2A", "Baixo (0-49)": "#E05252", "N/A": "#6B9090"}
            self.dash_chart_score = [
                {"name": k, "value": int(v), "fill": score_colors.get(k, "#94A3B8")}
                for k, v in score_buckets.items() if v > 0
            ]
            self.dash_chart_gps = [
                {"name": k, "value": int(v), "fill": "#2A9D8F" if k == "Com GPS" else "#4A5568"}
                for k, v in gps_count.items() if v > 0
            ]

            # Load features do contrato filtrado
            yield ReembolsoState.load_dash_features

        except Exception as e:
            logger.error(f"❌ FR load_dashboard: {e}")
        finally:
            self.dash_is_loading = False

    async def load_my_reimbursements(self):
        """Carrega reembolsos do usuário logado."""
        import asyncio

        loop = asyncio.get_running_loop()

        try:
            from bomtempo.state.global_state import GlobalState

            gs = await self.get_state(GlobalState)
            username = str(gs.current_user_name)

            records = await loop.run_in_executor(
                get_db_executor(), lambda: FuelService.get_reimbursements_by_user(username)
            )
            self.reembolsos_list = [self._normalize_record(r) for r in (records or [])]
        except Exception as e:
            logger.error(f"❌ FR load_my_reimbursements: {e}")

    # ── Email management ─────────────────────────────────────────────────────

    @staticmethod
    def _normalize_email_record(r: dict) -> dict:
        """Normaliza registro de email para uso em rx.foreach."""
        return {
            "contract": str(r.get("contract") or ""),
            "email": str(r.get("email") or ""),
            "module": str(r.get("module") or "reembolso"),
            "created_by": str(r.get("created_by") or ""),
            "updated_date": str(r.get("updated_date") or ""),
        }

    async def load_emails(self):
        """Carrega lista de emails de notificação (module='reembolso') — filtrado por tenant."""
        self.email_is_loading = True
        yield
        import asyncio

        loop = asyncio.get_running_loop()
        try:
            from bomtempo.state.global_state import GlobalState
            _gs = await self.get_state(GlobalState)
            _cid = str(_gs.current_client_id or "")
        except Exception:
            _cid = ""
        try:
            records = await loop.run_in_executor(get_db_executor(), lambda: FuelService.get_email_records(client_id=_cid))
            self.email_list = [self._normalize_email_record(r) for r in (records or [])]
        except Exception as e:
            logger.error(f"❌ load_emails: {e}")
        finally:
            self.email_is_loading = False

    async def add_email(self):
        """Adiciona email à lista de notificação."""
        import asyncio

        loop = asyncio.get_running_loop()

        contract = str(self.email_new_contract).strip()
        email_addr = str(self.email_new_address).strip()
        if not contract or not email_addr:
            yield rx.toast("⚠️ Preencha contrato e email.", position="top-center")
            return

        try:
            from bomtempo.state.global_state import GlobalState

            gs = await self.get_state(GlobalState)
            created_by = str(gs.current_user_name)
        except Exception:
            created_by = "admin"

        _cid_add = ""
        try:
            _cid_add = str(gs.current_client_id or "")
        except Exception:
            pass
        ok = await loop.run_in_executor(
            get_db_executor(), lambda: FuelService.add_notification_email(contract, email_addr, created_by)
        )
        if ok:
            self.email_new_contract = ""
            self.email_new_address = ""
            records = await loop.run_in_executor(get_db_executor(), lambda: FuelService.get_email_records(client_id=_cid_add))
            self.email_list = [self._normalize_email_record(r) for r in (records or [])]
            yield rx.toast("✅ Email adicionado com sucesso.", position="top-center")
        else:
            yield rx.toast("❌ Erro ao adicionar email.", position="top-center")

    async def delete_email(self, contract: str, email: str):
        """Remove email da lista de notificação."""
        import asyncio

        loop = asyncio.get_running_loop()
        _cid_del = ""
        try:
            from bomtempo.state.global_state import GlobalState
            _gs_del = await self.get_state(GlobalState)
            _cid_del = str(_gs_del.current_client_id or "")
        except Exception:
            pass

        ok = await loop.run_in_executor(
            get_db_executor(), lambda: FuelService.delete_notification_email(contract, email)
        )
        if ok:
            records = await loop.run_in_executor(get_db_executor(), lambda: FuelService.get_email_records(client_id=_cid_del))
            self.email_list = [self._normalize_email_record(r) for r in (records or [])]
            yield rx.toast("✅ Email removido.", position="top-center")
        else:
            yield rx.toast("❌ Erro ao remover email.", position="top-center")
