import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { HardHat, AlertTriangle, CheckCircle, Clock } from 'lucide-react'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const AMBER  = '#F59E0B'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

async function api(path: string) {
  const r = await fetch(path, { credentials:'include' })
  if (!r.ok) throw new Error()
  return r.json()
}

export default function Obras() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['obras-list'],
    queryFn:  () => api('/api/hub/contratos'),
    staleTime: Infinity,
  })

  const all: any[] = data?.contratos ?? []
  const obras = filter
    ? all.filter(c => c.contrato.toLowerCase().includes(filter.toLowerCase()) || (c.projeto||'').toLowerCase().includes(filter.toLowerCase()))
    : all

  function riskColor(pct: number) {
    if (pct >= 80) return TEAL
    if (pct >= 50) return COPPER
    if (pct >= 30) return AMBER
    return RED
  }

  function RiskIcon({ pct }: { pct: number }) {
    if (pct >= 80) return <CheckCircle size={14} style={{ color:TEAL }} />
    if (pct >= 50) return <Clock size={14} style={{ color:COPPER }} />
    return <AlertTriangle size={14} style={{ color:RED }} />
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <HardHat size={20} style={{ color:COPPER }} />
          <h1 className="font-display text-xl font-bold text-text-primary">Obras</h1>
        </div>
        <input
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filtrar obra..."
          style={{ background:'#0d1117', border:'1px solid rgba(201,139,42,0.3)', color:'#e2c87a', borderRadius:8, padding:'6px 12px', fontSize:13, width:200 }}
        />
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 animate-pulse">
          {[...Array(6)].map((_,i) => <div key={i} style={{ height:180, background:GLASS, borderRadius:14 }} />)}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {obras.map((c: any) => {
          const pct = c.realizado_pct ?? 0
          return (
            <div key={c.contrato}
              onClick={() => navigate(`/hub?contrato=${c.contrato}`)}
              style={{ background:GLASS, border:BORDER, borderRadius:14, cursor:'pointer' }}
              className="p-4 hover:border-copper-dim transition-colors group">
              <div className="flex items-center justify-between mb-2">
                <div className="font-mono text-xs" style={{ color:COPPER }}>{c.contrato}</div>
                <RiskIcon pct={pct} />
              </div>
              <div className="font-semibold text-text-primary text-sm mb-1 truncate">{c.projeto || c.contrato}</div>
              <div className="text-xs text-text-muted mb-3">{c.cliente || '—'}</div>

              {/* Gauge */}
              <div className="relative" style={{ height:6, background:'rgba(255,255,255,0.06)', borderRadius:4, marginBottom:10 }}>
                <div style={{ width:`${Math.min(pct,100)}%`, background:riskColor(pct), height:'100%', borderRadius:4, transition:'width 0.6s' }} />
              </div>

              <div className="flex justify-between">
                <div>
                  <div className="text-xs text-text-muted">Físico</div>
                  <div className="font-mono text-sm font-bold" style={{ color:riskColor(pct) }}>{pct}%</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">Previsto</div>
                  <div className="font-mono text-sm font-bold" style={{ color:'#888' }}>{c.previsto_pct ?? 0}%</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">Atividades</div>
                  <div className="font-mono text-sm font-bold" style={{ color:COPPER }}>{c.total_atividades ?? 0}</div>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {!isLoading && obras.length === 0 && (
        <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="p-12 text-center">
          <HardHat size={40} style={{ margin:'0 auto 12px', color:'#333' }} />
          <p className="text-text-muted">Nenhuma obra encontrada.</p>
        </div>
      )}
    </div>
  )
}
