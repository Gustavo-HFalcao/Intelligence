import { useQuery, useQueryClient, useMutation, keepPreviousData } from '@tanstack/react-query'
import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, CartesianGrid, ComposedChart, ReferenceLine, Bar, BarChart, LabelList, Legend,
} from 'recharts'
import {
  Plus, Image as ImageIcon, Clock, Activity,
  AlertTriangle, CheckCircle, GanttChartIcon, List,
  Mic, CloudRain, Zap, TrendingDown, TrendingUp, BarChart2, Search,
  User, LayoutDashboard, ScanEye, GitBranch, Wallet, DollarSign,
  ArrowRight, Gauge, Sparkles, X, CalendarCheck, MinusCircle, ChevronDown,
  ChevronRight, Pencil, Trash2, CalendarRange, MapPin, HardHat,
  Download, Send, Paperclip, Bell, FileText, AlertOctagon, Banknote,
  Edit2, Building2, ShieldCheck, Calculator, PieChart, Info,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import ActivityModal from '@/components/ActivityModal'
import ProjectModal from '@/components/ProjectModal'
import GanttChart from '@/components/GanttChart'
import './Dashboard.css'
import api from '@/services/api'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

const TABS = [
  { id: 'visao_geral', label: 'Visão Geral', icon: LayoutDashboard },
  { id: 'dashboard',   label: 'Dashboard',   icon: BarChart2 },
  { id: 'cronograma',  label: 'Cronograma',  icon: List },
  { id: 'auditoria',   label: 'Auditoria',   icon: ScanEye },
  { id: 'timeline',    label: 'Timeline',    icon: GitBranch },
  { id: 'financeiro',  label: 'Financeiro',  icon: Wallet },
]

function _fmt(v: any) {
  const n = typeof v === 'number' ? v : parseFloat(v || '0')
  return new Intl.NumberFormat('pt-BR', { style:'currency', currency:'BRL' }).format(n)
}

function _iso_to_br(iso: string) {
  if (!iso) return '—'
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${y}`
}

function formatDateBR(iso?: string) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch { return '—' }
}

// ── Custom Recharts Tooltips ──────────────────────────────────────────────────

function TooltipShell({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      background: 'rgba(8,18,16,0.97)', border: '1px solid rgba(201,139,42,0.2)',
      borderRadius: 14, padding: '12px 16px', minWidth: 180,
      boxShadow: '0 16px 40px rgba(0,0,0,0.6), 0 0 0 1px rgba(201,139,42,0.08)',
      fontFamily: 'Outfit, sans-serif',
    }}>
      {children}
    </div>
  )
}

function TipLabel({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 9, fontWeight: 800, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 8 }}>{children}</div>
}

function TipRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, marginBottom: 4 }}>
      <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)', fontWeight: 600 }}>{label}</span>
      <span style={{ fontSize: 11, color: color || 'rgba(255,255,255,0.9)', fontWeight: 800, fontFamily: 'monospace' }}>{value}</span>
    </div>
  )
}

function SCurveTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const prev = payload.find((p: any) => p.dataKey === 'previsto')
  const real = payload.find((p: any) => p.dataKey === 'realizado')
  const desvio = real && prev ? (real.value - prev.value).toFixed(1) : null
  return (
    <TooltipShell>
      <TipLabel>{label}</TipLabel>
      {prev && <TipRow label="Planejado" value={`${prev.value}%`} color={COPPER} />}
      {real && <TipRow label="Realizado" value={`${real.value}%`} color={TEAL} />}
      {desvio !== null && (
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <TipRow
            label="Desvio"
            value={`${Number(desvio) >= 0 ? '+' : ''}${desvio}%`}
            color={Number(desvio) >= 0 ? TEAL : RED}
          />
        </div>
      )}
    </TooltipShell>
  )
}

function SPITip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const spi = payload[0]?.value
  const label2 = spi >= 1.05 ? 'Acima do ritmo' : spi >= 0.95 ? 'No ritmo' : 'Abaixo do ritmo'
  const col = spi >= 1.05 ? TEAL : spi >= 0.95 ? COPPER : RED
  return (
    <TooltipShell>
      <TipLabel>Performance · {label}</TipLabel>
      <TipRow label="SPI" value={spi?.toFixed(3)} color={col} />
      <div style={{ marginTop: 8, fontSize: 10, fontWeight: 700, color: col, background: col + '15', borderRadius: 6, padding: '3px 8px', display: 'inline-block' }}>{label2}</div>
    </TooltipShell>
  )
}

function ProdDiariaTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const real = payload.find((p: any) => p.dataKey === 'realizado')
  const prev = payload.find((p: any) => p.dataKey === 'previsto')
  const eff = real && prev && prev.value > 0 ? Math.round(real.value / prev.value * 100) : null
  return (
    <TooltipShell>
      <TipLabel>Produtividade · {label}</TipLabel>
      {prev && <TipRow label="Meta" value={`${prev.value}`} color={COPPER} />}
      {real && <TipRow label="Realizado" value={`${real.value}`} color={TEAL} />}
      {eff !== null && <TipRow label="Eficiência" value={`${eff}%`} color={eff >= 100 ? TEAL : RED} />}
    </TooltipShell>
  )
}

function DisciplinaTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const pct = payload[0]?.value
  return (
    <TooltipShell>
      <TipLabel>{label}</TipLabel>
      <TipRow label="Progresso" value={`${pct}%`} color={pct >= 80 ? TEAL : pct >= 50 ? COPPER : RED} />
      <div style={{ marginTop: 8, height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: pct >= 80 ? TEAL : pct >= 50 ? COPPER : RED, borderRadius: 4 }} />
      </div>
    </TooltipShell>
  )
}

function OrcamentoTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const prev = payload.find((p: any) => p.dataKey === 'previsto')
  const real = payload.find((p: any) => p.dataKey === 'realizado')
  return (
    <TooltipShell>
      <TipLabel>Orçamento · {label}</TipLabel>
      {prev && <TipRow label="Previsto" value={_fmt(prev.value)} color={COPPER} />}
      {real && <TipRow label="Realizado" value={_fmt(real.value)} color={TEAL} />}
    </TooltipShell>
  )
}

function SCurveFinTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const plan = payload.find((p: any) => p.dataKey === 'previsto_acum'  || p.dataKey === 'planejado')
  const real = payload.find((p: any) => p.dataKey === 'executado_acum' || p.dataKey === 'realizado')
  return (
    <TooltipShell>
      <TipLabel>S-Curve · {label}</TipLabel>
      {plan && <TipRow label="Baseline Acum." value={_fmt(plan.value)} color={COPPER} />}
      {real && <TipRow label="Executado Acum." value={_fmt(real.value)} color={TEAL} />}
    </TooltipShell>
  )
}

// ── Components ──────────────────────────────────────────────────────────────

const TIPO_CONFIG: Record<string, { icon: string; color: string }> = {
  risco:       { icon: '⚠', color: '#EF4444' },
  anomalia:    { icon: '🔴', color: '#dc2626' },
  producao:    { icon: '⚡', color: '#C98B2A' },
  oportunidade:{ icon: '✦', color: '#22c55e' },
  equipe:      { icon: '👥', color: '#3B82F6' },
  clima:       { icon: '🌧', color: '#2A9D8F' },
  delta:       { icon: '↗', color: '#A855F7' },
}

// Converte todas as datas ISO (YYYY-MM-DD) encontradas numa string para DD/MM/AAAA
function fmtDatasTexto(texto: string): string {
  if (!texto) return texto
  return texto.replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, '$3/$2/$1')
}

function InsightCard({ insight, idx }: { insight: any; idx: number }) {
  const priorityCfg: Record<string, { border: string; badge: string; badgeText: string }> = {
    High:   { border: 'border-red-500/40',   badge: 'bg-red-500/15 text-red-400 border border-red-500/30',   badgeText: 'CRÍTICO' },
    Medium: { border: 'border-copper/40',    badge: 'bg-copper/15 text-copper border border-copper/30',       badgeText: 'MÉDIO' },
    Low:    { border: 'border-teal-500/30',  badge: 'bg-teal-500/10 text-teal-400 border border-teal-500/20', badgeText: 'BAIXO' },
  }
  const cfg     = priorityCfg[insight.priority] || priorityCfg.Low
  const tipoCfg = TIPO_CONFIG[insight.tipo] || TIPO_CONFIG.risco
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.07 }}
      className={`bg-white/[0.03] border ${cfg.border} rounded-xl p-4 flex flex-col gap-2`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <span style={{ color: tipoCfg.color, fontSize: 12, lineHeight: 1 }}>{tipoCfg.icon}</span>
          <span className="text-[11px] font-black uppercase text-white leading-tight truncate">{fmtDatasTexto(insight.title)}</span>
        </div>
        <span className={`text-[8px] font-black px-2 py-0.5 rounded-full uppercase shrink-0 ${cfg.badge}`}>{cfg.badgeText}</span>
      </div>
      <p className="text-[11px] text-white/50 leading-relaxed">{fmtDatasTexto(insight.body)}</p>
    </motion.div>
  )
}

function OverviewTab({ contrato, contratoInfo }: { contrato: string; contratoInfo?: any }) {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['hub-visao-geral', contrato],
    queryFn:  () => api.get(`/hub/visao-geral?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    enabled:  !!contrato,
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  })
  const { data: insightsData, refetch: refetchInsights } = useQuery({
    queryKey: ['hub-agente-insights', contrato],
    queryFn:  () => api.get(`/hub/agente/insights?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    enabled:  !!contrato,
    staleTime: Infinity,
  })
  const [riscoOpen, setRiscoOpen] = useState(false)
  const [alertaOpen, setAlertaOpen] = useState(false)
  const [generatingInsights, setGeneratingInsights] = useState(false)
  const [liveInsights, setLiveInsights] = useState<any[] | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [chatMsgs, setChatMsgs] = useState<{role:'user'|'assistant'; content:string}[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatSessionId, setChatSessionId] = useState<string|null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  async function handleChatSend() {
    const msg = chatInput.trim()
    if (!msg || chatLoading) return
    setChatInput('')
    setChatMsgs(prev => [...prev, { role: 'user', content: msg }])
    setChatLoading(true)
    try {
      const res = await api.post('/hub/agente/chat', { contrato, mensagem: msg, session_id: chatSessionId })
      const { resposta, session_id } = res.data
      if (session_id && !chatSessionId) setChatSessionId(session_id)
      setChatMsgs(prev => [...prev, { role: 'assistant', content: resposta }])
    } catch {
      setChatMsgs(prev => [...prev, { role: 'assistant', content: 'Erro ao consultar o agente. Tente novamente.' }])
    } finally {
      setChatLoading(false)
    }
  }

  useEffect(() => {
    if (chatMsgs.length > 0) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [chatMsgs])

  async function handleGerarInsights() {
    setGeneratingInsights(true)
    try {
      // POST gera ao vivo e retorna inline — sem esperar Celery
      const res = await api.post(`/hub/agente/insights/generate`, { contrato })
      const fresh = res.data?.insights
      if (fresh?.length) {
        setLiveInsights(fresh)
        // Atualiza cache sem refetch
        queryClient.setQueryData(['hub-agente-insights', contrato], (old: any) => ({ ...old, insights: fresh }))
      }
    } finally {
      setGeneratingInsights(false)
    }
  }

  if (isLoading) return <Skeleton />
  const d = data ?? {}
  // liveInsights tem prioridade (resultado do botão), depois cache, depois visao-geral
  const insights: any[] = liveInsights ?? (insightsData?.insights?.length ? insightsData.insights : d.insights) ?? []

  // Coordenadas do contrato para o Windy — usa lat/lng do contrato ou default Brasil
  const windyLat = contratoInfo?.latitude ?? d.latitude ?? -15.78
  const windyLng = contratoInfo?.longitude ?? d.longitude ?? -47.93

  const desvio = d.desvio_pct ?? 0
  const desvioStr = desvio > 0 ? `+${desvio}%` : desvio < 0 ? `${desvio}%` : '0%'
  // desvio = realizado - esperado: positivo = adiantado (TEAL), negativo = atrasado (RED)
  const desvioColor = desvio > 0 ? TEAL : desvio < 0 ? RED : '#888'

  const cards = [
    { label: 'Progresso Físico', value: `${d.progress_pct ?? 0}%`, icon: Activity, color: COPPER, sub: 'Avanço Realizado', onClick: undefined },
    { label: 'Nota de Risco',   value: d.risk?.label || 'CONTROLADO', icon: AlertTriangle, color: d.risk?.color || TEAL, sub: `SCORE: ${d.risk?.nota ?? '—'}/10`, onClick: () => setRiscoOpen(true) },
    { label: 'Alerta IA',       value: d.atividades_criticas > 0 ? 'CRÍTICO' : 'NORMAL', icon: Zap, color: d.atividades_criticas > 0 ? RED : TEAL, sub: `${d.atividades_criticas ?? 0} Impedimentos`, onClick: () => setAlertaOpen(true) },
    { label: 'Desvio vs. Plan', value: desvioStr, icon: TrendingDown, color: desvioColor, sub: 'Realizado vs. Planejado', onClick: undefined },
    { label: 'Telemetria',      value: d.temperatura ? `${d.temperatura}°C` : '—', icon: CloudRain, color: TEAL, sub: d.clima_resumido || 'Sem dados', onClick: undefined },
  ]

  // Preenche até 4 cards para a grid do agente IA
  const insightCards = [...insights]
  while (insightCards.length < 4) insightCards.push(null)

  return (
    <div className="flex flex-col gap-6 animate-enter">
      {/* KPI pulse cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {cards.map(k => (
          <div
            key={k.label}
            onClick={k.onClick}
            style={{ background: GLASS, border: BORDER, borderRadius: 12, cursor: k.onClick ? 'pointer' : 'default' }}
            className="p-4 relative overflow-hidden group hover:bg-white/5 transition-colors"
          >
            <div className="text-[9px] text-text-muted uppercase font-black tracking-widest mb-1">{k.label}</div>
            <div className="font-display text-lg font-bold" style={{ color: k.color }}>{k.value}</div>
            <div className="text-[8px] text-white/30 uppercase mt-1 font-mono">{k.sub}</div>
            {k.onClick && <div className="absolute top-2 right-2 text-[8px] text-white/20 font-bold">↗</div>}
            <div className="absolute right-[-8px] bottom-[-8px] opacity-5 group-hover:scale-110 transition-transform">
               <k.icon size={48} />
            </div>
          </div>
        ))}
      </div>

      {/* Agente IA + Windy */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Agente de Inteligência Artificial */}
        <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(201,139,42,0.15)', borderRadius: 16 }} className="p-6 flex flex-col gap-4">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-copper/15 border border-copper/30 text-copper">
                <Sparkles size={18} />
              </div>
              <div>
                <h3 className="text-[11px] font-black uppercase tracking-[0.15em] text-white">Agente de Inteligência Artificial</h3>
                <p className="text-[9px] text-white/30 font-bold uppercase tracking-widest">Insights inteligentes baseados em cronograma + RDO</p>
              </div>
            </div>
            <button
              onClick={handleGerarInsights}
              disabled={generatingInsights}
              style={{ background: generatingInsights ? `${COPPER}80` : COPPER, color: '#0d1117', border: 'none', borderRadius: 8, padding: '6px 14px', fontSize: 11, fontWeight: 700, cursor: generatingInsights ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <Sparkles size={12} className={generatingInsights ? 'animate-spin' : ''} />
              {generatingInsights ? 'Analisando...' : 'Gerar Insights'}
            </button>
          </div>
          {/* 4 cards grid */}
          <div className="grid grid-cols-2 gap-3 flex-1">
            {insightCards.slice(0, 4).map((ins, i) =>
              ins ? (
                <InsightCard key={i} insight={ins} idx={i} />
              ) : (
                <div key={i} className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4 flex items-center justify-center">
                  <span className="text-[9px] text-white/15 font-black uppercase tracking-widest">Sem dados</span>
                </div>
              )
            )}
          </div>
        </div>

        {/* Chat com o Agente IA */}
        <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(42,157,143,0.2)', borderRadius: 16, minHeight: 400 }} className="flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-white/5">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-teal-500/15 border border-teal-500/25 text-teal-400"><Sparkles size={16}/></div>
              <div>
                <h3 className="text-[11px] font-black uppercase tracking-widest text-white">Pergunte ao Agente</h3>
                <p className="text-[9px] text-white/30 font-bold uppercase tracking-widest">Análise contextual da obra</p>
              </div>
            </div>
            {chatMsgs.length > 0 && (
              <button onClick={() => { setChatMsgs([]); setChatSessionId(null) }}
                style={{ fontSize: 9, color: '#888', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 6, padding: '3px 8px' }}>
                Limpar
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ maxHeight: 260 }}>
            {chatMsgs.length === 0 && (
              <div className="flex flex-col gap-2 pt-2">
                <p className="text-[10px] text-white/20 text-center pb-1">Exemplos de perguntas:</p>
                {[
                  'Se eu adicionar 2 pessoas na perfuração, quando termino?',
                  'Quais atividades posso antecipar essa semana?',
                  'Qual o impacto do atraso atual no prazo final?',
                ].map((q, i) => (
                  <button key={i} onClick={() => { setChatInput(q) }}
                    style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8, padding: '7px 10px', textAlign: 'left', color: 'rgba(255,255,255,0.4)', fontSize: 10, cursor: 'pointer' }}>
                    {q}
                  </button>
                ))}
              </div>
            )}
            {chatMsgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div style={{
                  maxWidth: '85%', padding: '8px 12px', borderRadius: m.role === 'user' ? '12px 12px 4px 12px' : '12px 12px 12px 4px',
                  background: m.role === 'user' ? 'rgba(201,139,42,0.15)' : 'rgba(42,157,143,0.1)',
                  border: `1px solid ${m.role === 'user' ? 'rgba(201,139,42,0.25)' : 'rgba(42,157,143,0.2)'}`,
                  fontSize: 11, color: m.role === 'user' ? '#e2c87a' : 'rgba(255,255,255,0.75)',
                  lineHeight: 1.5, whiteSpace: 'pre-wrap',
                }}>
                  {m.content}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="flex justify-start">
                <div style={{ padding: '8px 14px', borderRadius: '12px 12px 12px 4px', background: 'rgba(42,157,143,0.08)', border: '1px solid rgba(42,157,143,0.15)' }}>
                  <div className="flex gap-1">
                    {[0,1,2].map(i => <div key={i} className="w-1.5 h-1.5 rounded-full bg-teal-400/50 animate-bounce" style={{ animationDelay: `${i*0.15}s` }} />)}
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-white/5 flex gap-2">
            <input
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleChatSend()}
              placeholder="Pergunte sobre o cronograma, equipe, prazos..."
              style={{ flex: 1, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: '7px 10px', color: '#e2e8f0', fontSize: 11, outline: 'none' }}
            />
            <button onClick={handleChatSend} disabled={chatLoading || !chatInput.trim()}
              style={{ background: chatLoading || !chatInput.trim() ? 'rgba(42,157,143,0.3)' : '#2A9D8F', border: 'none', borderRadius: 8, padding: '7px 14px', color: '#fff', fontSize: 11, fontWeight: 700, cursor: chatLoading || !chatInput.trim() ? 'not-allowed' : 'pointer' }}>
              ↑
            </button>
          </div>
        </div>

        {/* Radar Meteorológico */}
        <div className="bg-[#081210]/60 backdrop-blur-xl border border-white/5 rounded-2xl overflow-hidden min-h-[400px] flex flex-col">
          <div className="p-5 border-b border-white/10 flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-teal-500/20 border border-teal-500/30">
              <CloudRain size={18} className="text-teal-400" />
            </div>
            <div>
              <h3 className="text-[11px] font-black uppercase tracking-widest text-white">Radar Meteorológico</h3>
              <p className="text-[9px] text-text-muted font-bold uppercase tracking-widest">Monitoramento Geo-Espacial</p>
            </div>
          </div>
          <iframe
            src={`https://embed.windy.com/embed2.html?lat=${windyLat.toFixed(3)}&lon=${windyLng.toFixed(3)}&detailLat=${windyLat.toFixed(3)}&detailLon=${windyLng.toFixed(3)}&width=650&height=450&zoom=9&level=surface&overlay=rain&product=ecmwf&menu=&message=true&marker=true&calendar=now&pressure=&type=map&location=coordinates&detail=&metricWind=km%2Fh&metricTemp=%C2%B0C&radarRange=-1`}
            className="w-full flex-1 min-h-[320px] opacity-90"
            title="Windy Radar"
            frameBorder={0}
          />
        </div>
      </div>

      {/* Dialog: Nota de Risco */}
      <AnimatePresence>
        {riscoOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={() => setRiscoOpen(false)}>
            <motion.div initial={{ opacity:0,scale:0.95 }} animate={{ opacity:1,scale:1 }} exit={{ opacity:0,scale:0.95 }}
              onClick={e => e.stopPropagation()}
              style={{ background:'#0a0f0e', border:'1px solid rgba(255,255,255,0.08)', borderRadius:16, width:'90%', maxWidth:480 }}
              className="p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-black uppercase text-white">Nota de Risco do Projeto</h3>
                <button onClick={() => setRiscoOpen(false)} className="text-white/30 hover:text-white"><X size={16}/></button>
              </div>
              <div className="text-4xl font-black mb-1" style={{ color: d.risk?.color || TEAL }}>{d.risk?.nota ?? '—'}<span className="text-base text-white/30">/10</span></div>
              <div className="text-xs text-white/50 mb-4 uppercase font-bold">{d.risk?.label || 'Controlado'}</div>
              <div className="space-y-2">
                {(d.risk?.criterios || []).map((c: any, i: number) => (
                  <div key={i} className="flex items-center justify-between bg-white/[0.03] border border-white/5 rounded-xl px-4 py-2">
                    <span className="text-xs text-white/70">{c.nome}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <div style={{ width:`${c.nota*10}%`, background: c.nota >= 7 ? RED : c.nota >= 4 ? COPPER : TEAL }} className="h-full rounded-full" />
                      </div>
                      <span className="text-xs font-mono font-bold" style={{ color: c.nota >= 7 ? RED : COPPER }}>{c.nota}</span>
                    </div>
                  </div>
                ))}
                {!(d.risk?.criterios?.length) && <p className="text-xs text-white/30 text-center py-4">Nenhum critério cadastrado</p>}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Dialog: Alertas IA */}
      <AnimatePresence>
        {alertaOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={() => setAlertaOpen(false)}>
            <motion.div initial={{ opacity:0,scale:0.95 }} animate={{ opacity:1,scale:1 }} exit={{ opacity:0,scale:0.95 }}
              onClick={e => e.stopPropagation()}
              style={{ background:'#0a0f0e', border:'1px solid rgba(255,255,255,0.08)', borderRadius:16, width:'90%', maxWidth:560, maxHeight:'80vh', overflow:'hidden', display:'flex', flexDirection:'column' }}
            >
              <div className="flex items-center justify-between p-5 border-b border-white/5">
                <h3 className="text-sm font-black uppercase text-white">Alertas da IA ({insights.length})</h3>
                <button onClick={() => setAlertaOpen(false)} className="text-white/30 hover:text-white"><X size={16}/></button>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {insights.length > 0 ? insights.map((ins, i) => <InsightCard key={i} insight={ins} idx={i} />) : (
                  <p className="text-xs text-white/30 text-center py-8">Nenhum alerta ativo</p>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}

function DashboardTab({ contrato }: { contrato: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['hub-dashboard', contrato],
    queryFn:  () => api.get(`/hub/dashboard?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    enabled:  !!contrato,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: true,
    placeholderData: keepPreviousData,
  })
  if (isLoading) return <Skeleton />
  const d = data ?? {}
  const k = d.kpis || {}

  const ChartWrapper = ({ title, children, icon: Icon }: any) => (
    <div style={{ background: GLASS, border: BORDER, borderRadius: 24 }} className="p-6 flex flex-col gap-6 group overflow-hidden">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-copper/10 rounded-xl text-copper"><Icon size={16} /></div>
          <h3 className="text-[11px] font-black uppercase tracking-widest text-white/90">{title}</h3>
        </div>
      </div>
      <div className="h-[260px] w-full">{children}</div>
    </div>
  )

  return (
    <div className="flex flex-col gap-8 animate-enter">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { l: 'Progresso Global',  v: `${k.progress_global || 0}%`, icon: Activity,     col: COPPER },
          { l: 'Performance (SPI)', v: (k.spi || 1.0).toFixed(2),    icon: TrendingUp,   col: (k.spi >= 1 ? TEAL : RED) },
          { l: 'Desvio vs. Plan',   v: (() => { const d = k.desvio_pct ?? 0; return `${d > 0 ? '+' : ''}${d}%` })(), icon: TrendingDown, col: (k.desvio_pct ?? 0) > 0 ? TEAL : (k.desvio_pct ?? 0) < 0 ? RED : '#888' },
          { l: 'Deliveries Blue',   v: k.concluidas || 0,             icon: CheckCircle,  col: TEAL },
        ].map(card => (
          <div key={card.l} style={{ background: GLASS, border: BORDER, borderRadius: 20 }} className="p-6 relative overflow-hidden group">
             <div className="text-[9px] text-text-muted font-black uppercase tracking-[0.2em] mb-2">{card.l}</div>
             <div className="text-2xl font-display font-bold" style={{ color: card.col }}>{card.v}</div>
             <div className="absolute right-[-14px] bottom-[-14px] opacity-[0.03] group-hover:opacity-10 group-hover:scale-110 transition-all duration-500"><card.icon size={80} /></div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartWrapper title="Curva S: Planejado vs Realizado" icon={TrendingUp}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={d.scurve} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="gCopper" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={COPPER} stopOpacity={0.1}/><stop offset="95%" stopColor={COPPER} stopOpacity={0}/></linearGradient>
                <linearGradient id="gTeal" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={TEAL} stopOpacity={0.2}/><stop offset="95%" stopColor={TEAL} stopOpacity={0}/></linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="data" tick={{ fill: '#444', fontSize: 10 }} axisLine={false} />
              <YAxis tick={{ fill: '#444', fontSize: 10 }} axisLine={false} tickFormatter={v => `${v}%`} />
              <Tooltip content={<SCurveTip />} />
              <Legend
                wrapperStyle={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.4)', paddingTop: 8 }}
                formatter={(value) => value === 'previsto' ? 'Planejado' : 'Realizado'}
              />
              <Area type="monotone" dataKey="previsto" name="previsto" stroke={COPPER} fill="url(#gCopper)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="realizado" name="realizado" stroke={TEAL} fill="url(#gTeal)" strokeWidth={3} dot={{ r: 3, fill: TEAL }} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartWrapper>

        <ChartWrapper title="Tendência de Performance (SPI)" icon={Activity}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={d.spi_trend} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
              <XAxis dataKey="data" tick={{ fill: '#444', fontSize: 10 }} axisLine={false} />
              <YAxis tick={{ fill: '#444', fontSize: 10 }} axisLine={false} domain={[0.5, 1.5]} tickFormatter={v => v.toFixed(1)} />
              <Tooltip content={<SPITip />} />
              <Legend
                wrapperStyle={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.4)', paddingTop: 8 }}
                formatter={() => 'SPI (Schedule Performance Index)'}
              />
              <ReferenceLine y={1} stroke="#666" strokeDasharray="5 5" label={{ value: '1.0 — Meta', position: 'insideTopRight', fill: '#555', fontSize: 9 }} />
              <Line type="step" dataKey="spi" name="spi" stroke={TEAL} strokeWidth={3} dot={{ r: 3, fill: TEAL }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartWrapper>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <ChartWrapper title="Produtividade Diária" icon={Activity}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={d.produtividade_diaria || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="data" tick={{ fill: '#444', fontSize: 9 }} axisLine={false} />
              <YAxis tick={{ fill: '#444', fontSize: 9 }} axisLine={false} />
              <Tooltip content={<ProdDiariaTip />} />
              <Legend wrapperStyle={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.4)', paddingTop: 8 }} formatter={(v) => v === 'realizado' ? 'Realizado' : 'Meta'} />
              <Bar dataKey="realizado" name="realizado" fill={TEAL} radius={[4,4,0,0]} opacity={0.85} minPointSize={4}>
                <LabelList dataKey="realizado" position="top" style={{ fill: TEAL, fontSize: 9, fontWeight: 700 }} />
              </Bar>
              <Bar dataKey="previsto" name="previsto" fill={COPPER} radius={[4,4,0,0]} opacity={0.45}>
                <LabelList dataKey="previsto" position="top" style={{ fill: COPPER, fontSize: 9, fontWeight: 700 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartWrapper>

        <ChartWrapper title="Progresso por Disciplina" icon={BarChart2}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={d.por_disciplina || []} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" horizontal={false} />
              <XAxis type="number" domain={[0,100]} tick={{ fill: '#444', fontSize: 9 }} axisLine={false} tickFormatter={v => `${v}%`} />
              <YAxis type="category" dataKey="disciplina" tick={{ fill: '#888', fontSize: 9 }} axisLine={false} width={90} />
              <Tooltip content={<DisciplinaTip />} />
              <Bar dataKey="pct" fill={COPPER} radius={[0,4,4,0]} opacity={0.85} minPointSize={4}>
                <LabelList dataKey="pct" position="right" formatter={(v: number) => `${v}%`} style={{ fill: '#aaa', fontSize: 9, fontWeight: 700 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartWrapper>

        <ChartWrapper title="Orçamento Executado" icon={DollarSign}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={d.orcamento_mensal || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="mes" tick={{ fill: '#444', fontSize: 9 }} axisLine={false} />
              <YAxis tick={{ fill: '#444', fontSize: 9 }} axisLine={false} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
              <Tooltip content={<OrcamentoTip />} />
              <Legend wrapperStyle={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.4)', paddingTop: 8 }} formatter={(v) => v === 'previsto' ? 'Previsto' : 'Realizado'} />
              <Bar dataKey="previsto" name="previsto" fill={COPPER} opacity={0.3} radius={[4,4,0,0]} />
              <Bar dataKey="realizado" name="realizado" fill={TEAL} opacity={0.8} radius={[4,4,0,0]}>
                <LabelList dataKey="realizado" position="top" formatter={(v: number) => v > 0 ? `${(v/1000).toFixed(0)}k` : ''} style={{ fill: TEAL, fontSize: 9, fontWeight: 700 }} />
              </Bar>
            </ComposedChart>
          </ResponsiveContainer>
        </ChartWrapper>
      </div>
    </div>
  )
}

// ── Cronograma Helpers ────────────────────────────────────────────────────────

const TENDENCIA_CONFIG: Record<string, { color: string; label: string; dot: string }> = {
  acima:    { color: '#22c55e', label: 'Adiantado', dot: 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]' },
  dentro:   { color: COPPER,   label: 'No Ritmo',  dot: 'bg-copper shadow-[0_0_8px_rgba(201,139,42,0.5)]' },
  abaixo:   { color: RED,      label: 'Abaixo',    dot: 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]' },
  concluida:{ color: TEAL,     label: 'Concluída', dot: 'bg-teal-500 shadow-[0_0_8px_rgba(42,157,143,0.5)]' },
  sem_dados:{ color: '#888',   label: 'Sem dados', dot: 'bg-white/20' },
}

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  concluida:    { color: TEAL,   label: 'Concluída' },
  em_execucao:  { color: COPPER, label: 'Em andamento' },
  em_andamento: { color: COPPER, label: 'Em andamento' },  // alias legado
  atrasada:     { color: RED,    label: 'Atrasada' },
  pendente:     { color: '#888', label: 'Pendente' },
  nao_iniciada: { color: '#888', label: 'Pendente' },
}

function TendenciaDot({ tendencia }: { tendencia: string }) {
  const cfg = TENDENCIA_CONFIG[tendencia] || TENDENCIA_CONFIG.sem_dados
  return <div className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot}`} title={cfg.label} />
}

// KPI cards clicáveis do topo do cronograma
function CronMenuBar({ allRows, kpisData, onCreateMacro, onImportIA, onRecalcular, onKpiClick }: any) {
  const total = allRows.length
  const concluidas = allRows.filter((a: any) => Number(a.conclusao_pct || 0) >= 100).length
  const criticas = allRows.filter((a: any) => String(a.critico).toLowerCase() === 'sim').length
  // Progresso vem do backend (_calc_progress_spi com hist_map) — mesma fonte que Visão Geral e Dashboard
  const progresso = kpisData?.progress_pct ?? 0

  const kpis = [
    { id: 'total',     label: 'Total de Atividades', value: total,              color: '#fff',   icon: List },
    { id: 'concluidas',label: 'Concluídas',           value: concluidas,         color: TEAL,     icon: CheckCircle },
    { id: 'criticas',  label: 'Críticas',             value: criticas,           color: RED,      icon: AlertTriangle },
    { id: 'progresso', label: 'Progresso Geral',      value: `${Number(progresso).toFixed(1)}%`, color: COPPER, icon: Activity },
  ]

  return (
    <div style={{ background: 'rgba(255,255,255,0.02)', border: BORDER, borderRadius: 16 }} className="p-4">
      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        {kpis.map(k => (
          <button
            key={k.id}
            onClick={() => onKpiClick(k.id)}
            style={{ background: 'rgba(13,17,23,0.6)', border: `1px solid rgba(255,255,255,0.05)`, borderRadius: 10, padding: '10px 14px', cursor: 'pointer', textAlign: 'left', transition: 'border-color 0.2s' }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = `${k.color}40`)}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.05)')}
          >
            <div className="flex items-center gap-2 mb-1">
              <k.icon size={11} style={{ color: k.color }} />
              <span className="text-[9px] uppercase font-black tracking-widest" style={{ color: 'rgba(255,255,255,0.3)' }}>{k.label}</span>
            </div>
            <div className="text-xl font-display font-bold" style={{ color: k.color }}>{k.value}</div>
          </button>
        ))}
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={onCreateMacro}
          style={{ background: COPPER, color: '#0d1117', border: 'none', borderRadius: 8, padding: '7px 16px', fontSize: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <Plus size={13} /> Criar Atividade Macro
        </button>
        <button
          onClick={onImportIA}
          style={{ background: `${TEAL}20`, color: TEAL, border: `1px solid ${TEAL}40`, borderRadius: 8, padding: '7px 16px', fontSize: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <Sparkles size={13} /> Importar via IA
        </button>
        <button
          onClick={onRecalcular}
          style={{ background: 'rgba(255,255,255,0.04)', color: '#888', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: '7px 16px', fontSize: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <CalendarCheck size={13} /> Recalcular Datas
        </button>
      </div>
    </div>
  )
}

// Popup de detalhe ao clicar num KPI
function KpiDetailDialog({ type, activities, prefiltered, isOpen, onClose, refDate }: any) {
  if (!isOpen) return null
  const today = refDate || new Date().toISOString().slice(0, 10)

  const filtered = useMemo(() => {
    if (prefiltered) return prefiltered
    if (type === 'total')     return activities
    if (type === 'concluidas') return activities.filter((a: any) => Number(a.conclusao_pct || 0) >= 100)
    if (type === 'criticas')  return activities.filter((a: any) => String(a.critico).toLowerCase() === 'sim')
    if (type === 'atrasadas') return activities.filter((a: any) => {
      const ter = a.termino_previsto?.slice(0, 10)
      return ter && ter < today && Number(a.conclusao_pct || 0) < 100
    })
    if (type === 'risco')     return activities.filter((a: any) => a._tendencia === 'abaixo')
    if (type === 'adiantadas') return activities.filter((a: any) => a._tendencia === 'acima')
    return activities
  }, [prefiltered, activities, type, today])

  const titles: Record<string, string> = {
    total: 'Todas as Atividades', concluidas: 'Atividades Concluídas',
    criticas: 'Atividades Críticas', atrasadas: 'Atividades Atrasadas',
    risco: 'Em Risco (Abaixo do Ritmo)', adiantadas: 'Adiantadas',
    programadas: 'Programadas Hoje', realizadas: 'Realizadas Hoje',
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        onClick={e => e.stopPropagation()}
        style={{ background: '#0a0f0e', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, width: '90%', maxWidth: 640, maxHeight: '80vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
      >
        <div style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }} className="p-5 flex items-center justify-between">
          <h3 className="text-sm font-black uppercase tracking-widest text-white">{titles[type] || type} ({filtered.length})</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer' }}><X size={16} /></button>
        </div>
        <div className="overflow-y-auto flex-1 p-4 space-y-2">
          {filtered.map((a: any) => (
            <div key={a.id} style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 8 }} className="p-3 flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <div className="text-xs font-semibold text-text-primary truncate">{a.atividade}</div>
                <div className="text-[10px] text-text-muted">{a.fase} · {a.responsavel || '—'}</div>
              </div>
              <div className="flex items-center gap-3 shrink-0 ml-3">
                <TendenciaDot tendencia={a._tendencia || 'sem_dados'} />
                <div style={{ color: COPPER, fontWeight: 700, fontSize: 13 }}>{a.conclusao_pct || 0}%</div>
                <div className="text-[10px] text-text-muted font-mono">{a.termino_br || '—'}</div>
              </div>
            </div>
          ))}
          {filtered.length === 0 && <div className="text-center text-text-muted text-xs py-8">Nenhuma atividade nesta categoria</div>}
        </div>
      </motion.div>
    </div>
  )
}

// Linha de atividade (macro, micro, sub) com expansão
function AtivRow({
  row, level, allRows, onEdit, onDelete, onAddChild, onKpiClick, expanded, onToggle,
}: {
  row: any; level: number; allRows: any[]
  onEdit: (r: any) => void
  onDelete: (id: string) => void
  onAddChild: (parent: any) => void
  onKpiClick?: (id: string) => void
  expanded: boolean
  onToggle: () => void
}) {
  const hasChildren = allRows.some(a => a.parent_id === row.id)
  const depRef  = row.dependencia_id ? allRows.find(a => a.id === row.dependencia_id) : null
  const depName = depRef?.atividade?.slice(0, 22) ?? null
  const depTipoLabel = row.dep_tipo === 'depende_inicio' ? 'SS' : row.dep_tipo === 'depende_termino' ? 'FS' : row.dep_tipo === 'depende_progresso' ? 'QS' : null

  const pct = Number(row.conclusao_pct || 0)
  const status = row.status || 'pendente'
  const statusCfg = STATUS_CONFIG[status] || STATUS_CONFIG.pendente
  const tendCfg = TENDENCIA_CONFIG[row._tendencia || 'sem_dados'] || TENDENCIA_CONFIG.sem_dados

  const bgByLevel = level === 0
    ? 'rgba(201,139,42,0.04)'
    : level === 1
    ? 'rgba(42,157,143,0.03)'
    : 'rgba(255,255,255,0.015)'

  const borderByLevel = level === 0
    ? 'rgba(201,139,42,0.15)'
    : level === 1
    ? 'rgba(42,157,143,0.1)'
    : 'rgba(255,255,255,0.04)'

  return (
    <div style={{ marginLeft: level * 20 }}>
      <div
        style={{ background: bgByLevel, border: `1px solid ${borderByLevel}`, borderRadius: 8, marginBottom: 3 }}
        className="flex items-center gap-2 px-3 py-2 group hover:bg-white/5 transition-colors"
      >
        {/* Expand toggle */}
        <button
          onClick={onToggle}
          style={{ background: 'none', border: 'none', cursor: hasChildren ? 'pointer' : 'default', color: hasChildren ? COPPER : 'transparent', width: 16, flexShrink: 0 }}
        >
          {hasChildren ? (expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />) : null}
        </button>

        {/* Fase badge */}
        <div style={{ fontSize: 9, fontWeight: 700, color: row.fase_color || '#888', background: `${row.fase_color || '#888'}15`, borderRadius: 4, padding: '2px 6px', whiteSpace: 'nowrap', flexShrink: 0 }}>
          {row.fase || '—'}
        </div>

        {/* Nome */}
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold text-text-primary truncate flex items-center gap-1">
            {row.atividade}
            {String(row.critico).toLowerCase() === 'sim' && (
              <span style={{ color: RED, fontSize: 9, fontWeight: 800, background: `${RED}15`, borderRadius: 3, padding: '0 4px' }}>CRÍTICO</span>
            )}
            {row.status_atividade === 'Pendente Aprovação' && (
              <span style={{ color: '#F59E0B', fontSize: 9, fontWeight: 800, background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 3, padding: '0 5px' }}>
                ⏳ APROVAÇÃO PENDENTE
              </span>
            )}
          </div>
          {row.status_atividade === 'Pendente Aprovação' && (
            <div style={{ fontSize: 9, color: 'rgba(245,158,11,0.7)' }}>
              Registrada via RDO — preencha macro, fase e datas para incluir no cronograma
            </div>
          )}
          {depName && (
            <div style={{ fontSize: 9, color: '#888' }} className="flex items-center gap-1">
              <MinusCircle size={8} />
              <span>Depende de: <span style={{ color: '#aaa', fontWeight: 700 }}>{depName}</span></span>
              {depTipoLabel && (
                <span style={{ fontSize: 8, fontWeight: 800, color: COPPER, background: `${COPPER}18`, borderRadius: 3, padding: '0 4px', letterSpacing: '0.05em' }}>{depTipoLabel}</span>
              )}
            </div>
          )}
        </div>

        {/* Responsável */}
        <div className="hidden lg:block text-[10px] text-text-muted w-24 truncate shrink-0">{row.responsavel || '—'}</div>

        {/* Datas */}
        <div className="hidden md:block text-[10px] text-text-muted font-mono w-20 text-center shrink-0">{row.inicio_br || '—'}</div>
        <div className="hidden md:block text-[10px] text-text-muted font-mono w-20 text-center shrink-0">{row.termino_br || '—'}</div>

        {/* Progresso */}
        <div style={{ width: 60, flexShrink: 0 }}>
          <div className="flex items-center justify-between mb-0.5">
            <span style={{ fontSize: 10, fontWeight: 700, color: pct >= 100 ? TEAL : COPPER }}>{pct}%</span>
          </div>
          <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 99 }}>
            <div style={{ width: `${pct}%`, height: '100%', background: pct >= 100 ? TEAL : pct >= 50 ? COPPER : RED, borderRadius: 99, transition: 'width 0.3s' }} />
          </div>
        </div>

        {/* Tendência */}
        <div style={{ color: tendCfg.color, fontSize: 9, fontWeight: 700, width: 52, textAlign: 'center', flexShrink: 0 }}>
          <TendenciaDot tendencia={row._tendencia || 'sem_dados'} />
        </div>

        {/* Status */}
        <div style={{ fontSize: 9, fontWeight: 700, color: statusCfg.color, background: `${statusCfg.color}15`, borderRadius: 4, padding: '2px 6px', flexShrink: 0, whiteSpace: 'nowrap' }}>
          {statusCfg.label}
        </div>

        {/* Risk Score */}
        {row._risk_score > 0 && (
          <div title={`Risco: ${row._risk_score}/10${row._velocity > 0 ? ` | Vel: ${row._velocity}/dia` : ''}${row._eac_date ? ` | EAC: ${row._eac_date}` : ''}`}
            style={{
              fontSize: 9, fontWeight: 800, borderRadius: 4, padding: '2px 5px', flexShrink: 0,
              color: row._risk_score >= 7 ? '#EF4444' : row._risk_score >= 4 ? '#C98B2A' : '#22c55e',
              background: row._risk_score >= 7 ? 'rgba(239,68,68,0.12)' : row._risk_score >= 4 ? 'rgba(201,139,42,0.12)' : 'rgba(34,197,94,0.08)',
              border: `1px solid ${row._risk_score >= 7 ? 'rgba(239,68,68,0.3)' : row._risk_score >= 4 ? 'rgba(201,139,42,0.3)' : 'rgba(34,197,94,0.2)'}`,
            }}>
            R{row._risk_score}
          </div>
        )}

        {/* Actions — always visible */}
        <div className="flex items-center gap-1 shrink-0">
          {level < 2 && (
            <button title="Adicionar sub-atividade" onClick={() => onAddChild(row)}
              style={{ background: `${TEAL}20`, border: `1px solid ${TEAL}30`, color: TEAL, borderRadius: 5, padding: '2px 6px', cursor: 'pointer', fontSize: 10 }}>
              <Plus size={10} />
            </button>
          )}
          <button title="Editar" onClick={() => onEdit(row)}
            style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: '#888', borderRadius: 5, padding: '2px 6px', cursor: 'pointer' }}>
            <Pencil size={10} />
          </button>
          <button title="Excluir" onClick={() => onDelete(row.id)}
            style={{ background: `${RED}10`, border: `1px solid ${RED}20`, color: RED, borderRadius: 5, padding: '2px 6px', cursor: 'pointer' }}>
            <Trash2 size={10} />
          </button>
        </div>
      </div>
    </div>
  )
}

// Seção Previsto vs Realizado do Dia
function PrevistoRealizadoSection({ allRows, refDate, onKpiClick }: { allRows: any[]; refDate?: string; onKpiClick: (t: string, rows: any[]) => void }) {
  const today = refDate || new Date().toISOString().slice(0, 10)

  const { programadasHoje, realizadasHoje, atrasadas, emRisco, adiantadas } = useMemo(() => {
    // Apenas micros/subs na listagem do dia (macros são fruto das filhas)
    const folhas = allRows.filter((a: any) => !allRows.some((b: any) => b.parent_id === a.id))
    const prog = folhas.filter((a: any) => {
      const ini = a.inicio_previsto?.slice(0, 10)
      const ter = a.termino_previsto?.slice(0, 10)
      return ini && ter && ini <= today && ter >= today
    })
    // Realizadas HOJE: concluídas cujo last_rdo_date é hoje — evita contar atividades de dias anteriores
    const real = folhas.filter((a: any) => {
      const rdoDate = a.last_rdo_date?.slice(0, 10)
      return rdoDate === today && Number(a.conclusao_pct || 0) >= 100
    })
    // Atrasadas: prazo vencido ANTES de hoje com pct < 100
    const atras = folhas.filter((a: any) => {
      const ter = a.termino_previsto?.slice(0, 10)
      return ter && ter < today && Number(a.conclusao_pct || 0) < 100
    })
    const risco = folhas.filter((a: any) => a._tendencia === 'abaixo')
    const adiant = folhas.filter((a: any) => a._tendencia === 'acima')
    return { programadasHoje: prog, realizadasHoje: real, atrasadas: atras, emRisco: risco, adiantadas: adiant }
  }, [allRows, today])

  // Desvio do dia: diferença entre o que foi realizado e o que era esperado para hoje
  // (atividades programadas para hoje que já concluíram - as que deveriam ter concluído hoje)
  const desvio = realizadasHoje.length - programadasHoje.length

  const cards = [
    { id: 'programadas', label: 'Programadas Hoje', value: programadasHoje.length, color: COPPER, icon: CalendarCheck, rows: programadasHoje },
    { id: 'realizadas',  label: 'Realizadas Hoje',  value: realizadasHoje.length,  color: TEAL,  icon: CheckCircle,  rows: realizadasHoje },
    { id: 'desvio',      label: 'Desvio Hoje',      value: desvio >= 0 ? `+${desvio}` : desvio, color: desvio >= 0 ? TEAL : RED, icon: desvio >= 0 ? TrendingUp : TrendingDown, rows: null },
    { id: 'risco',       label: 'Em Risco',          value: emRisco.length,         color: RED,   icon: AlertTriangle, rows: emRisco },
    { id: 'atrasadas',   label: 'Atrasadas',         value: atrasadas.length,       color: RED,   icon: Clock,       rows: atrasadas },
    { id: 'adiantadas',  label: 'Adiantadas',        value: adiantadas.length,      color: '#22c55e', icon: Gauge,  rows: adiantadas },
  ]

  return (
    <div style={{ background: GLASS, border: BORDER, borderRadius: 16 }} className="p-5">
      <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-white/50 mb-4 flex items-center gap-2">
        <CalendarRange size={12} style={{ color: COPPER }} /> Previsto vs Realizado do Dia
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {cards.map(c => (
          <button
            key={c.id}
            onClick={() => c.rows && onKpiClick(c.id, c.rows)}
            disabled={!c.rows}
            style={{ background: 'rgba(13,17,23,0.5)', border: `1px solid rgba(255,255,255,0.04)`, borderRadius: 10, padding: '10px', cursor: c.rows ? 'pointer' : 'default', textAlign: 'left' }}
            onMouseEnter={e => c.rows && (e.currentTarget.style.borderColor = `${c.color}30`)}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.04)')}
          >
            <c.icon size={12} style={{ color: c.color, marginBottom: 4 }} />
            <div className="text-[9px] uppercase tracking-widest font-bold" style={{ color: 'rgba(255,255,255,0.3)' }}>{c.label}</div>
            <div className="text-xl font-display font-bold mt-1" style={{ color: c.color }}>{c.value}</div>
          </button>
        ))}
      </div>
    </div>
  )
}

// Seção Produtividade & Forecast
function ProdutividadeSection({ allRows, refDate }: { allRows: any[]; refDate?: string }) {
  const [filter, setFilter] = useState<'execucao' | 'concluidas' | 'previstas'>('execucao')
  const today = refDate || new Date().toISOString().slice(0, 10)

  // Apenas folhas (sem filhos) — macros são agrupamentos, não unidades mensuráveis
  const folhas = useMemo(() => allRows.filter(a => !allRows.some(b => b.parent_id === a.id)), [allRows])

  const filtered = useMemo(() => {
    let rows = folhas
    if (filter === 'execucao') {
      rows = folhas.filter((a: any) => {
        const ini = a.inicio_previsto?.slice(0, 10)
        const ter = a.termino_previsto?.slice(0, 10)
        const pct = Number(a.conclusao_pct || 0)
        return ini && ini <= today && pct < 100 && (ter >= today || a.status === 'atrasada')
      })
    } else if (filter === 'concluidas') {
      rows = folhas.filter((a: any) => Number(a.conclusao_pct || 0) >= 100)
    } else {
      rows = folhas.filter((a: any) => {
        const ini = a.inicio_previsto?.slice(0, 10)
        return ini && ini > today
      })
    }
    return rows
  }, [folhas, filter, today])

  const filterBtns = [
    { id: 'execucao',  label: 'Em Execução' },
    { id: 'concluidas', label: 'Concluídas' },
    { id: 'previstas', label: 'Previstas' },
  ] as const

  return (
    <div style={{ background: GLASS, border: BORDER, borderRadius: 16 }} className="overflow-hidden">
      {/* Header */}
      <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }} className="p-5 flex items-center justify-between">
        <div>
          <h3 className="text-xs font-black uppercase tracking-widest text-white">Produtividade & Forecast</h3>
          <p className="text-[9px] text-text-muted uppercase mt-0.5">Ritmo de execução · Projeção EAC · Tendência</p>
        </div>
        <div className="flex bg-black/30 p-1 rounded-lg border border-white/5">
          {filterBtns.map(f => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`px-3 py-1.5 rounded text-[9px] uppercase font-black tracking-widest transition-all ${filter === f.id ? 'bg-copper text-void' : 'text-text-muted hover:text-white'}`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', background: 'rgba(255,255,255,0.01)' }}>
              {['Atividade', 'Dia do Plano', 'Progresso', 'Produtividade', 'Tendência', 'Conclusão EAC'].map(h => (
                <th key={h} className="text-left px-4 py-2.5 text-[9px] uppercase font-black tracking-widest text-white/30">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={6} className="text-center py-8 text-text-muted text-xs">Nenhuma atividade nesta categoria</td></tr>
            )}
            {filtered.map((a: any) => {
              const pct = Number(a.conclusao_pct || 0)
              const ini = a.inicio_previsto?.slice(0, 10)
              const ter = a.termino_previsto?.slice(0, 10)
              // Fallback: calcula dias pelo intervalo de datas quando diasPlan não foi salvo
              const diasPlanDB = Number(a.dias_planejados || 0)
              const diasPlan = diasPlanDB > 0 ? diasPlanDB
                : (ini && ter ? Math.max(1, Math.round((new Date(ter).getTime() - new Date(ini).getTime()) / 86400000) + 1) : 0)
              const daysElapsed = ini ? Math.max(0, Math.ceil((new Date(today).getTime() - new Date(ini).getTime()) / 86400000)) : 0
              const dayText = ini && ter && diasPlan > 0 ? `Dia ${Math.min(daysElapsed + 1, diasPlan)} de ${diasPlan}` : '—'

              const totalQty = Number(a.total_qty || 0)
              const execQty = Number(a.exec_qty || 0)
              const prodPlan = Number(a._prod_plan) || (diasPlan > 0 && totalQty > 0 ? totalQty / diasPlan : 0)
              const prodReal = Number(a._prod_real) || 0
              // Acumulado planejado até hoje: total_qty × % esperado pelo backend (dias úteis)
              const pctEsperado = Number(a._pct_esperado || 0)
              const cumPlan = totalQty > 0 && pctEsperado > 0 ? totalQty * pctEsperado / 100 : 0
              // prodPct: compara acumulado real vs acumulado planejado se tiver qty; senão usa taxa diária
              const prodPct = cumPlan > 0
                ? Math.round(execQty / cumPlan * 100)
                : (prodPlan > 0 && prodReal > 0 ? Math.round(prodReal / prodPlan * 100) : null)

              const tendCfg = TENDENCIA_CONFIG[a._tendencia || 'sem_dados'] || TENDENCIA_CONFIG.sem_dados

              return (
                <tr key={a.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.025)' }} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-4 py-2.5">
                    <div className="font-semibold text-text-primary truncate max-w-[200px]">{a.atividade}</div>
                    <div className="text-[9px] text-text-muted">{a.fase}</div>
                  </td>
                  <td className="px-4 py-2.5 text-[10px] text-text-muted font-mono whitespace-nowrap">{dayText}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <div style={{ width: 60, height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 99 }}>
                        <div style={{ width: `${pct}%`, height: '100%', background: pct >= 100 ? TEAL : COPPER, borderRadius: 99 }} />
                      </div>
                      <span style={{ color: pct >= 100 ? TEAL : COPPER, fontWeight: 700, fontSize: 10 }}>{pct}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    {(a.tipo_medicao === 'marco' || a.unidade === 'marco') ? (
                      <span style={{ color: pct >= 100 ? TEAL : COPPER, fontWeight: 700, fontSize: 10 }}>
                        {pct >= 100 ? '✓ Marco Concluído' : 'Marco — Pendente'}
                      </span>
                    ) : prodPct !== null ? (
                      <div>
                        <span style={{ color: prodPct >= 100 ? TEAL : prodPct >= 70 ? COPPER : RED, fontWeight: 700, fontSize: 10 }}>
                          {prodPct}% do planejado
                        </span>
                        <div className="text-[9px] text-text-muted font-mono mt-0.5">
                          {cumPlan > 0
                            ? `${execQty.toFixed(0)} / ${cumPlan.toFixed(0)} ${a.unidade} acum.`
                            : `${prodReal.toFixed(1)} / ${prodPlan.toFixed(1)} ${a.unidade}/dia`}
                        </div>
                      </div>
                    ) : totalQty > 0 ? (
                      <div>
                        <span className="text-[10px] text-text-muted">Aguard. produção</span>
                        <div className="text-[9px] text-text-muted font-mono mt-0.5">plan: {prodPlan.toFixed(1)} {a.unidade}/dia</div>
                      </div>
                    ) : (
                      <span className="text-[10px] text-text-muted">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-1.5">
                      <TendenciaDot tendencia={a._tendencia || 'sem_dados'} />
                      <span style={{ color: tendCfg.color, fontSize: 9, fontWeight: 700 }}>{tendCfg.label}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-[10px] font-mono" style={{ color: a._data_fim_prevista ? (a._desvio_dias > 0 ? RED : TEAL) : '#888' }}>
                    {a._data_fim_prevista ? _iso_to_br(a._data_fim_prevista) : ter ? _iso_to_br(ter) : '—'}
                    {a._desvio_dias && a._desvio_dias !== 0 ? (
                      <span style={{ color: a._desvio_dias > 0 ? RED : TEAL, fontSize: 9, marginLeft: 4 }}>
                        ({a._desvio_dias > 0 ? '+' : ''}{a._desvio_dias}d)
                      </span>
                    ) : null}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── CronogramaTab Principal ────────────────────────────────────────────────────

function CronogramaTab({ contrato }: { contrato: string }) {
  const qc = useQueryClient()
  const [expandedIds, setExpandedIds]     = useState<Set<string>>(new Set())
  const [filterText, setFilterText]       = useState('')
  const [filterStatus, setFilterStatus]   = useState('todas')
  const [filterFase, setFilterFase]       = useState('')
  const [isModalOpen, setIsModalOpen]     = useState(false)
  const [editingActivity, setEditingActivity] = useState<any>(null)
  const [parentForNew, setParentForNew]   = useState<any>(null)
  const [kpiDialogType, setKpiDialogType] = useState<string | null>(null)
  const [kpiDialogRows, setKpiDialogRows] = useState<any[] | null>(null)
  const [viewMode, setViewMode]           = useState<'lista' | 'gantt'>('lista')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['hub-cronograma', contrato],
    queryFn:  () => api.get(`/hub/cronograma?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    enabled:  !!contrato,
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  })

  const allRows: any[] = data?.atividades || []
  const ganttRows: any[] = data?.gantt || []
  const refDate: string = data?.ref_d || new Date().toISOString().slice(0, 10)

  // Hierarquia: macros (sem parent), micros (parent = macro), subs (parent = micro)
  const macros = useMemo(() => allRows.filter(a => !a.parent_id), [allRows])

  const fases = useMemo(() => {
    const set = new Set(allRows.map((a: any) => a.fase).filter(Boolean))
    return Array.from(set) as string[]
  }, [allRows])

  const filteredMacros = useMemo(() => {
    return macros.filter(a => {
      const txt = filterText.toLowerCase()
      const matchText = !txt || a.atividade?.toLowerCase().includes(txt) || a.responsavel?.toLowerCase().includes(txt)
      const matchStatus = filterStatus === 'todas' || a.status === filterStatus || (filterStatus === 'criticas' && String(a.critico).toLowerCase() === 'sim')
      const matchFase = !filterFase || a.fase === filterFase
      return matchText && matchStatus && matchFase
    })
  }, [macros, filterText, filterStatus, filterFase])

  function toggleExpand(id: string) {
    setExpandedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  async function handleDelete(id: string) {
    if (!confirm('Excluir esta atividade e todas as sub-atividades?')) return
    await api.delete(`/hub/cronograma/${id}`)
    qc.invalidateQueries({ queryKey: ['hub-cronograma', contrato] })
  }

  function openCreateMacro() {
    setParentForNew(null)
    setEditingActivity(null)
    setIsModalOpen(true)
  }

  function openAddChild(parent: any) {
    setParentForNew(parent)
    setEditingActivity(null)
    setIsModalOpen(true)
  }

  async function handleRecalcular() {
    // Endpoint de recalcular datas com base em dependências
    await api.post(`/hub/cronograma/recalcular`, { contrato })
    refetch()
  }

  function renderRows(rows: any[], level: number): React.ReactNode {
    return rows.map(row => {
      const children = allRows.filter(a => a.parent_id === row.id)
      const isExpanded = expandedIds.has(row.id)
      return (
        <div key={row.id}>
          <AtivRow
            row={row}
            level={level}
            allRows={allRows}
            expanded={isExpanded}
            onToggle={() => toggleExpand(row.id)}
            onEdit={r => { setEditingActivity(r); setParentForNew(null); setIsModalOpen(true) }}
            onDelete={handleDelete}
            onAddChild={openAddChild}
            onKpiClick={setKpiDialogType}
          />
          <AnimatePresence>
            {isExpanded && children.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
              >
                {renderRows(children, level + 1)}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )
    })
  }

  if (isLoading) return <Skeleton />

  return (
    <div className="flex flex-col gap-5 animate-enter">

      {/* 1 — Menu Bar: KPIs + botões de ação */}
      <CronMenuBar
        allRows={allRows}
        kpisData={data?.kpis}
        onCreateMacro={openCreateMacro}
        onImportIA={() => alert('Importar via IA — em breve')}
        onRecalcular={handleRecalcular}
        onKpiClick={(t: string) => { setKpiDialogType(t); setKpiDialogRows(null) }}
      />

      {/* 2 — Filtros */}
      <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="p-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[180px]">
          <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
          <input
            placeholder="Filtrar atividades..."
            value={filterText}
            onChange={e => setFilterText(e.target.value)}
            style={{ background: 'rgba(13,17,23,0.6)', border: '1px solid rgba(255,255,255,0.07)', color: '#e2c87a', borderRadius: 8, padding: '7px 10px 7px 28px', fontSize: 12, width: '100%', outline: 'none' }}
          />
        </div>

        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          style={{ background: 'rgba(13,17,23,0.6)', border: '1px solid rgba(255,255,255,0.07)', color: '#e2c87a', borderRadius: 8, padding: '7px 10px', fontSize: 12, outline: 'none' }}
        >
          {[['todas','Todos os Status'],['em_execucao','Em Andamento'],['concluida','Concluída'],['atrasada','Atrasada'],['nao_iniciada','Pendente'],['criticas','Críticas']].map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>

        <select
          value={filterFase}
          onChange={e => setFilterFase(e.target.value)}
          style={{ background: 'rgba(13,17,23,0.6)', border: '1px solid rgba(255,255,255,0.07)', color: '#e2c87a', borderRadius: 8, padding: '7px 10px', fontSize: 12, outline: 'none' }}
        >
          <option value="">Todas as fases</option>
          {fases.map(f => <option key={f} value={f}>{f}</option>)}
        </select>

        {/* View toggle */}
        <div className="flex bg-black/30 p-0.5 rounded-lg border border-white/5 ml-auto">
          <button onClick={() => setViewMode('lista')}
            className={`px-3 py-1.5 rounded text-[9px] uppercase font-black tracking-widest transition-all ${viewMode === 'lista' ? 'bg-copper text-void' : 'text-text-muted hover:text-white'}`}>
            Lista
          </button>
          <button onClick={() => setViewMode('gantt')}
            className={`px-3 py-1.5 rounded text-[9px] uppercase font-black tracking-widest transition-all ${viewMode === 'gantt' ? 'bg-copper text-void' : 'text-text-muted hover:text-white'}`}>
            Gantt
          </button>
        </div>
      </div>

      {/* 3 — Atividades hierárquicas */}
      {viewMode === 'lista' && (
        <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="overflow-hidden">
          {/* Cabeçalho da tabela */}
          <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(255,255,255,0.01)' }}
            className="flex items-center gap-2 px-3 py-2">
            <div style={{ width: 16 }} />
            <div className="w-16 text-[9px] uppercase font-black text-white/30">Fase</div>
            <div className="flex-1 text-[9px] uppercase font-black text-white/30">Atividade</div>
            <div className="hidden lg:block w-24 text-[9px] uppercase font-black text-white/30">Responsável</div>
            <div className="hidden md:block w-20 text-center text-[9px] uppercase font-black text-white/30">Início</div>
            <div className="hidden md:block w-20 text-center text-[9px] uppercase font-black text-white/30">Término</div>
            <div className="w-16 text-[9px] uppercase font-black text-white/30">Progresso</div>
            <div className="w-8 text-[9px] uppercase font-black text-white/30">Tend.</div>
            <div className="w-20 text-[9px] uppercase font-black text-white/30">Status</div>
            <div className="w-20 text-[9px] uppercase font-black text-white/30 text-right">Ações</div>
          </div>

          <div className="p-2">
            {filteredMacros.length === 0 && (
              <div className="text-center py-8 text-text-muted text-xs">
                {allRows.length === 0
                  ? 'Nenhuma atividade cadastrada. Clique em "Criar Atividade Macro" para começar.'
                  : 'Nenhuma atividade corresponde ao filtro.'}
              </div>
            )}
            {renderRows(filteredMacros, 0)}
          </div>
        </div>
      )}

      {/* Gantt */}
      {viewMode === 'gantt' && (
        <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="overflow-hidden">
          <div className="p-4 border-b border-white/5">
            <h3 className="text-xs font-black uppercase tracking-widest text-white flex items-center gap-2">
              <GanttChartIcon size={14} style={{ color: COPPER }} /> Diagrama de Gantt
            </h3>
          </div>
          <div className="p-2">
            <GanttChart referenceDate={refDate} data={ganttRows.map((r: any) => ({
              label:        r.label,
              start_iso:    r.start_iso,
              end_iso:      r.end_iso,
              forecast_end: r.forecast_end ?? undefined,
              pct:          r.pct,
              critico:      r.critico,
              nivel:        (r.nivel || 'macro') as 'macro' | 'micro' | 'sub',
              color:        r.color,
              responsavel:  r.responsavel,
              fase:         r.fase,
            }))} />
          </div>
        </div>
      )}

      {/* 4 — Previsto vs Realizado do Dia */}
      <PrevistoRealizadoSection allRows={allRows} refDate={refDate} onKpiClick={(t, rows) => { setKpiDialogType(t); setKpiDialogRows(rows) }} />

      {/* 5 — Produtividade & Forecast */}
      <ProdutividadeSection allRows={allRows} refDate={refDate} />

      {/* Legenda */}
      <div className="flex flex-wrap items-center gap-4 px-4 py-3 bg-white/[0.02] border border-white/5 rounded-2xl">
        <span className="text-[9px] font-black text-white/30 uppercase tracking-[0.2em]">Tendência:</span>
        {Object.entries(TENDENCIA_CONFIG).filter(([k]) => k !== 'sem_dados').map(([k, v]) => (
          <div key={k} className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full ${v.dot}`} />
            <span className="text-[9px] text-white/60 font-bold uppercase">{v.label}</span>
          </div>
        ))}
      </div>

      {/* Modal de atividade */}
      <ActivityModal
        isOpen={isModalOpen}
        onClose={() => { setIsModalOpen(false); setEditingActivity(null); setParentForNew(null) }}
        contrato={contrato}
        editingActivity={editingActivity}
        parentActivity={parentForNew}
      />

      {/* KPI Dialog */}
      <AnimatePresence>
        {kpiDialogType && (
          <KpiDetailDialog
            type={kpiDialogType}
            activities={allRows}
            prefiltered={kpiDialogRows}
            isOpen={!!kpiDialogType}
            onClose={() => { setKpiDialogType(null); setKpiDialogRows(null) }}
            refDate={refDate}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function AuditoriaTab({ contrato }: { contrato: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['hub-auditoria', contrato],
    queryFn:  () => api.get(`/hub/auditoria?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    enabled:  !!contrato,
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  })
  const [lightbox, setLightbox] = useState<any>(null)

  if (isLoading) return <Skeleton />
  const cats = data?.por_categoria ?? {}
  const items = data?.categories || []

  // Flat list for prev/next navigation
  const allImgs: any[] = Object.values(cats).flat()
  const lbIdx = lightbox ? allImgs.findIndex((i: any) => i.id === lightbox.id) : -1
  const lbPrev = lbIdx > 0 ? allImgs[lbIdx - 1] : null
  const lbNext = lbIdx < allImgs.length - 1 ? allImgs[lbIdx + 1] : null

  return (
    <div className="flex flex-col gap-8 animate-enter">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="p-2 bg-patina/10 rounded-lg"><ScanEye size={18} className="text-patina" /></div>
          <div>
            <h3 className="text-sm font-black uppercase tracking-widest text-white">Auditoria Fotográfica</h3>
            <p className="text-[9px] text-text-muted uppercase font-bold tracking-tighter italic">Bolsões de evidências por categoria operacional</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {items.map((c: any) => (
            <div key={c.slug} className="px-3 py-1 rounded-full border border-white/5 bg-void/40 flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: c.color }} />
              <span className="text-[9px] text-white/40 uppercase font-black">{c.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-12">
        {Object.entries(cats).map(([catSlug, imgs]: [string, any]) => {
          const category = items.find((c: any) => c.slug === catSlug)
          if (!imgs.length) return null
          return (
            <div key={catSlug} className="flex flex-col gap-4">
              <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-white/60 flex items-center gap-3">
                <span className="w-8 h-[1px] bg-white/10" />
                {category?.label || catSlug}
                <span className="text-white/20 font-mono">({imgs.length})</span>
                <span className="flex-1 h-[1px] bg-white/10" />
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {imgs.map((img: any) => (
                  <div key={img.id} onClick={() => setLightbox(img)}
                    className="aspect-square rounded-2xl overflow-hidden border border-white/5 bg-void group cursor-pointer relative shadow-lg hover:border-patina/40 transition-all">
                    <img src={img.url} className="w-full h-full object-cover grayscale group-hover:grayscale-0 group-hover:scale-105 transition-all duration-500" alt={img.legenda} />
                    <div className="absolute inset-0 bg-gradient-to-t from-void to-transparent opacity-0 group-hover:opacity-100 transition-opacity p-4 flex flex-col justify-end">
                      <p className="text-[9px] text-white font-bold leading-tight">{img.legenda}</p>
                      <span className="text-[8px] text-white/40 font-mono mt-1">{_iso_to_br(img.data_captura)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* Lightbox */}
      <AnimatePresence>
        {lightbox && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[300] flex flex-col items-center justify-center bg-black/95"
            onClick={() => setLightbox(null)}>
            {/* Header */}
            <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-6 py-4 bg-gradient-to-b from-black/80 to-transparent z-10" onClick={e => e.stopPropagation()}>
              <div>
                <p className="text-sm font-bold text-white">{lightbox.legenda || 'Foto'}</p>
                <p className="text-[10px] text-white/40 font-mono">{_iso_to_br(lightbox.data_captura)}</p>
              </div>
              <div className="flex items-center gap-3">
                <a href={lightbox.url} download target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
                  style={{ background: COPPER, color: '#000', border: 'none', borderRadius: 8, padding: '8px 16px', fontSize: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}>
                  <Download size={14} /> Download
                </a>
                <button onClick={() => setLightbox(null)} style={{ background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: 8, padding: 8, cursor: 'pointer', color: '#fff', display: 'flex' }}>
                  <X size={20} />
                </button>
              </div>
            </div>

            {/* Image */}
            <motion.img key={lightbox.id} initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
              src={lightbox.url} alt={lightbox.legenda}
              className="max-h-[85vh] max-w-[90vw] object-contain rounded-2xl shadow-2xl"
              onClick={e => e.stopPropagation()} />

            {/* Prev/Next */}
            {lbPrev && (
              <button onClick={e => { e.stopPropagation(); setLightbox(lbPrev) }}
                style={{ position: 'absolute', left: 20, top: '50%', transform: 'translateY(-50%)', background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '50%', width: 44, height: 44, cursor: 'pointer', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                ‹
              </button>
            )}
            {lbNext && (
              <button onClick={e => { e.stopPropagation(); setLightbox(lbNext) }}
                style={{ position: 'absolute', right: 20, top: '50%', transform: 'translateY(-50%)', background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '50%', width: 44, height: 44, cursor: 'pointer', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                ›
              </button>
            )}
            {/* Counter */}
            <div style={{ position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)', background: 'rgba(0,0,0,0.6)', borderRadius: 20, padding: '4px 12px', fontSize: 11, color: 'rgba(255,255,255,0.5)', fontFamily: 'monospace' }}>
              {lbIdx + 1} / {allImgs.length}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

const TIMELINE_TYPES = [
  { id: 'Atualização',  label: 'Atualização de Cronograma', icon: CalendarCheck, color: COPPER,    bg: `${COPPER}15`,      auto: false },
  { id: 'Reunião',      label: 'Reunião',                   icon: User,          color: '#60a5fa', bg: 'rgba(96,165,250,0.12)', auto: false },
  { id: 'Falha',        label: 'Falha / Interrupção',       icon: AlertOctagon,  color: '#ef4444', bg: 'rgba(239,68,68,0.12)', auto: false },
  { id: 'Decisão',      label: 'Decisão',                   icon: Zap,           color: TEAL,      bg: `${TEAL}15`,        auto: false },
  { id: 'Custo',        label: 'Evento de Custo',           icon: Banknote,      color: '#a78bfa', bg: 'rgba(167,139,250,0.12)', auto: false },
  { id: 'Documento',    label: 'Documento / Contrato',      icon: FileText,      color: '#34d399', bg: 'rgba(52,211,153,0.12)', auto: false },
  { id: 'Marco',        label: 'Marco do Projeto',          icon: Gauge,         color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', auto: false },
] as const

function TimelineTab({ contrato }: { contrato: string }) {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['hub-timeline', contrato],
    queryFn:  () => api.get(`/hub/timeline?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    enabled:  !!contrato,
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  })

  const [tipo, setTipo]     = useState('Reunião')
  const [titulo, setTitulo] = useState('')
  const [descricao, setDesc] = useState('')
  const [mencoes, setMencoes] = useState('')
  const [anexo, setAnexo]   = useState<File | null>(null)
  const [filterTipo, setFilterTipo] = useState('')

  const { data: usersData } = useQuery({
    queryKey: ['hub-users'],
    queryFn: () => api.get('/usuarios').then(r => r.data),
    staleTime: Infinity,
  })
  const userList: any[] = usersData?.users ?? []

  // @mention autocomplete
  const [mentionSearch, setMentionSearch] = useState('')
  const [showMention, setShowMention] = useState(false)
  const mentionSuggestions = userList.filter(u =>
    mentionSearch && u.login?.toLowerCase().includes(mentionSearch.toLowerCase())
  ).slice(0, 5)

  function handleDescChange(v: string) {
    setDesc(v)
    const atMatch = v.match(/@(\w*)$/)
    if (atMatch) { setMentionSearch(atMatch[1]); setShowMention(true) }
    else { setShowMention(false); setMentionSearch('') }
  }

  function insertMention(login: string) {
    const newDesc = descricao.replace(/@\w*$/, `@${login} `)
    setDesc(newDesc)
    const cur = mencoes ? `${mencoes},${login}` : login
    setMencoes(cur)
    setShowMention(false)
  }

  const createMut = useMutation({
    mutationFn: async () => {
      let anexo_url = ''
      let anexo_nome = ''
      if (anexo) {
        const fd = new FormData()
        fd.append('file', anexo)
        const r = await api.post('/hub/timeline/upload', fd, { headers: { 'Content-Type': undefined } })
        anexo_url  = r.data.url  ?? ''
        anexo_nome = r.data.nome ?? anexo.name
      }
      await api.post('/hub/timeline', {
        contrato, tipo, titulo, descricao,
        mencoes: mencoes ? mencoes.split(',').map(s => s.trim()).filter(Boolean) : [],
        anexo_url, anexo_nome,
        is_document: tipo === 'Documento',
        is_cost:     tipo === 'Custo',
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['hub-timeline', contrato] })
      setTitulo(''); setDesc(''); setMencoes(''); setAnexo(null)
    },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/hub/timeline/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hub-timeline', contrato] }),
  })

  if (isLoading) return <Skeleton />
  const events: any[] = (data?.eventos || []).filter((e: any) => !filterTipo || e.tipo === filterTipo)

  const tipoConfig = (t: string) => TIMELINE_TYPES.find(x => x.id === t) ?? TIMELINE_TYPES[0]

  return (
    <div className="flex flex-col gap-6 animate-enter">
      <div className="flex items-center gap-4">
        <div className="p-2 bg-blue-500/10 rounded-lg"><GitBranch size={18} className="text-blue-400" /></div>
        <div>
          <h3 className="text-sm font-black uppercase tracking-widest text-white">Linha do Tempo</h3>
          <p className="text-[9px] text-text-muted uppercase font-bold tracking-tighter italic">Registro histórico de eventos, decisões e interrupções</p>
        </div>
        {/* Filter chips */}
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          <button onClick={() => setFilterTipo('')}
            style={{ fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 6, border: `1px solid ${!filterTipo ? COPPER : 'rgba(255,255,255,0.1)'}`, background: !filterTipo ? `${COPPER}20` : 'transparent', color: !filterTipo ? COPPER : '#666', cursor: 'pointer' }}>
            Todos
          </button>
          {TIMELINE_TYPES.map(t => (
            <button key={t.id} onClick={() => setFilterTipo(filterTipo === t.id ? '' : t.id)}
              style={{ fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 6, border: `1px solid ${filterTipo === t.id ? t.color : 'rgba(255,255,255,0.1)'}`, background: filterTipo === t.id ? t.bg : 'transparent', color: filterTipo === t.id ? t.color : '#666', cursor: 'pointer' }}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6">
        {/* ── Left: Entry Form ─────────────────────────────── */}
        <div style={{ background: GLASS, border: BORDER, borderRadius: 16 }} className="p-5 flex flex-col gap-4 self-start">
          <h4 style={{ fontSize: 11, fontWeight: 700, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Novo Registro</h4>

          {/* Type selector */}
          <div className="grid grid-cols-2 gap-2">
            {TIMELINE_TYPES.map(t => {
              const IconC = t.icon
              const active = tipo === t.id
              return (
                <button key={t.id} onClick={() => setTipo(t.id)}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, border: `1px solid ${active ? t.color : 'rgba(255,255,255,0.06)'}`, background: active ? t.bg : 'transparent', cursor: 'pointer', transition: 'all 0.15s' }}>
                  <IconC size={12} style={{ color: active ? t.color : '#555', flexShrink: 0 }} />
                  <span style={{ fontSize: 10, fontWeight: 700, color: active ? t.color : '#666', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{t.label}</span>
                </button>
              )
            })}
          </div>

          {/* Título */}
          <input value={titulo} onChange={e => setTitulo(e.target.value)} placeholder="Título do evento..."
            style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: '9px 12px', fontSize: 13, color: '#fff', outline: 'none', width: '100%', boxSizing: 'border-box' }} />

          {/* Descrição with @mention */}
          <div className="relative">
            <textarea value={descricao} onChange={e => handleDescChange(e.target.value)} placeholder="Descreva o evento... Use @nome para mencionar usuários"
              rows={3}
              style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: '9px 12px', fontSize: 12, color: '#fff', outline: 'none', width: '100%', resize: 'none', boxSizing: 'border-box' }} />
            {showMention && mentionSuggestions.length > 0 && (
              <div style={{ position: 'absolute', bottom: '100%', left: 0, right: 0, background: '#0d1117', border: '1px solid rgba(201,139,42,0.3)', borderRadius: 8, zIndex: 10, overflow: 'hidden' }}>
                {mentionSuggestions.map((u: any) => (
                  <button key={u.login} onClick={() => insertMention(u.login)}
                    style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', background: 'none', border: 'none', color: '#ccc', fontSize: 12, cursor: 'pointer' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.05)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
                    @{u.login}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Anexo */}
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, border: '1px dashed rgba(255,255,255,0.1)', cursor: 'pointer', fontSize: 11, color: '#666' }}>
            <Paperclip size={13} style={{ color: '#555' }} />
            {anexo ? <span style={{ color: TEAL }}>{anexo.name}</span> : 'Anexar documento ou imagem'}
            <input type="file" style={{ display: 'none' }} onChange={e => setAnexo(e.target.files?.[0] ?? null)} />
          </label>

          {/* Menções ativas */}
          {mencoes && (
            <div style={{ fontSize: 10, color: '#555' }}>
              Mencionando: <span style={{ color: COPPER }}>{mencoes}</span>
              <button onClick={() => setMencoes('')} style={{ background: 'none', border: 'none', color: '#444', cursor: 'pointer', marginLeft: 4 }}>×</button>
            </div>
          )}

          {createMut.isError && (
            <div style={{ fontSize: 11, color: '#ef4444', padding: '6px 10px', background: 'rgba(239,68,68,0.1)', borderRadius: 6 }}>
              Erro ao salvar entrada
            </div>
          )}

          <button
            onClick={() => { if (titulo.trim()) createMut.mutate() }}
            disabled={!titulo.trim() || createMut.isPending}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, background: titulo.trim() ? COPPER : 'rgba(255,255,255,0.05)', color: titulo.trim() ? '#000' : '#555', border: 'none', borderRadius: 8, padding: '10px', fontSize: 12, fontWeight: 700, cursor: titulo.trim() ? 'pointer' : 'not-allowed', transition: 'all 0.15s' }}>
            {createMut.isPending ? <span className="animate-spin">⟳</span> : <><Send size={13} /> Registrar na Linha do Tempo</>}
          </button>
        </div>

        {/* ── Right: Timeline feed ─────────────────────────── */}
        <div>
          {events.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 opacity-30">
              <GitBranch size={40} className="text-white/20 mb-3" />
              <p className="text-sm font-bold text-text-muted uppercase tracking-widest">Nenhum evento registrado</p>
            </div>
          )}
          <div className="relative pl-8 space-y-6">
            {events.length > 0 && <div className="absolute left-3 top-0 bottom-0 w-[1px] bg-white/10" />}
            {events.map((e: any) => {
              const tc = tipoConfig(e.tipo)
              const IconC = tc.icon
              return (
                <div key={e.id} className="relative group">
                  <div className="absolute -left-8 top-2 w-6 h-6 rounded-full flex items-center justify-center z-10"
                    style={{ background: tc.bg, border: `1px solid ${tc.color}40` }}>
                    <IconC size={11} style={{ color: tc.color }} />
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 16 }}
                    className="p-5 hover:bg-white/[0.03] transition-all">
                    <div className="flex items-center justify-between mb-2">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 5, background: tc.bg, border: `1px solid ${tc.color}30`, color: tc.color, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{e.tipo}</span>
                        {(e.mencoes ?? []).length > 0 && (
                          <span style={{ fontSize: 9, color: '#555', display: 'flex', alignItems: 'center', gap: 3 }}>
                            <Bell size={10} style={{ color: COPPER }} />
                            {(e.mencoes as string[]).map(m => `@${m}`).join(' ')}
                          </span>
                        )}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', fontFamily: 'monospace' }}>{e.created_at_br}</span>
                        <button onClick={() => deleteMut.mutate(e.id)}
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#333', display: 'flex', padding: 4 }}
                          onMouseEnter={ev => (ev.currentTarget.style.color = '#ef4444')}
                          onMouseLeave={ev => (ev.currentTarget.style.color = '#333')}>
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>
                    <h4 style={{ fontSize: 14, fontWeight: 700, color: '#fff', marginBottom: 4 }}>{e.titulo}</h4>
                    <p style={{ fontSize: 12, color: '#666', lineHeight: 1.6, marginBottom: e.anexo_url ? 10 : 0 }}>{e.descricao}</p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }} className="mt-3">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        <User size={11} style={{ color: '#444' }} />
                        <span style={{ fontSize: 10, color: '#555', fontWeight: 700, textTransform: 'uppercase' }}>{e.autor}</span>
                      </div>
                      {e.anexo_url && (
                        <a href={e.anexo_url} target="_blank" rel="noreferrer" download
                          style={{ display: 'flex', alignItems: 'center', gap: 5, color: TEAL, fontSize: 10, fontWeight: 700, textDecoration: 'none' }}>
                          <Download size={11} /> {e.anexo_nome || 'Ver Anexo'}
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Financial CRUD helpers (used only inside FinanceiroTab) ───────────────────

function fmtBRL(v: any) {
  const n = typeof v === 'number' ? v : parseFloat(String(v || '0').replace(/[^\d.,-]/g, '').replace(',', '.'))
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(isNaN(n) ? 0 : n)
}

function BrlInput({ value, onChange, placeholder, className }: {
  value: number; onChange: (v: number) => void; placeholder?: string; className?: string
}) {
  const fmt = (n: number) => n > 0 ? n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : ''
  const [display, setDisplay] = useState(() => fmt(value))
  const [focused, setFocused] = useState(false)
  useEffect(() => { if (!focused) setDisplay(fmt(value)) }, [value, focused])
  return (
    <input
      value={display}
      onChange={e => setDisplay(e.target.value.replace(/[^\d,.]/g, ''))}
      onFocus={e => { setFocused(true); e.target.select() }}
      onBlur={() => {
        setFocused(false)
        const raw = display.replace(/\./g, '').replace(',', '.')
        const n = parseFloat(raw) || 0
        onChange(n)
        setDisplay(n > 0 ? fmt(n) : '')
      }}
      placeholder={placeholder ?? '0,00'}
      className={className}
      inputMode="decimal"
    />
  )
}

const EVM_DESC: Record<string, { full: string; formula: string; good: string }> = {
  CPI:  { full: 'Cost Performance Index', formula: 'CPI = EV ÷ AC', good: '≥ 1.0 = gastando menos do que o valor entregue' },
  SPI:  { full: 'Schedule Performance Index', formula: 'SPI = EV ÷ PV', good: '≥ 1.0 = avanço físico à frente do planejado' },
  EAC:  { full: 'Estimate at Completion', formula: 'EAC = BAC ÷ CPI', good: 'Projeção do custo total ao fim da obra' },
  VAC:  { full: 'Variance at Completion', formula: 'VAC = BAC − EAC', good: 'Positivo = economia. Negativo = estouro projetado' },
  TCPI: { full: 'To-Complete Performance Index', formula: 'TCPI = (BAC−EV)÷(BAC−AC)', good: '≤ 1.0 = meta alcançável' },
  BAC:  { full: 'Budget at Completion', formula: 'Soma de todos os valores previstos', good: 'Referência máxima de orçamento aprovado' },
  PV:   { full: 'Planned Value', formula: 'Soma do orçamento planejado até hoje', good: 'Baseline do quanto deveria ter sido gasto' },
  EV:   { full: 'Earned Value', formula: 'EV = BAC × % Avanço Físico', good: 'Quanto do orçamento foi "ganho" pelo avanço real' },
  AC:   { full: 'Actual Cost', formula: 'Soma de todos os lançamentos', good: 'Total desembolsado até o momento' },
  CV:   { full: 'Cost Variance', formula: 'CV = EV − AC', good: 'Positivo = sob controle. Negativo = gastando mais' },
}

function FinStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    previsto: 'bg-white/5 text-white/40 border-white/10',
    em_andamento: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    parcial: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    concluido: 'bg-teal-500/10 text-teal-400 border-teal-500/20',
    executado: 'bg-teal-500/10 text-teal-400 border-teal-500/20',
    cancelado: 'bg-red-500/10 text-red-400 border-red-500/20',
  }
  return (
    <span className={`px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-wider border ${map[status] ?? 'bg-white/5 text-white/40'}`}>
      {status.replace('_', ' ')}
    </span>
  )
}

function FinEVMTooltip({ metric }: { metric: string }) {
  const [open, setOpen] = useState(false)
  const desc = EVM_DESC[metric]
  if (!desc) return null
  return (
    <div className="relative inline-block">
      <button onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)} className="p-0.5 rounded text-white/20 hover:text-white/60">
        <Info size={11} />
      </button>
      {open && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 bg-[#0d1117] border border-white/10 rounded-xl p-3 shadow-2xl pointer-events-none">
          <div className="text-[9px] font-black text-copper uppercase tracking-widest mb-1">{metric}</div>
          <div className="text-[9px] text-white/70 mb-2">{desc.full}</div>
          <div className="font-mono text-[9px] text-teal-400 bg-teal-500/5 border border-teal-500/20 rounded px-2 py-1 mb-1">{desc.formula}</div>
          <div className="text-[9px] text-white/40">{desc.good}</div>
        </div>
      )}
    </div>
  )
}

function FinEVMCard({ metric, fmt, good }: { metric: string; fmt: string; good: boolean }) {
  return (
    <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        <span className="text-[9px] font-black uppercase tracking-widest text-white/40">{metric}</span>
        <FinEVMTooltip metric={metric} />
      </div>
      <div className="text-lg font-black font-mono" style={{ color: good ? TEAL : RED }}>{fmt}</div>
      <div className="text-[9px]" style={{ color: good ? TEAL : RED }}>{good ? 'OK' : 'Atenção'}</div>
    </div>
  )
}

function FinSCurveTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-[#0d1117] border border-white/10 rounded-xl p-3 text-[10px] shadow-xl">
      <div className="font-mono text-white/40 mb-2">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4">
          <span className="text-white/60">{p.name}</span>
          <span className="font-mono font-black" style={{ color: p.color }}>{fmtBRL(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

function FinModalNovoCusto({ contrato, cats, atividades, onClose, onSaved, qc }: {
  contrato: string; cats: any[]; atividades: any[]; onClose: () => void; onSaved: () => void; qc: any
}) {
  const [form, setForm] = useState<Record<string, any>>({ status: 'previsto' })
  const f = (k: string, v: any) => setForm(p => ({ ...p, [k]: v }))
  const mut = useMutation({
    mutationFn: (b: any) => api.post(`/financeiro/${contrato}`, b).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['fin', contrato] }); onSaved(); onClose() },
  })
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-2xl bg-[#0d1117] border border-white/10 rounded-2xl shadow-2xl">
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-copper/10 border border-copper/20"><DollarSign size={16} className="text-copper" /></div>
            <span className="text-sm font-black uppercase tracking-widest text-white">Novo Item de Custo</span>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 text-white/40 hover:text-white"><X size={16} /></button>
        </div>
        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Categoria *</label>
            <select className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-copper outline-none"
              onChange={e => { f('categoria_id', e.target.value); f('categoria_nome', cats.find(c => c.id === e.target.value)?.nome ?? '') }}>
              <option value="">Selecionar...</option>
              {cats.map((c: any) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Empresa / Fornecedor</label>
            <input className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white outline-none" placeholder="Nome do fornecedor" onChange={e => f('empresa', e.target.value)} />
          </div>
          <div className="md:col-span-2 space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Descrição *</label>
            <input className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white outline-none" placeholder="Descreva o item de custo" onChange={e => f('descricao', e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Valor Previsto (R$) *</label>
            <BrlInput value={form.valor_previsto ?? 0} onChange={v => f('valor_previsto', v)} className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-copper font-mono outline-none" />
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Data de Referência</label>
            <input type="date" className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white outline-none" onChange={e => f('data_custo', e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Atividade Vinculada</label>
            <select className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white/60 outline-none" onChange={e => f('atividade_id', e.target.value)}>
              <option value="">Nenhuma</option>
              {atividades.map((a: any) => <option key={a.id} value={a.id}>{a.atividade ?? a.nome ?? a.id}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Status</label>
            <select defaultValue="previsto" className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white/60 outline-none" onChange={e => f('status', e.target.value)}>
              {['previsto', 'em_andamento', 'parcial', 'concluido', 'cancelado'].map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
            </select>
          </div>
          <div className="md:col-span-2 space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Observações</label>
            <textarea rows={2} className="w-full bg-void border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white/60 outline-none resize-none" placeholder="Notas opcionais" onChange={e => f('observacoes', e.target.value)} />
          </div>
        </div>
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/5">
          {(!form.categoria_id || !form.descricao || !form.valor_previsto) && (
            <span className="text-[9px] text-white/30 mr-auto">
              {!form.categoria_id ? 'Selecione uma categoria' : !form.descricao ? 'Informe uma descrição' : 'Informe o valor previsto'}
            </span>
          )}
          <Button onClick={onClose} variant="outline" className="border-white/10 text-white/40 text-xs h-9">Cancelar</Button>
          <Button onClick={() => mut.mutate({ ...form })} disabled={mut.isPending || !form.categoria_id || !form.descricao || !form.valor_previsto}
            className="bg-copper text-void font-black text-xs h-9 px-6 hover:bg-copper/90 disabled:opacity-40">
            {mut.isPending ? 'Salvando...' : 'Criar Item'}
          </Button>
        </div>
      </div>
    </div>
  )
}

function FinModalAvanco({ custo, contrato, onClose, qc }: { custo: any; contrato: string; onClose: () => void; qc: any }) {
  const [valor, setValor]           = useState(0)
  const [data, setData]             = useState(new Date().toISOString().slice(0, 10))
  const [obs, setObs]               = useState('')
  const [savedMsg, setSavedMsg]     = useState(false)
  const [pendingDelLanc, setPendingDelLanc] = useState<string | null>(null)
  const { data: lancData } = useQuery({
    queryKey: ['fin-lanc', custo.id],
    queryFn: () => api.get(`/financeiro/${contrato}/lancamentos/${custo.id}`).then(r => r.data),
    staleTime: 30_000,
  })
  const lancamentos: any[] = lancData?.lancamentos ?? []
  const delLanc = useMutation({
    mutationFn: (id: string) => api.delete(`/financeiro/lancamentos/${id}`).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fin-lanc', custo.id] })
      qc.invalidateQueries({ queryKey: ['fin', contrato] })
      setPendingDelLanc(null)
    },
  })
  const mut = useMutation({
    mutationFn: (b: any) => api.post(`/financeiro/${contrato}/lancamentos/${custo.id}`, b).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fin-lanc', custo.id] })
      qc.invalidateQueries({ queryKey: ['fin', contrato] })
      setValor(0); setObs('')
      setSavedMsg(true); setTimeout(() => setSavedMsg(false), 2500)
    },
  })
  const saldo  = custo.valor_previsto - custo.valor_executado
  const overrun = valor > 0 && valor > saldo && saldo > 0
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-[#0d1117] border border-white/10 rounded-2xl shadow-2xl">
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/5">
          <div>
            <div className="flex items-center gap-2 mb-0.5"><Zap size={14} className="text-teal-400" /><span className="text-sm font-black uppercase tracking-widest text-white">Registrar Pagamento</span></div>
            <p className="text-[10px] text-white/40 ml-5">{custo.descricao}</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 text-white/40 hover:text-white"><X size={16} /></button>
        </div>
        <div className="px-6 pt-5 pb-4">
          <div className="flex justify-between text-[9px] font-black uppercase tracking-widest mb-2">
            <span className="text-white/40">Executado</span>
            <span className="text-teal-400">{fmtBRL(custo.valor_executado)} / {fmtBRL(custo.valor_previsto)}</span>
          </div>
          <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
            <div className="h-full bg-teal-500 rounded-full transition-all duration-700"
              style={{ width: `${Math.min(100, custo.valor_previsto > 0 ? (custo.valor_executado / custo.valor_previsto) * 100 : 0)}%` }} />
          </div>
          <div className="text-[9px] text-white/30 mt-1.5">Saldo disponível: {fmtBRL(saldo)}</div>
        </div>
        <div className="px-6 pb-4 grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Valor (R$) *</label>
            <BrlInput value={valor} onChange={setValor} className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-teal-400 font-mono outline-none" />
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Data</label>
            <input type="date" value={data} className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white outline-none" onChange={e => setData(e.target.value)} />
          </div>
          <div className="col-span-2 space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Observação</label>
            <input value={obs} className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white/60 outline-none" placeholder="Opcional" onChange={e => setObs(e.target.value)} />
          </div>
          {overrun && (
            <div className="col-span-2 flex items-center gap-2 bg-amber-500/5 border border-amber-500/20 rounded-lg px-3 py-2">
              <AlertTriangle size={12} className="text-amber-400 shrink-0" />
              <span className="text-[9px] text-amber-400">Valor excede o saldo de {fmtBRL(saldo)} — o item ficará em estouro</span>
            </div>
          )}
        </div>
        <div className="flex items-center justify-end gap-3 px-6 pb-4">
          {savedMsg && <span className="text-[10px] text-teal-400 font-black mr-auto">✓ Registrado com sucesso</span>}
          <Button onClick={onClose} variant="outline" className="border-white/10 text-white/40 text-xs h-9">Fechar</Button>
          <Button onClick={() => mut.mutate({ valor, data, observacoes: obs })}
            disabled={mut.isPending || valor <= 0}
            className="bg-teal-600 hover:bg-teal-500 text-white font-black text-xs h-9 px-6 disabled:opacity-40">
            {mut.isPending ? 'Registrando...' : 'Registrar'}
          </Button>
        </div>
        {lancamentos.length > 0 && (
          <div className="border-t border-white/5 px-6 py-4">
            <div className="text-[9px] font-black uppercase tracking-widest text-white/30 mb-3 flex items-center gap-2"><Clock size={10} /> Histórico</div>
            <div className="space-y-2 max-h-40 overflow-y-auto pr-1 custom-scroll">
              {lancamentos.map((lc: any) => (
                <div key={lc.id} className="flex items-center justify-between bg-white/[0.02] border border-white/5 rounded-lg px-3 py-2 group">
                  <div>
                    <span className="text-teal-400 font-mono text-xs font-black">{lc.valor_fmt}</span>
                    {lc.observacoes && <span className="text-white/30 text-[10px] ml-2">{lc.observacoes}</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] font-mono text-white/30">{lc.data}</span>
                    {pendingDelLanc === lc.id ? (
                      <div className="flex items-center gap-1">
                        <button onClick={() => delLanc.mutate(lc.id)} className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-[9px] font-black hover:bg-red-500/30">Excluir</button>
                        <button onClick={() => setPendingDelLanc(null)} className="px-2 py-0.5 rounded bg-white/5 text-white/40 text-[9px] font-black">Não</button>
                      </div>
                    ) : (
                      <button onClick={() => setPendingDelLanc(lc.id)} className="p-1 rounded hover:bg-red-500/20 text-red-400/30 hover:text-red-400 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                        <Trash2 size={11} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function FinModalEditar({ custo, cats, contrato, onClose, qc, onSaved }: { custo: any; cats: any[]; contrato: string; onClose: () => void; qc: any; onSaved?: () => void }) {
  const [form, setForm] = useState({
    categoria_id: custo.categoria_id, categoria_nome: custo.categoria_nome,
    empresa: custo.empresa ?? '', descricao: custo.descricao,
    valor_previsto: custo.valor_previsto, data_custo: custo.data_custo ?? '',
    observacoes: custo.observacoes ?? '', status: custo.status,
  })
  const f = (k: string, v: any) => setForm(p => ({ ...p, [k]: v }))
  const mut = useMutation({
    mutationFn: (b: any) => api.patch(`/financeiro/${custo.id}`, b).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['fin', contrato] }); onClose(); onSaved?.() },
  })
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-xl bg-[#0d1117] border border-white/10 rounded-2xl shadow-2xl">
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/5">
          <div className="flex items-center gap-3"><Edit2 size={14} className="text-copper" /><span className="text-sm font-black uppercase tracking-widest text-white">Editar Item</span></div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 text-white/40 hover:text-white"><X size={16} /></button>
        </div>
        <div className="p-6 grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Categoria</label>
            <select className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-copper outline-none" value={form.categoria_id}
              onChange={e => { f('categoria_id', e.target.value); f('categoria_nome', cats.find(c => c.id === e.target.value)?.nome ?? '') }}>
              {cats.map((c: any) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Empresa</label>
            <input className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white outline-none" value={form.empresa} onChange={e => f('empresa', e.target.value)} />
          </div>
          <div className="col-span-2 space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Descrição</label>
            <input className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white outline-none" value={form.descricao} onChange={e => f('descricao', e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Valor Previsto (R$)</label>
            <BrlInput value={form.valor_previsto ?? 0} onChange={v => f('valor_previsto', v)} className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-copper font-mono outline-none" />
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Data</label>
            <input type="date" className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white outline-none" value={form.data_custo} onChange={e => f('data_custo', e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Status</label>
            <select className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white/60 outline-none" value={form.status} onChange={e => f('status', e.target.value)}>
              {['previsto', 'em_andamento', 'parcial', 'concluido', 'cancelado'].map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
            </select>
          </div>
          <div className="col-span-2 space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Observações</label>
            <textarea rows={2} className="w-full bg-void border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white/60 outline-none resize-none" value={form.observacoes} onChange={e => f('observacoes', e.target.value)} />
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-white/5">
          <Button onClick={onClose} variant="outline" className="border-white/10 text-white/40 text-xs h-9">Cancelar</Button>
          <Button onClick={() => mut.mutate({ ...form, data: form.data_custo })} disabled={mut.isPending}
            className="bg-copper text-void font-black text-xs h-9 px-6 hover:bg-copper/90">
            {mut.isPending ? 'Salvando...' : 'Salvar'}
          </Button>
        </div>
      </div>
    </div>
  )
}

function FinCategoriaGrupo({ nome, itens, contrato, cats, onAvanco, onEdit, onDelete }: {
  nome: string; itens: any[]; contrato: string; cats: any[];
  onAvanco: (c: any) => void; onEdit: (c: any) => void; onDelete: (id: string) => void
}) {
  const [open, setOpen] = useState(true)
  const [pendingDelete, setPendingDelete] = useState<string | null>(null)
  const totalPrev = itens.reduce((s, r) => s + r.valor_previsto, 0)
  const totalExec = itens.reduce((s, r) => s + r.valor_executado, 0)
  const pct = totalPrev > 0 ? Math.min(100, (totalExec / totalPrev) * 100) : 0
  return (
    <div className="rounded-2xl border border-white/5 overflow-hidden">
      <button onClick={() => setOpen(o => !o)} className="w-full flex items-center justify-between px-5 py-4 bg-white/[0.02] hover:bg-white/[0.04] transition-colors">
        <div className="flex items-center gap-3">
          {open ? <ChevronDown size={14} className="text-copper" /> : <ChevronRight size={14} className="text-white/30" />}
          <span className="text-[10px] font-black uppercase tracking-widest text-white">{nome}</span>
          <span className="text-[9px] text-white/30 font-mono">{itens.length} iten{itens.length !== 1 ? 's' : ''}</span>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-right hidden sm:block">
            <div className="text-[9px] text-white/30 uppercase tracking-widest">Previsto</div>
            <div className="text-xs font-mono font-black text-copper">{fmtBRL(totalPrev)}</div>
          </div>
          <div className="text-right hidden sm:block">
            <div className="text-[9px] text-white/30 uppercase tracking-widest">Executado</div>
            <div className="text-xs font-mono font-black text-teal-400">{fmtBRL(totalExec)}</div>
          </div>
          <div className="flex items-center gap-2 min-w-[80px]">
            <div className="h-1.5 flex-1 bg-white/5 rounded-full overflow-hidden">
              <div className="h-full bg-teal-500 rounded-full transition-all duration-700" style={{ width: `${pct}%` }} />
            </div>
            <span className="text-[9px] font-mono text-white/40 w-8 text-right">{pct.toFixed(0)}%</span>
          </div>
        </div>
      </button>
      {open && (
        <div className="divide-y divide-white/[0.02]">
          {itens.map(r => {
            const pctI = r.valor_previsto > 0 ? Math.min(100, (r.valor_executado / r.valor_previsto) * 100) : 0
            return (
              <div key={r.id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-white/[0.015] transition-colors group">
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-bold text-white truncate">{r.descricao}</div>
                  {r.empresa && <div className="flex items-center gap-1 mt-0.5"><Building2 size={9} className="text-white/20" /><span className="text-[9px] text-white/30">{r.empresa}</span></div>}
                </div>
                <div className="flex items-center gap-2 w-28 shrink-0 hidden md:flex">
                  <div className="h-1 flex-1 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-teal-500 rounded-full" style={{ width: `${pctI}%` }} />
                  </div>
                  <span className="text-[9px] font-mono text-white/30 w-7 text-right">{pctI.toFixed(0)}%</span>
                </div>
                <div className="text-right shrink-0 hidden sm:block">
                  <div className="text-[9px] text-white/30">Prev</div>
                  <div className="text-xs font-mono text-copper">{r.valor_previsto_fmt}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-[9px] text-white/30">Exec</div>
                  <div className="text-xs font-mono text-teal-400">{r.valor_executado_fmt}</div>
                </div>
                <div className="shrink-0 hidden lg:block"><FinStatusBadge status={r.status} /></div>
                {pendingDelete === r.id ? (
                  <div className="flex items-center gap-1.5 shrink-0 animate-enter">
                    <span className="text-[9px] text-white/40">Confirmar?</span>
                    <button onClick={() => { onDelete(r.id); setPendingDelete(null) }} className="px-2 py-1 rounded-lg bg-red-500/20 text-red-400 text-[9px] font-black hover:bg-red-500/30">Sim</button>
                    <button onClick={() => setPendingDelete(null)} className="px-2 py-1 rounded-lg bg-white/5 text-white/40 text-[9px] font-black hover:bg-white/10">Não</button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1 shrink-0 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                    <button onClick={() => onAvanco(r)} className="p-1.5 rounded-lg hover:bg-teal-500/20 text-teal-400/50 hover:text-teal-400" title="Registrar Pagamento"><Zap size={13} /></button>
                    <button onClick={() => onEdit(r)} className="p-1.5 rounded-lg hover:bg-copper/20 text-copper/50 hover:text-copper" title="Editar"><Edit2 size={13} /></button>
                    <button onClick={() => setPendingDelete(r.id)} className="p-1.5 rounded-lg hover:bg-red-500/20 text-red-400/40 hover:text-red-400" title="Excluir"><Trash2 size={13} /></button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function FinanceiroTab({ contrato }: { contrato: string }) {
  const qc = useQueryClient()
  const [finTab, setFinTab]       = useState<'lancamentos' | 'scurve' | 'bycat' | 'evm'>('lancamentos')
  const [modalNovo, setModalNovo] = useState(false)
  const [avancoItem, setAvancoItem] = useState<any>(null)
  const [editItem, setEditItem]   = useState<any>(null)
  const [filterCat, setFilterCat] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000) }

  const { data, isLoading } = useQuery({
    queryKey: ['fin', contrato],
    queryFn:  () => api.get(`/financeiro/${contrato}`).then(r => r.data),
    staleTime: 2 * 60_000,
    refetchOnWindowFocus: true,
    placeholderData: keepPreviousData,
    enabled: !!contrato,
  })

  const { data: ativData } = useQuery({
    queryKey: ['hub-cronograma', contrato],
    queryFn:  () => api.get(`/hub/cronograma?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    staleTime: Infinity,
    enabled: !!contrato,
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/financeiro/${id}`).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['fin', contrato] }); showToast('Item excluído') },
    onError:   () => showToast('Erro ao excluir item'),
  })

  if (isLoading) return <Skeleton />

  const d        = data || {}
  const custos: any[]  = d.custos ?? []
  const cats: any[]    = d.categorias ?? []
  const scurve: any[]  = d.scurve ?? []
  const bycat: any[]   = d.by_categoria ?? []
  const evm            = d.evm ?? {}
  const atividades: any[] = ativData?.atividades ?? []

  const custosFiltrados = custos.filter(r => {
    if (filterCat && r.categoria_nome !== filterCat) return false
    if (filterStatus && r.status !== filterStatus) return false
    return true
  })

  const grupos: Record<string, any[]> = {}
  for (const r of custosFiltrados) {
    const cat = r.categoria_nome || '— Sem Categoria'
    if (!grupos[cat]) grupos[cat] = []
    grupos[cat].push(r)
  }

  const totalPrev = custos.reduce((s, r) => s + (r.valor_previsto ?? 0), 0)
  const totalExec = custos.reduce((s, r) => s + (r.valor_executado ?? 0), 0)
  const burnPct   = totalPrev > 0 ? Math.min(100, (totalExec / totalPrev) * 100) : 0

  return (
    <div className="flex flex-col gap-6 animate-enter">
      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-panel p-5 border-white/5">
          <div className="flex items-center gap-2 mb-3"><div className="p-1.5 rounded-lg bg-white/5"><Wallet size={14} className="text-white/60" /></div><span className="text-[9px] font-black uppercase tracking-widest text-white/40">Total Previsto</span></div>
          <div className="text-xl font-black font-mono text-white">{fmtBRL(totalPrev)}</div>
          <div className="text-[9px] text-white/20 mt-1">{custos.length} itens de custo</div>
        </div>
        <div className="glass-panel p-5 border-white/5">
          <div className="flex items-center gap-2 mb-3"><div className="p-1.5 rounded-lg bg-teal-500/10"><TrendingUp size={14} className="text-teal-400" /></div><span className="text-[9px] font-black uppercase tracking-widest text-white/40">Executado</span></div>
          <div className="text-xl font-black font-mono text-teal-400">{fmtBRL(totalExec)}</div>
          <div className="text-[9px] text-teal-400/40 mt-1">{d.kpis?.concluidos ?? 0} concluídos</div>
        </div>
        <div className="glass-panel p-5 border-white/5">
          <div className="flex items-center gap-2 mb-3"><div className="p-1.5 rounded-lg bg-copper/10"><ShieldCheck size={14} className="text-copper" /></div><span className="text-[9px] font-black uppercase tracking-widest text-white/40">Saldo</span></div>
          <div className="text-xl font-black font-mono text-copper">{fmtBRL(totalPrev - totalExec)}</div>
          <div className="text-[9px] text-white/20 mt-1">Remanescente</div>
        </div>
        <div className="glass-panel p-5 border-white/5">
          <div className="flex items-center gap-2 mb-3"><div className="p-1.5 rounded-lg bg-amber-500/10"><Activity size={14} className="text-amber-400" /></div><span className="text-[9px] font-black uppercase tracking-widest text-white/40">Burn Rate</span></div>
          <div className="text-xl font-black font-mono" style={{ color: burnPct > 90 ? RED : burnPct > 70 ? '#F59E0B' : TEAL }}>{burnPct.toFixed(1)}%</div>
          <div className="h-1.5 w-full bg-white/5 rounded-full mt-2 overflow-hidden">
            <div className="h-full rounded-full transition-all duration-700" style={{ width: `${burnPct}%`, background: burnPct > 90 ? RED : burnPct > 70 ? '#F59E0B' : TEAL }} />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-1 bg-white/[0.02] border border-white/5 p-1 rounded-xl">
          {[
            { id: 'lancamentos', label: 'Lançamentos', icon: FileText },
            { id: 'scurve',      label: 'Curva-S',     icon: TrendingUp },
            { id: 'bycat',       label: 'Por Categoria', icon: PieChart },
            { id: 'evm',         label: 'EVM',          icon: Calculator },
          ].map(t => (
            <button key={t.id} onClick={() => setFinTab(t.id as any)}
              className={`px-3 py-2 rounded-lg flex items-center gap-2 text-[10px] font-black uppercase tracking-widest transition-all ${finTab === t.id ? 'bg-copper text-void shadow-lg' : 'text-text-muted hover:text-white'}`}>
              <t.icon size={12} /> {t.label}
            </button>
          ))}
        </div>
        {finTab === 'lancamentos' && (
          <Button onClick={() => setModalNovo(true)} className="bg-void border border-copper/40 hover:border-copper text-copper font-black text-[10px] uppercase tracking-widest h-9 px-4">
            <Plus size={14} className="mr-2" /> Novo Item
          </Button>
        )}
      </div>

      {/* Lançamentos */}
      {finTab === 'lancamentos' && (
        <div className="flex flex-col gap-3 animate-enter">
          {(cats.length > 0 || custos.length > 0) && (
            <div className="flex items-center gap-3 flex-wrap">
              <select className="bg-void border border-white/10 rounded-lg h-8 px-3 text-[10px] text-white/60 outline-none" value={filterCat} onChange={e => setFilterCat(e.target.value)}>
                <option value="">Todas categorias</option>
                {cats.map((c: any) => <option key={c.id} value={c.nome}>{c.nome}</option>)}
              </select>
              <select className="bg-void border border-white/10 rounded-lg h-8 px-3 text-[10px] text-white/60 outline-none" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
                <option value="">Todos status</option>
                {['previsto', 'em_andamento', 'parcial', 'concluido', 'cancelado'].map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
              </select>
              {(filterCat || filterStatus) && (
                <button onClick={() => { setFilterCat(''); setFilterStatus('') }} className="text-[9px] text-white/30 hover:text-white flex items-center gap-1">
                  <X size={10} /> Limpar
                </button>
              )}
              <span className="text-[9px] text-white/20 ml-auto">{custosFiltrados.length} de {custos.length} itens</span>
            </div>
          )}
          {Object.keys(grupos).length === 0 ? (
            <div className="glass-panel p-20 text-center border-white/5">
              <DollarSign size={32} className="text-white/10 mx-auto mb-4" />
              <p className="text-white/20 text-sm font-bold">Nenhum item de custo cadastrado</p>
              <button onClick={() => setModalNovo(true)} className="mt-4 text-copper text-[10px] font-black uppercase tracking-widest hover:underline">+ Criar primeiro item</button>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {Object.entries(grupos).map(([cat, itens]) => (
                <FinCategoriaGrupo key={cat} nome={cat} itens={itens} contrato={contrato} cats={cats}
                  onAvanco={setAvancoItem} onEdit={setEditItem}
                  onDelete={id => deleteMut.mutate(id)} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Curva-S */}
      {finTab === 'scurve' && (
        <div className="glass-panel p-8 border-white/5 animate-enter">
          <h3 className="text-xs font-black uppercase tracking-widest text-copper mb-1">Curva-S Acumulada</h3>
          <p className="text-[10px] text-text-muted mb-8">Evolução diária: Baseline planejada vs. execução real</p>
          {scurve.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-white/20 text-sm">Sem dados temporais</div>
          ) : (
            <div className="h-[360px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={scurve} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="fin_fp" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={COPPER} stopOpacity={0.12} /><stop offset="95%" stopColor={COPPER} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="fin_fe" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={TEAL} stopOpacity={0.15} /><stop offset="95%" stopColor={TEAL} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                  <XAxis dataKey="data" axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9, fontWeight: 700 }} interval={Math.max(0, Math.floor(scurve.length / 8) - 1)} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9, fontWeight: 700 }} tickFormatter={v => `R$${(v / 1000).toFixed(0)}k`} />
                  <Tooltip content={<FinSCurveTip />} />
                  <Legend formatter={v => <span className="text-[9px] font-black uppercase tracking-widest text-white/40">{v}</span>} iconType="circle" iconSize={8} />
                  <Area type="monotone" dataKey="previsto_acum" stroke={COPPER} strokeWidth={2} fill="url(#fin_fp)" name="Baseline" dot={false} />
                  <Area type="monotone" dataKey="executado_acum" stroke={TEAL} strokeWidth={2.5} fill="url(#fin_fe)" name="Executado" dot={{ r: 3, fill: TEAL, strokeWidth: 0 }} activeDot={{ r: 5 }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Por Categoria */}
      {finTab === 'bycat' && (
        <div className="flex flex-col gap-4 animate-enter">
          <div className="glass-panel p-8 border-white/5">
            <h3 className="text-xs font-black uppercase tracking-widest text-copper mb-1">Distribuição por Categoria</h3>
            <p className="text-[10px] text-text-muted mb-8">Previsto vs. executado por categoria de custo</p>
            {bycat.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-white/20 text-sm">Sem dados</div>
            ) : (
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={bycat} layout="vertical" margin={{ left: 20, right: 30 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(255,255,255,0.03)" />
                    <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9 }} tickFormatter={v => `R$${(v/1000).toFixed(0)}k`} />
                    <YAxis type="category" dataKey="categoria" width={130} axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 10, fontWeight: 700 }} />
                    <Tooltip contentStyle={{ background: '#0d1117', border: BORDER, borderRadius: 12 }} formatter={(v: any) => fmtBRL(v)} />
                    <Legend formatter={v => <span className="text-[9px] font-black uppercase tracking-widest text-white/40">{v}</span>} iconType="circle" iconSize={8} />
                    <Bar dataKey="previsto" fill={COPPER} radius={[0, 4, 4, 0]} name="Previsto" barSize={14} />
                    <Bar dataKey="executado" fill={TEAL} radius={[0, 4, 4, 0]} name="Executado" barSize={14} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
          <div className="glass-panel border-white/5 overflow-hidden">
            <table className="w-full">
              <thead><tr className="bg-white/[0.02] border-b border-white/5">
                <th className="text-left px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">Categoria</th>
                <th className="text-right px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">Previsto</th>
                <th className="text-right px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">Executado</th>
                <th className="text-right px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">%</th>
                <th className="px-5 py-3" />
              </tr></thead>
              <tbody className="divide-y divide-white/[0.02]">
                {bycat.map((r: any) => {
                  const p = r.previsto > 0 ? Math.min(100, (r.executado / r.previsto) * 100) : 0
                  return (
                    <tr key={r.categoria} className="hover:bg-white/[0.015]">
                      <td className="px-5 py-3 text-xs font-bold text-white">{r.categoria}</td>
                      <td className="px-5 py-3 text-right font-mono text-xs text-copper">{fmtBRL(r.previsto)}</td>
                      <td className="px-5 py-3 text-right font-mono text-xs text-teal-400">{fmtBRL(r.executado)}</td>
                      <td className="px-5 py-3 text-right text-[10px] font-mono text-white/40">{p.toFixed(1)}%</td>
                      <td className="px-5 py-3 w-28"><div className="h-1.5 bg-white/5 rounded-full overflow-hidden"><div className="h-full bg-teal-500 rounded-full" style={{ width: `${p}%` }} /></div></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* EVM */}
      {finTab === 'evm' && (
        <div className="flex flex-col gap-6 animate-enter">
          {Object.keys(evm).length === 0 ? (
            <div className="glass-panel p-20 text-center border-white/5">
              <Calculator size={32} className="text-white/10 mx-auto mb-4" />
              <p className="text-white/20 text-sm font-bold">Sem dados suficientes para calcular EVM</p>
            </div>
          ) : (
            <>
              <div>
                <div className="text-[9px] font-black uppercase tracking-widest text-white/30 mb-3">Índices de Desempenho</div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                  <FinEVMCard metric="CPI"  fmt={String(evm.CPI)}  good={evm.CPI >= 1} />
                  <FinEVMCard metric="SPI"  fmt={String(evm.SPI)}  good={evm.SPI >= 1} />
                  <FinEVMCard metric="TCPI" fmt={String(evm.TCPI)} good={evm.TCPI <= 1} />
                  <FinEVMCard metric="CV"   fmt={(evm.CV >= 0 ? '+' : '-') + evm.CV_fmt} good={evm.CV >= 0} />
                  <FinEVMCard metric="SV"   fmt={(evm.SV >= 0 ? '+' : '-') + evm.SV_fmt} good={evm.SV >= 0} />
                </div>
              </div>
              <div>
                <div className="text-[9px] font-black uppercase tracking-widest text-white/30 mb-3">Valores de Referência</div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {([
                    { m: 'BAC', fmt: evm.BAC_fmt, good: true },
                    { m: 'EAC', fmt: evm.EAC_fmt, good: !evm.is_overrun },
                    { m: 'VAC', fmt: (evm.is_overrun ? '-' : '+') + evm.VAC_fmt, good: !evm.is_overrun },
                    { m: 'PV',  fmt: evm.PV_fmt,  good: true },
                    { m: 'EV',  fmt: evm.EV_fmt,  good: true },
                    { m: 'AC',  fmt: evm.AC_fmt,  good: true },
                  ] as any[]).map(x => (
                    <div key={x.m} className="bg-white/[0.02] border border-white/5 rounded-xl p-4">
                      <div className="flex items-center gap-1.5 mb-2">
                        <span className="text-[9px] font-black uppercase tracking-widest text-white/40">{x.m}</span>
                        <FinEVMTooltip metric={x.m} />
                      </div>
                      <div className="text-base font-black font-mono" style={{ color: x.good ? '#FFF' : RED }}>{x.fmt}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="glass-panel p-6 border-white/5">
                <h3 className="text-[10px] font-black uppercase tracking-widest text-white/40 mb-6 flex items-center gap-2">
                  <Activity size={12} className="text-copper" /> Avanço Físico vs. Financeiro
                </h3>
                <div className="space-y-5">
                  <div>
                    <div className="flex justify-between text-[9px] font-black uppercase tracking-widest mb-2">
                      <span className="text-copper">Físico</span><span className="text-white">{evm.physical_pct}%</span>
                    </div>
                    <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden"><div className="h-full bg-copper rounded-full transition-all" style={{ width: `${evm.physical_pct}%` }} /></div>
                  </div>
                  <div>
                    <div className="flex justify-between text-[9px] font-black uppercase tracking-widest mb-2">
                      <span className="text-teal-400">Financeiro</span><span className="text-white">{evm.cost_pct}%</span>
                    </div>
                    <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden"><div className="h-full bg-teal-500 rounded-full transition-all" style={{ width: `${evm.cost_pct}%` }} /></div>
                  </div>
                </div>
                {evm.is_overrun && (
                  <div className="mt-6 flex items-start gap-3 bg-red-500/5 border border-red-500/20 rounded-xl p-4">
                    <AlertTriangle size={16} className="text-red-400 shrink-0 mt-0.5" />
                    <div>
                      <div className="text-xs font-black text-red-400 mb-1">Alerta de Estouro Orçamentário</div>
                      <div className="text-[10px] text-red-400/60">Projeção indica custo final {evm.VAC_fmt} acima do BAC.</div>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Modals */}
      {modalNovo && <FinModalNovoCusto contrato={contrato} cats={cats} atividades={atividades} onClose={() => setModalNovo(false)} onSaved={() => showToast('Item criado com sucesso')} qc={qc} />}
      {avancoItem && <FinModalAvanco custo={avancoItem} contrato={contrato} onClose={() => setAvancoItem(null)} qc={qc} />}
      {editItem && <FinModalEditar custo={editItem} cats={cats} contrato={contrato} onClose={() => setEditItem(null)} qc={qc} onSaved={() => showToast('Item atualizado')} />}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-[100] bg-teal-700 border border-teal-500/30 text-white text-xs font-black px-5 py-3 rounded-xl shadow-2xl animate-enter">
          {toast}
        </div>
      )}
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const shimmer = 'relative overflow-hidden before:absolute before:inset-0 before:-translate-x-full before:animate-[shimmer_1.5s_infinite] before:bg-gradient-to-r before:from-transparent before:via-white/5 before:to-transparent'

function Skeleton() {
  return (
    <div className="flex flex-col gap-5 animate-in fade-in duration-300">
      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {Array.from({length: 5}).map((_, i) => (
          <div key={i} className={`h-24 bg-white/[0.04] rounded-2xl border border-white/[0.04] ${shimmer}`} />
        ))}
      </div>
      {/* Main chart area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className={`lg:col-span-2 h-64 bg-white/[0.04] rounded-2xl border border-white/[0.04] ${shimmer}`} />
        <div className="flex flex-col gap-4">
          {Array.from({length: 4}).map((_, i) => (
            <div key={i} className={`h-12 bg-white/[0.04] rounded-xl border border-white/[0.04] ${shimmer}`} />
          ))}
        </div>
      </div>
      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className={`h-48 bg-white/[0.04] rounded-2xl border border-white/[0.04] ${shimmer}`} />
        <div className={`h-48 bg-white/[0.04] rounded-2xl border border-white/[0.04] ${shimmer}`} />
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function HubOperacoes({ hubTab, onHubTabChange }: any) {
  const [searchParams, setSearchParams] = useSearchParams()
  const contrato = searchParams.get('contrato') ?? ''
  const activeTab = hubTab || searchParams.get('tab') || 'visao_geral'
  const queryClient = useQueryClient()

  // Scroll to top when entering a contract view
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [contrato])

  const { data: contratosList } = useQuery({
    queryKey: ['hub-contratos'],
    queryFn:  () => api.get('/hub/contratos').then(r => r.data),
    staleTime: Infinity,
    gcTime:    30 * 60_000,
    placeholderData: keepPreviousData,
  })

  // Prefetch todas as tabs em background quando contrato é selecionado
  const prefetchTabs = useCallback((cod: string) => {
    if (!cod) return
    const tabs = [
      { key: ['hub-visao-geral', cod],  url: `/hub/visao-geral?contrato=${encodeURIComponent(cod)}` },
      { key: ['hub-dashboard', cod],    url: `/hub/dashboard?contrato=${encodeURIComponent(cod)}` },
      { key: ['hub-cronograma', cod],   url: `/hub/cronograma?contrato=${encodeURIComponent(cod)}` },
      { key: ['hub-timeline', cod],     url: `/hub/timeline?contrato=${encodeURIComponent(cod)}` },
      { key: ['hub-auditoria', cod],    url: `/hub/auditoria?contrato=${encodeURIComponent(cod)}` },
      { key: ['fin', cod],              url: `/financeiro/${encodeURIComponent(cod)}` },
      { key: ['hub-agente-insights', cod], url: `/hub/agente/insights?contrato=${encodeURIComponent(cod)}` },
    ]
    const FINANCIAL_KEYS = ['hub-dashboard', 'fin']
    tabs.forEach(({ key, url }) => {
      const isFinancial = FINANCIAL_KEYS.includes(key[0] as string)
      queryClient.prefetchQuery({
        queryKey: key,
        queryFn:  () => api.get(url).then(r => r.data),
        staleTime: isFinancial ? 5 * 60_000 : Infinity,
      })
    })
  }, [queryClient])

  const contratos: any[] = contratosList?.contratos ?? []
  const [isProjectModalOpen, setIsProjectModalOpen] = useState(false)
  const [editingProject, setEditingProject] = useState<any>(null)

  return (
    <div className="flex flex-col gap-6 pb-20">
      {!contrato ? (
        <div className="flex flex-col gap-8 animate-enter">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
                  <HardHat size={22} className="text-copper" />
                </div>
                <h2 className="font-display text-3xl font-black text-white uppercase tracking-tight">Radar de Projetos</h2>
              </div>
              <p className="text-text-muted text-[10px] uppercase font-bold tracking-[0.3em] ml-1">Central de Operações Ativas</p>
            </div>
            <Button onClick={() => { setEditingProject(null); setIsProjectModalOpen(true); }} className="bg-copper hover:bg-copper/90 text-void font-black text-[10px] uppercase h-11 px-6 shadow-[0_0_20px_rgba(201,139,42,0.2)]">
              <Plus size={16} className="mr-2" /> Novo Projeto
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {contratos.map(c => {
              const saude = c.saude || 'OK'
              const saudeColor = c.saude_color || TEAL
              const desvio = c.desvio_pct || 0
              // desvio = realizado - esperado: positivo = adiantado (TEAL), negativo = atrasado (RED)
              const desvioColor = desvio > 0 ? TEAL : desvio < 0 ? RED : '#888'
              const statusColors: Record<string, { color: string; bg: string }> = {
                'Em Execução':    { color: TEAL,   bg: `${TEAL}15` },
                'Em Planejamento':{ color: COPPER, bg: `${COPPER}15` },
                'Concluído':      { color: '#3B82F6', bg: 'rgba(59,130,246,0.15)' },
                'Pausado':        { color: '#888', bg: 'rgba(136,136,136,0.15)' },
                'Cancelado':      { color: RED, bg: `${RED}15` },
              }
              const sc = statusColors[c.status] ?? { color: COPPER, bg: `${COPPER}15` }

              return (
                <div
                  key={c.contrato}
                  className="project-card-glow glass-panel rounded-2xl p-6 flex flex-col group border-white/5 cursor-pointer"
                  onMouseEnter={() => prefetchTabs(c.contrato)}
                  onClick={() => { prefetchTabs(c.contrato); setSearchParams({ contrato: c.contrato }) }}
                >
                  {/* Status badge + menu */}
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-[10px] font-black px-3 py-1 rounded-full uppercase tracking-widest" style={{ color: sc.color, background: sc.bg }}>
                      {c.status || 'Ativo'}
                    </span>
                    <button
                      onClick={e => { e.stopPropagation(); setEditingProject(c); setIsProjectModalOpen(true); }}
                      className="p-1.5 hover:bg-white/10 rounded-md text-text-muted transition-colors"
                    >
                      <Pencil size={14} />
                    </button>
                  </div>

                  {/* Title */}
                  <div className="mb-5">
                    <h3 className="text-lg font-bold text-white uppercase tracking-tight leading-tight group-hover:text-copper transition-colors">
                      {c.projeto || 'Sem Nome'}
                    </h3>
                    <div className="flex items-center gap-2 mt-1 text-[10px] font-mono text-text-muted">
                      <span className="text-copper/60">ID:</span> {c.contrato}
                    </div>
                  </div>

                  {/* Info grid */}
                  <div className="grid grid-cols-2 gap-3 mb-5">
                    <div>
                      <span className="text-[9px] font-bold text-text-muted uppercase tracking-[0.15em] flex items-center gap-1.5 mb-1">
                        <User size={9} className="text-copper" /> Cliente
                      </span>
                      <p className="text-xs text-white/80 font-medium truncate">{c.cliente || '—'}</p>
                    </div>
                    <div>
                      <span className="text-[9px] font-bold text-text-muted uppercase tracking-[0.15em] flex items-center gap-1.5 mb-1">
                        <MapPin size={9} className="text-copper" /> Localização
                      </span>
                      <p className="text-xs text-white/80 font-medium truncate">{c.localizacao || '—'}</p>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="space-y-2 mb-5">
                    <div className="flex justify-between items-end">
                      <span className="text-[9px] font-bold text-text-muted uppercase tracking-[0.15em]">Progresso Físico</span>
                      <span className="text-xs font-mono font-bold text-copper">{c.progress ?? 0}%</span>
                    </div>
                    <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-copper to-[#E0A63B] shadow-[0_0_8px_rgba(201,139,42,0.4)] transition-all duration-1000"
                        style={{ width: `${c.progress ?? 0}%` }}
                      />
                    </div>
                  </div>

                  {/* Stats strip */}
                  <div className="grid grid-cols-3 gap-2 mt-auto">
                    <div className="bg-white/[0.03] border border-white/[0.05] rounded-xl p-3">
                      <div className="text-[8px] font-bold text-text-muted uppercase mb-1">Saúde</div>
                      <div className="text-sm font-black" style={{ color: saudeColor }}>{saude}</div>
                    </div>
                    <div className="bg-white/[0.03] border border-white/[0.05] rounded-xl p-3">
                      <div className="text-[8px] font-bold text-text-muted uppercase mb-1">Prazo</div>
                      <div className="text-[10px] font-mono text-white/80">
                        {c.termino ? new Date(c.termino).toLocaleDateString('pt-BR') : '—'}
                      </div>
                    </div>
                    <div className="bg-white/[0.03] border border-white/[0.05] rounded-xl p-3">
                      <div className="text-[8px] font-bold text-text-muted uppercase mb-1">Desvio</div>
                      <div className="text-sm font-black" style={{ color: desvioColor }}>
                        {desvio > 0 ? '+' : ''}{desvio}%
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
                    <span className="text-[9px] font-bold uppercase tracking-widest text-text-muted">Entrar no Hub</span>
                    <ChevronRight size={14} className="text-copper group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>
              )
            })}
          </div>

          {contratos.length === 0 && (
            <div className="p-20 glass-panel rounded-3xl flex flex-col items-center text-center gap-4">
              <div className="p-8 rounded-full bg-white/5 border border-white/10">
                <Activity size={48} className="text-text-muted opacity-20" />
              </div>
              <p className="text-text-muted font-mono uppercase tracking-widest text-sm">Nenhum projeto no radar.</p>
              <Button onClick={() => { setEditingProject(null); setIsProjectModalOpen(true); }} variant="outline" className="border-copper/40 text-copper hover:bg-copper/10">
                Criar Primeiro Projeto
              </Button>
            </div>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {/* Parity Title Row: Voltar + Título (No internal tabs here - they are in the TopBar) */}
          <div className="flex flex-col gap-6">
            <div className="flex items-center gap-4">
                <button 
                  onClick={() => setSearchParams({})} 
                  className="p-3 bg-white/5 border border-white/10 rounded-2xl text-text-muted hover:text-white hover:bg-white/10 transition-all group"
                >
                  <ArrowRight size={20} className="rotate-180 group-hover:-translate-x-1 transition-transform" />
                </button>
                <div>
                  <span className="text-[10px] text-copper font-black uppercase tracking-widest">{contrato}</span>
                  <h2 className="text-2xl font-display font-bold text-white uppercase tracking-tight">
                    {contratos.find((c: any) => c.contrato === contrato)?.projeto || 'Carregando...'}
                  </h2>
                </div>
            </div>
            <div className="h-px w-full bg-gradient-to-r from-white/10 via-white/5 to-transparent" />
          </div>

          <div className="min-h-[400px]">
            {activeTab === 'visao_geral' && <OverviewTab contrato={contrato} contratoInfo={contratos.find((c: any) => c.contrato === contrato)} />}
            {activeTab === 'dashboard' && <DashboardTab contrato={contrato} />}
            {activeTab === 'cronograma' && <CronogramaTab contrato={contrato} />}
            {activeTab === 'auditoria' && <AuditoriaTab contrato={contrato} />}
            {activeTab === 'timeline' && <TimelineTab contrato={contrato} />}
            {activeTab === 'financeiro' && <FinanceiroTab contrato={contrato} />}
          </div>
        </div>
      )}
      <ProjectModal isOpen={isProjectModalOpen} onClose={() => setIsProjectModalOpen(false)} editingProject={editingProject} />
    </div>
  )
}
