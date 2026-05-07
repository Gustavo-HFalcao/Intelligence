/**
 * API base client — Bomtempo Frontend
 * Todas as chamadas ao backend FastAPI passam por aqui.
 *
 * Autenticação por aba:
 *   O token de sessão é armazenado em sessionStorage (isolado por aba).
 *   Cada request envia "Authorization: Bearer <token>" para que o backend
 *   use a sessão específica desta aba, não o cookie global do browser.
 *   O cookie é mantido como fallback para compatibilidade.
 */
import axios from 'axios'

const SESSION_KEY = 'bti_session_token'

export function storeSessionToken(token: string) {
  sessionStorage.setItem(SESSION_KEY, token)
}

export function clearSessionToken() {
  sessionStorage.removeItem(SESSION_KEY)
}

export function getSessionToken(): string | null {
  return sessionStorage.getItem(SESSION_KEY)
}

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

let _loggingOut = false
export function setLoggingOut(v: boolean) { _loggingOut = v }

// Injeta Authorization header com o token da aba atual
api.interceptors.request.use((config) => {
  const token = getSessionToken()
  if (token) {
    config.headers = config.headers ?? {}
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// Redireciona para /login em caso de 401, exceto em auth routes e durante logout
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const url = err.config?.url ?? ''
    const is401 = err.response?.status === 401
    const isAuthRoute = url.includes('/auth/')
    if (is401 && !isAuthRoute && !_loggingOut && window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
