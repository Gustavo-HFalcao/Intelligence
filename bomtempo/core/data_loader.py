"""
Carregamento e normalização de dados — Usando APENAS dados reais da planilha.
"""

import os
import pickle
import tempfile
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from bomtempo.core.logging_utils import get_logger
from bomtempo.core.supabase_client import sb_select

logger = get_logger(__name__)

# Cache absoluto completamente FORA do diretório do projeto
# Isso garante 100% que o Reflex (watchfiles) não vai dar hot-reload ao deletar/salvar o cache
CACHE_TTL = 3600  # 1 hora

# Tabelas globais — lidas sem filtro de client_id
GLOBAL_TABLES = {"clients", "roles"}


def _cache_path(client_id: str = "") -> str:
    """Retorna caminho de cache separado por tenant."""
    safe_id = (client_id[:8] if client_id else "global").replace("-", "")
    return os.path.join(tempfile.gettempdir(), f"bomtempo_cache_{safe_id}.pkl")


def _strip_accents(text: str) -> str:
    """Remove acentos para comparação segura de colunas."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _parse_brl(val) -> float:
    """Converte 'R$ 80.000,00' ou '4.661.063 kWh' para float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()

    # Remove tudo que não for número, ponto ou vírgula (ex: " R$", " kWh")
    import re

    s = re.sub(r"[^\d,.-]", "", s)

    if s in ("-", "", "—", "–"):
        return 0.0

    # BRL: "80.000,00" → "80000.00"
    # Note: we assume DD.MMM,CC format.
    # If there is a comma, it's the decimal separator.
    if "," in s:
        s = s.replace(".", "").replace(",", ".")

    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


class DataLoader:
    """Carrega e normaliza todas as planilhas"""

    def __init__(self, client_id: str = ""):
        self.client_id = client_id

    def load_all(self) -> dict:
        """Carrega todos os dados (Redis Cache -> Pickle Cache -> Supabase), normaliza e retorna."""
        from bomtempo.core.redis_cache import cache_get, cache_set, is_redis_available
        data = {}

        # 1. Tentar Redis cache (primário — sobrevive a restarts, TTL gerenciado automaticamente)
        cached = cache_get(self.client_id, "data_all")
        if cached:
            logger.info(f"⚡ Dados carregados do Redis tenant={self.client_id[:8] if self.client_id else 'global'}")
            return cached

        # 2. Tentar pickle file cache (fallback quando Redis não disponível)
        cached = self._try_load_cache(fresh_only=True)
        if cached:
            logger.info(f"✅ Dados carregados do Cache (pickle) tenant={self.client_id[:8] if self.client_id else 'global'}")
            return cached

        # 2. Carregar do Supabase em paralelo
        logger.info(f"Carregando dados do Supabase — tenant={self.client_id[:8] if self.client_id else 'global'}...")
        # (table_name_in_db, state_key)
        TABLE_MAP = [
            ("contratos",              "contratos"),
            ("hub_atividades",         "projeto"),
            ("hub_atividade_historico","hub_historico"),
            ("fin_custos",             "financeiro"),
            ("om_geracoes",            "om"),
        ]
        # "obras" será derivado de contratos + hub_atividades + fin_custos abaixo
        sucesso = False

        def _fetch(table: str, key: str):
            if self.client_id:
                rows = sb_select(table, filters={"client_id": self.client_id})
            else:
                rows = sb_select(table)
            return key, rows

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(_fetch, t, k): (t, k) for t, k in TABLE_MAP}
            for future in as_completed(futures):
                t, k = futures[future]
                try:
                    key, rows = future.result()
                    if rows:
                        data[key] = pd.DataFrame(rows)
                        logger.info(f"  {key}: {len(rows)} linhas (Supabase)")
                        sucesso = True
                    else:
                        data[key] = pd.DataFrame()
                        if self.client_id:
                            logger.info(f"  {key}: sem dados para este tenant ainda")
                        else:
                            logger.warning(f"  {key}: tabela vazia no Supabase")
                except Exception as e:
                    logger.error(f"Erro ao carregar {t} do Supabase: {e}")
                    data[k] = pd.DataFrame()

        # Fallbacks antigos foram removidos conforme instrução.

        # 3. Normalizar colunas
        data = self._normalize_all(data)

        # 4. Salvar cache — Redis (primário) + pickle (fallback)
        if sucesso:
            from bomtempo.core.redis_cache import cache_set, CACHE_TTL_SECONDS
            saved_redis = cache_set(self.client_id, "data_all", data, ttl=CACHE_TTL_SECONDS)
            if not saved_redis:
                self._save_cache(data)  # fallback para pickle se Redis indisponível

        logger.info("✅ Carga de dados concluída")
        return data

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def invalidate_cache(client_id: str = ""):
        """Remove cache do tenant (Redis + pickle) — força recarga do Supabase na próxima requisição."""
        # 1. Invalida Redis (primário)
        try:
            from bomtempo.core.redis_cache import cache_invalidate
            cache_invalidate(client_id, "data_all")
        except Exception as e:
            logger.debug(f"Redis invalidate falhou (ok se Redis não configurado): {e}")

        # 2. Invalida pickle file (fallback)
        try:
            path = _cache_path(client_id)
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"🗑️ Cache pickle invalidado — tenant={client_id[:8] if client_id else 'global'}")
        except Exception as e:
            logger.warning(f"Falha ao invalidar cache pickle: {e}")

    def _try_load_cache(self, fresh_only: bool = True):
        path = _cache_path(self.client_id)
        if not os.path.exists(path):
            return None
        try:
            if fresh_only:
                mtime = os.path.getmtime(path)
                if (time.time() - mtime) >= CACHE_TTL:
                    return None
            with open(path, "rb") as f:
                data = pickle.load(f)
            if data and isinstance(data, dict):
                return data
        except Exception as e:
            logger.warning(f"Erro ao ler cache: {e}")
        return None

    def _save_cache(self, data: dict):
        try:
            path = _cache_path(self.client_id)
            with open(path, "wb") as f:
                pickle.dump(data, f)
            logger.info("Cache atualizado (dados normalizados)")
        except Exception as e:
            logger.error(f"Erro ao salvar cache: {e}")

    # ── Normalização ──────────────────────────────────────────────

    def _normalize_all(self, data: dict) -> dict:
        """Normaliza colunas reais para snake_case usado no código."""

        # ── Contratos ────────────────────────────────────────────
        if "contratos" in data and not data["contratos"].empty:
            df = data["contratos"]
            rename = {}
            for col in df.columns:
                cl = _strip_accents(col).lower()
                if cl == "projeto":
                    rename[col] = "projeto"
                elif cl == "contrato":
                    rename[col] = "contrato"
                elif cl == "cliente":
                    rename[col] = "cliente"
                elif cl == "terceirizado":
                    rename[col] = "terceirizado"
                elif "localiza" in cl:
                    rename[col] = "localizacao"
                elif "valor" in cl and "contratado" in cl:
                    rename[col] = "valor_contratado"
                elif cl == "status":
                    rename[col] = "status"
            df = df.rename(columns=rename)

            if "valor_contratado" not in df.columns:
                df["valor_contratado"] = 0.0
            if "status" not in df.columns:
                df["status"] = "Em Execução"

            data["contratos"] = df

        # ── Projeto (hub_atividades) ──────────────────────────────
        if "projeto" in data and not data["projeto"].empty:
            df = data["projeto"]
            rename = {}
            for col in df.columns:
                cl = _strip_accents(col).lower()
                if cl == "id":
                    rename[col] = "id"
                elif cl == "fase":
                    rename[col] = "fase"
                elif cl == "atividade":
                    rename[col] = "atividade"
                elif cl == "critico":
                    rename[col] = "critico"
                elif cl == "data_inicio":
                    rename[col] = "inicio_previsto"
                elif cl == "data_termino":
                    rename[col] = "termino_previsto"
                elif "conclusao" in cl:
                    rename[col] = "conclusao_pct"
                elif cl == "dependencia":
                    rename[col] = "dependencia"
                elif cl == "responsavel":
                    rename[col] = "responsavel"
                elif cl == "contrato":
                    rename[col] = "contrato"
                elif cl == "fase_macro":
                    rename[col] = "fase_macro"
                elif cl in ("peso_pct", "weight"):
                    rename[col] = "peso_pct"
                elif cl == "nivel":
                    rename[col] = "nivel"
                elif cl == "parent_id":
                    rename[col] = "parent_id"
            df = df.rename(columns=rename)
            # hub_atividades não tem coluna "critico" — garantir que existe
            if "critico" not in df.columns:
                df["critico"] = "Nao"
            for col in ["inicio_previsto", "termino_previsto"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
            if "conclusao_pct" in df.columns:
                df["conclusao_pct"] = pd.to_numeric(df["conclusao_pct"], errors="coerce").fillna(0)
            # Filtrar apenas atividades não-pendentes para dashboards globais
            if "pendente_aprovacao" in df.columns:
                df = df[df["pendente_aprovacao"].astype(str) != "1"].copy()
            data["projeto"] = df

        # ── Obras ────────────────────────────────────────────────
        # ── Obras: derivado de contratos + hub_atividades + fin_custos ──────────
        # Não há mais tabela "projects" — tudo é computado em tempo real.
        if "contratos" in data and not data["contratos"].empty:
            from datetime import date as _date
            import numpy as np

            df = data["contratos"].copy()

            # Renomear colunas para padrão interno usado pelo global_state
            df = df.rename(columns={
                "data_inicio":          "inicio",
                "data_termino":         "termino",
                "prazo_contratual_dias": "prazo_contratual",
            })

            for date_col in ["inicio", "termino"]:
                if date_col in df.columns:
                    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

            # ── realizado_pct: média ponderada de conclusao_pct de hub_atividades ──
            if "projeto" in data and not data["projeto"].empty:
                ativ = data["projeto"]
                if "conclusao_pct" in ativ.columns and "contrato" in ativ.columns:
                    ativ = ativ.copy()
                    ativ["conclusao_pct"] = pd.to_numeric(ativ["conclusao_pct"], errors="coerce").fillna(0)
                    peso_col = "peso_pct" if "peso_pct" in ativ.columns else None
                    if peso_col:
                        ativ["peso_pct"] = pd.to_numeric(ativ[peso_col], errors="coerce").fillna(1)
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

            # ── previsto_pct: % do prazo decorrido até hoje ──
            today = pd.Timestamp(_date.today())
            if "inicio" in df.columns and "termino" in df.columns:
                duracao = (df["termino"] - df["inicio"]).dt.days.clip(lower=1)
                decorrido = (today - df["inicio"]).dt.days.clip(lower=0)
                df["previsto_pct"] = (decorrido / duracao * 100).clip(0, 100).round(1)
                df["previsto_pct"] = df["previsto_pct"].fillna(0)
            else:
                df["previsto_pct"] = 0.0

            # ── budget: sum de fin_custos por contrato ──
            if "financeiro" in data and not data["financeiro"].empty:
                fin = data["financeiro"]
                if "valor_previsto" in fin.columns and "contrato" in fin.columns:
                    bgt = fin.groupby("contrato").agg(
                        budget_planejado=("valor_previsto", "sum"),
                        budget_realizado=("valor_executado", "sum"),
                    ).reset_index()
                    df = df.merge(bgt, on="contrato", how="left")
                    df["budget_planejado"] = df["budget_planejado"].fillna(0)
                    df["budget_realizado"] = df["budget_realizado"].fillna(0)

            if "budget_planejado" not in df.columns:
                df["budget_planejado"] = 0.0
            if "budget_realizado" not in df.columns:
                df["budget_realizado"] = 0.0

            data["obras"] = df
            logger.info(f"Obras computadas: {len(df)} contratos | campos: realizado_pct, previsto_pct, budget")

        # ── Financeiro (fin_custos) ───────────────────────────────
        # Fonte: tabela fin_custos — valor_previsto / valor_executado / status / data
        # Normalização de tipos numéricos
        if "financeiro" in data and not data["financeiro"].empty:
            df = data["financeiro"]
            for col in ("valor_previsto", "valor_executado"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            data["financeiro"] = df

        # ── O&M ──────────────────────────────────────────────────
        if "om" in data and not data["om"].empty:
            df = data["om"]
            rename = {}
            for col in df.columns:
                cl = _strip_accents(col).lower()
                if cl in ("data", "data_referencia"):
                    rename[col] = "data"
                elif cl == "contrato":
                    rename[col] = "contrato"
                elif cl == "projeto":
                    rename[col] = "projeto"
                elif cl == "cliente":
                    rename[col] = "cliente"
                elif cl == "terceirizado":
                    rename[col] = "terceirizado"
                elif "localiza" in cl:
                    rename[col] = "localizacao"
                elif "gera" in cl and "prevista" in cl:
                    rename[col] = "geracao_prevista_kwh"
                elif "energia" in cl and "injetada" in cl:
                    rename[col] = "energia_injetada_kwh"
                elif "compensado" in cl or ("kwh" in cl and "compens" in cl):
                    rename[col] = "compensado_kwh"
                elif "acumulado" in cl or ("kwh" in cl and "acumul" in cl):
                    rename[col] = "acumulado_kwh"
                elif "valor" in cl and "faturado" in cl:
                    rename[col] = "valor_faturado"
                elif "gest" in cl:
                    rename[col] = "gestao"
                elif ("liquido" in cl) or ("fat" in cl and "liq" in cl):
                    rename[col] = "faturamento_liquido"

            df = df.rename(columns=rename)

            if "data" in df.columns:
                df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
                df["mes_ano"] = df["data"].dt.strftime("%m/%Y")

            # Parse numeric/money columns
            num_cols = [
                "geracao_prevista_kwh",
                "energia_injetada_kwh",
                "compensado_kwh",
                "acumulado_kwh",
                "valor_faturado",
                "gestao",
                "faturamento_liquido",
            ]
            for col in num_cols:
                if col in df.columns:
                    df[col] = df[col].apply(_parse_brl)

            data["om"] = df

        # Login agora vem do Supabase — não precisa normalizar a sheet

        # ── Cross-reference: valor_contratado from fin_custos ───
        if "contratos" in data:
            con = data["contratos"]
            if "valor_contratado" not in con.columns:
                con["valor_contratado"] = 0.0

            if "financeiro" in data and not data["financeiro"].empty:
                fin = data["financeiro"]
                if "valor_previsto" in fin.columns and "contrato" in fin.columns:
                    totals = fin.groupby("contrato")["valor_previsto"].sum().reset_index()
                    totals.columns = ["contrato", "valor_total"]
                    valor_map = dict(zip(totals["contrato"], totals["valor_total"]))
                    logger.info(f"Cross-ref fin_custos→contratos: {len(valor_map)} contratos")
                    con["valor_contratado"] = con["contrato"].map(valor_map).fillna(con["valor_contratado"])

            data["contratos"] = con

        # ── Cross-reference: status from obras ───────────────────
        if "contratos" in data and "obras" in data and not data["obras"].empty:
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

        # RDO sheets removidos — dados agora vêm do Supabase via rdo_service.py

        return data
