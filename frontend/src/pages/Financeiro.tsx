import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend,
  BarChart, Bar,
} from 'recharts'
import {
  DollarSign, TrendingUp, Wallet, ShieldCheck, Activity,
  AlertTriangle, Calculator, PieChart, FileText, Sparkles,
  ArrowUpRight, Building2, Info, X,
} from 'lucide-react'
import './Dashboard.css'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const AMBER  = '#F59E0B'
const BORDER = '1px solid rgba(201,139,42,0.15)'

async function apiFetch(path: string) {
  const r = await fetch(path, { credentials: 'include' })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

function fmtBRL(v: any) {
  const n = typeof v === 'number' ? v : parseFloat(String(v || '0').replace(/[^\d.,-]/g, '').replace(',', '.'))
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(isNaN(n) ? 0 : n)
}

function SCurveTip({ active, payload, label }: any) {
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

function InsightCard({ insight }: { insight: any }) {
  const colors: Record<string, string> = {
    High: RED, Medium: AMBER, Low: TEAL,
  }
  const color = colors[insight.priority] ?? TEAL
  return (
    <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5 flex gap-4">
      <div className="w-1 rounded-full shrink-0 self-stretch" style={{ background: color }} />
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 mb-2">
          <span className="text-xs font-black text-white leading-tight">{insight.title}</span>
          <span className="text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-md border shrink-0"
            style={{ color, borderColor: `${color}30`, background: `${color}10` }}>
            {insight.priority}
          </span>
        </div>
        <p className="text-[10px] text-white/50 leading-relaxed">{insight.body}</p>
      </div>
    </div>
  )
}

export default function Financeiro() {
  const [searchParams, setSearchParams] = useSearchParams()
  const contrato = searchParams.get('contrato') ?? ''
  const [activeTab, setActiveTab] = useState<'overview' | 'scurve' | 'bycat' | 'evm'>('overview')
  const [noticeDismissed, setNoticeDismissed] = useState(() => localStorage.getItem('fin_notice_v1') === '1')
  const dismissNotice = () => { localStorage.setItem('fin_notice_v1', '1'); setNoticeDismissed(true) }

  const { data, isLoading } = useQuery({
    queryKey: ['fin-exec', contrato],
    queryFn:  () => contrato
      ? apiFetch(`/api/financeiro/${contrato}`)
      : apiFetch('/api/financeiro'),
    staleTime: 3 * 60_000,
    refetchOnWindowFocus: true,
  })

  const hasFinData = !contrato && ((data?.por_contrato?.length ?? 0) > 0)
  const { data: insightsData, isLoading: insightsLoading } = useQuery({
    queryKey: ['fin-exec-insights'],
    queryFn:  () => apiFetch('/api/financeiro/insights'),
    staleTime: 20 * 60_000,
    enabled: hasFinData,
  })

  const { data: contratosList } = useQuery({
    queryKey: ['hub-contratos'],
    queryFn:  () => apiFetch('/api/hub/contratos'),
    staleTime: Infinity,
  })

  const d = data || {}
  const kpis           = d.kpis ?? {}
  const scurve: any[]  = d.scurve ?? []
  const bycat: any[]   = d.by_categoria ?? []
  const evm            = d.evm ?? {}
  const porContrato: any[] = contrato ? [] : (d.por_contrato ?? [])
  const contratos: any[]   = contratosList?.contratos ?? []

  const totalPrev = kpis.total_previsto_raw ?? 0
  const totalExec = kpis.total_executado_raw ?? 0
  const burnPct   = totalPrev > 0 ? Math.min(100, (totalExec / totalPrev) * 100) : 0
  const insights: any[] = insightsData?.insights ?? []

  return (
    <div className="flex flex-col gap-6 animate-enter">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
            <DollarSign size={24} className="text-copper" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-white uppercase tracking-tight">Inteligência Financeira</h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">Visão Executiva da Carteira</p>
          </div>
        </div>
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
          <button onClick={() => setSearchParams({})}
            className={`px-4 py-2 rounded-lg text-xs font-black uppercase tracking-widest transition-all whitespace-nowrap border ${
              !contrato ? 'bg-copper text-void border-copper' : 'bg-white/5 text-text-muted border-white/5 hover:border-copper/40 hover:text-white'
            }`}>
            Todos
          </button>
          {contratos.map((c: any) => (
            <button key={c.contrato} onClick={() => setSearchParams({ contrato: c.contrato })}
              className={`px-4 py-2 rounded-lg text-xs font-black uppercase tracking-widest transition-all whitespace-nowrap border ${
                contrato === c.contrato ? 'bg-copper text-void border-copper' : 'bg-white/5 text-text-muted border-white/5 hover:border-copper/40 hover:text-white'
              }`}>
              {c.contrato}
            </button>
          ))}
        </div>
      </div>

      {/* Notice: CRUD is in Hub — dismissable */}
      {!noticeDismissed && (
        <div className="flex items-center gap-3 bg-copper/5 border border-copper/20 rounded-xl px-4 py-3">
          <Info size={14} className="text-copper shrink-0" />
          <p className="text-[10px] text-copper/80 flex-1">
            Para lançar custos, acesse <strong>Hub de Operações → aba Financeiro</strong> dentro de cada contrato.
            Esta tela é exclusiva para visualização executiva e inteligência de carteira.
          </p>
          <button onClick={dismissNotice} className="p-1 rounded hover:bg-copper/10 text-copper/40 hover:text-copper shrink-0" title="Dispensar">
            <X size={13} />
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="h-28 bg-white/[0.03] rounded-2xl border border-white/5 animate-pulse" />)}
        </div>
      ) : (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="glass-panel p-5 border-white/5">
              <div className="flex items-center gap-2 mb-3"><div className="p-1.5 rounded-lg bg-white/5"><Wallet size={14} className="text-white/60" /></div><span className="text-[9px] font-black uppercase tracking-widest text-white/40">Total Previsto</span></div>
              <div className="text-xl font-black font-mono text-white">{kpis.total_previsto ?? fmtBRL(totalPrev)}</div>
              <div className="text-[9px] text-white/20 mt-1">{kpis.total_itens ?? 0} itens</div>
            </div>
            <div className="glass-panel p-5 border-white/5">
              <div className="flex items-center gap-2 mb-3"><div className="p-1.5 rounded-lg bg-teal-500/10"><TrendingUp size={14} className="text-teal-400" /></div><span className="text-[9px] font-black uppercase tracking-widest text-white/40">Executado</span></div>
              <div className="text-xl font-black font-mono text-teal-400">{kpis.total_executado ?? fmtBRL(totalExec)}</div>
              <div className="text-[9px] text-teal-400/40 mt-1">{kpis.concluidos ?? 0} concluídos</div>
            </div>
            <div className="glass-panel p-5 border-white/5">
              <div className="flex items-center gap-2 mb-3"><div className="p-1.5 rounded-lg bg-copper/10"><ShieldCheck size={14} className="text-copper" /></div><span className="text-[9px] font-black uppercase tracking-widest text-white/40">Saldo</span></div>
              <div className="text-xl font-black font-mono text-copper">{kpis.saldo ?? fmtBRL(totalPrev - totalExec)}</div>
              <div className="text-[9px] text-white/20 mt-1">Remanescente</div>
            </div>
            <div className="glass-panel p-5 border-white/5">
              <div className="flex items-center gap-2 mb-3"><div className="p-1.5 rounded-lg bg-amber-500/10"><Activity size={14} className="text-amber-400" /></div><span className="text-[9px] font-black uppercase tracking-widest text-white/40">Burn Rate</span></div>
              <div className="text-xl font-black font-mono" style={{ color: burnPct > 90 ? RED : burnPct > 70 ? AMBER : TEAL }}>{burnPct.toFixed(1)}%</div>
              <div className="h-1.5 w-full bg-white/5 rounded-full mt-2 overflow-hidden">
                <div className="h-full rounded-full transition-all duration-700" style={{ width: `${burnPct}%`, background: burnPct > 90 ? RED : burnPct > 70 ? AMBER : TEAL }} />
              </div>
            </div>
          </div>

          {/* AI Insights — only on aggregate view */}
          {!contrato && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-copper" />
                <span className="text-xs font-black uppercase tracking-widest text-white">Inteligência Executiva</span>
                {insightsLoading && <span className="text-[9px] text-white/30 animate-pulse">Gerando análise...</span>}
              </div>
              {insights.length > 0 ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                  {insights.map((ins: any, i: number) => <InsightCard key={i} insight={ins} />)}
                </div>
              ) : !insightsLoading ? (
                <div className="glass-panel p-6 text-center border-white/5 text-white/20 text-sm">Sem dados financeiros suficientes para análise</div>
              ) : null}
            </div>
          )}

          {/* Tabs */}
          <div className="flex items-center gap-1 bg-white/[0.02] border border-white/5 p-1 rounded-xl w-fit">
            {[
              { id: 'overview', label: !contrato ? 'Por Contrato' : 'Visão Geral', icon: !contrato ? Building2 : FileText },
              { id: 'scurve',   label: 'Curva-S',     icon: TrendingUp },
              { id: 'bycat',    label: 'Por Categoria', icon: PieChart },
              { id: 'evm',      label: 'EVM',          icon: Calculator },
            ].map(t => (
              <button key={t.id} onClick={() => setActiveTab(t.id as any)}
                className={`px-4 py-2 rounded-lg flex items-center gap-2 text-[10px] font-black uppercase tracking-widest transition-all ${
                  activeTab === t.id ? 'bg-copper text-void shadow-lg' : 'text-text-muted hover:text-white'
                }`}>
                <t.icon size={13} /> {t.label}
              </button>
            ))}
          </div>

          {/* Per-contract comparison (all contracts view) */}
          {activeTab === 'overview' && !contrato && (
            <div className="flex flex-col gap-3 animate-enter">
              {porContrato.length === 0 ? (
                <div className="glass-panel p-16 text-center border-white/5 text-white/20">Sem dados financeiros cadastrados</div>
              ) : (
                <>
                  {/* Bar chart comparison */}
                  <div className="glass-panel p-8 border-white/5">
                    <h3 className="text-xs font-black uppercase tracking-widest text-copper mb-1">Previsto vs. Executado por Contrato</h3>
                    <p className="text-[10px] text-text-muted mb-8">Comparativo orçamentário da carteira completa</p>
                    <div className="h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={porContrato.map(c => ({
                          contrato: c.contrato.length > 12 ? c.contrato.slice(0, 12) + '…' : c.contrato,
                          Previsto: c.total_previsto_raw ?? 0,
                          Executado: c.total_executado_raw ?? 0,
                        }))} margin={{ left: 20, right: 20 }}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                          <XAxis dataKey="contrato" axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 10, fontWeight: 700 }} />
                          <YAxis axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9 }} tickFormatter={v => `R$${(v/1000).toFixed(0)}k`} />
                          <Tooltip contentStyle={{ background: '#0d1117', border: BORDER, borderRadius: 12 }} formatter={(v: any) => fmtBRL(v)} />
                          <Legend formatter={v => <span className="text-[9px] font-black uppercase tracking-widest text-white/40">{v}</span>} iconType="circle" iconSize={8} />
                          <Bar dataKey="Previsto"  fill={COPPER} radius={[4, 4, 0, 0]} barSize={22} />
                          <Bar dataKey="Executado" fill={TEAL}   radius={[4, 4, 0, 0]} barSize={22} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* Table */}
                  <div className="glass-panel border-white/5 overflow-hidden">
                    <table className="w-full">
                      <thead><tr className="bg-white/[0.02] border-b border-white/5">
                        <th className="text-left px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">Contrato</th>
                        <th className="text-right px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">Previsto</th>
                        <th className="text-right px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">Executado</th>
                        <th className="text-right px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">Burn</th>
                        <th className="text-right px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">CPI</th>
                        <th className="px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">Status</th>
                      </tr></thead>
                      <tbody className="divide-y divide-white/[0.02]">
                        {porContrato.map((r: any) => (
                          <tr key={r.contrato} className="hover:bg-white/[0.015] transition-colors cursor-pointer"
                            onClick={() => setSearchParams({ contrato: r.contrato })}>
                            <td className="px-5 py-3">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-white">{r.contrato}</span>
                                <ArrowUpRight size={11} className="text-white/20" />
                              </div>
                            </td>
                            <td className="px-5 py-3 text-right font-mono text-xs text-copper">{r.total_previsto}</td>
                            <td className="px-5 py-3 text-right font-mono text-xs text-teal-400">{r.total_executado}</td>
                            <td className="px-5 py-3 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <div className="w-16 h-1.5 bg-white/5 rounded-full overflow-hidden hidden sm:block">
                                  <div className="h-full rounded-full" style={{ width: `${Math.min(100, r.pct_executado)}%`, background: r.pct_executado > 90 ? RED : r.pct_executado > 70 ? AMBER : TEAL }} />
                                </div>
                                <span className="text-[10px] font-mono text-white/40">{r.pct_executado?.toFixed(1)}%</span>
                              </div>
                            </td>
                            <td className="px-5 py-3 text-right">
                              <span className="text-xs font-mono font-black" style={{ color: (r.cpi ?? 1) >= 1 ? TEAL : RED }}>{(r.cpi ?? 0).toFixed(2)}</span>
                            </td>
                            <td className="px-5 py-3">
                              {r.is_overrun
                                ? <span className="px-2 py-0.5 rounded-md text-[9px] font-black uppercase border bg-red-500/10 text-red-400 border-red-500/20">Estouro</span>
                                : <span className="px-2 py-0.5 rounded-md text-[9px] font-black uppercase border bg-teal-500/10 text-teal-400 border-teal-500/20">OK</span>
                              }
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Single contract overview */}
          {activeTab === 'overview' && contrato && (
            <div className="glass-panel p-8 border-white/5 animate-enter">
              <h3 className="text-xs font-black uppercase tracking-widest text-copper mb-6">Resumo — {contrato}</h3>
              {Object.keys(evm).length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {([
                    { label: 'CPI',  val: evm.CPI,  good: evm.CPI >= 1,  fmt: String(evm.CPI) },
                    { label: 'SPI',  val: evm.SPI,  good: evm.SPI >= 1,  fmt: String(evm.SPI) },
                    { label: 'TCPI', val: evm.TCPI, good: evm.TCPI <= 1, fmt: String(evm.TCPI) },
                    { label: 'EAC',  val: 1,        good: !evm.is_overrun, fmt: evm.EAC_fmt },
                    { label: 'VAC',  val: evm.VAC,  good: evm.VAC >= 0,  fmt: (evm.VAC >= 0 ? '+' : '-') + evm.VAC_fmt },
                    { label: 'BAC',  val: 1,        good: true,           fmt: evm.BAC_fmt },
                  ] as any[]).map(x => (
                    <div key={x.label} className="bg-white/[0.02] border border-white/5 rounded-xl p-4">
                      <div className="text-[9px] font-black uppercase tracking-widest text-white/40 mb-2">{x.label}</div>
                      <div className="text-lg font-black font-mono" style={{ color: x.good ? TEAL : RED }}>{x.fmt}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-white/20 text-sm text-center py-8">Sem dados EVM para este contrato</div>
              )}
            </div>
          )}

          {/* Curva-S */}
          {activeTab === 'scurve' && (
            <div className="glass-panel p-8 border-white/5 animate-enter">
              <h3 className="text-xs font-black uppercase tracking-widest text-copper mb-1">Curva-S Acumulada</h3>
              <p className="text-[10px] text-text-muted mb-8">Baseline planejada vs. execução real{contrato ? ` — ${contrato}` : ' (carteira total)'}</p>
              {scurve.length === 0 ? (
                <div className="h-64 flex items-center justify-center text-white/20 text-sm">Sem dados temporais suficientes</div>
              ) : (
                <div className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={scurve} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                      <defs>
                        <linearGradient id="exec_fp" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={COPPER} stopOpacity={0.12} /><stop offset="95%" stopColor={COPPER} stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="exec_fe" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={TEAL} stopOpacity={0.15} /><stop offset="95%" stopColor={TEAL} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                      <XAxis dataKey="data" axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9, fontWeight: 700 }} interval={Math.max(0, Math.floor(scurve.length / 8) - 1)} dy={10} />
                      <YAxis axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9, fontWeight: 700 }} tickFormatter={v => `R$${(v / 1000).toFixed(0)}k`} />
                      <Tooltip content={<SCurveTip />} />
                      <Legend formatter={v => <span className="text-[9px] font-black uppercase tracking-widest text-white/40">{v}</span>} iconType="circle" iconSize={8} />
                      <Area type="monotone" dataKey="previsto_acum"  stroke={COPPER} strokeWidth={2}   fill="url(#exec_fp)" name="Baseline Planejada" dot={false} />
                      <Area type="monotone" dataKey="executado_acum" stroke={TEAL}   strokeWidth={2.5} fill="url(#exec_fe)" name="Execução Real" dot={{ r: 3, fill: TEAL, strokeWidth: 0 }} activeDot={{ r: 5 }} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}

          {/* Por Categoria */}
          {activeTab === 'bycat' && (
            <div className="flex flex-col gap-4 animate-enter">
              <div className="glass-panel p-8 border-white/5">
                <h3 className="text-xs font-black uppercase tracking-widest text-copper mb-1">Distribuição por Categoria</h3>
                <p className="text-[10px] text-text-muted mb-8">Previsto vs. executado por categoria{contrato ? ` — ${contrato}` : ' (carteira total)'}</p>
                {bycat.length === 0 ? (
                  <div className="h-48 flex items-center justify-center text-white/20 text-sm">Sem dados</div>
                ) : (
                  <div className="h-[320px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={bycat} layout="vertical" margin={{ left: 20, right: 30 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(255,255,255,0.03)" />
                        <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9 }} tickFormatter={v => `R$${(v/1000).toFixed(0)}k`} />
                        <YAxis type="category" dataKey="categoria" width={130} axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 10, fontWeight: 700 }} />
                        <Tooltip contentStyle={{ background: '#0d1117', border: BORDER, borderRadius: 12 }} formatter={(v: any) => fmtBRL(v)} />
                        <Legend formatter={v => <span className="text-[9px] font-black uppercase tracking-widest text-white/40">{v}</span>} iconType="circle" iconSize={8} />
                        <Bar dataKey="previsto"  fill={COPPER} radius={[0, 4, 4, 0]} name="Previsto"  barSize={14} />
                        <Bar dataKey="executado" fill={TEAL}   radius={[0, 4, 4, 0]} name="Executado" barSize={14} />
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
          {activeTab === 'evm' && (
            <div className="flex flex-col gap-6 animate-enter">
              {Object.keys(evm).length === 0 ? (
                <div className="glass-panel p-20 text-center border-white/5">
                  <Calculator size={32} className="text-white/10 mx-auto mb-4" />
                  <p className="text-white/20 text-sm font-bold">Sem dados EVM suficientes</p>
                </div>
              ) : (
                <>
                  <div>
                    <div className="text-[9px] font-black uppercase tracking-widest text-white/30 mb-3">Índices de Desempenho{contrato ? ` — ${contrato}` : ' (carteira total)'}</div>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                      {([
                        { label: 'CPI',  fmt: String(evm.CPI),  good: evm.CPI >= 1 },
                        { label: 'SPI',  fmt: String(evm.SPI),  good: evm.SPI >= 1 },
                        { label: 'TCPI', fmt: String(evm.TCPI), good: evm.TCPI <= 1 },
                        { label: 'CV',   fmt: (evm.CV >= 0 ? '+' : '-') + evm.CV_fmt, good: evm.CV >= 0 },
                        { label: 'SV',   fmt: (evm.SV >= 0 ? '+' : '-') + evm.SV_fmt, good: evm.SV >= 0 },
                      ] as any[]).map(x => (
                        <div key={x.label} className="bg-white/[0.02] border border-white/5 rounded-xl p-4">
                          <div className="text-[9px] font-black uppercase tracking-widest text-white/40 mb-2">{x.label}</div>
                          <div className="text-lg font-black font-mono" style={{ color: x.good ? TEAL : RED }}>{x.fmt}</div>
                          <div className="text-[9px] mt-1" style={{ color: x.good ? TEAL : RED }}>{x.good ? 'OK' : 'Atenção'}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="glass-panel p-6 border-white/5">
                    <h3 className="text-[10px] font-black uppercase tracking-widest text-white/40 mb-6">Avanço Físico vs. Financeiro</h3>
                    <div className="space-y-5">
                      <div>
                        <div className="flex justify-between text-[9px] font-black uppercase tracking-widest mb-2"><span className="text-copper">Físico</span><span className="text-white">{evm.physical_pct}%</span></div>
                        <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden"><div className="h-full bg-copper rounded-full" style={{ width: `${evm.physical_pct}%` }} /></div>
                      </div>
                      <div>
                        <div className="flex justify-between text-[9px] font-black uppercase tracking-widest mb-2"><span className="text-teal-400">Financeiro</span><span className="text-white">{evm.cost_pct}%</span></div>
                        <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden"><div className="h-full bg-teal-500 rounded-full" style={{ width: `${evm.cost_pct}%` }} /></div>
                      </div>
                    </div>
                    {evm.is_overrun && (
                      <div className="mt-6 flex items-start gap-3 bg-red-500/5 border border-red-500/20 rounded-xl p-4">
                        <AlertTriangle size={16} className="text-red-400 shrink-0" />
                        <div>
                          <div className="text-xs font-black text-red-400 mb-1">Alerta de Estouro Orçamentário</div>
                          <div className="text-[10px] text-red-400/60">Projeção indica custo final {evm.VAC_fmt} acima do BAC. Revise eficiência de execução.</div>
                        </div>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
