"""
Master State — BTP MASTER tenant dashboard state.
Loads cross-tenant stats from the master_stats view.
Manages tenant creation + cross-tenant user listing.
"""
from __future__ import annotations

from typing import Dict, List

import reflex as rx

from bomtempo.core.logging_utils import get_logger
from bomtempo.core.supabase_client import sb_insert, sb_select
from bomtempo.state.global_state import GlobalState

logger = get_logger(__name__)


class MasterState(rx.State):
    """Estado da Master Console — visão global multi-tenant."""

    # ── Tenant list ───────────────────────────────────────────────
    tenants: List[Dict] = []
    is_loading: bool = False

    # ── Users across all tenants ──────────────────────────────────
    all_users: List[Dict] = []
    users_loading: bool = False

    # ── Create tenant modal ───────────────────────────────────────
    show_create_modal: bool = False
    new_tenant_name: str = ""
    new_tenant_budget: str = "100"
    new_admin_username: str = ""
    new_admin_password: str = ""
    create_error: str = ""
    is_creating: bool = False

    # ── Handlers: create modal ────────────────────────────────────
    def open_create_modal(self):
        self.show_create_modal = True
        self.new_tenant_name = ""
        self.new_tenant_budget = "100"
        self.new_admin_username = ""
        self.new_admin_password = ""
        self.create_error = ""

    def close_create_modal(self):
        self.show_create_modal = False

    def set_new_tenant_name(self, v: str): self.new_tenant_name = v
    def set_new_tenant_budget(self, v: str): self.new_tenant_budget = v
    def set_new_admin_username(self, v: str): self.new_admin_username = v
    def set_new_admin_password(self, v: str): self.new_admin_password = v

    # ── Load page ─────────────────────────────────────────────────
    async def load_page(self):
        """Carrega stats de todos os tenants. Guard via get_state."""
        gs = await self.get_state(GlobalState)
        if not gs.client_is_master:
            yield rx.redirect("/")
            return

        self.is_loading = True
        self.users_loading = True
        yield

        await self._fetch_tenants()
        await self._fetch_all_users()

        self.is_loading = False
        self.users_loading = False

    async def _fetch_tenants(self):
        try:
            rows = sb_select("master_stats") or []
            self.tenants = [
                {
                    "client_id":     str(r.get("client_id", "")),
                    "client_name":   str(r.get("client_name", "")),
                    "is_master":     str(r.get("is_master", False)),
                    "status":        str(r.get("status", "active")),
                    "ai_budget":     str(r.get("ai_budget", "100")),
                    "user_count":    str(r.get("user_count", 0)),
                    "total_logs":    str(r.get("total_logs", 0)),
                    "session_count": str(r.get("session_count", 0)),
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"_fetch_tenants error: {e}")
            self.tenants = []

    async def _fetch_all_users(self):
        try:
            rows = sb_select("login", order="username") or []
            # Carrega mapa client_id → name
            clients = sb_select("clients") or []
            client_map = {str(c.get("id", "")): str(c.get("name", "—")) for c in clients}
            self.all_users = [
                {
                    "id":          str(r.get("id", "")),
                    "username":    str(r.get("username", "")),
                    "user_role":   str(r.get("user_role", "")),
                    "client_id":   str(r.get("client_id", "")),
                    "client_name": client_map.get(str(r.get("client_id", "")), "—"),
                    "email":       str(r.get("email", "") or ""),
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"_fetch_all_users error: {e}")
            self.all_users = []

    # ── Create tenant ─────────────────────────────────────────────
    async def create_tenant(self):
        """Cria novo tenant + usuário administrador vinculado."""
        name = self.new_tenant_name.strip()
        admin_user = self.new_admin_username.strip()
        admin_pw = self.new_admin_password.strip()

        if not name:
            self.create_error = "Nome do cliente é obrigatório."
            return
        if not admin_user:
            self.create_error = "Login do administrador é obrigatório."
            return
        if not admin_pw:
            self.create_error = "Senha do administrador é obrigatória."
            return

        try:
            budget = float(self.new_tenant_budget or "100")
        except ValueError:
            budget = 100.0

        self.is_creating = True
        self.create_error = ""
        yield

        try:
            # 1. Cria o tenant
            tenant = sb_insert("clients", {
                "name":      name,
                "is_master": False,
                "ai_budget": budget,
                "status":    "active",
            })
            if not tenant:
                self.create_error = "Falha ao criar tenant no banco."
                return

            new_client_id = str(tenant.get("id", ""))

            # 2. Cria role "Administrador" com acesso total para o novo tenant
            #    (outras roles podem ser criadas depois pelo admin do tenant)
            sb_insert("roles", {
                "name": "Administrador",
                "modules": ["visao_geral", "obras", "projetos", "financeiro", "om",
                            "relatorios", "chat_ia", "reembolso_dash", "rdo_dashboard",
                            "alertas", "logs_auditoria", "gerenciar_usuarios"],
                "icon": "user",
                "client_id": new_client_id,
            })

            # 3. Cria usuário admin vinculado ao tenant
            from bomtempo.core.auth_utils import hash_password
            sb_insert("login", {
                "username":  admin_user,
                "password":  hash_password(admin_pw),
                "user_role": "Administrador",
                "client_id": new_client_id,
            })

            logger.info(f"Tenant '{name}' criado com ID={new_client_id}, admin='{admin_user}'")

            self.show_create_modal = False
            yield rx.toast(f"✅ Tenant '{name}' criado com sucesso!", position="top-center")

            # Recarrega dados
            await self._fetch_tenants()
            await self._fetch_all_users()

        except Exception as e:
            logger.error(f"create_tenant error: {e}")
            self.create_error = f"Erro: {str(e)[:120]}"
        finally:
            self.is_creating = False
