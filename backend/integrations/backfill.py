"""
Historical data backfill engine.

Phase 1 — Daily (fast): 1 reading per day anchored at 23:30 BRT.
  ShineMonitor : queryDeviceDataOneDay datetype=month  → 6 calls for 6 months
  Solarman     : device/v1.0/historical time_type=3    → 1 call for full range
  → Feeds PR history, yield analysis, financeiro retroativo.

Phase 2 — Intraday (slower): full power curve per day.
  ShineMonitor : queryDeviceDataOneDay datetype=day    → 1 call/day (~180 calls for 6 mo)
  Solarman     : device/v1.0/historical time_type=2    → 1 call/week (~26 calls for 6 mo)
  → Feeds curva de potência, temperatura, strings históricas.

Estimated runtime (Phase 2):
  ShineMonitor : 180 days × 0.4 s delay ≈ 3 min
  Solarman     : 26 chunks × 0.5 s delay ≈ 13 s

Deduplication:
  Phase 1 : skip dates already present in DB (date set, 1 round-trip)
  Phase 2 : 5-min bucket set built in-memory; dates already covered by intraday data skipped
"""

import time
from datetime import date as _date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

BRT = timezone(timedelta(hours=-3))


# ── Shared helpers ────────────────────────────────────────────────────────────

def _today_brt() -> _date:
    return datetime.now(BRT).date()


def _fetch_existing_dates(inv_id: str, start: _date, end: _date) -> Set[str]:
    """One DB round-trip → set of BRT date strings already covered."""
    from backend.integrations.supabase import sb_select
    start_utc = datetime(start.year, start.month, start.day, tzinfo=BRT).astimezone(timezone.utc).isoformat()
    days = (end - start).days + 1
    rows = sb_select(
        "inverter_readings",
        filters={"inverter_id": inv_id},
        raw_filters={"ts": f"gte.{start_utc}"},
        order="ts.asc",
        limit=days * 20 + 100,
    ) or []
    out: Set[str] = set()
    for r in rows:
        ts_str = r.get("ts") or ""
        try:
            out.add(datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(BRT).date().isoformat())
        except Exception:
            pass
    return out


def _fetch_existing_buckets(inv_id: str, start: _date, end: _date) -> Set[str]:
    """
    One DB round-trip → set of 5-min bucket strings 'YYYY-MM-DD:N' already in DB.
    Used by Phase 2 to skip timestamps already inserted (cross-run dedup).
    With 200 readings/day budget, covers 6 months of dense intraday data (~26 000 rows max).
    """
    from backend.integrations.supabase import sb_select
    start_utc = datetime(start.year, start.month, start.day, tzinfo=BRT).astimezone(timezone.utc).isoformat()
    days = (end - start).days + 1
    rows = sb_select(
        "inverter_readings",
        filters={"inverter_id": inv_id},
        raw_filters={"ts": f"gte.{start_utc}"},
        order="ts.asc",
        limit=days * 200 + 100,
    ) or []
    out: Set[str] = set()
    for r in rows:
        ts_str = r.get("ts") or ""
        try:
            dt      = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(BRT)
            day_str = dt.date().isoformat()
            bucket  = f"{day_str}:{dt.hour * 12 + dt.minute // 5}"
            out.add(bucket)
        except Exception:
            pass
    return out


def _month_first(base: _date, months_back: int) -> _date:
    """Return the first day of the month that is `months_back` months before `base`."""
    year  = base.year
    month = base.month - months_back
    while month <= 0:
        month += 12
        year  -= 1
    return _date(year, month, 1)


def _make_record(inv_id: str, ts_iso: str, reading: dict) -> dict:
    """Build a flat inverter_readings record from a normalised reading dict."""
    return {
        "inverter_id":       inv_id,
        "ts":                ts_iso,
        "active_power_w":    reading.get("active_power_w"),
        "energy_today_kwh":  reading.get("energy_today_kwh"),
        "energy_total_kwh":  reading.get("energy_total_kwh"),
        "energy_year_kwh":   reading.get("energy_year_kwh"),
        "grid_frequency_hz": reading.get("grid_frequency_hz"),
        "temp_inverter_c":   reading.get("temp_inverter_c"),
        "dc_voltage_1_v":    reading.get("dc_voltage_1_v"),
        "dc_voltage_2_v":    reading.get("dc_voltage_2_v"),
        "dc_voltage_3_v":    reading.get("dc_voltage_3_v"),
        "dc_voltage_4_v":    reading.get("dc_voltage_4_v"),
        "dc_current_1_a":    reading.get("dc_current_1_a"),
        "dc_current_2_a":    reading.get("dc_current_2_a"),
        "dc_current_3_a":    reading.get("dc_current_3_a"),
        "dc_current_4_a":    reading.get("dc_current_4_a"),
        "ac_voltage_a_v":    reading.get("ac_voltage_a_v"),
        "ac_voltage_b_v":    reading.get("ac_voltage_b_v"),
        "ac_voltage_c_v":    reading.get("ac_voltage_c_v"),
        "ac_current_a_a":    reading.get("ac_current_a_a"),
        "ac_current_b_a":    reading.get("ac_current_b_a"),
        "ac_current_c_a":    reading.get("ac_current_c_a"),
        "battery_soc_pct":   reading.get("battery_soc_pct"),
        "battery_power_w":   reading.get("battery_power_w"),
        "battery_voltage_v": reading.get("battery_voltage_v"),
        "status":            "normal",
        "raw_data":          reading.get("raw_data") or {},
    }


def _bulk_insert(records: List[dict]) -> int:
    """
    POST a list of records directly to Supabase REST in chunks of 200.
    Falls back to individual sb_insert on chunk failure.
    Returns count of successfully inserted records.
    """
    if not records:
        return 0

    try:
        import httpx as _httpx
        from backend.core.config import Config
        url = f"{Config.SUPABASE_URL}/rest/v1/inverter_readings"
        headers = {
            "apikey":          Config.SUPABASE_SERVICE_KEY,
            "Authorization":   f"Bearer {Config.SUPABASE_SERVICE_KEY}",
            "Content-Type":    "application/json",
            "Prefer":          "return=minimal",
        }
        inserted = 0
        for i in range(0, len(records), 200):
            chunk = records[i: i + 200]
            try:
                resp = _httpx.post(url, headers=headers, json=chunk, timeout=30.0)
                if resp.status_code in (200, 201, 204):
                    inserted += len(chunk)
                    continue
            except Exception:
                pass
            # Per-record fallback
            from backend.integrations.supabase import sb_insert
            for rec in chunk:
                try:
                    sb_insert("inverter_readings", rec)
                    inserted += 1
                except Exception:
                    pass
        return inserted
    except Exception:
        from backend.integrations.supabase import sb_insert
        inserted = 0
        for rec in records:
            try:
                sb_insert("inverter_readings", rec)
                inserted += 1
            except Exception:
                pass
        return inserted


# ── ShineMonitor helpers ──────────────────────────────────────────────────────

def _shine_col(fields: list, titles: list, *names: str) -> Optional[float]:
    for name in names:
        try:
            col = titles.index(name)
            v = fields[col]
            return float(str(v).replace(",", ".")) if v not in (None, "", "null") else None
        except (ValueError, IndexError):
            pass
    return None


def _parse_shine_row(fields: list, titles: list) -> Optional[Tuple[str, dict]]:
    """
    Parse one ShineMonitor title/row field list.
    Returns (ts_local_str, reading_dict) or None if invalid.
    """
    if not fields or len(fields) < 2:
        return None
    ts_str = fields[1]
    if not ts_str or ts_str == "null":
        return None
    try:
        datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    c = lambda *names: _shine_col(fields, titles, *names)
    reading: dict = {
        "energy_today_kwh":  c("today energy",   "eday",  "daily energy"),
        "energy_total_kwh":  c("total energy",   "etotal","total generating capacity"),
        "energy_year_kwh":   c("current year generating capacity", "eyear"),
        "active_power_w":    c("active power",   "pac",   "output power"),
        "temp_inverter_c":   c("inverter temperature", "tempdc", "temperature"),
        "grid_frequency_hz": c("grid frequency", "fac"),
        "dc_voltage_1_v":    c("dc voltage 1",   "vpv1"),
        "dc_voltage_2_v":    c("dc voltage 2",   "vpv2"),
        "dc_voltage_3_v":    c("dc voltage 3",   "vpv3"),
        "dc_voltage_4_v":    c("dc voltage 4",   "vpv4"),
        "dc_current_1_a":    c("dc current 1",   "ipv1"),
        "dc_current_2_a":    c("dc current 2",   "ipv2"),
        "dc_current_3_a":    c("dc current 3",   "ipv3"),
        "dc_current_4_a":    c("dc current 4",   "ipv4"),
        "ac_voltage_a_v":    c("ab voltage/a phase voltage"),
        "ac_voltage_b_v":    c("bc voltage/b phase voltage"),
        "ac_voltage_c_v":    c("ca voltage/c phase voltage"),
        "ac_current_a_a":    c("a phase current", "iac1"),
        "ac_current_b_a":    c("b phase current", "iac2"),
        "ac_current_c_a":    c("c phase current", "iac3"),
    }
    return ts_str, reading


# ── ShineMonitor Phase 1 ──────────────────────────────────────────────────────

def backfill_shine_phase1(inv: dict, auth: dict, months: int = 6) -> Tuple[int, int]:
    """
    Daily energy backfill via queryDeviceDataOneDay datetype=month.
    6 API calls for 6 months. Returns (inserted, skipped).
    """
    from backend.integrations.shinemonitor import get_energy_history

    pn      = inv.get("pn", "")
    sn      = inv.get("sn", "")
    devcode = inv.get("devcode", "")
    devaddr = inv.get("devaddr", "1")
    token, secret = auth["token"], auth["secret"]

    today = _today_brt()
    start = _month_first(today, months - 1)
    existing = _fetch_existing_dates(inv["id"], start, today)

    records: List[dict] = []
    skipped = 0

    for i in range(months):
        mo  = _month_first(today, i)
        raw = get_energy_history(token, secret, pn, sn, devcode, devaddr, mo.strftime("%Y-%m"))

        if not isinstance(raw, dict):
            time.sleep(0.3)
            continue

        titles = [t.get("title", "").lower().strip() for t in raw.get("title", [])]
        rows   = raw.get("row", [])

        for row in rows:
            fields = row.get("field", [])
            parsed = _parse_shine_row(fields, titles)
            if not parsed:
                continue
            ts_local_str, reading = parsed

            try:
                dt_local = datetime.strptime(ts_local_str, "%Y-%m-%d %H:%M:%S")
                day_str  = dt_local.date().isoformat()
            except ValueError:
                continue

            if day_str in existing:
                skipped += 1
                continue

            e_today = reading.get("energy_today_kwh")
            if e_today is None or e_today < 0:
                skipped += 1
                continue

            # Anchor at 23:30 BRT so it sorts after any real intraday readings
            eod    = datetime(dt_local.year, dt_local.month, dt_local.day, 23, 30, tzinfo=BRT)
            ts_iso = eod.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

            reading["active_power_w"] = None  # meaningless for a daily aggregate
            reading["raw_data"] = {"source": "backfill_phase1_shinemonitor"}
            records.append(_make_record(inv["id"], ts_iso, reading))
            existing.add(day_str)

        time.sleep(0.3)

    inserted = _bulk_insert(records)
    return inserted, skipped + max(0, len(records) - inserted)


# ── ShineMonitor Phase 2 ──────────────────────────────────────────────────────

def backfill_shine_phase2(
    inv: dict,
    auth: dict,
    months: int = 6,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Tuple[int, int]:
    """
    Intraday backfill via queryDeviceDataOneDay datetype=day.
    1 API call per day → ~180 calls for 6 months.
    Returns (inserted, skipped).
    """
    from backend.integrations.shinemonitor import _signed_params, _get

    pn      = inv.get("pn", "")
    sn      = inv.get("sn", "")
    devcode = inv.get("devcode", "")
    devaddr = inv.get("devaddr", "1")
    token, secret = auth["token"], auth["secret"]

    today = _today_brt()
    start = _month_first(today, months - 1)

    # Pre-load all existing 5-min buckets for the period — handles both:
    #   (a) skipping days already saturated with real-time intraday data
    #   (b) cross-run dedup so reimporting never creates duplicate timestamps
    seen_buckets: Set[str] = _fetch_existing_buckets(inv["id"], start, today)

    # Build list of historical days (exclude today — still generating)
    all_days      = [(start + timedelta(days=i)) for i in range((today - start).days)]
    total         = len(all_days)
    total_ins = total_sk = 0

    for idx, day in enumerate(all_days):
        day_str = day.isoformat()
        try:
            params = _signed_params(token, secret, "queryDeviceDataOneDay", {
                "pn": pn, "devcode": devcode, "sn": sn, "devaddr": devaddr,
                "date": day_str, "datetype": "day",
            })
            data = _get(params)
            raw  = data.get("dat", {})
        except Exception:
            if progress_cb:
                progress_cb(idx + 1, total)
            time.sleep(0.5)
            continue

        if not isinstance(raw, dict):
            if progress_cb:
                progress_cb(idx + 1, total)
            time.sleep(0.2)
            continue

        titles = [t.get("title", "").lower().strip() for t in raw.get("title", [])]
        rows   = raw.get("row", [])
        day_records: List[dict] = []

        for row in rows:
            fields = row.get("field", [])
            parsed = _parse_shine_row(fields, titles)
            if not parsed:
                continue
            ts_local_str, reading = parsed

            try:
                dt_local = datetime.strptime(ts_local_str, "%Y-%m-%d %H:%M:%S")
                # 5-min bucket dedup
                bucket = f"{day_str}:{dt_local.hour * 12 + dt_local.minute // 5}"
                if bucket in seen_buckets:
                    total_sk += 1
                    continue
                seen_buckets.add(bucket)

                dt_utc = dt_local.replace(tzinfo=BRT).astimezone(timezone.utc)
                ts_iso = dt_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            except ValueError:
                continue

            if reading.get("energy_today_kwh") is None and reading.get("active_power_w") is None:
                total_sk += 1
                continue

            reading["raw_data"] = {"source": "backfill_phase2_shinemonitor"}
            day_records.append(_make_record(inv["id"], ts_iso, reading))

        if day_records:
            n = _bulk_insert(day_records)
            total_ins += n
            total_sk  += len(day_records) - n

        if progress_cb:
            progress_cb(idx + 1, total)

        time.sleep(0.4)

    return total_ins, total_sk


# ── Solarman Phase 1 ──────────────────────────────────────────────────────────

def backfill_solarman_phase1(inv: dict, auth: dict, months: int = 6) -> Tuple[int, int]:
    """
    Daily energy backfill via Solarman time_type=3 (daily aggregates).
    Single API call covers the full date range. Returns (inserted, skipped).
    """
    from backend.integrations.solarman import get_historical_readings

    device_sn = inv.get("sn", "")
    token     = auth["token"]

    today = _today_brt()
    start = today - timedelta(days=months * 30)
    existing = _fetch_existing_dates(inv["id"], start, today)

    start_ts = int(datetime(start.year, start.month, start.day, 0, 0, tzinfo=BRT).timestamp())
    end_ts   = int(datetime(today.year, today.month, today.day, 23, 59, tzinfo=BRT).timestamp())

    rows = get_historical_readings(token, device_sn, start_ts, end_ts, time_type=3)

    records: List[dict] = []
    skipped = 0

    for row in rows:
        ts_epoch = row.get("time")
        if not ts_epoch:
            continue

        dt_brt  = datetime.fromtimestamp(ts_epoch, tz=BRT)
        day_str = dt_brt.date().isoformat()

        if day_str in existing:
            skipped += 1
            continue

        data_list = row.get("dataList", [])
        mapped: Dict[str, Any] = {
            (item.get("key") or "").strip(): item.get("value")
            for item in data_list
        }

        def _f(k: str) -> Optional[float]:
            v = mapped.get(k)
            try:
                return float(str(v).replace(",", ".")) if v is not None else None
            except (ValueError, TypeError):
                return None

        def _first(*keys: str) -> Optional[float]:
            for k in keys:
                v = _f(k)
                if v is not None:
                    return v
            return None

        e_today = _first("dailyEnergy", "eToday", "todayEnergy", "Daily Generation")
        if e_today is None or e_today < 0:
            skipped += 1
            continue

        eod    = datetime(dt_brt.year, dt_brt.month, dt_brt.day, 23, 30, tzinfo=BRT)
        ts_iso = eod.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        reading = {
            "energy_today_kwh":  e_today,
            "energy_total_kwh":  _first("totalEnergy", "eTotal", "Total Generation"),
            "energy_year_kwh":   _first("yearEnergy",  "Year Generation"),
            "active_power_w":    None,
            "temp_inverter_c":   _first("dcTemperature", "temperature"),
            "grid_frequency_hz": _first("gridFrequency", "frequency"),
            "dc_voltage_1_v":    _first("pv1Voltage", "vpv1"),
            "dc_voltage_2_v":    _first("pv2Voltage", "vpv2"),
            "ac_voltage_a_v":    _first("gridVoltage", "uac1"),
            "raw_data":          {"source": "backfill_phase1_solarman"},
        }
        records.append(_make_record(inv["id"], ts_iso, reading))
        existing.add(day_str)

    inserted = _bulk_insert(records)
    return inserted, skipped + max(0, len(records) - inserted)


# ── Solarman Phase 2 ──────────────────────────────────────────────────────────

def backfill_solarman_phase2(
    inv: dict,
    auth: dict,
    months: int = 6,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Tuple[int, int]:
    """
    Hourly backfill via Solarman time_type=2, chunked weekly (~26 calls for 6 mo).
    Returns (inserted, skipped).
    """
    from backend.integrations.solarman import get_historical_readings

    device_sn = inv.get("sn", "")
    token     = auth["token"]

    today = _today_brt()
    start = today - timedelta(days=months * 30)

    # Weekly chunks
    chunks: List[Tuple[_date, _date]] = []
    cur = start
    while cur < today:
        end_chunk = min(cur + timedelta(days=6), today - timedelta(days=1))
        chunks.append((cur, end_chunk))
        cur = end_chunk + timedelta(days=1)

    seen_epochs: Set[int] = set()
    total_ins = total_sk = 0
    total = len(chunks)

    for idx, (cs, ce) in enumerate(chunks):
        start_ts = int(datetime(cs.year, cs.month, cs.day, 0, 0, tzinfo=BRT).timestamp())
        end_ts   = int(datetime(ce.year, ce.month, ce.day, 23, 59, tzinfo=BRT).timestamp())

        rows = get_historical_readings(token, device_sn, start_ts, end_ts, time_type=2)
        chunk_records: List[dict] = []

        for row in rows:
            ts_epoch = row.get("time")
            if not ts_epoch or ts_epoch in seen_epochs:
                total_sk += 1
                continue
            seen_epochs.add(ts_epoch)

            data_list = row.get("dataList", [])
            mapped: Dict[str, Any] = {
                (item.get("key") or "").strip(): item.get("value")
                for item in data_list
            }

            def _f(k: str) -> Optional[float]:
                v = mapped.get(k)
                try:
                    return float(str(v).replace(",", ".")) if v is not None else None
                except (ValueError, TypeError):
                    return None

            def _first(*keys: str) -> Optional[float]:
                for k in keys:
                    v = _f(k)
                    if v is not None:
                        return v
                return None

            e_today  = _first("dailyEnergy", "eToday", "todayEnergy")
            active_w = _first("activePower", "pac", "generationPower")
            if active_w is not None and active_w < 500:
                active_w = active_w * 1000  # kW → W

            if e_today is None and active_w is None:
                total_sk += 1
                continue

            dt_utc = datetime.fromtimestamp(ts_epoch, tz=timezone.utc)
            ts_iso = dt_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")

            reading = {
                "energy_today_kwh":  e_today,
                "energy_total_kwh":  _first("totalEnergy", "eTotal"),
                "active_power_w":    active_w,
                "temp_inverter_c":   _first("dcTemperature", "temperature"),
                "grid_frequency_hz": _first("gridFrequency", "frequency"),
                "dc_voltage_1_v":    _first("pv1Voltage", "vpv1"),
                "dc_voltage_2_v":    _first("pv2Voltage", "vpv2"),
                "dc_current_1_a":    _first("pv1Current", "ipv1"),
                "dc_current_2_a":    _first("pv2Current", "ipv2"),
                "ac_voltage_a_v":    _first("gridVoltage", "uac1"),
                "raw_data":          {"source": "backfill_phase2_solarman"},
            }
            chunk_records.append(_make_record(inv["id"], ts_iso, reading))

        if chunk_records:
            n = _bulk_insert(chunk_records)
            total_ins += n
            total_sk  += len(chunk_records) - n

        if progress_cb:
            progress_cb(idx + 1, total)

        time.sleep(0.5)

    return total_ins, total_sk


# ── Main entry point ──────────────────────────────────────────────────────────

def run_backfill(
    inv: dict,
    auth: dict,
    months: int = 6,
    phase: str = "both",
    progress_cb: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, Any]:
    """
    Run Phase 1 and/or Phase 2 for the given inverter.
    phase: "1" | "2" | "both"
    progress_cb(phase_name, done, total) — called per day/chunk during Phase 2.
    Returns summary dict with phase1/phase2 keys.
    """
    slug   = inv.get("platform_slug", "")
    result: Dict[str, Any] = {"slug": slug, "months": months}

    if phase in ("1", "both"):
        if slug == "shinemonitor":
            ins, sk = backfill_shine_phase1(inv, auth, months)
        elif slug == "solarman":
            ins, sk = backfill_solarman_phase1(inv, auth, months)
        else:
            ins, sk = 0, 0
        result["phase1"] = {"inserted": ins, "skipped": sk}

    if phase in ("2", "both"):
        cb2 = (lambda d, t: progress_cb("phase2", d, t)) if progress_cb else None
        if slug == "shinemonitor":
            ins2, sk2 = backfill_shine_phase2(inv, auth, months, progress_cb=cb2)
        elif slug == "solarman":
            ins2, sk2 = backfill_solarman_phase2(inv, auth, months, progress_cb=cb2)
        else:
            ins2, sk2 = 0, 0
        result["phase2"] = {"inserted": ins2, "skipped": sk2}

    return result
