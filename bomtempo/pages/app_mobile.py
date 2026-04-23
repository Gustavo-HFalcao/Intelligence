"""
App Mobile — Página PWA (instalação do dashboard como app nativo)
"""
import reflex as rx
from bomtempo.core import styles as S


# ─── Script de controle do botão de instalação ───────────────────────────────
_INSTALL_PAGE_SCRIPT = """
(function () {
  // Detecta se o navegador é Chromium-based (suporta beforeinstallprompt)
  function _isChromium() {
    return !!(window.chrome || navigator.userAgentData &&
      navigator.userAgentData.brands &&
      navigator.userAgentData.brands.some(function(b) {
        return b.brand === 'Chromium' || b.brand === 'Google Chrome' || b.brand === 'Microsoft Edge';
      }));
  }

  function _syncButton() {
    var btn  = document.getElementById('btp-install-cta');
    var note = document.getElementById('btp-install-note');
    if (!btn) return;

    // Estado 1: já instalado (rodando em standalone)
    if (window.matchMedia('(display-mode: standalone)').matches ||
        window.navigator.standalone === true) {
      btn.textContent   = '✓ App já instalado neste dispositivo';
      btn.disabled      = true;
      btn.style.opacity = '0.55';
      if (note) note.textContent =
        'O Bomtempo Dashboard já está instalado. Abra pelo ícone na tela inicial.';
      return;
    }

    // Estado 2: prompt disponível — botão ativo
    if (window._btpDeferredPrompt) {
      btn.textContent   = 'Instalar Agora';
      btn.disabled      = false;
      btn.style.opacity = '1';
      if (note) note.textContent =
        'Requer Google Chrome, Microsoft Edge ou Safari (iOS 16.4+)';
      return;
    }

    // Estado 3: Chrome/Edge mas prompt ainda não chegou — orientar pela barra de endereço
    if (_isChromium()) {
      btn.textContent   = 'Instalar via Barra do Navegador';
      btn.disabled      = false;
      btn.style.opacity = '0.85';
      if (note) note.textContent =
        'Clique no ícone ⊕ na barra de endereço do Chrome/Edge para instalar — ou aguarde o botão ativar automaticamente.';
      btn.onclick = function() {
        if (window._btpDeferredPrompt) {
          window._btpInstall && window._btpInstall();
        } else {
          alert('Procure o ícone de instalação (⊕) na barra de endereço do seu navegador.');
        }
      };
      return;
    }

    // Estado 4: navegador não suporta
    btn.textContent   = 'Navegador não suportado';
    btn.disabled      = true;
    btn.style.opacity = '0.5';
    if (note) note.textContent =
      'Use Google Chrome (Android/Desktop) ou Microsoft Edge para instalar.';
  }

  // Atualiza assim que o prompt chegar (evento customizado despachado pelo init global)
  window.addEventListener('_btpPromptReady', _syncButton);

  // Atualiza ao instalar
  window.addEventListener('appinstalled', function () {
    var btn  = document.getElementById('btp-install-cta');
    var note = document.getElementById('btp-install-note');
    if (btn) { btn.textContent = '✓ Instalado com sucesso!'; btn.disabled = true; btn.style.opacity = '0.55'; }
    if (note) note.textContent = 'O app foi instalado. Abra pelo ícone na tela inicial.';
  });

  // Polling: tenta por até 10 segundos (beforeinstallprompt é assíncrono)
  var _attempts = 0;
  var _poll = setInterval(function () {
    _syncButton();
    _attempts++;
    if (_attempts >= 20 || window._btpDeferredPrompt) clearInterval(_poll);
  }, 500);

  // Sync inicial
  _syncButton();
  setTimeout(_syncButton, 300);
})();
"""

_PLATFORM_SCRIPT = """
(function() {
  // Mostra a seção correta por plataforma
  function _detectPlatform() {
    var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
    var iosSection   = document.getElementById('btp-ios-steps');
    var otherSection = document.getElementById('btp-other-steps');
    var ctaSection   = document.getElementById('btp-cta-section');
    if (!iosSection || !otherSection) return;
    if (isIOS) {
      iosSection.style.display   = 'block';
      otherSection.style.display = 'none';
      if (ctaSection) ctaSection.style.display = 'none';
    } else {
      iosSection.style.display   = 'none';
      otherSection.style.display = 'block';
      if (ctaSection) ctaSection.style.display = 'flex';
    }
  }
  document.addEventListener('DOMContentLoaded', _detectPlatform);
  setTimeout(_detectPlatform, 300);
})();
"""


def _feature_card(icon: str, title: str, body: str, accent: str = S.COPPER) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.box(
                rx.icon(tag=icon, size=22, color=accent),
                width="44px",
                height="44px",
                border_radius="10px",
                bg=f"rgba({_hex_to_rgb(accent)}, 0.12)",
                border=f"1px solid rgba({_hex_to_rgb(accent)}, 0.25)",
                display="flex",
                align_items="center",
                justify_content="center",
                flex_shrink="0",
            ),
            rx.text(
                title,
                font_family=S.FONT_TECH,
                font_weight="700",
                font_size="15px",
                color="white",
                letter_spacing="0.03em",
            ),
            rx.text(
                body,
                font_size="13px",
                color=S.TEXT_MUTED,
                line_height="1.6",
            ),
            spacing="3",
            align="start",
        ),
        padding="20px",
        border_radius=S.R_CARD,
        bg=S.BG_ELEVATED,
        border=f"1px solid {S.BORDER_SUBTLE}",
        width="100%",
    )


def _hex_to_rgb(hex_color: str) -> str:
    """Converte #RRGGBB para 'R, G, B' para uso em rgba()."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r}, {g}, {b}"


def _step_item(num: str, text: str) -> rx.Component:
    return rx.hstack(
        rx.box(
            rx.text(
                num,
                font_family=S.FONT_TECH,
                font_weight="700",
                font_size="12px",
                color=S.COPPER,
            ),
            width="28px",
            height="28px",
            border_radius="50%",
            bg="rgba(201, 139, 42, 0.12)",
            border="1px solid rgba(201, 139, 42, 0.3)",
            display="flex",
            align_items="center",
            justify_content="center",
            flex_shrink="0",
        ),
        rx.text(text, font_size="14px", color=S.TEXT_PRIMARY, line_height="1.5"),
        spacing="3",
        align="center",
        width="100%",
    )


def _install_section_other() -> rx.Component:
    """Instruções para Android / Chrome / Edge (não-iOS)."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="chrome", size=16, color=S.COPPER),
                rx.text(
                    "Android · Chrome · Edge",
                    font_family=S.FONT_TECH,
                    font_weight="700",
                    font_size="14px",
                    color="white",
                    letter_spacing="0.04em",
                ),
                spacing="2",
                align="center",
            ),
            rx.divider(border_color=S.BORDER_SUBTLE, opacity="0.4"),
            _step_item("1", "Clique no botão \"Instalar Agora\" abaixo."),
            _step_item("2", "Uma janela do navegador vai aparecer pedindo confirmação."),
            _step_item("3", "Confirme — o ícone aparece na tela inicial."),
            _step_item("4", "Abra o app pelo ícone a qualquer momento, sem precisar do navegador."),
            spacing="3",
            align="start",
            width="100%",
        ),
        id="btp-other-steps",
        padding="20px 24px",
        border_radius=S.R_CARD,
        bg=S.BG_ELEVATED,
        border=f"1px solid {S.BORDER_SUBTLE}",
        width="100%",
        display="none",  # JS revela a seção correta
    )


def _install_section_ios() -> rx.Component:
    """Instruções para iOS Safari (sem beforeinstallprompt)."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="apple", size=16, color="#A0A0A0"),
                rx.text(
                    "iPhone · iPad (Safari)",
                    font_family=S.FONT_TECH,
                    font_weight="700",
                    font_size="14px",
                    color="white",
                    letter_spacing="0.04em",
                ),
                spacing="2",
                align="center",
            ),
            rx.divider(border_color=S.BORDER_SUBTLE, opacity="0.4"),
            _step_item("1", "Abra esta página no Safari (não no Chrome para iOS)."),
            _step_item("2", "Toque no ícone de compartilhar — o quadrado com a setinha para cima — na barra inferior."),
            _step_item("3", "Role a lista e toque em \"Adicionar à Tela de Início\"."),
            _step_item("4", "Confirme o nome e toque em \"Adicionar\" no canto superior direito."),
            rx.box(
                rx.hstack(
                    rx.icon(tag="info", size=13, color=S.TEXT_MUTED),
                    rx.text(
                        "No iOS, a instalação é sempre manual — o Safari não exibe um botão automático. "
                        "Isso é uma limitação da Apple, não do sistema.",
                        font_size="12px",
                        color=S.TEXT_MUTED,
                        line_height="1.6",
                    ),
                    spacing="2",
                    align="start",
                ),
                padding="10px 12px",
                border_radius=S.R_CONTROL,
                bg="rgba(255,255,255,0.02)",
                border=f"1px solid {S.BORDER_SUBTLE}",
                margin_top="4px",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        id="btp-ios-steps",
        padding="20px 24px",
        border_radius=S.R_CARD,
        bg=S.BG_ELEVATED,
        border=f"1px solid rgba(160,160,160,0.2)",
        width="100%",
        display="none",  # JS revela a seção correta
    )


def app_mobile_page() -> rx.Component:
    return rx.box(
        # Scripts de controle
        rx.script(_INSTALL_PAGE_SCRIPT),
        rx.script(_PLATFORM_SCRIPT),

        rx.center(
            rx.vstack(

                # ── Hero ────────────────────────────────────────────────────
                rx.vstack(
                    # Banner
                    rx.image(
                        src="/banner.png",
                        max_width=["260px", "320px"],
                        width="100%",
                        object_fit="contain",
                    ),

                    rx.text(
                        "Instale o dashboard como um app nativo no seu celular ou computador — "
                        "sem loja de aplicativos, sem instalação lenta, sem taxas.",
                        font_size=["14px", "15px"],
                        color=S.TEXT_MUTED,
                        text_align="center",
                        max_width="520px",
                        line_height="1.7",
                    ),

                    spacing="5",
                    align="center",
                    padding_bottom="8px",
                ),

                # ── Divisor ─────────────────────────────────────────────────
                rx.divider(
                    border_color=S.BORDER_SUBTLE,
                    width="100%",
                    opacity="0.5",
                ),

                # ── Feature Cards ────────────────────────────────────────────
                rx.grid(
                    _feature_card(
                        "smartphone",
                        "O que é isso?",
                        "Uma PWA (Progressive Web App) é uma tecnologia que permite instalar "
                        "este site como se fosse um aplicativo nativo — com ícone na tela inicial, "
                        "tela cheia e carregamento rápido.",
                        S.COPPER,
                    ),
                    _feature_card(
                        "shield-check",
                        "É seguro?",
                        "Sim. Nenhum dado é salvo localmente sem sua permissão. "
                        "O app continua usando a mesma conexão segura (HTTPS) e "
                        "a mesma autenticação do sistema.",
                        S.PATINA,
                    ),
                    _feature_card(
                        "layout-dashboard",
                        "O que muda?",
                        "O sistema fica igual — mesmos dados, mesmas funções. "
                        "A diferença é que abre direto, sem barra de endereço, "
                        "ocupando a tela toda como um app real.",
                        "#8B9CF4",
                    ),
                    columns=rx.breakpoints(initial="1", sm="1", md="3"),
                    gap="16px",
                    width="100%",
                ),

                # ── Como instalar (seção dinâmica por plataforma) ─────────────
                _install_section_other(),
                _install_section_ios(),

                # ── CTA Instalar (oculto no iOS pelo JS) ─────────────────────
                rx.vstack(
                    rx.button(
                        rx.hstack(
                            rx.icon(tag="download", size=18, color="inherit"),
                            rx.text(
                                "Instalar Agora",
                                font_family=S.FONT_TECH,
                                font_weight="700",
                                font_size="15px",
                                letter_spacing="0.05em",
                            ),
                            spacing="2",
                            align="center",
                        ),
                        id="btp-install-cta",
                        on_click=rx.call_script(
                            "window._btpInstall && window._btpInstall()"
                        ),
                        width=["100%", "320px"],
                        height="52px",
                        border_radius="10px",
                        bg=S.COPPER,
                        color=S.BG_VOID,
                        cursor="pointer",
                        font_weight="700",
                        transition="all 0.2s ease",
                        _hover={
                            "filter": "brightness(1.1)",
                            "transform": "translateY(-1px)",
                            "box_shadow": "0 8px 20px rgba(201, 139, 42, 0.35)",
                        },
                        _active={"transform": "translateY(0px)"},
                        _disabled={
                            "cursor": "default",
                            "filter": "none",
                            "transform": "none",
                            "box_shadow": "none",
                        },
                    ),
                    rx.text(
                        "Requer Google Chrome, Microsoft Edge ou Safari (iOS 16.4+)",
                        id="btp-install-note",
                        font_size="12px",
                        color=S.TEXT_MUTED,
                        text_align="center",
                    ),
                    id="btp-cta-section",
                    display="none",
                    spacing="3",
                    align="center",
                    width="100%",
                ),

                # ── Nota técnica ──────────────────────────────────────────────
                rx.box(
                    rx.hstack(
                        rx.icon(tag="info", size=14, color=S.TEXT_MUTED),
                        rx.text(
                            "Esta é uma instalação PWA (Nível 1). O app requer conexão com a internet "
                            "para funcionar, pois os dados são processados em tempo real no servidor.",
                            font_size="12px",
                            color=S.TEXT_MUTED,
                            line_height="1.6",
                        ),
                        spacing="2",
                        align="start",
                    ),
                    padding="14px 16px",
                    border_radius=S.R_CONTROL,
                    bg="rgba(255,255,255,0.02)",
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    width="100%",
                ),

                spacing="6",
                width="100%",
                max_width="760px",
                align="center",
                padding=["20px 16px", "32px 24px", "48px 0"],
            ),
            width="100%",
            min_height="100vh",
            align_items="start",
            padding_top=["24px", "40px"],
        ),

        width="100%",
        min_height="100vh",
        bg=S.BG_VOID,
    )
