"""
Action AI — Escutador Executivo Premium.
FAB: bottom-right. Popup: orb animado, última resposta, HITL. Entrada: voz ou texto.
"""

import reflex as rx

from bomtempo.core import styles as S
from bomtempo.state.action_ai_state import ActionAIState
from bomtempo.state.global_state import GlobalState


# ── CSS ───────────────────────────────────────────────────────────────────────

ACTION_AI_CSS = """
@keyframes aai-orb-idle {
  0%,100% { box-shadow: 0 0 0 0 rgba(201,139,42,0.5), 0 0 30px rgba(201,139,42,0.18); }
  50%      { box-shadow: 0 0 0 16px rgba(201,139,42,0), 0 0 40px rgba(201,139,42,0.3); }
}
@keyframes aai-orb-listen {
  0%,100% { transform:scale(1);    box-shadow:0 0 0 0   rgba(201,139,42,0.9), 0 0 0 4px rgba(201,139,42,0.3); }
  50%      { transform:scale(1.08); box-shadow:0 0 0 22px rgba(201,139,42,0), 0 0 0 4px rgba(201,139,42,0.15); }
}
@keyframes aai-orb-think {
  0%,100% { box-shadow: 0 0 0 0 rgba(99,102,241,0.7),  0 0 24px rgba(99,102,241,0.2); }
  50%      { box-shadow: 0 0 0 14px rgba(99,102,241,0), 0 0 36px rgba(99,102,241,0.4); }
}
@keyframes aai-ripple {
  0%   { transform:scale(0.8); opacity:0.6; }
  100% { transform:scale(2.2); opacity:0;   }
}
@keyframes aai-slide-up {
  from { opacity:0; transform:translateY(16px) scale(0.96); }
  to   { opacity:1; transform:translateY(0)    scale(1);    }
}
@keyframes aai-wave-bar {
  0%,100% { height:4px;  }
  50%      { height:20px; }
}
@keyframes aai-scan-line {
  0%   { top:0%;    opacity:0.9; }
  50%  { opacity:   0.2; }
  100% { top:100%;  opacity:0.9; }
}
@keyframes aai-spin { to { transform:rotate(360deg); } }
@keyframes aai-fade-in {
  from { opacity:0; transform:translateY(4px); }
  to   { opacity:1; transform:translateY(0);   }
}
@keyframes aai-pulse-dot {
  0%,100% { opacity:1; }
  50%      { opacity:0.3; }
}
@keyframes aai-chip-in {
  from { opacity:0; transform:translateY(6px) scale(0.95); }
  to   { opacity:1; transform:translateY(0)   scale(1);    }
}
@keyframes aai-fab-tooltip {
  from { opacity:0; transform:translateY(4px); }
  to   { opacity:1; transform:translateY(0); }
}

.aai-idle   { animation: aai-orb-idle   3.5s ease-in-out infinite; }
.aai-listen { animation: aai-orb-listen 1s   ease-in-out infinite !important; }
.aai-think  { animation: aai-orb-think  1.5s ease-in-out infinite !important; }

.aai-popup {
  animation: aai-slide-up 0.28s cubic-bezier(0.34,1.56,0.64,1) forwards;
}

.aai-ring {
  position:absolute; border-radius:50%; pointer-events:none;
  border:1px solid rgba(201,139,42,0.4);
  animation:aai-ripple 2.2s ease-out infinite;
}

.aai-wave { display:flex; align-items:center; gap:3px; height:24px; }
.aai-wave-bar {
  width:2.5px; border-radius:2px; background:rgba(201,139,42,0.9);
  animation:aai-wave-bar 0.75s ease-in-out infinite;
}

.aai-response { animation: aai-fade-in 0.35s ease forwards; }

.aai-scan {
  position:absolute; left:0; right:0; height:1px;
  background:linear-gradient(90deg,transparent,rgba(99,102,241,0.8),transparent);
  animation:aai-scan-line 1.8s linear infinite;
  pointer-events:none;
}

.aai-input {
  background:rgba(255,255,255,0.04);
  border:1px solid rgba(255,255,255,0.1);
  border-radius:10px;
  padding:9px 13px;
  color:#E0E0E0;
  font-size:13px;
  font-family:'Outfit',sans-serif;
  outline:none;
  width:100%;
  transition:border-color 0.2s ease;
}
.aai-input:focus { border-color:rgba(201,139,42,0.45); }
.aai-input::placeholder { color:#667777; }

.aai-status-dot {
  width:6px; height:6px; border-radius:50%; flex-shrink:0;
  animation:aai-pulse-dot 2s ease-in-out infinite;
}

/* ── Chips de sugestão ── */
.aai-chip {
  display:inline-flex; align-items:center; gap:5px;
  padding:5px 10px; border-radius:20px; cursor:pointer;
  background:rgba(201,139,42,0.08);
  border:1px solid rgba(201,139,42,0.2);
  font-size:11px; font-family:'Outfit',sans-serif;
  color:rgba(224,166,59,0.85);
  white-space:nowrap;
  transition:background 0.18s ease, border-color 0.18s ease, transform 0.15s ease;
  animation: aai-chip-in 0.3s ease forwards;
}
.aai-chip:hover {
  background:rgba(201,139,42,0.18);
  border-color:rgba(201,139,42,0.45);
  transform:translateY(-1px);
}
.aai-chip:active { transform:translateY(0); }

/* ── Top bar buttons ── */
.aai-topbtn {
  display:flex; flex-direction:column; align-items:center; gap:1px;
  background:transparent; border:none; border-radius:8px;
  padding:5px 8px; cursor:pointer;
  transition:background 0.15s ease, transform 0.12s ease;
}
.aai-topbtn:hover { background:rgba(255,255,255,0.07); transform:translateY(-1px); }
.aai-topbtn:active { transform:translateY(0); }

/* ── FAB tooltip ── */
.aai-fab-wrap { position:fixed; bottom:24px; right:24px; }
.aai-fab-tooltip {
  position:absolute; bottom:calc(100% + 10px); right:0;
  background:rgba(7,15,13,0.96); border:1px solid rgba(201,139,42,0.3);
  border-radius:8px; padding:7px 11px;
  font-size:11.5px; font-family:'Outfit',sans-serif;
  color:#bbb; white-space:nowrap; pointer-events:none;
  opacity:0; transition:opacity 0.2s ease;
  box-shadow:0 4px 16px rgba(0,0,0,0.4);
}
.aai-fab-tooltip strong { color:#C98B2A; font-weight:600; }
.aai-fab-wrap:hover .aai-fab-tooltip { opacity:1; }

/* ── Orb hover ── */
.aai-orb-btn { transition:transform 0.18s ease, box-shadow 0.18s ease !important; }
.aai-orb-btn:hover { transform:scale(1.06) !important; }
"""


# ── JS — Audio playback + Voice ───────────────────────────────────────────────
ACTION_AI_JS = """
(function(){
  var _rec = null;

  /* ── Mic permission ─────────────────────────────────────────────────────── */
  window.actionAIRequestMicPermission = function(){
    if(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia)
      navigator.mediaDevices.getUserMedia({audio:true})
        .then(function(s){ s.getTracks().forEach(function(t){t.stop();}); })
        .catch(function(e){ console.warn('[ActionAI] mic denied:',e); });
  };

  /* ── Speech Recognition ─────────────────────────────────────────────────── */
  window.actionAIStartVoice = function(){
    var SR = window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SR){ console.warn('[ActionAI] SR not supported'); if(window._aaiOnStopped) window._aaiOnStopped(); return; }
    if(_rec){ try{_rec.abort();}catch(e){} _rec=null; }
    _rec = new SR();
    _rec.continuous = false; _rec.lang = 'pt-BR';
    _rec.interimResults = false; _rec.maxAlternatives = 1;
    _rec.onresult = function(e){ if(window._aaiOnResult) window._aaiOnResult(e.results[0][0].transcript); };
    _rec.onend  = function(){ _rec=null; if(window._aaiOnStopped) window._aaiOnStopped(); };
    _rec.onerror= function(e){ console.warn('[ActionAI] SR error:',e.error); _rec=null; if(window._aaiOnStopped) window._aaiOnStopped(); };
    try{ _rec.start(); }catch(e){ console.warn('[ActionAI] rec.start() failed:',e); _rec=null; if(window._aaiOnStopped) window._aaiOnStopped(); }
  };
  window.actionAIStopVoice = function(){ if(_rec){ try{_rec.stop();}catch(e){} _rec=null; } };

  /* ── Hidden-input bridges (JS → Reflex) ─────────────────────────────────── */
  function _triggerInput(id, val){
    var el = document.getElementById(id);
    if(!el) return;
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(el, val);
    el.dispatchEvent(new Event('input',{bubbles:true}));
  }
  window._aaiOnResult  = function(t){ _triggerInput('_aai_transcript_input', t); };
  window._aaiOnStopped = function(){ _triggerInput('_aai_stopped_input', String(Date.now())); };

})();
"""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _wave_bars() -> rx.Component:
    delays = ["0s", "0.1s", "0.2s", "0.3s", "0.4s", "0.5s"]
    return rx.box(
        *[
            rx.box(
                class_name="aai-wave-bar",
                style={"animationDelay": d, "animationDuration": f"{0.65 + i*0.09:.2f}s"},
            )
            for i, d in enumerate(delays)
        ],
        class_name="aai-wave",
    )


def _orb_icon() -> rx.Component:
    return rx.cond(
        ActionAIState.is_processing,
        rx.box(
            rx.icon(tag="brain", size=24, color="white"),
            rx.box(class_name="aai-scan"),
            position="relative",
        ),
        rx.cond(
            ActionAIState.is_listening,
            rx.icon(tag="mic", size=24, color="#0a1f1a"),
            rx.icon(tag="zap", size=24, color="#0a1f1a"),
        ),
    )


# ── HITL Confirmation Card ─────────────────────────────────────────────────────

def _hitl_card() -> rx.Component:
    return rx.cond(
        ActionAIState.hitl_pending,
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.center(
                        rx.icon(tag="shield-alert", size=14, color=S.WARNING),
                        width="26px", height="26px", border_radius="50%",
                        bg="rgba(245,158,11,0.12)",
                    ),
                    rx.vstack(
                        rx.text("Confirmação necessária", font_size="11px", font_weight="700",
                                color=S.WARNING, font_family=S.FONT_TECH, letter_spacing="0.05em"),
                        rx.text(ActionAIState.hitl_summary, font_size="11px",
                                color=S.TEXT_SECONDARY, line_height="1.4"),
                        spacing="0", align="start",
                    ),
                    spacing="2", align="center",
                ),
                # Preview lines — texto puro para evitar conflito de cor do markdown
                rx.box(
                    rx.vstack(
                        rx.foreach(
                            ActionAIState.hitl_preview_lines,
                            lambda line: rx.hstack(
                                rx.box(
                                    width="3px", height="3px", border_radius="50%",
                                    bg=S.TEXT_MUTED, flex_shrink="0", margin_top="6px",
                                ),
                                rx.text(
                                    line, font_size="12px",
                                    color=S.TEXT_PRIMARY,
                                    font_family=S.FONT_MONO,
                                    line_height="1.5",
                                ),
                                spacing="2", align="start", width="100%",
                            ),
                        ),
                        spacing="1", align="start", width="100%",
                    ),
                    bg="rgba(0,0,0,0.25)", border=f"1px solid rgba(255,255,255,0.07)",
                    border_radius="7px", padding="10px", width="100%",
                ),
                # Action buttons
                rx.hstack(
                    rx.button(
                        rx.icon(tag="check", size=12),
                        rx.text("Confirmar", font_size="12px", font_weight="700"),
                        on_click=ActionAIState.confirm_hitl,
                        bg=S.SUCCESS, color="#0a1f1a", border_radius="7px",
                        padding_x="14px", padding_y="7px", cursor="pointer",
                        _hover={"opacity": "0.88"}, flex="1",
                    ),
                    rx.button(
                        rx.icon(tag="x", size=12),
                        rx.text("Cancelar", font_size="12px"),
                        on_click=ActionAIState.reject_hitl,
                        bg="rgba(239,68,68,0.08)", color=S.DANGER,
                        border=f"1px solid rgba(239,68,68,0.25)",
                        border_radius="7px", padding_x="14px", padding_y="7px",
                        cursor="pointer", _hover={"opacity": "0.88"}, flex="1",
                    ),
                    spacing="2", width="100%",
                ),
                spacing="2", width="100%",
            ),
            bg="rgba(245,158,11,0.05)", border=f"1px solid rgba(245,158,11,0.28)",
            border_radius="12px", padding="12px", width="100%",
        ),
    )


# ── Suggestion chips ──────────────────────────────────────────────────────────

_SUGGESTIONS_ADMIN = [
    ("map",          "Abrir painel de obras"),
    ("user-plus",    "Criar novo usuário"),
    ("key-round",    "Trocar minha senha"),
    ("bell-plus",    "Criar alerta de RDO ausente"),
    ("send",         "Enviar RDO para usuário"),
    ("wallet",       "Ir para financeiro"),
]

_SUGGESTIONS_MO = [
    ("clipboard-pen", "Preenche o RDO de hoje ensolarado"),
    ("fuel",          "Registra reembolso 40 litros a 5,89"),
    ("sun",           "RDO diurno clima parcialmente nublado"),
]


def _chip(icon: str, label: str, delay: float) -> rx.Component:
    return rx.el.button(
        rx.icon(tag=icon, size=11),
        rx.text(label, font_size="11px"),
        class_name="aai-chip",
        on_click=[
            ActionAIState.set_input_text(label),
            ActionAIState.set_show_text_input(True),
        ],
        style={"animationDelay": f"{delay:.2f}s"},
    )


def _suggestion_chips() -> rx.Component:
    """Chips de exemplos — visíveis só quando idle e sem resposta ainda.
    Conteúdo varia por role: Mestre de Obras vê apenas form-fill."""
    from bomtempo.state.global_state import GlobalState
    idle = ~ActionAIState.is_processing & ~ActionAIState.is_listening & (ActionAIState.last_response == "")
    return rx.cond(
        idle,
        rx.box(
            rx.vstack(
                rx.text(
                    "Experimente perguntar:",
                    font_size="10px", color=S.TEXT_MUTED,
                    font_family=S.FONT_TECH, letter_spacing="0.07em",
                    text_transform="uppercase",
                ),
                rx.cond(
                    GlobalState.current_user_role == "Mestre de Obras",
                    # MO: only form-fill chips
                    rx.box(
                        *[_chip(icon, label, i * 0.05)
                          for i, (icon, label) in enumerate(_SUGGESTIONS_MO)],
                        display="flex", flex_wrap="wrap", gap="6px",
                    ),
                    # Others: full admin chips
                    rx.box(
                        *[_chip(icon, label, i * 0.05)
                          for i, (icon, label) in enumerate(_SUGGESTIONS_ADMIN)],
                        display="flex", flex_wrap="wrap", gap="6px",
                    ),
                ),
                spacing="2", align="start", width="100%",
            ),
            width="100%",
        ),
    )


# ── Last Response ─────────────────────────────────────────────────────────────

def _last_response() -> rx.Component:
    return rx.cond(
        ActionAIState.last_response != "",
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.center(
                        rx.icon(tag="sparkles", size=10, color="#0a1f1a"),
                        width="18px", height="18px", border_radius="50%",
                        bg=S.COPPER, flex_shrink="0",
                    ),
                    rx.text("Resposta", font_size="9px", color=S.TEXT_MUTED,
                            font_family=S.FONT_TECH, letter_spacing="0.08em",
                            text_transform="uppercase"),
                    rx.spacer(),
                    # Botão "Nova conversa" inline
                    rx.el.button(
                        rx.icon(tag="rotate-ccw", size=10),
                        rx.text("Limpar", font_size="9px"),
                        on_click=ActionAIState.new_conversation,
                        style={
                            "display": "flex", "alignItems": "center", "gap": "4px",
                            "background": "transparent", "border": "none",
                            "color": "#556666", "cursor": "pointer", "padding": "2px 6px",
                            "borderRadius": "5px", "transition": "color 0.15s ease",
                            "fontSize": "9px",
                        },
                        _hover={"color": S.TEXT_MUTED},
                    ),
                    spacing="2", align="center", width="100%",
                ),
                rx.scroll_area(
                    rx.markdown(
                        ActionAIState.last_response,
                        font_size="13.5px",
                        color=S.TEXT_PRIMARY,
                        class_name="aai-response",
                        component_map={
                            "p": lambda *c, **p: rx.el.p(
                                *c, style={"lineHeight": "1.65", "marginBottom": "6px",
                                           "color": S.TEXT_PRIMARY}, **p),
                            "strong": lambda *c, **p: rx.el.strong(
                                *c, style={"color": S.COPPER_LIGHT, "fontWeight": "600"}, **p),
                            "li": lambda *c, **p: rx.el.li(
                                *c, style={"lineHeight": "1.6", "marginBottom": "3px",
                                           "color": S.TEXT_PRIMARY}, **p),
                        },
                    ),
                    max_height="240px",
                    type="hover", scrollbars="vertical", width="100%",
                ),
                spacing="2", width="100%", align="start",
            ),
            bg="rgba(255,255,255,0.02)",
            border=f"1px solid rgba(201,139,42,0.15)",
            border_radius="12px",
            padding="14px",
            width="100%",
        ),
    )


# ── Text input ────────────────────────────────────────────────────────────────

def _text_input_area() -> rx.Component:
    return rx.cond(
        ActionAIState.show_text_input,
        rx.hstack(
            rx.el.input(
                placeholder="Digite sua instrução...",
                value=ActionAIState.input_text,
                on_change=ActionAIState.set_input_text,
                on_key_down=ActionAIState.on_enter_key,
                debounce_timeout=80,
                class_name="aai-input",
                auto_focus=True,
            ),
            rx.button(
                rx.icon(tag="send", size=13, color="#0a1f1a"),
                on_click=ActionAIState.send_message,
                bg=S.COPPER, border_radius="8px", padding="8px",
                cursor="pointer", _hover={"opacity": "0.85"},
                is_loading=ActionAIState.is_processing,
                flex_shrink="0",
            ),
            spacing="2", align="center", width="100%",
        ),
    )


# ── Status label ──────────────────────────────────────────────────────────────

def _status_label() -> rx.Component:
    return rx.text(
        rx.cond(
            ActionAIState.is_processing, "Processando...",
            rx.cond(
                ActionAIState.is_listening, "Ouvindo... fale agora",
                rx.cond(
                    ActionAIState.is_hands_free, "Modo contínuo ativo",
                    "Toque no orb para falar",
                ),
            ),
        ),
        font_size="11px",
        color=rx.cond(
            ActionAIState.is_listening, S.COPPER,
            rx.cond(ActionAIState.is_processing, S.INFO, S.TEXT_MUTED),
        ),
        font_family=S.FONT_TECH,
        letter_spacing="0.05em",
        text_align="center",
    )


# ── Popup panel ───────────────────────────────────────────────────────────────

def _action_ai_popup() -> rx.Component:
    return rx.cond(
        ActionAIState.is_open,
        rx.box(
            rx.vstack(

                # ── Top bar ───────────────────────────────────────────────
                rx.hstack(
                    # Brand
                    rx.hstack(
                        rx.box(
                            class_name="aai-status-dot",
                            style={
                                "background": rx.cond(
                                    ActionAIState.is_processing, S.INFO,
                                    rx.cond(ActionAIState.is_listening, S.COPPER, S.SUCCESS),
                                ),
                            },
                        ),
                        rx.text(
                            "ACTION AI",
                            font_family=S.FONT_TECH, font_weight="800",
                            font_size="12px", color=S.COPPER, letter_spacing="0.12em",
                        ),
                        spacing="2", align="center",
                    ),
                    rx.spacer(),

                    # Controls cluster
                    rx.hstack(
                        # Contínuo
                        rx.el.button(
                            rx.icon(
                                tag=rx.cond(ActionAIState.is_hands_free, "headphones", "mic-off"),
                                size=13,
                                color=rx.cond(ActionAIState.is_hands_free, S.PATINA, S.TEXT_MUTED),
                            ),
                            rx.text("Contínuo", font_size="9px",
                                    color=rx.cond(ActionAIState.is_hands_free, S.PATINA, S.TEXT_MUTED)),
                            on_click=ActionAIState.toggle_hands_free,
                            class_name="aai-topbtn",
                            title="Modo contínuo: fala → resposta → fala, sem parar",
                            style={
                                "background": rx.cond(
                                    ActionAIState.is_hands_free,
                                    "rgba(42,157,143,0.15)", "transparent",
                                ),
                            },
                        ),
                        # Texto
                        rx.el.button(
                            rx.icon(
                                tag="keyboard", size=13,
                                color=rx.cond(ActionAIState.show_text_input, S.COPPER, S.TEXT_MUTED),
                            ),
                            rx.text("Texto", font_size="9px",
                                    color=rx.cond(ActionAIState.show_text_input, S.COPPER, S.TEXT_MUTED)),
                            on_click=ActionAIState.toggle_text_input,
                            class_name="aai-topbtn",
                            title="Digitar instrução ao invés de falar",
                            style={
                                "background": rx.cond(
                                    ActionAIState.show_text_input,
                                    "rgba(201,139,42,0.12)", "transparent",
                                ),
                            },
                        ),
                        # Novo
                        rx.el.button(
                            rx.icon(tag="rotate-ccw", size=13, color=S.TEXT_MUTED),
                            rx.text("Novo", font_size="9px", color=S.TEXT_MUTED),
                            on_click=ActionAIState.new_conversation,
                            class_name="aai-topbtn",
                            title="Iniciar nova conversa (limpa contexto)",
                            style={"background": "transparent"},
                        ),
                        # Fechar
                        rx.el.button(
                            rx.icon(tag="x", size=15, color=S.TEXT_MUTED),
                            on_click=ActionAIState.close_popup,
                            class_name="aai-topbtn",
                            title="Fechar",
                            style={
                                "background": "transparent",
                                "flexDirection": "row",
                                "padding": "6px 6px",
                            },
                        ),
                        spacing="1", align="center",
                    ),

                    width="100%", align="center",
                    padding="11px 12px 9px",
                    border_bottom=f"1px solid rgba(255,255,255,0.06)",
                ),

                # ── Orb + status ──────────────────────────────────────────
                rx.center(
                    rx.vstack(
                        # Orb + rings (200px container so rings aren't clipped)
                        rx.box(
                            # Ripple rings — centered on the 68px orb inside 200px container
                            rx.cond(
                                ActionAIState.is_listening,
                                rx.fragment(
                                    rx.box(class_name="aai-ring", style={"width":"88px","height":"88px","top":"calc(50% - 44px)","left":"calc(50% - 44px)","animationDelay":"0s","position":"absolute"}),
                                    rx.box(class_name="aai-ring", style={"width":"120px","height":"120px","top":"calc(50% - 60px)","left":"calc(50% - 60px)","animationDelay":"0.55s","position":"absolute"}),
                                    rx.box(class_name="aai-ring", style={"width":"152px","height":"152px","top":"calc(50% - 76px)","left":"calc(50% - 76px)","animationDelay":"1.1s","position":"absolute"}),
                                ),
                            ),
                            # Orb
                            rx.center(
                                _orb_icon(),
                                width="60px", height="60px",
                                border_radius="50%",
                                bg=rx.cond(
                                    ActionAIState.is_processing,
                                    "linear-gradient(135deg,#1a1a5e,#2a2a8e)",
                                    f"linear-gradient(135deg,{S.COPPER},#a06c1a)",
                                ),
                                position="absolute",
                                top="calc(50% - 30px)",
                                left="calc(50% - 30px)",
                                overflow="hidden",
                                cursor="pointer",
                                on_click=rx.cond(
                                    ActionAIState.is_listening,
                                    ActionAIState.stop_listening(),
                                    rx.cond(
                                        ActionAIState.is_hands_free | ActionAIState.is_processing,
                                        rx.noop(),
                                        ActionAIState.start_listening(),
                                    ),
                                ),
                                class_name=rx.cond(
                                    ActionAIState.is_processing, "aai-think",
                                    rx.cond(ActionAIState.is_listening, "aai-listen", "aai-idle"),
                                ),
                                transition="background 0.3s ease",
                                box_shadow="0 4px 20px rgba(0,0,0,0.4)",
                            ),
                            position="relative",
                            width="160px",
                            height="160px",
                            flex_shrink="0",
                        ),

                        # Wave bars when listening
                        rx.cond(
                            ActionAIState.is_listening,
                            _wave_bars(),
                            rx.box(height="8px"),
                        ),

                        _status_label(),

                        spacing="2", align="center",
                    ),
                    padding_y="16px",
                    width="100%",
                ),

                # ── Content area ──────────────────────────────────────────
                rx.box(
                    rx.vstack(
                        _hitl_card(),
                        _suggestion_chips(),
                        _last_response(),
                        _text_input_area(),
                        spacing="2", width="100%",
                    ),
                    padding_x="14px",
                    padding_bottom="14px",
                    width="100%",
                ),

                spacing="0",
                width="100%",
            ),

            id="_aai_popup",
            class_name="aai-popup",
            position="fixed",
            bottom="96px",
            right="24px",
            width=["calc(100vw - 48px)", "calc(100vw - 48px)", "360px"],
            bg="rgba(7,15,13,0.97)",
            backdrop_filter="blur(32px)",
            border=f"1px solid rgba(201,139,42,0.3)",
            border_radius="20px",
            box_shadow=(
                "0 24px 64px rgba(0,0,0,0.65),"
                "0 0 0 1px rgba(255,255,255,0.03),"
                "0 0 40px rgba(201,139,42,0.06)"
            ),
            z_index="9997",
            overflow="hidden",
        ),
    )


# ── FAB orb ───────────────────────────────────────────────────────────────────

def _fab_orb() -> rx.Component:
    return rx.box(
        # Idle ring
        rx.cond(
            ~ActionAIState.is_open,
            rx.box(
                class_name="aai-ring",
                style={"width": "62px", "height": "62px",
                       "top": "-5px", "left": "-5px",
                       "animationDuration": "3.2s"},
            ),
        ),
        rx.center(
            rx.cond(
                ActionAIState.is_processing,
                rx.box(
                    rx.icon(tag="loader", size=20, color="white"),
                    style={"animation": "aai-spin 1s linear infinite"},
                ),
                rx.cond(
                    ActionAIState.is_listening,
                    rx.icon(tag="mic", size=20, color="#0a1f1a"),
                    rx.icon(tag="zap", size=20, color="#0a1f1a"),
                ),
            ),
            width="52px", height="52px",
            border_radius="50%",
            bg=rx.cond(
                ActionAIState.is_hands_free & ActionAIState.is_open,
                S.PATINA,
                S.COPPER,
            ),
            cursor="pointer",
            on_click=rx.cond(
                ActionAIState.is_open,
                ActionAIState.close_popup(),
                ActionAIState.open_popup(),
            ),
            class_name=rx.cond(
                ActionAIState.is_listening, "aai-listen aai-orb-btn", "aai-idle aai-orb-btn",
            ),
            transition="background 0.3s ease, transform 0.18s ease",
            position="relative",
            z_index="1",
            box_shadow="0 4px 16px rgba(0,0,0,0.4)",
        ),
        position="relative",
        width="52px",
        height="52px",
    )


# ── Hidden inputs (JS→Reflex bridge) ─────────────────────────────────────────

def _hidden_inputs() -> rx.Component:
    return rx.fragment(
        rx.el.input(
            id="_aai_transcript_input",
            style={"display": "none"},
            on_change=ActionAIState.on_voice_result,
        ),
        rx.el.input(
            id="_aai_stopped_input",
            style={"display": "none"},
            on_change=ActionAIState.on_voice_stopped,
        ),
    )


# ── Public export ─────────────────────────────────────────────────────────────

def action_ai_fab() -> rx.Component:
    """
    Complete Action AI system.
    Renders: CSS + JS + hidden inputs + popup + FAB orb.
    """
    return rx.fragment(
        rx.html(f"<style>{ACTION_AI_CSS}</style>"),
        rx.script(src="/js/aai.js"),
        rx.cond(
            GlobalState.is_authenticated,
            rx.fragment(
                _hidden_inputs(),
                _action_ai_popup(),
                rx.box(
                    # Tooltip visível no hover quando popup fechado
                    rx.cond(
                        ~ActionAIState.is_open,
                        rx.html(
                            '<div class="aai-fab-tooltip">'
                            '<strong>Action AI</strong> · Assistente executivo<br>'
                            '<span style="font-size:10px;color:#667777">Clique para falar ou digitar</span>'
                            '</div>'
                        ),
                    ),
                    _fab_orb(),
                    class_name="aai-fab-wrap",
                    z_index="9998",
                ),
            ),
        ),
    )
