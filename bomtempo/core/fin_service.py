"""
FinService — Serviço de custos por projeto (Feature #21)
Tabelas: fin_categorias, fin_custos

Colunas reais de fin_custos:
  id, contrato, categoria_id, categoria_nome, atividade_id, atividade_nome,
  descricao, valor_previsto, valor_executado, status, data, criado_por,
  created_at, updated_at, empresa
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from bomtempo.core.supabase_client import sb_select, sb_insert, sb_update, sb_delete

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _norm(v: Any, fallback: str = "") -> str:
    if v is None or str(v) in ("None", "NaT", "nan", ""):
        return fallback
    return str(v)


def _parse_float(v: Any) -> float:
    """Parse float from various formats including BR currency strings."""
    if v is None:
        return 0.0
    s = str(v).strip()
    if not s or s in ("None", "nan", ""):
        return 0.0
    # BR format: 1.000,50
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    # strip non-numeric except . and -
    import re
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _fmt_brl(v: float) -> str:
    """Format float as BR currency string for display. e.g. 1234.56 → 'R$ 1.234,56'"""
    s = f"R$ {v:_.2f}"            # "R$ 1_234.56"
    s = s.replace(".", "DECPT")   # "R$ 1_234DECPT56"
    s = s.replace("_", ".")       # "R$ 1.234DECPT56"
    s = s.replace("DECPT", ",")   # "R$ 1.234,56"
    return s


# ─────────────────────────────────────────────────────────────────────────────
# FinService
# ─────────────────────────────────────────────────────────────────────────────

class FinService:

    # ── Categorias ────────────────────────────────────────────────────────────

    @staticmethod
    def load_categorias() -> List[Dict[str, str]]:
        """Load all fin_categorias ordered by nome."""
        try:
            rows = sb_select("fin_categorias", order="nome.asc", limit=100)
            return [
                {
                    "id":    _norm(r.get("id")),
                    "nome":  _norm(r.get("nome"), "—"),
                    "cor":   _norm(r.get("cor"), "#889999"),
                    "icone": _norm(r.get("icone"), "tag"),
                }
                for r in (rows or [])
            ]
        except Exception as e:
            logger.error(f"load_categorias error: {e}")
            return []

    @staticmethod
    def get_or_create_categoria(nome: str) -> Tuple[str, str]:
        """Returns (id, nome). Finds existing by name (case-insensitive) or creates new."""
        nome = nome.strip()
        if not nome:
            return "", ""
        try:
            rows = sb_select("fin_categorias", limit=200)
            for r in (rows or []):
                if str(r.get("nome", "")).strip().lower() == nome.lower():
                    return _norm(r.get("id")), _norm(r.get("nome"), nome)
            result = sb_insert("fin_categorias", {"nome": nome, "cor": "#889999", "icone": "tag"})
            new_id = _norm((result or [{}])[0].get("id")) if result else ""
            return new_id, nome
        except Exception as e:
            logger.error(f"get_or_create_categoria error: {e}")
            return "", nome

    # ── Custos ────────────────────────────────────────────────────────────────

    @staticmethod
    def load_custos(contrato: str) -> List[Dict[str, str]]:
        """Load all fin_custos for a contract, normalized as string dicts."""
        try:
            rows = sb_select(
                "fin_custos",
                filters={"contrato": contrato},
                order="created_at.asc",
                limit=1000,
            )
            result = []
            for r in (rows or []):
                prev = _parse_float(r.get("valor_previsto", 0))
                exec_ = _parse_float(r.get("valor_executado", 0))
                result.append({
                    "id":                 _norm(r.get("id")),
                    "contrato":           _norm(r.get("contrato")),
                    "categoria_id":       _norm(r.get("categoria_id")),
                    "categoria_nome":     _norm(r.get("categoria_nome"), "—"),
                    "empresa":            _norm(r.get("empresa"), ""),
                    "descricao":          _norm(r.get("descricao"), "—"),
                    "valor_previsto":     str(prev),
                    "valor_executado":    str(exec_),
                    "valor_previsto_fmt": _fmt_brl(prev),
                    "valor_executado_fmt": _fmt_brl(exec_),
                    "status":             _norm(r.get("status"), "previsto"),
                    "data_custo":         _norm(r.get("data"), "")[:10],  # coluna: "data"
                    "atividade_id":       _norm(r.get("atividade_id")),
                    "atividade_nome":     _norm(r.get("atividade_nome")),
                })
            return result
        except Exception as e:
            logger.error(f"load_custos error: {e}")
            return []

    @staticmethod
    def save_custo(
        contrato: str,
        categoria_id: str,
        categoria_nome: str,
        empresa: str,
        descricao: str,
        valor_previsto: float,
        valor_executado: float,
        status: str,
        data_custo: str,
        atividade_id: str,
        custo_id: str = "",
        client_id: str = "",
    ) -> Tuple[bool, str]:
        """
        Insert or update a custo record.
        Returns (success, id_or_error).
        """
        payload: Dict[str, Any] = {
            "contrato":        contrato,
            "categoria_id":    categoria_id or None,
            "categoria_nome":  categoria_nome,
            "empresa":         empresa or "",
            "descricao":       descricao,
            "valor_previsto":  round(valor_previsto, 2),
            "valor_executado": round(valor_executado, 2),
            "status":          status or "previsto",
            "data":            data_custo or None,  # coluna real: "data"
            "atividade_id":    atividade_id or None,
            "client_id":       client_id or None,
        }
        try:
            if custo_id:
                sb_update("fin_custos", {"id": custo_id}, payload)
                return True, custo_id
            else:
                rows = sb_insert("fin_custos", payload)
                # sb_insert may return a dict or a list
                if isinstance(rows, dict):
                    new_id = _norm(rows.get("id"))
                elif isinstance(rows, list) and rows:
                    new_id = _norm(rows[0].get("id"))
                else:
                    new_id = ""
                return True, new_id
        except Exception as e:
            logger.error(f"save_custo error: {e}")
            return False, str(e)

    @staticmethod
    def delete_custo(custo_id: str) -> bool:
        try:
            sb_delete("fin_custos", {"id": custo_id})
            return True
        except Exception as e:
            logger.error(f"delete_custo error: {e}")
            return False

    # ── KPIs ──────────────────────────────────────────────────────────────────

    @staticmethod
    def compute_kpis(custos: List[Dict[str, str]]) -> Dict[str, str]:
        """Compute KPI summary from normalized custo rows."""
        total_prev = sum(_parse_float(r.get("valor_previsto", 0)) for r in custos)
        total_exec = sum(_parse_float(r.get("valor_executado", 0)) for r in custos)
        saldo = total_prev - total_exec
        pct = round(total_exec / total_prev * 100, 1) if total_prev > 0 else 0.0
        concluidos = sum(1 for r in custos if r.get("status") in ("concluido", "executado"))
        return {
            "total_previsto":   _fmt_brl(total_prev),
            "total_executado":  _fmt_brl(total_exec),
            "saldo":            _fmt_brl(saldo),
            "pct_executado":    f"{pct:.1f}",
            "total_itens":      str(len(custos)),
            "concluidos":       str(concluidos),
        }

    # ── S-Curve ───────────────────────────────────────────────────────────────

    @staticmethod
    def compute_scurve(custos: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Build cumulative S-curve data from custo rows.
        Returns list of {data, previsto_acum, executado_acum} sorted by date.
        """
        from collections import defaultdict
        prev_by_date: Dict[str, float] = defaultdict(float)
        exec_by_date: Dict[str, float] = defaultdict(float)

        for r in custos:
            d = r.get("data_custo", "") or ""
            if not d or len(d) < 10:
                continue
            d = d[:10]
            prev_by_date[d] += _parse_float(r.get("valor_previsto", 0))
            exec_by_date[d] += _parse_float(r.get("valor_executado", 0))

        all_dates = sorted(set(list(prev_by_date.keys()) + list(exec_by_date.keys())))
        if not all_dates:
            return []

        result = []
        acum_prev = 0.0
        acum_exec = 0.0
        for d in all_dates:
            acum_prev += prev_by_date.get(d, 0.0)
            acum_exec += exec_by_date.get(d, 0.0)
            try:
                parts = d.split("-")
                label = f"{parts[2]}/{parts[1]}"
            except Exception:
                label = d
            result.append({
                "data":           label,
                "previsto_acum":  str(round(acum_prev, 2)),
                "executado_acum": str(round(acum_exec, 2)),
            })
        return result

    # ── EVM — Earned Value Management ────────────────────────────────────────

    @staticmethod
    def compute_evm(
        custos: List[Dict[str, str]],
        avg_activity_pct: float = 0.0,
    ) -> Dict[str, str]:
        """
        Earned Value Management forecast.

        Métricas EVM para gestão financeira de obra:
          BAC  — Budget at Completion (total previsto)
          AC   — Actual Cost (executado até hoje)
          EV   — Earned Value = BAC × % físico concluído
          PV   — Planned Value (previsto acumulado até hoje por data)
          CPI  — Cost Performance Index = EV / AC (>1 = abaixo do orçamento)
          SPI  — Schedule Performance Index = EV / PV (>1 = adiantado)
          EAC  — Estimate at Completion = BAC / CPI
          VAC  — Variance at Completion = BAC - EAC (positivo = sobra, negativo = estouro)
          CV   — Cost Variance = EV - AC
          TCPI — To-Complete Performance Index = (BAC - EV) / (BAC - AC)
        """
        from datetime import date as _date

        if not custos:
            return {}

        BAC = sum(_parse_float(r.get("valor_previsto", 0)) for r in custos)
        AC = sum(_parse_float(r.get("valor_executado", 0)) for r in custos)

        if BAC <= 0:
            return {}

        # Planned Value: soma dos valores previstos de itens com data <= hoje
        today_str = str(_date.today())
        PV = sum(
            _parse_float(r.get("valor_previsto", 0))
            for r in custos
            if (r.get("data_custo") or "")[:10] and (r.get("data_custo") or "")[:10] <= today_str
        )

        # Earned Value: % físico × BAC
        physical_pct = avg_activity_pct if avg_activity_pct > 0 else (AC / BAC * 100 if BAC > 0 else 0)
        EV = BAC * (min(physical_pct, 100) / 100)

        CPI = EV / AC if AC > 0 else 1.0
        SPI = EV / PV if PV > 0 else 1.0

        EAC = BAC / CPI if CPI > 0 else BAC
        VAC = BAC - EAC
        CV = EV - AC
        SV = EV - PV

        remaining_budget = BAC - AC
        remaining_work_value = BAC - EV
        TCPI = remaining_work_value / remaining_budget if remaining_budget > 0 else 0.0

        dates = sorted(
            [r.get("data_custo", "")[:10] for r in custos if (r.get("data_custo") or "")[:10]],
        )
        burn_rate_daily = 0.0
        if dates and AC > 0:
            try:
                from datetime import datetime as _dt
                start = _dt.strptime(dates[0], "%Y-%m-%d").date()
                days_elapsed = max(1, (_date.today() - start).days)
                burn_rate_daily = AC / days_elapsed
            except Exception:
                pass

        return {
            "BAC_fmt":       _fmt_brl(BAC),
            "AC_fmt":        _fmt_brl(AC),
            "EV_fmt":        _fmt_brl(EV),
            "PV_fmt":        _fmt_brl(PV),
            "EAC_fmt":       _fmt_brl(EAC),
            "VAC_fmt":       _fmt_brl(abs(VAC)),
            "CV_fmt":        _fmt_brl(abs(CV)),
            "SV_fmt":        _fmt_brl(abs(SV)),
            "CPI":           f"{CPI:.2f}",
            "SPI":           f"{SPI:.2f}",
            "TCPI":          f"{TCPI:.2f}",
            "physical_pct":  f"{physical_pct:.1f}",
            "cost_pct":      f"{AC / BAC * 100:.1f}",
            "burn_rate_fmt": _fmt_brl(burn_rate_daily) + "/dia",
            "is_overrun":    str(VAC < 0),
            "is_behind":     str(SV < 0),
            "vac_positive":  str(VAC >= 0),
            "sv_positive":   str(SV >= 0),
        }

    # ── Por categoria (bar chart) ─────────────────────────────────────────────

    @staticmethod
    def compute_by_categoria(custos: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Aggregate previsto/executado by categoria for bar chart."""
        from collections import defaultdict
        prev_cat: Dict[str, float] = defaultdict(float)
        exec_cat: Dict[str, float] = defaultdict(float)

        for r in custos:
            cat = r.get("categoria_nome", "Outros") or "Outros"
            prev_cat[cat] += _parse_float(r.get("valor_previsto", 0))
            exec_cat[cat] += _parse_float(r.get("valor_executado", 0))

        all_cats = sorted(set(list(prev_cat.keys()) + list(exec_cat.keys())))
        return [
            {
                "categoria": cat,
                "previsto":  str(round(prev_cat.get(cat, 0), 2)),
                "executado": str(round(exec_cat.get(cat, 0), 2)),
            }
            for cat in all_cats
        ]
