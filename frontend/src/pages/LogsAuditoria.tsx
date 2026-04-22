import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  Shield, CheckCircle, XCircle, ChevronRight, X,
  CalendarDays, User, Tag, Search, RefreshCw, Activity,
} from 'lucide-react'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

// Audit categories from backend/core/audit.py
const AUDIT_CATS: Record<string, { label: string; color: string }> = {
  LOGIN:            { label: 'Login',        color: TEAL },
  LOGOUT:           { label: 'Logout',       color: '#889999' },
  DATA_EDIT:        { label: 'Edição',       color: COPPER },
  DATA_UPLOAD:      { label: 'Upload',       color: '#E0A63B' },
  DATA_SAVE:        { label: 'Salvar',       color: TEAL },
  DATA_DELETE:      { label: 'Exclusão',     color: RED },
  RDO_CREATE:       { label: 'RDO',          color: '#3B82F6' },
  REEMBOLSO_CREATE: { label: 'Reembolso',   color: '#8B5CF6' },
  REPORT_GEN:       { label: 'Relatório',   color: '#06B6D4' },
  AI_CHAT:          { label: 'Chat IA',     color: '#F59E0B' },
  AI_INSIGHT:       { label: 'Insight IA',  color: '#F59E0B' },
  ALERT_TRIGGER:    { label: 'Alerta',      color: RED },
  ALERT_CONFIG:     { label: 'Config Alerta', color: COPPER },
  USER_MGMT:        { label: 'Usuários',    color: '#8B5CF6' },
  ERROR:            { label: 'Erro',        color: RED },
  SYSTEM:           { label: 'Sistema',     color: '#6B7280' },
}

async function api(path: string) {
  const r = await fetch(path, { credentials: 'include' })
  if (!r.ok) throw new Error()
  return r.json()
}

function CatBadge({ cat }: { cat: string }) {
  const cfg = AUDIT_CATS[cat] ?? { label: cat, color: '#888' }
  return (
    <span style={{
      color: cfg.color,
      background: `${cfg.color}18`,
      fontSize: 9,
      fontWeight: 700,
      padding: '2px 7px',
      borderRadius: 5,
      textTransform: 'uppercase',
      letterSpacing: '0.07em',
      border: `1px solid ${cfg.color}30`,
      whiteSpace: 'nowrap',
    }}>
      {cfg.label}
    </span>
  )
}

type Tab = 'audit' | 'llm'

export default function LogsAuditoria() {
  const [tab, setTab]           = useState<Tab>('audit')
  const [page, setPage]         = useState(1)
  const [category, setCategory] = useState('')
  const [search, setSearch]     = useState('')
  const [userFilter, setUser]   = useState('')
  const [onlyErrors, setErrors] = useState(false)
  const [selected, setSelected] = useState<any>(null)

  // Audit logs
  const auditQs = new URLSearchParams({ page: String(page) })
  if (category)   auditQs.set('category', category)
  if (search)     auditQs.set('search', search)
  if (userFilter) auditQs.set('username', userFilter)
  if (onlyErrors) auditQs.set('status', 'error')

  const { data: auditData, isLoading: auditLoading, refetch: refetchAudit } = useQuery({
    queryKey: ['system-logs', page, category, search, userFilter, onlyErrors],
    queryFn:  () => api(`/api/obs/system-logs?${auditQs.toString()}`),
    staleTime: 15_000,
    enabled: tab === 'audit',
  })

  // LLM observability
  const llmQs = new URLSearchParams({ page: String(page) })
  const { data: llmData, isLoading: llmLoading, refetch: refetchLlm } = useQuery({
    queryKey: ['llm-logs', page],
    queryFn:  () => api(`/api/obs/logs?${llmQs.toString()}`),
    staleTime: 15_000,
    enabled: tab === 'llm',
  })

  const { data: llmMetrics } = useQuery({
    queryKey: ['llm-metrics'],
    queryFn:  () => api('/api/obs/metricas'),
    staleTime: 60_000,
  })

  const logs   = tab === 'audit' ? (auditData?.logs ?? []) : (llmData?.logs ?? [])
  const hasNext = tab === 'audit' ? !!auditData?.has_next : !!llmData?.has_next
  const loading = tab === 'audit' ? auditLoading : llmLoading
  const m = llmMetrics ?? {}

  function handleTabChange(t: Tab) {
    setTab(t)
    setPage(1)
    setSelected(null)
    setCategory('')
    setSearch('')
    setUser('')
    setErrors(false)
  }

  const auditStats = [
    { label: 'Registros', value: auditData?.logs?.length ?? '—', color: '#fff' },
    { label: 'Erros', value: auditData?.logs?.filter((l: any) => l.status === 'error').length ?? 0, color: RED },
  ]
  const llmStats = [
    { label: 'Chamadas IA', value: m.total_calls ?? 0, color: COPPER },
    { label: 'Custo Total', value: m.total_cost_fmt ?? 'US$ 0.00', color: TEAL },
    { label: 'Erros', value: m.errors ?? 0, color: RED },
    { label: 'Lat. Média', value: m.avg_latency_ms ? `${m.avg_latency_ms}ms` : '—', color: '#888' },
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
          onClick={() => tab === 'audit' ? refetchAudit() : refetchLlm()}
          style={{ background: GLASS, border: BORDER, color: COPPER, borderRadius: 8, padding: '6px 14px', fontSize: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <RefreshCw size={12} /> Atualizar
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {([['audit','Auditoria do Sistema', Shield], ['llm','Observabilidade IA', Activity]] as const).map(([t, label, Icon]) => (
          <button key={t} onClick={() => handleTabChange(t as Tab)}
            style={{
              background: tab === t ? `${COPPER}18` : GLASS,
              border: tab === t ? `1px solid ${COPPER}50` : BORDER,
              color: tab === t ? COPPER : '#888',
              borderRadius: 8,
              padding: '7px 16px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}>
            <Icon size={13} />{label}
          </button>
        ))}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {(tab === 'audit' ? auditStats : llmStats).map(s => (
          <div key={s.label} style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-4">
            <div className="text-[9px] font-bold text-text-muted uppercase tracking-widest mb-1">{s.label}</div>
            <div className="font-display text-xl font-bold" style={{ color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Filters — audit tab only */}
      {tab === 'audit' && (
        <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-4 flex flex-wrap gap-3 items-center">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => { setCategory(''); setPage(1) }}
              style={{ background: !category ? COPPER : 'rgba(255,255,255,0.05)', color: !category ? '#0d1117' : '#888', border: `1px solid ${!category ? COPPER : 'rgba(255,255,255,0.1)'}`, borderRadius: 6, padding: '4px 12px', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}
            >
              Todas
            </button>
            {Object.entries(AUDIT_CATS).map(([key, cfg]) => {
              const active = category === key
              return (
                <button key={key} onClick={() => { setCategory(key); setPage(1) }}
                  style={{ background: active ? `${cfg.color}20` : 'rgba(255,255,255,0.04)', color: active ? cfg.color : '#888', border: `1px solid ${active ? `${cfg.color}40` : 'rgba(255,255,255,0.1)'}`, borderRadius: 6, padding: '4px 12px', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}
                >
                  {cfg.label}
                </button>
              )
            })}
          </div>

          <div className="flex gap-3 items-center flex-1 min-w-0">
            <div className="relative flex-1 min-w-[140px]">
              <Search size={12} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#555' }} />
              <input value={search} onChange={e => { setSearch(e.target.value); setPage(1) }} placeholder="Buscar ação..."
                style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, height: 32, paddingLeft: 28, paddingRight: 8, fontSize: 12, color: '#ccc', outline: 'none' }} />
            </div>
            <div className="relative">
              <User size={12} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#555' }} />
              <input value={userFilter} onChange={e => { setUser(e.target.value); setPage(1) }} placeholder="Usuário..."
                style={{ width: 130, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, height: 32, paddingLeft: 28, paddingRight: 8, fontSize: 12, color: '#ccc', outline: 'none' }} />
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#888', cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}>
              <input type="checkbox" checked={onlyErrors} onChange={e => { setErrors(e.target.checked); setPage(1) }} />
              Só erros
            </label>
          </div>
        </div>
      )}

      {/* Table */}
      <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="overflow-x-auto">
        {loading && <div className="p-6 text-center text-text-muted text-sm animate-pulse">Carregando...</div>}

        {tab === 'audit' ? (
          <table className="w-full text-xs">
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(201,139,42,0.15)' }}>
                {['Timestamp', 'Categoria', 'Usuário', 'Ação', 'Entidade', 'Status', ''].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-text-muted uppercase tracking-wider" style={{ fontSize: 9, fontWeight: 700 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.map((l: any) => (
                <tr key={l.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer' }}
                  className="hover:bg-white/5 transition-colors group" onClick={() => setSelected(l)}>
                  <td className="px-4 py-3 font-mono text-text-muted whitespace-nowrap">{l.created_at}</td>
                  <td className="px-4 py-3"><CatBadge cat={l.action_category} /></td>
                  <td className="px-4 py-3 text-text-muted">{l.username}</td>
                  <td className="px-4 py-3 text-white/80 max-w-[260px] truncate">{l.action}</td>
                  <td className="px-4 py-3 text-text-muted text-[10px]">{l.entity_type}{l.entity_id ? ` #${l.entity_id.slice(0, 8)}` : ''}</td>
                  <td className="px-4 py-3">
                    {l.status === 'error'
                      ? <XCircle size={13} style={{ color: RED }} />
                      : <CheckCircle size={13} style={{ color: TEAL }} />}
                  </td>
                  <td className="px-4 py-3">
                    <ChevronRight size={13} className="text-white/20 group-hover:text-copper transition-colors" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(201,139,42,0.15)' }}>
                {['Timestamp', 'Modelo', 'Endpoint', 'Usuário', 'Tokens', 'Custo', 'Latência', 'Status', ''].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-text-muted uppercase tracking-wider" style={{ fontSize: 9, fontWeight: 700 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.map((l: any) => (
                <tr key={l.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer' }}
                  className="hover:bg-white/5 transition-colors group" onClick={() => setSelected(l)}>
                  <td className="px-4 py-3 font-mono text-text-muted whitespace-nowrap">{l.created_at}</td>
                  <td className="px-4 py-3 text-white/80 text-[10px] font-mono">{l.model}</td>
                  <td className="px-4 py-3 text-text-muted text-[10px]">{l.endpoint}</td>
                  <td className="px-4 py-3 text-text-muted">{l.user_login}</td>
                  <td className="px-4 py-3 font-mono" style={{ color: COPPER }}>{l.total_tokens?.toLocaleString()}</td>
                  <td className="px-4 py-3 font-mono" style={{ color: TEAL }}>{l.cost_fmt}</td>
                  <td className="px-4 py-3 text-text-muted font-mono">{l.latency_fmt}</td>
                  <td className="px-4 py-3">
                    {l.success !== false
                      ? <CheckCircle size={13} style={{ color: TEAL }} />
                      : <XCircle size={13} style={{ color: RED }} />}
                  </td>
                  <td className="px-4 py-3">
                    <ChevronRight size={13} className="text-white/20 group-hover:text-copper transition-colors" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {logs.length === 0 && !loading && (
          <div className="p-10 text-center text-text-muted text-sm">Nenhum registro encontrado.</div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex gap-2 justify-center items-center">
        <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
          style={{ background: GLASS, border: BORDER, color: '#888', borderRadius: 8, padding: '6px 16px', cursor: 'pointer', fontSize: 12 }}>← Anterior</button>
        <span className="text-xs text-text-muted font-mono">Página {page}</span>
        <button onClick={() => setPage(p => p + 1)} disabled={!hasNext}
          style={{ background: GLASS, border: BORDER, color: '#888', borderRadius: 8, padding: '6px 16px', cursor: 'pointer', fontSize: 12 }}>Próxima →</button>
      </div>

      {/* Detail panel */}
      {selected && (
        <div className="fixed inset-0 z-[200] flex justify-end" onClick={() => setSelected(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div onClick={e => e.stopPropagation()}
            style={{ position: 'relative', width: 440, height: '100vh', background: '#0a0f0e', borderLeft: '1px solid rgba(201,139,42,0.2)', overflowY: 'auto', padding: 28 }}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-sm font-black uppercase text-white tracking-widest">Detalhe</h3>
              <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <div className="flex flex-col gap-4">
              {[
                { label: 'Timestamp', value: selected.created_at, icon: CalendarDays },
                { label: 'Usuário', value: selected.username ?? selected.user_login ?? '—', icon: User },
                { label: 'Categoria / Modelo', value: selected.action_category ?? selected.model ?? '—', icon: Tag },
              ].map(f => (
                <div key={f.label} style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '12px 14px' }}>
                  <div className="flex items-center gap-2 mb-1">
                    <f.icon size={11} style={{ color: COPPER }} />
                    <span style={{ fontSize: 9, fontWeight: 700, color: '#555', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{f.label}</span>
                  </div>
                  <div style={{ fontSize: 13, color: '#ccc', fontFamily: 'monospace' }}>{f.value}</div>
                </div>
              ))}

              {selected.action && (
                <div style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: '#555', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>Ação</div>
                  <p style={{ fontSize: 12, color: '#ccc', lineHeight: 1.6 }}>{selected.action}</p>
                </div>
              )}

              {selected.total_tokens != null && (
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { l: 'Tokens', v: selected.total_tokens?.toLocaleString(), color: '#fff' },
                    { l: 'Custo', v: selected.cost_fmt, color: COPPER },
                    { l: 'Latência', v: selected.latency_fmt, color: TEAL },
                  ].map(k => (
                    <div key={k.l} style={{ background: GLASS, border: BORDER, borderRadius: 8, padding: '10px 12px' }}>
                      <div style={{ fontSize: 9, color: '#555', textTransform: 'uppercase', fontWeight: 700 }}>{k.l}</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: k.color, fontFamily: 'monospace' }}>{k.v}</div>
                    </div>
                  ))}
                </div>
              )}

              {selected.prompt_preview && (
                <div style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: '#555', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>Prompt Preview</div>
                  <p style={{ fontSize: 12, color: '#888', lineHeight: 1.6, fontFamily: 'monospace' }}>{selected.prompt_preview}</p>
                </div>
              )}

              {selected.error_msg && (
                <div style={{ background: `${RED}08`, border: `1px solid ${RED}30`, borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: RED, textTransform: 'uppercase', marginBottom: 6 }}>Erro</div>
                  <p style={{ fontSize: 12, color: '#ccc', lineHeight: 1.5 }}>{selected.error_msg}</p>
                </div>
              )}

              <div style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '12px 14px' }}>
                <div style={{ fontSize: 9, fontWeight: 700, color: '#555', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>Metadata / Raw</div>
                <pre style={{ fontSize: 10, color: '#666', fontFamily: 'monospace', overflow: 'auto', maxHeight: 220 }}>
                  {JSON.stringify(selected.metadata ?? selected, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
