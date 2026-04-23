"""
Reembolso de Combustível — Formulário Mobile-First
Acesso: role 'solicitacao_reembolso'
"""

import reflex as rx

from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState
from bomtempo.state.reembolso_state import ReembolsoState

# Capacidades de tanque comuns (litros)

# ── Paleta local ────────────────────────────────────────────────────────────


def _card(*children, **kwargs) -> rx.Component:
    padding = kwargs.pop("padding", "20px")
    return rx.box(
        *children,
        bg=S.BG_ELEVATED,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="16px",
        padding=padding,
        **kwargs,
    )


def _label(text: str) -> rx.Component:
    return rx.text(
        text,
        font_size="11px",
        font_weight="700",
        letter_spacing="0.08em",
        color=S.TEXT_MUTED,
        font_family=S.FONT_TECH,
        text_transform="uppercase",
        margin_bottom="6px",
    )


def _input(
    placeholder: str, var, on_change, input_type: str = "text", input_mode: str = None
) -> rx.Component:
    return rx.input(
        placeholder=placeholder,
        value=var,
        on_change=on_change,
        type=input_type,
        input_mode=input_mode if input_mode else ("decimal" if input_type == "text" else "text"),
        bg=S.BG_INPUT,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="10px",
        height="48px",
        font_size="16px",
        color=S.TEXT_PRIMARY,
        padding_x="14px",
        width="100%",
        _focus={"border_color": S.COPPER, "box_shadow": f"0 0 0 2px {S.COPPER_GLOW}"},
        _placeholder={"color": S.TEXT_MUTED},
    )


def _select(options: list, var, on_change) -> rx.Component:
    return rx.select.root(
        rx.select.trigger(
            width="100%",
            height="48px",
            bg=S.BG_INPUT,
            border=f"1px solid {S.BORDER_SUBTLE}",
            border_radius="10px",
            font_size="16px",
            color=S.TEXT_PRIMARY,
            padding_x="14px",
            _focus={"border_color": S.COPPER},
        ),
        rx.select.content(
            *[rx.select.item(opt, value=opt) for opt in options],
            bg=S.BG_ELEVATED,
        ),
        value=var,
        on_change=on_change,
        width="100%",
    )


def _section_title(icon: str, title: str) -> rx.Component:
    return rx.hstack(
        rx.icon(tag=icon, size=16, color=S.COPPER),
        rx.text(
            title,
            font_size="13px",
            font_weight="700",
            font_family=S.FONT_TECH,
            letter_spacing="0.06em",
            color=S.COPPER,
            text_transform="uppercase",
        ),
        align="center",
        spacing="2",
        margin_bottom="14px",
    )


# ── Seção 1: Dados do Abastecimento ─────────────────────────────────────────


def section_abastecimento() -> rx.Component:
    return _card(
        _section_title("fuel", "Dados do Abastecimento"),
        rx.vstack(
            rx.grid(
                rx.box(
                    _label("Combustível"),
                    _select(
                        ["Gasolina", "Gasolina Aditivada", "Etanol", "Diesel", "Diesel S10", "GNV"],
                        ReembolsoState.combustivel,
                        ReembolsoState.set_combustivel,
                    ),
                ),
                rx.box(
                    _label("Data do Abastecimento"),
                    _input(
                        "",
                        ReembolsoState.data_abastecimento,
                        ReembolsoState.set_data_abastecimento,
                        "date",
                    ),
                ),
                columns=rx.breakpoints(initial="1", sm="2"),
                spacing="3",
                width="100%",
            ),
            rx.grid(
                rx.box(
                    _label("Litros"),
                    _input(
                        "0.000", ReembolsoState.litros, ReembolsoState.set_litros_and_calc, "text"
                    ),
                ),
                rx.box(
                    _label("Preço por Litro (R$)"),
                    _input(
                        "0.000",
                        ReembolsoState.valor_litro,
                        ReembolsoState.set_valor_litro_and_calc,
                        "text",
                    ),
                ),
                columns=rx.breakpoints(initial="1", sm="2"),
                spacing="3",
                width="100%",
            ),
            rx.box(
                _label("Valor Total (R$)"),
                _input("0.00", ReembolsoState.valor_total, ReembolsoState.set_valor_total, "text"),
                rx.text(
                    "Calculado automaticamente. Edite se necessário.",
                    font_size="11px",
                    color=S.TEXT_MUTED,
                    margin_top="4px",
                ),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


# ── Seção 2: Localização ─────────────────────────────────────────────────────


def section_localizacao() -> rx.Component:
    estados_br = [
        "AC",
        "AL",
        "AP",
        "AM",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MT",
        "MS",
        "MG",
        "PA",
        "PB",
        "PR",
        "PE",
        "PI",
        "RJ",
        "RN",
        "RS",
        "RO",
        "RR",
        "SC",
        "SP",
        "SE",
        "TO",
    ]
    return _card(
        _section_title("map-pin", "Localização"),
        rx.grid(
            rx.box(
                _label("Estado"),
                _select(
                    estados_br,
                    ReembolsoState.estado,
                    ReembolsoState.set_estado,
                ),
            ),
            rx.box(
                _label("Cidade"),
                _input("Ex: São Paulo", ReembolsoState.cidade, ReembolsoState.set_cidade),
            ),
            columns="2",
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


# ── Seção 2b: GPS Check-in (feature flag: gps_validation) ────────────────────


def section_gps_checkin() -> rx.Component:
    """Captura de localização GPS do usuário no momento do preenchimento."""
    return rx.cond(
        ReembolsoState.feat_gps,
        _card(
            _section_title("map-pin", "Check-in GPS"),
            rx.cond(
                ReembolsoState.checkin_done,
                # GPS já capturado
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="map-pin", size=16, color=S.SUCCESS),
                        rx.text(
                            ReembolsoState.checkin_endereco,
                            font_size="14px",
                            font_weight="600",
                            color=S.TEXT_PRIMARY,
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.cond(
                        ReembolsoState.checkin_distancia_str != "",
                        rx.hstack(
                            rx.icon(tag="navigation", size=13, color=ReembolsoState.checkin_distancia_color),
                            rx.text(
                                ReembolsoState.checkin_distancia_str,
                                font_size="12px",
                                color=ReembolsoState.checkin_distancia_color,
                                font_weight="600",
                            ),
                            spacing="1",
                            align="center",
                        ),
                    ),
                    rx.button(
                        rx.icon(tag="x", size=14),
                        "Limpar",
                        on_click=ReembolsoState.clear_checkin,
                        size="1",
                        variant="ghost",
                        color_scheme="red",
                    ),
                    spacing="2",
                    align="start",
                    width="100%",
                ),
                # GPS ainda não capturado
                rx.vstack(
                    rx.text(
                        "Registre sua localização atual para validar o abastecimento.",
                        font_size="13px",
                        color=S.TEXT_MUTED,
                        line_height="1.5",
                    ),
                    rx.button(
                        rx.cond(
                            ReembolsoState.is_getting_checkin,
                            rx.hstack(rx.spinner(size="2"), rx.text("Obtendo localização..."), spacing="2", align="center"),
                            rx.hstack(rx.icon(tag="map-pin", size=16), rx.text("Registrar Localização GPS"), spacing="2", align="center"),
                        ),
                        on_click=ReembolsoState.do_checkin,
                        disabled=ReembolsoState.is_getting_checkin,
                        bg=S.PATINA,
                        color="white",
                        width="100%",
                        height="48px",
                        border_radius="10px",
                        font_size="15px",
                        font_weight="600",
                        _hover={"bg": S.SUCCESS},
                        cursor="pointer",
                    ),
                    spacing="3",
                    width="100%",
                ),
            ),
            rx.cond(
                ReembolsoState.duplicate_warning != "",
                rx.hstack(
                    rx.icon(tag="alert-triangle", size=14, color="#E05252"),
                    rx.text(
                        f"Nota: imagem já utilizada em outro reembolso.",
                        font_size="12px",
                        color="#E05252",
                        font_weight="600",
                    ),
                    spacing="1",
                    align="center",
                    margin_top="8px",
                ),
            ),
            width="100%",
        ),
        rx.fragment(),
    )


# ── Seção 3: KM e Rota ──────────────────────────────────────────────────────


def section_km() -> rx.Component:
    return _card(
        _section_title("gauge", "Hodômetro e Rota"),
        rx.vstack(
            rx.grid(
                rx.box(
                    _label("KM Inicial"),
                    _input(
                        "Ex: 45000",
                        ReembolsoState.km_inicial,
                        ReembolsoState.set_km_inicial,
                        "text",
                        input_mode="numeric",
                    ),
                ),
                rx.box(
                    _label("KM Final"),
                    _input(
                        "Ex: 45150",
                        ReembolsoState.km_final,
                        ReembolsoState.set_km_final,
                        "text",
                        input_mode="numeric",
                    ),
                ),
                columns=rx.breakpoints(initial="1", sm="2"),
                spacing="3",
                width="100%",
            ),
            rx.box(
                _label("Finalidade"),
                _select(
                    [
                        "Visita a cliente",
                        "Transporte de material",
                        "Deslocamento para obra",
                        "Reunião externa",
                        "Supervisão de campo",
                        "Emergência",
                        "Outro",
                    ],
                    ReembolsoState.finalidade,
                    ReembolsoState.set_finalidade,
                ),
            ),
            rx.box(
                _label("Descrição da Rota"),
                rx.text_area(
                    placeholder="Ex: Saída de São Paulo, chegada em Campinas via Anhanguera...",
                    value=ReembolsoState.rota,
                    on_change=ReembolsoState.set_rota,
                    rows="3",
                    bg=S.BG_INPUT,
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    border_radius="10px",
                    font_size="15px",
                    color=S.TEXT_PRIMARY,
                    padding="14px",
                    width="100%",
                    resize="none",
                    _focus={"border_color": S.COPPER, "box_shadow": f"0 0 0 2px {S.COPPER_GLOW}"},
                    _placeholder={"color": S.TEXT_MUTED},
                ),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


# ── Seção 4: Nota Fiscal ─────────────────────────────────────────────────────


def section_nota_fiscal() -> rx.Component:
    """Upload e Análise IA da Nota Fiscal."""
    return _card(
        _section_title("receipt", "Nota Fiscal"),
        rx.vstack(
            # SmartScan: feedback de qualidade da foto em tempo real
            rx.html("""
<script src="/js/smart_scan.js"></script>
<div id="nf-scan-feedback" style="display:none;font-size:12px;font-weight:600;padding:6px 10px;border-radius:8px;margin-bottom:6px;background:rgba(255,255,255,0.06);transition:all 0.3s ease;"></div>
<script>
(function(){
  var _scanner = null;
  var _video   = null;
  var _canvas  = null;

  function _initSmartScan(){
    var zone = document.getElementById('nf_upload');
    if(!zone) return;
    var inp = zone.querySelector('input[type="file"]');
    if(!inp || inp._smartScanBound) return;
    inp._smartScanBound = true;

    inp.addEventListener('click', function(){
      // Só inicia scanner se o dispositivo tiver câmera traseira (mobile)
      if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
      var feedback = document.getElementById('nf-scan-feedback');

      // Cria elementos de vídeo/canvas ocultos para análise de frame
      if(!_video){
        _video  = document.createElement('video');
        _canvas = document.createElement('canvas');
        _video.style.display  = 'none';
        _canvas.style.display = 'none';
        document.body.appendChild(_video);
        document.body.appendChild(_canvas);
      }

      if(window.SmartScanPreview){
        if(_scanner) _scanner.stopCamera();
        // Substitui IDs por referências diretas
        _scanner = new SmartScanPreview(null, null, null);
        _scanner.video    = _video;
        _scanner.canvas   = _canvas;
        _scanner.ctx      = _canvas.getContext('2d');
        _scanner.feedback = { textContent: '', style: {} };
        _scanner.updateFeedback = function(msg, color){
          if(!feedback) return;
          feedback.textContent = msg;
          feedback.style.color = color;
          feedback.style.display = 'block';
        };
        _scanner.startCamera();
      }
    });

    // Para câmera assim que o arquivo for selecionado
    inp.addEventListener('change', function(){
      if(_scanner){ _scanner.stopCamera(); _scanner = null; }
      var feedback = document.getElementById('nf-scan-feedback');
      if(feedback) feedback.style.display = 'none';
    });
  }

  // Tenta inicializar assim que o DOM estiver pronto
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', _initSmartScan);
  } else {
    setTimeout(_initSmartScan, 800);
  }
})();
</script>
"""),
            # Upload area — com loading overlay enquanto processa
            rx.box(
                rx.upload(
                    rx.vstack(
                        rx.icon(tag="camera", size=28, color=S.COPPER),
                        rx.text(
                            "Foto ou arquivo da NF",
                            font_size="14px",
                            font_weight="600",
                            color=S.TEXT_PRIMARY,
                        ),
                        rx.text(
                            "JPG, PNG, HEIC — máx. 10MB",
                            font_size="12px",
                            color=S.TEXT_MUTED,
                        ),
                        align="center",
                        spacing="1",
                        padding_y="20px",
                    ),
                    id="nf_upload",
                    accept={"image/*": [".jpg", ".jpeg", ".png", ".heic", ".webp"]},
                    max_files=1,
                    max_size=10 * 1024 * 1024,
                    on_drop=ReembolsoState.handle_nf_upload(rx.upload_files(upload_id="nf_upload")),
                    border=f"2px dashed {S.BORDER_ACCENT}",
                    border_radius="12px",
                    bg=S.COPPER_GLOW,
                    cursor="pointer",
                    width="100%",
                    _hover={"border_color": S.COPPER, "bg": "rgba(201,139,42,0.12)"},
                    transition="all 0.2s ease",
                ),
                # Overlay de loading enquanto a imagem é processada
                rx.cond(
                    ReembolsoState.is_uploading_nf,
                    rx.box(
                        rx.vstack(
                            rx.spinner(size="3", color=S.COPPER),
                            rx.text(
                                "Processando imagem...",
                                font_size="13px",
                                color=S.TEXT_PRIMARY,
                                font_weight="600",
                            ),
                            spacing="3",
                            align="center",
                        ),
                        position="absolute",
                        top="0", left="0", right="0", bottom="0",
                        bg="rgba(3,5,4,0.82)",
                        border_radius="12px",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        z_index="10",
                    ),
                ),
                position="relative",
                width="100%",
            ),
            # Preview da imagem e bloco da IA
            rx.cond(
                ReembolsoState.image_data_url != "",
                rx.vstack(
                    rx.image(
                        src=ReembolsoState.image_data_url,
                        max_height="220px",
                        border_radius="10px",
                        object_fit="contain",
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        width="100%",
                    ),
                    rx.hstack(
                        rx.icon(tag="check-circle", size=14, color=S.SUCCESS),
                        rx.text(
                            ReembolsoState.image_filename,
                            font_size="12px",
                            color=S.SUCCESS,
                            font_weight="600",
                        ),
                        spacing="1",
                        align="center",
                    ),
                    # Botão extrair IA
                    rx.button(
                        rx.cond(
                            ReembolsoState.is_analyzing,
                            rx.hstack(
                                rx.spinner(size="2"),
                                rx.text("Analisando NF..."),
                                spacing="2",
                                align="center",
                            ),
                            rx.hstack(
                                rx.icon(tag="bot", size=16),
                                rx.text("Extrair Dados com IA"),
                                spacing="2",
                                align="center",
                            ),
                        ),
                        on_click=ReembolsoState.analyze_receipt,
                        disabled=ReembolsoState.is_analyzing,
                        width="100%",
                        margin_top="10px",
                        bg=S.PATINA,
                        color="white",
                        _hover={"bg": S.SUCCESS},
                        border_radius="8px",
                    ),
                    # Feedback IA
                    rx.cond(
                        ReembolsoState.analysis_done,
                        rx.vstack(
                            rx.cond(
                                ReembolsoState.ai_verified,
                                # Sucesso
                                rx.box(
                                    rx.hstack(
                                        rx.icon(tag="check-circle", size=16, color=S.SUCCESS),
                                        rx.text(
                                            "Dados validados com sucesso pela IA!",
                                            font_size="13px",
                                            font_weight="bold",
                                            color=S.SUCCESS,
                                        ),
                                        align="center",
                                        spacing="2",
                                    ),
                                    bg="rgba(42, 157, 143, 0.1)",
                                    border=f"1px solid {S.SUCCESS}",
                                    padding="10px",
                                    border_radius="8px",
                                    width="100%",
                                ),
                                # Erro/Divergência
                                rx.box(
                                    rx.hstack(
                                        rx.icon(tag="alert-triangle", size=16, color=S.WARNING),
                                        rx.text(
                                            "Divergência Encontrada",
                                            font_size="13px",
                                            font_weight="bold",
                                            color=S.WARNING,
                                        ),
                                        align="center",
                                        spacing="2",
                                        margin_bottom="6px",
                                    ),
                                    rx.foreach(
                                        ReembolsoState.validation_errors,
                                        lambda err: rx.text(
                                            f"• {err}", color=S.WARNING, font_size="12px"
                                        ),
                                    ),
                                    rx.cond(
                                        ReembolsoState.ai_override,
                                        rx.text(
                                            "Você optou por enviar com divergência.",
                                            font_size="12px",
                                            color=S.WARNING,
                                            font_style="italic",
                                            margin_top="8px",
                                        ),
                                        rx.cond(
                                            ReembolsoState.ai_attempt_count < 3,
                                            rx.text(
                                                f"Corrija os valores ou envie foto melhor ({ReembolsoState.ai_attempt_count}/3).",
                                                font_size="12px",
                                                color=S.TEXT_MUTED,
                                                margin_top="8px",
                                            ),
                                            rx.vstack(
                                                rx.text(
                                                    "Limite de 3 tentativas atingido.",
                                                    font_size="12px",
                                                    color=S.WARNING,
                                                ),
                                                rx.button(
                                                    "Permitir envio com divergência (Sujeito a auditoria)",
                                                    on_click=ReembolsoState.set_ai_override,
                                                    bg=S.WARNING,
                                                    color="white",
                                                    size="1",
                                                    margin_top="4px",
                                                    border_radius="6px",
                                                ),
                                                align="start",
                                                margin_top="8px",
                                            ),
                                        ),
                                    ),
                                    bg="rgba(192, 57, 43, 0.1)",
                                    border=f"1px solid {S.WARNING}",
                                    padding="10px",
                                    border_radius="8px",
                                    width="100%",
                                    margin_top="6px",
                                ),
                            ),
                            align="start",
                            width="100%",
                            margin_top="10px",
                        ),
                    ),
                    align="center",
                    spacing="2",
                    width="100%",
                ),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


# ── Seção 6: AI Score Badge (feature flag: ai_score) ─────────────────────────


def section_ai_score() -> rx.Component:
    return rx.cond(
        ReembolsoState.feat_score & ReembolsoState.analysis_done,
        _card(
            rx.hstack(
                rx.vstack(
                    _section_title("shield-check", "Score de Confiabilidade"),
                    rx.text(
                        "Calculado com base em GPS, verificação IA e histórico.",
                        font_size="11px",
                        color=S.TEXT_MUTED,
                        margin_top="-10px",
                    ),
                    spacing="0",
                    align="start",
                ),
                rx.spacer(),
                rx.vstack(
                    rx.text(
                        ReembolsoState.ai_score.to_string(),
                        font_size="40px",
                        font_weight="900",
                        color=ReembolsoState.ai_score_color,
                        font_family=S.FONT_TECH,
                        line_height="1",
                    ),
                    rx.badge(
                        ReembolsoState.ai_score_label,
                        color_scheme=rx.match(
                            ReembolsoState.ai_score_label,
                            ("Alto", "teal"),
                            ("Médio", "amber"),
                            ("Baixo", "red"),
                            "gray",
                        ),
                        variant="soft",
                        radius="full",
                    ),
                    align="center",
                    spacing="1",
                ),
                align="center",
                width="100%",
            ),
            width="100%",
        ),
        rx.fragment(),
    )


# ── Seção 7: Assinatura Digital (feature flag: digital_signature) ─────────────


def section_assinatura() -> rx.Component:
    return rx.cond(
        ReembolsoState.feat_signature,
        _card(
            _section_title("pen-line", "Assinatura Digital"),
            rx.vstack(
                rx.text(
                    "Assine com o dedo ou mouse abaixo para atestar a veracidade do reembolso.",
                    font_size="12px",
                    color=S.TEXT_MUTED,
                    line_height="1.5",
                    margin_bottom="4px",
                ),
                # Canvas de assinatura — script inline via rx.html para executar no corpo
                rx.html("""
<div id="fr-sig-init-hook" style="display:none"></div>
<script>
(function(){
  if(window._frSigObs){window._frSigObs.disconnect();window._frSigObs=null;}
  function _bind(){
    var c=document.getElementById('fr-sig-canvas');
    if(!c)return;
    var ctx=c.getContext('2d');
    ctx.strokeStyle='#C98B2A';ctx.lineWidth=3;ctx.lineCap='round';ctx.lineJoin='round';
    var drawing=false;
    function pos(e){
      var r=c.getBoundingClientRect();var s=e.touches?e.touches[0]:e;
      return{x:(s.clientX-r.left)*(c.width/r.width),y:(s.clientY-r.top)*(c.height/r.height)};
    }
    c.onmousedown=function(e){e.preventDefault();drawing=true;var p=pos(e);ctx.beginPath();ctx.moveTo(p.x,p.y);};
    c.onmousemove=function(e){if(!drawing)return;var p=pos(e);ctx.lineTo(p.x,p.y);ctx.stroke();};
    c.onmouseup=function(){drawing=false;};
    c.onmouseleave=function(){drawing=false;};
    c.ontouchstart=function(e){e.preventDefault();drawing=true;var p=pos(e);ctx.beginPath();ctx.moveTo(p.x,p.y);};
    c.ontouchmove=function(e){e.preventDefault();if(!drawing)return;var p=pos(e);ctx.lineTo(p.x,p.y);ctx.stroke();};
    c.ontouchend=function(){drawing=false;};
  }
  _bind();
  [50,150,300,600,1000,2000].forEach(function(t){setTimeout(_bind,t);});
  var _t;
  window._frSigObs=new MutationObserver(function(){clearTimeout(_t);_t=setTimeout(_bind,80);});
  window._frSigObs.observe(document.body,{childList:true,subtree:true,attributes:false});
})();
</script>
"""),
                rx.el.canvas(
                    id="fr-sig-canvas",
                    width="800",
                    height="200",
                    style={
                        "border": "1px solid rgba(255,255,255,0.15)",
                        "borderRadius": "8px",
                        "background": "rgba(255,255,255,0.04)",
                        "width": "100%",
                        "minHeight": "160px",
                        "cursor": "crosshair",
                        "touchAction": "none",
                        "display": "block",
                        "userSelect": "none",
                    },
                ),
                rx.hstack(
                    rx.button(
                        rx.icon(tag="eraser", size=14),
                        "Limpar",
                        on_click=ReembolsoState.clear_signature,
                        size="1",
                        variant="ghost",
                        color_scheme="red",
                    ),
                    rx.button(
                        rx.icon(tag="check", size=13),
                        "Confirmar Assinatura",
                        on_click=ReembolsoState.capture_signature,
                        size="1",
                        style={
                            "background": "rgba(42,157,143,0.12)",
                            "border": "1px solid rgba(42,157,143,0.3)",
                            "color": S.PATINA,
                            "cursor": "pointer",
                            "border_radius": "6px",
                            "padding": "5px 14px",
                        },
                    ),
                    rx.cond(
                        ReembolsoState.signature_b64 != "",
                        rx.hstack(
                            rx.icon(tag="check-circle", size=14, color=S.PATINA),
                            rx.text("Assinatura capturada ✓", size="1", color=S.PATINA, weight="medium"),
                            spacing="1",
                            align="center",
                        ),
                    ),
                    spacing="2",
                    align="center",
                    flex_wrap="wrap",
                    margin_top="8px",
                ),
                spacing="3",
                width="100%",
            ),
            width="100%",
        ),
        rx.fragment(),
    )


# ── Overlay de loading ───────────────────────────────────────────────────────


def loading_overlay() -> rx.Component:
    return rx.cond(
        ReembolsoState.is_submitting,
        rx.box(
            rx.vstack(
                rx.spinner(size="3", color=S.COPPER),
                rx.text(
                    "Enviando Reembolso...",
                    color=S.COPPER,
                    font_family=S.FONT_TECH,
                    font_size="16px",
                    font_weight="700",
                    letter_spacing="0.06em",
                ),
                rx.text(
                    "PDF sendo gerado e enviado ao servidor",
                    color=S.TEXT_MUTED,
                    font_size="13px",
                ),
                spacing="3",
                align="center",
            ),
            position="fixed",
            inset="0",
            bg="rgba(3,5,4,0.88)",
            display="flex",
            align_items="center",
            justify_content="center",
            z_index="9999",
            backdrop_filter="blur(6px)",
        ),
    )


# ── Tab 1: Formulário ────────────────────────────────────────────────────────


def _tab_nova_solicitacao() -> rx.Component:
    return rx.vstack(
        section_abastecimento(),
        section_localizacao(),
        section_gps_checkin(),
        section_km(),
        section_nota_fiscal(),
        section_ai_score(),
        section_assinatura(),
        # Botão submit
        rx.button(
            rx.cond(
                ReembolsoState.is_submitting,
                rx.hstack(
                    rx.spinner(size="2"),
                    rx.text("Enviando..."),
                    spacing="2",
                    align="center",
                ),
                rx.hstack(
                    rx.icon(tag="send", size=18),
                    rx.text("Enviar Solicitação de Reembolso"),
                    spacing="2",
                    align="center",
                ),
            ),
            on_click=ReembolsoState.try_submit,
            disabled=ReembolsoState.is_submitting,
            bg=S.COPPER,
            color="white",
            height="54px",
            width="100%",
            border_radius="12px",
            font_size="15px",
            font_weight="700",
            font_family=S.FONT_TECH,
            letter_spacing="0.05em",
            _hover={"bg": S.COPPER_LIGHT},
            _active={"bg": S.COPPER},
            margin_top="4px",
            cursor="pointer",
        ),
        rx.text(
            "Após enviar, o PDF do comprovante será gerado automaticamente.",
            font_size="12px",
            color=S.TEXT_MUTED,
            text_align="center",
        ),
        spacing="4",
        width="100%",
        padding_top="16px",
    )


# ── Tab 2: Meus Reembolsos ───────────────────────────────────────────────────


def _card_reembolso(r: dict) -> rx.Component:
    """Card de reembolso no histórico do usuário."""
    # date_short é pré-formatado no state (não usar slicing Python em Vars)
    return rx.box(
        rx.vstack(
            # Linha 1: fuel badge + data + AI badge
            rx.hstack(
                rx.badge(
                    r.get("fuel_type", "—"),
                    color_scheme=rx.match(
                        r.get("fuel_type", ""),
                        ("Gasolina", "yellow"),
                        ("Gasolina Aditivada", "yellow"),
                        ("Etanol", "teal"),
                        ("Diesel", "blue"),
                        ("Diesel S10", "blue"),
                        ("GNV", "violet"),
                        "gray",
                    ),
                    variant="soft",
                    radius="full",
                    font_size="11px",
                    font_weight="600",
                ),
                rx.spacer(),
                rx.cond(
                    r.get("ai_verified", False),
                    rx.badge(
                        "IA ✓", color_scheme="teal", variant="soft", radius="full", font_size="10px"
                    ),
                ),
                rx.text(
                    r.get("date_short", "—"),
                    font_size="11px",
                    color=S.TEXT_MUTED,
                    font_family=S.FONT_TECH,
                ),
                spacing="2",
                align="center",
                width="100%",
            ),
            # Linha 2: valor total (destaque) + finalidade
            rx.hstack(
                rx.vstack(
                    rx.hstack(
                        rx.text("R$", font_size="11px", color=S.TEXT_MUTED, margin_top="3px"),
                        rx.text(
                            r.get("total_value", "—"),
                            font_size="24px",
                            font_weight="700",
                            color=S.COPPER,
                            font_family=S.FONT_TECH,
                            line_height="1",
                        ),
                        spacing="1",
                        align="end",
                    ),
                    rx.text(
                        r.get("purpose", "—"),
                        font_size="12px",
                        color=S.TEXT_MUTED,
                        max_width="200px",
                        overflow="hidden",
                        text_overflow="ellipsis",
                        white_space="nowrap",
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="map-pin", size=12, color=S.TEXT_MUTED),
                        rx.text(r.get("city", "—"), font_size="11px", color=S.TEXT_MUTED),
                        spacing="1",
                        align="center",
                    ),
                    rx.cond(
                        r.get("km_per_liter", "") != "",
                        rx.hstack(
                            rx.icon(tag="gauge", size=12, color=S.PATINA),
                            rx.text(
                                r.get("km_per_liter", "—"),
                                rx.el.span(" km/L", font_size="10px"),
                                font_size="12px",
                                font_weight="600",
                                color=S.PATINA,
                                font_family=S.FONT_TECH,
                            ),
                            spacing="1",
                            align="center",
                        ),
                    ),
                    spacing="1",
                    align="end",
                ),
                width="100%",
                align="center",
            ),
            # Linha 3: PDF download (Sempre visível conforme especificação)
            rx.link(
                rx.hstack(
                    rx.icon(tag="file-down", size=14, color=S.PATINA),
                    rx.text(
                        "Baixar Comprovante PDF",
                        font_size="12px",
                        color=S.PATINA,
                        font_weight="600",
                    ),
                    spacing="2",
                    align="center",
                ),
                href=r.get("pdf_report_url", "#"),
                is_external=True,
                style={"text_decoration": "none"},
            ),
            spacing="3",
            width="100%",
        ),
        bg=S.BG_ELEVATED,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="14px",
        padding="16px",
        width="100%",
        _hover={"border_color": S.BORDER_ACCENT},
        transition="border-color 0.2s",
    )


def _tab_meus_reembolsos() -> rx.Component:
    return rx.vstack(
        # Cabeçalho da seção
        rx.hstack(
            rx.icon(tag="clock", size=16, color=S.COPPER),
            rx.text(
                "Histórico de Solicitações",
                font_size="14px",
                font_weight="700",
                color=S.TEXT_PRIMARY,
                font_family=S.FONT_TECH,
            ),
            rx.spacer(),
            rx.text(
                ReembolsoState.reembolsos_list.length().to_string(),
                font_size="12px",
                color=S.TEXT_MUTED,
                font_family=S.FONT_TECH,
            ),
            rx.text("registros", font_size="12px", color=S.TEXT_MUTED),
            spacing="2",
            align="center",
            width="100%",
        ),
        # Lista
        rx.cond(
            ReembolsoState.reembolsos_list,
            rx.vstack(
                rx.foreach(ReembolsoState.reembolsos_list, _card_reembolso),
                spacing="3",
                width="100%",
            ),
            rx.center(
                rx.vstack(
                    rx.icon(tag="inbox", size=48, color=S.TEXT_MUTED),
                    rx.text(
                        "Nenhuma solicitação enviada ainda.",
                        font_size="14px",
                        color=S.TEXT_MUTED,
                        text_align="center",
                    ),
                    rx.text(
                        "Após enviar seu primeiro reembolso, ele aparecerá aqui.",
                        font_size="12px",
                        color=S.TEXT_MUTED,
                        text_align="center",
                    ),
                    spacing="2",
                    align="center",
                ),
                padding_y="48px",
                width="100%",
            ),
        ),
        spacing="4",
        width="100%",
        padding_top="16px",
    )


# ── Tab 3: E-mails ───────────────────────────────────────────────────────────


def _email_row_form(r: dict) -> rx.Component:
    return _card(
        rx.hstack(
            rx.vstack(
                rx.text(r.get("contract", ""), font_weight="bold", color=S.TEXT_PRIMARY),
                rx.text(r.get("email", ""), font_size="13px", color=S.TEXT_MUTED),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            rx.icon_button(
                rx.icon(tag="trash-2", size=16),
                on_click=lambda: ReembolsoState.delete_email(
                    r.get("contract", ""), r.get("email", "")
                ),
                color_scheme="red",
                variant="soft",
            ),
            align="center",
            width="100%",
        ),
        padding="12px",
        margin_bottom="8px",
    )


def _tab_emails_form() -> rx.Component:
    return rx.vstack(
        # Formulário para adicionar email
        _card(
            _section_title("mail-plus", "Novo Destinatário"),
            rx.vstack(
                rx.box(
                    _label("Contrato"),
                    _input(
                        "Ex: BOM-001",
                        ReembolsoState.email_new_contract,
                        ReembolsoState.set_email_new_contract,
                    ),
                ),
                rx.box(
                    _label("E-mail"),
                    _input(
                        "exemplo@bomtempo.com",
                        ReembolsoState.email_new_address,
                        ReembolsoState.set_email_new_address,
                        "email",
                    ),
                ),
                rx.button(
                    "Adicionar E-mail",
                    on_click=ReembolsoState.add_email,
                    bg=S.COPPER,
                    color="white",
                    width="100%",
                    disabled=(ReembolsoState.email_new_contract == "")
                    | (ReembolsoState.email_new_address == ""),
                ),
                spacing="3",
                width="100%",
            ),
        ),
        # Lista de emails cadastrados
        rx.hstack(
            rx.icon(tag="users", size=16, color=S.COPPER),
            rx.text(
                "E-mails Cadastrados",
                font_size="14px",
                font_weight="700",
                color=S.TEXT_PRIMARY,
                font_family=S.FONT_TECH,
            ),
            rx.spacer(),
            rx.icon_button(
                rx.icon(tag="refresh-cw", size=14),
                on_click=ReembolsoState.load_emails,
                variant="ghost",
            ),
            align="center",
            width="100%",
            margin_top="16px",
        ),
        rx.cond(
            ReembolsoState.email_list,
            rx.vstack(rx.foreach(ReembolsoState.email_list, _email_row_form), width="100%"),
            rx.box(
                rx.hstack(
                    rx.icon(tag="alert-triangle", size=16, color=S.WARNING),
                    rx.vstack(
                        rx.text(
                            "Nenhum e-mail de notificação cadastrado",
                            font_size="13px",
                            font_weight="600",
                            color=S.WARNING,
                            font_family=S.FONT_TECH,
                        ),
                        rx.text(
                            "O comprovante será gerado, mas nenhum responsável receberá o e-mail de aprovação. "
                            "Acesse a aba 'E-mails de Notificação' no Dashboard para cadastrar.",
                            font_size="12px",
                            color=S.TEXT_MUTED,
                            font_family=S.FONT_BODY,
                            line_height="1.5",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    spacing="3",
                    align="start",
                    width="100%",
                ),
                padding="14px 16px",
                bg=S.WARNING_BG,
                border=f"1px solid rgba(245,158,11,0.25)",
                border_radius=S.R_CONTROL,
                width="100%",
            ),
        ),
        spacing="4",
        width="100%",
        padding_top="16px",
    )


# ── Formulário principal ─────────────────────────────────────────────────────


def reembolso_form_page() -> rx.Component:
    return rx.box(
        loading_overlay(),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.text(
                        "REEMBOLSO",
                        font_size="22px",
                        font_weight="900",
                        font_family=S.FONT_TECH,
                        letter_spacing="0.08em",
                        color="white",
                        line_height="1",
                    ),
                    rx.text(
                        "Combustível",
                        font_size="13px",
                        font_weight="400",
                        color=S.TEXT_MUTED,
                        font_family=S.FONT_TECH,
                        letter_spacing="0.12em",
                    ),
                    spacing="0",
                    align="start",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.icon(tag="user", size=14, color=S.TEXT_MUTED),
                    rx.text(
                        GlobalState.current_user_name,
                        font_size="13px",
                        color=S.TEXT_MUTED,
                    ),
                    spacing="1",
                    align="center",
                ),
                width="100%",
                align="center",
                margin_bottom="4px",
            ),
            # Linha decorativa
            rx.box(
                height="1px",
                bg=f"linear-gradient(90deg, {S.COPPER}, transparent)",
                width="100%",
                margin_bottom="8px",
            ),
            # Tabs
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon(tag="circle-plus", size=14, color=S.TEXT_PRIMARY),
                            rx.text(
                                "Nova Solicitação",
                                font_family=S.FONT_TECH,
                                font_size="13px",
                                font_weight="600",
                                color=S.TEXT_PRIMARY,
                            ),
                            spacing="2",
                            align="center",
                        ),
                        value="form",
                        cursor="pointer",
                        style={"color": S.TEXT_PRIMARY},
                    ),
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon(tag="clock", size=14, color=S.TEXT_PRIMARY),
                            rx.text(
                                "Meus Reembolsos",
                                font_family=S.FONT_TECH,
                                font_size="13px",
                                font_weight="600",
                                color=S.TEXT_PRIMARY,
                            ),
                            spacing="2",
                            align="center",
                        ),
                        value="historico",
                        cursor="pointer",
                        style={"color": S.TEXT_PRIMARY},
                    ),
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon(tag="mail", size=14, color=S.TEXT_PRIMARY),
                            rx.text(
                                "E-mails",
                                font_family=S.FONT_TECH,
                                font_size="13px",
                                font_weight="600",
                                color=S.TEXT_PRIMARY,
                            ),
                            spacing="2",
                            align="center",
                        ),
                        value="emails",
                        cursor="pointer",
                        style={"color": S.TEXT_PRIMARY},
                        on_click=ReembolsoState.load_emails,
                    ),
                    bg=S.BG_ELEVATED,
                    border_radius="12px",
                    padding="4px",
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    width="100%",
                    style={
                        "--tabs-trigger-active-color": S.COPPER,
                        "--tabs-trigger-color": S.TEXT_MUTED,
                    },
                ),
                rx.tabs.content(_tab_nova_solicitacao(), value="form"),
                rx.tabs.content(_tab_meus_reembolsos(), value="historico"),
                rx.tabs.content(_tab_emails_form(), value="emails"),
                default_value="historico",
                width="100%",
            ),
            spacing="4",
            width="100%",
            max_width="680px",
            margin_x="auto",
            padding_x=["16px", "16px", "24px"],
            padding_y="24px",
        ),
        min_height="100vh",
        bg=S.BG_DEPTH,
        width="100%",
    )
