import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { 
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, 
  ResponsiveContainer, AreaChart, Area, CartesianGrid, Legend, Cell
} from 'recharts'
import { 
  Plus, Trash2, Edit2, X, Check, DollarSign, TrendingUp, 
  ArrowDownLeft, ArrowUpRight, PieChart, Wallet, 
  ShieldCheck, Calculator, AlertTriangle, FileText,
  ChevronDown
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import './Dashboard.css'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

async function api(path: string, opts?: RequestInit) {
  const r = await fetch(path, { credentials: 'include', ...opts })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

function EVMGauge({ label, value, fmt, good, icon: Icon }: { label: string; value: number; fmt: string; good: boolean; icon: any }) {
  return (
    <div className="glass-panel p-5 border-white/5 relative overflow-hidden group">
      <div className="flex justify-between items-start mb-4">
         <div className={`p-2 rounded-lg bg-white/5 border border-white/5`}>
            <Icon size={18} style={{ color: good ? TEAL : RED }} />
         </div>
      </div>
      <div className="text-[10px] text-text-muted uppercase font-black tracking-widest mb-1">{label}</div>
      <div className="text-2xl font-bold mt-1" style={{ color: good ? TEAL : RED }}>{fmt}</div>
      {typeof value === 'number' && (
        <div className="text-[9px] mt-2 font-mono flex items-center gap-1.5" style={{ color: good ? TEAL : RED }}>
          {value >= 1 ? <TrendingUp size={10} /> : <AlertTriangle size={10} />}
          {value >= 1 ? 'Performance Positiva' : 'Abaixo do Baseline'}
        </div>
      )}
      <div className="absolute top-0 right-0 w-16 h-16 bg-white/[0.01] -rotate-45 translate-x-8 -translate-y-8" />
    </div>
  )
}

export default function Financeiro() {
  const [searchParams, setSearchParams] = useSearchParams()
  const contrato = searchParams.get('contrato') ?? ''
  const qc = useQueryClient()

  const [showForm, setShowForm]     = useState(false)
  const [editId, setEditId]         = useState<string|null>(null)
  const [form, setForm]             = useState<Record<string,any>>({ status: 'previsto' })
  const [activeTab, setActiveTab]   = useState<'cockpit'|'scurve'|'cashflow'|'evm'>('cockpit')

  const { data, isLoading } = useQuery({
    queryKey: ['financeiro', contrato],
    queryFn:  () => contrato ? api(`/api/financeiro/${contrato}`) : api('/api/financeiro'),
    staleTime: 30_000,
  })

  const { data: contratosList } = useQuery({
    queryKey: ['hub-contratos'],
    queryFn:  () => api('/api/hub/contratos'),
    staleTime: 60_000,
  })

  const createMut = useMutation({
    mutationFn: (body: any) => api(`/api/financeiro/${contrato}`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({queryKey:['financeiro',contrato]}); setShowForm(false); setForm({status:'previsto'}) },
  })

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id:string, body:any }) => api(`/api/financeiro/${id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({queryKey:['financeiro',contrato]}); setEditId(null) },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => api(`/api/financeiro/${id}`, { method:'DELETE' }),
    onSuccess: () => qc.invalidateQueries({queryKey:['financeiro',contrato]}),
  })

  const contratos: any[] = contratosList?.contratos ?? []
  const kpis    = data?.kpis ?? {}
  const scurve  = data?.scurve ?? []
  const bycat   = data?.by_categoria ?? []
  const evm     = data?.evm ?? {}
  const custos: any[] = data?.custos ?? []
  const cats: any[]   = data?.categorias ?? []
  const statuses: string[] = data?.status_options ?? []

  // Formatting 1:1
  const fmtCurrency = (v: any) => typeof v === 'string' ? v : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0)

  return (
    <div className="flex flex-col gap-6 animate-enter">
      {/* ── HEADER & SELECTOR ────────────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
            <DollarSign size={24} className="text-copper" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-white uppercase tracking-tight">Inteligência Financeira</h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">Auditoria de Capex & Opex (1:1)</p>
          </div>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
          <button
            onClick={() => setSearchParams({})}
            className={`px-4 py-2 rounded-lg text-xs font-black uppercase tracking-widest transition-all whitespace-nowrap border ${
              !contrato
                ? 'bg-copper text-void border-copper shadow-[0_0_20px_rgba(201,139,42,0.2)]'
                : 'bg-white/5 text-text-muted border-white/5 hover:border-copper/40 hover:text-white'
            }`}
          >
            Todos
          </button>
          {contratos.map((c: any) => (
            <button key={c.contrato}
              onClick={() => setSearchParams({ contrato: c.contrato })}
              className={`px-4 py-2 rounded-lg text-xs font-black uppercase tracking-widest transition-all whitespace-nowrap border ${
                contrato === c.contrato
                  ? 'bg-copper text-void border-copper shadow-[0_0_20px_rgba(201,139,42,0.2)]'
                  : 'bg-white/5 text-text-muted border-white/5 hover:border-copper/40 hover:text-white'
              }`}
            >
              {c.contrato}
            </button>
          ))}
        </div>
      </div>

      {!isLoading && (
        <>
          {/* ── KPI SECTION ───────────────────────────────────────────── */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label:'Budget Previsto', value: kpis.total_previsto, icon: Wallet, color: '#FFF' },
              { label:'Total Executado', value: kpis.total_executado, icon: TrendingUp, color: TEAL },
              { label:'Saldo Remanescente', value: kpis.saldo, icon: ShieldCheck, color: COPPER },
              { label:'Burn Rate %', value: `${kpis.pct_executado}%`, icon: Activity, color: RED },
            ].map((k, i) => (
              <div key={i} className="glass-panel p-5 border-white/5">
                <div className="flex justify-between items-start mb-4">
                   <div className="p-2 rounded-lg bg-white/5 border border-white/5">
                      <k.icon size={18} style={{ color: k.color }} />
                   </div>
                </div>
                <div className="text-[10px] text-text-muted uppercase font-black tracking-widest mb-1">{k.label}</div>
                <div className="text-xl font-bold text-white mb-1">{k.value}</div>
                <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden mt-2">
                   <div className="h-full bg-copper" style={{ width: k.label === 'Burn Rate %' ? k.value : '0%' }} />
                </div>
              </div>
            ))}
          </div>

          {/* ── TABS SELECTOR ─────────────────────────────────────────── */}
          <div className="flex items-center gap-1 bg-white/[0.02] border border-white/5 p-1 rounded-xl self-start">
            {[
              { id: 'cockpit', label: 'Lançamentos', icon: FileText },
              { id: 'scurve', label: 'S-Curve', icon: TrendingUp },
              { id: 'cashflow', label: 'Fluxo Mensal', icon: ArrowUpRight },
              { id: 'evm', label: 'Análise EVM', icon: PieChart },
            ].map(t => (
              <button 
                key={t.id} 
                onClick={() => setActiveTab(t.id as any)}
                className={`px-4 py-2 rounded-lg flex items-center gap-2 text-[10px] font-black uppercase tracking-widest transition-all ${
                  activeTab === t.id ? 'bg-copper text-void shadow-lg' : 'text-text-muted hover:text-white'
                }`}
              >
                <t.icon size={14} /> {t.label}
              </button>
            ))}
          </div>

          {/* ── SUB-PAGE CONTENT ──────────────────────────────────────── */}
          
          {/* COCKPIT (TRANSACTIONS) */}
          {activeTab === 'cockpit' && (
            <div className="flex flex-col gap-4 animate-enter">
              <div className="flex justify-between items-center">
                 <h2 className="text-[11px] font-black uppercase tracking-widest text-text-muted">Registro de Transações</h2>
                 <Button onClick={() => setShowForm(true)} className="bg-void border border-copper/40 hover:border-copper text-copper font-bold text-[10px] uppercase tracking-widest h-9 px-4">
                    <Plus size={16} className="mr-2" /> Novo Lançamento
                 </Button>
              </div>

              {showForm && (
                <div className="glass-panel p-6 border-copper/20 bg-copper/[0.02] animate-in slide-in-from-top duration-300">
                   <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-[9px] font-black uppercase tracking-wider text-text-muted">Categoria</label>
                        <select 
                          className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-[#e2c87a]"
                          onChange={e => setForm({...form, categoria_id: e.target.value})}
                        >
                           <option value="">Selecionar...</option>
                           {cats.map((c:any) => <option key={c.id} value={c.id}>{c.nome}</option>)}
                        </select>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[9px] font-black uppercase tracking-wider text-text-muted">Descrição</label>
                        <Input className="bg-void border-white/10 text-sm h-10" onChange={e => setForm({...form, descricao: e.target.value})} />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[9px] font-black uppercase tracking-wider text-text-muted">Valor Previsto</label>
                        <Input type="number" className="bg-void border-white/10 text-sm h-10" onChange={e => setForm({...form, valor_previsto: parseFloat(e.target.value)})} />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[9px] font-black uppercase tracking-wider text-text-muted">Valor Executado</label>
                        <Input type="number" className="bg-void border-white/10 text-sm h-10" onChange={e => setForm({...form, valor_executado: parseFloat(e.target.value)})} />
                      </div>
                   </div>
                   <div className="flex gap-2 mt-6">
                      <Button onClick={() => createMut.mutate(form)} className="bg-copper text-void font-bold text-xs">SALVAR</Button>
                      <Button onClick={() => setShowForm(false)} variant="outline" className="border-white/10 text-text-muted text-xs">CANCELAR</Button>
                   </div>
                </div>
              )}

              <div className="glass-panel border-white/5 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-white/[0.01] border-b border-white/5">
                        {['Categoria','Descrição','Previsto','Executado','Status','Data',''].map(h => (
                          <th key={h} className="px-5 py-4 text-[9px] font-black text-text-muted uppercase tracking-widest">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.02]">
                      {custos.map(r => (
                        <tr key={r.id} className="hover:bg-white/[0.02] transition-colors group">
                          <td className="px-5 py-4">
                            <span className="text-[10px] font-black uppercase text-white/40">{r.categoria_nome}</span>
                          </td>
                          <td className="px-5 py-4 text-xs font-bold text-white">{r.descricao}</td>
                          <td className="px-5 py-4 font-mono text-xs text-copper">{r.valor_previsto_fmt}</td>
                          <td className="px-5 py-4 font-mono text-xs text-teal-500">{r.valor_executado_fmt}</td>
                          <td className="px-5 py-4">
                            <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${
                              r.status === 'concluido' ? 'bg-teal-500/10 text-teal-500' : 'bg-copper/10 text-copper'
                            }`}>
                              {r.status}
                            </span>
                          </td>
                          <td className="px-5 py-4 font-mono text-[10px] text-text-muted">{r.data_custo}</td>
                          <td className="px-5 py-4">
                            <button onClick={() => deleteMut.mutate(r.id)} className="p-2 hover:bg-red-500/20 rounded text-red-500 transition-colors opacity-0 group-hover:opacity-100">
                              <Trash2 size={13} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {custos.length === 0 && (
                    <div className="p-20 text-center text-text-muted opacity-20 italic">Aguardando inserção de dados financeiros...</div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* S-CURVE */}
          {activeTab === 'scurve' && (
            <div className="glass-panel p-8 border-white/5 animate-enter">
              <div className="flex items-center justify-between mb-10">
                 <div>
                    <h3 className="text-xs font-black uppercase tracking-widest text-copper mb-1">Curva-S Acumulada</h3>
                    <p className="text-[10px] text-text-muted">Análise de saúde financeira acumulada (Baseline vs Real)</p>
                 </div>
              </div>
              <div className="h-[400px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={scurve} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="scurve_prev" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={COPPER} stopOpacity={0.1}/>
                        <stop offset="95%" stopColor={COPPER} stopOpacity={0}/>
                      </linearGradient>
                      <linearGradient id="scurve_exec" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={TEAL} stopOpacity={0.1}/>
                        <stop offset="95%" stopColor={TEAL} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                    <XAxis dataKey="data" axisLine={false} tickLine={false} tick={{fill:'rgba(255,255,255,0.3)',fontSize:10,fontWeight:700}} dy={15} />
                    <YAxis axisLine={false} tickLine={false} tick={{fill:'rgba(255,255,255,0.3)',fontSize:10,fontWeight:700}} tickFormatter={v=>`R$${v/1000}k`} />
                    <Tooltip contentStyle={{background:'#0d1117', border:BORDER, borderRadius:12}} />
                    <Area type="monotone" dataKey="previsto_acum" stroke={COPPER} strokeWidth={3} fillOpacity={1} fill="url(#scurve_prev)" name="Baseline Planejada" />
                    <Area type="monotone" dataKey="executado_acum" stroke={TEAL} strokeWidth={3} fillOpacity={1} fill="url(#scurve_exec)" name="Execução Real" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* CASH FLOW */}
          {activeTab === 'cashflow' && (
            <div className="glass-panel p-8 border-white/5 animate-enter">
               <div className="mb-10">
                  <h3 className="text-xs font-black uppercase tracking-widest text-teal-500 mb-1">Fluxo Mensal de Custos</h3>
                  <p className="text-[10px] text-text-muted">Monitoramento de desembolso por período (Bar Correlation)</p>
               </div>
               <div className="h-[350px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={scurve}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                      <XAxis dataKey="data" axisLine={false} tickLine={false} tick={{fill:'rgba(255,255,255,0.3)',fontSize:10,fontWeight:700}} />
                      <YAxis axisLine={false} tickLine={false} tick={{fill:'rgba(255,255,255,0.3)',fontSize:10,fontWeight:700}} tickFormatter={v=>`R$${v/1000}k`} />
                      <Tooltip cursor={{fill:'rgba(255,255,255,0.02)'}} contentStyle={{background:'#0d1117', border:BORDER, borderRadius:12}} />
                      <Bar dataKey="previsto" fill={COPPER} radius={[4,4,0,0]} name="Previsto Mês" />
                      <Bar dataKey="executado" fill={TEAL} radius={[4,4,0,0]} name="Executado Mês" />
                    </BarChart>
                  </ResponsiveContainer>
               </div>
            </div>
          )}

          {/* EVM (EARNED VALUE MANAGEMENT) */}
          {activeTab === 'evm' && Object.keys(evm).length > 0 && (
            <div className="flex flex-col gap-6 animate-enter">
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <EVMGauge label="CPI (Custo)" value={evm.CPI} fmt={String(evm.CPI)} good={evm.CPI >= 1} icon={DollarSign} />
                <EVMGauge label="SPI (Prazo)" value={evm.SPI} fmt={String(evm.SPI)} good={evm.SPI >= 1} icon={Activity} />
                <div className="glass-panel p-5 border-white/5">
                  <div className="text-[10px] text-text-muted uppercase font-black tracking-widest mb-1">BAC (Orc. Total)</div>
                  <div className="text-2xl font-bold mt-1 text-white">{evm.BAC_fmt}</div>
                </div>
                <div className="glass-panel p-5 border-white/5">
                  <div className="text-[10px] text-text-muted uppercase font-black tracking-widest mb-1">EAC (Estim. Final)</div>
                  <div className="text-2xl font-bold mt-1" style={{ color: evm.is_overrun ? RED : TEAL }}>{evm.EAC_fmt}</div>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                 <div className="glass-panel p-6 border-white/5">
                    <h3 className="text-xs font-black uppercase tracking-widest text-text-muted mb-6 flex items-center gap-2">
                       <Calculator size={14} className="text-copper" /> Auditoria de Valores
                    </h3>
                    <div className="space-y-4">
                       {[
                         { l: 'AC (Custo Real)', v: evm.AC_fmt, c: '#FFF' },
                         { l: 'EV (Valor Agregado)', v: evm.EV_fmt, c: TEAL },
                         { l: 'VAC (Variação no Término)', v: (evm.is_overrun ? '-' : '+') + evm.VAC_fmt, c: evm.is_overrun ? RED : TEAL },
                       ].map((x,idx) => (
                         <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/5">
                            <span className="text-xs font-bold text-text-muted">{x.l}</span>
                            <span className="text-sm font-mono font-black" style={{ color: x.c }}>{x.v}</span>
                         </div>
                       ))}
                    </div>
                 </div>

                 <div className="glass-panel p-6 border-white/5">
                    <h3 className="text-xs font-black uppercase tracking-widest text-text-muted mb-6 flex items-center gap-2">
                       <Activity size={14} className="text-copper" /> Evolução de Progresso
                    </h3>
                    <div className="space-y-8">
                       <div className="space-y-2">
                          <div className="flex justify-between text-[10px] font-black uppercase tracking-widest">
                             <span className="text-copper">Progresso Físico</span>
                             <span className="text-white">{evm.physical_pct}%</span>
                          </div>
                          <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                             <div className="h-full bg-copper transition-all duration-1000" style={{ width: `${evm.physical_pct}%` }} />
                          </div>
                       </div>
                       <div className="space-y-2">
                          <div className="flex justify-between text-[10px] font-black uppercase tracking-widest">
                             <span className="text-teal-500">Progresso Financeiro</span>
                             <span className="text-white">{evm.cost_pct}%</span>
                          </div>
                          <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                             <div className="h-full bg-teal-500 transition-all duration-1000" style={{ width: `${evm.cost_pct}%` }} />
                          </div>
                       </div>
                    </div>
                 </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
