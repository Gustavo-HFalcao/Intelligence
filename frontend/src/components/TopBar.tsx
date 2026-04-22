import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/context/AuthContext'
import { useTenant } from '@/context/TenantContext'
import { useTheme } from '@/context/ThemeContext'
import { Bell, LogOut, Users, Sun, Moon } from 'lucide-react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

const PATH_TITLES: Record<string, string> = {
  '/':                    'Visão Geral',
  '/hub':                 'Hub de Operações',
  '/financeiro':          'Financeiro',
  '/om':                  'O&M',
  '/analytics':           'Analytics',
  '/previsoes':           'Previsões',
  '/relatorios':          'Relatórios',
  '/chat-ia':             'Chat IA',
  '/reembolso-form':      'Reembolso',
  '/reembolso-dashboard': 'Reembolso Dashboard',
  '/rdo-form':            'RDO Diário',
  '/rdo-historico':       'Meus RDOs',
  '/rdo-dashboard':       'RDO Analytics',
  '/alertas':             'Alertas',
  '/logs-auditoria':      'Logs & Auditoria',
  '/usuarios':            'Usuários',
  '/editar-dados':        'Editar Dados',
  '/observabilidade':     'Observabilidade',
  '/contract-features':   'Feature Flags',
  '/perfil':              'Meu Perfil',
  '/master-console':      'Master Console',
  '/master-metrics':      'Master Métricas',
  '/master-settings':     'Master Settings',
}

const HUB_TABS = [
  { label: 'Visão Geral', value: 'visao_geral' },
  { label: 'Dashboard',   value: 'dashboard' },
  { label: 'Cronograma',  value: 'cronograma' },
  { label: 'Auditoria',   value: 'auditoria' },
  { label: 'Timeline',    value: 'timeline' },
  { label: 'Financeiro',  value: 'financeiro' },
]

interface TopBarProps {
  sidebarExpanded: boolean
  hubTab?: string
  onHubTabChange?: (tab: string) => void
}

export default function TopBar({ sidebarExpanded, hubTab, onHubTabChange }: TopBarProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { user, logout } = useAuth()
  const { hasRole } = useTenant()
  const { theme, toggleTheme } = useTheme()
  const queryClient = useQueryClient()

  const isHub = location.pathname === '/hub' || location.pathname.startsWith('/hub/')
  const hubContrato = searchParams.get('contrato')
  const title = PATH_TITLES[location.pathname] ?? 'Dashboard'

  const avatarInitials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : '?'

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={cn(
        "fixed top-0 right-0 h-14 bg-background/80 backdrop-blur-xl border-bottom border-white/5 z-[49] transition-all duration-300 flex items-center px-6 gap-4",
        sidebarExpanded ? "left-64" : "left-[72px]"
      )}
    >
      {/* Search / Breadcrumb / Title */}
      <div className="flex-1 flex items-center gap-4 overflow-hidden">
        <h1 className="font-display text-xs font-bold tracking-[0.08em] uppercase text-white whitespace-nowrap">
          {title}
        </h1>

        {isHub && onHubTabChange && !!hubContrato && (
          <>
            <Separator orientation="vertical" className="h-5 bg-white/10" />
            <div className="flex items-center gap-1 overflow-x-auto no-scrollbar h-full">
              {HUB_TABS.map((tab) => {
                const active = hubTab === tab.value
                return (
                  <button
                    key={tab.value}
                    onClick={() => onHubTabChange(tab.value)}
                    className={cn(
                      "px-3 h-14 relative transition-all text-[11px] font-mono whitespace-nowrap uppercase tracking-wider",
                      active ? "text-primary font-bold" : "text-muted-foreground hover:text-white"
                    )}
                  >
                    {tab.label}
                    {active && (
                      <motion.div 
                        layoutId="hub-tab-indicator"
                        className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary shadow-[0_0_10px_rgba(201,139,42,0.5)]" 
                      />
                    )}
                  </button>
                )
              })}
            </div>
          </>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-primary transition-colors">
          <Bell size={16} />
        </Button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Modo claro' : 'Modo escuro'}
          className="w-8 h-8 flex items-center justify-center rounded-lg transition-all hover:bg-white/10"
          style={{
            background: theme === 'light' ? 'rgba(176,120,32,0.12)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${theme === 'light' ? 'rgba(176,120,32,0.3)' : 'rgba(255,255,255,0.08)'}`,
            color: theme === 'light' ? '#b07820' : '#888',
          }}
        >
          {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
        </button>

        {hasRole('Administrador') && (
          <Button
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-primary transition-colors"
            onClick={() => navigate('/usuarios')}
          >
            <Users size={18} />
          </Button>
        )}

        <Separator orientation="vertical" className="h-6 bg-white/10 mx-2" />

        {/* User Pill */}
        <div 
          onClick={() => navigate('/perfil')}
          className="group flex items-center gap-3 pl-1 pr-3 py-1 bg-white/[0.03] border border-white/5 rounded-control cursor-pointer transition-all hover:bg-white/[0.06] hover:border-primary/30"
        >
          <div className="w-7 h-7 rounded-[4px] bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-lg group-hover:scale-105 transition-transform">
            <span className="font-display font-bold text-[11px] text-void">
              {avatarInitials}
            </span>
          </div>
          <div className="flex flex-col -space-y-0.5">
            <span className="font-display text-[11px] font-bold text-white group-hover:text-primary transition-colors">
              {user?.email?.split('@')[0] ?? 'Usuário'}
            </span>
            <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-widest opacity-60">
              {user?.role_name ?? 'Cargos...'}
            </span>
          </div>
          <Separator orientation="vertical" className="h-4 bg-white/10 ml-1" />
          <button 
            onClick={async (e) => {
              e.stopPropagation()
              queryClient.clear()   // wipe all cached tenant data before user changes
              await logout()
              navigate('/login')
            }} 
            className="text-muted-foreground hover:text-destructive transition-colors ml-1"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </motion.div>
  )
}
