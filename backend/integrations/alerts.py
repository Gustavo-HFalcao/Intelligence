"""
Alert engine — detecta e persiste alertas operacionais por inversor.

Tipos:
  offline           — sem sync há > 30 min
  low_generation    — gerando < 60% do previsto (irradiância válida)
  string_imbalance  — desvio de string > 15% (strings com > 10% da potência máxima)
  high_temp         — temperatura > 75°C por 15+ min
  pr_degradation    — PR médio 7 dias < 75%

Deduplicação: nunca abre alert duplicado enquanto há um aberto do mesmo tipo.
Auto-resolve: fecha alert aberto quando condição não é mais verdadeira.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from backend.integrations.supabase import sb_insert, sb_select, sb_update

# Alert types that auto-create a maintenance task when opened
_AUTO_MAINTENANCE: Dict[str, str] = {
    "offline":      "high",
    "high_temp":    "critical",
    "pr_degradation": "medium",
}


# ── Severity map ──────────────────────────────────────────────────────────────

_SEVERITY: Dict[str, str] = {
    "offline":           "critical",
    "low_generation":    "warning",
    "string_imbalance":  "warning",
    "high_temp":         "critical",
    "pr_degradation":    "warning",
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _open_alert(inverter_id: str, client_id: str, alert_type: str,
                title: str, detail: str, value: float, threshold: float,
                meta: dict = None) -> None:
    existing = sb_select(
        "inverter_alerts",
        filters={"inverter_id": inverter_id, "alert_type": alert_type, "status": "open"},
        limit=1,
    ) or []
    if existing:
        return  # deduplicate

    alert_row = sb_insert("inverter_alerts", {
        "inverter_id": inverter_id,
        "client_id":   client_id,
        "alert_type":  alert_type,
        "severity":    _SEVERITY.get(alert_type, "warning"),
        "status":      "open",
        "title":       title,
        "detail":      detail,
        "value":       value,
        "threshold":   threshold,
        "opened_at":   _now().isoformat(),
        "meta":        meta or {},
    })

    # Auto-create maintenance task for critical/high alerts (deduped by alert_type + open status)
    if alert_type in _AUTO_MAINTENANCE and alert_row:
        try:
            existing_task = sb_select(
                "inverter_maintenance",
                filters={"inverter_id": inverter_id, "alert_type": alert_type},
                raw_filters={"status": "in.(pending,in_progress)"},
                limit=1,
            ) or []
            if not existing_task:
                alert_id = alert_row[0]["id"] if isinstance(alert_row, list) else alert_row.get("id")
                sb_insert("inverter_maintenance", {
                    "inverter_id": inverter_id,
                    "client_id":   client_id,
                    "title":       f"[Auto] {title}",
                    "description": detail,
                    "status":      "pending",
                    "priority":    _AUTO_MAINTENANCE[alert_type],
                    "alert_id":    alert_id,
                    "alert_type":  alert_type,
                })
        except Exception:
            pass


def _resolve_alert(inverter_id: str, alert_type: str) -> None:
    ts = _now().isoformat()
    for status in ("open", "muted"):
        existing = sb_select(
            "inverter_alerts",
            filters={"inverter_id": inverter_id, "alert_type": alert_type, "status": status},
            limit=1,
        ) or []
        if existing:
            sb_update(
                "inverter_alerts",
                {"id": existing[0]["id"]},
                {"status": "resolved", "resolved_at": ts},
            )


# ── Individual checks ─────────────────────────────────────────────────────────

def check_offline(inv: dict, last_reading: Optional[dict]) -> None:
    inv_id    = inv["id"]
    client_id = inv.get("client_id", "")
    threshold_min = 35  # minutes

    if not last_reading:
        _open_alert(inv_id, client_id, "offline",
                    title="Inversor offline — sem leituras",
                    detail="Nenhuma leitura registrada. Verifique conectividade do datalogger.",
                    value=0, threshold=threshold_min)
        return

    ts_str = last_reading.get("ts") or ""
    try:
        last_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        age_min = (_now() - last_ts).total_seconds() / 60
    except Exception:
        return

    if age_min > threshold_min:
        _open_alert(inv_id, client_id, "offline",
                    title=f"Inversor offline — sem sync há {int(age_min)} min",
                    detail=f"Última leitura recebida há {int(age_min)} minutos. Verifique datalogger e conexão.",
                    value=round(age_min, 1), threshold=threshold_min,
                    meta={"last_ts": ts_str})
    else:
        _resolve_alert(inv_id, "offline")


def check_low_generation(inv: dict, last_reading: Optional[dict], irr_kwh_m2: Optional[float] = None) -> None:
    inv_id    = inv["id"]
    client_id = inv.get("client_id", "")

    kWp = float(inv.get("nominal_power_kw") or 0)
    if kWp <= 0 or not last_reading:
        return

    # Fetch irradiance internally when not provided (background sync path)
    if irr_kwh_m2 is None:
        meta = inv.get("plant_meta") or {}
        if isinstance(meta, str):
            try:
                import json
                meta = json.loads(meta)
            except Exception:
                meta = {}
        if meta.get("coords_valid") and meta.get("lat"):
            from datetime import date as _date
            irr_kwh_m2 = _fetch_irradiance_simple(
                float(meta["lat"]), float(meta["lon"]),
                _date.today().isoformat(),
            )

    if irr_kwh_m2 is None or irr_kwh_m2 < 0.5:
        # sem irradiância confiável (noite ou dado indisponível) — não alertar
        _resolve_alert(inv_id, "low_generation")
        return

    active_w = float(last_reading.get("active_power_w") or 0)
    if active_w < 5:
        # noite ou inversor desligado — não é alerta de baixa geração
        _resolve_alert(inv_id, "low_generation")
        return

    # Potência prevista para agora: irradiância × kWp × 0.80 / 8h (dia solar médio)
    # Usamos potência atual como proxy: comparar active_w com expected_w
    expected_w = irr_kwh_m2 * kWp * 1000 * 0.80 / 8.0  # média do dia em W
    threshold_pct = 0.60

    if active_w < expected_w * threshold_pct:
        pct = round(active_w / expected_w * 100, 1) if expected_w > 0 else 0
        _open_alert(inv_id, client_id, "low_generation",
                    title=f"Baixa geração — {pct}% do esperado",
                    detail=(f"Potência atual {round(active_w/1000,2)} kW vs "
                            f"{round(expected_w/1000,2)} kW esperado. "
                            f"Verifique sombreamento, sujeira ou falha de string."),
                    value=round(active_w, 1), threshold=round(expected_w * threshold_pct, 1),
                    meta={"pct_real": pct, "expected_w": round(expected_w, 1)})
    else:
        _resolve_alert(inv_id, "low_generation")


def check_string_imbalance(inv: dict, last_reading: Optional[dict]) -> None:
    inv_id    = inv["id"]
    client_id = inv.get("client_id", "")

    if not last_reading:
        return

    strings = []
    for i in range(1, 5):
        v = last_reading.get(f"dc_voltage_{i}_v")
        a = last_reading.get(f"dc_current_{i}_a")
        if v is not None and a is not None:
            power = float(v) * float(a)
            strings.append((i, power))

    if len(strings) < 2:
        return

    powers = [p for _, p in strings]
    max_p  = max(powers)
    if max_p < 10:  # < 10 W total — desconsiderar (noite)
        _resolve_alert(inv_id, "string_imbalance")
        return

    # Ignorar strings com < 10% da máxima (desconectadas)
    active = [(i, p) for i, p in strings if p >= max_p * 0.10]
    if len(active) < 2:
        return

    active_powers = [p for _, p in active]
    avg_p = sum(active_powers) / len(active_powers)
    deviation = (max(active_powers) - min(active_powers)) / avg_p if avg_p > 0 else 0
    threshold = 0.15

    if deviation > threshold:
        worst_i, worst_p = min(active, key=lambda x: x[1])
        _open_alert(inv_id, client_id, "string_imbalance",
                    title=f"Desbalanceamento de string — desvio {round(deviation*100,1)}%",
                    detail=(f"String {worst_i} produzindo {round(worst_p,1)} W vs média de "
                            f"{round(avg_p,1)} W. Verifique sombreamento, módulo degradado ou conexão."),
                    value=round(deviation * 100, 1), threshold=round(threshold * 100, 1),
                    meta={"strings": {str(i): round(p, 1) for i, p in strings},
                          "avg_w": round(avg_p, 1), "deviation_pct": round(deviation * 100, 1)})
    else:
        _resolve_alert(inv_id, "string_imbalance")


def check_high_temp(inv: dict, recent_readings: List[dict]) -> None:
    inv_id    = inv["id"]
    client_id = inv.get("client_id", "")
    threshold_c = 75.0
    window_min  = 15

    if not recent_readings:
        return

    # Verificar se TODAS as leituras dos últimos 15 min estão acima do threshold
    cutoff = _now() - timedelta(minutes=window_min)
    window_readings = []
    for r in recent_readings:
        ts_str = r.get("ts") or ""
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts >= cutoff:
                window_readings.append(r)
        except Exception:
            pass

    if not window_readings:
        return

    temps = [float(r["temp_inverter_c"]) for r in window_readings
             if r.get("temp_inverter_c") is not None]

    if not temps:
        return

    avg_temp = sum(temps) / len(temps)
    max_temp = max(temps)

    if avg_temp > threshold_c:
        _open_alert(inv_id, client_id, "high_temp",
                    title=f"Temperatura alta — {round(max_temp,1)}°C",
                    detail=(f"Temperatura média de {round(avg_temp,1)}°C nos últimos {window_min} min "
                            f"(máx {round(max_temp,1)}°C). Verifique ventilação e carga do inversor."),
                    value=round(max_temp, 1), threshold=threshold_c)
    else:
        _resolve_alert(inv_id, "high_temp")


def check_pr_degradation(inv: dict, readings_7d: List[dict] = None) -> None:
    """PR médio dos últimos 7 dias. Busca leituras do banco internamente se não fornecidas."""
    inv_id    = inv["id"]
    client_id = inv.get("client_id", "")

    if readings_7d is None:
        readings_7d = sb_select(
            "inverter_readings",
            filters={"inverter_id": inv_id},
            order="ts.desc",
            limit=1100,  # ~7 dias × 144 leituras/dia
        ) or []

    meta = inv.get("plant_meta") or {}
    if isinstance(meta, str):
        try:
            import json
            meta = json.loads(meta)
        except Exception:
            meta = {}

    if not meta.get("coords_valid") or not meta.get("lat"):
        return

    kWp = float(inv.get("nominal_power_kw") or 0)
    if kWp <= 0:
        return

    lat = float(meta["lat"])
    lon = float(meta["lon"])

    # Group readings by BRT date, get max energy_today_kwh per day
    from datetime import date as _date, datetime as _dt
    BRT = timezone(timedelta(hours=-3))

    daily: Dict[str, float] = {}
    for r in readings_7d:
        ts_str = r.get("ts") or ""
        e = r.get("energy_today_kwh")
        if not ts_str or e is None:
            continue
        try:
            d = _dt.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(BRT).date().isoformat()
            daily[d] = max(daily.get(d, 0.0), float(e))
        except Exception:
            pass

    if len(daily) < 3:  # precisa de ao menos 3 dias com dados
        return

    # Calculate PR per day — track date alongside PR to avoid zip misalignment
    pr_by_day: Dict[str, float] = {}
    for d, e_real in daily.items():
        irr = _fetch_irradiance_simple(lat, lon, d)
        if irr is None or irr < 0.5:
            continue
        e_prev = irr * kWp * 0.80
        if e_prev > 0 and e_real >= 0.5:
            pr_by_day[d] = e_real / e_prev

    if len(pr_by_day) < 3:
        return

    prs = list(pr_by_day.values())
    avg_pr = sum(prs) / len(prs)
    threshold = 0.75

    if avg_pr < threshold:
        _open_alert(inv_id, client_id, "pr_degradation",
                    title=f"PR degradado — média {round(avg_pr,3)} últimos {len(prs)} dias",
                    detail=(f"Performance Ratio médio de {round(avg_pr*100,1)}% nos últimos {len(prs)} dias "
                            f"(limiar: {round(threshold*100)}%). Verifique acúmulo de sujeira, "
                            f"degradação de módulos ou falhas elétricas."),
                    value=round(avg_pr, 3), threshold=threshold,
                    meta={"days": len(prs), "pr_per_day": {d: round(p, 3) for d, p in pr_by_day.items()}})
    else:
        _resolve_alert(inv_id, "pr_degradation")


def _fetch_irradiance_simple(lat: float, lon: float, date_str: str) -> Optional[float]:
    """Retorna kWh/m² ou None. Sem side effects."""
    import httpx

    date_compact = date_str.replace("-", "")
    try:
        r = httpx.get(
            "https://power.larc.nasa.gov/api/temporal/daily/point",
            params={"parameters": "ALLSKY_SFC_SW_DWN", "community": "RE",
                    "longitude": lon, "latitude": lat,
                    "start": date_compact, "end": date_compact, "format": "JSON"},
            timeout=10.0,
        )
        val = (r.json().get("properties", {}).get("parameter", {})
               .get("ALLSKY_SFC_SW_DWN", {}).get(date_compact))
        if val is not None and float(val) >= 0:
            return float(val)
    except Exception:
        pass

    try:
        r2 = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "daily": "shortwave_radiation_sum",
                    "past_days": 10, "forecast_days": 1, "timezone": "auto"},
            timeout=8.0,
        )
        daily = r2.json().get("daily", {})
        for t, v in zip(daily.get("time", []), daily.get("shortwave_radiation_sum", [])):
            if t == date_str and v is not None and float(v) >= 0:
                return float(v) / 3.6
    except Exception:
        pass

    return None


# ── Main entry point (called during each sync) ────────────────────────────────

def run_alert_checks(inv: dict, last_reading: Optional[dict], recent_readings: List[dict],
                     irr_kwh_m2: Optional[float] = None) -> None:
    """
    Executa todos os checks de alerta para um inversor.
    Chamado após cada sync bem-sucedido.
    recent_readings: leituras recentes (últimas horas), ordenadas desc.
    """
    try:
        check_offline(inv, last_reading)
    except Exception:
        pass

    try:
        check_low_generation(inv, last_reading, irr_kwh_m2)
    except Exception:
        pass

    try:
        check_string_imbalance(inv, last_reading)
    except Exception:
        pass

    try:
        check_high_temp(inv, recent_readings)
    except Exception:
        pass

    # PR degradation: só roda a cada 4h para economizar chamadas de API de irradiância
    # Passa None para forçar busca interna dos 7 dias de leituras
    try:
        if datetime.now(timezone.utc).hour % 4 == 0:
            check_pr_degradation(inv, None)
    except Exception:
        pass
