import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useTenant } from '@/context/TenantContext'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard, HardHat, Wallet, Zap, BarChart3, TrendingUp,
  FileText, MessageSquare, Fuel, Receipt, ClipboardList, Clock,
  BarChart2, Bell, ShieldCheck, ToggleRight, Activity,
  UsersRound, Settings, ChevronLeft, ChevronRight,
  X, Menu,
} from 'lucide-react'

interface NavItem {
  label: string
  icon: React.ElementType
  path: string
  module?: string
}

const MASTER_ITEMS: NavItem[] = [
  { label: 'CLIENTES E TENANTS', icon: UsersRound,   path: '/master-console' },
  { label: 'AUDITORIA GLOBAL',   icon: ShieldCheck,  path: '/logs-auditoria' },
  { label: 'CUSTOS & UTILIZAÇÃO',icon: BarChart3,     path: '/master-metrics' },
  { label: 'CONFIGURAÇÕES',      icon: Settings,      path: '/master-settings' },
]

const CLIENT_SECTIONS = [
  {
    label: 'PRINCIPAL',
    items: [
      { label: 'VISÃO GERAL',       icon: LayoutDashboard, path: '/',            module: 'visao_geral' },
      { label: 'HUB DE OPERAÇÕES',  icon: HardHat,         path: '/hub',         module: 'obras' },
    ],
  },
  {
    label: 'OPERACIONAL',
    items: [
      { label: 'FINANCEIRO',        icon: Wallet,          path: '/financeiro',         module: 'financeiro' },
      { label: 'O&M',               icon: Zap,             path: '/om',                 module: 'om' },
      { label: 'ANALYTICS',         icon: BarChart3,       path: '/analytics',          module: 'analytics' },
      { label: 'PREVISÕES ML',      icon: TrendingUp,      path: '/previsoes',          module: 'previsoes' },
      { label: 'RELATÓRIOS',        icon: FileText,        path: '/relatorios',         module: 'relatorios' },
      { label: 'CHAT IA',           icon: MessageSquare,   path: '/chat-ia',            module: 'chat_ia' },
      { label: 'REEMBOLSO',         icon: Fuel,            path: '/reembolso-form',     module: 'reembolso' },
      { label: 'REEMBOLSO DASH',    icon: Receipt,         path: '/reembolso-dashboard',module: 'reembolso_dash' },
    ],
  },
  {
    label: 'RDO',
    items: [
      { label: 'RDO DIÁRIO',        icon: ClipboardList,   path: '/rdo-form',      module: 'rdo_form' },
      { label: 'MEUS RDOS',         icon: Clock,           path: '/rdo-historico', module: 'rdo_historico' },
      { label: 'RDO ANALYTICS',     icon: BarChart2,       path: '/rdo-dashboard', module: 'rdo_dashboard' },
    ],
  },
  {
    label: 'ADMINISTRAÇÃO',
    items: [
      { label: 'GESTÃO DE ALERTAS', icon: Bell,         path: '/alertas',            module: 'alertas' },
      { label: 'LOGS & AUDITORIA',  icon: ShieldCheck,  path: '/logs-auditoria',     module: 'logs_auditoria' },
      { label: 'FEATURE FLAGS',     icon: ToggleRight,  path: '/contract-features',  module: 'gerenciar_usuarios' },
      { label: 'OBSERVABILIDADE',   icon: Activity,     path: '/observabilidade',    module: 'gerenciar_usuarios' },
    ],
  },
]

function SidebarItem({ item, expanded }: { item: NavItem; expanded: boolean }) {
  const location = useLocation()
  const isActive = item.path === '/'
    ? location.pathname === '/'
    : location.pathname === item.path || location.pathname.startsWith(item.path + '/')

  return (
    <NavLink to={item.path} className="no-underline group">
      <div className={cn(
        "flex items-center gap-3 transition-all duration-200 rounded-control border-l-2 mb-1",
        expanded ? "px-4 py-2.5" : "justify-center py-2.5 px-0",
        isActive 
          ? "bg-primary/10 border-primary shadow-[inset_1px_0_10px_rgba(201,139,42,0.05)]" 
          : "bg-transparent border-transparent hover:bg-white/[0.03] hover:border-primary/30"
      )}>
        <item.icon
          size={18}
          className={cn(
            "shrink-0 transition-colors",
            isActive ? "text-primary" : "text-muted-foreground group-hover:text-primary/70"
          )}
        />
        <AnimatePresence>
          {expanded && (
            <motion.span
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              className={cn(
                "font-display font-bold text-[13px] tracking-wide whitespace-nowrap overflow-hidden transition-colors",
                isActive ? "text-white" : "text-muted-foreground group-hover:text-white/80"
              )}
            >
              {item.label}
            </motion.span>
          )}
        </AnimatePresence>
      </div>
    </NavLink>
  )
}

function SectionLabel({ label, expanded }: { label: string; expanded: boolean }) {
  return (
    <div className={cn(
      "transition-all duration-300",
      expanded ? "px-4 pt-6 pb-2" : "px-0 py-4 flex justify-center"
    )}>
      {expanded ? (
        <span className="text-[9px] font-bold tracking-[0.2em] text-muted-foreground/50 uppercase">
          {label}
        </span>
      ) : (
        <div className="w-8 h-px bg-white/5" />
      )}
    </div>
  )
}

function SidebarContent({ expanded, onClose }: { expanded: boolean; onClose?: () => void }) {
  const { isMaster, allowedModules } = useTenant()

  // Se allowed_modules está vazio (admin sem restrição), mostra tudo
  const canSee = (module?: string) => {
    if (!module) return true
    if (allowedModules.length === 0) return true
    return allowedModules.includes(module)
  }

  return (
    <div className="flex flex-col h-full w-full">
      {/* Brand space */}
      <div className={cn(
        "h-16 flex items-center border-b border-white/5 bg-void/50 backdrop-blur-md",
        expanded ? "px-4 justify-between" : "justify-center px-0"
      )}>
        {expanded ? (
          <img src="/banner.png" alt="Bomtempo" className="h-8 object-contain" />
        ) : (
          <img src="/icon.png" alt="B" className="w-8 h-8 rounded-control" />
        )}
        {onClose && (
          <button onClick={onClose} className="lg:hidden text-muted-foreground hover:text-white">
            <X size={20} />
          </button>
        )}
      </div>

      {/* Navigation Space */}
      <div className="flex-1 overflow-y-auto px-2 py-4 custom-scrollbar">
        {isMaster ? (
          <>
            <SectionLabel label="GESTÃO GLOBAL" expanded={expanded} />
            {MASTER_ITEMS.map((item) => (
              <SidebarItem key={item.path} item={item} expanded={expanded} />
            ))}
          </>
        ) : (
          CLIENT_SECTIONS.map((section) => {
            const visibleItems = section.items.filter(item => canSee(item.module))
            if (visibleItems.length === 0) return null
            return (
              <div key={section.label}>
                <SectionLabel label={section.label} expanded={expanded} />
                {visibleItems.map((item) => (
                  <SidebarItem key={item.path} item={item} expanded={expanded} />
                ))}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

export function Sidebar({ expanded, onToggle }: { expanded: boolean; onToggle: () => void }) {
  const width = expanded ? '256px' : '72px'

  return (
    <motion.div 
      animate={{ width }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="fixed top-0 left-0 h-screen bg-card border-r border-white/5 z-50 flex flex-col"
    >
      <SidebarContent expanded={expanded} />

      {/* Expand/Collapse Toggle */}
      <button
        onClick={onToggle}
        className="absolute -right-3 top-16 w-6 h-6 bg-card border border-white/10 rounded-control flex items-center justify-center text-primary shadow-lg hover:border-primary/50 transition-colors z-50"
      >
        {expanded ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
      </button>
    </motion.div>
  )
}

export function MobileSidebar() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button onClick={() => setOpen(true)} className="text-primary lg:hidden">
        <Menu size={24} />
      </button>

      <AnimatePresence>
        {open && (
          <div className="fixed inset-0 z-[100] lg:hidden">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            />
            <motion.div
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="absolute top-0 left-0 w-[280px] h-full bg-card border-r border-white/5 shadow-2xl"
            >
              <SidebarContent expanded={true} onClose={() => setOpen(false)} />
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  )
}
