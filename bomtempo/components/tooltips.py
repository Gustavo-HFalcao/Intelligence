"""
Premium tooltip system for BomTempo dashboard.

Técnica para gráficos Recharts:
    rx.recharts.graphing_tooltip(
        content=rx.Var.create(JS_IIFE_STRING, _var_is_string=False)
    )

Para elementos HTML (Gantt, KPI cards):
    rx.hover_card.root / trigger / content

Regras JS (ES5 puro, sem arrow functions, const/let, template literals,
optional chaining). Aspas duplas em todos os valores de string JS.
style= sempre objeto JS {}, nunca string CSS.

Exports públicos (constantes pré-instanciadas):
    TOOLTIP_MONEY
    TOOLTIP_SPI
    TOOLTIP_PIE
    TOOLTIP_GENERIC
    TOOLTIP_PCT_SCURVE     -- previsto / realizado (%) com delta
    TOOLTIP_PCT_DAILY      -- meta / realizado por dia com eficiência
    TOOLTIP_PCT_DISC       -- previsto_pct / realizado_pct (disciplinas) com mini-bar
    TOOLTIP_PCT_GENERIC    -- genérico sem label map
    gantt_hover_content()  -- hover card Reflex para o Gantt HTML
"""
import reflex as rx


# ── Design tokens ──────────────────────────────────────────────────────────────

_BG      = "#141414"
_BORDER  = "rgba(255,255,255,0.10)"
_DIVIDER = "rgba(255,255,255,0.07)"
_ROW_SEP = "rgba(255,255,255,0.04)"
_AMBER   = "#c98b2a"
_GREEN   = "#4ead78"
_RED     = "#e05a5a"
_BLUE    = "#5282dc"
_TEXT    = "#f0ede6"
_MUTED   = "#7a7870"

_HOVER_CARD_STYLE = {
    "background":   _BG,
    "border":       f"1px solid {_BORDER}",
    "borderRadius": "12px",
    "padding":      "14px 16px",
    "minWidth":     "260px",
    "maxWidth":     "320px",
    "boxShadow":    "0 8px 32px rgba(0,0,0,0.6)",
    "fontFamily":   "-apple-system, BlinkMacSystemFont, 'Inter', sans-serif",
    "fontSize":     "13px",
    "color":        _TEXT,
    "zIndex":       "9999",
}

# Cursor styles for Recharts
_CURSOR_AREA  = {"strokeWidth": 1, "fill": "rgba(201,139,42,0.06)"}
_CURSOR_LINE  = {"strokeWidth": 1, "fill": "rgba(82,130,220,0.04)"}

# ── Shared JS fragments ────────────────────────────────────────────────────────
# _JS_CARD_STYLE_FN built dynamically — dynamic left-border from first series color.

_JS_CARD_STYLE_FN = (
    "function(accentColor) {"
    "return {"
    "background:\"rgba(18,18,18,0.96)\","
    "border:\"1px solid rgba(255,255,255,0.10)\","
    "borderLeft:\"3px solid \" + (accentColor || \"#c98b2a\"),"
    "borderRadius:\"12px\","
    "padding:\"0\","
    "minWidth:\"220px\","
    "maxWidth:\"320px\","
    "boxShadow:\"0 12px 40px rgba(0,0,0,0.7)\","
    "fontFamily:\"-apple-system,BlinkMacSystemFont,sans-serif\","
    "fontSize:\"13px\","
    "color:\"#F0EDE6\","
    "pointerEvents:\"none\","
    "backdropFilter:\"blur(10px)\","
    "WebkitBackdropFilter:\"blur(10px)\","
    "overflow:\"hidden\""
    "};"
    "}"
)

# Zone styles — padding separated per zone
_JS_ZONE_HEADER = (
    "{"
    "padding:\"12px 14px 10px\","
    "borderBottom:\"1px solid rgba(255,255,255,0.06)\","
    "display:\"flex\",alignItems:\"center\",gap:\"8px\""
    "}"
)

_JS_ZONE_BODY = (
    "{"
    "padding:\"10px 14px\""
    "}"
)

_JS_ZONE_FOOTER = (
    "{"
    "padding:\"8px 14px 12px\","
    "borderTop:\"1px solid rgba(255,255,255,0.06)\","
    "background:\"rgba(255,255,255,0.02)\""
    "}"
)

# Row separator (applied from 2nd row onward via borderTop)
_JS_ROW_STYLE = (
    "{"
    "display:\"flex\",justifyContent:\"space-between\",alignItems:\"center\","
    "gap:\"16px\",padding:\"5px 0\","
    "borderTop:\"1px solid rgba(255,255,255,0.04)\""
    "}"
)

# First row in body zone — no top border
_JS_ROW_FIRST_STYLE = (
    "{"
    "display:\"flex\",justifyContent:\"space-between\",alignItems:\"center\","
    "gap:\"16px\",padding:\"5px 0\""
    "}"
)

# Dot style helper (inlined in JS as function call)
_JS_DOT_FN = (
    "function(color) {"
    "return React.createElement(\"div\",{"
    "style:{width:\"7px\",height:\"7px\",borderRadius:\"50%\","
    "background:color||\"#c98b2a\",flexShrink:\"0\","
    "boxShadow:\"0 0 0 2px rgba(255,255,255,0.08)\"}"
    "});"
    "}"
)

# ── Shared preamble for every IIFE ─────────────────────────────────────────────
_JS_PREAMBLE = (
    "var React = { createElement: (typeof jsx !== \"undefined\") ? jsx"
    " : (window.React ? window.React.createElement : function(){return null;}) };\n"
    "var _cardStyle = " + _JS_CARD_STYLE_FN + ";\n"
    "var _dot = " + _JS_DOT_FN + ";\n"
)


# ── TOOLTIP_MONEY ──────────────────────────────────────────────────────────────

def tooltip_money(
    label_subtitle: str = "Valores Financeiros",
    icon: str = "[obra]",
    currency: str = "R$",
) -> rx.Component:
    """
    Tooltip premium para gráficos monetários.
    Formata valores >= 1M como '3,2M', >= 1k como '450k'.
    Exibe percentual relativo ao total como badge âmbar separado.
    """
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  var CURRENCY = \"""" + currency + """\";
  var SUBTITLE = \"""" + label_subtitle + """\";
  var LABELS = {
    "valor":"Valor",
    "previsto":"Planejado",
    "realizado":"Realizado",
    "executado":"Executado",
    "previsto_acum":"Planejado Acum.",
    "executado_acum":"Realizado Acum.",
    "total_contratado":"Contratado",
    "total_realizado":"Realizado",
    "cumulative_planned":"Previsto Acum.",
    "cumulative_actual":"Realizado Acum.",
    "total":"Total",
    "meta":"Meta"
  };

  var fmtLabel = function(k) {
    return k.replace(/_/g, " ").replace(/\\b\\w/g, function(c) { return c.toUpperCase(); });
  };

  var fmt = function(v) {
    var n = parseFloat(v);
    if (isNaN(n)) return String(v);
    if (n >= 1000000) return CURRENCY + "\u00a0" + (n/1000000).toFixed(1).replace(".",",") + "M";
    if (n >= 1000)    return CURRENCY + "\u00a0" + (n/1000).toFixed(1).replace(".",",") + "k";
    return CURRENCY + "\u00a0" + n.toFixed(0);
  };

  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    var label   = props.label;
    if (!active || !payload || !payload.length) return null;

    var accentColor = payload[0] ? (payload[0].color || payload[0].fill || "#c98b2a") : "#c98b2a";

    var header = React.createElement("div", {style:""" + _JS_ZONE_HEADER + """},
      React.createElement("div", null,
        React.createElement("div", {style:{fontSize:"13px",fontWeight:"600",color:"#F0EDE6",letterSpacing:"-0.01em"}}, String(label != null ? label : "")),
        React.createElement("div", {style:{fontSize:"11px",fontWeight:"400",color:"#5A5852",letterSpacing:"0.02em",textTransform:"uppercase",marginTop:"2px"}}, SUBTITLE)
      )
    );

    // Compute total for percentage
    var total = 0;
    for (var k = 0; k < payload.length; k++) {
      var nv = parseFloat(payload[k].value);
      if (!isNaN(nv) && nv > 0) total += nv;
    }

    var rows = [];
    for (var i = 0; i < payload.length; i++) {
      var p = payload[i];
      var rawKey = p.dataKey || p.name || "";
      var name = LABELS[rawKey] || fmtLabel(rawKey);
      var numVal = parseFloat(p.value);
      var rowStyle = i === 0 ? """ + _JS_ROW_FIRST_STYLE + """ : """ + _JS_ROW_STYLE + """;

      var pctBadge = null;
      if (total > 0 && !isNaN(numVal) && numVal > 0) {
        var pctNum = Math.round(numVal / total * 100);
        pctBadge = React.createElement("span", {
          style:{
            padding:"2px 7px 3px",
            borderRadius:"4px",
            fontSize:"11px",
            fontWeight:"600",
            letterSpacing:"0.01em",
            background:"rgba(251,191,36,0.12)",
            color:"#FBBF24",
            marginLeft:"6px",
            display:"inline-block"
          }
        }, pctNum + "%");
      }

      rows.push(React.createElement("div", {key:i, style:rowStyle},
        React.createElement("div", {style:{display:"flex",alignItems:"center",gap:"8px"}},
          _dot(p.color||p.fill||"#c98b2a"),
          React.createElement("span", {style:{color:"#7A7870",fontSize:"12px",fontWeight:"400"}}, name)
        ),
        React.createElement("div", {style:{display:"flex",alignItems:"center"}},
          React.createElement("span", {style:{color:"#F0EDE6",fontSize:"13px",fontWeight:"600",fontVariantNumeric:"tabular-nums"}},
            fmt(p.value)
          ),
          pctBadge
        )
      ));
    }

    var bodyEl = React.createElement("div", {style:""" + _JS_ZONE_BODY + """}, rows);

    return React.createElement("div", {style:_cardStyle(accentColor)}, header, bodyEl);
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_AREA,
    )


# ── TOOLTIP_PCT (base) ─────────────────────────────────────────────────────────

def tooltip_pct(
    label_map: dict | None = None,
    title: str = "",
    icon: str = "[up]",
) -> rx.Component:
    """Tooltip base para percentuais — sem delta extra (para uso genérico)."""
    map_js = (
        "{"
        + ", ".join('"' + k + '":"' + v + '"' for k, v in (label_map or {}).items())
        + "}"
    )
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  var LABELS = """ + map_js + """;
  var TITLE  = \"""" + title + """\";
  var ICON   = \"""" + icon + """\";

  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    var label   = props.label;
    if (!active || !payload || !payload.length) return null;

    var accentColor = payload[0] ? (payload[0].color || payload[0].fill || "#c98b2a") : "#c98b2a";

    var headerInner = React.createElement("div", null,
      React.createElement("div", {style:{fontSize:"13px",fontWeight:"600",color:"#F0EDE6",letterSpacing:"-0.01em"}}, String(label != null ? label : ""))
    );
    if (TITLE) {
      headerInner = React.createElement("div", null,
        React.createElement("div", {style:{fontSize:"13px",fontWeight:"600",color:"#F0EDE6",letterSpacing:"-0.01em"}}, String(label != null ? label : "")),
        React.createElement("div", {style:{fontSize:"11px",fontWeight:"400",color:"#5A5852",letterSpacing:"0.02em",textTransform:"uppercase",marginTop:"2px"}}, TITLE)
      );
    }
    var header = React.createElement("div", {style:""" + _JS_ZONE_HEADER + """}, headerInner);

    var rows = [];
    for (var i = 0; i < payload.length; i++) {
      var p    = payload[i];
      var name = LABELS[p.dataKey] || LABELS[p.name] || p.name;
      var v    = parseFloat(p.value);
      var fmt  = isNaN(v) ? String(p.value) : v.toFixed(1) + "%";
      var rowStyle = i === 0 ? """ + _JS_ROW_FIRST_STYLE + """ : """ + _JS_ROW_STYLE + """;
      rows.push(React.createElement("div", {key:i, style:rowStyle},
        React.createElement("div", {style:{display:"flex",alignItems:"center",gap:"8px"}},
          _dot(p.color||p.fill||"#c98b2a"),
          React.createElement("span", {style:{color:"#7A7870",fontSize:"12px",fontWeight:"400"}}, name)
        ),
        React.createElement("span", {style:{color:"#F0EDE6",fontSize:"13px",fontWeight:"600",fontVariantNumeric:"tabular-nums"}}, fmt)
      ));
    }

    var bodyEl = React.createElement("div", {style:""" + _JS_ZONE_BODY + """}, rows);

    return React.createElement("div", {style:_cardStyle(accentColor)}, header, bodyEl);
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_AREA,
    )


# ── TOOLTIP_PCT_SCURVE (especializado — com delta previsto vs realizado) ────────

def tooltip_pct_scurve() -> rx.Component:
    """Tooltip para Curva S: mostra previsto, realizado e delta colorido."""
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  var LABELS = {"previsto":"Planejado","realizado":"Realizado"};
  var TITLE  = "Curva S \u2014 Avan\u00e7o F\u00edsico";

  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    var label   = props.label;
    if (!active || !payload || !payload.length) return null;

    var accentColor = "#2a9d8f";

    var labelStr = (label != null && !isNaN(parseInt(label, 10)))
      ? "Sem.\u00a0" + label
      : String(label != null ? label : "");

    var header = React.createElement("div", {style:""" + _JS_ZONE_HEADER + """},
      React.createElement("div", null,
        React.createElement("div", {style:{fontSize:"13px",fontWeight:"600",color:"#F0EDE6",letterSpacing:"-0.01em"}}, labelStr),
        React.createElement("div", {style:{fontSize:"11px",fontWeight:"400",color:"#5A5852",letterSpacing:"0.02em",textTransform:"uppercase",marginTop:"2px"}}, TITLE)
      )
    );

    var rows = [];
    var prevVal = null, realVal = null;
    for (var i = 0; i < payload.length; i++) {
      var p    = payload[i];
      var name = LABELS[p.dataKey] || LABELS[p.name] || p.name;
      var v    = parseFloat(p.value);
      var fmt  = isNaN(v) ? String(p.value) : v.toFixed(1) + "%";
      if (p.dataKey === "previsto") prevVal = v;
      if (p.dataKey === "realizado") realVal = v;
      var rowStyle = i === 0 ? """ + _JS_ROW_FIRST_STYLE + """ : """ + _JS_ROW_STYLE + """;
      rows.push(React.createElement("div", {key:i, style:rowStyle},
        React.createElement("div", {style:{display:"flex",alignItems:"center",gap:"8px"}},
          _dot(p.color||p.fill||"#c98b2a"),
          React.createElement("span", {style:{color:"#7A7870",fontSize:"12px",fontWeight:"400"}}, name)
        ),
        React.createElement("span", {style:{color:"#F0EDE6",fontSize:"13px",fontWeight:"600",fontVariantNumeric:"tabular-nums"}}, fmt)
      ));
    }

    var bodyEl = React.createElement("div", {style:""" + _JS_ZONE_BODY + """}, rows);

    // Delta section in footer zone
    var deltaEl = null;
    if (prevVal !== null && realVal !== null && !isNaN(prevVal) && !isNaN(realVal)) {
      var delta = realVal - prevVal;
      var deltaColor  = delta >= 0 ? "#4ADE80" : "#F87171";
      var deltaSign   = delta >= 0 ? "+" : "";
      var deltaLabel  = delta >= 0 ? " \u25b2 Adiantado" : " \u25bc Atrasado";
      var deltaFmt    = deltaSign + delta.toFixed(1) + "%" + deltaLabel;
      var deltaBadgeBg = delta >= 0 ? "rgba(74,222,128,0.12)" : "rgba(248,113,113,0.12)";
      deltaEl = React.createElement("div", {style:""" + _JS_ZONE_FOOTER + """},
        React.createElement("div", {style:{display:"flex",justifyContent:"space-between",alignItems:"center"}},
          React.createElement("span", {style:{fontSize:"11px",fontWeight:"400",color:"#5A5852",letterSpacing:"0.02em",textTransform:"uppercase"}}, "Delta"),
          React.createElement("span", {style:{
            padding:"2px 7px 3px",
            borderRadius:"4px",
            fontSize:"11px",
            fontWeight:"600",
            letterSpacing:"0.01em",
            background:deltaBadgeBg,
            color:deltaColor
          }}, deltaFmt)
        )
      );
    }

    return React.createElement("div", {style:_cardStyle(accentColor)}, header, bodyEl, deltaEl);
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_AREA,
    )


# ── TOOLTIP_PCT_DAILY (especializado — com eficiência meta vs realizado) ────────

def tooltip_pct_daily() -> rx.Component:
    """Tooltip produtividade diária: meta/realizado + eficiência colorida."""
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  var LABELS = {"meta":"Meta/dia","realizado":"Realizado/dia"};
  var TITLE  = "Produtividade Di\u00e1ria";

  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    var label   = props.label;
    if (!active || !payload || !payload.length) return null;

    var accentColor = "#e89845";

    var header = React.createElement("div", {style:""" + _JS_ZONE_HEADER + """},
      React.createElement("div", null,
        React.createElement("div", {style:{fontSize:"13px",fontWeight:"600",color:"#F0EDE6",letterSpacing:"-0.01em"}}, String(label != null ? label : "")),
        React.createElement("div", {style:{fontSize:"11px",fontWeight:"400",color:"#5A5852",letterSpacing:"0.02em",textTransform:"uppercase",marginTop:"2px"}}, TITLE)
      )
    );

    var metaVal = null, realVal = null;
    var rows = [];
    for (var i = 0; i < payload.length; i++) {
      var p    = payload[i];
      var name = LABELS[p.dataKey] || LABELS[p.name] || p.name;
      var v    = parseFloat(p.value);
      var fmt  = isNaN(v) ? String(p.value) : v.toFixed(2) + "%";
      if (p.dataKey === "meta")      metaVal = v;
      if (p.dataKey === "realizado") realVal = v;
      var rowStyle = i === 0 ? """ + _JS_ROW_FIRST_STYLE + """ : """ + _JS_ROW_STYLE + """;
      rows.push(React.createElement("div", {key:i, style:rowStyle},
        React.createElement("div", {style:{display:"flex",alignItems:"center",gap:"8px"}},
          _dot(p.color||p.fill||"#e89845"),
          React.createElement("span", {style:{color:"#7A7870",fontSize:"12px",fontWeight:"400"}}, name)
        ),
        React.createElement("span", {style:{color:"#F0EDE6",fontSize:"13px",fontWeight:"600",fontVariantNumeric:"tabular-nums"}}, fmt)
      ));
    }

    var bodyEl = React.createElement("div", {style:""" + _JS_ZONE_BODY + """}, rows);

    // Efficiency ratio in footer zone
    var effEl = null;
    if (metaVal !== null && realVal !== null && !isNaN(metaVal) && metaVal > 0) {
      var eff = (realVal / metaVal) * 100;
      var effColor = eff >= 100 ? "#4ADE80" : (eff >= 80 ? "#FBBF24" : "#F87171");
      var effBadgeBg = eff >= 100 ? "rgba(74,222,128,0.12)" : (eff >= 80 ? "rgba(251,191,36,0.12)" : "rgba(248,113,113,0.12)");
      var effLabel = eff >= 100 ? "\u2713 Meta atingida" : (eff >= 80 ? "\u25cf Abaixo da meta" : "\u25bc Cr\u00edtico");
      effEl = React.createElement("div", {style:""" + _JS_ZONE_FOOTER + """},
        React.createElement("div", {style:{display:"flex",justifyContent:"space-between",alignItems:"center"}},
          React.createElement("span", {style:{fontSize:"11px",fontWeight:"400",color:"#5A5852",letterSpacing:"0.02em",textTransform:"uppercase"}}, "Efici\u00eancia"),
          React.createElement("span", {style:{
            padding:"2px 7px 3px",
            borderRadius:"4px",
            fontSize:"11px",
            fontWeight:"600",
            letterSpacing:"0.01em",
            background:effBadgeBg,
            color:effColor
          }}, eff.toFixed(0) + "% " + effLabel)
        )
      );
    }

    return React.createElement("div", {style:_cardStyle(accentColor)}, header, bodyEl, effEl);
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_AREA,
    )


# ── TOOLTIP_PCT_DISC (especializado — com mini progress bar visual) ─────────────

def tooltip_pct_disc() -> rx.Component:
    """Tooltip disciplinas: previsto_pct / realizado_pct com mini barra visual."""
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  var LABELS = {"previsto_pct":"Planejado","realizado_pct":"Realizado"};
  var TITLE  = "Disciplinas";

  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    var label   = props.label;
    if (!active || !payload || !payload.length) return null;

    var accentColor = payload[0] ? (payload[0].color || payload[0].fill || "#c98b2a") : "#c98b2a";

    var header = React.createElement("div", {style:""" + _JS_ZONE_HEADER + """},
      React.createElement("div", null,
        React.createElement("div", {style:{fontSize:"13px",fontWeight:"600",color:"#F0EDE6",letterSpacing:"-0.01em",maxWidth:"200px",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}, String(label != null ? label : "")),
        React.createElement("div", {style:{fontSize:"11px",fontWeight:"400",color:"#5A5852",letterSpacing:"0.02em",textTransform:"uppercase",marginTop:"2px"}}, TITLE)
      )
    );

    var prevVal = null, realVal = null;
    var prevColor = "#888999";
    var realColor = "#2a9d8f";

    for (var i = 0; i < payload.length; i++) {
      var p = payload[i];
      if (p.dataKey === "previsto_pct")  { prevVal = parseFloat(p.value); prevColor = p.color||p.fill||prevColor; }
      if (p.dataKey === "realizado_pct") { realVal = parseFloat(p.value); realColor = p.color||p.fill||realColor; }
    }

    // Mini double bar visualization in body zone
    // Each bar: label+value on same line (Nível 3 left, Nível 4 right), bar below
    var barEl = null;
    if (prevVal !== null && realVal !== null && !isNaN(prevVal) && !isNaN(realVal)) {
      var maxV = Math.max(prevVal, realVal, 1);
      var prevW = Math.min((prevVal / maxV) * 100, 100).toFixed(0) + "%";
      var realW = Math.min((realVal / maxV) * 100, 100).toFixed(0) + "%";
      var delta = realVal - prevVal;
      var deltaColor = delta >= 0 ? "#4ADE80" : "#F87171";
      var deltaStr = (delta >= 0 ? "+" : "") + delta.toFixed(1) + "%";
      var deltaBadgeBg = delta >= 0 ? "rgba(74,222,128,0.12)" : "rgba(248,113,113,0.12)";

      barEl = React.createElement("div", {style:""" + _JS_ZONE_BODY + """},
        // Planejado row + bar
        React.createElement("div", {style:{marginBottom:"8px"}},
          React.createElement("div", {style:{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"4px"}},
            React.createElement("span", {style:{color:"#7A7870",fontSize:"12px",fontWeight:"400"}}, "Planejado"),
            React.createElement("span", {style:{color:"#F0EDE6",fontSize:"13px",fontWeight:"600",fontVariantNumeric:"tabular-nums"}}, prevVal.toFixed(1) + "%")
          ),
          React.createElement("div", {style:{width:"100%",height:"3px",background:"rgba(255,255,255,0.07)",borderRadius:"2px"}},
            React.createElement("div", {style:{width:prevW,height:"100%",background:prevColor,borderRadius:"2px"}})
          )
        ),
        // Realizado row + bar
        React.createElement("div", null,
          React.createElement("div", {style:{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"4px"}},
            React.createElement("span", {style:{color:"#7A7870",fontSize:"12px",fontWeight:"400"}}, "Realizado"),
            React.createElement("span", {style:{color:"#F0EDE6",fontSize:"13px",fontWeight:"600",fontVariantNumeric:"tabular-nums"}}, realVal.toFixed(1) + "%")
          ),
          React.createElement("div", {style:{width:"100%",height:"3px",background:"rgba(255,255,255,0.07)",borderRadius:"2px"}},
            React.createElement("div", {style:{width:realW,height:"100%",background:realColor,borderRadius:"2px"}})
          )
        )
      );
    }

    var deltaFooter = null;
    if (prevVal !== null && realVal !== null && !isNaN(prevVal) && !isNaN(realVal)) {
      var delta2 = realVal - prevVal;
      var deltaColor2 = delta2 >= 0 ? "#4ADE80" : "#F87171";
      var deltaStr2 = (delta2 >= 0 ? "+" : "") + delta2.toFixed(1) + "%";
      var deltaBadgeBg2 = delta2 >= 0 ? "rgba(74,222,128,0.12)" : "rgba(248,113,113,0.12)";
      deltaFooter = React.createElement("div", {style:""" + _JS_ZONE_FOOTER + """},
        React.createElement("div", {style:{display:"flex",justifyContent:"space-between",alignItems:"center"}},
          React.createElement("span", {style:{fontSize:"11px",fontWeight:"400",color:"#5A5852",letterSpacing:"0.02em",textTransform:"uppercase"}}, "Delta"),
          React.createElement("span", {style:{
            padding:"2px 7px 3px",
            borderRadius:"4px",
            fontSize:"11px",
            fontWeight:"600",
            letterSpacing:"0.01em",
            background:deltaBadgeBg2,
            color:deltaColor2
          }}, deltaStr2)
        )
      );
    }

    return React.createElement("div", {style:_cardStyle(accentColor)}, header, barEl, deltaFooter);
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_AREA,
    )


# ── TOOLTIP_SPI ────────────────────────────────────────────────────────────────

def tooltip_spi() -> rx.Component:
    """Tooltip premium para gráfico SPI — valor + interpretação + escala visual."""
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    var label   = props.label;
    if (!active || !payload || !payload.length) return null;

    var spiVal = null;
    var rows = [];
    for (var i = 0; i < payload.length; i++) {
      var p = payload[i];
      if (p.dataKey === "baseline") {
        rows.push(React.createElement("div", {key:i, style:""" + _JS_ROW_FIRST_STYLE + """},
          React.createElement("span", {style:{color:"#7A7870",fontSize:"12px",fontWeight:"400"}}, "Base"),
          React.createElement("span", {style:{color:"#F0EDE6",fontSize:"13px",fontWeight:"600",fontVariantNumeric:"tabular-nums"}}, "1,00")
        ));
      } else {
        var v = parseFloat(p.value);
        spiVal = v;
        var interp = "";
        var interpColor = "#7A7870";
        var interpBadgeBg = "rgba(255,255,255,0.06)";
        if (!isNaN(v)) {
          if (v >= 1.05) { interp = "\u25b2 Adiantado"; interpColor = "#4ADE80"; interpBadgeBg = "rgba(74,222,128,0.12)"; }
          else if (v >= 0.95) { interp = "\u25cf No prazo"; interpColor = "#FBBF24"; interpBadgeBg = "rgba(251,191,36,0.12)"; }
          else { interp = "\u25bc Atrasado"; interpColor = "#F87171"; interpBadgeBg = "rgba(248,113,113,0.12)"; }
        }
        var rowStyle = rows.length === 0 ? """ + _JS_ROW_FIRST_STYLE + """ : """ + _JS_ROW_STYLE + """;
        rows.push(React.createElement("div", {key:i, style:rowStyle},
          React.createElement("span", {style:{color:"#7A7870",fontSize:"12px",fontWeight:"400"}}, "SPI"),
          React.createElement("div", {style:{display:"flex",alignItems:"center",gap:"6px"}},
            React.createElement("span", {style:{color:"#F0EDE6",fontSize:"13px",fontWeight:"600",fontVariantNumeric:"tabular-nums"}},
              isNaN(v) ? "\u2014" : v.toFixed(2)
            ),
            interp ? React.createElement("span", {style:{
              padding:"2px 7px 3px",
              borderRadius:"4px",
              fontSize:"11px",
              fontWeight:"600",
              letterSpacing:"0.01em",
              background:interpBadgeBg,
              color:interpColor
            }}, interp) : null
          )
        ));
      }
    }

    var bodyEl = React.createElement("div", {style:""" + _JS_ZONE_BODY + """}, rows);

    // SPI scale bar 0.5→1.5 with tick markers
    var scaleEl = null;
    if (spiVal !== null && !isNaN(spiVal)) {
      var pct = Math.max(0, Math.min(1, (spiVal - 0.5) / 1.0)) * 100;
      var markerColor = spiVal >= 1.05 ? "#4ADE80" : (spiVal >= 0.95 ? "#FBBF24" : "#F87171");
      scaleEl = React.createElement("div", {style:""" + _JS_ZONE_FOOTER + """},
        React.createElement("div", {style:{display:"flex",justifyContent:"space-between",marginBottom:"5px"}},
          React.createElement("span", {style:{color:"#5A5852",fontSize:"9px"}}, "0.5"),
          React.createElement("span", {style:{color:"#5A5852",fontSize:"9px",textTransform:"uppercase",letterSpacing:"0.06em"}}, "Escala SPI"),
          React.createElement("span", {style:{color:"#5A5852",fontSize:"9px"}}, "1.5")
        ),
        React.createElement("div", {style:{position:"relative",width:"100%",height:"4px",borderRadius:"2px",background:"linear-gradient(to right, #e05a5a 0%, #e05a5a 35%, #c98b2a 45%, #c98b2a 55%, #4ead78 65%, #4ead78 100%)"}},
          React.createElement("div", {style:{position:"absolute",left:"0%",top:"-2px",width:"1px",height:"8px",background:"rgba(255,255,255,0.2)"}}),
          React.createElement("div", {style:{position:"absolute",left:"50%",top:"-2px",width:"1px",height:"8px",background:"rgba(255,255,255,0.2)"}}),
          React.createElement("div", {style:{position:"absolute",left:"100%",top:"-2px",width:"1px",height:"8px",background:"rgba(255,255,255,0.2)"}}),
          React.createElement("div", {style:{
            position:"absolute",
            left:pct + "%",
            top:"-4px",
            transform:"translateX(-50%)",
            width:"12px",
            height:"12px",
            borderRadius:"50%",
            background:markerColor,
            border:"2px solid #141414",
            boxShadow:"0 0 6px " + markerColor
          }})
        )
      );
    }

    var header = React.createElement("div", {style:""" + _JS_ZONE_HEADER + """},
      React.createElement("span", {style:{fontSize:"14px",color:"#60A5FA",fontWeight:"700",letterSpacing:"-0.01em"}}, "SPI"),
      React.createElement("div", null,
        React.createElement("div", {style:{fontSize:"13px",fontWeight:"600",color:"#F0EDE6",letterSpacing:"-0.01em"}}, String(label != null ? label : "")),
        React.createElement("div", {style:{fontSize:"11px",fontWeight:"400",color:"#5A5852",letterSpacing:"0.02em",textTransform:"uppercase",marginTop:"2px"}}, "Schedule Performance Index")
      )
    );

    return React.createElement("div", {style:_cardStyle("#5282dc")}, header, bodyEl, scaleEl);
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_LINE,
    )


# ── TOOLTIP_PIE ────────────────────────────────────────────────────────────────

def tooltip_pie() -> rx.Component:
    """Tooltip premium para pie/donut charts. Mostra nome, valor, percentual e barra visual."""
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    if (!active || !payload || !payload.length) return null;
    var item = payload[0];
    if (!item) return null;

    var name  = item.name || (item.payload && item.payload.name) || "";
    var value = item.value != null ? item.value : "";
    var raw   = item.payload ? item.payload : {};
    var pct   = raw.percent != null ? raw.percent : (item.percent != null ? item.percent : null);
    var color = raw.fill || item.fill || item.color || "#c98b2a";
    var pctVal = pct != null ? parseFloat(pct) * 100 : null;
    var pctFmt = pctVal !== null ? pctVal.toFixed(1) + "%" : "";

    // Progress bar for participation
    var barEl = pctVal !== null ? React.createElement("div", {style:{marginTop:"6px"}},
      React.createElement("div", {style:{width:"100%",height:"3px",background:"rgba(255,255,255,0.07)",borderRadius:"2px",overflow:"hidden"}},
        React.createElement("div", {style:{width:Math.min(pctVal, 100).toFixed(0) + "%",height:"100%",background:color,borderRadius:"2px"}})
      )
    ) : null;

    var smallCard = {
      background:"rgba(18,18,18,0.96)",
      border:"1px solid rgba(255,255,255,0.10)",
      borderLeft:"3px solid " + color,
      borderRadius:"12px",
      padding:"0",
      minWidth:"180px",
      maxWidth:"260px",
      boxShadow:"0 12px 40px rgba(0,0,0,0.7)",
      fontFamily:"-apple-system,BlinkMacSystemFont,sans-serif",
      fontSize:"13px",
      color:"#F0EDE6",
      pointerEvents:"none",
      backdropFilter:"blur(10px)",
      WebkitBackdropFilter:"blur(10px)",
      overflow:"hidden"
    };

    return React.createElement("div", {style:smallCard},
      React.createElement("div", {style:""" + _JS_ZONE_HEADER + """},
        React.createElement("div", {style:{width:"7px",height:"7px",borderRadius:"50%",background:color,flexShrink:"0",boxShadow:"0 0 0 2px rgba(255,255,255,0.08)"}}),
        React.createElement("span", {style:{fontSize:"13px",fontWeight:"600",color:"#F0EDE6",letterSpacing:"-0.01em"}}, name)
      ),
      React.createElement("div", {style:""" + _JS_ZONE_BODY + """},
        React.createElement("div", {style:{fontSize:"26px",fontWeight:"700",color:color,textAlign:"center",margin:"4px 0",fontVariantNumeric:"tabular-nums"}},
          String(value)
        ),
        pctFmt ? React.createElement("div", null,
          React.createElement("div", {style:{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"5px 0"}},
            React.createElement("span", {style:{color:"#7A7870",fontSize:"12px",fontWeight:"400"}}, "Participa\u00e7\u00e3o"),
            React.createElement("span", {style:{color:color,fontSize:"13px",fontWeight:"600",fontVariantNumeric:"tabular-nums"}}, pctFmt)
          ),
          barEl
        ) : null
      )
    );
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=False,
    )


# ── TOOLTIP_GENERIC ────────────────────────────────────────────────────────────

def tooltip_generic(icon: str = "[lista]") -> rx.Component:
    """
    Tooltip genérico para contagens e valores não monetários / não percentuais.
    Exibe nome + valor bruto de cada série + indicador de tendência se múltiplas séries.
    """
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  var ICON = \"""" + icon + """\";
  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    var label   = props.label;
    if (!active || !payload || !payload.length) return null;

    var accentColor = payload[0] ? (payload[0].color || payload[0].fill || "#c98b2a") : "#c98b2a";

    var rows = [];
    for (var i = 0; i < payload.length; i++) {
      var p = payload[i];
      var rowStyle = i === 0 ? """ + _JS_ROW_FIRST_STYLE + """ : """ + _JS_ROW_STYLE + """;
      rows.push(React.createElement("div", {key:i, style:rowStyle},
        React.createElement("div", {style:{display:"flex",alignItems:"center",gap:"8px"}},
          _dot(p.color||p.fill||"#c98b2a"),
          React.createElement("span", {style:{color:"#7A7870",fontSize:"12px",fontWeight:"400"}}, p.name)
        ),
        React.createElement("span", {style:{color:"#F0EDE6",fontSize:"13px",fontWeight:"600",fontVariantNumeric:"tabular-nums"}}, String(p.value))
      ));
    }

    var bodyEl = React.createElement("div", {style:""" + _JS_ZONE_BODY + """}, rows);

    // Trend indicator: compare first two series
    var trendEl = null;
    if (payload.length >= 2) {
      var v0 = parseFloat(payload[0].value);
      var v1 = parseFloat(payload[1].value);
      if (!isNaN(v0) && !isNaN(v1) && v1 !== 0) {
        var diff = v0 - v1;
        var trendDir   = diff >= 0 ? "\u25b2" : "\u25bc";
        var trendColor = diff >= 0 ? "#4ADE80" : "#F87171";
        var trendBadgeBg = diff >= 0 ? "rgba(74,222,128,0.12)" : "rgba(248,113,113,0.12)";
        var trendPct   = Math.abs(diff / v1 * 100).toFixed(0) + "%";
        trendEl = React.createElement("div", {style:""" + _JS_ZONE_FOOTER + """},
          React.createElement("div", {style:{display:"flex",justifyContent:"space-between",alignItems:"center"}},
            React.createElement("span", {style:{fontSize:"11px",fontWeight:"400",color:"#5A5852",letterSpacing:"0.02em",textTransform:"uppercase"}}, "Varia\u00e7\u00e3o"),
            React.createElement("span", {style:{
              padding:"2px 7px 3px",
              borderRadius:"4px",
              fontSize:"11px",
              fontWeight:"600",
              letterSpacing:"0.01em",
              background:trendBadgeBg,
              color:trendColor
            }}, trendDir + " " + trendPct)
          )
        );
      }
    }

    var header = React.createElement("div", {style:""" + _JS_ZONE_HEADER + """},
      React.createElement("div", {style:{fontSize:"13px",fontWeight:"600",color:"#F0EDE6",letterSpacing:"-0.01em",display:"flex",alignItems:"center",gap:"6px"}},
        React.createElement("span", {style:{fontSize:"14px"}}, ICON),
        React.createElement("span", null, String(label != null ? label : ""))
      )
    );

    return React.createElement("div", {style:_cardStyle(accentColor)}, header, bodyEl, trendEl);
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_AREA,
    )


# ── TOOLTIP_SIGNAL (substitui TOOLTIP_PCT_SCURVE) ─────────────────────────────

def tooltip_signal() -> rx.Component:
    """S-curve tooltip: previsto / realizado (%) com sparkline e delta pp."""
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    var label   = props.label;
    if (!active || !payload || !payload.length) return null;

    var accentColor = "#2a9d8f";

    var labelNum = parseFloat(label);
    var labelStr = !isNaN(labelNum) ? ("Sem. " + label) : String(label != null ? label : "");

    // sparkline bars
    var sparks = [30, 45, 55, 60, 70, 90];
    var sparkBars = [];
    for (var si = 0; si < sparks.length; si++) {
      var sh = Math.round(24 * sparks[si] / 100);
      var sy = 24 - sh;
      sparkBars.push(React.createElement("rect", {
        key: si,
        x: String(si * 8),
        y: String(sy),
        width: "5",
        height: String(sh),
        rx: "2",
        fill: si === sparks.length - 1 ? "#c98b2a" : "rgba(255,255,255,0.15)"
      }));
    }
    var sparkSvg = React.createElement("svg", {width: "48", height: "24"}, sparkBars);

    var header = React.createElement("div", {style: {
      padding: "12px 14px 10px",
      borderBottom: "1px solid rgba(255,255,255,0.06)",
      display: "flex", alignItems: "center", justifyContent: "space-between"
    }},
      React.createElement("div", null,
        React.createElement("div", {style: {fontSize: "13px", fontWeight: "600", color: "#F0EDE6", letterSpacing: "-0.01em"}}, labelStr),
        React.createElement("div", {style: {fontSize: "10px", color: "#5A5852", textTransform: "uppercase", letterSpacing: "0.05em", marginTop: "2px"}}, "curva s")
      ),
      sparkSvg
    );

    var prevVal = null, realVal = null;
    for (var i = 0; i < payload.length; i++) {
      var p = payload[i];
      if (p.dataKey === "previsto")  prevVal = parseFloat(p.value);
      if (p.dataKey === "realizado") realVal = parseFloat(p.value);
    }

    var atrasado = (prevVal !== null && realVal !== null && !isNaN(prevVal) && !isNaN(realVal)) ? (realVal < prevVal) : false;
    var prevColor = "#888999";
    var realColor = atrasado ? "#e05a5a" : "#4ead78";
    var realBg    = atrasado ? "rgba(224,90,90,0.07)" : "rgba(78,173,120,0.07)";
    var realBorder = atrasado ? "1px solid rgba(224,90,90,0.15)" : "1px solid rgba(78,173,120,0.15)";

    var tileStyle = {borderRadius: "6px", padding: "7px 9px", flex: "1"};

    var prevTile = React.createElement("div", {style: Object.assign({}, tileStyle, {background: "rgba(255,255,255,0.03)"})},
      React.createElement("div", {style: {fontSize: "11px", color: "#7A7870", marginBottom: "2px"}}, "Planejado"),
      React.createElement("div", {style: {fontSize: "20px", fontWeight: "500", color: prevColor, lineHeight: "1"}},
        prevVal !== null && !isNaN(prevVal) ? prevVal.toFixed(1) : "--",
        React.createElement("span", {style: {fontSize: "12px", fontWeight: "400", marginLeft: "2px"}}, "%")
      )
    );

    var realTile = React.createElement("div", {style: Object.assign({}, tileStyle, {background: realBg, border: realBorder})},
      React.createElement("div", {style: {fontSize: "11px", color: "#7A7870", marginBottom: "2px"}}, "Realizado"),
      React.createElement("div", {style: {fontSize: "20px", fontWeight: "500", color: realColor, lineHeight: "1"}},
        realVal !== null && !isNaN(realVal) ? realVal.toFixed(1) : "--",
        React.createElement("span", {style: {fontSize: "12px", fontWeight: "400", marginLeft: "2px"}}, "%")
      )
    );

    var progressW = (realVal !== null && !isNaN(realVal)) ? Math.max(0, Math.min(realVal, 100)).toFixed(0) + "%" : "0%";
    var progressBar = React.createElement("div", {style: {marginTop: "8px", height: "3px", background: "rgba(255,255,255,0.07)", borderRadius: "2px", overflow: "hidden"}},
      React.createElement("div", {style: {width: progressW, height: "100%", background: realColor, borderRadius: "2px"}})
    );

    var bodyEl = React.createElement("div", {style: {padding: "10px 14px"}},
      React.createElement("div", {style: {display: "flex", gap: "8px"}}, prevTile, realTile),
      progressBar
    );

    var footerEl = null;
    if (prevVal !== null && realVal !== null && !isNaN(prevVal) && !isNaN(realVal)) {
      var delta = realVal - prevVal;
      var deltaAbs = Math.abs(delta).toFixed(1);
      var deltaColor = delta >= 0 ? "#4ead78" : "#e05a5a";
      var deltaBg    = delta >= 0 ? "rgba(78,173,120,0.12)" : "rgba(224,90,90,0.12)";
      var deltaStr   = delta >= 0 ? ("+" + deltaAbs + "pp \u25b2 adiantado") : ("\u2212" + deltaAbs + "pp \u25bc atrasado");
      footerEl = React.createElement("div", {style: {
        padding: "8px 14px 12px",
        borderTop: "1px solid rgba(255,255,255,0.06)",
        background: "rgba(255,255,255,0.02)",
        display: "flex", justifyContent: "space-between", alignItems: "center"
      }},
        React.createElement("span", {style: {fontSize: "10px", color: "#7A7870", textTransform: "uppercase", letterSpacing: "0.05em"}}, "DELTA"),
        React.createElement("span", {style: {
          padding: "2px 7px 3px", borderRadius: "4px", fontSize: "11px", fontWeight: "600",
          background: deltaBg, color: deltaColor
        }}, deltaStr)
      );
    }

    return React.createElement("div", {style: _cardStyle(accentColor)}, header, bodyEl, footerEl);
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_AREA,
    )


# ── TOOLTIP_SPLIT (previsto × realizado financeiro) ────────────────────────────

def tooltip_split(
    label_subtitle: str = "Valores Financeiros",
    currency: str = "R$",
) -> rx.Component:
    """Tooltip side-by-side previsto × realizado com desvio % e monetário."""
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  var CURRENCY = \"""" + currency + """\";
  var SUBTITLE = \"""" + label_subtitle + """\";

  var fmt = function(v) {
    var n = parseFloat(v);
    if (isNaN(n)) return String(v);
    if (n >= 1000000) return CURRENCY + "\u00a0" + (n/1000000).toFixed(1).replace(".",",") + "M";
    if (n >= 1000)    return CURRENCY + "\u00a0" + (n/1000).toFixed(1).replace(".",",") + "k";
    return CURRENCY + "\u00a0" + n.toFixed(0);
  };

  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    var label   = props.label;
    if (!active || !payload || !payload.length) return null;

    var accentColor = payload[0] ? (payload[0].color || payload[0].fill || "#5282dc") : "#5282dc";

    var header = React.createElement("div", {style: {
      padding: "12px 14px 10px",
      borderBottom: "1px solid rgba(255,255,255,0.06)",
      display: "flex", alignItems: "center", gap: "8px"
    }},
      React.createElement("div", {style: {width: "7px", height: "7px", borderRadius: "50%", background: accentColor, flexShrink: "0", boxShadow: "0 0 0 2px rgba(255,255,255,0.08)"}}),
      React.createElement("div", null,
        React.createElement("div", {style: {fontSize: "13px", fontWeight: "600", color: "#F0EDE6", letterSpacing: "-0.01em"}}, String(label != null ? label : "")),
        React.createElement("div", {style: {fontSize: "11px", color: "#5A5852", textTransform: "uppercase", letterSpacing: "0.02em", marginTop: "2px"}}, SUBTITLE)
      )
    );

    var prevVal = null, realVal = null;
    var prevColor = "#888999", realColor = accentColor;
    for (var i = 0; i < payload.length; i++) {
      var p = payload[i];
      var k = p.dataKey || p.name || "";
      if (k === "previsto" || k === "planejado" || k === "total_contratado" || k === "cumulative_planned" || k === "previsto_acum") {
        prevVal = parseFloat(p.value);
        prevColor = p.color || p.fill || "#888999";
      }
      if (k === "realizado" || k === "executado" || k === "total_realizado" || k === "cumulative_actual" || k === "executado_acum") {
        realVal = parseFloat(p.value);
        realColor = p.color || p.fill || accentColor;
      }
    }

    var hasBoth = (prevVal !== null && realVal !== null && !isNaN(prevVal) && !isNaN(realVal) && prevVal !== 0);

    var desvPct = hasBoth ? ((realVal / prevVal - 1) * 100) : null;
    var desvAbs = hasBoth ? (realVal - prevVal) : null;

    var desvPctEl = null;
    if (desvPct !== null) {
      var dpColor = desvPct >= 0 ? "#4ead78" : "#e05a5a";
      var dpStr   = desvPct >= 0 ? ("\u25b2 +" + Math.abs(desvPct).toFixed(1) + "%") : ("\u25bc \u2212" + Math.abs(desvPct).toFixed(1) + "%");
      desvPctEl = React.createElement("div", {style: {fontSize: "10px", color: dpColor, marginTop: "3px"}}, dpStr);
    }

    var desvAbsEl = null;
    if (desvAbs !== null) {
      var daColor = desvAbs >= 0 ? "#4ead78" : "#e05a5a";
      var daStr   = "\u00b1" + fmt(Math.abs(desvAbs));
      desvAbsEl = React.createElement("div", {style: {fontSize: "10px", color: daColor, marginTop: "3px"}}, daStr);
    }

    var bodyEl;
    if (hasBoth) {
      bodyEl = React.createElement("div", {style: {
        padding: "10px 13px",
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0"
      }},
        React.createElement("div", {style: {borderRight: "1px solid rgba(255,255,255,0.05)", padding: "10px 13px 10px 0"}},
          React.createElement("div", {style: {fontSize: "11px", color: "#7A7870", marginBottom: "2px"}}, "Previsto"),
          React.createElement("div", {style: {fontSize: "16px", fontWeight: "500", color: prevColor}}, fmt(prevVal)),
          desvPctEl
        ),
        React.createElement("div", {style: {padding: "10px 0 10px 13px"}},
          React.createElement("div", {style: {fontSize: "11px", color: "#7A7870", marginBottom: "2px"}}, "Realizado"),
          React.createElement("div", {style: {fontSize: "16px", fontWeight: "500", color: realColor}}, fmt(realVal)),
          desvAbsEl
        )
      );
    } else {
      var rows = [];
      for (var j = 0; j < payload.length; j++) {
        var pj = payload[j];
        var rowStyle = j === 0 ? """ + _JS_ROW_FIRST_STYLE + """ : """ + _JS_ROW_STYLE + """;
        rows.push(React.createElement("div", {key: j, style: rowStyle},
          React.createElement("div", {style: {display: "flex", alignItems: "center", gap: "8px"}},
            React.createElement("div", {style: {width: "7px", height: "7px", borderRadius: "50%", background: pj.color || pj.fill || "#c98b2a", flexShrink: "0"}}),
            React.createElement("span", {style: {color: "#7A7870", fontSize: "12px"}}, pj.name || pj.dataKey)
          ),
          React.createElement("span", {style: {color: "#F0EDE6", fontSize: "13px", fontWeight: "600", fontVariantNumeric: "tabular-nums"}}, fmt(pj.value))
        ));
      }
      bodyEl = React.createElement("div", {style: {padding: "10px 14px"}}, rows);
    }

    var progressW = (hasBoth && prevVal > 0) ? (Math.max(0, Math.min(realVal / prevVal * 100, 150)).toFixed(0) + "%") : "0%";
    var progColor = (desvPct !== null && desvPct >= 0) ? "#4ead78" : realColor;

    var footerEl = React.createElement("div", {style: {
      padding: "8px 14px 12px",
      borderTop: "1px solid rgba(255,255,255,0.06)",
      background: "rgba(255,255,255,0.02)"
    }},
      React.createElement("div", {style: {height: "3px", background: "rgba(255,255,255,0.07)", borderRadius: "2px", overflow: "hidden", marginBottom: "6px"}},
        React.createElement("div", {style: {width: progressW, height: "100%", background: progColor, borderRadius: "2px"}})
      ),
      React.createElement("div", {style: {display: "flex", justifyContent: "space-between", alignItems: "center"}},
        React.createElement("span", {style: {fontSize: "10px", color: "#7A7870"}},
          hasBoth ? (Math.min(realVal / prevVal * 100, 999).toFixed(0) + "% executado") : ""
        ),
        desvAbs !== null ? React.createElement("span", {style: {fontSize: "10px", color: (desvAbs >= 0 ? "#4ead78" : "#e05a5a")}},
          fmt(Math.abs(desvAbs))
        ) : null
      )
    );

    return React.createElement("div", {style: Object.assign({}, _cardStyle(accentColor), {borderTop: "2px solid " + accentColor})}, header, bodyEl, footerEl);
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_AREA,
    )


# ── TOOLTIP_PILL (substitui TOOLTIP_PCT_DAILY) ────────────────────────────────

def tooltip_pill(label_subtitle: str = "Produtividade Diária") -> rx.Component:
    """Tooltip compacto com mini-barras horizontais e badge de eficiência."""
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  var SUBTITLE = \"""" + label_subtitle + """\";

  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    var label   = props.label;
    if (!active || !payload || !payload.length) return null;

    var accentColor = "#c98b2a";
    var cardBase = _cardStyle(accentColor);
    var cardStyle = Object.assign({}, cardBase, {minWidth: "200px", maxWidth: "260px", borderRadius: "8px"});

    var header = React.createElement("div", {style: {
      padding: "8px 11px",
      borderBottom: "1px solid rgba(255,255,255,0.05)",
      display: "flex", alignItems: "center", gap: "6px"
    }},
      React.createElement("span", {style: {fontSize: "12px", fontWeight: "500", color: "#F0EDE6"}}, String(label != null ? label : "")),
      React.createElement("span", {style: {fontSize: "9px", textTransform: "uppercase", color: "#7A7870", letterSpacing: "0.05em", marginLeft: "auto"}}, SUBTITLE)
    );

    var maxVal = 0;
    for (var mi = 0; mi < payload.length; mi++) {
      var mv = parseFloat(payload[mi].value);
      if (!isNaN(mv) && mv > maxVal) maxVal = mv;
    }
    maxVal = maxVal || 1;

    var rows = [];
    for (var i = 0; i < payload.length; i++) {
      var p = payload[i];
      var pColor = p.color || p.fill || "#c98b2a";
      var pVal   = parseFloat(p.value);
      var pName  = p.name || p.dataKey || "";
      var barW   = (!isNaN(pVal) ? Math.min(pVal / maxVal * 100, 100) : 0).toFixed(0) + "%";
      rows.push(React.createElement("div", {key: i, style: {display: "flex", alignItems: "center", gap: "6px"}},
        React.createElement("div", {style: {width: "7px", height: "7px", borderRadius: "50%", background: pColor, flexShrink: "0", boxShadow: "0 0 0 2px rgba(255,255,255,0.08)"}}),
        React.createElement("span", {style: {fontSize: "11px", color: "#7A7870", flex: "1"}}, pName),
        React.createElement("div", {style: {flex: "1", height: "3px", background: "rgba(255,255,255,0.07)", borderRadius: "2px", overflow: "hidden"}},
          React.createElement("div", {style: {width: barW, height: "100%", background: pColor, borderRadius: "2px"}})
        ),
        React.createElement("span", {style: {fontSize: "12px", fontWeight: "500", color: "#F0EDE6", fontVariantNumeric: "tabular-nums", minWidth: "36px", textAlign: "right"}},
          !isNaN(pVal) ? pVal.toFixed(1) + "%" : "--"
        )
      ));
    }

    var bodyEl = React.createElement("div", {style: {padding: "7px 11px", display: "flex", flexDirection: "column", gap: "5px"}}, rows);

    var metaVal = null, realVal2 = null;
    for (var j = 0; j < payload.length; j++) {
      var pj = payload[j];
      if (pj.dataKey === "meta")      metaVal  = parseFloat(pj.value);
      if (pj.dataKey === "realizado") realVal2 = parseFloat(pj.value);
    }

    var footerEl = null;
    if (metaVal !== null && realVal2 !== null && !isNaN(metaVal) && !isNaN(realVal2) && metaVal > 0) {
      var eff = realVal2 / metaVal * 100;
      var effColor, effBg, effStr;
      if (eff >= 100) {
        effColor = "#4ead78"; effBg = "rgba(78,173,120,0.12)"; effStr = eff.toFixed(0) + "% \u2713 meta atingida";
      } else if (eff >= 80) {
        effColor = "#c98b2a"; effBg = "rgba(201,139,42,0.12)"; effStr = eff.toFixed(0) + "% \u25cf abaixo da meta";
      } else {
        effColor = "#e05a5a"; effBg = "rgba(224,90,90,0.12)"; effStr = eff.toFixed(0) + "% \u25bc critico";
      }
      footerEl = React.createElement("div", {style: {
        padding: "6px 11px 8px",
        borderTop: "1px solid rgba(255,255,255,0.05)",
        background: "rgba(255,255,255,0.02)",
        display: "flex", justifyContent: "space-between", alignItems: "center"
      }},
        React.createElement("span", {style: {fontSize: "9px", color: "#7A7870", textTransform: "uppercase", letterSpacing: "0.05em"}}, "EFICIENCIA"),
        React.createElement("span", {style: {
          padding: "2px 7px 3px", borderRadius: "4px", fontSize: "10px", fontWeight: "600",
          background: effBg, color: effColor
        }}, effStr)
      );
    }

    return React.createElement("div", {style: cardStyle}, header, bodyEl, footerEl);
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_AREA,
    )


# ── TOOLTIP_GANTT_RECHARTS ─────────────────────────────────────────────────────

def tooltip_gantt_recharts() -> rx.Component:
    """Tooltip para versões do Gantt baseadas em Recharts (não o hover card HTML)."""
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    if (!active || !payload || !payload.length) return null;

    var raw = payload[0].payload || {};
    var accentColor = raw.color || payload[0].fill || payload[0].color || "#c98b2a";
    var cardStyle = Object.assign({}, _cardStyle(accentColor), {minWidth: "280px", maxWidth: "380px"});

    var nivel = raw.nivel || "macro";
    var badgeColor, badgeBg, badgeLabel;
    if (nivel === "sub")   { badgeColor = "#8B5CF6"; badgeBg = "rgba(139,92,246,0.15)"; badgeLabel = "SUB"; }
    else if (nivel === "micro") { badgeColor = "#2a9d8f"; badgeBg = "rgba(42,157,143,0.15)"; badgeLabel = "MICRO"; }
    else                   { badgeColor = "#c98b2a"; badgeBg = "rgba(201,139,42,0.15)"; badgeLabel = "MACRO"; }

    var badge = React.createElement("span", {style: {
      fontSize: "8px", fontWeight: "500", padding: "1px 5px", borderRadius: "3px",
      letterSpacing: ".04em", background: badgeBg, color: badgeColor, marginLeft: "6px"
    }}, badgeLabel);

    var header = React.createElement("div", {style: {
      padding: "12px 14px 10px", borderBottom: "1px solid rgba(255,255,255,0.06)",
      display: "flex", alignItems: "center", gap: "8px"
    }},
      React.createElement("div", {style: {width: "7px", height: "7px", borderRadius: "50%", background: accentColor, flexShrink: "0", boxShadow: "0 0 0 2px rgba(255,255,255,0.08)"}}),
      React.createElement("div", null,
        React.createElement("div", {style: {fontSize: "12px", fontWeight: "500", color: "#F0EDE6", display: "flex", alignItems: "center"}},
          String(raw.atividade || ""),
          badge
        ),
        React.createElement("div", {style: {fontSize: "10px", color: accentColor, textTransform: "uppercase", letterSpacing: "0.04em", marginTop: "2px"}},
          String(raw.fase_macro || "")
        )
      )
    );

    var pct = raw.conclusao_pct || "0";
    var pctNum = parseFloat(pct);
    var overdue = raw.gantt_overdue === "1";
    var done    = pct === "100";
    var pctColor = done ? "#4ead78" : (overdue ? "#e05a5a" : "#c98b2a");

    var statusColor, statusBg, statusStr;
    if (overdue)     { statusColor = "#e05a5a"; statusBg = "rgba(224,90,90,0.12)"; statusStr = "\u26a0 atrasada"; }
    else if (done)   { statusColor = "#4ead78"; statusBg = "rgba(78,173,120,0.12)"; statusStr = "\u2713 concluida"; }
    else             { statusColor = "#5282dc"; statusBg = "rgba(82,130,220,0.12)"; statusStr = "\u25cf em execucao"; }

    var rows = [
      React.createElement("div", {key: "r", style: """ + _JS_ROW_FIRST_STYLE + """},
        React.createElement("span", {style: {color: "#7A7870", fontSize: "12px"}}, "Responsavel"),
        React.createElement("span", {style: {color: "#F0EDE6", fontSize: "12px", fontWeight: "500"}}, String(raw.responsavel || "—"))
      ),
      React.createElement("div", {key: "p", style: """ + _JS_ROW_STYLE + """},
        React.createElement("span", {style: {color: "#7A7870", fontSize: "12px"}}, "Progresso"),
        React.createElement("span", {style: {color: pctColor, fontSize: "12px", fontWeight: "500", fontVariantNumeric: "tabular-nums"}}, pct + "%")
      )
    ];

    var progressBar = React.createElement("div", {style: {height: "3px", background: "rgba(255,255,255,0.07)", borderRadius: "2px", overflow: "hidden", marginTop: "2px", marginBottom: "4px"}},
      React.createElement("div", {style: {width: Math.min(pctNum || 0, 100).toFixed(0) + "%", height: "100%", background: pctColor, borderRadius: "2px"}})
    );

    var statusRow = React.createElement("div", {key: "s", style: """ + _JS_ROW_STYLE + """},
      React.createElement("span", {style: {color: "#7A7870", fontSize: "12px"}}, "Status"),
      React.createElement("span", {style: {
        padding: "2px 7px 3px", borderRadius: "4px", fontSize: "11px", fontWeight: "600",
        background: statusBg, color: statusColor
      }}, statusStr)
    );

    var bodyChildren = [
      React.createElement("div", {key: "rows", style: {padding: "10px 14px"}}, rows, progressBar, statusRow)
    ];

    if (raw.critico === "1") {
      bodyChildren.push(React.createElement("div", {key: "crit", style: """ + _JS_ROW_STYLE + """},
        React.createElement("span", {style: {color: "#7A7870", fontSize: "12px"}}, "Prioridade"),
        React.createElement("span", {style: {
          padding: "2px 7px 3px", borderRadius: "4px", fontSize: "11px", fontWeight: "600",
          background: "rgba(201,139,42,0.12)", color: "#c98b2a"
        }}, "CRITICO")
      ));
    }

    var sep = React.createElement("div", {style: {height: "1px", background: "rgba(255,255,255,0.06)", margin: "4px 0"}});

    var termColor = overdue ? "#e05a5a" : "#F0EDE6";
    var datas = React.createElement("div", {style: {
      padding: "8px 13px", display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center"
    }},
      React.createElement("div", null,
        React.createElement("div", {style: {fontSize: "9px", color: "#7A7870", textTransform: "uppercase", letterSpacing: "0.05em"}}, "INICIO"),
        React.createElement("div", {style: {fontSize: "12px", fontWeight: "500", fontFamily: "monospace", color: "#F0EDE6"}}, String(raw.inicio_previsto || "—"))
      ),
      React.createElement("div", {style: {width: "1px", height: "24px", background: "rgba(255,255,255,0.07)", margin: "0 auto"}}),
      React.createElement("div", {style: {textAlign: "right"}},
        React.createElement("div", {style: {fontSize: "9px", color: "#7A7870", textTransform: "uppercase", letterSpacing: "0.05em"}}, "TERMINO"),
        React.createElement("div", {style: {fontSize: "12px", fontWeight: "500", fontFamily: "monospace", color: termColor}}, String(raw.termino_previsto || "—"))
      )
    );

    var totalQty = raw.total_qty || "0";
    var footerEl = null;
    if (totalQty !== "0") {
      footerEl = React.createElement("div", {style: {
        padding: "8px 14px 12px", borderTop: "1px solid rgba(255,255,255,0.06)",
        background: "rgba(255,255,255,0.02)",
        display: "flex", justifyContent: "space-between", alignItems: "center"
      }},
        React.createElement("div", null,
          React.createElement("span", {style: {fontSize: "9px", color: "#7A7870"}}, "exec: "),
          React.createElement("span", {style: {fontSize: "11px", fontWeight: "500", fontFamily: "monospace", color: "#F0EDE6"}},
            (raw.exec_qty || "0") + " / " + totalQty + " " + (raw.unidade || "")
          )
        ),
        raw.critico === "1" ? React.createElement("span", {style: {
          padding: "2px 7px 3px", borderRadius: "4px", fontSize: "10px", fontWeight: "600",
          background: "rgba(201,139,42,0.12)", color: "#c98b2a"
        }}, "CRITICO") : null
      );
    }

    return React.createElement("div", {style: cardStyle}, header,
      React.createElement("div", null, bodyChildren),
      sep, datas, footerEl
    );
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_LINE,
    )


# ── TOOLTIP_SPI_RING (substitui TOOLTIP_SPI) ──────────────────────────────────

def tooltip_spi_ring() -> rx.Component:
    """Tooltip SPI com gauge SVG, tendência e escala de gradiente."""
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    var label   = props.label;
    if (!active || !payload || !payload.length) return null;

    var accentColor = "#5282dc";

    var spiVal = null;
    for (var i = 0; i < payload.length; i++) {
      if (payload[i].dataKey !== "baseline") {
        spiVal = parseFloat(payload[i].value);
        break;
      }
    }

    var header = React.createElement("div", {style: {
      padding: "12px 14px 10px", borderBottom: "1px solid rgba(255,255,255,0.06)",
      display: "flex", alignItems: "center", gap: "8px"
    }},
      React.createElement("div", {style: {width: "7px", height: "7px", borderRadius: "50%", background: accentColor, flexShrink: "0", boxShadow: "0 0 0 2px rgba(255,255,255,0.08)"}}),
      React.createElement("div", null,
        React.createElement("div", {style: {fontSize: "13px", fontWeight: "600", color: "#F0EDE6", letterSpacing: "-0.01em"}}, String(label != null ? label : "")),
        React.createElement("div", {style: {fontSize: "11px", color: "#7A7870", marginTop: "2px"}}, "schedule performance index")
      )
    );

    var gaugeColor = (!isNaN(spiVal) && spiVal !== null)
      ? (spiVal >= 1.05 ? "#4ead78" : (spiVal >= 0.95 ? "#c98b2a" : "#e05a5a"))
      : "#7A7870";
    var arcLen = 163;
    var offset = (!isNaN(spiVal) && spiVal !== null)
      ? (arcLen - Math.max(0, Math.min((spiVal - 0.5) / 1.0, 1)) * arcLen)
      : arcLen;
    var spiText = (spiVal !== null && !isNaN(spiVal)) ? spiVal.toFixed(2) : "--";

    var gaugeSvg = React.createElement("svg", {width: "64", height: "64"},
      React.createElement("circle", {cx: "32", cy: "32", r: "26", fill: "none", stroke: "rgba(255,255,255,0.06)", strokeWidth: "6"}),
      React.createElement("circle", {cx: "32", cy: "32", r: "26", fill: "none",
        stroke: gaugeColor, strokeWidth: "6", strokeLinecap: "round",
        transform: "rotate(-90 32 32)",
        strokeDasharray: String(arcLen),
        strokeDashoffset: String(offset)
      }),
      React.createElement("text", {x: "32", y: "36", textAnchor: "middle",
        fill: "#F0EDE6", fontSize: "13", fontWeight: "500", fontFamily: "monospace"
      }, spiText)
    );

    var diff = (spiVal !== null && !isNaN(spiVal)) ? ((spiVal - 1.0) * 100) : 0;
    var trendColor = diff >= 0 ? "#4ead78" : "#e05a5a";
    var trendStr   = diff >= 0
      ? ("\u25b2 +" + diff.toFixed(0) + "%")
      : ("\u25bc \u2212" + Math.abs(diff).toFixed(0) + "%");

    var spiColor = gaugeColor;

    var rightRows = [
      React.createElement("div", {key: "spi", style: {display: "flex", justifyContent: "space-between", alignItems: "center", padding: "3px 0"}},
        React.createElement("span", {style: {color: "#7A7870", fontSize: "12px"}}, "SPI"),
        React.createElement("span", {style: {color: spiColor, fontSize: "13px", fontWeight: "600", fontVariantNumeric: "tabular-nums"}}, spiText)
      ),
      React.createElement("div", {key: "base", style: {display: "flex", justifyContent: "space-between", alignItems: "center", padding: "3px 0"}},
        React.createElement("span", {style: {color: "#7A7870", fontSize: "12px"}}, "Base"),
        React.createElement("span", {style: {color: "#F0EDE6", fontSize: "13px", fontWeight: "600"}}, "1.00")
      ),
      React.createElement("div", {key: "trend", style: {display: "flex", justifyContent: "space-between", alignItems: "center", padding: "3px 0"}},
        React.createElement("span", {style: {color: "#7A7870", fontSize: "12px"}}, "Tendencia"),
        React.createElement("span", {style: {color: trendColor, fontSize: "12px", fontWeight: "600"}}, trendStr)
      )
    ];

    var bodyEl = React.createElement("div", {style: {padding: "10px 14px"}},
      React.createElement("div", {style: {display: "flex", alignItems: "center", gap: "14px"}},
        gaugeSvg,
        React.createElement("div", {style: {flex: "1", display: "flex", flexDirection: "column", gap: "3px"}}, rightRows)
      )
    );

    var interpStr, interpColor2, interpBg;
    if (spiVal === null || isNaN(spiVal)) {
      interpStr = "sem dados"; interpColor2 = "#7A7870"; interpBg = "rgba(255,255,255,0.06)";
    } else if (spiVal >= 1.05) {
      interpStr = "\u25b2 Adiantado"; interpColor2 = "#4ead78"; interpBg = "rgba(78,173,120,0.12)";
    } else if (spiVal >= 0.95) {
      interpStr = "\u25cf No prazo"; interpColor2 = "#c98b2a"; interpBg = "rgba(201,139,42,0.12)";
    } else {
      interpStr = "\u25bc Atrasado"; interpColor2 = "#e05a5a"; interpBg = "rgba(224,90,90,0.12)";
    }

    var footerEl = React.createElement("div", {style: {
      padding: "8px 14px 12px", borderTop: "1px solid rgba(255,255,255,0.06)",
      background: "rgba(255,255,255,0.02)",
      display: "flex", justifyContent: "space-between", alignItems: "center"
    }},
      React.createElement("div", {style: {display: "flex", alignItems: "center", gap: "6px"}},
        React.createElement("div", {style: {
          width: "60px", height: "3px", borderRadius: "2px",
          background: "linear-gradient(90deg,#e05a5a 0%,#c98b2a 40%,#4ead78 75%)"
        }}),
        React.createElement("span", {style: {fontSize: "9px", color: "#7A7870"}}, "escala SPI")
      ),
      React.createElement("span", {style: {
        padding: "2px 7px 3px", borderRadius: "4px", fontSize: "11px", fontWeight: "600",
        background: interpBg, color: interpColor2
      }}, interpStr)
    );

    return React.createElement("div", {style: _cardStyle(accentColor)}, header, bodyEl, footerEl);
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_LINE,
    )


# ── TOOLTIP_STACK_DISC (substitui TOOLTIP_PCT_DISC) ───────────────────────────

def tooltip_stack_disc() -> rx.Component:
    """Tooltip disciplinas: barras empilhadas com delta e acum."""
    js = """
(function() {
  """ + _JS_PREAMBLE + """
  var LABELS = {
    "previsto_pct": "Planejado",
    "realizado_pct": "Realizado",
    "acum_previsto": "Acum. prev.",
    "cumulative_planned": "Acum. plan.",
    "cumulative_actual": "Acum. real."
  };
  var getName = function(p) {
    return LABELS[p.dataKey] || LABELS[p.name] || p.name || p.dataKey || "";
  };

  return function(props) {
    var active  = props.active;
    var payload = props.payload;
    var label   = props.label;
    if (!active || !payload || !payload.length) return null;

    var accentColor = payload[0] ? (payload[0].color || payload[0].fill || "#c98b2a") : "#c98b2a";

    var header = React.createElement("div", {style: {
      padding: "12px 14px 10px", borderBottom: "1px solid rgba(255,255,255,0.06)",
      display: "flex", alignItems: "center", gap: "8px"
    }},
      React.createElement("div", null,
        React.createElement("div", {style: {
          fontSize: "13px", fontWeight: "500", color: "#F0EDE6",
          maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap"
        }}, String(label != null ? label : "")),
        React.createElement("div", {style: {
          fontSize: "11px", color: "#5A5852", textTransform: "uppercase",
          letterSpacing: "0.02em", marginTop: "2px"
        }}, "disciplinas \u00b7 % avan\u00e7o")
      )
    );

    var maxVal = 0;
    for (var k = 0; k < payload.length; k++) {
      var vk = parseFloat(payload[k].value);
      if (!isNaN(vk) && vk > maxVal) maxVal = vk;
    }
    maxVal = maxVal || 1;

    var seriesEls = [];
    for (var i = 0; i < payload.length; i++) {
      var p = payload[i];
      var pColor = p.color || p.fill || "#c98b2a";
      var val = parseFloat(p.value);
      var barW = (!isNaN(val) ? Math.min(val / maxVal * 100, 100) : 0).toFixed(0) + "%";
      seriesEls.push(React.createElement("div", {
        key: i,
        style: {marginBottom: i < payload.length - 1 ? "8px" : "0"}
      },
        React.createElement("div", {style: {
          display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px"
        }},
          React.createElement("div", {style: {display: "flex", alignItems: "center", gap: "6px"}},
            React.createElement("div", {style: {width: "7px", height: "7px", borderRadius: "50%", background: pColor, flexShrink: "0", boxShadow: "0 0 0 2px rgba(255,255,255,0.08)"}}),
            React.createElement("span", {style: {fontSize: "12px", color: "#7A7870"}}, getName(p))
          ),
          React.createElement("span", {style: {fontSize: "12px", fontWeight: "500", color: pColor, fontVariantNumeric: "tabular-nums"}},
            !isNaN(val) ? val.toFixed(1) + "%" : "--"
          )
        ),
        React.createElement("div", {style: {height: "3px", background: "rgba(255,255,255,0.07)", borderRadius: "2px", overflow: "hidden"}},
          React.createElement("div", {style: {width: barW, height: "100%", background: pColor, borderRadius: "2px"}})
        )
      ));
    }

    var bodyEl = React.createElement("div", {style: {padding: "10px 14px"}}, seriesEls);

    var prevDisc = null, realDisc = null, acumPrev = null;
    for (var j = 0; j < payload.length; j++) {
      var pj = payload[j];
      if (pj.dataKey === "previsto_pct")  prevDisc = parseFloat(pj.value);
      if (pj.dataKey === "realizado_pct") realDisc = parseFloat(pj.value);
      if (pj.dataKey === "acum_previsto") acumPrev = parseFloat(pj.value);
    }

    var hasDelta = (prevDisc !== null && realDisc !== null && !isNaN(prevDisc) && !isNaN(realDisc));
    if (!hasDelta && acumPrev === null) return React.createElement("div", {style: _cardStyle(accentColor)}, header, bodyEl);

    var footerChildren = [];

    if (acumPrev !== null && !isNaN(acumPrev)) {
      footerChildren.push(React.createElement("div", {key: "acum", style: {
        display: "flex", justifyContent: "space-between", marginBottom: "6px"
      }},
        React.createElement("span", {style: {fontSize: "10px", color: "#7A7870"}}, "Acum. prev."),
        React.createElement("span", {style: {fontSize: "10px", color: "#7A7870", fontVariantNumeric: "tabular-nums"}}, acumPrev.toFixed(1) + "%")
      ));
    }

    if (hasDelta) {
      var delta = realDisc - prevDisc;
      var dColor = delta >= 0 ? "#4ead78" : "#e05a5a";
      var dBg    = delta >= 0 ? "rgba(78,173,120,0.12)" : "rgba(224,90,90,0.12)";
      var dStr   = delta >= 0 ? ("+" + Math.abs(delta).toFixed(1) + "pp \u25b2") : ("\u2212" + Math.abs(delta).toFixed(1) + "pp \u25bc");
      footerChildren.push(React.createElement("div", {key: "delta", style: {
        display: "flex", justifyContent: "space-between", alignItems: "center"
      }},
        React.createElement("span", {style: {fontSize: "10px", color: "#7A7870", textTransform: "uppercase", letterSpacing: "0.04em"}}, "DELTA"),
        React.createElement("span", {style: {
          padding: "2px 7px 3px", borderRadius: "4px", fontSize: "11px", fontWeight: "600",
          background: dBg, color: dColor
        }}, dStr)
      ));
    }

    var footerEl = React.createElement("div", {style: {
      padding: "8px 14px 12px", borderTop: "1px solid rgba(255,255,255,0.06)",
      background: "rgba(255,255,255,0.02)"
    }}, footerChildren);

    return React.createElement("div", {style: _cardStyle(accentColor)}, header, bodyEl, footerEl);
  };
})()
"""
    return rx.recharts.graphing_tooltip(
        special_props=[rx.Var("{content: " + js + "}")],
        wrapper_style={"zIndex": 9999, "outline": "none"},
        allow_escape_view_box={"x": True, "y": True},
        cursor=_CURSOR_AREA,
    )


# ── Module-level pre-instantiated constants ────────────────────────────────────
# Importe as constantes, não as funções, para evitar duplicação no bundle.

TOOLTIP_MONEY       = tooltip_money()
TOOLTIP_SPI         = tooltip_spi()
TOOLTIP_PIE         = tooltip_pie()
TOOLTIP_GENERIC     = tooltip_generic()

TOOLTIP_PCT_SCURVE  = tooltip_pct_scurve()
TOOLTIP_PCT_DAILY   = tooltip_pct_daily()
TOOLTIP_PCT_DISC    = tooltip_pct_disc()
TOOLTIP_PCT_GENERIC = tooltip_pct(icon="[grafico]")

# V2 — novos designs
TOOLTIP_SIGNAL          = tooltip_signal()
TOOLTIP_SPLIT           = tooltip_split()
TOOLTIP_PILL            = tooltip_pill()
TOOLTIP_GANTT_RECHARTS  = tooltip_gantt_recharts()
TOOLTIP_SPI_RING        = tooltip_spi_ring()
TOOLTIP_STACK_DISC      = tooltip_stack_disc()


# ── GANTT hover card (Reflex native — não é Recharts) ─────────────────────────

def _divider() -> rx.Component:
    return rx.box(height="1px", width="100%", background=_DIVIDER, flex_shrink="0")


def _row(label: str, value_component: rx.Component) -> rx.Component:
    return rx.hstack(
        rx.text(label, font_size="11px", color=_MUTED, flex="1"),
        value_component,
        width="100%",
        align="center",
        padding_y="1px",
    )


def gantt_hover_content(item: dict) -> rx.Component:
    """
    Hover card content para uma linha do Gantt.
    Recebe o dict reativo do rx.foreach (gantt_rows).

    Campos usados:
        atividade, fase_macro, responsavel, color,
        conclusao_pct, gantt_overdue, critico, dependencia,
        inicio_previsto, termino_previsto
    """
    status_color = rx.cond(
        item["gantt_overdue"] == "1",
        _RED,
        rx.cond(item["conclusao_pct"] == "100", _GREEN, _BLUE),
    )
    status_label = rx.cond(
        item["gantt_overdue"] == "1",
        "\u26a0 Atrasada",
        rx.cond(item["conclusao_pct"] == "100", "\u2713 Conclu\u00edda", "\u25cf Em execu\u00e7\u00e3o"),
    )
    status_badge_bg = rx.cond(
        item["gantt_overdue"] == "1",
        "rgba(248,113,113,0.12)",
        rx.cond(
            item["conclusao_pct"] == "100",
            "rgba(74,222,128,0.12)",
            "rgba(96,165,250,0.12)",
        ),
    )
    progress_color = rx.cond(
        item["conclusao_pct"] == "100",
        _GREEN,
        rx.cond(item["gantt_overdue"] == "1", _RED, _BLUE),
    )
    termino_color = rx.cond(item["gantt_overdue"] == "1", _RED, _TEXT)

    # Nivel badge color and label
    nivel_color = rx.cond(
        item["nivel"] == "sub", "#8B5CF6",
        rx.cond(item["nivel"] == "micro", "#2A9D8F", "#C98B2A"),
    )
    nivel_label = rx.cond(
        item["nivel"] == "sub", "SUB-ATIVIDADE",
        rx.cond(item["nivel"] == "micro", "MICRO", "MACRO"),
    )

    return rx.hover_card.content(
        rx.vstack(
            # ── Header ────────────────────────────────────────────
            rx.hstack(
                rx.text("\u26a1", font_size="20px", flex_shrink="0", line_height="1"),
                rx.vstack(
                    rx.hstack(
                        rx.text(
                            item["atividade"],
                            font_size="13px",
                            font_weight="600",
                            color=_TEXT,
                            white_space="normal",
                            overflow="hidden",
                            max_width="260px",
                            letter_spacing="-0.01em",
                        ),
                        rx.box(
                            rx.text(nivel_label, font_size="7px", font_weight="800", color=nivel_color, letter_spacing="0.06em"),
                            padding="1px 4px", border_radius="2px",
                            border=rx.cond(item["nivel"] == "sub", "1px solid rgba(139,92,246,0.5)", rx.cond(item["nivel"] == "micro", "1px solid rgba(42,157,143,0.5)", "1px solid rgba(201,139,42,0.5)")),
                            bg=rx.cond(item["nivel"] == "sub", "rgba(139,92,246,0.08)", rx.cond(item["nivel"] == "micro", "rgba(42,157,143,0.08)", "rgba(201,139,42,0.08)")),
                            flex_shrink="0",
                        ),
                        spacing="2", align="center",
                    ),
                    rx.text(
                        item["fase_macro"],
                        font_size="11px",
                        font_weight="400",
                        color=item["color"],
                        letter_spacing="0.02em",
                        text_transform="uppercase",
                    ),
                    spacing="0",
                    align_items="flex-start",
                ),
                spacing="2",
                align="center",
                width="100%",
            ),
            _divider(),
            # ── Responsável ───────────────────────────────────────
            _row("Responsável", rx.text(item["responsavel"], font_size="12px", color=_TEXT)),
            # ── Progresso + barra ─────────────────────────────────
            _row(
                "Progresso",
                rx.text(
                    item["conclusao_pct"] + "%",
                    font_size="13px",
                    font_weight="600",
                    color=progress_color,
                    font_variant_numeric="tabular-nums",
                ),
            ),
            rx.box(
                rx.box(
                    width=item["conclusao_pct"] + "%",
                    height="100%",
                    background=progress_color,
                    border_radius="2px",
                ),
                width="100%",
                height="3px",
                background="rgba(255,255,255,0.07)",
                border_radius="2px",
                overflow="hidden",
            ),
            # ── Status badge ──────────────────────────────────────
            _row(
                "Status",
                rx.box(
                    rx.text(
                        status_label,
                        font_size="11px",
                        font_weight="600",
                        color=status_color,
                        letter_spacing="0.01em",
                    ),
                    padding="2px 7px 3px",
                    border_radius="4px",
                    background=status_badge_bg,
                ),
            ),
            # ── Crítico badge (condicional) ───────────────────────
            rx.cond(
                item["critico"] == "1",
                _row(
                    "Prioridade",
                    rx.box(
                        rx.text(
                            "CR\u00cdTICO",
                            font_size="9px",
                            font_weight="800",
                            color="#FBBF24",
                            letter_spacing="0.06em",
                        ),
                        padding="2px 7px 3px",
                        border_radius="4px",
                        border="1px solid rgba(251,191,36,0.3)",
                        background="rgba(251,191,36,0.10)",
                    ),
                ),
            ),
            _divider(),
            # ── Datas — layout flexbox com divisor central ─────────
            rx.hstack(
                rx.vstack(
                    rx.text(
                        "IN\u00cdCIO",
                        font_size="9px",
                        color=_MUTED,
                        font_weight="400",
                        letter_spacing="0.08em",
                        text_transform="uppercase",
                    ),
                    rx.text(
                        item["inicio_previsto"],
                        font_size="13px",
                        color=_TEXT,
                        font_family="monospace",
                        font_weight="600",
                        letter_spacing="-0.01em",
                    ),
                    spacing="0",
                    align_items="flex-start",
                ),
                rx.box(width="1px", height="28px", background="rgba(255,255,255,0.08)"),
                rx.vstack(
                    rx.text(
                        "T\u00c9RMINO",
                        font_size="9px",
                        color=_MUTED,
                        font_weight="400",
                        letter_spacing="0.08em",
                        text_transform="uppercase",
                    ),
                    rx.text(
                        item["termino_previsto"],
                        font_size="13px",
                        color=termino_color,
                        font_family="monospace",
                        font_weight="600",
                        letter_spacing="-0.01em",
                    ),
                    spacing="0",
                    align_items="flex-start",
                ),
                width="100%",
                justify="between",
                align="center",
            ),
            # ── Qtd executada (quando rastreada) ─────────────────
            rx.cond(
                item["total_qty"] != "0",
                _row(
                    "Executado",
                    rx.text(
                        item["exec_qty"] + " / " + item["total_qty"] + " " + item["unidade"],
                        font_size="12px",
                        color=_TEXT,
                        font_family="monospace",
                        font_weight="600",
                    ),
                ),
            ),
            # ── Predecessoras (condicional) ───────────────────────
            rx.cond(
                item["dependencia"] != "",
                _row("Predecessora", rx.text(item["dependencia"], font_size="11px", color=_MUTED)),
            ),
            spacing="2",
            align_items="flex-start",
            width="100%",
        ),
        style={**_HOVER_CARD_STYLE, "minWidth": "320px", "maxWidth": "420px"},
        side="bottom",
        side_offset=8,
        avoid_collisions=True,
    )
