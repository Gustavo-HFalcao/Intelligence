import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, CartesianGrid,
} from 'recharts'
import {
  Activity, CheckCircle, XCircle, RefreshCw, X,
  Cpu, Database, Zap, Clock, DollarSign, TrendingUp, Filter,
} from 'lucide-react'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

async function api(path: string) {
  const r = await fetch(path, { credentials: 'include' })
  if (!r.ok) throw new Error()
  return r.json()
}

function TipShell({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ background: 'rgba(8,18,16,0.97)', border: `1px solid ${COPPER}30`, borderRadius: 12, padding: '10px 14px', fontFamily: 'Outfit, sans-serif', boxShadow: '0 12px 32px rgba(0,0,0,0.5)' }}>
      {children}
    </div>
  )
}
function CostTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <TipShell>
      <div style={{ fontSize: 9, color: '#555', textTransform: 'uppercase', fontWeight: 700, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 12, color: COPPER, fontWeight: 700, fontFamily: 'monospace' }}>US$ {payload[0]?.value?.toFixed(4)}</div>
    </TipShell>
  )
}
function CallsTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <TipShell>
      <div style={{ fontSize: 9, color: '#555', textTransform: 'uppercase', fontWeight: 700, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 12, color: TEAL, fontWeight: 700 }}>{payload[0]?.value} chamadas</div>
    </TipShell>
  )
}

export default function Observabilidade() {
  const [tab, setTab]       = useState<'metricas' | 'logs' | 'health'>('metricas')
  const [page, setPage]     = useState(1)
  const [modelFilter, setModelFilter] = useState('')
  const [errorsOnly, setErrorsOnly]   = useState(false)
  const [selected, setSelected]       = useState<any>(null)

  const qs = new URLSearchParams()
  qs.set('page', String(page))
  if (modelFilter) qs.set('model', modelFilter)
  if (errorsOnly)  qs.set('errors_only', '1')

  const { data: metricas, refetch: refetchM } = useQuery({
    queryKey: ['obs-metricas'],
    queryFn:  () => api('/api/obs/metricas'),
    staleTime: 30_000,
  })
  const { data: logsData, refetch: refetchL } = useQuery({
    queryKey: ['obs-logs', page, modelFilter, errorsOnly],
    queryFn:  () => api(`/api/obs/logs?${qs.toString()}`),
    staleTime: 15_000,
  })
  const { data: health, refetch: refetchH } = useQuery({
    queryKey: ['obs-health'],
    queryFn:  () => api('/api/obs/health'),
    refetchInterval: 30_000,
  })

  const m = metricas ?? {}
  const logs: any[] = logsData?.logs ?? []
  const TABS: [string, string][] = [['metricas', 'Métricas'], ['logs', 'Logs LLM'], ['health', 'Health']]

  const kpiCards = [
    { label: 'Chamadas AI', value: m.total_calls ?? 0, icon: Cpu, color: '#fff' },
    { label: 'Custo Total', value: m.total_cost_fmt ?? 'US$ 0.00', icon: DollarSign, color: COPPER },
    { label: 'Tokens',      value: (m.total_tokens ?? 0).toLocaleString(), icon: Zap, color: TEAL },
    { label: 'Latência Média', value: `${m.avg_latency_ms ?? 0} ms`, icon: Clock, color: '#3B82F6' },
    { label: 'Taxa Sucesso', value: m.total_calls ? `${Math.round((1 - (m.error_count ?? 0) / m.total_calls) * 100)}%` : '—', icon: TrendingUp, color: TEAL },
    { label: 'Erros', value: m.error_count ?? 0, icon: XCircle, color: RED },
  ]

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
            <Activity size={22} className="text-copper" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-white uppercase tracking-tight">Observabilidade</h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">Monitoramento de uso IA · Custo · Latência · Saúde do sistema</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {health?.status && (
            <span style={{
              background: health.status === 'ok' ? `${TEAL}20` : `${RED}20`,
              color: health.status === 'ok' ? TEAL : RED,
              border: `1px solid ${health.status === 'ok' ? TEAL : RED}40`,
              borderRadius: 8, padding: '4px 10px', fontSize: 11, fontWeight: 700,
            }}>
              {health.status === 'ok' ? '● Sistema OK' : '⚠ Degradado'}
            </span>
          )}
          <button onClick={() => { refetchM(); refetchL(); refetchH() }}
            style={{ background: GLASS, border: BORDER, color: '#888', borderRadius: 8, padding: '6px 12px', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
            <RefreshCw size={12} /> Atualizar
          </button>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1" style={{ borderBottom: '1px solid rgba(201,139,42,0.15)' }}>
        {TABS.map(([t, l]) => (
          <button key={t} onClick={() => setTab(t as any)}
            style={{
              background: 'none', border: 'none', padding: '10px 20px', fontSize: 13, cursor: 'pointer',
              color: tab === t ? COPPER : '#888', fontWeight: tab === t ? 700 : 400,
              borderBottom: tab === t ? `2px solid ${COPPER}` : '2px solid transparent',
            }}>{l}</button>
        ))}
      </div>

      {/* ── Métricas ─────────────────────────────────────────────────────── */}
      {tab === 'metricas' && (
        <div className="flex flex-col gap-6">
          {/* KPI grid */}
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            {kpiCards.map(k => (
              <div key={k.label} style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span style={{ fontSize: 9, fontWeight: 700, color: '#555', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{k.label}</span>
                  <k.icon size={13} style={{ color: k.color, opacity: 0.6 }} />
                </div>
                <div className="font-display text-xl font-bold" style={{ color: k.color }}>{k.value}</div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Daily cost chart */}
            {m.daily_series?.length > 0 && (
              <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-5">
                <h3 style={{ fontSize: 11, fontWeight: 700, color: '#666', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 16 }}>Custo Diário (US$)</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={m.daily_series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                    <XAxis dataKey="data" tick={{ fill: '#444', fontSize: 10 }} axisLine={false} />
                    <YAxis tick={{ fill: '#444', fontSize: 10 }} axisLine={false} tickFormatter={(v: number) => `$${v.toFixed(3)}`} />
                    <Tooltip content={<CostTip />} />
                    <Line type="monotone" dataKey="custo" stroke={COPPER} strokeWidth={2} dot={{ r: 3, fill: COPPER }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Calls by model */}
            {m.model_breakdown?.length > 0 && (
              <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-5">
                <h3 style={{ fontSize: 11, fontWeight: 700, color: '#666', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 16 }}>Chamadas por Modelo</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={m.model_breakdown} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" horizontal={false} />
                    <XAxis type="number" tick={{ fill: '#444', fontSize: 9 }} axisLine={false} />
                    <YAxis type="category" dataKey="model" tick={{ fill: '#888', fontSize: 9 }} axisLine={false} width={110} />
                    <Tooltip content={<CallsTip />} />
                    <Bar dataKey="calls" fill={TEAL} radius={[0, 4, 4, 0]} opacity={0.8} />
                  </BarChart>
                </ResponsiveContainer>

                {/* Cost breakdown list */}
                <div className="flex flex-col gap-2 mt-4 pt-4" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                  {m.model_breakdown.map((mb: any) => (
                    <div key={mb.model} className="flex items-center justify-between">
                      <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#888', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{mb.model}</span>
                      <div className="flex items-center gap-4">
                        <span style={{ fontSize: 10, color: '#555' }}>{mb.calls} calls</span>
                        <span style={{ fontSize: 11, color: COPPER, fontWeight: 700, fontFamily: 'monospace' }}>US$ {mb.cost_usd?.toFixed(4)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Logs LLM ─────────────────────────────────────────────────────── */}
      {tab === 'logs' && (
        <div className="flex flex-col gap-4">
          {/* Filter bar */}
          <div style={{ background: GLASS, border: BORDER, borderRadius: 10 }} className="p-3 flex flex-wrap gap-3 items-center">
            <Filter size={13} style={{ color: '#555' }} />
            <input
              value={modelFilter} onChange={e => { setModelFilter(e.target.value); setPage(1) }}
              placeholder="Filtrar por modelo..."
              style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 6, height: 30, padding: '0 10px', fontSize: 12, color: '#ccc', outline: 'none', width: 200 }}
            />
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#888', cursor: 'pointer', userSelect: 'none' }}>
              <input type="checkbox" checked={errorsOnly} onChange={e => { setErrorsOnly(e.target.checked); setPage(1) }} />
              Só erros
            </label>
          </div>

          <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(201,139,42,0.15)' }}>
                  {['Data/Hora', 'Modelo', 'Usuário', 'Tokens', 'Custo', 'Latência', 'Status', ''].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-text-muted uppercase" style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.1em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.map((l: any) => (
                  <tr key={l.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer' }}
                    className="hover:bg-white/5 transition-colors group" onClick={() => setSelected(l)}>
                    <td className="px-4 py-3 font-mono text-text-muted whitespace-nowrap">{l.created_at}</td>
                    <td className="px-4 py-3 text-white/80 font-mono text-[10px]">{l.model}</td>
                    <td className="px-4 py-3 text-text-muted">{l.user_login ?? '—'}</td>
                    <td className="px-4 py-3 font-mono">{l.total_tokens?.toLocaleString()}</td>
                    <td className="px-4 py-3 font-mono" style={{ color: COPPER }}>{l.cost_fmt}</td>
                    <td className="px-4 py-3 font-mono text-text-muted">{l.latency_fmt}</td>
                    <td className="px-4 py-3">
                      {l.success !== false
                        ? <CheckCircle size={13} style={{ color: TEAL }} />
                        : <XCircle size={13} style={{ color: RED }} />}
                    </td>
                    <td className="px-4 py-3 text-white/20 group-hover:text-copper transition-colors text-right">›</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {logs.length === 0 && <div className="p-8 text-center text-text-muted">Nenhum log disponível.</div>}
          </div>

          <div className="flex gap-2 justify-center items-center">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              style={{ background: GLASS, border: BORDER, color: '#888', borderRadius: 8, padding: '6px 16px', cursor: 'pointer', fontSize: 12 }}>← Anterior</button>
            <span className="text-xs text-text-muted font-mono">Página {page}</span>
            <button onClick={() => setPage(p => p + 1)} disabled={!logsData?.has_next}
              style={{ background: GLASS, border: BORDER, color: '#888', borderRadius: 8, padding: '6px 16px', cursor: 'pointer', fontSize: 12 }}>Próxima →</button>
          </div>
        </div>
      )}

      {/* ── Health ───────────────────────────────────────────────────────── */}
      {tab === 'health' && health && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(health.checks ?? {}).map(([svc, info]: [string, any]) => {
            const ok = info.status === 'ok'
            const Icon = svc === 'supabase' ? Database : svc === 'redis' ? Zap : Cpu
            return (
              <div key={svc} style={{ background: GLASS, border: `1px solid ${ok ? TEAL : RED}25`, borderRadius: 14 }} className="p-6 flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl" style={{ background: (ok ? TEAL : RED) + '15', border: `1px solid ${ok ? TEAL : RED}30` }}>
                      <Icon size={16} style={{ color: ok ? TEAL : RED }} />
                    </div>
                    <span className="font-bold text-white capitalize">{svc}</span>
                  </div>
                  <div style={{ width: 10, height: 10, borderRadius: '50%', background: ok ? TEAL : RED, boxShadow: `0 0 8px ${ok ? TEAL : RED}` }} />
                </div>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: ok ? TEAL : RED, fontFamily: 'Rajdhani, sans-serif' }}>{ok ? 'ONLINE' : 'OFFLINE'}</div>
                  {info.msg && <div style={{ fontSize: 11, color: '#555', marginTop: 4 }}>{info.msg}</div>}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ── Detail drawer ─────────────────────────────────────────────────── */}
      {selected && (
        <div className="fixed inset-0 z-[200] flex justify-end" onClick={() => setSelected(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div onClick={e => e.stopPropagation()}
            style={{ position: 'relative', width: 440, height: '100vh', background: '#0a0f0e', borderLeft: '1px solid rgba(201,139,42,0.2)', overflowY: 'auto', padding: 28 }}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-sm font-black uppercase text-white">Detalhe da Chamada</h3>
              <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>
            <div className="flex flex-col gap-4">
              {[
                ['Timestamp', selected.created_at],
                ['Usuário', selected.user_login ?? '—'],
                ['Modelo', selected.model ?? '—'],
                ['Endpoint', selected.endpoint ?? '—'],
              ].map(([k, v]) => (
                <div key={k} style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: '#555', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 4 }}>{k}</div>
                  <div style={{ fontSize: 13, color: '#ccc', fontFamily: 'monospace' }}>{v}</div>
                </div>
              ))}

              <div className="grid grid-cols-3 gap-3">
                {[
                  ['Tokens', selected.total_tokens?.toLocaleString(), '#fff'],
                  ['Custo', selected.cost_fmt ?? `$${selected.cost_usd?.toFixed(4)}`, COPPER],
                  ['Latência', selected.latency_fmt ?? `${selected.latency_ms}ms`, TEAL],
                ].map(([k, v, c]) => (
                  <div key={k} style={{ background: GLASS, border: BORDER, borderRadius: 8, padding: '10px 12px' }}>
                    <div style={{ fontSize: 9, color: '#555', textTransform: 'uppercase', fontWeight: 700 }}>{k}</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: c, fontFamily: 'monospace' }}>{v}</div>
                  </div>
                ))}
              </div>

              {selected.prompt_preview && (
                <div style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: '#555', textTransform: 'uppercase', marginBottom: 6 }}>Prompt Preview</div>
                  <p style={{ fontSize: 12, color: '#888', lineHeight: 1.6, fontFamily: 'monospace' }}>{selected.prompt_preview}</p>
                </div>
              )}

              {selected.error_msg && (
                <div style={{ background: `${RED}08`, border: `1px solid ${RED}30`, borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: RED, textTransform: 'uppercase', marginBottom: 6 }}>Erro</div>
                  <p style={{ fontSize: 12, color: '#ccc' }}>{selected.error_msg}</p>
                </div>
              )}

              <div style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '12px 14px' }}>
                <div style={{ fontSize: 9, fontWeight: 700, color: '#555', textTransform: 'uppercase', marginBottom: 6 }}>Metadata JSON</div>
                <pre style={{ fontSize: 10, color: '#555', fontFamily: 'monospace', overflow: 'auto', maxHeight: 240 }}>
                  {JSON.stringify(selected, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
