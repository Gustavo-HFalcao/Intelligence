"""
Chat Bubble Component — Premium Glassmorphic
User: right-aligned, copper/14 transparent bg, white text, copper border, sharp top-right corner.
AI:   left-aligned, white/4 glassmorphic card, subtle white border, copper sparkles avatar.
"""

import reflex as rx

from bomtempo.core import styles as S


# ── Chart.js renderer ────────────────────────────────────────────────────────
# Abordagem: o canvas é renderizado pelo React normalmente.
# O JSON do gráfico é passado via window.__btpCharts[id] antes do React montar.
# Um MutationObserver global inicializa cada canvas novo que apareça com data-chart-id.

CHART_INIT_SCRIPT = """
window.__btpCharts = window.__btpCharts || {};

function __btpBuildChart(canvas, def) {
  if (canvas._btpChart) return;
  var COPPER='#C98B2A', COPPER_A='rgba(201,139,42,0.18)';
  var COLORS=['#C98B2A','#4ECDC4','#45B7D1','#96CEB4','#FFEAA7','#DDA0DD','#98D8C8','#F7DC6F'];
  var labels = def.data.map(function(d){ return d.name; });
  var values = def.data.map(function(d){ return Number(d.value)||0; });
  var prefix = def.value_prefix||'', title=def.title||'', type=def.chart_type||'bar';
  function fmt(v){
    if(prefix==='R$') return 'R$ '+v.toLocaleString('pt-BR',{minimumFractionDigits:0,maximumFractionDigits:0});
    if(prefix==='%') return v.toFixed(1)+'%';
    return v.toLocaleString('pt-BR');
  }
  var dataset, options;
  if(type==='pie'){
    dataset={data:values,backgroundColor:COLORS,borderColor:'rgba(0,0,0,0.3)',borderWidth:1};
    options={responsive:true,maintainAspectRatio:false,plugins:{
      legend:{position:'right',labels:{color:'rgba(255,255,255,0.75)',font:{size:11},boxWidth:14}},
      title:title?{display:true,text:title,color:'rgba(255,255,255,0.9)',font:{size:13,weight:'bold'},padding:{bottom:10}}:{display:false},
      tooltip:{callbacks:{label:function(c){return ' '+c.label+': '+fmt(c.parsed);}}}
    }};
  } else {
    var isArea=type==='area';
    dataset={label:title||'Valor',data:values,
      backgroundColor:isArea?COPPER_A:COLORS.slice(0,values.length),
      borderColor:isArea?COPPER:COLORS.slice(0,values.length),
      borderWidth:isArea?2:0,fill:isArea,tension:isArea?0.35:0,
      pointBackgroundColor:isArea?COPPER:undefined,
      pointRadius:isArea?4:0,borderRadius:isArea?0:6};
    options={responsive:true,maintainAspectRatio:false,plugins:{
      legend:{display:false},
      title:title?{display:true,text:title,color:'rgba(255,255,255,0.9)',font:{size:13,weight:'bold'},padding:{bottom:10}}:{display:false},
      tooltip:{callbacks:{label:function(c){return ' '+fmt(c.parsed.y);}}},
      datalabels:{
        display:true,
        anchor:'end',align:'top',
        color:'rgba(255,255,255,0.85)',
        font:{size:10,weight:'600'},
        formatter:function(v){ return fmt(v); },
        clip:false
      }
    },scales:{
      x:{ticks:{color:'rgba(255,255,255,0.55)',font:{size:11},maxRotation:35},grid:{color:'rgba(255,255,255,0.04)'}},
      y:{ticks:{color:'rgba(255,255,255,0.55)',font:{size:11},
           callback:function(v){return prefix==='R$'?'R$ '+v.toLocaleString('pt-BR'):v.toLocaleString('pt-BR');}},
         grid:{color:'rgba(255,255,255,0.07)'}}
    }};
  }
  canvas._btpChart = new Chart(canvas, {
    type: type==='area'?'line':type,
    data:{labels:labels,datasets:[dataset]},
    options:options
  });
}

function __btpInitCanvas(canvas) {
  var id = canvas.getAttribute('data-chart-id');
  if (!id || canvas._btpChart) return;
  var def = window.__btpCharts[id];
  if (!def || !def.__chart__ || !def.data || !def.data.length) return;
  if (window.Chart) { __btpBuildChart(canvas, def); return; }
  if (!window._btpChartJsLoading) {
    window._btpChartJsLoading = true;
    var s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';
    s.onload = function() {
      // Carrega datalabels plugin depois do Chart.js
      var dl = document.createElement('script');
      dl.src = 'https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js';
      dl.onload = function() {
        Chart.register(ChartDataLabels);
        window._btpChartJsLoading = false;
        document.querySelectorAll('canvas[data-chart-id]').forEach(__btpInitCanvas);
      };
      document.head.appendChild(dl);
    };
    document.head.appendChild(s);
  } else {
    var t = setInterval(function(){ if(window.Chart){ clearInterval(t); __btpBuildChart(canvas, def); }}, 80);
  }
}

// MutationObserver: inicializa qualquer canvas novo com data-chart-id
if (!window._btpObserver) {
  window._btpObserver = new MutationObserver(function(mutations) {
    mutations.forEach(function(m) {
      m.addedNodes.forEach(function(node) {
        if (node.nodeType !== 1) return;
        if (node.tagName === 'CANVAS' && node.getAttribute('data-chart-id')) {
          setTimeout(function(){ __btpInitCanvas(node); }, 50);
        }
        node.querySelectorAll && node.querySelectorAll('canvas[data-chart-id]').forEach(function(c){
          setTimeout(function(){ __btpInitCanvas(c); }, 50);
        });
      });
    });
  });
  window._btpObserver.observe(document.body, {childList:true, subtree:true});
}
"""


def chart_init_script() -> rx.Component:
    """Injeta o script global de inicialização de gráficos uma vez no layout."""
    return rx.script(CHART_INIT_SCRIPT)


def _chart_bubble(chart_json_var, chart_id_var) -> rx.Component:
    """
    Renderiza um canvas placeholder. O React monta o canvas com data-chart-id;
    o MutationObserver detecta e chama __btpInitCanvas com o JSON já em window.__btpCharts.
    """
    return rx.cond(
        chart_json_var != "",
        rx.box(
            rx.el.canvas(
                data_chart_id=chart_id_var,
                style={"width": "100%", "height": "100%", "display": "block"},
            ),
            style={
                "position": "relative",
                "width": "100%",
                "height": "300px",
                "marginTop": "14px",
                "borderRadius": "10px",
                "background": "rgba(0,0,0,0.25)",
                "border": f"1px solid {S.BORDER_ACCENT}",
                "padding": "12px",
                "boxSizing": "border-box",
            },
        ),
        rx.fragment(),
    )


# ── Message Bubble ────────────────────────────────────────────────────────────

def message_bubble(message: dict) -> rx.Component:
    """
    Premium glassmorphic chat bubble with hover lift.
    Skips system messages silently.
    Renders inline Chart.js chart when message["chart_json"] is set.
    """
    is_user = message["role"] == "user"

    return rx.cond(
        message["role"] == "system",
        rx.fragment(),
        rx.box(
            rx.hstack(
                # ── AI Avatar (left) ──────────────────────────────────────
                rx.cond(
                    ~is_user,
                    rx.center(
                        rx.icon(tag="sparkles", size=14, color="#0A1F1A"),
                        width="34px",
                        height="34px",
                        border_radius="50%",
                        bg=S.COPPER,
                        flex_shrink="0",
                        margin_top="4px",
                        box_shadow="0 0 16px rgba(201, 139, 42, 0.5)",
                    ),
                ),
                # ── Message Content ───────────────────────────────────────
                rx.box(
                    rx.markdown(
                        message["content"],
                        color="white",
                        component_map={
                            "h2": lambda *children, **props: rx.heading(
                                *children,
                                size="4",
                                color=S.COPPER,
                                font_family=S.FONT_TECH,
                                margin_top="1em",
                                margin_bottom="0.3em",
                                **props,
                            ),
                            "h3": lambda *children, **props: rx.heading(
                                *children,
                                size="3",
                                color=S.COPPER_LIGHT,
                                font_family=S.FONT_TECH,
                                margin_top="0.8em",
                                margin_bottom="0.3em",
                                **props,
                            ),
                            "p": lambda *children, **props: rx.el.p(
                                *children,
                                style={
                                    "color": "white",
                                    "lineHeight": "1.7",
                                    "marginBottom": "6px",
                                    "wordSpacing": "0.02em",
                                },
                            ),
                            "strong": lambda *children, **props: rx.el.strong(
                                *children,
                                style={
                                    "color": S.COPPER_LIGHT,
                                    "fontWeight": "700",
                                },
                                **props,
                            ),
                            "em": lambda *children, **props: rx.el.em(
                                *children,
                                style={
                                    "color": S.TEXT_MUTED,
                                    "fontStyle": "normal",
                                    "fontSize": "0.92em",
                                },
                                **props,
                            ),
                            "li": lambda *children, **props: rx.el.li(
                                *children,
                                style={
                                    "color": "white",
                                    "marginBottom": "4px",
                                    "lineHeight": "1.6",
                                },
                                **props,
                            ),
                            "code": lambda *children, **props: rx.el.code(
                                *children,
                                style={
                                    "background": "rgba(255,255,255,0.08)",
                                    "color": S.COPPER_LIGHT,
                                    "padding": "1px 5px",
                                    "borderRadius": "3px",
                                    "fontFamily": S.FONT_MONO,
                                    "fontSize": "0.85em",
                                },
                                **props,
                            ),
                            "table": lambda *children, **props: rx.el.table(
                                *children,
                                style={
                                    "width": "100%",
                                    "borderCollapse": "collapse",
                                    "marginTop": "10px",
                                    "marginBottom": "10px",
                                    "fontSize": "12px",
                                    "border": f"1px solid {S.BORDER_ACCENT}",
                                },
                                **props,
                            ),
                            "thead": lambda *children, **props: rx.el.thead(
                                *children,
                                style={"backgroundColor": "rgba(10,31,26,0.8)"},
                                **props,
                            ),
                            "tbody": lambda *children, **props: rx.el.tbody(
                                *children, **props
                            ),
                            "tr": lambda *children, **props: rx.el.tr(
                                *children,
                                style={"borderBottom": f"1px solid {S.BORDER_SUBTLE}"},
                                **props,
                            ),
                            "th": lambda *children, **props: rx.el.th(
                                *children,
                                style={
                                    "padding": "8px 12px",
                                    "textAlign": "left",
                                    "fontWeight": "700",
                                    "color": S.COPPER_LIGHT,
                                    "borderRight": f"1px solid {S.BORDER_SUBTLE}",
                                    "fontSize": "11px",
                                    "letterSpacing": "0.04em",
                                    "backgroundColor": "rgba(10,31,26,0.9)",
                                },
                                **props,
                            ),
                            "td": lambda *children, **props: rx.el.td(
                                *children,
                                style={
                                    "padding": "7px 12px",
                                    "color": "white",
                                    "borderRight": f"1px solid {S.BORDER_SUBTLE}",
                                    "fontSize": "12px",
                                    "lineHeight": "1.5",
                                },
                                **props,
                            ),
                        },
                    ),
                    # Gráfico inline (só em mensagens do assistente com chart_json)
                    rx.cond(
                        ~is_user,
                        _chart_bubble(message["chart_json"], message["chart_id"]),
                    ),
                    bg=rx.cond(
                        is_user,
                        "rgba(201, 139, 42, 0.14)",
                        "rgba(255, 255, 255, 0.04)",
                    ),
                    backdrop_filter=rx.cond(~is_user, "blur(12px)", "none"),
                    padding="14px 18px",
                    border_radius="18px",
                    border_top_right_radius=rx.cond(is_user, "4px", "18px"),
                    border_top_left_radius=rx.cond(~is_user, "4px", "18px"),
                    border=rx.cond(
                        is_user,
                        "1px solid rgba(201, 139, 42, 0.30)",
                        "1px solid rgba(255, 255, 255, 0.07)",
                    ),
                    box_shadow=rx.cond(
                        ~is_user,
                        "0 4px 24px rgba(0, 0, 0, 0.3)",
                        "0 4px 16px rgba(201, 139, 42, 0.1)",
                    ),
                    max_width="80%",
                    font_weight=rx.cond(is_user, "500", "400"),
                    overflow_x="auto",
                    class_name=rx.cond(is_user, "chat-bubble-user", "chat-bubble-ai"),
                ),
                # ── User Avatar (right) ───────────────────────────────────
                rx.cond(
                    is_user,
                    rx.center(
                        rx.icon(tag="user", size=14, color=S.COPPER),
                        width="34px",
                        height="34px",
                        border_radius="50%",
                        bg="rgba(201, 139, 42, 0.15)",
                        border="1px solid rgba(201, 139, 42, 0.35)",
                        flex_shrink="0",
                        margin_top="4px",
                    ),
                ),
                align="start",
                justify=rx.cond(is_user, "end", "start"),
                spacing="3",
                width="100%",
                flex_direction=rx.cond(is_user, "row-reverse", "row"),
            ),
            width="100%",
            padding_y="6px",
        ),
    )
