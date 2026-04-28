/**
 * App.tsx — React Router v6
 * Espelha exatamente as 31 rotas do Reflex (@rx.page).
 */
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useTenant } from '@/context/TenantContext'

import Login           from '@/pages/Login'
import Dashboard       from '@/pages/Dashboard'
import HubOperacoes    from '@/pages/HubOperacoes'
import RDOForm         from '@/pages/RDOForm'
import RDOView         from '@/pages/RDOView'
import RDOHistorico    from '@/pages/RDOHistorico'
import RDODashboard    from '@/pages/RDODashboard'
import Financeiro      from '@/pages/Financeiro'
import ChatIA          from '@/pages/ChatIA'
import Alertas         from '@/pages/Alertas'
import Relatorios      from '@/pages/Relatorios'
import ReembolsoDashboard from '@/pages/ReembolsoDashboard'
import ReembolsoForm   from '@/pages/ReembolsoForm'
import Usuarios        from '@/pages/Usuarios'
import Perfil          from '@/pages/Perfil'
import MasterConsole   from '@/pages/MasterConsole'
import Analytics       from '@/pages/Analytics'
import Previsoes       from '@/pages/Previsoes'
import OM              from '@/pages/OM'
import LogsAuditoria   from '@/pages/LogsAuditoria'
import Observabilidade from '@/pages/Observabilidade'
import Projetos        from '@/pages/Projetos'
import FeatureFlags    from '@/pages/FeatureFlags'
import Obras           from '@/pages/Obras'
import EditorDados     from '@/pages/EditorDados'
import AppMobile       from '@/pages/AppMobile'
import MobileChat      from '@/pages/MobileChat'

import MainLayout from '@/components/MainLayout'

import LoadingScreen from '@/components/LoadingScreen'

// Mapa de módulo → rota (para redirect dinâmico)
const MODULE_ROUTES: Record<string, string> = {
  visao_geral:        '/',
  obras:              '/hub',
  financeiro:         '/financeiro',
  analytics:          '/analytics',
  alertas:            '/alertas',
  relatorios:         '/relatorios',
  om:                 '/om',
  chat_ia:            '/chat-ia',
  gerenciar_usuarios: '/usuarios',
  previsoes:          '/previsoes',
  logs_auditoria:     '/logs-auditoria',
  rdo_form:           '/rdo-form',
  rdo_historico:      '/rdo-historico',
  rdo_dashboard:      '/rdo-dashboard',
  reembolso:          '/reembolso-form',
  reembolso_dash:     '/reembolso-dashboard',
}

// Prioridade de landing page por módulo (ordem preferencial)
const MODULE_PRIORITY = [
  'visao_geral', 'obras', 'rdo_historico', 'rdo_form', 'rdo_dashboard',
  'financeiro', 'analytics', 'om', 'alertas', 'relatorios', 'chat_ia',
  'previsoes', 'reembolso_dash', 'reembolso', 'logs_auditoria', 'gerenciar_usuarios',
]

function getFirstAllowedRoute(allowedModules: string[]): string {
  if (!allowedModules?.length) return '/'
  for (const mod of MODULE_PRIORITY) {
    if (allowedModules.includes(mod)) return MODULE_ROUTES[mod] ?? '/'
  }
  return '/rdo-historico'
}

function PrivateRoute({ children, module }: { children: React.ReactNode; module?: string }) {
  const { isAuthenticated, isLoading, isPremiumLoading, user } = useAuth()
  const { hasModule } = useTenant()

  if (isLoading || isPremiumLoading) return <LoadingScreen />
  if (!isAuthenticated) return <Navigate to="/login" replace />

  // Module guard: se o usuário não tem acesso ao módulo, redireciona para o primeiro módulo permitido
  if (module && user?.allowed_modules?.length && !hasModule(module)) {
    const fallback = getFirstAllowedRoute(user.allowed_modules)
    return <Navigate to={fallback} replace />
  }

  return <>{children}</>
}

// Redirect após login baseado nos módulos permitidos do usuário
function RoleRedirect() {
  const { user, isLoading, isPremiumLoading } = useAuth()

  if (isLoading || isPremiumLoading) return <LoadingScreen />
  if (!user) return <Navigate to="/login" replace />

  // landing_page configurada no perfil tem prioridade
  if (user.landing_page) return <Navigate to={user.landing_page} replace />

  // Se tem allowed_modules, vai para o primeiro disponível
  if (user.allowed_modules?.length) {
    const target = getFirstAllowedRoute(user.allowed_modules)
    if (target !== '/') return <Navigate to={target} replace />
  }

  return null // sem restrições: fica no dashboard (visao_geral)
}

function WithLayout({ children, module }: { children: React.ReactNode; module?: string }) {
  return (
    <PrivateRoute module={module}>
      <MainLayout>
        {children}
      </MainLayout>
    </PrivateRoute>
  )
}

export default function App() {
  return (
    <Routes>
      {/* Público */}
      <Route path="/login"         element={<Login />} />
      <Route path="/rdo/:token"    element={<RDOView />} />

      {/* Protegido — com sidebar/topbar */}
      <Route path="/"                   element={<><RoleRedirect /><WithLayout module="visao_geral"><Dashboard /></WithLayout></>} />
      <Route path="/hub"                element={<WithLayout module="obras"><HubOperacoes /></WithLayout>} />
      <Route path="/financeiro"         element={<WithLayout module="financeiro"><Financeiro /></WithLayout>} />
      <Route path="/analytics"          element={<WithLayout module="analytics"><Analytics /></WithLayout>} />
      <Route path="/alertas"            element={<WithLayout module="alertas"><Alertas /></WithLayout>} />
      <Route path="/relatorios"         element={<WithLayout module="relatorios"><Relatorios /></WithLayout>} />
      <Route path="/om"                 element={<WithLayout module="om"><OM /></WithLayout>} />
      <Route path="/chat-ia"            element={<WithLayout module="chat_ia"><ChatIA /></WithLayout>} />
      <Route path="/usuarios"           element={<WithLayout module="gerenciar_usuarios"><Usuarios /></WithLayout>} />
      <Route path="/perfil"             element={<WithLayout><Perfil /></WithLayout>} />
      <Route path="/master-console"     element={<WithLayout><MasterConsole /></WithLayout>} />
      <Route path="/previsoes"          element={<WithLayout module="previsoes"><Previsoes /></WithLayout>} />
      <Route path="/logs-auditoria"     element={<WithLayout module="logs_auditoria"><LogsAuditoria /></WithLayout>} />
      <Route path="/observabilidade"    element={<WithLayout module="gerenciar_usuarios"><Observabilidade /></WithLayout>} />
      <Route path="/contract-features"  element={<WithLayout module="gerenciar_usuarios"><FeatureFlags /></WithLayout>} />
      <Route path="/reembolso-dashboard" element={<WithLayout module="reembolso_dash"><ReembolsoDashboard /></WithLayout>} />
      <Route path="/rdo-dashboard"      element={<WithLayout module="rdo_dashboard"><RDODashboard /></WithLayout>} />

      {/* Protegido — sem sidebar (full-screen forms / mobile) */}
      <Route path="/rdo-form"       element={<PrivateRoute module="rdo_form"><div className="min-h-screen bg-bg-void p-4 md:p-6"><RDOForm /></div></PrivateRoute>} />
      <Route path="/rdo-historico"  element={<PrivateRoute module="rdo_historico"><div className="min-h-screen bg-bg-void p-4 md:p-6"><RDOHistorico /></div></PrivateRoute>} />
      <Route path="/reembolso-form" element={<PrivateRoute module="reembolso"><div className="min-h-screen bg-bg-void p-6"><ReembolsoForm /></div></PrivateRoute>} />

      <Route path="/projetos"      element={<WithLayout><Projetos /></WithLayout>} />
      <Route path="/obras"         element={<WithLayout><Obras /></WithLayout>} />
      <Route path="/editar-dados"  element={<WithLayout><EditorDados /></WithLayout>} />

      {/* Placeholders */}
      <Route path="/master-metrics" element={<WithLayout><div className="p-8 text-text-muted">Master Métricas — Fase C.10</div></WithLayout>} />
      <Route path="/master-settings" element={<WithLayout><div className="p-8 text-text-muted">Master Settings — Fase C.10</div></WithLayout>} />
      <Route path="/app-mobile"    element={<WithLayout><AppMobile /></WithLayout>} />
      <Route path="/mobile-chat"   element={<PrivateRoute><MobileChat /></PrivateRoute>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
