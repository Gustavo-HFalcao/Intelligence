import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import {
  ClipboardList, CheckCircle, FileWarning, Camera,
  MapPin, Calendar, CloudRain, TrendingUp, Download,
  ChevronRight, Activity,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const BLUE   = '#3B82F6'
const VIOLET = '#8B5CF6'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

async function api(path: string) {
  const r = await fetch(path, { credentials: 'include' })
  if (!r.ok) throw new Error()
  return r.json()
}

function TipShell({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ background: 'rgba(8,18,16,0.97)', border: `1px solid ${COPPER}30`, borderRadius: 12, padding: '10px 14px', fontFamily: 'Outfit, sans-serif' }}>
      {children}
    </div>
  )
}

function RDOAreaTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <TipShell>
      <div style={{ fontSize: 9, color: '#555', textTransform: 'uppercase', fontWeight: 700, marginBottom: 6 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ fontSize: 11, color: p.color, fontWeight: 700, fontFamily: 'monospace' }}>
          {p.name}: {p.value}
        </div>
      ))}
    </TipShell>
  )
}

function PieTip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const p = payload[0]
  return (
    <TipShell>
      <div style={{ fontSize: 10, color: p.payload.fill, fontWeight: 700 }}>{p.name}</div>
      <div style={{ fontSize: 13, color: '#fff', fontWeight: 800 }}>{p.value}</div>
      <div style={{ fontSize: 10, color: '#555' }}>{p.payload.percent}%</div>
    </TipShell>
  )
}

export default function RDODashboard() {
  const navigate = useNavigate()
  const [contrato, setContrato] = useState('')

  const { data: contratos } = useQuery({
    queryKey: ['hub-contratos'],
    queryFn:  () => api('/api/hub/contratos'),
    staleTime: 60_000,
  })
  const { data, isLoading } = useQuery({
    queryKey: ['rdo-dashboard', contrato],
    queryFn:  () => api(`/api/rdo/dashboard?contrato=${encodeURIComponent(contrato)}`),
    enabled:  !!contrato,
  })

  const cl: any[] = contratos?.contratos ?? []
  const d = data ?? {}

  const climaData: any[] = (d.clima_breakdown ?? []).map((c: any) => ({
    name: c.clima, value: c.count,
    fill: c.clima?.toLowerCase().includes('sol') ? COPPER
        : c.clima?.toLowerCase().includes('chuva') ? BLUE
        : c.clima?.toLowerCase().includes('nublado') ? '#888'
        : TEAL,
    percent: d.total ? Math.round(c.count / d.total * 100) : 0,
  }))

  const atividadeStatus: any[] = (d.atividades_status ?? []).map((a: any) => ({
    name: a.status, value: a.count,
    fill: a.status === 'concluida' ? TEAL : a.status === 'em_andamento' ? COPPER : '#888',
    percent: d.total_atividades ? Math.round(a.count / d.total_atividades * 100) : 0,
  }))

  const kpis = [
    { l: 'Total RDOs',         v: d.total ?? 0,              icon: ClipboardList, color: '#fff' },
    { l: 'Obras com RDO',      v: d.obras_com_rdo ?? 0,      icon: Activity,      color: COPPER },
    { l: 'RDOs Hoje',          v: d.rdos_hoje ?? 0,          icon: Calendar,      color: TEAL },
    { l: 'Última Data',        v: d.ultima_data ?? '—',       icon: Calendar,      color: '#888' },
    { l: 'Total Atividades',   v: d.total_atividades ?? 0,    icon: CheckCircle,   color: TEAL },
    { l: 'Evidências (fotos)', v: d.total_evidencias ?? 0,    icon: Camera,        color: VIOLET },
    { l: 'Check-ins GPS',      v: d.total_checkins ?? 0,      icon: MapPin,        color: '#22c55e' },
    { l: 'Com Interrupção',    v: d.com_interrupcao ?? 0,     icon: FileWarning,   color: RED },
  ]

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
            <ClipboardList size={22} className="text-copper" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-white uppercase tracking-tight">RDO — Analytics</h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">Análise completa de Relatórios Diários de Obra</p>
          </div>
        </div>

        {/* Contract selector */}
        <div className="flex flex-wrap gap-2">
          {cl.map((c: any) => (
            <button key={c.contrato} onClick={() => setContrato(c.contrato)}
              style={{
                background: contrato === c.contrato ? COPPER : GLASS,
                border: `1px solid ${contrato === c.contrato ? COPPER : 'rgba(201,139,42,0.2)'}`,
                color: contrato === c.contrato ? '#0d1117' : '#e2c87a',
                borderRadius: 8, padding: '6px 14px', fontSize: 12, fontWeight: 700, cursor: 'pointer',
              }}>
              {c.contrato}
            </button>
          ))}
        </div>
      </div>

      {!contrato && (
        <div className="p-20 flex flex-col items-center gap-3 opacity-40">
          <ClipboardList size={48} className="text-white/20" />
          <p className="text-sm font-bold uppercase tracking-widest text-text-muted">Selecione um contrato acima</p>
        </div>
      )}

      {contrato && isLoading && (
        <div className="p-10 text-center text-text-muted animate-pulse text-sm">Carregando analytics...</div>
      )}

      {contrato && !isLoading && (
        <div className="flex flex-col gap-6">
          {/* KPI grid — 8 cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {kpis.map(k => (
              <div key={k.l} style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-4 relative overflow-hidden group">
                <div className="text-[9px] font-bold text-text-muted uppercase tracking-widest mb-1">{k.l}</div>
                <div className="font-display text-2xl font-bold" style={{ color: k.color }}>{k.v}</div>
                <div className="absolute right-3 bottom-3 opacity-5 group-hover:opacity-10 transition-all">
                  <k.icon size={40} />
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* RDOs por dia — area chart */}
            {d.rdos_por_dia?.length > 0 && (
              <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-5">
                <h3 style={{ fontSize: 11, fontWeight: 700, color: '#666', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 16 }}>
                  RDOs por Dia
                </h3>
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={d.rdos_por_dia}>
                    <defs>
                      <linearGradient id="rdoGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={COPPER} stopOpacity={0.2} />
                        <stop offset="95%" stopColor={COPPER} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                    <XAxis dataKey="data" tick={{ fill: '#444', fontSize: 9 }} axisLine={false} />
                    <YAxis tick={{ fill: '#444', fontSize: 9 }} axisLine={false} />
                    <Tooltip content={<RDOAreaTip />} />
                    <Area type="monotone" dataKey="total" name="RDOs" stroke={COPPER} fill="url(#rdoGrad)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Clima — pie chart */}
            {climaData.length > 0 && (
              <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-5">
                <h3 style={{ fontSize: 11, fontWeight: 700, color: '#666', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 16 }}>
                  <CloudRain size={12} style={{ color: BLUE, display: 'inline', marginRight: 6 }} />
                  Condição Climática
                </h3>
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={climaData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} innerRadius={45}>
                      {climaData.map((entry, idx) => <Cell key={idx} fill={entry.fill} />)}
                    </Pie>
                    <Tooltip content={<PieTip />} />
                    <Legend formatter={(v) => <span style={{ fontSize: 11, color: '#888' }}>{v}</span>} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Atividades por status — pie */}
            {atividadeStatus.length > 0 && (
              <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-5">
                <h3 style={{ fontSize: 11, fontWeight: 700, color: '#666', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 16 }}>
                  Atividades por Status
                </h3>
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={atividadeStatus} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} innerRadius={45}>
                      {atividadeStatus.map((entry, idx) => <Cell key={idx} fill={entry.fill} />)}
                    </Pie>
                    <Tooltip content={<PieTip />} />
                    <Legend formatter={(v) => <span style={{ fontSize: 11, color: '#888' }}>{v}</span>} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Atividades por contrato — bar */}
            {d.atividades_por_contrato?.length > 0 && (
              <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-5">
                <h3 style={{ fontSize: 11, fontWeight: 700, color: '#666', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 16 }}>
                  Atividades por Contrato
                </h3>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={d.atividades_por_contrato} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" horizontal={false} />
                    <XAxis type="number" tick={{ fill: '#444', fontSize: 9 }} axisLine={false} />
                    <YAxis type="category" dataKey="contrato" tick={{ fill: '#888', fontSize: 9 }} axisLine={false} width={80} />
                    <Tooltip content={<RDOAreaTip />} />
                    <Bar dataKey="total" name="Atividades" fill={TEAL} radius={[0, 4, 4, 0]} opacity={0.8} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Últimos RDOs table */}
          {d.rdos_recentes?.length > 0 && (
            <div style={{ background: GLASS, border: BORDER, borderRadius: 12, overflow: 'hidden' }}>
              <div className="p-4 flex items-center justify-between" style={{ borderBottom: '1px solid rgba(201,139,42,0.12)' }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#666', textTransform: 'uppercase', letterSpacing: '0.15em' }}>Últimos Relatórios</span>
                <button style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'none', border: 'none', color: '#555', cursor: 'pointer', fontSize: 11 }}>
                  <Download size={12} /> Exportar
                </button>
              </div>
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    {['Data', 'Clima', 'Turno', 'Equipe', 'Status', 'Atividades', 'PDF', ''].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-text-muted uppercase" style={{ fontSize: 9, fontWeight: 700 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {d.rdos_recentes.map((r: any) => (
                    <tr key={r.id} className="hover:bg-white/5 transition-colors group cursor-pointer" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}
                      onClick={() => r.view_token && window.open(`/rdo/${r.view_token}`, '_blank')}>
                      <td className="px-4 py-3 font-mono text-text-muted">{r.data}</td>
                      <td className="px-4 py-3 text-text-muted">{r.clima ?? r.condicao_climatica ?? '—'}</td>
                      <td className="px-4 py-3 text-text-muted">{r.turno ?? '—'}</td>
                      <td className="px-4 py-3 text-text-muted">{r.equipe_alocada ?? '—'}</td>
                      <td className="px-4 py-3">
                        <span style={{
                          fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 5,
                          color: r.status === 'Submetido' ? TEAL : COPPER,
                          background: r.status === 'Submetido' ? `${TEAL}20` : `${COPPER}20`,
                        }}>{r.status}</span>
                      </td>
                      <td className="px-4 py-3 font-mono text-white/60">{r.num_atividades ?? 0}</td>
                      <td className="px-4 py-3">
                        {r.pdf_url && (
                          <a href={r.pdf_url} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
                            style={{ color: COPPER, fontSize: 10, fontWeight: 700, textDecoration: 'none' }}>
                            PDF ↗
                          </a>
                        )}
                      </td>
                      <td className="px-4 py-3 text-white/20 group-hover:text-copper transition-colors">
                        <ChevronRight size={13} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
