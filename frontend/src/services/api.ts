/**
 * API base client — Bomtempo Frontend
 * Todas as chamadas ao backend FastAPI passam por aqui.
 * Credenciais (cookie httpOnly) são enviadas automaticamente via withCredentials.
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,  // envia o cookie bomtempo_session em toda request
  headers: {
    'Content-Type': 'application/json',
  },
})

let _loggingOut = false

export function setLoggingOut(v: boolean) { _loggingOut = v }

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
