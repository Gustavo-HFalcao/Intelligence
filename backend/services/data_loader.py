"""
DataLoader — port direto de bomtempo/core/data_loader.py.

Carrega dados de todas as tabelas Supabase em paralelo, normaliza colunas para
snake_case e armazena em cache (Redis → pickle → Supabase ao vivo).

Isolamento de tenant: todas as queries filtram por client_id (exceto master/global).
"""

import os
import pickle
import re
import tempfile
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _date

import pandas as pd

from backend.core.logging import get_logger
from backend.core.redis_cache import (
    CACHE_TTL_SECONDS,
    cache_get,
    cache_invalidate,
    cache_invalidate_all,
    cache_set,
)
from backend.integrations.supabase import sb_select

logger = get_logger(__name__)

CACHE_TTL = 3600  # pickle fallback TTL (segundos)

TABLE_MAP = [
    ("contratos",               "contratos"),
    ("hub_atividades",          "projeto"),
    ("hub_atividade_historico", "hub_historico"),
    ("fin_custos",              "financeiro"),
    ("om_geracoes",             "om"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cache_path(client_id: str = "") -> str:
    safe_id = (client_id[:8] if client_id else "global").replace("-", "")
    return os.path.join(tempfile.gettempdir(), f"bomtempo_cache_{safe_id}.pkl")


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _parse_brl(val) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = re.sub(r"[^\d,.-]", "", str(val).strip())
    if s in ("-", "", "—", "–"):
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


# ── DataLoader ────────────────────────────────────────────────────────────────

class DataLoader:
    """Carrega e normaliza todas as tabelas do tenant."""

    def __init__(self, client_id: str = ""):
        self.client_id = client_id

    # ── Carregamento ─────────────────────────────────────────────────────────

    def load_all(self) -> dict:
        """Redis → pickle → Supabase. Retorna dict[str, pd.DataFrame]."""
        # 1. Redis
        cached = cache_get(self.client_id, "data_all")
        if cached:
            logger.info(f"Dados do Redis — tenant={self._tid()}")
            return cached

        # 2. Pickle
        cached = self._try_load_pickle(fresh_only=True)
        if cached:
            logger.info(f"Dados do pickle — tenant={self._tid()}")
            return cached

        # 3. Supabase
        logger.info(f"Carregando do Supabase — tenant={self._tid()}")
        data: dict = {}
        success = False

        def _fetch(table: str, key: str):
            filters = {"client_id": self.client_id} if self.client_id else {}
            rows = sb_select(table, filters=filters)
            return key, rows

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(_fetch, t, k): (t, k) for t, k in TABLE_MAP}
            for future in as_completed(futures):
                t, k = futures[future]
                try:
                    key, rows = future.result()
                    data[key] = pd.DataFrame(rows) if rows else pd.DataFrame()
                    if rows:
                        logger.info(f"  {key}: {len(rows)} linhas")
                        success = True
                except Exception as e:
                    logger.error(f"Erro ao carregar {t}: {e}")
                    data[k] = pd.DataFrame()

        data = self._normalize_all(data)

        if success:
            saved = cache_set(self.client_id, "data_all", data, ttl=CACHE_TTL_SECONDS)
            if not saved:
                self._save_pickle(data)

        logger.info("Carga de dados concluída")
        return data

    # ── Cache invalidation (API pública) ────────────────────────────────────

    @staticmethod
    def invalidate_cache(client_id: str = "") -> None:
        """Remove cache Redis + pickle do tenant — força recarga na próxima request."""
        try:
            cache_invalidate(client_id, "data_all")
        except Exception as e:
            logger.debug(f"Redis invalidate: {e}")
        try:
            path = _cache_path(client_id)
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning(f"Falha ao invalidar pickle: {e}")

    @staticmethod
    def invalidate_all_caches(client_id: str = "") -> None:
        """Invalida todas as chaves do tenant no Redis + pickle."""
        try:
            cache_invalidate_all(client_id)
        except Exception as e:
            logger.debug(f"Redis invalidate_all: {e}")
        DataLoader.invalidate_cache(client_id)

    # ── Pickle helpers ───────────────────────────────────────────────────────

    def _try_load_pickle(self, fresh_only: bool = True):
        path = _cache_path(self.client_id)
        if not os.path.exists(path):
            return None
        try:
            if fresh_only and (time.time() - os.path.getmtime(path)) >= CACHE_TTL:
                return None
            with open(path, "rb") as f:
                data = pickle.load(f)
            return data if isinstance(data, dict) else None
        except Exception as e:
            logger.warning(f"Erro ao ler pickle: {e}")
            return None

    def _save_pickle(self, data: dict) -> None:
        try:
            with open(_cache_path(self.client_id), "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.error(f"Erro ao salvar pickle: {e}")

    # ── Normalização ─────────────────────────────────────────────────────────

    def _normalize_all(self, data: dict) -> dict:
        data = self._norm_contratos(data)
        data = self._norm_projeto(data)
        data = self._norm_obras(data)
        data = self._norm_financeiro(data)
        data = self._norm_om(data)
        data = self._crossref_valor_contratado(data)
        data = self._crossref_status(data)
        return data

    def _norm_contratos(self, data: dict) -> dict:
        if "contratos" not in data or data["contratos"].empty:
            return data
        df = data["contratos"]
        rename = {}
        for col in df.columns:
            cl = _strip_accents(col).lower()
            if cl == "projeto":            rename[col] = "projeto"
            elif cl == "contrato":         rename[col] = "contrato"
            elif cl == "cliente":          rename[col] = "cliente"
            elif cl == "terceirizado":     rename[col] = "terceirizado"
            elif "localiza" in cl:         rename[col] = "localizacao"
            elif "valor" in cl and "contratado" in cl: rename[col] = "valor_contratado"
            elif cl == "status":           rename[col] = "status"
        df = df.rename(columns=rename)
        if "valor_contratado" not in df.columns:
            df["valor_contratado"] = 0.0
        if "status" not in df.columns:
            df["status"] = "Em Execução"
        data["contratos"] = df
        return data

    def _norm_projeto(self, data: dict) -> dict:
        if "projeto" not in data or data["projeto"].empty:
            return data
        df = data["projeto"]
        rename = {}
        for col in df.columns:
            cl = _strip_accents(col).lower()
            if cl == "id":                         rename[col] = "id"
            elif cl == "fase":                     rename[col] = "fase"
            elif cl == "atividade":                rename[col] = "atividade"
            elif cl == "critico":                  rename[col] = "critico"
            elif cl == "data_inicio":              rename[col] = "inicio_previsto"
            elif cl == "data_termino":             rename[col] = "termino_previsto"
            elif "conclusao" in cl:                rename[col] = "conclusao_pct"
            elif cl == "dependencia":              rename[col] = "dependencia"
            elif cl == "responsavel":              rename[col] = "responsavel"
            elif cl == "contrato":                 rename[col] = "contrato"
            elif cl == "fase_macro":               rename[col] = "fase_macro"
            elif cl in ("peso_pct", "weight"):     rename[col] = "peso_pct"
            elif cl == "nivel":                    rename[col] = "nivel"
            elif cl == "parent_id":                rename[col] = "parent_id"
        df = df.rename(columns=rename)
        if "critico" not in df.columns:
            df["critico"] = "Nao"
        for col in ["inicio_previsto", "termino_previsto"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        if "conclusao_pct" in df.columns:
            df["conclusao_pct"] = pd.to_numeric(df["conclusao_pct"], errors="coerce").fillna(0)
        if "pendente_aprovacao" in df.columns:
            df = df[df["pendente_aprovacao"].astype(str) != "1"].copy()
        data["projeto"] = df
        return data

    def _norm_obras(self, data: dict) -> dict:
        if "contratos" not in data or data["contratos"].empty:
            return data
        import numpy as np  # noqa: F401

        df = data["contratos"].copy()
        df = df.rename(columns={
            "data_inicio":           "inicio",
            "data_termino":          "termino",
            "prazo_contratual_dias": "prazo_contratual",
        })
        for col in ["inicio", "termino"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # realizado_pct — média ponderada por peso_pct
        if "projeto" in data and not data["projeto"].empty:
            ativ = data["projeto"]
            if "conclusao_pct" in ativ.columns and "contrato" in ativ.columns:
                ativ = ativ.copy()
                ativ["conclusao_pct"] = pd.to_numeric(ativ["conclusao_pct"], errors="coerce").fillna(0)
                if "peso_pct" in ativ.columns:
                    ativ["peso_pct"] = pd.to_numeric(ativ["peso_pct"], errors="coerce").fillna(1)
                    grp = ativ.groupby("contrato").apply(
                        lambda g: (g["conclusao_pct"] * g["peso_pct"]).sum() / g["peso_pct"].sum()
                        if g["peso_pct"].sum() > 0 else 0
                    ).reset_index(name="realizado_pct")
                else:
                    grp = ativ.groupby("contrato")["conclusao_pct"].mean().reset_index(name="realizado_pct")
                df = df.merge(grp, on="contrato", how="left")
                df["realizado_pct"] = df["realizado_pct"].fillna(0).round(1)

        if "realizado_pct" not in df.columns:
            df["realizado_pct"] = 0.0

        # previsto_pct — % do prazo decorrido
        today = pd.Timestamp(_date.today())
        if "inicio" in df.columns and "termino" in df.columns:
            duracao = (df["termino"] - df["inicio"]).dt.days.clip(lower=1)
            decorrido = (today - df["inicio"]).dt.days.clip(lower=0)
            df["previsto_pct"] = (decorrido / duracao * 100).clip(0, 100).round(1).fillna(0)
        else:
            df["previsto_pct"] = 0.0

        # budget — soma de fin_custos por contrato
        if "financeiro" in data and not data["financeiro"].empty:
            fin = data["financeiro"]
            if "valor_previsto" in fin.columns and "contrato" in fin.columns:
                bgt = fin.groupby("contrato").agg(
                    budget_planejado=("valor_previsto", "sum"),
                    budget_realizado=("valor_executado", "sum"),
                ).reset_index()
                df = df.merge(bgt, on="contrato", how="left")

        df["budget_planejado"] = df.get("budget_planejado", pd.Series(0.0, index=df.index)).fillna(0)
        df["budget_realizado"] = df.get("budget_realizado", pd.Series(0.0, index=df.index)).fillna(0)

        data["obras"] = df
        logger.info(f"Obras computadas: {len(df)} contratos")
        return data

    def _norm_financeiro(self, data: dict) -> dict:
        if "financeiro" not in data or data["financeiro"].empty:
            return data
        df = data["financeiro"]
        for col in ("valor_previsto", "valor_executado"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        data["financeiro"] = df
        return data

    def _norm_om(self, data: dict) -> dict:
        if "om" not in data or data["om"].empty:
            return data
        df = data["om"]
        rename = {}
        for col in df.columns:
            cl = _strip_accents(col).lower()
            if cl in ("data", "data_referencia"):                    rename[col] = "data"
            elif cl == "contrato":                                    rename[col] = "contrato"
            elif cl == "projeto":                                     rename[col] = "projeto"
            elif cl == "cliente":                                     rename[col] = "cliente"
            elif cl == "terceirizado":                                rename[col] = "terceirizado"
            elif "localiza" in cl:                                    rename[col] = "localizacao"
            elif "gera" in cl and "prevista" in cl:                  rename[col] = "geracao_prevista_kwh"
            elif "energia" in cl and "injetada" in cl:               rename[col] = "energia_injetada_kwh"
            elif "compensado" in cl or ("kwh" in cl and "compens" in cl): rename[col] = "compensado_kwh"
            elif "acumulado" in cl or ("kwh" in cl and "acumul" in cl):   rename[col] = "acumulado_kwh"
            elif "valor" in cl and "faturado" in cl:                 rename[col] = "valor_faturado"
            elif "gest" in cl:                                       rename[col] = "gestao"
            elif "liquido" in cl or ("fat" in cl and "liq" in cl):  rename[col] = "faturamento_liquido"
        df = df.rename(columns=rename)
        if "data" in df.columns:
            df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
            df["mes_ano"] = df["data"].dt.strftime("%m/%Y")
        for col in ["geracao_prevista_kwh","energia_injetada_kwh","compensado_kwh",
                    "acumulado_kwh","valor_faturado","gestao","faturamento_liquido"]:
            if col in df.columns:
                df[col] = df[col].apply(_parse_brl)
        data["om"] = df
        return data

    def _crossref_valor_contratado(self, data: dict) -> dict:
        if "contratos" not in data:
            return data
        con = data["contratos"]
        if "valor_contratado" not in con.columns:
            con["valor_contratado"] = 0.0
        if "financeiro" in data and not data["financeiro"].empty:
            fin = data["financeiro"]
            if "valor_previsto" in fin.columns and "contrato" in fin.columns:
                totals = fin.groupby("contrato")["valor_previsto"].sum().reset_index()
                totals.columns = ["contrato", "valor_total"]
                valor_map = dict(zip(totals["contrato"], totals["valor_total"]))
                con["valor_contratado"] = con["contrato"].map(valor_map).fillna(con["valor_contratado"])
        data["contratos"] = con
        return data

    def _crossref_status(self, data: dict) -> dict:
        if "contratos" not in data or "obras" not in data or data["obras"].empty:
            return data
        obras = data["obras"]
        con = data["contratos"]
        if "realizado_pct" in obras.columns and "contrato" in obras.columns:
            avg_real = obras.groupby("contrato")["realizado_pct"].mean().reset_index()
            status_map = {}
            for _, row in avg_real.iterrows():
                if row["realizado_pct"] >= 100:
                    status_map[row["contrato"]] = "Concluído"
                elif row["realizado_pct"] > 0:
                    status_map[row["contrato"]] = "Em Execução"
                else:
                    status_map[row["contrato"]] = "Em Planejamento"
            con["status"] = con["contrato"].map(status_map).fillna("Em Planejamento")
            data["contratos"] = con
        return data

    # ── Utilidade ────────────────────────────────────────────────────────────

    def _tid(self) -> str:
        return self.client_id[:8] if self.client_id else "global"
