/**
 * RDOTopBar — Barra superior minimalista para páginas de campo (sem sidebar).
 * Contém: logo/título, toggle de tema, nome do usuário e logout.
 */
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/context/ThemeContext'
import { LogOut, Sun, Moon, ClipboardList, FileText } from 'lucide-react'
import { motion } from 'framer-motion'

const COPPER = '#C98B2A'

interface RDOTopBarProps {
  /** Qual página está ativa — controla os links de navegação */
  page?: 'form' | 'historico'
}

export default function RDOTopBar({ page }: RDOTopBarProps) {
  const navigate      = useNavigate()
  const qc            = useQueryClient()
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()

  const avatarInitials = (user?.email || user?.login || '?').slice(0, 2).toUpperCase()
  const userName       = (user?.email?.split('@')[0] ?? user?.login ?? 'Usuário')

  async function handleLogout() {
    qc.clear()
    await logout()
    navigate('/login')
  }

  return (
    <motion.header
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        background: 'rgba(8,18,16,0.95)',
        borderBottom: '1px solid rgba(201,139,42,0.15)',
        backdropFilter: 'blur(16px)',
      }}
      className="sticky top-0 z-50 flex items-center justify-between px-4 md:px-6 h-14"
    >
      {/* Left: Logo + nav links */}
      <div className="flex items-center gap-4">
        {/* Logo mark */}
        <div
          className="flex items-center gap-2 cursor-pointer select-none"
          onClick={() => navigate('/rdo-historico')}
        >
          <div
            style={{ background: `${COPPER}18`, border: `1px solid ${COPPER}40`, borderRadius: 8, padding: '5px 8px' }}
            className="flex items-center gap-1.5"
          >
            <ClipboardList size={14} style={{ color: COPPER }} />
            <span style={{ color: COPPER, fontSize: 11, fontWeight: 800, letterSpacing: '0.1em' }}>
              RDO
            </span>
          </div>
        </div>

        {/* Nav pills */}
        <div className="hidden sm:flex items-center gap-1">
          <button
            onClick={() => navigate('/rdo-historico')}
            style={{
              background: page === 'historico' ? `${COPPER}18` : 'transparent',
              border: `1px solid ${page === 'historico' ? `${COPPER}40` : 'transparent'}`,
              color: page === 'historico' ? COPPER : 'rgba(255,255,255,0.4)',
              borderRadius: 6, padding: '4px 12px', fontSize: 11, fontWeight: 700,
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5,
              letterSpacing: '0.05em',
            }}
          >
            <ClipboardList size={11} /> Histórico
          </button>
          <button
            onClick={() => navigate('/rdo-form')}
            style={{
              background: page === 'form' ? `${COPPER}18` : 'transparent',
              border: `1px solid ${page === 'form' ? `${COPPER}40` : 'transparent'}`,
              color: page === 'form' ? COPPER : 'rgba(255,255,255,0.4)',
              borderRadius: 6, padding: '4px 12px', fontSize: 11, fontWeight: 700,
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5,
              letterSpacing: '0.05em',
            }}
          >
            <FileText size={11} /> Novo RDO
          </button>
        </div>
      </div>

      {/* Right: theme + user + logout */}
      <div className="flex items-center gap-3">
        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Modo claro' : 'Modo escuro'}
          style={{
            background: theme === 'light' ? 'rgba(176,120,32,0.12)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${theme === 'light' ? 'rgba(176,120,32,0.3)' : 'rgba(255,255,255,0.08)'}`,
            color: theme === 'light' ? '#b07820' : 'rgba(255,255,255,0.4)',
            borderRadius: 7, padding: '5px 7px', cursor: 'pointer', display: 'flex',
          }}
        >
          {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
        </button>

        {/* User pill */}
        <div
          style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 8,
          }}
          className="flex items-center gap-2 pl-1 pr-2 py-1"
        >
          {/* Avatar */}
          <div
            style={{
              width: 26, height: 26, borderRadius: 6,
              background: `linear-gradient(135deg, ${COPPER}, #2A9D8F)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <span style={{ fontSize: 10, fontWeight: 800, color: '#000' }}>{avatarInitials}</span>
          </div>

          {/* Name */}
          <div className="flex flex-col leading-none hidden sm:flex">
            <span style={{ fontSize: 11, fontWeight: 700, color: 'rgba(255,255,255,0.85)' }}>
              {userName}
            </span>
            <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', letterSpacing: '0.08em', fontWeight: 600 }}>
              {(user as any)?.role_name ?? (user as any)?.role ?? 'Campo'}
            </span>
          </div>

          {/* Divider */}
          <div style={{ width: 1, height: 18, background: 'rgba(255,255,255,0.08)', margin: '0 2px' }} />

          {/* Logout */}
          <button
            onClick={handleLogout}
            title="Sair"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.3)', display: 'flex', padding: '2px' }}
            className="hover:text-red-400 transition-colors"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </motion.header>
  )
}
