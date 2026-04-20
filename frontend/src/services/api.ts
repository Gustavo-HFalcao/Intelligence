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

// Redireciona para /login em caso de 401, exceto na verificação de sessão inicial
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const url = err.config?.url ?? ''
    const is401 = err.response?.status === 401
    const isSessionCheck = url.includes('/auth/me')
    if (is401 && !isSessionCheck && window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
