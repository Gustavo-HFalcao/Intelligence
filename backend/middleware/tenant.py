"""
Tenant middleware — Bomtempo Backend (FastAPI)
Resolve o client_id do usuário autenticado e injeta no contexto da request.

O tenant é identificado pelo campo client_id na tabela login,
carregado na sessão durante o login — sem header adicional, sem subdomain.
Portado da lógica de isolamento do GlobalState (self.current_client_id).
"""

from typing import Optional

from fastapi import Depends, HTTPException, status

from backend.middleware.auth import get_current_user


async def get_current_tenant(user: dict = Depends(get_current_user)) -> Optional[str]:
    """Dependency: retorna o client_id do usuário autenticado.

    Retorna None apenas para usuários master (acesso global — sem filtro de tenant).
    Todas as queries de serviço devem filtrar por este valor:
        sb_select("contratos", filters={"client_id": tenant_id})
    """
    return user.get("client_id")


async def require_tenant(user: dict = Depends(get_current_user)) -> str:
    """Dependency: garante que o usuário tem um tenant válido.
    Lança 403 se client_id for None (não deve acontecer em condições normais).
    """
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem tenant associado",
        )
    return client_id
