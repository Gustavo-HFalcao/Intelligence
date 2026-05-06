import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Zap, Plus, Sun, Activity, Wifi, WifiOff, AlertTriangle,
  ChevronRight, Settings, RefreshCw, X, Check, Loader2,
  MapPin, Calendar, TrendingUp, Battery, Thermometer,
  LayoutGrid, List, Search, Filter, Wrench,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import './Dashboard.css'
import api from '@/services/api'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'

const STATUS_COLOR: Record<string, string> = {
  active:  'text-teal-400 bg-teal-400/10',
  pending: 'text-copper bg-copper/10',
  error:   'text-red-400 bg-red-400/10',
  offline: 'text-white/30 bg-white/5',
  manual:  'text-blue-400 bg-blue-400/10',
}
const STATUS_LABEL: Record<string, string> = {
  active:  'Online',
  pending: 'Pendente',
  error:   'Erro',
  offline: 'Offline',
  manual:  'Manual',
}

const PLATFORM_ICON: Record<string, string> = {
  shinemonitor: '⚡',
  growatt:      '☀️',
  solarman:     '🔆',
  manual:       '✏️',
}

// ── Wizard step types ─────────────────────────────────────────────────────────

interface Platform {
  slug: string
  name: string
  app_names: string[]
  market_coverage: string
  auth_type: string
  fields_form: Array<{ key: string; label: string; type: string; required: boolean; hint?: string }>
  capabilities: Record<string, any>
}

function timeAgo(ts: string): string {
  if (!ts) return '—'
  const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000)
  if (diff < 60)  return `há ${diff}s`
  if (diff < 3600) return `há ${Math.floor(diff / 60)}min`
  if (diff < 86400) return `há ${Math.floor(diff / 3600)}h`
  return `há ${Math.floor(diff / 86400)}d`
}

export default function GestaoInversores() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [view, setView] = useState<'grid' | 'list'>('grid')
  const [search, setSearch] = useState('')
  const [filterPlatform, setFilterPlatform] = useState('')
  const [showWizard, setShowWizard] = useState(false)
  const [syncToast, setSyncToast] = useState<{ id: string; msg: string; ok: boolean } | null>(null)

  const { data: invData, isLoading } = useQuery({
    queryKey: ['inversores'],
    queryFn: () => api.get('/inversores').then(r => r.data),
    refetchInterval: 60_000,
  })

  const { data: platformsData } = useQuery({
    queryKey: ['inversor-platforms'],
    queryFn: () => api.get('/inversores/platforms').then(r => r.data),
    staleTime: Infinity,
  })

  const syncMut = useMutation({
    mutationFn: (id: string) => api.post(`/inversores/${id}/sync`).then(r => r.data),
    onSuccess: (data, id) => {
      qc.invalidateQueries({ queryKey: ['inversores'] })
      const r = data?.reading
      const msg = r?.active_power_w != null
        ? `${(r.active_power_w / 1000).toFixed(1)} kW · ${r.energy_today_kwh?.toFixed(1)} kWh hoje`
        : 'Sincronizado'
      setSyncToast({ id, msg, ok: true })
      setTimeout(() => setSyncToast(null), 4000)
    },
    onError: (_err, id) => {
      setSyncToast({ id, msg: 'Erro ao sincronizar', ok: false })
      setTimeout(() => setSyncToast(null), 4000)
    },
  })

  const syncAllMut = useMutation({
    mutationFn: () => api.get('/inversores/sync-all').then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inversores'] }),
  })

  const inversores: any[] = invData?.inversores ?? []
  const platforms: Platform[] = platformsData?.platforms ?? []

  const filtered = useMemo(() => {
    let list = inversores
    if (search) {
      const q = search.toLowerCase()
      list = list.filter(i =>
        i.alias?.toLowerCase().includes(q) ||
        i.location?.toLowerCase().includes(q) ||
        i.platform_name?.toLowerCase().includes(q)
      )
    }
    if (filterPlatform) list = list.filter(i => i.platform_slug === filterPlatform)
    return list
  }, [inversores, search, filterPlatform])

  const totalKwh = useMemo(() =>
    inversores.reduce((s, i) => s + (i.nominal_power_kw || 0), 0), [inversores])

  return (
    <div className="flex flex-col gap-6 animate-enter">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
            <Zap size={24} className="text-copper" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-white uppercase tracking-tight">
              Gestão de Inversores
            </h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">
              Monitoramento Solar · O&M Inteligente
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={() => syncAllMut.mutate()}
            disabled={syncAllMut.isPending}
            variant="outline"
            className="border-white/10 text-white/50 hover:border-copper/40 hover:text-copper font-black text-[10px] uppercase tracking-widest h-10 px-4 gap-2"
          >
            <RefreshCw size={13} className={syncAllMut.isPending ? 'animate-spin text-copper' : ''} />
            {syncAllMut.isPending ? 'Sincronizando...' : 'Sync All'}
          </Button>
          <Button
            onClick={() => setShowWizard(true)}
            className="bg-copper hover:bg-copper/80 text-void font-black text-[10px] uppercase tracking-widest h-10 px-5 gap-2"
          >
            <Plus size={16} /> Novo Inversor
          </Button>
        </div>
      </div>

      {/* ── Toast de Sync ───────────────────────────────────────────────── */}
      {syncToast && (
        <div className={`fixed bottom-6 right-6 z-[300] flex items-center gap-3 px-4 py-3 rounded-xl border shadow-2xl text-xs font-bold transition-all ${
          syncToast.ok
            ? 'bg-teal-950/90 border-teal-500/30 text-teal-300'
            : 'bg-red-950/90 border-red-500/30 text-red-300'
        }`}>
          {syncToast.ok ? <Wifi size={14} /> : <WifiOff size={14} />}
          {syncToast.msg}
        </div>
      )}

      {/* ── KPI Strip ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          {
            label: 'Inversores Cadastrados', value: inversores.length,
            sub: `${invData?.active ?? 0} online`, icon: Zap, color: COPPER,
          },
          {
            label: 'Capacidade Total', value: `${totalKwh.toFixed(1)} kWp`,
            sub: 'instalado', icon: Sun, color: TEAL,
          },
          {
            label: 'Plataformas Ativas', value: invData?.platforms_used?.length ?? 0,
            sub: 'integradas', icon: Activity, color: TEAL,
          },
          {
            label: 'Cobertura de Mercado', value: '~80%',
            sub: 'mercado BR coberto', icon: TrendingUp, color: COPPER,
          },
        ].map((k, i) => (
          <div key={i} className="glass-panel p-4 border-white/5 hover:border-white/10 transition-all group">
            <div className="flex items-center justify-between mb-3">
              <k.icon size={16} style={{ color: k.color }} />
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: k.color }} />
            </div>
            <div className="text-[9px] text-text-muted uppercase font-black tracking-widest mb-1">{k.label}</div>
            <div className="text-xl font-black text-white">{k.value}</div>
            <div className="text-[9px] text-white/20 font-bold mt-0.5">{k.sub}</div>
          </div>
        ))}
      </div>

      {/* ── Fleet status strip ──────────────────────────────────────────── */}
      {inversores.filter(i => i.status === 'active').length > 1 && (
        <FleetStatusStrip inversores={inversores} />
      )}

      {/* ── Filters bar ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/20" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar inversor..."
            className="w-full bg-white/5 border border-white/5 rounded-xl h-9 pl-9 pr-3 text-xs text-white outline-none focus:border-copper/40 transition-all"
          />
        </div>

        <div className="flex items-center gap-1">
          {['', 'shinemonitor', 'growatt', 'solarman'].map(p => (
            <button
              key={p}
              onClick={() => setFilterPlatform(p)}
              className={`px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all border ${
                filterPlatform === p
                  ? 'bg-copper text-void border-copper'
                  : 'bg-white/5 text-text-muted border-white/5 hover:border-copper/30'
              }`}
            >
              {p ? PLATFORM_ICON[p] + ' ' + p : 'Todos'}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1 border border-white/5 rounded-lg p-1">
          {(['grid', 'list'] as const).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`p-1.5 rounded transition-all ${view === v ? 'bg-copper/20 text-copper' : 'text-white/20 hover:text-white/40'}`}
            >
              {v === 'grid' ? <LayoutGrid size={14} /> : <List size={14} />}
            </button>
          ))}
        </div>
      </div>

      {/* ── Inversor Grid / List ─────────────────────────────────────────── */}
      {isLoading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 size={24} className="animate-spin text-copper" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-panel p-16 text-center flex flex-col items-center gap-4 border-white/5">
          <Sun size={40} className="text-white/10" />
          <div>
            <p className="text-sm font-black text-white/40 uppercase tracking-widest">
              {inversores.length === 0 ? 'Nenhum inversor cadastrado' : 'Nenhum resultado'}
            </p>
            <p className="text-xs text-white/20 mt-1">
              {inversores.length === 0
                ? 'Clique em "Novo Inversor" para começar'
                : 'Tente ajustar os filtros'}
            </p>
          </div>
          {inversores.length === 0 && (
            <Button onClick={() => setShowWizard(true)} className="bg-copper text-void text-[10px] font-black uppercase tracking-widest">
              <Plus size={14} className="mr-2" /> Adicionar primeiro inversor
            </Button>
          )}
        </div>
      ) : view === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <AnimatePresence>
            {filtered.map(inv => (
              <InversorCard
                key={inv.id}
                inv={inv}
                onOpen={() => navigate(`/inversores/${inv.id}`)}
                onSync={() => syncMut.mutate(inv.id)}
                syncing={syncMut.isPending && syncMut.variables === inv.id}
              />
            ))}
          </AnimatePresence>
        </div>
      ) : (
        <div className="glass-panel border-white/5 overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-white/5">
                {['Inversor', 'Plataforma', 'Capacidade', 'Localização', 'Status', 'Ações'].map(h => (
                  <th key={h} className="px-5 py-3 text-[9px] font-black uppercase tracking-widest text-text-muted">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.02]">
              {filtered.map(inv => (
                <tr key={inv.id} className="hover:bg-copper/5 transition-colors group cursor-pointer"
                    onClick={() => navigate(`/inversores/${inv.id}`)}>
                  <td className="px-5 py-3">
                    <div className="font-bold text-white text-xs">{inv.alias}</div>
                    <div className="text-[9px] text-white/30 font-mono">{inv.sn || '—'}</div>
                  </td>
                  <td className="px-5 py-3">
                    <span className="text-xs font-bold text-copper">
                      {PLATFORM_ICON[inv.platform_slug]} {inv.platform_name}
                    </span>
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-white">{inv.nominal_power_kw} kWp</td>
                  <td className="px-5 py-3 text-xs text-white/50">{inv.location || '—'}</td>
                  <td className="px-5 py-3">
                    <StatusBadge status={inv.status} />
                  </td>
                  <td className="px-5 py-3">
                    <button
                      onClick={e => { e.stopPropagation(); syncMut.mutate(inv.id) }}
                      className="p-1.5 hover:bg-copper/10 rounded text-copper opacity-0 group-hover:opacity-100 transition-all"
                    >
                      <RefreshCw size={13} className={syncMut.isPending && syncMut.variables === inv.id ? 'animate-spin' : ''} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Wizard Modal ─────────────────────────────────────────────────── */}
      <AnimatePresence>
        {showWizard && (
          <InversorWizard
            platforms={platforms}
            onClose={() => setShowWizard(false)}
            onSaved={() => {
              setShowWizard(false)
              qc.invalidateQueries({ queryKey: ['inversores'] })
            }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Fleet Status Strip ───────────────────────────────────────────────────────

function FleetStatusStrip({ inversores }: { inversores: any[] }) {
  const active   = inversores.filter(i => i.status === 'active').length
  const errors   = inversores.filter(i => i.status === 'error').length
  const pending  = inversores.filter(i => i.status === 'pending').length
  const totalKwp = inversores.reduce((s, i) => s + (i.nominal_power_kw || 0), 0)

  const dots = inversores.map(inv => {
    const age = inv.last_sync_at
      ? (Date.now() - new Date(inv.last_sync_at).getTime()) / 60000
      : Infinity
    const live = inv.status === 'active' && age < 20
    const color = inv.status === 'error'   ? 'bg-red-400'
      : inv.status === 'pending' ? 'bg-amber-400/50'
      : live                     ? 'bg-teal-400'
      : inv.status === 'active'  ? 'bg-teal-400/40'
      :                            'bg-white/10'
    return { id: inv.id, alias: inv.alias, color, live }
  })

  return (
    <div className="glass-panel px-5 py-3 border-white/5 flex items-center justify-between gap-6">
      <div className="flex items-center gap-5">
        <div className="flex items-center gap-1.5">
          {dots.map(d => (
            <div key={d.id} className="relative" title={d.alias}>
              {d.live && <span className="absolute inset-0 rounded-full animate-ping bg-teal-400/30" />}
              <div className={`w-2.5 h-2.5 rounded-full ${d.color} transition-colors`} />
            </div>
          ))}
        </div>
        <div className="h-4 w-px bg-white/5" />
        <div className="flex items-center gap-4 text-[9px] font-black uppercase tracking-widest">
          <span className="text-teal-400">{active} online</span>
          {errors > 0 && <span className="text-red-400">{errors} erro{errors > 1 ? 's' : ''}</span>}
          {pending > 0 && <span className="text-amber-400/70">{pending} pendente{pending > 1 ? 's' : ''}</span>}
        </div>
      </div>
      <div className="text-[9px] text-white/20 font-bold">
        {totalKwp.toFixed(1)} kWp total instalado
      </div>
    </div>
  )
}

// ── Inversor Card ─────────────────────────────────────────────────────────────

const PR_STATUS: Record<string, { label: string; dot: string; text: string }> = {
  normal:      { label: 'Normal',   dot: 'bg-green-500',  text: 'text-green-400' },
  atencao:     { label: 'Atenção',  dot: 'bg-amber-400',  text: 'text-amber-400' },
  critico:     { label: 'Crítico',  dot: 'bg-red-500',    text: 'text-red-400'   },
  sem_dados:   { label: '—',        dot: 'bg-white/10',   text: 'text-white/20'  },
  sem_geracao: { label: '—',        dot: 'bg-white/10',   text: 'text-white/20'  },
}

function InversorCard({ inv, onOpen, onSync, syncing }: {
  inv: any; onOpen: () => void; onSync: () => void; syncing: boolean
}) {
  const caps = inv.capabilities || {}
  const hasCoords = inv.plant_meta?.coords_valid === true

  const { data: perf } = useQuery({
    queryKey: ['inv-perf', inv.id],
    queryFn: () => api.get(`/inversores/${inv.id}/performance`).then(r => r.data),
    enabled: inv.mode === 'api' && inv.status === 'active' && hasCoords,
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  })

  const { data: alertsData } = useQuery({
    queryKey: ['inv-alerts', inv.id],
    queryFn: () => api.get(`/inversores/${inv.id}/alerts`).then(r => r.data),
    enabled: inv.mode === 'api',
    staleTime: 2 * 60_000,
    refetchInterval: 5 * 60_000,
  })

  const { data: maintCount } = useQuery({
    queryKey: ['inv-maint-count', inv.id],
    queryFn: () => api.get(`/maintenance/inversor/${inv.id}/open-count`).then(r => r.data),
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  })

  const prInfo = perf?.status ? PR_STATUS[perf.status] ?? PR_STATUS.sem_dados : null
  const openAlerts: number = alertsData?.open_count ?? 0
  const criticalAlerts: number = alertsData?.critical_count ?? 0
  const openTasks: number = maintCount?.open_count ?? 0

  const lastSyncAge = inv.last_sync_at
    ? (Date.now() - new Date(inv.last_sync_at).getTime()) / 60000
    : Infinity
  const isLive = inv.status === 'active' && lastSyncAge < 20

  const ringClass: Record<string, string> = {
    active:  isLive
      ? 'border-teal-400 bg-teal-400/10'
      : 'border-teal-400/40 bg-teal-400/5',
    error:   'border-red-400/60 bg-red-400/10',
    pending: 'border-amber-400/40 bg-amber-400/5',
    offline: 'border-white/10 bg-white/5',
    manual:  'border-blue-400/40 bg-blue-400/5',
  }
  const iconRing = ringClass[inv.status] ?? 'border-white/10 bg-white/5'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="glass-panel p-5 border-white/5 hover:border-copper/20 transition-all cursor-pointer group flex flex-col gap-4"
      onClick={onOpen}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div className="relative">
            {isLive && (
              <span className="absolute -inset-1 rounded-[14px] animate-ping border border-teal-400/30 pointer-events-none" />
            )}
            <div className={`w-9 h-9 rounded-xl border flex items-center justify-center text-lg transition-colors ${iconRing}`}>
              {PLATFORM_ICON[inv.platform_slug] || '⚡'}
            </div>
          </div>
          <div>
            <div className="text-sm font-black text-white group-hover:text-copper transition-colors">
              {inv.alias}
            </div>
            <div className="text-[9px] text-white/30 font-bold uppercase tracking-widest">
              {inv.plant_name || inv.platform_name}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={e => { e.stopPropagation(); onSync() }}
            className="p-1.5 hover:bg-copper/10 rounded-lg text-white/20 hover:text-copper transition-all"
            title="Sincronizar agora"
          >
            <RefreshCw size={13} className={syncing ? 'animate-spin text-copper' : ''} />
          </button>
          <ChevronRight size={14} className="text-white/20 group-hover:text-copper transition-colors" />
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-2">
        <StatChip label="Potência" value={`${inv.nominal_power_kw} kWp`} />
        <StatChip label="Strings DC" value={caps.dc_strings ? `${caps.dc_strings}x` : '—'} />
        <StatChip label="Fases" value={caps.phases ? `${caps.phases}φ` : '—'} />
      </div>

      {/* Capability badges */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {caps.has_temperature && <CapBadge label="Temp." icon={<Thermometer size={10} />} />}
        {caps.has_battery && <CapBadge label="Bateria" icon={<Battery size={10} />} color="text-blue-400 bg-blue-400/10" />}
        {inv.mode === 'api' && <CapBadge label="API" icon={<Wifi size={10} />} color="text-teal-400 bg-teal-400/10" />}
        {inv.mode === 'manual' && <CapBadge label="Manual" icon={<Settings size={10} />} color="text-blue-400 bg-blue-400/10" />}
      </div>

      {/* Aviso credenciais pendentes */}
      {inv.status === 'pending' && inv.platform_slug === 'solarman' && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/5 border border-amber-500/20 text-[9px] text-amber-400 font-bold">
          <AlertTriangle size={10} />
          Aguardando app_id / app_secret
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-white/[0.04]">
        <div className="flex items-center gap-2">
          <StatusBadge status={inv.status} />
          {prInfo && perf?.pr != null && (
            <span className={`flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-widest ${prInfo.text} bg-white/[0.03]`}>
              <span className={`w-1.5 h-1.5 rounded-full ${prInfo.dot}`} />
              PR {perf.pr.toFixed(2)}
            </span>
          )}
          {perf?.perda_rs != null && perf.perda_rs > 0 && (
            <span className="text-[9px] text-red-400/70 font-bold">
              −R${perf.perda_rs.toFixed(0)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-[9px] text-white/20 font-bold">
          {openAlerts > 0 && (
            <span className={`flex items-center gap-1 px-1.5 py-0.5 rounded font-black uppercase tracking-widest ${
              criticalAlerts > 0 ? 'text-red-400 bg-red-400/10' : 'text-amber-400 bg-amber-400/10'
            }`}>
              <AlertTriangle size={9} />
              {openAlerts} alerta{openAlerts > 1 ? 's' : ''}
            </span>
          )}
          {openTasks > 0 && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded font-black uppercase tracking-widest text-amber-300 bg-amber-300/10">
              <Wrench size={9} />
              {openTasks} OS
            </span>
          )}
          {inv.location && (
            <span className="flex items-center gap-1">
              <MapPin size={10} /> {inv.location}
            </span>
          )}
          {inv.last_sync_at && (
            <span title={new Date(inv.last_sync_at).toLocaleString('pt-BR')}>
              {timeAgo(inv.last_sync_at)}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function StatChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white/[0.03] rounded-lg p-2 text-center border border-white/[0.04]">
      <div className="text-[8px] text-white/20 uppercase font-black tracking-widest mb-0.5">{label}</div>
      <div className="text-xs font-black text-white">{value}</div>
    </div>
  )
}

function CapBadge({ label, icon, color = 'text-copper bg-copper/10' }: {
  label: string; icon: React.ReactNode; color?: string
}) {
  return (
    <span className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-widest ${color}`}>
      {icon} {label}
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLOR[status] || 'text-white/30 bg-white/5'
  const label = STATUS_LABEL[status] || status
  return (
    <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-widest ${cls}`}>
      {label}
    </span>
  )
}

// ── Inversor Wizard ───────────────────────────────────────────────────────────

function InversorWizard({ platforms, onClose, onSaved }: {
  platforms: Platform[]
  onClose: () => void
  onSaved: () => void
}) {
  const [step, setStep] = useState<'mode' | 'platform' | 'form' | 'validating' | 'meta'>('mode')
  const [mode, setMode] = useState<'api' | 'manual'>('api')
  const [platform, setPlatform] = useState<Platform | null>(null)
  const [form, setForm] = useState<Record<string, string>>({})
  const [meta, setMeta] = useState<Record<string, string>>({ alias: '', location: '', nominal_power_kw: '', install_date: '' })
  const [validation, setValidation] = useState<any>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const qc = useQueryClient()

  const setF = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(p => ({ ...p, [k]: e.target.value }))
  const setM = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setMeta(p => ({ ...p, [k]: e.target.value }))

  async function doValidate() {
    setStep('validating')
    setError('')
    try {
      const result = await api.post('/inversores/validate', { platform_slug: platform!.slug, ...form }).then(r => r.data)
      setValidation(result)
      setStep('meta')
    } catch (e: any) {
      setError(e.message || 'Erro ao validar credenciais')
      setStep('form')
    }
  }

  async function doSave() {
    setSaving(true)
    setError('')
    try {
      await api.post('/inversores', {
        platform_slug: platform?.slug || '',
        mode,
        ...form,
        ...meta,
        nominal_power_kw: parseFloat(meta.nominal_power_kw || '0'),
        plant_id:   validation?.plant_id  || form.plant_id  || '',
        plant_name: validation?.plant_name || '',
        plant_meta: validation?.plant_meta || {},
        devaddr:    validation?.devaddr    || form.devaddr   || '1',
      })
      onSaved()
    } catch (e: any) {
      setError(e.message || 'Erro ao salvar')
    } finally {
      setSaving(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[200] flex items-center justify-end bg-void/80 backdrop-blur-sm"
    >
      <motion.div
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 28, stiffness: 280 }}
        className="w-full max-w-lg h-full bg-[#0D1117] border-l border-white/10 flex flex-col shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-copper/10 border border-copper/20">
              <Zap size={18} className="text-copper" />
            </div>
            <div>
              <h2 className="text-sm font-black text-white uppercase tracking-tight">Novo Inversor</h2>
              <p className="text-[9px] text-white/30 font-bold uppercase tracking-widest">
                {step === 'mode' ? 'Escolha o modo' :
                 step === 'platform' ? 'Selecione a plataforma' :
                 step === 'form' ? `Credenciais · ${platform?.name}` :
                 step === 'validating' ? 'Validando...' :
                 'Informações do inversor'}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-lg text-white/30 transition-all">
            <X size={18} />
          </button>
        </div>

        {/* Steps indicator */}
        <div className="flex items-center gap-1 px-6 py-3 border-b border-white/[0.03]">
          {['Modo', 'Plataforma', 'Credenciais', 'Detalhes'].map((s, i) => {
            const stepIdx = ['mode', 'platform', 'form', 'meta'].indexOf(step)
            const done = i < stepIdx
            const active = i === stepIdx
            return (
              <div key={s} className="flex items-center gap-1 flex-1">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-black transition-all ${
                  done ? 'bg-teal-500 text-void' : active ? 'bg-copper text-void' : 'bg-white/5 text-white/20'
                }`}>
                  {done ? <Check size={10} /> : i + 1}
                </div>
                <span className={`text-[8px] font-black uppercase tracking-widest hidden sm:block ${active ? 'text-copper' : 'text-white/20'}`}>
                  {s}
                </span>
                {i < 3 && <div className="h-[1px] flex-1 bg-white/5 mx-1" />}
              </div>
            )
          })}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 custom-scrollbar">

          {/* Step: Mode */}
          {step === 'mode' && (
            <div className="space-y-3">
              <p className="text-[10px] text-white/40 uppercase font-black tracking-widest">Como este inversor será alimentado?</p>
              {[
                {
                  id: 'api', icon: Wifi, color: 'text-teal-400',
                  title: 'Integração via API',
                  desc: 'Puxa dados automaticamente da plataforma do datalogger. ShineMonitor, Growatt, Solarman e mais.',
                },
                {
                  id: 'manual', icon: Settings, color: 'text-blue-400',
                  title: 'Alimentação Manual',
                  desc: 'Você preenche os dados de geração manualmente. Útil para inversores sem conectividade ou marcas não suportadas.',
                },
              ].map(m => (
                <button
                  key={m.id}
                  onClick={() => setMode(m.id as any)}
                  className={`w-full text-left p-4 rounded-xl border transition-all ${
                    mode === m.id
                      ? 'border-copper/50 bg-copper/5'
                      : 'border-white/5 bg-white/[0.02] hover:border-white/10'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <m.icon size={18} className={m.color} />
                    <div>
                      <div className="text-sm font-black text-white">{m.title}</div>
                      <div className="text-[10px] text-white/40 mt-1">{m.desc}</div>
                    </div>
                    {mode === m.id && <Check size={16} className="text-copper ml-auto mt-0.5" />}
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Step: Platform (API mode only) */}
          {step === 'platform' && mode === 'api' && (
            <div className="space-y-3">
              <p className="text-[10px] text-white/40 uppercase font-black tracking-widest">
                Qual app o cliente usa para ver a geração?
              </p>
              {platforms.map(p => (
                <button
                  key={p.slug}
                  onClick={() => setPlatform(p)}
                  className={`w-full text-left p-4 rounded-xl border transition-all ${
                    platform?.slug === p.slug
                      ? 'border-copper/50 bg-copper/5'
                      : 'border-white/5 bg-white/[0.02] hover:border-white/10'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <span className="text-xl">{PLATFORM_ICON[p.slug]}</span>
                    <div className="flex-1">
                      <div className="text-sm font-black text-white">{p.name}</div>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {p.app_names.map(a => (
                          <span key={a} className="text-[8px] px-1.5 py-0.5 rounded bg-white/5 text-white/40 font-bold">{a}</span>
                        ))}
                      </div>
                      <div className="text-[9px] text-white/30 mt-1">{p.market_coverage}</div>
                    </div>
                    {platform?.slug === p.slug && <Check size={16} className="text-copper" />}
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Step: Platform (Manual) */}
          {step === 'platform' && mode === 'manual' && (
            <div className="space-y-4">
              <p className="text-[10px] text-white/40 uppercase font-black tracking-widest">
                Qual a marca do inversor? (opcional)
              </p>
              <input
                className="w-full bg-white/5 border border-white/10 rounded-xl h-11 px-4 text-sm text-white outline-none focus:border-copper/60 transition-all"
                placeholder="Ex: Fronius, Solis, Canadian, ABB..."
                onChange={e => setForm(p => ({ ...p, brand: e.target.value }))}
              />
              <p className="text-[9px] text-white/30">
                No modo manual você não precisa de credenciais. Os dados serão inseridos manualmente.
              </p>
            </div>
          )}

          {/* Step: Credentials form */}
          {step === 'form' && platform && (
            <div className="space-y-4">
              {platform.fields_form.map(field => (
                <div key={field.key} className="space-y-1.5">
                  <label className="text-[10px] font-black uppercase tracking-widest text-text-muted">
                    {field.label}
                    {field.required && <span className="text-copper ml-1">*</span>}
                  </label>
                  <input
                    type={field.type}
                    required={field.required}
                    className="w-full bg-white/5 border border-white/10 rounded-xl h-11 px-4 text-sm text-white outline-none focus:border-copper/60 transition-all font-mono"
                    onChange={setF(field.key)}
                  />
                  {field.hint && (
                    <p className="text-[9px] text-white/25 font-medium">{field.hint}</p>
                  )}
                </div>
              ))}
              {error && (
                <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-400 font-bold">
                  <AlertTriangle size={12} className="inline mr-2" />{error}
                </div>
              )}
            </div>
          )}

          {/* Step: Validating */}
          {step === 'validating' && (
            <div className="flex flex-col items-center justify-center h-48 gap-4">
              <Loader2 size={32} className="animate-spin text-copper" />
              <div className="text-center">
                <p className="text-sm font-black text-white">Conectando à plataforma...</p>
                <p className="text-[10px] text-white/30 mt-1">Autenticando e descobrindo dispositivos</p>
              </div>
            </div>
          )}

          {/* Step: Meta */}
          {step === 'meta' && (
            <div className="space-y-4">
              {validation && (
                <div className="p-4 rounded-xl bg-teal-500/10 border border-teal-500/20">
                  <div className="flex items-center gap-2 mb-2">
                    <Check size={14} className="text-teal-400" />
                    <span className="text-xs font-black text-teal-400 uppercase">Conexão validada</span>
                  </div>
                  {validation.plant_name && (
                    <div className="text-[10px] text-white/50">Planta: <span className="text-white font-bold">{validation.plant_name}</span></div>
                  )}
                  {validation.devices?.length > 0 && (
                    <div className="text-[10px] text-white/50 mt-1">
                      {validation.devices.length} dispositivo(s) encontrado(s)
                    </div>
                  )}
                </div>
              )}

              {[
                { key: 'alias', label: 'Nome do Inversor *', type: 'text', placeholder: 'Ex: Usina Guarulhos Norte' },
                { key: 'location', label: 'Localização', type: 'text', placeholder: 'Ex: Guarulhos, SP' },
                { key: 'nominal_power_kw', label: 'Potência Nominal (kWp)', type: 'number', placeholder: '0.0' },
                { key: 'install_date', label: 'Data de Instalação', type: 'date', placeholder: '' },
              ].map(f => (
                <div key={f.key} className="space-y-1.5">
                  <label className="text-[10px] font-black uppercase tracking-widest text-text-muted">{f.label}</label>
                  <input
                    type={f.type}
                    placeholder={f.placeholder}
                    className="w-full bg-white/5 border border-white/10 rounded-xl h-11 px-4 text-sm text-white outline-none focus:border-copper/60 transition-all"
                    onChange={setM(f.key)}
                  />
                </div>
              ))}

              {error && (
                <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-400 font-bold">
                  <AlertTriangle size={12} className="inline mr-2" />{error}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer nav */}
        <div className="p-6 border-t border-white/5 flex items-center gap-3">
          {step !== 'mode' && step !== 'validating' && (
            <Button
              variant="outline"
              className="flex-1 border-white/10 text-white/40 h-11 font-bold text-xs"
              onClick={() => {
                if (step === 'meta') setStep('form')
                else if (step === 'form') setStep(mode === 'api' ? 'platform' : 'platform')
                else if (step === 'platform') setStep('mode')
              }}
            >
              Voltar
            </Button>
          )}

          {step === 'mode' && (
            <Button
              className="flex-1 bg-copper hover:bg-copper/80 text-void font-black text-xs uppercase tracking-widest h-11"
              onClick={() => setStep('platform')}
            >
              Continuar <ChevronRight size={14} className="ml-1" />
            </Button>
          )}

          {step === 'platform' && (
            <Button
              className="flex-1 bg-copper hover:bg-copper/80 text-void font-black text-xs uppercase tracking-widest h-11"
              disabled={mode === 'api' && !platform}
              onClick={() => {
                if (mode === 'manual') { setStep('meta') }
                else setStep('form')
              }}
            >
              Continuar <ChevronRight size={14} className="ml-1" />
            </Button>
          )}

          {step === 'form' && (
            <Button
              className="flex-1 bg-copper hover:bg-copper/80 text-void font-black text-xs uppercase tracking-widest h-11"
              onClick={doValidate}
            >
              Validar Conexão <Wifi size={14} className="ml-1" />
            </Button>
          )}

          {step === 'meta' && (
            <Button
              className="flex-1 bg-teal-600 hover:bg-teal-500 text-white font-black text-xs uppercase tracking-widest h-11"
              onClick={doSave}
              disabled={saving || !meta.alias}
            >
              {saving ? <Loader2 size={14} className="animate-spin mr-2" /> : <Check size={14} className="mr-2" />}
              Salvar Inversor
            </Button>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}
