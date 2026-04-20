import { motion } from 'framer-motion'
import { ShieldCheck, Database, LayoutGrid, BarChart3, Zap } from 'lucide-react'
import './LoadingScreen.css'

const STEPS = [
  { id: 1, icon: ShieldCheck, label: "Autenticando sessão" },
  { id: 2, icon: Database,    label: "Conectando ao Supabase" },
  { id: 3, icon: LayoutGrid,  label: "Carregando módulos" },
  { id: 4, icon: BarChart3,   label: "Preparando dados operacionais" },
  { id: 5, icon: Zap,          label: "Iniciando plataforma" },
]

export default function LoadingScreen() {
  return (
    <div className="loading-screen-container">
      {/* Scan line effect */}
      <div className="sync-scan-line" />

      {/* Decorative grid background */}
      <div className="loading-grid" />

      {/* Copper glow orb */}
      <div className="loading-glow-orb" />

      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="relative z-10 flex flex-col items-center max-w-[400px] w-full px-6"
      >
        {/* Brand Lockup */}
        <div className="flex flex-col items-center mb-8">
          <img 
            src="/banner.png" 
            alt="Bomtempo" 
            className="w-[220px] object-contain mb-3"
            style={{ filter: 'drop-shadow(0 0 8px rgba(201,139,42,0.12))' }}
          />
          <span className="font-display text-[0.65rem] font-bold text-primary tracking-[0.28em] opacity-75 uppercase">
            Iniciando plataforma
          </span>
        </div>

        {/* Progress Bar Container */}
        <div className="w-[300px] h-[2px] bg-white/5 overflow-hidden mb-10">
          <div className="loader-progress-fill w-full h-full" />
        </div>

        {/* Step List */}
        <div className="flex flex-col gap-2 w-full max-w-[340px]">
          {STEPS.map((step, index) => (
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ 
                delay: 0.4 + index * 0.6, // Matches the 4.5s overall progress feeling
                duration: 0.4,
                ease: "easeOut" 
              }}
              className="flex items-center gap-3 p-[9px_14px] bg-white/[0.02] border border-white/[0.04] rounded-control w-full"
            >
              <div className="w-5 h-5 flex items-center justify-center rounded-control bg-primary/10 border border-primary/30 shrink-0">
                <span className="font-mono text-[9px] text-primary font-bold">{step.id}</span>
              </div>
              <step.icon size={12} className="text-muted-foreground" />
              <span className="text-xs text-muted-foreground font-body">{step.label}</span>
              <div className="ml-auto w-[5px] h-[5px] rounded-full bg-primary/60 indicator-pulse" />
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}
