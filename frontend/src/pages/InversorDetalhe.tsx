import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  ComposedChart, ScatterChart, Scatter, ZAxis,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine, Legend,
} from 'recharts'
import {
  ArrowLeft, Zap, Sun, Thermometer, Battery, Activity,
  Wifi, RefreshCw, LayoutDashboard, BarChart2, Wallet,
  Settings, Plus, Trash2, Loader2, AlertTriangle, X,
  TrendingUp, ChevronDown, Wind, Radio, Wrench,
  CheckCircle2, Clock, CircleDot, Ban,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import './Dashboard.css'
import api from '@/services/api'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const BLUE   = '#3B82F6'
const RED    = '#EF4444'

function _fv(v: number | null | undefined, decimals = 1): string {
  if (v === null || v === undefined) return '—'
  return v.toFixed(decimals)
}

function _kwh(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  if (v >= 1000) return `${(v / 1000).toFixed(2)} MWh`
  return `${v.toFixed(1)} kWh`
}

const TABS = [
  { id: 'visao_geral',  label: 'Visão Geral',  icon: LayoutDashboard },
  { id: 'dashboard',    label: 'Dashboard',    icon: BarChart2 },
  { id: 'strings',      label: 'Strings DC',   icon: Zap },
  { id: 'analise',      label: 'Análise',      icon: TrendingUp },
  { id: 'financeiro',   label: 'Financeiro',   icon: Wallet },
  { id: 'manual',       label: 'Lançamentos',  icon: Plus },
  { id: 'manutencao',   label: 'Manutenção',   icon: Wrench },
  { id: 'config',       label: 'Configuração', icon: Settings },
]

export default function InversorDetalhe() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [tab, setTab] = useState('visao_geral')
  const [showManualForm, setShowManualForm] = useState(false)
  const [manualForm, setManualForm] = useState<Record<string, any>>({})

  const { data, isLoading, isError } = useQuery({
    queryKey: ['inversor', id],
    queryFn: () => api.get(`/inversores/${id}`).then(r => r.data),
    enabled: !!id,
    refetchInterval: 120_000,
  })

  const { data: readingsData } = useQuery({
    queryKey: ['inversor-readings', id],
    queryFn: () => api.get(`/inversores/${id}/readings`, { params: { limit: 500, order: 'asc' } }).then(r => r.data),
    enabled: !!id,
  })

  const { data: perfData } = useQuery({
    queryKey: ['inversor-performance', id],
    queryFn: () => api.get(`/inversores/${id}/performance`).then(r => r.data),
    enabled: !!id,
    refetchInterval: 300_000,
    staleTime: 60_000,
  })

  const { data: prHistory } = useQuery({
    queryKey: ['inversor-pr-history', id],
    queryFn: () => api.get(`/inversores/${id}/pr-history`, { params: { days: 30 } }).then(r => r.data),
    enabled: !!id,
    staleTime: 30 * 60_000,   // irradiância histórica não muda — cache 30 min
    refetchInterval: 60 * 60_000,
  })

  const { data: alertsData, refetch: refetchAlerts } = useQuery({
    queryKey: ['inversor-alerts', id],
    // status=all para que a timeline veja alertas resolvidos; open_count/critical_count são calculados server-side
    queryFn: () => api.get(`/inversores/${id}/alerts`, { params: { status: 'all', limit: 100 } }).then(r => r.data),
    enabled: !!id,
    refetchInterval: 120_000,
  })

  const resolveAlertMut = useMutation({
    mutationFn: (alertId: string) =>
      api.patch(`/inversores/${id}/alerts/${alertId}/resolve`).then(r => r.data),
    onSuccess: () => refetchAlerts(),
  })

  const muteAlertMut = useMutation({
    mutationFn: ({ alertId, hours }: { alertId: string; hours: number }) =>
      api.patch(`/inversores/${id}/alerts/${alertId}/mute`, null, { params: { hours } }).then(r => r.data),
    onSuccess: () => refetchAlerts(),
  })

  const syncMut = useMutation({
    mutationFn: () => api.post(`/inversores/${id}/sync`).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inversor', id] })
      qc.invalidateQueries({ queryKey: ['inversor-readings', id] })
    },
  })

  const { data: backfillStatus, refetch: refetchBackfill } = useQuery({
    queryKey: ['inversor-backfill-status', id],
    queryFn: () => api.get(`/inversores/${id}/backfill-status`).then(r => r.data),
    enabled: !!id && tab === 'config',
    refetchInterval: (query) =>
      query.state.data?.status === 'running' ? 3_000 : false,
  })

  const backfillMut = useMutation({
    mutationFn: ({ months, phase }: { months: number; phase: string }) =>
      api.post(`/inversores/${id}/backfill`, null, { params: { months, phase } }).then(r => r.data),
    onSuccess: () => refetchBackfill(),
  })

  const { data: maintenanceData, refetch: refetchMaintenance } = useQuery({
    queryKey: ['inversor-maintenance', id],
    queryFn: () => api.get('/maintenance', { params: { inverter_id: id, limit: 200 } }).then(r => r.data),
    enabled: !!id && tab === 'manutencao',
    refetchInterval: 60_000,
  })

  const createTaskMut = useMutation({
    mutationFn: (body: any) => api.post('/maintenance', body).then(r => r.data),
    onSuccess: () => { refetchMaintenance(); qc.invalidateQueries({ queryKey: ['inversor-maintenance-count', id] }) },
  })

  const updateTaskMut = useMutation({
    mutationFn: ({ taskId, patch }: { taskId: string; patch: any; onSuccess?: () => void }) =>
      api.patch(`/maintenance/${taskId}`, patch).then(r => r.data),
    onSuccess: (_data, vars) => {
      refetchMaintenance()
      qc.invalidateQueries({ queryKey: ['inversor-maintenance-count', id] })
      vars.onSuccess?.()
    },
  })

  const deleteTaskMut = useMutation({
    mutationFn: (taskId: string) => api.delete(`/maintenance/${taskId}`),
    onSuccess: () => { refetchMaintenance(); qc.invalidateQueries({ queryKey: ['inversor-maintenance-count', id] }) },
  })

  const { data: maintenanceCount } = useQuery({
    queryKey: ['inversor-maintenance-count', id],
    queryFn: () => api.get(`/maintenance/inversor/${id}/open-count`).then(r => r.data),
    enabled: !!id,
    refetchInterval: 120_000,
  })

  const manualMut = useMutation({
    mutationFn: (body: any) => api.post(`/inversores/${id}/readings`, body).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inversor-readings', id] })
      setShowManualForm(false)
      setManualForm({})
    },
  })

  const inv = data?.inversor
  const latest = data?.latest
  const serieMensal: any[] = data?.serie_mensal ?? []
  const readings: any[] = readingsData?.readings ?? []
  const serieDiaria: any[] = readingsData?.serie_diaria ?? []
  const caps = inv?.capabilities || {}

  if (isLoading) return (
    <div className="flex items-center justify-center h-80">
      <Loader2 size={28} className="animate-spin text-copper" />
    </div>
  )

  if (isError || !inv) return (
    <div className="flex flex-col items-center justify-center h-80 gap-4">
      <AlertTriangle size={32} className="text-red-400" />
      <p className="text-white/40 font-bold">Inversor não encontrado</p>
      <Button onClick={() => navigate('/inversores')} variant="outline" className="border-white/10 text-white/40">
        Voltar
      </Button>
    </div>
  )

  const openTaskCount = maintenanceCount?.open_count ?? 0

  const visibleTabs = TABS.filter(t => {
    if (t.id === 'strings' && !caps.dc_strings) return false
    if (t.id === 'manual' && inv.mode !== 'manual') return false
    if (t.id === 'analise' && inv.mode !== 'api') return false
    return true
  })

  return (
    <div className="flex flex-col gap-6 animate-enter">
      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/inversores')}
            className="p-2 hover:bg-white/5 rounded-xl text-white/30 hover:text-white transition-all"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-8 w-px bg-white/5" />
          <div>
            <h1 className="font-display text-xl font-black text-white uppercase tracking-tight">
              {inv.alias}
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-[9px] text-white/30 font-bold uppercase tracking-widest">
                {inv.platform_name}
              </span>
              {inv.sn && (
                <>
                  <span className="text-white/10">·</span>
                  <span className="text-[9px] font-mono text-white/20">{inv.sn}</span>
                </>
              )}
              {inv.location && (
                <>
                  <span className="text-white/10">·</span>
                  <span className="text-[9px] text-white/30">{inv.location}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <StatusChip status={latest?.status || inv.status} />
          {inv.mode === 'api' && (
            <Button
              onClick={() => syncMut.mutate()}
              disabled={syncMut.isPending}
              className="bg-copper/10 hover:bg-copper/20 text-copper border border-copper/20 font-black text-[9px] uppercase tracking-widest h-9 gap-2"
            >
              <RefreshCw size={13} className={syncMut.isPending ? 'animate-spin' : ''} />
              {syncMut.isPending ? 'Sincronizando...' : 'Sincronizar'}
            </Button>
          )}
          {inv.mode === 'manual' && (
            <Button
              onClick={() => setShowManualForm(true)}
              className="bg-copper text-void font-black text-[9px] uppercase tracking-widest h-9 gap-2"
            >
              <Plus size={13} /> Novo Lançamento
            </Button>
          )}
        </div>
      </div>

      {/* ── Alert banner ────────────────────────────────────────────────── */}
      {alertsData?.open_count > 0 && (
        <AlertBanner
          alerts={alertsData.alerts.filter((a: any) => a.status === 'open')}
          onResolve={(id: string) => resolveAlertMut.mutate(id)}
          onMute={(id: string) => muteAlertMut.mutate({ alertId: id, hours: 24 })}
        />
      )}

      {/* ── Tabs ────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-1 overflow-x-auto no-scrollbar border-b border-white/[0.04] pb-0">
        {visibleTabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`relative flex items-center gap-2 px-4 py-3 text-[10px] font-black uppercase tracking-widest whitespace-nowrap transition-all border-b-2 -mb-px ${
              tab === t.id
                ? 'text-copper border-copper'
                : 'text-white/30 border-transparent hover:text-white/50'
            }`}
          >
            <t.icon size={13} />
            {t.label}
            {t.id === 'manutencao' && openTaskCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-amber-500 text-void text-[8px] font-black flex items-center justify-center">
                {openTaskCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tab content ─────────────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
        >
          {tab === 'visao_geral' && <TabVisaoGeral inv={inv} latest={latest} serieMensal={serieMensal} caps={caps} perf={perfData} readings={readings} alerts={alertsData?.alerts ?? []} />}
          {tab === 'dashboard'   && <TabDashboard readings={readings} serieDiaria={serieDiaria} caps={caps} latest={latest} perf={perfData} />}
          {tab === 'analise'     && <TabAnalise inv={inv} latest={latest} readings={readings} prHistory={prHistory} caps={caps} />}
          {tab === 'strings'     && <TabStrings readings={readings} caps={caps} latest={latest} />}
          {tab === 'financeiro'  && <TabFinanceiro inv={inv} serieMensal={serieMensal} />}
          {tab === 'manual'      && (
            <TabManual
              readings={readings}
              showForm={showManualForm}
              setShowForm={setShowManualForm}
              form={manualForm}
              setForm={setManualForm}
              onSave={() => manualMut.mutate(manualForm)}
              saving={manualMut.isPending}
              caps={caps}
            />
          )}
          {tab === 'manutencao'  && (
            <TabManutencao
              tasks={maintenanceData ?? []}
              onCreate={(body: any) => createTaskMut.mutate({ ...body, inverter_id: id })}
              onUpdate={(taskId: string, patch: any, onSuccess?: () => void) => updateTaskMut.mutate({ taskId, patch, onSuccess })}
              onDelete={(taskId: string) => deleteTaskMut.mutate(taskId)}
              saving={createTaskMut.isPending || updateTaskMut.isPending}
            />
          )}
          {tab === 'config'      && (
            <TabConfig
              inv={inv} caps={caps}
              onUpdate={() => qc.invalidateQueries({ queryKey: ['inversor', id] })}
              backfillStatus={backfillStatus}
              onBackfill={(months: number, phase: string) => backfillMut.mutate({ months, phase })}
              backfillPending={backfillMut.isPending}
            />
          )}
        </motion.div>
      </AnimatePresence>

      {/* ── Quick manual form (fab) ─────────────────────────────────────── */}
      <AnimatePresence>
        {showManualForm && inv.mode !== 'manual' && (
          <QuickManualForm
            caps={caps}
            form={manualForm}
            setForm={setManualForm}
            onSave={() => manualMut.mutate(manualForm)}
            onClose={() => setShowManualForm(false)}
            saving={manualMut.isPending}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Tab: Visão Geral ──────────────────────────────────────────────────────────

const STATUS_PR: Record<string, { label: string; color: string; dot: string }> = {
  normal:       { label: 'Normal',       color: '#22C55E', dot: 'bg-green-500' },
  atencao:      { label: 'Atenção',      color: '#F59E0B', dot: 'bg-amber-400' },
  critico:      { label: 'Crítico',      color: '#EF4444', dot: 'bg-red-500' },
  sem_dados:    { label: 'Sem dados',    color: '#6B7280', dot: 'bg-gray-500' },
  sem_geracao:  { label: 'Sem geração',  color: '#6B7280', dot: 'bg-gray-500' },
}

function buildPrevistoCurve(ePrevista: number, dateStr: string): { time: string; previsto: number }[] {
  // Synthetic bell curve (sine profile) from 06:00 to 18:00 local time
  const pts: { time: string; previsto: number }[] = []
  for (let h = 6; h <= 18; h += 0.5) {
    const hh = Math.floor(h)
    const mm = h % 1 === 0.5 ? '30' : '00'
    const t = `${String(hh).padStart(2, '0')}:${mm}`
    // cumulative fraction of sine bell: (1 - cos(π(h-6)/12)) / 2
    const frac = (1 - Math.cos(Math.PI * (h - 6) / 12)) / 2
    pts.push({ time: t, previsto: Math.round(ePrevista * frac * 10) / 10 })
  }
  return pts
}

const ALERT_SEVERITY: Record<string, { bg: string; border: string; icon: string; text: string }> = {
  critical: { bg: 'bg-red-950/60',    border: 'border-red-500/30',    icon: 'text-red-400',    text: 'text-red-300' },
  warning:  { bg: 'bg-amber-950/40',  border: 'border-amber-500/20',  icon: 'text-amber-400',  text: 'text-amber-300' },
  info:     { bg: 'bg-blue-950/40',   border: 'border-blue-500/20',   icon: 'text-blue-400',   text: 'text-blue-300' },
}

function AlertBanner({ alerts, onResolve, onMute }: { alerts: any[]; onResolve: (id: string) => void; onMute: (id: string) => void }) {
  const sorted = [...alerts].sort((a, b) =>
    (b.severity === 'critical' ? 1 : 0) - (a.severity === 'critical' ? 1 : 0)
  )
  return (
    <div className="flex flex-col gap-2">
      {sorted.map((alert: any) => {
        const s = ALERT_SEVERITY[alert.severity] ?? ALERT_SEVERITY.warning
        return (
          <div key={alert.id} className={`flex items-start justify-between gap-3 px-4 py-3 rounded-xl border ${s.bg} ${s.border}`}>
            <div className="flex items-start gap-3 min-w-0">
              <AlertTriangle size={14} className={`${s.icon} mt-0.5 shrink-0`} />
              <div className="min-w-0">
                <p className={`text-xs font-black ${s.text}`}>{alert.title}</p>
                {alert.detail && <p className="text-[10px] text-white/40 mt-0.5 leading-relaxed">{alert.detail}</p>}
              </div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                onClick={() => onMute(alert.id)}
                className="px-2 py-1 rounded text-[9px] font-black uppercase tracking-widest text-white/30 hover:text-white/60 hover:bg-white/5 transition-all"
                title="Silenciar 24h"
              >
                24h
              </button>
              <button
                onClick={() => onResolve(alert.id)}
                className="p-1.5 rounded hover:bg-white/10 text-white/30 hover:text-white/60 transition-all"
                title="Marcar como resolvido"
              >
                <X size={12} />
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function EventTimeline({ readings, alerts }: { readings: any[]; alerts: any[] }) {
  const events = useMemo(() => {
    const syncEvents = (readings as any[]).slice(0, 30).map(r => ({
      ts:       r.ts,
      type:     'sync' as const,
      label:    r.active_power_w != null
        ? `${(r.active_power_w / 1000).toFixed(2)} kW · ${r.energy_today_kwh?.toFixed(2) ?? '—'} kWh acum.`
        : 'Sync sem dados de potência',
    }))

    const alertOpen = (alerts as any[])
      .filter(a => a.opened_at)
      .map(a => ({
        ts:       a.opened_at,
        type:     'alert_open' as const,
        severity: a.severity as string,
        label:    a.title,
      }))

    const alertResolved = (alerts as any[])
      .filter(a => a.resolved_at)
      .map(a => ({
        ts:       a.resolved_at,
        type:     'alert_resolved' as const,
        severity: a.severity as string,
        label:    `Resolvido: ${a.title}`,
      }))

    return [...syncEvents, ...alertOpen, ...alertResolved]
      .sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime())
      .slice(0, 18)
  }, [readings, alerts])

  if (events.length === 0) return null

  return (
    <div className="glass-panel p-6 border-white/5">
      <h3 className="text-xs font-black uppercase tracking-widest text-white/40 mb-4">Timeline de Eventos</h3>
      <div className="relative">
        <div className="absolute left-[5px] top-2 bottom-2 w-px bg-white/[0.04]" />
        <div className="flex flex-col gap-0">
          {events.map((ev, i) => {
            const dotColor = ev.type === 'alert_open'
              ? ev.severity === 'critical' ? 'bg-red-400' : 'bg-amber-400'
              : ev.type === 'alert_resolved'
              ? 'bg-teal-400'
              : 'bg-white/20'
            const textColor = ev.type === 'alert_open'
              ? ev.severity === 'critical' ? 'text-red-300' : 'text-amber-300'
              : ev.type === 'alert_resolved'
              ? 'text-teal-400/70'
              : 'text-white/50'

            const d = new Date(ev.ts)
            const timeLabel = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
            const dateLabel = d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
            const isToday = d.toDateString() === new Date().toDateString()

            return (
              <div key={i} className="flex items-start gap-4 pl-1 py-2 group">
                <div className={`w-2.5 h-2.5 rounded-full shrink-0 mt-0.5 ${dotColor} relative z-10`} />
                <div className="flex-1 min-w-0">
                  <p className={`text-[10px] font-bold leading-tight ${textColor}`}>{ev.label}</p>
                </div>
                <div className="text-[9px] text-white/20 font-bold tabular-nums shrink-0">
                  {isToday ? timeLabel : `${dateLabel} ${timeLabel}`}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function TabVisaoGeral({ inv, latest, serieMensal, caps, perf, readings, alerts }: any) {
  const prStatus = perf?.status ? STATUS_PR[perf.status] ?? STATUS_PR.sem_dados : null
  const hasPerf = perf?.pr !== null && perf?.pr !== undefined

  // Build Real vs Previsto chart data
  const todayStr = new Date().toDateString()
  const todayReadings = (readings as any[])?.filter(r => new Date(r.ts).toDateString() === todayStr) ?? []
  const chartData = useMemo(() => {
    if (!perf?.e_prevista_kwh || todayReadings.length === 0) return []
    const previstoCurve = buildPrevistoCurve(perf.e_prevista_kwh, '')
    const prevMap: Record<string, number> = {}
    previstoCurve.forEach(p => { prevMap[p.time] = p.previsto })

    const realPts = todayReadings.map((r: any) => {
      const d = new Date(r.ts)
      const h = d.getHours()
      const m = d.getMinutes()
      // nearest 30-min slot for previsto lookup
      const slot = `${String(h).padStart(2,'0')}:${m < 30 ? '00' : '30'}`
      return {
        time: `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`,
        real: r.energy_today_kwh != null ? Math.round(r.energy_today_kwh * 10) / 10 : null,
        previsto: prevMap[slot] ?? null,
      }
    })
    return realPts
  }, [perf?.e_prevista_kwh, todayReadings.length])

  const kpis = [
    { label: 'Potência Agora', value: latest ? `${_fv(latest.active_power_w, 0)} W` : '—', icon: Zap, color: COPPER, sub: 'em tempo real' },
    { label: 'Geração Hoje', value: latest ? _kwh(latest.energy_today_kwh) : '—', icon: Sun, color: TEAL, sub: 'gerado no dia' },
    { label: 'Geração Total', value: latest ? _kwh(latest.energy_total_kwh) : '—', icon: TrendingUp, color: COPPER, sub: 'histórico acumulado' },
    { label: 'Capacidade', value: `${inv.nominal_power_kw} kWp`, icon: Activity, color: TEAL, sub: 'instalado' },
  ]

  if (caps.has_temperature && latest?.temp_inverter_c !== null && latest?.temp_inverter_c !== undefined) {
    kpis.push({ label: 'Temperatura', value: `${_fv(latest.temp_inverter_c)}°C`, icon: Thermometer, color: COPPER, sub: 'inversor' })
  }
  if (latest?.grid_frequency_hz) {
    kpis.push({ label: 'Frequência', value: `${_fv(latest.grid_frequency_hz, 2)} Hz`, icon: Radio, color: TEAL, sub: 'rede elétrica' })
  }

  return (
    <div className="flex flex-col gap-6">
      {/* KPI grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {kpis.map((k, i) => (
          <div key={i} className="glass-panel p-4 border-white/5 hover:border-white/10 transition-all group">
            <div className="flex items-center justify-between mb-3">
              <k.icon size={15} style={{ color: k.color }} />
              <div className="w-1 h-1 rounded-full" style={{ background: k.color }} />
            </div>
            <div className="text-[9px] text-text-muted uppercase font-black tracking-widest mb-1">{k.label}</div>
            <div className="text-lg font-black text-white">{k.value}</div>
            <div className="text-[9px] text-white/20 mt-0.5">{k.sub}</div>
          </div>
        ))}
      </div>

      {/* Performance block — PR, Previsto, Perda */}
      {perf && (
        <div className="glass-panel p-5 border-white/5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-xs font-black uppercase tracking-widest text-copper">Performance de Hoje</h3>
              <p className="text-[9px] text-white/30 mt-0.5">
                Irradiância via {perf.irradiance?.source === 'nasa_power' ? 'NASA POWER' : perf.irradiance?.source === 'open_meteo' ? 'Open-Meteo' : '—'}
                {perf.irradiance?.irradiance_kwh_m2 ? ` · ${perf.irradiance.irradiance_kwh_m2} kWh/m²` : ''}
                {perf.irradiance?.is_forecast && ' · previsão (não medido)'}
              </p>
            </div>
            {prStatus && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border"
                style={{ borderColor: prStatus.color + '40', background: prStatus.color + '12' }}>
                <div className={`w-1.5 h-1.5 rounded-full`} style={{ background: prStatus.color }} />
                <span className="text-[9px] font-black uppercase tracking-widest" style={{ color: prStatus.color }}>
                  {prStatus.label}
                </span>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {/* PR */}
            <div className="flex flex-col gap-1">
              <span className="text-[9px] text-white/30 font-black uppercase tracking-widest">PR</span>
              <span className="text-2xl font-black" style={{ color: prStatus?.color ?? '#6B7280' }}>
                {hasPerf ? perf.pr.toFixed(2) : '—'}
              </span>
              <span className="text-[9px] text-white/20">Performance Ratio</span>
            </div>

            {/* E_prevista */}
            <div className="flex flex-col gap-1">
              <span className="text-[9px] text-white/30 font-black uppercase tracking-widest">Previsto</span>
              <span className="text-2xl font-black text-white/60">
                {perf.e_prevista_kwh != null ? `${perf.e_prevista_kwh.toFixed(1)}` : '—'}
              </span>
              <span className="text-[9px] text-white/20">kWh esperados</span>
            </div>

            {/* Desvio */}
            <div className="flex flex-col gap-1">
              <span className="text-[9px] text-white/30 font-black uppercase tracking-widest">Desvio</span>
              <span className={`text-2xl font-black ${
                perf.desvio_pct == null ? 'text-white/30'
                : perf.desvio_pct >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {perf.desvio_pct != null ? `${perf.desvio_pct > 0 ? '+' : ''}${perf.desvio_pct.toFixed(1)}%` : '—'}
              </span>
              <span className="text-[9px] text-white/20">real vs previsto</span>
            </div>

            {/* Perda financeira */}
            <div className="flex flex-col gap-1">
              <span className="text-[9px] text-white/30 font-black uppercase tracking-widest">Perda</span>
              <span className={`text-2xl font-black ${perf.perda_rs ? 'text-red-400' : 'text-white/30'}`}>
                {perf.perda_rs != null ? `R$ ${perf.perda_rs.toFixed(2)}` : '—'}
              </span>
              <span className="text-[9px] text-white/20">não gerado hoje</span>
            </div>
          </div>

          {!perf.irradiance?.available && (
            <p className="text-[9px] text-white/20 mt-3">
              {perf.irradiance?.reason === 'coords_pending'
                ? 'Coordenadas pendentes — configure a localização para habilitar PR.'
                : 'Dados de irradiância indisponíveis para esta data.'}
            </p>
          )}
          {perf.irradiance?.available && perf.irradiance?.is_forecast && (
            <p className="text-[9px] text-amber-400/50 mt-3">
              Irradiância baseada em previsão meteorológica — PR revisado ao final do dia com dados medidos.
            </p>
          )}
        </div>
      )}

      {/* Real vs Previsto chart */}
      {chartData.length > 1 && perf?.e_prevista_kwh && (
        <div className="glass-panel p-6 border-white/5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-xs font-black uppercase tracking-widest text-copper">Real vs Previsto — Hoje</h3>
              <p className="text-[9px] text-white/30 mt-0.5">
                Energia acumulada no dia (kWh) · curva prevista = perfil senoidal × {perf.e_prevista_kwh.toFixed(1)} kWh
              </p>
            </div>
            <div className="flex items-center gap-4 text-[9px] font-bold">
              <span className="flex items-center gap-1.5 text-teal-400"><span className="w-3 h-0.5 rounded bg-teal-400 inline-block"/>{perf.e_real_kwh?.toFixed(1)} kWh real</span>
              <span className="flex items-center gap-1.5 text-white/30"><span className="w-3 h-0.5 rounded bg-white/20 inline-block border-dashed"/>{perf.e_prevista_kwh?.toFixed(1)} kWh prev.</span>
            </div>
          </div>
          <div className="h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradReal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={TEAL} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={TEAL} stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="gradPrev" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#fff" stopOpacity={0.05} />
                    <stop offset="95%" stopColor="#fff" stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="time" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9, fontWeight: 700 }}
                  interval="preserveStartEnd" />
                <YAxis axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9 }}
                  tickFormatter={v => `${v}`} unit=" kWh" width={52} />
                <Tooltip
                  contentStyle={{ background: '#0D1117', border: `1px solid ${TEAL}40`, borderRadius: 12, padding: 12 }}
                  formatter={(v: any, name: string) => [
                    `${Number(v).toFixed(1)} kWh`,
                    name === 'real' ? 'Real' : 'Previsto'
                  ]}
                />
                <Area type="monotone" dataKey="previsto" stroke="rgba(255,255,255,0.15)"
                  strokeWidth={1.5} strokeDasharray="4 3" fill="url(#gradPrev)" name="previsto" connectNulls />
                <Area type="monotone" dataKey="real" stroke={TEAL}
                  strokeWidth={2} fill="url(#gradReal)" name="real" connectNulls dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Monthly chart */}
      <div className="glass-panel p-6 border-white/5">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xs font-black uppercase tracking-widest text-copper">Geração Acumulada Mensal</h3>
            <p className="text-[9px] text-white/30 mt-1">Energia gerada por mês (kWh)</p>
          </div>
          <div className="text-[9px] text-white/20 font-bold uppercase">
            {serieMensal.length} meses de histórico
          </div>
        </div>
        {serieMensal.length > 0 ? (
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={serieMensal} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="month" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9, fontWeight: 700 }} />
                <YAxis axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }}
                  tickFormatter={v => `${v} kWh`} />
                <Tooltip
                  contentStyle={{ background: '#0D1117', border: `1px solid ${COPPER}40`, borderRadius: 12, padding: 12 }}
                  formatter={(v: any) => [`${Number(v).toFixed(1)} kWh`, 'Geração']}
                />
                <Bar dataKey="energy_kwh" fill={TEAL} radius={[4, 4, 0, 0]} name="Geração (kWh)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-[120px] flex items-center justify-center">
            <p className="text-xs text-white/20 font-bold">Sem dados históricos ainda. Sincronize para começar.</p>
          </div>
        )}
      </div>

      {/* Event timeline */}
      <EventTimeline readings={readings} alerts={alerts} />

      {/* Device info card */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="glass-panel p-5 border-white/5">
          <h3 className="text-[10px] font-black uppercase tracking-widest text-white/40 mb-4">Informações do Dispositivo</h3>
          <div className="space-y-3">
            {[
              { label: 'Plataforma', value: inv.platform_name },
              { label: 'Número de Série', value: inv.sn || '—' },
              { label: 'Datalogger PN', value: inv.pn || '—' },
              { label: 'Devcode', value: inv.devcode || '—' },
              { label: 'Plant ID', value: inv.plant_id || '—' },
              { label: 'Instalação', value: inv.install_date || '—' },
              { label: 'Última Sync', value: inv.last_sync_at ? new Date(inv.last_sync_at).toLocaleString('pt-BR') : '—' },
            ].map(row => (
              <div key={row.label} className="flex items-center justify-between py-2 border-b border-white/[0.03]">
                <span className="text-[10px] text-white/30 font-bold uppercase tracking-widest">{row.label}</span>
                <span className="text-xs font-mono text-white/70">{row.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-panel p-5 border-white/5">
          <h3 className="text-[10px] font-black uppercase tracking-widest text-white/40 mb-4">Capacidades do Sistema</h3>
          <div className="space-y-3">
            {[
              { label: 'Strings DC', value: caps.dc_strings ? `${caps.dc_strings} strings` : 'Não disponível' },
              { label: 'Fases CA', value: caps.phases === 3 ? 'Trifásico (3φ)' : caps.phases === 1 ? 'Monofásico (1φ)' : '—' },
              { label: 'Temperatura', value: caps.has_temperature ? 'Disponível' : 'Não disponível' },
              { label: 'Bateria/Armazenamento', value: caps.has_battery ? 'Disponível' : 'Não disponível' },
              { label: 'Histórico', value: caps.has_history ? 'Disponível' : 'Não disponível' },
              { label: 'Modo de Alimentação', value: inv.mode === 'api' ? 'API Automática' : 'Manual' },
            ].map(row => (
              <div key={row.label} className="flex items-center justify-between py-2 border-b border-white/[0.03]">
                <span className="text-[10px] text-white/30 font-bold uppercase tracking-widest">{row.label}</span>
                <span className={`text-xs font-bold ${row.value.includes('Disponível') || row.value.includes('API') ? 'text-teal-400' : 'text-white/40'}`}>
                  {row.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Shared: power previsto helper ────────────────────────────────────────────

function _previstoW(timeStr: string, ePrevistaKwh: number): number | null {
  const parts = timeStr.split(':')
  if (parts.length < 2) return null
  const t = parseInt(parts[0]) + parseInt(parts[1]) / 60
  if (t < 6 || t > 18) return null
  const pPicoW = ePrevistaKwh * Math.PI * 1000 / 24
  return Math.round(pPicoW * Math.sin(Math.PI * (t - 6) / 12))
}

// ── Shared: rich tooltip ─────────────────────────────────────────────────────

function PowerTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload ?? {}
  return (
    <div className="glass-panel px-3.5 py-3 border-white/10 min-w-[170px] text-[10px]">
      <p className="text-[9px] text-white/30 font-black uppercase tracking-widest mb-2.5">{label}</p>
      {d.power_w != null && (
        <div className="flex justify-between gap-4 mb-1">
          <span className="text-white/40">Potência real</span>
          <span className="font-black" style={{ color: COPPER }}>{d.power_w.toFixed(0)} W</span>
        </div>
      )}
      {d.power_prev != null && (
        <div className="flex justify-between gap-4 mb-1">
          <span className="text-white/40">Previsto</span>
          <span className="font-black text-white/30">{d.power_prev.toFixed(0)} W</span>
        </div>
      )}
      {d.energy != null && (
        <div className="flex justify-between gap-4 mb-1">
          <span className="text-white/40">Acum. hoje</span>
          <span className="font-black" style={{ color: TEAL }}>{d.energy.toFixed(2)} kWh</span>
        </div>
      )}
      {d.temp != null && (
        <div className="flex justify-between gap-4">
          <span className="text-white/40">Temperatura</span>
          <span className="font-black text-amber-400">{d.temp.toFixed(1)}°C</span>
        </div>
      )}
    </div>
  )
}

// ── Tab: Dashboard ────────────────────────────────────────────────────────────

// ── Tab: Análise (Sprint 5) ──────────────────────────────────────────────────

const PR_THRESHOLDS = [
  { value: 0.85, label: 'Normal', color: '#22D3EE' },
  { value: 0.70, label: 'Atenção', color: '#FBBF24' },
]

function _csvDownload(rows: any[], filename: string) {
  const header = Object.keys(rows[0] ?? {}).join(',')
  const body = rows.map(r => Object.values(r).join(',')).join('\n')
  const blob = new Blob([`${header}\n${body}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

function TabAnalise({ inv, latest, readings, prHistory, caps }: any) {
  const kWp = inv.nominal_power_kw ?? 0
  const installDate = inv.install_date ? new Date(inv.install_date) : null
  const hoursOp = installDate
    ? (Date.now() - installDate.getTime()) / 3_600_000
    : null

  // Specific Yield: kWh gerado por kWp instalado
  const specificYield = (latest?.energy_total_kwh && kWp)
    ? Math.round(latest.energy_total_kwh / kWp)
    : null

  // Capacity Factor: E_total / (kWp × horas_operando)
  const capacityFactor = (latest?.energy_total_kwh && kWp && hoursOp && hoursOp > 0)
    ? round3(latest.energy_total_kwh / (kWp * hoursOp))
    : null

  // Temp vs Power scatter data
  const scatterData = useMemo(() =>
    (readings as any[])
      .filter(r => r.temp_inverter_c != null && r.active_power_w != null && r.active_power_w > 50)
      .map(r => ({ x: r.temp_inverter_c, y: Math.round(r.active_power_w / 100) / 10 }))
      .slice(-300),
    [readings]
  )

  const prDays = prHistory?.days ?? []
  const summary = prHistory?.summary ?? {}

  return (
    <div className="flex flex-col gap-6">

      {/* ── KPI cards ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <AnaliseKpi label="PR Médio 30d" value={summary.avg_pr != null ? summary.avg_pr.toFixed(3) : '—'}
          sub={`${summary.days_with_pr ?? 0} dias com dados`}
          color={summary.avg_pr != null ? (summary.avg_pr >= 0.85 ? TEAL : summary.avg_pr >= 0.70 ? '#FBBF24' : '#EF4444') : '#6B7280'} />
        <AnaliseKpi label="Perda Acum. 30d" value={summary.total_perda_rs != null ? `R$ ${summary.total_perda_rs.toFixed(0)}` : '—'}
          sub="não gerado vs previsto" color="#EF4444" />
        <AnaliseKpi label="Specific Yield" value={specificYield != null ? `${specificYield.toLocaleString('pt-BR')}` : '—'}
          sub="kWh / kWp instalado" color={COPPER} />
        <AnaliseKpi label="Capacity Factor" value={capacityFactor != null ? `${(capacityFactor * 100).toFixed(1)}%` : '—'}
          sub={`base: ${installDate ? installDate.toLocaleDateString('pt-BR') : '—'}`} color={TEAL} />
      </div>

      {/* ── PR Histórico ──────────────────────────────────────────────── */}
      <div className="glass-panel p-6 border-white/5">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-xs font-black uppercase tracking-widest text-copper">PR Histórico — 30 dias</h3>
            <p className="text-[9px] text-white/30 mt-1">
              Performance Ratio diário · NASA POWER + Open-Meteo · eficiência {((prHistory?.efficiency ?? 0.8) * 100).toFixed(0)}%
            </p>
          </div>
          <div className="flex items-center gap-4 text-[9px] font-bold text-white/30">
            {PR_THRESHOLDS.map(t => (
              <span key={t.value} className="flex items-center gap-1.5">
                <span className="w-3 h-px border-t border-dashed inline-block" style={{ borderColor: t.color }} />
                {t.label} {t.value}
              </span>
            ))}
          </div>
        </div>
        {prDays.filter((d: any) => d.pr != null).length > 0 ? (
          <div className="h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={prDays} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradPR" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={COPPER} stopOpacity={0.25} />
                    <stop offset="95%" stopColor={COPPER} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="date" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }}
                  tickFormatter={d => d?.slice(5) ?? ''} interval={4} />
                <YAxis domain={[0, 1.2]} axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }}
                  tickFormatter={v => v.toFixed(2)} />
                <Tooltip
                  contentStyle={{ background: '#0D1117', border: `1px solid ${COPPER}40`, borderRadius: 12, padding: 12 }}
                  formatter={(v: any, name: string) => {
                    if (name === 'pr') return [v != null ? Number(v).toFixed(3) : '—', 'PR']
                    if (name === 'e_real_kwh') return [v != null ? `${Number(v).toFixed(1)} kWh` : '—', 'Geração']
                    if (name === 'irr_kwh_m2') return [v != null ? `${Number(v).toFixed(2)} kWh/m²` : '—', 'Irradiância']
                    return [v, name]
                  }}
                  labelFormatter={l => `${l}`}
                />
                <ReferenceLine y={0.85} stroke="#22D3EE" strokeDasharray="4 3" strokeOpacity={0.5} />
                <ReferenceLine y={0.70} stroke="#FBBF24" strokeDasharray="4 3" strokeOpacity={0.5} />
                <Area type="monotone" dataKey="pr" stroke={COPPER} strokeWidth={2}
                  fill="url(#gradPR)" connectNulls dot={false} name="pr" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyChart label={prHistory?.available === false
            ? 'Coordenadas ou kWp não configurados.'
            : 'Dados insuficientes — aguarde mais leituras.'} />
        )}
      </div>

      {/* ── Geração real vs irradiância ───────────────────────────────── */}
      {prDays.filter((d: any) => d.e_real_kwh != null && d.irr_kwh_m2 != null).length > 2 && (
        <div className="glass-panel p-6 border-white/5">
          <div className="mb-5">
            <h3 className="text-xs font-black uppercase tracking-widest text-teal-400">Geração Real vs Irradiância</h3>
            <p className="text-[9px] text-white/30 mt-1">kWh gerado (barras) · irradiância kWh/m² (linha)</p>
          </div>
          <div className="h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={prDays} margin={{ top: 4, right: 32, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="date" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }}
                  tickFormatter={d => d?.slice(5) ?? ''} interval={4} />
                <YAxis yAxisId="left" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }}
                  tickFormatter={v => `${v}`} unit=" kWh" />
                <YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.2)', fontSize: 9 }}
                  tickFormatter={v => `${v}`} unit=" kWh/m²" width={56} />
                <Tooltip
                  contentStyle={{ background: '#0D1117', border: `1px solid ${TEAL}40`, borderRadius: 12, padding: 12 }}
                  formatter={(v: any, name: string) => name === 'e_real_kwh'
                    ? [`${Number(v).toFixed(1)} kWh`, 'Geração']
                    : [`${Number(v).toFixed(2)} kWh/m²`, 'Irradiância']}
                  labelFormatter={l => `${l}`}
                />
                <Bar yAxisId="left" dataKey="e_real_kwh" fill={TEAL} radius={[3, 3, 0, 0]} opacity={0.8} name="e_real_kwh" />
                <Line yAxisId="right" type="monotone" dataKey="irr_kwh_m2" stroke={COPPER}
                  strokeWidth={1.5} dot={false} connectNulls name="irr_kwh_m2" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── Temperatura vs Potência scatter ───────────────────────────── */}
      {caps.has_temperature && scatterData.length > 10 && (
        <div className="glass-panel p-6 border-white/5">
          <div className="mb-5">
            <h3 className="text-xs font-black uppercase tracking-widest text-copper">Temperatura vs Potência</h3>
            <p className="text-[9px] text-white/30 mt-1">Correlação entre temperatura do inversor (°C) e potência gerada (kW)</p>
          </div>
          <div className="h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="x" type="number" name="Temp" unit="°C" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }} domain={['auto', 'auto']} />
                <YAxis dataKey="y" type="number" name="Potência" unit=" kW" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }} />
                <ZAxis range={[18, 18]} />
                <Tooltip
                  contentStyle={{ background: '#0D1117', border: `1px solid ${COPPER}40`, borderRadius: 12, padding: 12 }}
                  formatter={(v: any, name: string) => name === 'Temp' ? [`${v}°C`, 'Temperatura'] : [`${v} kW`, 'Potência']}
                />
                <Scatter data={scatterData} fill={COPPER} fillOpacity={0.5} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── Export CSV ────────────────────────────────────────────────── */}
      {prDays.length > 0 && (
        <div className="flex justify-end">
          <button
            onClick={() => _csvDownload(prDays, `pr-history-${inv.alias?.replace(/\s+/g, '-')}.csv`)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl border border-white/10 text-[10px] font-black uppercase tracking-widest text-white/40 hover:border-copper/40 hover:text-copper transition-all"
          >
            <ChevronDown size={12} />
            Exportar CSV
          </button>
        </div>
      )}
    </div>
  )
}

function round3(v: number) { return Math.round(v * 1000) / 1000 }

function AnaliseKpi({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  return (
    <div className="glass-panel p-4 border-white/5">
      <div className="text-[9px] text-white/30 font-black uppercase tracking-widest mb-2">{label}</div>
      <div className="text-xl font-black" style={{ color }}>{value}</div>
      <div className="text-[9px] text-white/20 mt-1">{sub}</div>
    </div>
  )
}

function TabDashboard({ readings, serieDiaria, caps, latest, perf }: any) {
  // Power curve: today's readings only (prevents duplicate HH:MM labels across days)
  const todayStr = new Date().toDateString()
  const powerSeries = readings
    .filter((r: any) => r.ts && new Date(r.ts).toDateString() === todayStr)
    .map((r: any) => {
      const ts = new Date(r.ts).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
      return {
        ts,
        power_w:    r.active_power_w ?? null,
        power_prev: perf?.e_prevista_kwh ? _previstoW(ts, perf.e_prevista_kwh) : null,
        energy:     r.energy_today_kwh ?? null,
        temp:       r.temp_inverter_c ?? null,
        freq:       r.grid_frequency_hz ?? null,
      }
    })

  return (
    <div className="flex flex-col gap-6">
      {/* Real-time metrics */}
      {latest && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard label="Potência CA" value={`${_fv(latest.active_power_w, 0)} W`} color={COPPER} />
          <MetricCard label="Freq. Rede" value={`${_fv(latest.grid_frequency_hz, 2)} Hz`} color={TEAL} />
          {caps.has_temperature && <MetricCard label="Temperatura" value={`${_fv(latest.temp_inverter_c)}°C`} color={COPPER} />}
          <MetricCard label="Geração Hoje" value={_kwh(latest.energy_today_kwh)} color={TEAL} />
          {caps.phases > 1 && (
            <>
              <MetricCard label="Tensão CA-A" value={`${_fv(latest.ac_voltage_a_v)} V`} color={BLUE} />
              <MetricCard label="Tensão CA-B" value={`${_fv(latest.ac_voltage_b_v)} V`} color={BLUE} />
              <MetricCard label="Tensão CA-C" value={`${_fv(latest.ac_voltage_c_v)} V`} color={BLUE} />
            </>
          )}
          {caps.phases === 1 && (
            <MetricCard label="Tensão CA" value={`${_fv(latest.ac_voltage_a_v)} V`} color={BLUE} />
          )}
          {caps.has_battery && latest.battery_soc_pct !== null && (
            <MetricCard label="SOC Bateria" value={`${_fv(latest.battery_soc_pct, 0)}%`} color={BLUE} />
          )}
        </div>
      )}

      {/* Power curve */}
      <div className="glass-panel p-6 border-white/5">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-xs font-black uppercase tracking-widest text-copper">Curva de Potência</h3>
            <p className="text-[9px] text-white/30 mt-1">Potência ativa vs previsto (W)</p>
          </div>
          {perf?.e_prevista_kwh && (
            <div className="flex items-center gap-3 text-[9px] text-white/30 font-bold">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 rounded" style={{ background: COPPER }} />
                Real
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 rounded bg-white/20 border-dashed" />
                Previsto
              </span>
            </div>
          )}
        </div>
        {powerSeries.length > 0 ? (
          <div className="h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={powerSeries} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradPower" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COPPER} stopOpacity={0.35} />
                    <stop offset="95%" stopColor={COPPER} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="ts" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }} interval="preserveStartEnd" />
                <YAxis axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }}
                  tickFormatter={v => `${(v/1000).toFixed(1)}k`} />
                <Tooltip content={<PowerTooltip />} />
                <Area type="monotone" dataKey="power_w" stroke={COPPER} strokeWidth={2}
                  fill="url(#gradPower)" connectNulls dot={false} />
                {perf?.e_prevista_kwh && (
                  <Line type="monotone" dataKey="power_prev" stroke="rgba(255,255,255,0.18)"
                    strokeWidth={1.5} strokeDasharray="5 3" dot={false} connectNulls />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyChart />
        )}
      </div>

      {/* Daily energy bar */}
      <div className="glass-panel p-6 border-white/5">
        <div className="mb-5">
          <h3 className="text-xs font-black uppercase tracking-widest text-teal-400">Geração Diária</h3>
          <p className="text-[9px] text-white/30 mt-1">kWh por dia</p>
        </div>
        {serieDiaria.length > 0 ? (
          <div className="h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={serieDiaria.slice(-30)} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="day" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 8 }}
                  tickFormatter={d => d?.slice(5) || ''} interval={2} />
                <YAxis axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }}
                  tickFormatter={v => `${v}`} />
                <Tooltip
                  contentStyle={{ background: '#0D1117', border: `1px solid ${TEAL}40`, borderRadius: 12, padding: 12 }}
                  formatter={(v: any) => [`${Number(v).toFixed(1)} kWh`, 'Geração']}
                />
                <Bar dataKey="energy_kwh" fill={TEAL} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyChart />
        )}
      </div>

      {/* Temperature (conditional) */}
      {caps.has_temperature && powerSeries.some((r: any) => r.temp !== null) && (
        <div className="glass-panel p-6 border-white/5">
          <div className="mb-5">
            <h3 className="text-xs font-black uppercase tracking-widest text-copper">Temperatura do Inversor</h3>
            <p className="text-[9px] text-white/30 mt-1">°C ao longo do tempo</p>
          </div>
          <div className="h-[180px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={powerSeries} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="ts" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }} interval="preserveStartEnd" />
                <YAxis axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }}
                  tickFormatter={v => `${v}°`} />
                <ReferenceLine y={70} stroke={RED} strokeDasharray="4 4" label={{ value: 'Crítico', fill: RED, fontSize: 9 }} />
                <Tooltip contentStyle={{ background: '#0D1117', border: `1px solid ${COPPER}40`, borderRadius: 12, padding: 12 }}
                  formatter={(v: any) => [`${Number(v).toFixed(1)}°C`, 'Temperatura']} />
                <Line type="monotone" dataKey="temp" stroke={COPPER} strokeWidth={2} dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Battery (conditional) */}
      {caps.has_battery && readings.some((r: any) => r.battery_soc_pct !== null) && (
        <div className="glass-panel p-6 border-white/5">
          <div className="mb-5">
            <h3 className="text-xs font-black uppercase tracking-widest text-blue-400">Estado da Bateria (SOC)</h3>
            <p className="text-[9px] text-white/30 mt-1">% de carga ao longo do tempo</p>
          </div>
          <div className="h-[180px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={powerSeries} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradBat" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={BLUE} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={BLUE} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="ts" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }} interval="preserveStartEnd" />
                <YAxis domain={[0, 100]} axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }}
                  tickFormatter={v => `${v}%`} />
                <Tooltip contentStyle={{ background: '#0D1117', border: `1px solid ${BLUE}40`, borderRadius: 12, padding: 12 }}
                  formatter={(v: any) => [`${Number(v).toFixed(0)}%`, 'SOC Bateria']} />
                <Area type="monotone" dataKey="battery_soc_pct" stroke={BLUE} strokeWidth={2}
                  fill="url(#gradBat)" connectNulls />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Tab: Strings DC ───────────────────────────────────────────────────────────

function TabStrings({ readings, caps, latest }: any) {
  const nStrings = caps.dc_strings || 2
  const todayStr = new Date().toDateString()
  const recent = readings.filter((r: any) => r.ts && new Date(r.ts).toDateString() === todayStr)

  return (
    <div className="flex flex-col gap-6">
      {/* Current values */}
      {latest && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: nStrings }, (_, i) => i + 1).map(n => (
            <div key={n} className="glass-panel p-4 border-white/5">
              <div className="text-[9px] text-white/30 uppercase font-black tracking-widest mb-2">String {n}</div>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-[9px] text-white/40">Tensão</span>
                  <span className="text-xs font-mono font-black text-copper">
                    {_fv(latest[`dc_voltage_${n}_v`])} V
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[9px] text-white/40">Corrente</span>
                  <span className="text-xs font-mono font-black text-teal-400">
                    {_fv(latest[`dc_current_${n}_a`])} A
                  </span>
                </div>
                <div className="flex justify-between items-center border-t border-white/[0.03] pt-2">
                  <span className="text-[9px] text-white/40">Potência</span>
                  <span className="text-xs font-mono font-black text-white">
                    {latest[`dc_voltage_${n}_v`] !== null && latest[`dc_current_${n}_a`] !== null
                      ? `${((latest[`dc_voltage_${n}_v`] || 0) * (latest[`dc_current_${n}_a`] || 0)).toFixed(0)} W`
                      : '—'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Voltage chart per string */}
      <div className="glass-panel p-6 border-white/5">
        <div className="mb-5">
          <h3 className="text-xs font-black uppercase tracking-widest text-copper">Tensão DC por String</h3>
          <p className="text-[9px] text-white/30 mt-1">Comparativo de tensão (V) — identifica strings problemáticas</p>
        </div>
        {recent.length > 0 ? (
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={recent.map((r: any) => ({
                ts: r.ts ? new Date(r.ts).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '',
                ...Object.fromEntries(
                  Array.from({ length: nStrings }, (_, i) => [`s${i + 1}`, r[`dc_voltage_${i + 1}_v`]])
                ),
              }))} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="ts" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }} interval="preserveStartEnd" />
                <YAxis axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }}
                  tickFormatter={v => `${v}V`} />
                <Tooltip contentStyle={{ background: '#0D1117', border: `1px solid ${COPPER}40`, borderRadius: 12, padding: 12 }} />
                <Legend wrapperStyle={{ fontSize: 9, fontWeight: 700 }} />
                {Array.from({ length: nStrings }, (_, i) => (
                  <Line key={i} type="monotone" dataKey={`s${i + 1}`}
                    name={`String ${i + 1}`}
                    stroke={[COPPER, TEAL, BLUE, '#A855F7'][i % 4]}
                    strokeWidth={2} dot={false} connectNulls />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyChart />
        )}
      </div>
    </div>
  )
}

// ── Tab: Financeiro ───────────────────────────────────────────────────────────

function TabFinanceiro({ inv, serieMensal }: any) {
  const TARIFA = 0.85
  const totalKwh = serieMensal.reduce((s: number, m: any) => s + (m.energy_kwh || 0), 0)
  const totalReceita = totalKwh * TARIFA
  const mediaKwhMes = serieMensal.length > 0 ? totalKwh / serieMensal.length : 0

  const serieFinanceira = serieMensal.map((m: any) => ({
    ...m,
    receita: parseFloat(((m.energy_kwh || 0) * TARIFA).toFixed(2)),
  }))

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Receita Total Est.', value: `R$ ${totalReceita.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`, color: COPPER },
          { label: 'Energia Total', value: _kwh(totalKwh), color: TEAL },
          { label: 'Média Mensal', value: _kwh(mediaKwhMes), color: COPPER },
          { label: 'Tarifa Usada', value: `R$ ${TARIFA}/kWh`, color: TEAL },
        ].map((k, i) => (
          <div key={i} className="glass-panel p-4 border-white/5">
            <div className="text-[9px] text-white/30 uppercase font-black tracking-widest mb-2">{k.label}</div>
            <div className="text-lg font-black" style={{ color: k.color }}>{k.value}</div>
          </div>
        ))}
      </div>

      <div className="glass-panel p-6 border-white/5">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-xs font-black uppercase tracking-widest text-copper">Receita Estimada por Mês</h3>
            <p className="text-[9px] text-white/30 mt-1">Baseado na tarifa de R$ {TARIFA}/kWh</p>
          </div>
          <div className="text-[9px] text-white/20 font-bold px-2 py-1 border border-white/5 rounded">Estimativa</div>
        </div>
        {serieFinanceira.length > 0 ? (
          <div className="h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={serieFinanceira} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="month" axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }} />
                <YAxis axisLine={false} tickLine={false}
                  tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }}
                  tickFormatter={v => `R$${v}`} />
                <Tooltip contentStyle={{ background: '#0D1117', border: `1px solid ${COPPER}40`, borderRadius: 12, padding: 12 }}
                  formatter={(v: any) => [`R$ ${Number(v).toFixed(2)}`, 'Receita Est.']} />
                <Bar dataKey="receita" fill={COPPER} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyChart />
        )}
      </div>
    </div>
  )
}

// ── Tab: Manual Readings ──────────────────────────────────────────────────────

function TabManual({ readings, showForm, setShowForm, form, setForm, onSave, saving, caps }: any) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xs font-black uppercase tracking-widest text-white/40">Lançamentos Manuais</h3>
          <p className="text-[9px] text-white/20 mt-1">{readings.length} registros encontrados</p>
        </div>
        <Button onClick={() => setShowForm(true)} className="bg-copper text-void font-black text-[9px] uppercase tracking-widest h-9 gap-1">
          <Plus size={12} /> Novo
        </Button>
      </div>

      {showForm && (
        <QuickManualForm caps={caps} form={form} setForm={setForm} onSave={onSave} onClose={() => setShowForm(false)} saving={saving} />
      )}

      <div className="glass-panel border-white/5 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-white/5">
              {['Data/Hora', 'Potência', 'Energia Hoje', 'Energia Total', 'Temp.', 'Status'].map(h => (
                <th key={h} className="px-4 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.02]">
            {readings.slice(0, 50).map((r: any) => (
              <tr key={r.id} className="hover:bg-white/[0.01] transition-colors">
                <td className="px-4 py-3 text-[10px] font-mono text-white/50">
                  {r.ts ? new Date(r.ts).toLocaleString('pt-BR') : '—'}
                </td>
                <td className="px-4 py-3 text-[10px] font-mono text-copper">{_fv(r.active_power_w, 0)} W</td>
                <td className="px-4 py-3 text-[10px] font-mono text-white">{_kwh(r.energy_today_kwh)}</td>
                <td className="px-4 py-3 text-[10px] font-mono text-white/50">{_kwh(r.energy_total_kwh)}</td>
                <td className="px-4 py-3 text-[10px] font-mono text-white/40">{r.temp_inverter_c != null ? `${_fv(r.temp_inverter_c)}°C` : '—'}</td>
                <td className="px-4 py-3">
                  <span className={`text-[9px] font-black uppercase px-2 py-0.5 rounded ${r.status === 'normal' ? 'text-teal-400 bg-teal-400/10' : 'text-red-400 bg-red-400/10'}`}>
                    {r.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {readings.length === 0 && (
          <div className="p-12 text-center">
            <p className="text-xs text-white/20 font-bold">Nenhum lançamento ainda.</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Tab: Config ───────────────────────────────────────────────────────────────

function BackfillSection({ inv, status, onBackfill, pending }: any) {
  const [months, setMonths] = useState(6)
  const [phase, setPhase]   = useState<'both' | '1' | '2'>('both')

  const isRunning = status?.status === 'running'
  const isDone    = status?.status === 'done'
  const isError   = status?.status === 'error'
  const p1        = status?.phase1
  const p2        = status?.phase2

  const progress = isRunning && status.days_total > 0
    ? Math.round((status.days_done / status.days_total) * 100)
    : null

  const phaseLabel: Record<string, string> = {
    '1': 'Fase 1 — diário',
    '2': 'Fase 2 — intraday',
    'both': 'Fase 1 + 2',
  }

  const platformSupported = ['shinemonitor', 'solarman'].includes(inv.platform_slug)

  return (
    <div className="glass-panel p-5 border-white/5">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-[10px] font-black uppercase tracking-widest text-copper">Dados Históricos</h3>
          <p className="text-[9px] text-white/30 mt-1">
            Importa até 6 meses de dados reais da plataforma {inv.platform_name}.
          </p>
        </div>
        {isDone && (
          <span className="px-2 py-1 rounded-lg bg-teal-400/10 border border-teal-400/20 text-[9px] font-black uppercase tracking-widest text-teal-400">
            Concluído
          </span>
        )}
        {isError && (
          <span className="px-2 py-1 rounded-lg bg-red-400/10 border border-red-400/20 text-[9px] font-black uppercase tracking-widest text-red-400">
            Erro
          </span>
        )}
      </div>

      {/* Resultado anterior */}
      {isDone && (p1 || p2) && (
        <div className="grid grid-cols-2 gap-3 mb-4">
          {p1 && (
            <div className="bg-white/[0.02] rounded-xl p-3 border border-white/5">
              <div className="text-[9px] text-white/30 font-black uppercase tracking-widest mb-1">Fase 1 · Diário</div>
              <div className="text-sm font-black text-teal-400">{p1.inserted} inseridos</div>
              <div className="text-[9px] text-white/20">{p1.skipped} já existiam</div>
            </div>
          )}
          {p2 && (
            <div className="bg-white/[0.02] rounded-xl p-3 border border-white/5">
              <div className="text-[9px] text-white/30 font-black uppercase tracking-widest mb-1">Fase 2 · Intraday</div>
              <div className="text-sm font-black text-teal-400">{p2.inserted} inseridos</div>
              <div className="text-[9px] text-white/20">{p2.skipped} já existiam</div>
            </div>
          )}
        </div>
      )}

      {isError && (
        <div className="mb-4 p-3 rounded-xl bg-red-400/5 border border-red-400/10 text-[10px] text-red-400/80 font-mono">
          {status.error}
        </div>
      )}

      {/* Progress bar (Phase 2 running) */}
      {isRunning && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[9px] text-white/40 font-black uppercase tracking-widest">
              {status.phase === '1' ? 'Fase 1 — importando dados diários…' : `Fase 2 — ${status.days_done}/${status.days_total} dias`}
            </span>
            {progress !== null && (
              <span className="text-[9px] font-black text-copper">{progress}%</span>
            )}
          </div>
          <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-copper to-amber-400 rounded-full transition-all duration-500"
              style={{ width: progress !== null ? `${progress}%` : '100%' }}
            />
          </div>
          {progress === null && (
            <p className="text-[9px] text-white/20 mt-1">Buscando dados da API…</p>
          )}
        </div>
      )}

      {/* Controls */}
      {!isRunning && platformSupported && (
        <div className="flex items-end gap-3 flex-wrap">
          <div className="space-y-1">
            <label className="text-[9px] text-white/30 font-black uppercase tracking-widest">Período</label>
            <select
              value={months}
              onChange={e => setMonths(Number(e.target.value))}
              className="bg-white/5 border border-white/10 rounded-lg h-9 px-3 text-xs text-white outline-none focus:border-copper/60 transition-all"
            >
              {[1, 2, 3, 6].map(m => (
                <option key={m} value={m}>{m} {m === 1 ? 'mês' : 'meses'}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-[9px] text-white/30 font-black uppercase tracking-widest">Granularidade</label>
            <select
              value={phase}
              onChange={e => setPhase(e.target.value as any)}
              className="bg-white/5 border border-white/10 rounded-lg h-9 px-3 text-xs text-white outline-none focus:border-copper/60 transition-all"
            >
              <option value="both">Diário + Intraday</option>
              <option value="1">Só diário (rápido)</option>
              <option value="2">Só intraday</option>
            </select>
          </div>
          <button
            onClick={() => onBackfill(months, phase)}
            disabled={pending}
            className="flex items-center gap-2 h-9 px-4 rounded-xl bg-copper text-void text-[9px] font-black uppercase tracking-widest hover:bg-amber-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {pending ? <Loader2 size={11} className="animate-spin" /> : <Radio size={11} />}
            {isDone ? 'Reimportar' : 'Importar histórico'}
          </button>
        </div>
      )}

      {!platformSupported && (
        <p className="text-[9px] text-white/20">
          Backfill automático disponível para ShineMonitor e Solarman. Em breve: Growatt.
        </p>
      )}

      {/* Time estimates */}
      {!isRunning && platformSupported && (
        <div className="mt-3 flex gap-4 text-[9px] text-white/20">
          <span>Fase 1: ~{months * 1}s · {months * 30} leituras diárias</span>
          {phase !== '1' && (
            <span>Fase 2 (ShineMonitor): ~{Math.round(months * 30 * 0.4 / 60)} min · {months * 30} chamadas</span>
          )}
        </div>
      )}
    </div>
  )
}

function TabConfig({ inv, caps, onUpdate, backfillStatus, onBackfill, backfillPending }: any) {
  return (
    <div className="flex flex-col gap-5 max-w-2xl">
      {/* Backfill section — first, above fold */}
      {inv.mode === 'api' && (
        <BackfillSection
          inv={inv}
          status={backfillStatus}
          onBackfill={onBackfill}
          pending={backfillPending}
        />
      )}

      <div className="glass-panel p-5 border-white/5">
        <h3 className="text-[10px] font-black uppercase tracking-widest text-white/40 mb-4">Informações Gerais</h3>
        <div className="space-y-3 text-xs">
          <div className="flex justify-between py-2 border-b border-white/[0.03]">
            <span className="text-white/30 font-bold uppercase tracking-widest text-[9px]">ID</span>
            <span className="font-mono text-white/40">{inv.id}</span>
          </div>
          <div className="flex justify-between py-2 border-b border-white/[0.03]">
            <span className="text-white/30 font-bold uppercase tracking-widest text-[9px]">Status</span>
            <span className="font-bold text-copper">{inv.status}</span>
          </div>
          <div className="flex justify-between py-2 border-b border-white/[0.03]">
            <span className="text-white/30 font-bold uppercase tracking-widest text-[9px]">Modo</span>
            <span className="font-bold text-white">{inv.mode}</span>
          </div>
          <div className="flex justify-between py-2">
            <span className="text-white/30 font-bold uppercase tracking-widest text-[9px]">Criado em</span>
            <span className="font-mono text-white/40">{inv.created_at}</span>
          </div>
        </div>
      </div>

      <div className="glass-panel p-5 border-white/5">
        <h3 className="text-[10px] font-black uppercase tracking-widest text-white/40 mb-4">Capabilities (JSON)</h3>
        <pre className="text-[10px] font-mono text-copper/80 bg-black/30 p-3 rounded-xl overflow-x-auto">
          {JSON.stringify(caps, null, 2)}
        </pre>
        <p className="text-[9px] text-white/20 mt-2">
          Controla quais gráficos e métricas aparecem neste inversor.
        </p>
      </div>
    </div>
  )
}

// ── Quick Manual Form ─────────────────────────────────────────────────────────

function QuickManualForm({ caps, form, setForm, onSave, onClose, saving }: any) {
  const setF = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((p: any) => ({ ...p, [k]: parseFloat(e.target.value) || null }))

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="glass-panel p-5 border-copper/20 bg-copper/[0.02]"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-black uppercase tracking-widest text-copper">Novo Lançamento Manual</h3>
        <button onClick={onClose} className="text-white/30 hover:text-white transition-all"><X size={16} /></button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {[
          { key: 'active_power_w', label: 'Potência (W)', step: '1' },
          { key: 'energy_today_kwh', label: 'Energia Hoje (kWh)', step: '0.1' },
          { key: 'energy_total_kwh', label: 'Energia Total (kWh)', step: '0.1' },
          ...(caps.has_temperature ? [{ key: 'temp_inverter_c', label: 'Temperatura (°C)', step: '0.1' }] : []),
          { key: 'grid_frequency_hz', label: 'Frequência (Hz)', step: '0.01' },
          ...(caps.has_battery ? [{ key: 'battery_soc_pct', label: 'SOC Bateria (%)', step: '1' }] : []),
        ].map(f => (
          <div key={f.key} className="space-y-1">
            <label className="text-[9px] text-white/30 font-black uppercase tracking-widest">{f.label}</label>
            <input
              type="number" step={f.step}
              className="w-full bg-white/5 border border-white/10 rounded-lg h-9 px-3 text-xs font-mono text-white outline-none focus:border-copper/60 transition-all"
              onChange={setF(f.key)}
            />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 mt-4">
        <Button onClick={onSave} disabled={saving}
          className="bg-copper text-void font-black text-[9px] uppercase tracking-widest h-9">
          {saving ? <Loader2 size={12} className="animate-spin mr-1" /> : null}
          Salvar
        </Button>
        <Button onClick={onClose} variant="outline" className="border-white/10 text-white/30 h-9 text-xs">
          Cancelar
        </Button>
      </div>
    </motion.div>
  )
}

// ── Tab: Manutenção ───────────────────────────────────────────────────────────

const PRIORITY_META: Record<string, { label: string; color: string; bg: string }> = {
  low:      { label: 'Baixa',    color: '#6B7280', bg: 'bg-gray-500/10'  },
  medium:   { label: 'Média',    color: '#3B82F6', bg: 'bg-blue-500/10'  },
  high:     { label: 'Alta',     color: '#F59E0B', bg: 'bg-amber-500/10' },
  critical: { label: 'Crítica',  color: '#EF4444', bg: 'bg-red-500/10'   },
}

const STATUS_META: Record<string, { label: string; icon: any; color: string }> = {
  pending:     { label: 'Pendente',    icon: Clock,         color: '#F59E0B' },
  in_progress: { label: 'Em andamento', icon: CircleDot,   color: '#3B82F6' },
  done:        { label: 'Concluída',   icon: CheckCircle2,  color: '#22C55E' },
  cancelled:   { label: 'Cancelada',  icon: Ban,            color: '#6B7280' },
}

const EMPTY_TASK = { title: '', description: '', priority: 'medium', assignee: '', due_date: '' }

function TabManutencao({
  tasks, onCreate, onUpdate, onDelete, saving,
}: {
  tasks: any[]
  onCreate: (body: any) => void
  onUpdate: (taskId: string, patch: any, onSuccess?: () => void) => void
  onDelete: (taskId: string) => void
  saving: boolean
}) {
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<Record<string, string>>(EMPTY_TASK)
  const [filter, setFilter] = useState<'all' | 'open' | 'done'>('open')
  const [editId, setEditId] = useState<string | null>(null)
  const [editPatch, setEditPatch] = useState<Record<string, string>>({})

  const setF = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm(p => ({ ...p, [k]: e.target.value }))

  const visible = tasks.filter(t => {
    if (filter === 'open')  return t.status === 'pending' || t.status === 'in_progress'
    if (filter === 'done')  return t.status === 'done' || t.status === 'cancelled'
    return true
  })

  const openCount = tasks.filter(t => t.status === 'pending' || t.status === 'in_progress').length

  function handleCreate() {
    if (!form.title.trim()) return
    onCreate(form)
    setShowForm(false)
    setForm(EMPTY_TASK)
  }

  function startEdit(task: any) {
    setEditId(task.id)
    setEditPatch({ status: task.status, priority: task.priority, assignee: task.assignee ?? '', notes: task.notes ?? '' })
  }

  function saveEdit() {
    if (!editId) return
    onUpdate(editId, editPatch, () => setEditId(null))
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xs font-black uppercase tracking-widest text-white/60">Manutenção</h2>
          <p className="text-[10px] text-white/30 mt-0.5">
            {openCount > 0 ? `${openCount} tarefa${openCount > 1 ? 's' : ''} aberta${openCount > 1 ? 's' : ''}` : 'Nenhuma tarefa aberta'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Filter chips */}
          {(['open', 'all', 'done'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${
                filter === f ? 'bg-copper/20 text-copper border border-copper/30' : 'text-white/30 border border-white/10 hover:border-white/20'
              }`}
            >
              {f === 'open' ? 'Abertas' : f === 'done' ? 'Fechadas' : 'Todas'}
            </button>
          ))}
          <Button
            onClick={() => setShowForm(v => !v)}
            className="bg-copper text-void font-black text-[9px] uppercase tracking-widest h-8 gap-1.5"
          >
            <Plus size={12} /> Nova Tarefa
          </Button>
        </div>
      </div>

      {/* New task form */}
      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="glass-panel p-5 border-copper/20 bg-copper/[0.02]"
          >
            <h3 className="text-xs font-black uppercase tracking-widest text-copper mb-4">Nova Tarefa</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="md:col-span-2 space-y-1">
                <label className="text-[9px] text-white/30 font-black uppercase tracking-widest">Título *</label>
                <input
                  value={form.title} onChange={setF('title')}
                  placeholder="Descreva a tarefa..."
                  className="w-full bg-white/5 border border-white/10 rounded-lg h-9 px-3 text-xs text-white outline-none focus:border-copper/60 transition-all"
                />
              </div>
              <div className="md:col-span-2 space-y-1">
                <label className="text-[9px] text-white/30 font-black uppercase tracking-widest">Descrição</label>
                <textarea
                  value={form.description} onChange={setF('description')}
                  rows={2}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-copper/60 transition-all resize-none"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[9px] text-white/30 font-black uppercase tracking-widest">Prioridade</label>
                <select
                  value={form.priority} onChange={setF('priority')}
                  className="w-full bg-white/5 border border-white/10 rounded-lg h-9 px-3 text-xs text-white outline-none focus:border-copper/60 transition-all"
                >
                  {Object.entries(PRIORITY_META).map(([k, v]) => (
                    <option key={k} value={k} className="bg-[#0A0A0A]">{v.label}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-[9px] text-white/30 font-black uppercase tracking-widest">Responsável</label>
                <input
                  value={form.assignee} onChange={setF('assignee')}
                  placeholder="Nome ou e-mail"
                  className="w-full bg-white/5 border border-white/10 rounded-lg h-9 px-3 text-xs text-white outline-none focus:border-copper/60 transition-all"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[9px] text-white/30 font-black uppercase tracking-widest">Prazo</label>
                <input
                  type="date" value={form.due_date} onChange={setF('due_date')}
                  className="w-full bg-white/5 border border-white/10 rounded-lg h-9 px-3 text-xs text-white outline-none focus:border-copper/60 transition-all"
                />
              </div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <Button onClick={handleCreate} disabled={saving || !form.title.trim()}
                className="bg-copper text-void font-black text-[9px] uppercase tracking-widest h-8">
                {saving ? <Loader2 size={11} className="animate-spin mr-1" /> : null}
                Criar Tarefa
              </Button>
              <Button onClick={() => setShowForm(false)} variant="outline"
                className="border-white/10 text-white/30 h-8 text-xs">
                Cancelar
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Task list */}
      {visible.length === 0 ? (
        <div className="glass-panel p-8 flex flex-col items-center gap-3">
          <Wrench size={28} className="text-white/10" />
          <p className="text-xs text-white/30 font-bold">
            {filter === 'open' ? 'Nenhuma tarefa aberta' : 'Nenhuma tarefa encontrada'}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {visible.map((task: any) => {
            const pm = PRIORITY_META[task.priority] ?? PRIORITY_META.medium
            const sm = STATUS_META[task.status] ?? STATUS_META.pending
            const StatusIcon = sm.icon
            const isEditing = editId === task.id
            const isOverdue = task.due_date && new Date(task.due_date) < new Date() && task.status !== 'done' && task.status !== 'cancelled'

            return (
              <div key={task.id} className={`glass-panel p-4 border-white/5 ${isEditing ? 'border-copper/30' : ''}`}>
                <div className="flex items-start gap-3">
                  {/* Status icon */}
                  <StatusIcon size={15} style={{ color: sm.color }} className="mt-0.5 shrink-0" />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-xs font-black text-white truncate">{task.title}</p>
                        {task.description && (
                          <p className="text-[10px] text-white/40 mt-0.5 leading-relaxed line-clamp-2">{task.description}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-widest ${pm.bg}`} style={{ color: pm.color }}>
                          {pm.label}
                        </span>
                      </div>
                    </div>

                    {/* Meta row */}
                    <div className="flex items-center gap-3 mt-2 flex-wrap">
                      {task.assignee && (
                        <span className="text-[9px] text-white/30">👤 {task.assignee}</span>
                      )}
                      {task.due_date && (
                        <span className={`text-[9px] ${isOverdue ? 'text-red-400 font-bold' : 'text-white/30'}`}>
                          📅 {new Date(task.due_date + 'T12:00:00').toLocaleDateString('pt-BR')}
                          {isOverdue && ' · Atrasada'}
                        </span>
                      )}
                      {task.alert_id && (
                        <span className="text-[9px] text-amber-400/60">⚠ Gerada por alerta</span>
                      )}
                      <span className="text-[9px] text-white/20">
                        {new Date(task.created_at).toLocaleDateString('pt-BR')}
                      </span>
                    </div>

                    {/* Inline edit */}
                    {isEditing && (
                      <div className="mt-3 grid grid-cols-2 gap-2 border-t border-white/5 pt-3">
                        <div className="space-y-1">
                          <label className="text-[8px] text-white/30 font-black uppercase tracking-widest">Status</label>
                          <select
                            value={editPatch.status}
                            onChange={e => setEditPatch(p => ({ ...p, status: e.target.value }))}
                            className="w-full bg-white/5 border border-white/10 rounded-lg h-8 px-2 text-[10px] text-white outline-none focus:border-copper/60"
                          >
                            {Object.entries(STATUS_META).map(([k, v]) => (
                              <option key={k} value={k} className="bg-[#0A0A0A]">{v.label}</option>
                            ))}
                          </select>
                        </div>
                        <div className="space-y-1">
                          <label className="text-[8px] text-white/30 font-black uppercase tracking-widest">Prioridade</label>
                          <select
                            value={editPatch.priority}
                            onChange={e => setEditPatch(p => ({ ...p, priority: e.target.value }))}
                            className="w-full bg-white/5 border border-white/10 rounded-lg h-8 px-2 text-[10px] text-white outline-none focus:border-copper/60"
                          >
                            {Object.entries(PRIORITY_META).map(([k, v]) => (
                              <option key={k} value={k} className="bg-[#0A0A0A]">{v.label}</option>
                            ))}
                          </select>
                        </div>
                        <div className="col-span-2 space-y-1">
                          <label className="text-[8px] text-white/30 font-black uppercase tracking-widest">Responsável</label>
                          <input
                            value={editPatch.assignee}
                            onChange={e => setEditPatch(p => ({ ...p, assignee: e.target.value }))}
                            className="w-full bg-white/5 border border-white/10 rounded-lg h-8 px-2 text-[10px] text-white outline-none focus:border-copper/60"
                          />
                        </div>
                        <div className="col-span-2 space-y-1">
                          <label className="text-[8px] text-white/30 font-black uppercase tracking-widest">Observações</label>
                          <textarea
                            value={editPatch.notes}
                            onChange={e => setEditPatch(p => ({ ...p, notes: e.target.value }))}
                            rows={2}
                            className="w-full bg-white/5 border border-white/10 rounded-lg px-2 py-1.5 text-[10px] text-white outline-none focus:border-copper/60 resize-none"
                          />
                        </div>
                        <div className="col-span-2 flex gap-2">
                          <Button onClick={saveEdit} disabled={saving}
                            className="bg-copper text-void font-black text-[8px] uppercase tracking-widest h-7">
                            Salvar
                          </Button>
                          <Button onClick={() => setEditId(null)} variant="outline"
                            className="border-white/10 text-white/30 h-7 text-[10px]">
                            Cancelar
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  {!isEditing && (
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => startEdit(task)}
                        className="p-1.5 rounded hover:bg-white/10 text-white/30 hover:text-white/60 transition-all"
                        title="Editar"
                      >
                        <Wrench size={12} />
                      </button>
                      {task.status !== 'done' && task.status !== 'cancelled' && (
                        <button
                          onClick={() => onUpdate(task.id, { status: 'done' })}
                          className="p-1.5 rounded hover:bg-green-500/10 text-white/30 hover:text-green-400 transition-all"
                          title="Marcar como concluída"
                        >
                          <CheckCircle2 size={12} />
                        </button>
                      )}
                      <button
                        onClick={() => onDelete(task.id)}
                        className="p-1.5 rounded hover:bg-red-500/10 text-white/30 hover:text-red-400 transition-all"
                        title="Excluir"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="glass-panel p-4 border-white/5">
      <div className="text-[9px] text-white/30 uppercase font-black tracking-widest mb-2">{label}</div>
      <div className="text-base font-black font-mono" style={{ color }}>{value}</div>
    </div>
  )
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    normal: 'text-teal-400 bg-teal-400/10 border-teal-400/20',
    active: 'text-teal-400 bg-teal-400/10 border-teal-400/20',
    offline: 'text-white/30 bg-white/5 border-white/10',
    error: 'text-red-400 bg-red-400/10 border-red-400/20',
    pending: 'text-copper bg-copper/10 border-copper/20',
  }
  const label: Record<string, string> = {
    normal: 'Online', active: 'Online', offline: 'Offline', error: 'Erro', pending: 'Pendente',
  }
  return (
    <span className={`px-3 py-1 rounded-lg border text-[9px] font-black uppercase tracking-widest ${map[status] || map.offline}`}>
      {label[status] || status}
    </span>
  )
}

function EmptyChart({ label }: { label?: string } = {}) {
  return (
    <div className="h-[140px] flex items-center justify-center">
      <p className="text-xs text-white/20 font-bold text-center max-w-xs">
        {label ?? 'Nenhum dado para exibir. Sincronize para começar.'}
      </p>
    </div>
  )
}
