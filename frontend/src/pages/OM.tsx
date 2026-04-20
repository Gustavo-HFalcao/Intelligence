import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { 
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, 
  BarChart, Bar, CartesianGrid, Legend, AreaChart, Area
} from 'recharts'
import { 
  Zap, Plus, Trash2, Activity, Battery, Sun, 
  AlertCircle, CheckCircle2, Calendar, FileText,
  ArrowUpRight, TrendingUp, Settings, Download
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import './Dashboard.css'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const BORDER = '1px solid rgba(201,139,42,0.15)'
const GLASS  = 'rgba(255,255,255,0.04)'

async function api(path: string, opts?: RequestInit) {
  const r = await fetch(path, { credentials:'include', ...opts })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export default function OM() {
  const [searchParams, setSearchParams] = useSearchParams()
  const contrato = searchParams.get('contrato') ?? ''
  const [showForm, setShowForm] = useState(false)
  const [form, setForm]         = useState<Record<string,any>>({ status:'concluido' })
  const qc = useQueryClient()

  const { data:omData, isLoading } = useQuery({
    queryKey:['om', contrato],
    queryFn:()=> contrato ? api(`/api/om/${contrato}`) : api('/api/om'),
  })
  const { data:contratos } = useQuery({ queryKey:['hub-contratos'], queryFn:()=>api('/api/hub/contratos'), staleTime:60_000 })

  const createMut = useMutation({
    mutationFn:(body:any) => api(`/api/om/${contrato}`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }),
    onSuccess:() => { qc.invalidateQueries({queryKey:['om',contrato]}); setShowForm(false); setForm({status:'concluido'}) },
  })

  const deleteMut = useMutation({
    mutationFn:(id:string) => api(`/api/om/${id}`, { method:'DELETE' }),
    onSuccess:() => qc.invalidateQueries({queryKey:['om',contrato]}),
  })

  const cl: any[]      = contratos?.contratos ?? []
  const kpis           = omData?.kpis ?? {}
  const geracoes: any[] = omData?.geracoes ?? []
  const serie: any[]   = omData?.serie_mensal ?? []

  // Formatting helpers 1:1
  const fmtKwh = (v: number) => (v || 0).toLocaleString('pt-BR') + ' kWh'
  const fmtCurrency = (v: any) => typeof v === 'string' ? v : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0)

  return (
    <div className="flex flex-col gap-6 animate-enter">
      {/* ── HEADER & SELECTOR ────────────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
            <Zap size={24} className="text-copper" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-white uppercase tracking-tight">Operação & Manutenção</h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">Gestão de Performance de Ativos</p>
          </div>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-2 lg:pb-0 no-scrollbar">
          <button
            onClick={() => setSearchParams({})}
            className={`px-4 py-2 rounded-lg text-xs font-black uppercase tracking-widest transition-all whitespace-nowrap border ${
              !contrato ? 'bg-copper text-void border-copper shadow-[0_0_20px_rgba(201,139,42,0.2)]' : 'bg-white/5 text-text-muted border-white/5 hover:border-copper/40 hover:text-white'
            }`}
          >
            Todos
          </button>
          {cl.map((c:any) => (
            <button
              key={c.contrato}
              onClick={() => setSearchParams({ contrato:c.contrato })}
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
              { label:'Geração Acumulada', value: fmtKwh(kpis.total_kwh), icon: Sun, color: COPPER, trend: '+12.4%' },
              { label:'Performance Ratio', value: `${kpis.avg_disponibilidade || 98.2}%`, icon: Activity, color: TEAL, trend: 'Ótimo' },
              { label:'Receita O&M', value: fmtCurrency(kpis.total_executado), icon: TrendingUp, color: TEAL, trend: 'Executado' },
              { label:'Specific Yield', value: '142.5 kWh/kWp', icon: Battery, color: COPPER, trend: 'Início out/23' },
            ].map((k, i) => (
              <div key={i} className="glass-panel p-5 border-white/5 hover:border-white/10 transition-all group overflow-hidden relative">
                <div className="flex justify-between items-start mb-4">
                   <div className={`p-2 rounded-lg bg-white/5 border border-white/5 group-hover:border-${k.color === COPPER ? 'copper' : 'teal'}-500/30 transition-all`}>
                      <k.icon size={18} style={{ color: k.color }} />
                   </div>
                   <span className="text-[9px] font-black uppercase tracking-tighter text-white/20 border border-white/10 px-1.5 py-0.5 rounded italic">RT-L5</span>
                </div>
                <div className="text-[10px] text-text-muted uppercase font-black tracking-widest mb-1">{k.label}</div>
                <div className="text-xl font-bold text-white mb-2">{k.value}</div>
                <div className="flex items-center gap-1.5">
                   <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded bg-white/5`} style={{ color: k.trend.includes('%') || k.trend === 'Ótimo' ? TEAL : COPPER }}>{k.trend}</span>
                   <div className="h-[1px] flex-1 bg-white/5" />
                   <ArrowUpRight size={12} className="text-white/20" />
                </div>
              </div>
            ))}
          </div>

          {/* ── CHARTS SECTION ────────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 glass-panel p-6 border-white/5">
              <div className="flex items-center justify-between mb-8">
                 <div>
                    <h3 className="text-xs font-black uppercase tracking-widest text-[#C98B2A] mb-1">Geração vs Histórico</h3>
                    <p className="text-[9px] text-text-muted">Análise de produção energética mensal x baseline projetada</p>
                 </div>
                 <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" className="h-8 text-[9px] font-bold border-white/5 bg-white/5 h-7">MENSAL</Button>
                    <Button variant="outline" size="sm" className="h-8 text-[9px] font-bold border-white/5 opacity-50 h-7">DIÁRIO</Button>
                 </div>
              </div>
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={serie} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorPrev" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={COPPER} stopOpacity={0.3}/>
                        <stop offset="95%" stopColor={COPPER} stopOpacity={0}/>
                      </linearGradient>
                      <linearGradient id="colorExec" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={TEAL} stopOpacity={0.3}/>
                        <stop offset="95%" stopColor={TEAL} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                    <XAxis 
                      dataKey="mes" 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10, fontWeight: 700 }} 
                      dy={10}
                    />
                    <YAxis 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10, fontWeight: 700 }}
                      tickFormatter={(v) => `R$${v/1000}k`}
                    />
                    <Tooltip 
                      contentStyle={{ background: '#0D1117', border: `1px solid ${COPPER}40`, borderRadius: 12, padding: 12 }}
                      itemStyle={{ fontSize: 11, fontWeight: 700, color: '#FFF' }}
                    />
                    <Area type="monotone" dataKey="previsto" stroke={COPPER} strokeWidth={2} fillOpacity={1} fill="url(#colorPrev)" name="Baseline Planejada" />
                    <Area type="monotone" dataKey="executado" stroke={TEAL} strokeWidth={2} fillOpacity={1} fill="url(#colorExec)" name="Execução Real (kWh)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="glass-panel p-6 border-white/5 flex flex-col">
               <div className="mb-6">
                  <h3 className="text-xs font-black uppercase tracking-widest text-teal-500 mb-1">Status de Disponibilidade</h3>
                  <p className="text-[9px] text-text-muted">Uptime técnico e logs de manutenção preventiva</p>
               </div>
               
               <div className="flex-1 space-y-4">
                  {[
                    { label: 'Uptime Sistema', val: '99.8%', icon: CheckCircle2, status: 'OK' },
                    { label: 'Inversores Ativos', val: '12/12', icon: Activity, status: 'Crítico' },
                    { label: 'Temperatura Mód.', val: '42°C', icon: AlertCircle, status: 'Normal' },
                  ].map((s, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5">
                       <div className="flex items-center gap-3">
                          <s.icon size={16} className={s.status === 'OK' ? 'text-teal-500' : s.status === 'Crítico' ? 'text-copper' : 'text-white/40'} />
                          <span className="text-xs font-bold text-white/60">{s.label}</span>
                       </div>
                       <span className="text-xs font-mono font-black text-white">{s.val}</span>
                    </div>
                  ))}
               </div>

               <Button 
                onClick={() => setShowForm(true)}
                className="w-full mt-6 bg-copper hover:bg-copper/80 text-void font-bold text-[10px] uppercase tracking-widest h-10"
               >
                 <Plus size={16} className="mr-2" /> Registrar Evento
               </Button>
            </div>
          </div>

          {/* ── LOGS TABLE ────────────────────────────────────────────── */}
          <div className="glass-panel border-white/5 overflow-hidden">
            <div className="p-5 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
               <div className="flex items-center gap-3">
                  <FileText size={16} className="text-copper" />
                  <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Log de Atividades e Geração</span>
               </div>
               <button className="p-2 hover:bg-white/5 rounded-lg text-text-muted transition-all">
                  <Download size={14} />
               </button>
            </div>
            
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/5">
                    {['Período','Data Referência','Energia (kWh)','Valor Direto','Disp.%','Status','Ações'].map(h=>(
                      <th key={h} className="px-5 py-4 text-[9px] font-black text-text-muted uppercase tracking-widest">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.02]">
                  {geracoes.map(g=>(
                    <tr key={g.id} className="hover:bg-copper/5 transition-colors group">
                      <td className="px-5 py-4">
                        <span className="text-[10px] font-black uppercase text-white/40">{g.periodo}</span>
                      </td>
                      <td className="px-5 py-4 font-mono text-xs text-text-muted">{g.data}</td>
                      <td className="px-5 py-4">
                         <div className="flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-teal-500" />
                            <span className="font-mono text-xs text-white font-bold">{g.kwh_gerado.toLocaleString()} kWh</span>
                         </div>
                      </td>
                      <td className="px-5 py-4 font-mono text-xs text-copper font-bold">{g.valor_executado_fmt}</td>
                      <td className="px-5 py-4 font-mono text-xs text-text-muted">{g.disponibilidade_pct}%</td>
                      <td className="px-5 py-4">
                         <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${
                           g.status === 'concluido' ? 'bg-teal-500/10 text-teal-500' : 'bg-copper/10 text-copper animate-pulse border border-copper/20'
                         }`}>
                           {g.status}
                         </span>
                      </td>
                      <td className="px-5 py-4">
                        <button onClick={() => deleteMut.mutate(g.id)} className="p-2 hover:bg-red-500/20 rounded text-red-500 transition-colors opacity-0 group-hover:opacity-100">
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {geracoes.length === 0 && (
                <div className="p-16 text-center text-text-muted flex flex-col items-center gap-3">
                   <Battery size={32} className="opacity-10" />
                   <p className="text-xs uppercase tracking-widest font-bold">Base de dados limpa. Nenhuma ocorrência detectada.</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* ── QUICK ENTRY DRAWER (FORM) ─────────────────────────────── */}
      {showForm && (
        <div className="fixed inset-0 z-[100] flex items-center justify-end p-4 bg-void/80 backdrop-blur-sm animate-in fade-in duration-300">
           <div className="w-full max-w-md h-full bg-[#0D1117] border-l border-white/10 p-8 shadow-2xl flex flex-col animate-in slide-in-from-right duration-500">
              <div className="flex items-center justify-between mb-8">
                 <div className="flex items-center gap-3">
                   <Plus className="text-copper" size={20} />
                   <h2 className="text-lg font-black uppercase text-white tracking-tight">Nova Geração O&M</h2>
                 </div>
                 <button onClick={() => setShowForm(false)} className="p-2 hover:bg-white/5 rounded-full transition-all text-text-muted"><X size={20} /></button>
              </div>

              <div className="space-y-6 flex-1 overflow-y-auto pr-2 custom-scrollbar">
                 <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-text-muted">Período Fiscal</label>
                    <input 
                      className="w-full bg-white/5 border border-white/10 rounded-xl h-12 px-4 text-sm font-bold text-copper outline-none focus:border-copper/60 transition-all" 
                      placeholder="Ex: JAN-24"
                      onChange={e => setForm({...form, periodo: e.target.value})}
                    />
                 </div>
                 <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                       <label className="text-[10px] font-black uppercase tracking-widest text-text-muted">kWh Gerado (Real)</label>
                       <input 
                        type="number"
                        className="w-full bg-white/5 border border-white/10 rounded-xl h-12 px-4 text-sm font-mono text-white outline-none focus:border-copper/60 transition-all font-bold" 
                        onChange={e => setForm({...form, kwh_gerado: parseFloat(e.target.value)})}
                       />
                    </div>
                    <div className="space-y-2">
                       <label className="text-[10px] font-black uppercase tracking-widest text-text-muted">Disp. Técnica %</label>
                       <input 
                        type="number"
                        className="w-full bg-white/5 border border-white/10 rounded-xl h-12 px-4 text-sm font-mono text-white outline-none focus:border-copper/60 transition-all font-bold" 
                        onChange={e => setForm({...form, disponibilidade_pct: parseFloat(e.target.value)})}
                       />
                    </div>
                 </div>
                 <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-text-muted">Valor Executado (BRL)</label>
                    <input 
                      type="number"
                      className="w-full bg-white/5 border border-white/10 rounded-xl h-12 px-4 text-sm font-mono text-white outline-none focus:border-copper/60 transition-all font-bold" 
                      onChange={e => setForm({...form, valor_executado: parseFloat(e.target.value)})}
                    />
                 </div>
                 <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-text-muted">Contexto Operacional</label>
                    <textarea 
                      className="w-full bg-white/5 border border-white/10 rounded-xl p-4 text-sm text-text-muted outline-none focus:border-copper/60 transition-all min-h-[120px]" 
                      placeholder="Descreva observações técnicas relevantes..."
                      onChange={e => setForm({...form, descricao: e.target.value})}
                    />
                 </div>
              </div>

              <div className="mt-8 pt-8 border-t border-white/5 flex gap-3">
                 <Button 
                   onClick={() => createMut.mutate(form)}
                   className="flex-1 bg-teal-600 hover:bg-teal-500 text-white font-black text-xs uppercase tracking-widest h-12 shadow-[0_0_20px_rgba(20,184,166,0.2)]"
                 >
                   Salvar Ativo
                 </Button>
                 <Button 
                   onClick={() => setShowForm(false)} 
                   variant="outline" 
                   className="flex-1 border-white/10 text-white/40 h-12 font-bold text-xs"
                 >
                   CANCELAR
                 </Button>
              </div>
           </div>
        </div>
      )}
    </div>
  )
}

function X(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  )
}
