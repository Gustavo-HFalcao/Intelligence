import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bell, BellOff, Plus, Trash2, Check, X, ChevronRight, ChevronLeft,
  Sun, CalendarDays, FileText, AlertTriangle, TrendingUp, Clock,
  Mic, MicOff, Mail, Building2, Volume2, Settings2, History,
  CheckCircle2, AlertCircle,
} from 'lucide-react'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

const ALERT_TYPE_META: Record<string, { icon: any; color: string; schedule: string; category: string }> = {
  daily:          { icon: Sun,           color: TEAL,       schedule: 'Todos os dias às 18h',         category: 'Cronológico' },
  weekly:         { icon: CalendarDays,  color: '#3B82F6',  schedule: 'Toda segunda-feira às 8h',     category: 'Cronológico' },
  monthly:        { icon: FileText,      color: COPPER,     schedule: 'Todo dia 25 às 9h',            category: 'Cronológico' },
  risk_high:      { icon: AlertTriangle, color: RED,        schedule: 'Verificado diariamente às 18h', category: 'Reativo' },
  budget_overage: { icon: TrendingUp,    color: '#F59E0B',  schedule: 'Verificado diariamente às 18h', category: 'Reativo' },
  rdo_pending:    { icon: Clock,         color: '#8B5CF6',  schedule: 'Verificado diariamente às 18h', category: 'Reativo' },
}

const WIZARD_METRICS = [
  { key: 'spi',            label: 'SPI (Performance Index)',       desc: 'Dispara quando SPI cai abaixo do limiar' },
  { key: 'progress_pct',   label: 'Progresso Físico (%)',          desc: 'Dispara quando progresso está abaixo do esperado' },
  { key: 'budget_pct',     label: 'Orçamento Executado (%)',       desc: 'Dispara quando gasto supera o planejado' },
  { key: 'days_to_end',    label: 'Dias até Término',              desc: 'Dispara quando faltam N dias para o deadline' },
  { key: 'rdo_gap_hours',  label: 'Horas sem RDO',                 desc: 'Dispara quando obra passa X horas sem RDO' },
  { key: 'risk_score',     label: 'Nota de Risco (0–10)',          desc: 'Dispara quando nota de risco ultrapassa limiar' },
]

const OPERATORS = [
  { key: 'gte', label: '≥  maior ou igual' },
  { key: 'lte', label: '≤  menor ou igual' },
  { key: 'eq',  label: '=  igual' },
]

async function api(path: string, opts?: RequestInit) {
  const r = await fetch(path, { credentials: 'include', ...opts })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TabBar({ tab, setTab }: { tab: string; setTab: (t: string) => void }) {
  const tabs = [['regras', 'Minhas Regras'], ['criar', 'Criar Alerta'], ['historico', 'Histórico']]
  return (
    <div className="flex gap-1 border-b" style={{ borderColor: 'rgba(201,139,42,0.15)' }}>
      {tabs.map(([t, l]) => (
        <button key={t} onClick={() => setTab(t)}
          style={{
            background: 'none', border: 'none', padding: '10px 20px', fontSize: 13, cursor: 'pointer',
            color: tab === t ? COPPER : '#888', fontWeight: tab === t ? 700 : 400,
            borderBottom: tab === t ? `2px solid ${COPPER}` : '2px solid transparent',
          }}>{l}</button>
      ))}
    </div>
  )
}

// ── Minhas Regras tab ─────────────────────────────────────────────────────────

function RegrasTab() {
  const qc = useQueryClient()
  const { data: subData } = useQuery({ queryKey: ['alertas-subs'], queryFn: () => api('/api/alertas/subscriptions') })
  const { data: tiposData } = useQuery({ queryKey: ['alertas-tipos'], queryFn: () => api('/api/alertas/tipos') })
  const { data: rulesData } = useQuery({ queryKey: ['alertas-rules'], queryFn: () => api('/api/alertas/rules') })

  const toggleMut = useMutation({
    mutationFn: (body: any) => api('/api/alertas/subscriptions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alertas-subs'] }),
  })
  const deleteRuleMut = useMutation({
    mutationFn: (id: string) => api(`/api/alertas/rules/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alertas-rules'] }),
  })

  const tipos: Record<string, any> = tiposData?.tipos ?? {}
  const subs: any[] = subData?.subscriptions ?? []
  const rules: any[] = rulesData?.rules ?? []

  // Build subscription map keyed by alert_type
  const subsMap: Record<string, any> = {}
  subs.forEach(s => { subsMap[s.alert_type] = s })

  return (
    <div className="flex flex-col gap-6">
      {/* Built-in alert types */}
      <div>
        <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-4">Alertas do Sistema</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(tipos).map(([key, info]: [string, any]) => {
            const meta = ALERT_TYPE_META[key] ?? { icon: Bell, color: COPPER, schedule: '', category: '' }
            const IconC = meta.icon
            const sub = subsMap[key]
            const isActive = sub?.is_active !== false
            return (
              <div key={key} style={{ background: GLASS, border: isActive ? `1px solid ${meta.color}30` : BORDER, borderRadius: 14, padding: '16px 18px' }}
                className="flex items-start gap-4">
                <div className="p-2.5 rounded-xl flex-shrink-0" style={{ background: meta.color + '15', border: `1px solid ${meta.color}30` }}>
                  <IconC size={16} style={{ color: meta.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-bold text-white">{info.label}</div>
                      <div className="text-[10px] text-text-muted mt-0.5">{info.description}</div>
                    </div>
                    <button
                      onClick={() => toggleMut.mutate({ alert_type: key, contrato: '', is_active: !isActive })}
                      style={{
                        background: isActive ? `${TEAL}20` : GLASS, border: `1px solid ${isActive ? TEAL : '#444'}`,
                        color: isActive ? TEAL : '#666', borderRadius: 8, padding: '4px 12px', fontSize: 11, fontWeight: 700, cursor: 'pointer', flexShrink: 0,
                      }}>
                      {isActive ? 'Ativo' : 'Inativo'}
                    </button>
                  </div>
                  <div className="mt-2 flex items-center gap-3">
                    <span style={{ fontSize: 9, color: meta.color, background: meta.color + '15', borderRadius: 4, padding: '2px 7px', fontWeight: 700 }}>{meta.category}</span>
                    <span className="text-[10px] text-text-muted">{meta.schedule}</span>
                    {sub?.count && Number(sub.count) > 0 && (
                      <span className="text-[10px] text-text-muted flex items-center gap-1">
                        <Mail size={9} /> {sub.count} destinatário(s)
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Custom rules */}
      {rules.length > 0 && (
        <div>
          <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted mb-4">Regras Personalizadas</h3>
          <div className="flex flex-col gap-3">
            {rules.map((r: any) => (
              <div key={r.id} style={{ background: GLASS, border: BORDER, borderRadius: 12, padding: '14px 16px' }}
                className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="text-sm font-bold text-white">{r.name}</div>
                  <div className="text-[10px] text-text-muted mt-1">
                    {r.metric} {r.operator} {r.threshold} · {r.contrato || 'Global'} · {r.channel}
                  </div>
                </div>
                <div style={{ fontSize: 10, color: r.is_active ? TEAL : '#555', background: r.is_active ? `${TEAL}15` : 'rgba(255,255,255,0.04)', borderRadius: 6, padding: '2px 8px', fontWeight: 700 }}>
                  {r.is_active ? 'Ativo' : 'Inativo'}
                </div>
                <button onClick={() => deleteRuleMut.mutate(r.id)} className="p-2 hover:bg-red-500/20 rounded-lg text-red-500/50 hover:text-red-400 transition-colors">
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {subs.length === 0 && rules.length === 0 && (
        <div className="p-16 text-center text-text-muted flex flex-col items-center gap-3">
          <BellOff size={32} className="opacity-20" />
          <p className="text-xs uppercase tracking-widest font-bold">Nenhuma regra configurada</p>
        </div>
      )}
    </div>
  )
}

// ── Criar Alerta Wizard ───────────────────────────────────────────────────────

function CriarTab() {
  const qc = useQueryClient()
  const [step, setStep] = useState(0) // 0=O que, 1=Quando, 2=Quem
  const [form, setForm] = useState<Record<string, any>>({
    category: 'threshold', metric: 'spi', operator: 'lte', threshold: 0.85,
    name: '', channel: 'email', recipients: '', contrato: '', is_active: true,
  })
  const [voiceActive, setVoiceActive] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'ok' | 'err'>('idle')

  const { data: contratos } = useQuery({ queryKey: ['hub-contratos'], queryFn: () => api('/api/hub/contratos'), staleTime: 60_000 })
  const clList: any[] = contratos?.contratos ?? []

  const createMut = useMutation({
    mutationFn: (body: any) => api('/api/alertas/rules', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alertas-rules'] })
      setSaveStatus('ok')
      setTimeout(() => { setSaveStatus('idle'); setStep(0) }, 2000)
    },
    onError: () => setSaveStatus('err'),
  })

  // Voice input (Whisper)
  const mediaRef = useRef<MediaRecorder | null>(null)
  async function toggleVoice() {
    if (voiceActive && mediaRef.current) {
      mediaRef.current.stop()
      setVoiceActive(false)
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      const chunks: Blob[] = []
      rec.ondataavailable = e => chunks.push(e.data)
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunks, { type: 'audio/webm' })
        const fd = new FormData()
        fd.append('file', blob, 'voice.webm')
        try {
          const res = await fetch('/api/ai/whisper', { method: 'POST', credentials: 'include', body: fd })
          const json = await res.json()
          if (json.text) setForm(f => ({ ...f, name: json.text.trim() }))
        } catch { /* ignore */ }
      }
      rec.start()
      mediaRef.current = rec
      setVoiceActive(true)
    } catch { /* no mic */ }
  }

  const STEPS = ['O que monitorar', 'Quando disparar', 'Quem notificar']

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {STEPS.map((s, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="flex items-center gap-2">
              <div style={{
                width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 700, flexShrink: 0,
                background: i < step ? TEAL : i === step ? COPPER : 'rgba(255,255,255,0.08)',
                color: i <= step ? '#0d1117' : '#666',
                border: i === step ? `2px solid ${COPPER}` : '2px solid transparent',
              }}>{i < step ? <CheckCircle2 size={14} /> : i + 1}</div>
              <span style={{ fontSize: 11, fontWeight: i === step ? 700 : 400, color: i === step ? COPPER : '#666' }}>{s}</span>
            </div>
            {i < STEPS.length - 1 && <div style={{ flex: 1, height: 1, background: i < step ? TEAL : 'rgba(255,255,255,0.08)', width: 24, flexShrink: 0 }} />}
          </div>
        ))}
      </div>

      {/* Step 0: O que monitorar */}
      {step === 0 && (
        <div style={{ background: GLASS, border: BORDER, borderRadius: 14, padding: 24 }} className="flex flex-col gap-4">
          <h3 className="text-sm font-black uppercase text-white">Selecione o que monitorar</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {WIZARD_METRICS.map(m => (
              <div key={m.key} onClick={() => setForm(f => ({ ...f, metric: m.key }))}
                style={{
                  background: form.metric === m.key ? `${COPPER}12` : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${form.metric === m.key ? COPPER + '50' : 'rgba(255,255,255,0.08)'}`,
                  borderRadius: 10, padding: '12px 14px', cursor: 'pointer',
                }}>
                <div className="text-xs font-bold text-white">{m.label}</div>
                <div className="text-[10px] text-text-muted mt-0.5">{m.desc}</div>
              </div>
            ))}
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-bold uppercase text-text-muted tracking-widest">Contrato (opcional — vazio = global)</label>
            <select value={form.contrato} onChange={e => setForm(f => ({ ...f, contrato: e.target.value }))}
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, height: 40, padding: '0 12px', fontSize: 13, color: '#ccc', outline: 'none' }}>
              <option value="">Global (todos os contratos)</option>
              {clList.map((c: any) => <option key={c.contrato} value={c.contrato}>{c.contrato} — {c.projeto}</option>)}
            </select>
          </div>
        </div>
      )}

      {/* Step 1: Quando disparar */}
      {step === 1 && (
        <div style={{ background: GLASS, border: BORDER, borderRadius: 14, padding: 24 }} className="flex flex-col gap-5">
          <h3 className="text-sm font-black uppercase text-white">Configure o gatilho</h3>
          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-bold uppercase text-text-muted tracking-widest">Operador</label>
            <div className="flex gap-2">
              {OPERATORS.map(op => (
                <button key={op.key} onClick={() => setForm(f => ({ ...f, operator: op.key }))}
                  style={{
                    flex: 1, background: form.operator === op.key ? `${COPPER}15` : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${form.operator === op.key ? COPPER + '50' : 'rgba(255,255,255,0.08)'}`,
                    borderRadius: 8, padding: '8px', fontSize: 12, fontWeight: 700, cursor: 'pointer',
                    color: form.operator === op.key ? COPPER : '#888',
                  }}>{op.label}</button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-bold uppercase text-text-muted tracking-widest">Valor limiar</label>
            <input
              type="number" step="0.01" value={form.threshold}
              onChange={e => setForm(f => ({ ...f, threshold: parseFloat(e.target.value) }))}
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, height: 44, padding: '0 14px', fontSize: 16, color: COPPER, fontFamily: 'monospace', fontWeight: 700, outline: 'none', width: '100%' }}
            />
            <p className="text-[10px] text-text-muted">
              Exemplo: {form.metric} {form.operator === 'gte' ? '≥' : form.operator === 'lte' ? '≤' : '='} {form.threshold}
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-bold uppercase text-text-muted tracking-widest">Canal de notificação</label>
            <div className="flex gap-2">
              {['email', 'whatsapp', 'sistema'].map(ch => (
                <button key={ch} onClick={() => setForm(f => ({ ...f, channel: ch }))}
                  style={{
                    flex: 1, background: form.channel === ch ? `${TEAL}15` : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${form.channel === ch ? TEAL + '50' : 'rgba(255,255,255,0.08)'}`,
                    borderRadius: 8, padding: '8px', fontSize: 11, fontWeight: 700, cursor: 'pointer',
                    color: form.channel === ch ? TEAL : '#888', textTransform: 'uppercase',
                  }}>{ch}</button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Quem notificar */}
      {step === 2 && (
        <div style={{ background: GLASS, border: BORDER, borderRadius: 14, padding: 24 }} className="flex flex-col gap-5">
          <h3 className="text-sm font-black uppercase text-white">Nomeie e configure destinatários</h3>

          {/* Nome da regra — com voice input */}
          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-bold uppercase text-text-muted tracking-widest">Nome da Regra</label>
            <div className="relative">
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="Ex: Alerta crítico de SPI baixo"
                style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, height: 44, padding: '0 44px 0 14px', fontSize: 13, color: '#fff', outline: 'none' }}
              />
              <button onClick={toggleVoice}
                style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: voiceActive ? RED : '#555' }}>
                {voiceActive ? <MicOff size={16} /> : <Mic size={16} />}
              </button>
            </div>
            {voiceActive && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: RED }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: RED, animation: 'pulse 1s infinite' }} />
                Gravando… clique no microfone para parar
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-bold uppercase text-text-muted tracking-widest">Destinatários (emails separados por vírgula)</label>
            <input value={form.recipients} onChange={e => setForm(f => ({ ...f, recipients: e.target.value }))}
              placeholder="fulano@empresa.com, ciclano@empresa.com"
              style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, height: 44, padding: '0 14px', fontSize: 13, color: '#ccc', outline: 'none' }}
            />
          </div>

          {/* Summary */}
          <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: '14px 16px' }}>
            <div className="text-[10px] font-bold uppercase text-text-muted tracking-widest mb-3">Resumo da Regra</div>
            <div className="space-y-1.5">
              {[
                ['Métrica', WIZARD_METRICS.find(m => m.key === form.metric)?.label ?? form.metric],
                ['Operador', OPERATORS.find(o => o.key === form.operator)?.label ?? form.operator],
                ['Limiar', String(form.threshold)],
                ['Canal', form.channel],
                ['Contrato', form.contrato || 'Global'],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between text-xs">
                  <span className="text-text-muted">{k}</span>
                  <span className="text-white font-mono font-bold">{v}</span>
                </div>
              ))}
            </div>
          </div>

          {saveStatus === 'ok' && (
            <div style={{ background: `${TEAL}15`, border: `1px solid ${TEAL}40`, borderRadius: 8, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: TEAL, fontWeight: 700 }}>
              <CheckCircle2 size={14} /> Regra criada com sucesso!
            </div>
          )}
          {saveStatus === 'err' && (
            <div style={{ background: `${RED}15`, border: `1px solid ${RED}40`, borderRadius: 8, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: RED, fontWeight: 700 }}>
              <AlertCircle size={14} /> Erro ao salvar. Tente novamente.
            </div>
          )}
        </div>
      )}

      {/* Navigation buttons */}
      <div className="flex gap-3">
        {step > 0 && (
          <button onClick={() => setStep(s => s - 1)}
            style={{ display: 'flex', alignItems: 'center', gap: 6, background: GLASS, border: BORDER, color: '#888', borderRadius: 8, padding: '10px 20px', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
            <ChevronLeft size={14} /> Voltar
          </button>
        )}
        {step < 2 ? (
          <button onClick={() => setStep(s => s + 1)}
            style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, background: COPPER, color: '#0d1117', border: 'none', borderRadius: 8, padding: '10px 20px', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
            Próximo <ChevronRight size={14} />
          </button>
        ) : (
          <button onClick={() => { setSaveStatus('saving'); createMut.mutate(form) }} disabled={!form.name || saveStatus === 'saving'}
            style={{ flex: 1, background: saveStatus === 'saving' ? `${TEAL}80` : TEAL, color: '#0d1117', border: 'none', borderRadius: 8, padding: '10px 20px', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
            {saveStatus === 'saving' ? 'Salvando...' : '✓ Criar Alerta'}
          </button>
        )}
      </div>
    </div>
  )
}

// ── Histórico tab ─────────────────────────────────────────────────────────────

function HistoricoTab() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [contrato, setContrato] = useState('')

  const { data: contratos } = useQuery({ queryKey: ['hub-contratos'], queryFn: () => api('/api/hub/contratos'), staleTime: 60_000 })
  const { data: histData } = useQuery({
    queryKey: ['alertas-hist', page, contrato],
    queryFn: () => api(`/api/alertas/history?page=${page}${contrato ? `&contrato=${contrato}` : ''}`),
    staleTime: 15_000,
  })

  const markReadMut = useMutation({
    mutationFn: (id: string) => api(`/api/alertas/history/${id}/read`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: '{}' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alertas-hist'] }),
  })

  const hist: any[] = histData?.history ?? []
  const clList: any[] = contratos?.contratos ?? []
  const unread = hist.filter(h => !h.is_read).length

  return (
    <div className="flex flex-col gap-4">
      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        {unread > 0 && (
          <span style={{ background: `${RED}15`, border: `1px solid ${RED}30`, color: RED, fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 6 }}>
            {unread} não lido(s)
          </span>
        )}
        <select value={contrato} onChange={e => { setContrato(e.target.value); setPage(1) }}
          style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, height: 36, padding: '0 12px', fontSize: 12, color: '#ccc', outline: 'none' }}>
          <option value="">Todos os contratos</option>
          {clList.map((c: any) => <option key={c.contrato} value={c.contrato}>{c.contrato}</option>)}
        </select>
      </div>

      <div className="flex flex-col gap-2">
        {hist.map((h: any) => (
          <motion.div
            key={h.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: h.is_read ? 0.55 : 1 }}
            style={{ background: GLASS, border: `1px solid ${h.is_read ? 'rgba(255,255,255,0.05)' : h.alert_color + '25'}`, borderRadius: 12, padding: '14px 16px' }}
            className="flex items-start gap-3"
          >
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: h.alert_color, flexShrink: 0, marginTop: 4 }} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span style={{ color: h.alert_color, fontSize: 11, fontWeight: 700 }}>{h.alert_label}</span>
                {h.contract && h.contract !== '—' && (
                  <span style={{ fontSize: 10, color: '#555', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Building2 size={9} /> {h.contract}
                  </span>
                )}
              </div>
              <div className="text-sm text-white/80">{h.message}</div>
              <div className="text-[10px] text-text-muted mt-1 flex items-center gap-1">
                <CalendarDays size={9} /> {h.timestamp}
              </div>
            </div>
            {!h.is_read && (
              <button onClick={() => markReadMut.mutate(h.id)}
                style={{ background: 'none', border: `1px solid ${TEAL}`, color: TEAL, borderRadius: 6, padding: '4px 8px', cursor: 'pointer', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
                <Check size={11} /> Lido
              </button>
            )}
          </motion.div>
        ))}
        {hist.length === 0 && (
          <div className="p-14 text-center text-text-muted flex flex-col items-center gap-3">
            <History size={32} className="opacity-20" />
            <p className="text-xs uppercase tracking-widest font-bold">Nenhum evento no histórico</p>
          </div>
        )}
      </div>

      <div className="flex gap-2 justify-center items-center">
        <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
          style={{ background: GLASS, border: BORDER, color: '#888', borderRadius: 8, padding: '6px 16px', cursor: 'pointer', fontSize: 12 }}>← Anterior</button>
        <span className="text-xs text-text-muted font-mono">Página {page}</span>
        <button onClick={() => setPage(p => p + 1)} disabled={!histData?.has_next}
          style={{ background: GLASS, border: BORDER, color: '#888', borderRadius: 8, padding: '6px 16px', cursor: 'pointer', fontSize: 12 }}>Próxima →</button>
      </div>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function Alertas() {
  const [tab, setTab] = useState('regras')

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
          <Bell size={22} className="text-copper" />
        </div>
        <div>
          <h1 className="font-display text-2xl font-black text-white uppercase tracking-tight">Gestão de Alertas</h1>
          <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">Monitoramento proativo com IA · Notificação por voz, email e sistema</p>
        </div>
      </div>

      <TabBar tab={tab} setTab={setTab} />

      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.18 }}>
          {tab === 'regras'    && <RegrasTab />}
          {tab === 'criar'     && <CriarTab />}
          {tab === 'historico' && <HistoricoTab />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
