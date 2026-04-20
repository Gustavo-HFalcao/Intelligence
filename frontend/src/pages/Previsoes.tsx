import { TrendingUp } from 'lucide-react'

const COPPER = '#C98B2A'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

export default function Previsoes() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 mb-2">
        <TrendingUp size={20} style={{ color:COPPER }} />
        <h1 className="font-display text-xl font-bold text-text-primary">Previsões ML</h1>
      </div>
      <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="p-8 text-center">
        <TrendingUp size={48} style={{ margin:'0 auto 16px', color:'#333' }} />
        <p className="text-text-muted text-sm">Módulo de previsões com Machine Learning será ativado na Fase D.</p>
        <p className="text-xs text-text-muted mt-2">Requer integração com modelos preditivos (Prophet / ARIMA).</p>
      </div>
    </div>
  )
}
