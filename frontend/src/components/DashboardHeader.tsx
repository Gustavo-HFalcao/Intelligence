import { Activity, HardHat, TrendingUp, DollarSign } from 'lucide-react'
import '../pages/Dashboard.css'

interface DashboardHeaderProps {
  contratosAtivos: number
  avancoGeral: string
  valorTcv: string
}

export default function DashboardHeader({ contratosAtivos, avancoGeral, valorTcv }: DashboardHeaderProps) {
  return (
    <div className="dashboard-header-banner glass-panel animate-enter mb-6 p-6 lg:p-10 rounded-xl overflow-hidden relative">
      {/* Decorative Gradients */}
      <div 
        className="absolute inset-0 pointer-events-none"
        style={{ background: 'linear-gradient(135deg, rgba(201,139,42,0.08) 0%, transparent 45%)' }}
      />
      <div 
        className="absolute bottom-0 right-0 w-1/2 h-full pointer-events-none"
        style={{ background: 'linear-gradient(225deg, rgba(42,157,143,0.04) 0%, transparent 60%)' }}
      />
      
      {/* Background Icon */}
      <div className="absolute right-0 top-0 p-8 opacity-5 pointer-events-none">
        <Activity size={200} strokeWidth={0.5} color="#888" />
      </div>

      <div className="relative z-10 flex flex-col gap-0">
        {/* Status Pill Row */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full border border-teal-500/30 bg-teal-500/10">
            <div className="relative w-2 h-2 rounded-full bg-teal-500">
              <div className="absolute inset-0 rounded-full bg-teal-500 live-indicator-pulse" />
            </div>
            <span className="text-[10px] font-bold uppercase tracking-widest text-[#2A9D8F]">
              Sistema Online
            </span>
          </div>
          <div className="w-12 h-[1px] bg-[#C98B2A]/30" />
          <span className="text-[10px] font-semibold tracking-widest text-text-muted font-mono uppercase">
            BTP Intelligence v2
          </span>
        </div>

        {/* Main Title */}
        <h1 className="font-display text-4xl lg:text-5xl font-bold text-white mt-4 leading-none tracking-tight">
          VISÃO GERAL
        </h1>

        {/* Subtitle */}
        <p className="text-text-muted text-sm lg:text-base font-light max-w-2xl mt-3 leading-relaxed">
          Centro de Comando BOMTEMPO INTELLIGENCE. Telemetria financeira, velocidade operacional e marcadores estratégicos em tempo real.
        </p>

        {/* Quick Stats Strip */}
        <div className="flex flex-wrap items-center gap-4 mt-6">
          <div className="flex items-center gap-2">
            <HardHat size={14} className="text-[#C98B2A]" />
            <span className="font-mono text-sm font-bold text-white">{contratosAtivos}</span>
            <span className="text-[11px] text-text-muted">obras ativas</span>
          </div>
          
          <div className="w-[1px] h-4 bg-white/10" />
          
          <div className="flex items-center gap-2">
            <TrendingUp size={14} className="text-[#C98B2A]" />
            <span className="font-mono text-sm font-bold text-white">{avancoGeral}</span>
            <span className="text-[11px] text-text-muted">velocidade média</span>
          </div>

          <div className="w-[1px] h-4 bg-white/10" />

          <div className="flex items-center gap-2">
            <DollarSign size={14} className="text-[#C98B2A]" />
            <span className="font-mono text-sm font-bold text-white">{valorTcv}</span>
            <span className="text-[11px] text-text-muted">carteira total</span>
          </div>
        </div>
      </div>
    </div>
  )
}
