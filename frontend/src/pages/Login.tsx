import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { motion } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { GlassCard } from '@/components/ui/card'
import { LogIn, Info, Activity, Database, Globe } from 'lucide-react'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err: any) {
      if (err.response?.status === 401) {
        setError('Credenciais inválidas. Verifique usuário e senha.')
      } else if (!err.response) {
        setError('Não foi possível conectar ao servidor (Porta 8000). Verifique se o backend está rodando no terminal.')
      } else {
        setError('Ocorreu um erro inesperado no acesso à API.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-[#030504] overflow-hidden flex flex-col lg:flex-row">
      {/* ── PAINEL DE BRANDING (Desktop 1:1) ───────────────────────────────── */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden bg-[#081210] border-r border-white/5">
        {/* Grid Background */}
        <div 
          className="absolute inset-0 opacity-[0.04] pointer-events-none"
          style={{
            backgroundImage: 'linear-gradient(rgba(201,139,42,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(201,139,42,0.6) 1px, transparent 1px)',
            backgroundSize: '48px 48px'
          }}
        />

        {/* Glow Orbs */}
        <div className="absolute -top-20 -left-20 w-[320px] h-[320px] rounded-full bg-copper/10 blur-[80px] pointer-events-none" />
        <div className="absolute -bottom-16 -right-16 w-[250px] h-[250px] rounded-full bg-emerald-500/5 blur-[70px] pointer-events-none" />

        {/* Content Header */}
        <motion.div 
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="relative z-10 flex items-center gap-3"
        >
          <div className="w-1 h-6 bg-emerald-500" />
          <span className="font-display text-[9px] font-bold tracking-[0.22em] text-emerald-500 uppercase">
            Plataforma Operacional
          </span>
        </motion.div>

        {/* Hero Section */}
        <div className="relative z-10 space-y-8">
          <motion.img 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            src="/banner.png" 
            alt="Banner" 
            className="w-full max-w-[400px] opacity-90"
          />
          
          <div className="space-y-4">
            <h1 className="font-display text-4xl font-bold text-white uppercase tracking-tight leading-none">
              Inteligência<br />
              <span className="text-copper">Operacional</span>
            </h1>
            <p className="text-white/40 text-sm leading-relaxed max-w-sm">
              Plataforma centralizada de dados operacionais, controle financeiro e analytics preditivo para gestão de obras e contratos.
            </p>
          </div>

          {/* Stats Grid 1:1 */}
          <div className="grid grid-cols-2 gap-3 max-w-md">
            <StatItem label="Contratos Ativos" value="147" icon={<Database size={14} />} color="text-copper" />
            <StatItem label="RDOs Processados" value="8.4k" icon={<Activity size={14} />} color="text-emerald-500" />
            <StatItem label="Volume Gerenciado" value="R$ 2.1B" icon={<Globe size={14} />} color="text-copper" />
            <StatItem label="Uptime" value="99.97%" icon={<Info size={14} />} color="text-emerald-500" />
          </div>
        </div>

        {/* Footer Status */}
        <div className="relative z-10 flex items-center gap-2 opacity-60">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-mono text-[9px] text-white/40 tracking-widest uppercase">
            Sistemas Operacionais · Infraestrutura OK · UTC-3 BRT
          </span>
        </div>
      </div>

      {/* ── PAINEL DE AUTENTICAÇÃO (1:1) ───────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-6 bg-[#0e1a17] relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-[420px] space-y-8"
        >
          <div className="text-center lg:text-left space-y-2">
            <span className="font-display text-[9px] font-bold tracking-[0.22em] text-emerald-500 uppercase">
              Acesso Seguro
            </span>
            <h2 className="font-body text-3xl font-bold text-white tracking-tight">
              Autentique-se
            </h2>
          </div>

          <GlassCard className="p-8 space-y-6 border-white/5 bg-white/[0.02]">
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <label className="text-[9px] font-bold text-white/40 uppercase tracking-[0.18em] ml-1">
                  Usuário
                </label>
                <Input
                  type="text"
                  required
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Digite seu usuário"
                  className="bg-[#06100e] border-white/5 h-12 font-mono text-sm focus:border-b-2 focus:border-copper transition-all"
                />
              </div>

              <div className="space-y-2">
                <label className="text-[9px] font-bold text-white/40 uppercase tracking-[0.18em] ml-1">
                  Senha
                </label>
                <Input
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="bg-[#06100e] border-white/5 h-12 font-mono text-sm focus:border-b-2 focus:border-copper transition-all"
                />
                <div className="flex justify-end px-1 pt-0.5">
                  <button type="button" tabIndex={-1} className="text-[10px] text-emerald-500 opacity-70 hover:opacity-100 underline">
                    Esqueci minha senha?
                  </button>
                </div>
              </div>

              {error && (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center gap-2 p-3 bg-red-500/5 border border-red-500/20 rounded-sm text-red-500 text-xs font-mono"
                >
                  <Info size={14} />
                  <span>{error}</span>
                </motion.div>
              )}

              <Button
                type="submit"
                disabled={isLoading}
                className="w-full h-12 bg-gradient-to-br from-copper to-[#E0A63B] text-[#0A1F1A] font-bold tracking-widest hover:opacity-90 transition-all uppercase"
              >
                {isLoading ? (
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 border-2 border-[#0A1F1A] border-t-transparent rounded-full animate-spin" />
                    <span>Autenticando</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <LogIn size={16} />
                    <span>Entrar no Sistema</span>
                  </div>
                )}
              </Button>
            </form>
          </GlassCard>

          <p className="text-center font-mono text-[9px] text-white/40 tracking-[0.1em] opacity-40 uppercase">
            Bomtempo Intelligence · Plataforma Restrita · Acesso Monitorado
          </p>
        </motion.div>
      </div>
    </div>
  )
}

function StatItem({ label, value, icon, color }: { label: string, value: string, icon: any, color: string }) {
  return (
    <div className="p-4 bg-white/[0.02] border border-white/5 rounded-sm space-y-1">
      <div className="flex items-center gap-2 text-[8px] font-bold text-white/30 uppercase tracking-widest">
        {icon}
        {label}
      </div>
      <div className={`font-display text-xl font-black ${color} leading-none`}>
        {value}
      </div>
    </div>
  )
}
