import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { TrendingUp, TrendingDown, AlertTriangle, CheckCircle, Clock, BarChart3, DollarSign, Briefcase, Target, Activity, HardHat } from 'lucide-react'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import DashboardHeader from '../components/DashboardHeader'
import './Dashboard.css'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const AMBER  = '#F59E0B'
const GLASS  = 'rgba(255,255,255,0.04)'
const PIE_COLORS = [COPPER, TEAL, '#3B82F6', '#8B5CF6', '#10B981', RED, AMBER]

async function fetchKPIs(period: string, project: string) {
  const params = new URLSearchParams()
  if (period)  params.append('period', period)
  if (project) params.append('project_filter', project)
  const r = await fetch(`/api/dashboard/kpis?${params}`, { credentials: 'include' })
  if (!r.ok) throw new Error('Falha ao carregar KPIs')
  return r.json()
}

function KPICard({ title, value, sub, icon: Icon, trend, color = COPPER, trendType = 'neutral' }: {
  title: string; value: string; sub?: string
  icon: React.ElementType; trend?: string; color?: string; trendType?: 'positive'|'negative'|'neutral'
}) {
  return (
    <div style={{ background: GLASS, border: '1px solid rgba(201,139,42,0.15)', borderRadius: 12 }}
         className="p-5 flex flex-col gap-2 glass-panel transition-all hover:border-[#C98B2A]/50 group">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-text-muted uppercase tracking-widest font-bold">{title}</span>
        <div className="p-2 rounded-lg bg-[#C98B2A]/10 group-hover:bg-[#C98B2A]/20 transition-colors">
          <Icon size={16} style={{ color }} />
        </div>
      </div>
      <div className="font-display text-2xl font-bold mt-1 text-white">{value}</div>
      {sub && (
        <div className="flex items-center gap-1 text-[10px] font-mono whitespace-nowrap overflow-hidden text-ellipsis">
          {trendType === 'positive' && <TrendingUp size={10} style={{ color: TEAL }} />}
          {trendType === 'negative' && <TrendingDown size={10} style={{ color: RED }} />}
          {trendType === 'neutral' && <Activity size={10} style={{ color: '#888' }} />}
          <span className="font-bold mr-1" style={{ color: trendType === 'positive' ? TEAL : trendType === 'negative' ? RED : '#888' }}>
            {trend}
          </span>
          <span className="text-text-muted opacity-50">{sub}</span>
        </div>
      )}
    </div>
  )
}

const PERIOD_OPTIONS = [
  { value: 'all',   label: 'Tudo' },
  { value: 'month', label: 'Mês atual' },
  { value: 'quarter', label: 'Trimestre' },
  { value: 'year',  label: 'Ano' },
]

export default function Dashboard() {
  const [period, setPeriod]   = useState('all')
  const [project, setProject] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard-kpis', period, project],
    queryFn:  () => fetchKPIs(period, project),
    staleTime: 5 * 60_000,
    gcTime:    30 * 60_000,
    refetchOnWindowFocus: false,
  })

  const projectOptions: string[] = data?.project_filter_options ?? []

  if (isLoading) return (
    <div className="flex flex-col gap-6 animate-pulse p-6">
      <div className="h-48 bg-white/5 rounded-xl mb-4" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_,i) => (
          <div key={i} className="h-32 bg-white/5 rounded-xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-4">
        <div className="lg:col-span-2 h-80 bg-white/5 rounded-xl" />
        <div className="h-80 bg-white/5 rounded-xl" />
      </div>
    </div>
  )

  if (error) return (
    <div className="p-10 flex flex-col items-center justify-center text-center gap-4">
      <div className="p-4 rounded-full bg-red-500/10 border border-red-500/20">
        <AlertTriangle size={48} className="text-red-500" />
      </div>
      <div>
        <h2 className="text-xl font-bold text-white mb-1">Erro na Telemetria</h2>
        <p className="text-text-muted text-sm">Não foi possível estabelecer conexão com o servidor de dados.</p>
      </div>
      <button 
        onClick={() => window.location.reload()}
        className="mt-2 px-6 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-500 rounded-lg text-sm font-bold transition-all border border-red-500/30"
      >
        Tentar Reconectar
      </button>
    </div>
  )

  const kpis = data ?? {}

  return (
    <div className="flex flex-col gap-6 pb-20">
      {/* Premium Header Banner */}
      <DashboardHeader 
        contratosAtivos={kpis.contratos_ativos ?? 0}
        avancoGeral={kpis.avanco_geral_fmt ?? '0.0%'}
        valorTcv={kpis.valor_tcv_fmt ?? 'R$ 0,00'}
      />

      {/* Grid Filtros */}
      <div className="flex flex-wrap items-center justify-end gap-3 -mt-2">
        <div className="flex items-center gap-2 group">
          <Clock size={12} className="text-[#C98B2A] opacity-50" />
          <select value={period} onChange={e => setPeriod(e.target.value)}
            className="bg-[#0b1412] border border-[#C98B2A]/20 text-[#e2c87a] rounded-lg px-3 py-1.5 text-xs font-mono outline-none focus:border-[#C98B2A] transition-all cursor-pointer hover:bg-[#0e1a17]">
            {PERIOD_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        {projectOptions.length > 0 && (
          <div className="flex items-center gap-2">
            <Briefcase size={12} className="text-[#C98B2A] opacity-50" />
            <select value={project} onChange={e => setProject(e.target.value)}
              className="bg-[#0b1412] border border-[#C98B2A]/20 text-[#e2c87a] rounded-lg px-3 py-1.5 text-xs font-mono outline-none focus:border-[#C98B2A] transition-all cursor-pointer hover:bg-[#0e1a17]">
              <option value="">TODOS OS PROJETOS</option>
              {projectOptions.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        )}
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard title="Financeiro" value={kpis.valor_tcv_fmt ?? 'R$ 0,00'} icon={DollarSign}
          trend="+4.2%" trendType="positive" sub="carteira" />
        <KPICard title="Operacional" value={String(kpis.total_contratos ?? 0)} icon={HardHat}
          sub={`${kpis.contratos_ativos ?? 0} ativos`} trend="Live" color={TEAL} />
        <KPICard title="Velocidade" value={kpis.avanco_geral_fmt ?? '0.0%'} icon={TrendingUp}
           trend="+0.8%" trendType="positive" sub="avg speed" />
        <KPICard title="Sinal Crítico" value={String(kpis.atividades_criticas_count ?? 0)} icon={AlertTriangle}
          color={kpis.atividades_criticas_atrasadas > 0 ? RED : COPPER}
          trend={kpis.atividades_criticas_atrasadas > 0 ? 'CRÍTICO' : 'ESTÁVEL'} 
          trendType={kpis.atividades_criticas_atrasadas > 0 ? 'negative' : 'neutral'}
          sub="atrasos" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Faturamento por cliente - Main Chart */}
        <div className="lg:col-span-2 glass-panel chart-enter delay-300 p-6 rounded-xl border border-white/5">
          <div className="flex flex-col gap-1 mb-10">
            <h2 className="font-display text-xl font-bold text-white tracking-tight uppercase">Alocação de Volume</h2>
            <div className="w-12 h-1 bg-[#C98B2A] rounded-full" />
          </div>
          <div className="h-[320px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={kpis.faturamento_por_cliente} layout="vertical" margin={{ left: 10, right: 30, top: 0, bottom: 0 }}>
                <XAxis type="number" hide />
                <YAxis dataKey="name" type="category" tick={{ fill: '#888', fontSize: 10, fontWeight: 'bold' }} width={120} axisLine={false} tickLine={false} />
                <Tooltip 
                  cursor={{ fill: 'rgba(255,255,255,0.02)' }}
                  contentStyle={{ background: '#081210', border: '1px solid #C98B2A', borderRadius: 6, fontSize: 12 }}
                  itemStyle={{ color: '#fff' }}
                  labelStyle={{ color: '#888', marginBottom: 4 }}
                />
                <Bar dataKey="value" fill={COPPER} radius={[0, 4, 4, 0]} barSize={24}>
                  {kpis.faturamento_por_cliente?.map((_: any, index: number) => (
                    <Cell key={`cell-${index}`} fillOpacity={1 - (index * 0.08)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Status contratos - Donut */}
        <div className="glass-panel chart-enter delay-400 p-6 rounded-xl border border-white/5 flex flex-col items-center">
          <div className="w-full text-left mb-6">
            <h2 className="font-display text-xl font-bold text-white tracking-tight uppercase">Status Portfolio</h2>
            <div className="w-10 h-1 bg-teal-500 rounded-full" />
          </div>
          <div className="relative w-full h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={kpis.status_contratos_dist} dataKey="value" nameKey="name" cx="50%" cy="50%" 
                  innerRadius={70} outerRadius={90} paddingAngle={2} stroke="none">
                  {kpis.status_contratos_dist?.map((_: any, i: number) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#081210', border: '1px solid #C98B2A', borderRadius: 6, fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none">
              <div className="font-display text-4xl font-bold text-white">{kpis.total_contratos ?? 0}</div>
              <div className="text-[10px] text-text-muted uppercase tracking-widest font-bold">Total</div>
            </div>
          </div>
          {/* Legend */}
          <div className="w-full grid grid-cols-1 gap-2 mt-6">
            {kpis.status_contratos_dist?.map((item: any, i: number) => (
              <div key={item.name} className="flex items-center justify-between text-[11px] p-2 bg-[#0e1a17]/50 rounded-lg border border-white/5 hover:border-[#C98B2A]/20 transition-all">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                  <span className="text-text-muted uppercase font-bold tracking-tight">{item.name}</span>
                </div>
                <span className="font-mono font-bold text-white">{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Contratos progress */}
      {kpis.contratos_progress && kpis.contratos_progress.length > 0 && (
        <div className="glass-panel animate-enter delay-400 p-8 rounded-xl border border-white/5">
          <div className="flex items-center justify-between mb-8">
            <div className="flex flex-col gap-1">
              <h2 className="font-display text-xl font-bold text-white tracking-tight uppercase">Radar de Evolução</h2>
              <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">Acompanhamento de Obras Ativas</p>
            </div>
            <div className="p-3 rounded-full bg-[#C98B2A]/10 border border-[#C98B2A]/20">
              <Activity size={20} className="text-[#C98B2A]" />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {kpis.contratos_progress.map((c: any) => (
              <div key={c.contrato} className="bg-[#0b1412] p-5 rounded-xl border border-white/5 hover:border-[#C98B2A]/40 transition-all group relative overflow-hidden">
                {/* Progress Background Hint */}
                <div 
                  className="absolute left-0 bottom-0 top-0 bg-[#C98B2A]/5 pointer-events-none transition-all duration-1000"
                  style={{ width: `${Math.min(c.pct, 100)}%` }}
                />
                
                <div className="relative z-10">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2 mb-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-[#C98B2A]" />
                        <span className="text-xs font-mono font-black text-[#C98B2A] tracking-tighter uppercase">{c.contrato}</span>
                      </div>
                      <span className="text-[11px] text-white font-bold truncate max-w-[180px] uppercase tracking-tight">{c.cliente}</span>
                      <span className="text-[9px] text-text-muted truncate max-w-[180px] font-mono mt-0.5">{c.projeto}</span>
                    </div>
                    <div className="text-right">
                      <span className="font-mono text-xl font-black text-white">{c.pct}</span>
                      <span className="text-[10px] text-[#C98B2A] font-bold ml-0.5">%</span>
                    </div>
                  </div>
                  <div className="relative w-full h-1.5 bg-void/50 rounded-full overflow-hidden border border-white/5">
                    <div 
                      className="absolute top-0 left-0 h-full bg-gradient-to-r from-[#8B6119] to-[#C98B2A] transition-all duration-1000 shadow-[0_0_10px_rgba(201,139,42,0.3)]"
                      style={{ width: `${Math.min(c.pct, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
