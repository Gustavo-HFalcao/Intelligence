import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  Shield, CheckCircle, XCircle, ChevronRight, X,
  CalendarDays, User, Tag, Search, Filter, RefreshCw,
} from 'lucide-react'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

const CATEGORY_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  login:     { label: 'Login',     color: TEAL,    bg: `${TEAL}18` },
  edit:      { label: 'Edição',    color: COPPER,  bg: `${COPPER}18` },
  delete:    { label: 'Exclusão',  color: RED,     bg: `${RED}18` },
  create:    { label: 'Criação',   color: '#3B82F6', bg: 'rgba(59,130,246,0.15)' },
  export:    { label: 'Exportação',color: '#8B5CF6', bg: 'rgba(139,92,246,0.15)' },
  ai:        { label: 'IA',        color: '#F59E0B', bg: 'rgba(245,158,11,0.15)' },
  error:     { label: 'Erro',      color: RED,     bg: `${RED}18` },
  system:    { label: 'Sistema',   color: '#888',  bg: 'rgba(136,136,136,0.12)' },
}

async function api(path: string) {
  const r = await fetch(path, { credentials: 'include' })
  if (!r.ok) throw new Error()
  return r.json()
}

function CategoryBadge({ cat }: { cat: string }) {
  const cfg = CATEGORY_CONFIG[cat] ?? { label: cat, color: '#888', bg: 'rgba(136,136,136,0.12)' }
  return (
    <span style={{ color: cfg.color, background: cfg.bg, fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6, textTransform: 'uppercase', letterSpacing: '0.08em', border: `1px solid ${cfg.color}30` }}>
      {cfg.label}
    </span>
  )
}

export default function LogsAuditoria() {
  const [page, setPage]         = useState(1)
  const [category, setCategory] = useState('')
  const [search, setSearch]     = useState('')
  const [userFilter, setUser]   = useState('')
  const [onlyErrors, setErrors] = useState(false)
  const [selected, setSelected] = useState<any>(null)

  const qs = new URLSearchParams()
  qs.set('page', String(page))
  if (category) qs.set('category', category)
  if (search)   qs.set('search', search)
  if (userFilter) qs.set('user', userFilter)
  if (onlyErrors) qs.set('errors_only', '1')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['audit-logs', page, category, search, userFilter, onlyErrors],
    queryFn:  () => api(`/api/obs/logs?${qs.toString()}`),
    staleTime: 15_000,
  })

  const { data: statsData } = useQuery({
    queryKey: ['audit-stats'],
    queryFn:  () => api('/api/obs/metricas'),
    staleTime: 60_000,
  })

  const logs: any[] = data?.logs ?? []
  const m = statsData ?? {}

  const CATEGORIES = ['login', 'edit', 'delete', 'create', 'export', 'ai', 'error', 'system']

  const stats = [
    { label: 'Eventos Hoje', value: m.today_events ?? logs.length, color: '#fff' },
    { label: 'Chamadas IA',  value: m.total_calls ?? 0, color: COPPER },
    { label: 'Erros',        value: m.error_count ?? logs.filter((l: any) => !l.success).length, color: RED },
    { label: 'Custo Total',  value: m.total_cost_fmt ?? 'US$ 0.00', color: TEAL },
  ]

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
            <Shield size={22} className="text-copper" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-white uppercase tracking-tight">Logs & Auditoria</h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">Trilha de eventos do sistema</p>
          </div>
        </div>
        <button
          onClick={() => refetch()}
          style={{ background: GLASS, border: BORDER, color: COPPER, borderRadius: 8, padding: '6px 14px', fontSize: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <RefreshCw size={12} /> Atualizar
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(s => (
          <div key={s.label} style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-4">
            <div className="text-[9px] font-bold text-text-muted uppercase tracking-widest mb-1">{s.label}</div>
            <div className="font-display text-xl font-bold" style={{ color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-4 flex flex-wrap gap-3 items-center">
        {/* Category chips */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => { setCategory(''); setPage(1) }}
            style={{ background: !category ? COPPER : 'rgba(255,255,255,0.05)', color: !category ? '#0d1117' : '#888', border: `1px solid ${!category ? COPPER : 'rgba(255,255,255,0.1)'}`, borderRadius: 6, padding: '4px 12px', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}
          >
            Todos
          </button>
          {CATEGORIES.map(cat => {
            const cfg = CATEGORY_CONFIG[cat]
            const active = category === cat
            return (
              <button key={cat} onClick={() => { setCategory(cat); setPage(1) }}
                style={{ background: active ? cfg.color + '20' : 'rgba(255,255,255,0.04)', color: active ? cfg.color : '#888', border: `1px solid ${active ? cfg.color + '40' : 'rgba(255,255,255,0.1)'}`, borderRadius: 6, padding: '4px 12px', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}
              >
                {cfg.label}
              </button>
            )
          })}
        </div>

        <div className="flex-1 min-w-0 flex gap-3">
          <div className="relative flex-1 min-w-[160px]">
            <Search size={12} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#555' }} />
            <input
              value={search} onChange={e => { setSearch(e.target.value); setPage(1) }}
              placeholder="Buscar ação..."
              style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, height: 32, paddingLeft: 28, paddingRight: 8, fontSize: 12, color: '#ccc', outline: 'none' }}
            />
          </div>
          <div className="relative">
            <User size={12} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#555' }} />
            <input
              value={userFilter} onChange={e => { setUser(e.target.value); setPage(1) }}
              placeholder="Usuário..."
              style={{ width: 140, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, height: 32, paddingLeft: 28, paddingRight: 8, fontSize: 12, color: '#ccc', outline: 'none' }}
            />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#888', cursor: 'pointer', userSelect: 'none' }}>
            <input type="checkbox" checked={onlyErrors} onChange={e => { setErrors(e.target.checked); setPage(1) }} />
            Só erros
          </label>
        </div>
      </div>

      {/* Table */}
      <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="overflow-x-auto">
        {isLoading && <div className="p-6 text-center text-text-muted text-sm animate-pulse">Carregando...</div>}
        <table className="w-full text-xs">
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(201,139,42,0.15)' }}>
              {['Timestamp', 'Categoria', 'Usuário', 'Ação / Entidade', 'Status', ''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-text-muted uppercase tracking-wider" style={{ fontSize: 9, fontWeight: 700 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {logs.map((l: any) => (
              <tr
                key={l.id}
                style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer' }}
                className="hover:bg-white/5 transition-colors group"
                onClick={() => setSelected(l)}
              >
                <td className="px-4 py-3 font-mono text-text-muted whitespace-nowrap">{l.created_at}</td>
                <td className="px-4 py-3"><CategoryBadge cat={l.category ?? (l.success === false ? 'error' : 'ai')} /></td>
                <td className="px-4 py-3 text-text-muted">{l.user_login ?? l.endpoint ?? '—'}</td>
                <td className="px-4 py-3">
                  <div className="text-white/80 font-medium">{l.model ?? l.action ?? '—'}</div>
                  {l.prompt_preview && <div className="text-[10px] text-text-muted mt-0.5 truncate max-w-[280px]">{l.prompt_preview}</div>}
                </td>
                <td className="px-4 py-3">
                  {l.success !== false
                    ? <CheckCircle size={13} style={{ color: TEAL }} />
                    : <XCircle size={13} style={{ color: RED }} aria-label={l.error_msg} />}
                </td>
                <td className="px-4 py-3">
                  <ChevronRight size={13} className="text-white/20 group-hover:text-copper transition-colors" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {logs.length === 0 && !isLoading && (
          <div className="p-10 text-center text-text-muted text-sm">Nenhum log encontrado.</div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex gap-2 justify-center items-center">
        <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
          style={{ background: GLASS, border: BORDER, color: '#888', borderRadius: 8, padding: '6px 16px', cursor: 'pointer', fontSize: 12 }}>← Anterior</button>
        <span className="text-xs text-text-muted font-mono">Página {page}</span>
        <button onClick={() => setPage(p => p + 1)} disabled={!data?.has_next}
          style={{ background: GLASS, border: BORDER, color: '#888', borderRadius: 8, padding: '6px 16px', cursor: 'pointer', fontSize: 12 }}>Próxima →</button>
      </div>

      {/* Detail Side Panel */}
      {selected && (
        <div className="fixed inset-0 z-[200] flex justify-end" onClick={() => setSelected(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            onClick={e => e.stopPropagation()}
            style={{ position: 'relative', width: 420, height: '100vh', background: '#0a0f0e', borderLeft: '1px solid rgba(201,139,42,0.2)', overflowY: 'auto', padding: 28 }}
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-sm font-black uppercase text-white tracking-widest">Detalhe do Log</h3>
              <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <div className="flex flex-col gap-4">
              {[
                { label: 'Timestamp', value: selected.created_at, icon: CalendarDays },
                { label: 'Usuário', value: selected.user_login ?? '—', icon: User },
                { label: 'Modelo / Ação', value: selected.model ?? selected.action ?? '—', icon: Tag },
              ].map(f => (
                <div key={f.label} style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '12px 14px' }}>
                  <div className="flex items-center gap-2 mb-1">
                    <f.icon size={11} style={{ color: COPPER }} />
                    <span style={{ fontSize: 9, fontWeight: 700, color: '#555', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{f.label}</span>
                  </div>
                  <div style={{ fontSize: 13, color: '#ccc', fontFamily: 'monospace' }}>{f.value}</div>
                </div>
              ))}

              {/* Tokens & Cost */}
              {selected.total_tokens != null && (
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { l: 'Tokens', v: selected.total_tokens?.toLocaleString(), color: '#fff' },
                    { l: 'Custo', v: selected.cost_fmt ?? `$${selected.cost_usd?.toFixed(4) ?? '0.0000'}`, color: COPPER },
                    { l: 'Latência', v: selected.latency_fmt ?? `${selected.latency_ms}ms`, color: TEAL },
                  ].map(k => (
                    <div key={k.l} style={{ background: GLASS, border: BORDER, borderRadius: 8, padding: '10px 12px' }}>
                      <div style={{ fontSize: 9, color: '#555', textTransform: 'uppercase', fontWeight: 700 }}>{k.l}</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: k.color, fontFamily: 'monospace' }}>{k.v}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Prompt preview */}
              {selected.prompt_preview && (
                <div style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: '#555', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>Prompt Preview</div>
                  <p style={{ fontSize: 12, color: '#888', lineHeight: 1.6, fontFamily: 'monospace' }}>{selected.prompt_preview}</p>
                </div>
              )}

              {/* Error */}
              {selected.error_msg && (
                <div style={{ background: `${RED}08`, border: `1px solid ${RED}30`, borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: RED, textTransform: 'uppercase', marginBottom: 6 }}>Erro</div>
                  <p style={{ fontSize: 12, color: '#ccc', lineHeight: 1.5 }}>{selected.error_msg}</p>
                </div>
              )}

              {/* Raw JSON */}
              <div style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '12px 14px' }}>
                <div style={{ fontSize: 9, fontWeight: 700, color: '#555', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>Metadata</div>
                <pre style={{ fontSize: 10, color: '#666', fontFamily: 'monospace', overflow: 'auto', maxHeight: 200 }}>
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
