import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { useState, useMemo, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, CartesianGrid, ComposedChart, ReferenceLine, Bar, BarChart, LabelList,
} from 'recharts'
import {
  Plus, Image as ImageIcon, Clock, Activity,
  AlertTriangle, CheckCircle, GanttChartIcon, List,
  Mic, CloudRain, Zap, TrendingDown, TrendingUp, BarChart2, Search,
  User, LayoutDashboard, ScanEye, GitBranch, Wallet, DollarSign,
  ArrowRight, Gauge, Sparkles, X, CalendarCheck, MinusCircle, ChevronDown,
  ChevronRight, Pencil, Trash2, CalendarRange, MapPin, HardHat,
  Download, Send, Paperclip, Bell, FileText, AlertOctagon, Banknote,
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
  const real = payload.find((p: any) => p.dataKey === 'realizado')
  const plan = payload.find((p: any) => p.dataKey === 'planejado')
  return (
    <TooltipShell>
      <TipLabel>S-Curve · {label}</TipLabel>
      {plan && <TipRow label="Planejado" value={_fmt(plan.value)} color={COPPER} />}
      {real && <TipRow label="Realizado" value={_fmt(real.value)} color={TEAL} />}
    </TooltipShell>
  )
}

// ── Components ──────────────────────────────────────────────────────────────

function InsightCard({ insight, idx }: { insight: any; idx: number }) {
  const priorityCfg: Record<string, { label: string; border: string; badge: string; badgeText: string }> = {
    High:   { label: 'CRÍTICO', border: 'border-red-500/40',   badge: 'bg-red-500/15 text-red-400 border border-red-500/30',   badgeText: 'CRÍTICO' },
    Medium: { label: 'MÉDIO',   border: 'border-copper/40',    badge: 'bg-copper/15 text-copper border border-copper/30',       badgeText: 'MÉDIO' },
    Low:    { label: 'BAIXO',   border: 'border-teal-500/30',  badge: 'bg-teal-500/10 text-teal-400 border border-teal-500/20', badgeText: 'BAIXO' },
  }
  const cfg = priorityCfg[insight.priority] || priorityCfg.Low
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.07 }}
      className={`bg-white/[0.03] border ${cfg.border} rounded-xl p-4 flex flex-col gap-2`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-[11px] font-black uppercase text-white leading-tight flex-1">{insight.title}</span>
        <span className={`text-[8px] font-black px-2 py-0.5 rounded-full uppercase shrink-0 ${cfg.badge}`}>{cfg.badgeText}</span>
      </div>
      <p className="text-[11px] text-white/50 leading-relaxed">{insight.body}</p>
    </motion.div>
  )
}

function OverviewTab({ contrato, contratoInfo }: { contrato: string; contratoInfo?: any }) {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['hub-visao-geral', contrato],
    queryFn:  () => api.get(`/hub/visao-geral?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    enabled:  !!contrato,
  })
  const { data: insightsData, refetch: refetchInsights } = useQuery({
    queryKey: ['hub-agente-insights', contrato],
    queryFn:  () => api.get(`/hub/agente/insights?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    enabled:  !!contrato,
    staleTime: 60_000,
  })
  const [riscoOpen, setRiscoOpen] = useState(false)
  const [alertaOpen, setAlertaOpen] = useState(false)
  const [generatingInsights, setGeneratingInsights] = useState(false)

  async function handleGerarInsights() {
    setGeneratingInsights(true)
    try {
      await refetchInsights()
      await queryClient.invalidateQueries({ queryKey: ['hub-visao-geral', contrato] })
    } finally {
      setGeneratingInsights(false)
    }
  }

  if (isLoading) return <Skeleton />
  const d = data ?? {}
  // Prefer live insights from agente/insights; fallback to visao-geral embedded insights
  const insights: any[] = (insightsData?.insights?.length ? insightsData.insights : d.insights) || []

  // Coordenadas do contrato para o Windy — usa lat/lng do contrato ou default Brasil
  const windyLat = contratoInfo?.latitude ?? d.latitude ?? -15.78
  const windyLng = contratoInfo?.longitude ?? d.longitude ?? -47.93

  const desvio = d.desvio_pct ?? 0
  const desvioStr = desvio > 0 ? `+${desvio}%` : desvio < 0 ? `${desvio}%` : '0%'
  const desvioColor = desvio > 0 ? RED : desvio < 0 ? TEAL : '#888'

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
    staleTime: 30_000,
    refetchInterval: 30_000,
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
          { l: 'Progresso Global', v: `${k.progress_global || 0}%`, icon: Activity, col: COPPER },
          { l: 'Performance (SPI)', v: (k.spi || 1.0).toFixed(2), icon: TrendingUp, col: (k.spi >= 1 ? TEAL : RED) },
          { l: 'Workflow Total', v: k.total_atividades || 0, icon: List, col: '#fff' },
          { l: 'Deliveries Blue', v: k.concluidas || 0, icon: CheckCircle, col: TEAL },
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
            <AreaChart data={d.scurve}>
              <defs>
                <linearGradient id="gCopper" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={COPPER} stopOpacity={0.1}/><stop offset="95%" stopColor={COPPER} stopOpacity={0}/></linearGradient>
                <linearGradient id="gTeal" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={TEAL} stopOpacity={0.2}/><stop offset="95%" stopColor={TEAL} stopOpacity={0}/></linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="data" tick={{ fill: '#444', fontSize: 10 }} axisLine={false} />
              <YAxis tick={{ fill: '#444', fontSize: 10 }} axisLine={false} />
              <Tooltip content={<SCurveTip />} />
              <Area type="monotone" dataKey="previsto" stroke={COPPER} fill="url(#gCopper)" strokeWidth={2} />
              <Area type="monotone" dataKey="realizado" stroke={TEAL} fill="url(#gTeal)" strokeWidth={3} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartWrapper>

        <ChartWrapper title="Tendência de Performance (SPI)" icon={Activity}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={d.spi_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
              <XAxis dataKey="data" tick={{ fill: '#444', fontSize: 10 }} axisLine={false} />
              <YAxis tick={{ fill: '#444', fontSize: 10 }} axisLine={false} domain={[0.5, 1.5]} />
              <Tooltip content={<SPITip />} />
              <Line type="step" dataKey="spi" stroke={TEAL} strokeWidth={3} dot={false} />
              <ReferenceLine y={1} stroke="#666" strokeDasharray="5 5" label={{ value: '1.0', position: 'right', fill: '#444', fontSize: 10 }} />
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
              <Bar dataKey="realizado" fill={TEAL} radius={[4,4,0,0]} opacity={0.85} minPointSize={4}>
                <LabelList dataKey="realizado" position="top" style={{ fill: TEAL, fontSize: 9, fontWeight: 700 }} />
              </Bar>
              <Bar dataKey="previsto" fill={COPPER} radius={[4,4,0,0]} opacity={0.45}>
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
              <Bar dataKey="previsto" fill={COPPER} opacity={0.3} radius={[4,4,0,0]} />
              <Bar dataKey="realizado" fill={TEAL} opacity={0.8} radius={[4,4,0,0]} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartWrapper>
      </div>
    </div>
  )
}

// ── Cronograma Helpers ────────────────────────────────────────────────────────

const TENDENCIA_CONFIG: Record<string, { color: string; label: string; dot: string }> = {
  acima:    { color: '#22c55e', label: 'Acima',    dot: 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]' },
  dentro:   { color: COPPER,   label: 'No Ritmo', dot: 'bg-copper shadow-[0_0_8px_rgba(201,139,42,0.5)]' },
  abaixo:   { color: RED,      label: 'Abaixo',   dot: 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]' },
  concluida:{ color: TEAL,     label: 'Concluída',dot: 'bg-teal-500 shadow-[0_0_8px_rgba(42,157,143,0.5)]' },
  sem_dados:{ color: '#888',   label: 'Sem dados',dot: 'bg-white/20' },
}

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  concluida:    { color: TEAL,   label: 'Concluída' },
  em_andamento: { color: COPPER, label: 'Em andamento' },
  atrasada:     { color: RED,    label: 'Atrasada' },
  pendente:     { color: '#888', label: 'Pendente' },
}

function TendenciaDot({ tendencia }: { tendencia: string }) {
  const cfg = TENDENCIA_CONFIG[tendencia] || TENDENCIA_CONFIG.sem_dados
  return <div className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot}`} title={cfg.label} />
}

// KPI cards clicáveis do topo do cronograma
function CronMenuBar({ allRows, onCreateMacro, onImportIA, onRecalcular, onKpiClick }: any) {
  const total = allRows.length
  const concluidas = allRows.filter((a: any) => Number(a.conclusao_pct || 0) >= 100).length
  const criticas = allRows.filter((a: any) => String(a.critico).toLowerCase() === 'sim').length
  const progresso = useMemo(() => {
    if (!total) return 0
    const weights = allRows.reduce((s: number, a: any) => s + Number(a.peso_pct || 1), 0)
    if (!weights) return 0
    return allRows.reduce((s: number, a: any) => s + Number(a.conclusao_pct || 0) * Number(a.peso_pct || 1), 0) / weights
  }, [allRows, total])

  const kpis = [
    { id: 'total',     label: 'Total de Atividades', value: total,              color: '#fff',   icon: List },
    { id: 'concluidas',label: 'Concluídas',           value: concluidas,         color: TEAL,     icon: CheckCircle },
    { id: 'criticas',  label: 'Críticas',             value: criticas,           color: RED,      icon: AlertTriangle },
    { id: 'progresso', label: 'Progresso Geral',      value: `${progresso.toFixed(1)}%`, color: COPPER, icon: Activity },
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
function KpiDetailDialog({ type, activities, prefiltered, isOpen, onClose }: any) {
  if (!isOpen) return null
  const today = new Date().toISOString().slice(0, 10)

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
  const depTipoLabel = row.dep_tipo === 'depende_inicio' ? 'SS' : row.dep_tipo === 'depende_termino' ? 'FS' : null

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
          </div>
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
function PrevistoRealizadoSection({ allRows, onKpiClick }: { allRows: any[]; onKpiClick: (t: string, rows: any[]) => void }) {
  const today = new Date().toISOString().slice(0, 10)

  const { programadasHoje, realizadasHoje, atrasadas, emRisco, adiantadas } = useMemo(() => {
    const prog = allRows.filter((a: any) => {
      const ini = a.inicio_previsto?.slice(0, 10)
      const ter = a.termino_previsto?.slice(0, 10)
      return ini && ter && ini <= today && ter >= today
    })
    const real = prog.filter((a: any) => Number(a.conclusao_pct || 0) >= 100)
    const atras = allRows.filter((a: any) => {
      const ter = a.termino_previsto?.slice(0, 10)
      return ter && ter < today && Number(a.conclusao_pct || 0) < 100
    })
    const risco = allRows.filter((a: any) => a._tendencia === 'abaixo')
    const adiant = allRows.filter((a: any) => a._tendencia === 'acima')
    return { programadasHoje: prog, realizadasHoje: real, atrasadas: atras, emRisco: risco, adiantadas: adiant }
  }, [allRows, today])

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
function ProdutividadeSection({ allRows }: { allRows: any[] }) {
  const [filter, setFilter] = useState<'execucao' | 'concluidas' | 'previstas'>('execucao')
  const today = new Date().toISOString().slice(0, 10)

  const filtered = useMemo(() => {
    let rows = allRows
    if (filter === 'execucao') {
      rows = allRows.filter((a: any) => {
        const ini = a.inicio_previsto?.slice(0, 10)
        const ter = a.termino_previsto?.slice(0, 10)
        const pct = Number(a.conclusao_pct || 0)
        return ini && ini <= today && pct < 100 && (ter >= today || a.status === 'atrasada')
      })
    } else if (filter === 'concluidas') {
      rows = allRows.filter((a: any) => Number(a.conclusao_pct || 0) >= 100)
    } else {
      rows = allRows.filter((a: any) => {
        const ini = a.inicio_previsto?.slice(0, 10)
        return ini && ini > today
      })
    }
    return rows
  }, [allRows, filter, today])

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
              const diasPlan = Number(a.dias_planejados || 0)
              const ini = a.inicio_previsto?.slice(0, 10)
              const ter = a.termino_previsto?.slice(0, 10)
              const daysElapsed = ini ? Math.max(0, Math.ceil((new Date(today).getTime() - new Date(ini).getTime()) / 86400000)) : 0
              const dayText = ini && ter ? `Dia ${Math.min(daysElapsed + 1, diasPlan)} de ${diasPlan}` : '—'

              const totalQty = Number(a.total_qty || 0)
              const execQty = Number(a.exec_qty || 0)
              const prodPlan = diasPlan > 0 && totalQty > 0 ? totalQty / diasPlan : 0
              const prodReal = daysElapsed > 0 && execQty > 0 ? execQty / Math.max(1, daysElapsed) : 0
              const prodPct = prodPlan > 0 ? Math.round((prodReal / prodPlan) * 100) : null

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
                    {prodPct !== null ? (
                      <span style={{ color: prodPct >= 100 ? TEAL : prodPct >= 70 ? COPPER : RED, fontWeight: 700, fontSize: 10 }}>
                        {prodPct}% do planejado
                      </span>
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
    staleTime: 30_000,
    refetchInterval: 30_000,
  })

  const allRows: any[] = data?.atividades || []
  const ganttRows: any[] = data?.gantt || []

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
          {[['todas','Todos os Status'],['em_andamento','Em Andamento'],['concluida','Concluída'],['atrasada','Atrasada'],['pendente','Pendente'],['criticas','Críticas']].map(([v, l]) => (
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
            <GanttChart data={ganttRows.map((r: any) => ({
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
      <PrevistoRealizadoSection allRows={allRows} onKpiClick={(t, rows) => { setKpiDialogType(t); setKpiDialogRows(rows) }} />

      {/* 5 — Produtividade & Forecast */}
      <ProdutividadeSection allRows={allRows} />

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
  })

  const [tipo, setTipo]     = useState('Reunião')
  const [titulo, setTitulo] = useState('')
  const [descricao, setDesc] = useState('')
  const [mencoes, setMencoes] = useState('')
  const [anexo, setAnexo]   = useState<File | null>(null)
  const [filterTipo, setFilterTipo] = useState('')

  const { data: usersData } = useQuery({
    queryKey: ['hub-users'],
    queryFn: () => api.get('/users').then(r => r.data),
    staleTime: 300_000,
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
        const r = await api.post('/hub/timeline/upload', fd)
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

function FinanceiroTab({ contrato }: { contrato: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['hub-financeiro', contrato],
    queryFn:  () => api.get(`/hub/financeira?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    enabled:  !!contrato,
  })

  if (isLoading) return <Skeleton />
  const d = data || {}

  return (
    <div className="flex flex-col gap-8 animate-enter">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="bg-void/40 border border-white/5 p-6 rounded-2xl">
          <div className="text-[10px] text-text-muted uppercase font-black tracking-widest mb-2">Budget Planejado</div>
          <div className="text-xl font-bold font-display text-white">{_fmt(d.budget_planejado)}</div>
        </div>
        <div className="bg-void/40 border border-white/5 p-6 rounded-2xl">
          <div className="text-[10px] text-text-muted uppercase font-black tracking-widest mb-2">Budget Executado</div>
          <div className="text-xl font-bold font-display text-patina">{_fmt(d.budget_realizado)}</div>
        </div>
        <div className="bg-void/40 border border-white/5 p-6 rounded-2xl">
          <div className="text-[10px] text-text-muted uppercase font-black tracking-widest mb-2">Saldo Remanescente</div>
          <div className="text-xl font-bold font-display text-copper">{_fmt(d.saldo)}</div>
        </div>
        <div className="bg-void/40 border border-white/5 p-6 rounded-2xl">
          <div className="text-[10px] text-text-muted uppercase font-black tracking-widest mb-2">Índice CPI</div>
          <div className="text-xl font-bold font-display text-blue-400">{d.cpi}</div>
          <div className="text-[9px] text-text-muted uppercase mt-1">Cost Performance Index</div>
        </div>
      </div>

      <div className="bg-void/40 border border-white/5 p-8 rounded-3xl">
        <div className="flex items-center gap-2 mb-8">
           <Wallet size={16} className="text-copper" />
           <h3 className="text-xs font-black uppercase tracking-widest text-white">S-Curve Financeira — Fluxo de Desembolso</h3>
        </div>
        <div className="h-[350px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={d.series}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="mes" stroke="#666" fontSize={10} axisLine={false} />
              <YAxis stroke="#666" fontSize={10} axisLine={false} />
              <Tooltip content={<SCurveFinTip />} />
              <Bar dataKey="realizado" fill={TEAL} radius={[4, 4, 0, 0]} />
              <Line type="monotone" dataKey="planejado" stroke={COPPER} strokeWidth={3} dot={{ r: 4, fill: COPPER }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="flex flex-col gap-4 animate-pulse">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4"><div className="h-24 bg-white/5 rounded-xl"/><div className="h-24 bg-white/5 rounded-xl"/><div className="h-24 bg-white/5 rounded-xl"/><div className="h-24 bg-white/5 rounded-xl"/></div>
      <div className="h-64 bg-white/5 rounded-xl" />
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function HubOperacoes({ hubTab, onHubTabChange }: any) {
  const [searchParams, setSearchParams] = useSearchParams()
  const contrato = searchParams.get('contrato') ?? ''
  const activeTab = hubTab || searchParams.get('tab') || 'visao_geral'

  const { data: contratosList } = useQuery({
    queryKey: ['hub-contratos'],
    queryFn:  () => api.get('/hub/contratos').then(r => r.data),
    staleTime: 60_000,
  })

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
              const desvioColor = desvio > 0 ? RED : desvio < 0 ? TEAL : '#888'
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
                  onClick={() => setSearchParams({ contrato: c.contrato })}
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
