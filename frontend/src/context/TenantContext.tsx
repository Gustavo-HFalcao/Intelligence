/**
 * TenantContext + useTenant hook — Bomtempo Frontend
 * Expõe client_id, role_name e feature flags do usuário autenticado.
 * Substitui as vars de tenant do GlobalState (current_client_id, rdo_active_features, etc.).
 */
import React, { createContext, useContext, useMemo } from 'react'
import { useAuth } from '@/context/AuthContext'

// Roles idênticos ao Reflex (sem renomear)
export type Role = 'Administrador' | 'Engenheiro' | 'Gestão-Mobile' | 'Operário' | string

export interface TenantContextValue {
  clientId: string | null
  clientName: string | null
  role: Role
  isMaster: boolean
  allowedModules: string[]
  hasRole: (...roles: Role[]) => boolean
  hasModule: (module: string) => boolean
}

const TenantContext = createContext<TenantContextValue | null>(null)

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()

  const value = useMemo<TenantContextValue>(() => {
    const modules = user?.allowed_modules ?? []
    return {
      clientId:       user?.client_id ?? null,
      clientName:     user?.client_name ?? null,
      role:           user?.role_name ?? '',
      isMaster:       user?.is_master ?? false,
      allowedModules: modules,
      hasRole:        (...roles: Role[]) => roles.includes(user?.role_name ?? ''),
      hasModule:      (mod: string) => modules.includes(mod),
    }
  }, [user])

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
}

export function useTenant() {
  const ctx = useContext(TenantContext)
  if (!ctx) throw new Error('useTenant must be used within TenantProvider')
  return ctx
}
