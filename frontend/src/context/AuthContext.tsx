/**
 * AuthContext — Bomtempo Frontend
 * Gerencia autenticação global: login, logout, sessão persistida.
 * Substitui as variáveis de auth do GlobalState (current_user_id, current_user_role, etc.).
 */
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import api from '@/services/api'

export interface User {
  user_id: string
  login: string
  email: string
  role_name: string
  client_id: string | null
  client_name: string | null
  is_master: boolean
  allowed_modules: string[]
  avatar_icon?: string
  whatsapp?: string
}

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  isPremiumLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isPremiumLoading, setIsPremiumLoading] = useState(false)

  // Rehydrata sessão ao montar (verifica cookie existente)
  useEffect(() => {
    api.get<User>('/auth/me')
      .then((res) => setUser(res.data))
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post<User>('/auth/login', { email, password })
    
    // Inicia sequência premium de 5.5s (Paridade 1:1)
    setIsPremiumLoading(true)
    setUser(res.data)
    
    setTimeout(() => {
      setIsPremiumLoading(false)
    }, 5500)
  }, [])

  const logout = useCallback(async () => {
    await api.post('/auth/logout')
    setUser(null)
    setIsPremiumLoading(false)
  }, [])

  return (
    <AuthContext.Provider value={{ 
      user, 
      isLoading, 
      isPremiumLoading,
      isAuthenticated: !!user, 
      login, 
      logout 
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
