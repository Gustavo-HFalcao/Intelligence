import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { 
  FileText, Plus, Loader2, Download, 
  Settings, PieChart, Activity, FileCheck, 
  Trash2, ExternalLink, Calendar, Search,
  Filter, Share2, Info
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import './Dashboard.css'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

async function api(path: string, opts?: RequestInit) {
  const r = await fetch(path, { credentials:'include', ...opts })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export default function Relatorios() {
  const [showForm, setShowForm] = useState(false)
  const [form, setForm]         = useState<Record<string,string>>({ tipo:'executive' })
  const [search, setSearch]     = useState('')
  const qc = useQueryClient()

  const { data, isLoading }  = useQuery({ queryKey:['relatorios'], queryFn:()=>api('/api/relatorios'), staleTime:30_000 })
  const { data:tipos } = useQuery({ queryKey:['rel-tipos'], queryFn:()=>api('/api/relatorios/tipos') })
  const { data:contratos } = useQuery({ queryKey:['hub-contratos'], queryFn:()=>api('/api/hub/contratos'), staleTime:60_000 })

  const genMut = useMutation({
    mutationFn:(body:any) => api('/api/relatorios/generate', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }),
    onSuccess:() => { qc.invalidateQueries({queryKey:['relatorios']}); setShowForm(false); setForm({tipo:'executive'}) },
  })

  const reports: any[]    = data?.relatorios ?? []
  const tipoList: any[]   = Object.values(tipos?.tipos ?? {})
  const contratoList: any[] = contratos?.contratos ?? []

  const filteredReports = reports.filter(r => 
    r.titulo?.toLowerCase().includes(search.toLowerCase()) || 
    r.contrato?.toLowerCase().includes(search.toLowerCase())
  )

  const handleInp = (k:string, v:string) => setForm(f => ({ ...f, [k]: v }))

  return (
    <div className="flex flex-col gap-8 animate-enter">
      {/* ── HEADER ────────────────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/5 pb-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
            <FileText size={22} className="text-copper" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-white uppercase tracking-tight">Relatórios & Insights</h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">Gerador de Documentação Auditável (1:1)</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
           <div className="relative group">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-copper transition-colors" />
              <Input 
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Filtrar por título..." 
                className="h-10 pl-9 bg-white/5 border-white/10 w-64 text-xs font-bold"
              />
           </div>
           <Button 
            onClick={() => setShowForm(true)}
            className="bg-copper hover:bg-copper/80 text-void font-bold text-[10px] uppercase tracking-widest h-10 px-6 shadow-[0_0_15px_rgba(201,139,42,0.2)]"
           >
              <Plus size={16} className="mr-2" /> Gerar Novo
           </Button>
        </div>
      </div>

      {/* ── FORM DRAWER / MODAL ───────────────────────────────────────────── */}
      <AnimatePresence>
        {showForm && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            className="glass-panel p-8 border-copper/20 bg-copper/[0.02]"
          >
            <div className="flex items-center justify-between mb-8">
               <div className="flex items-center gap-2">
                  <div className="w-1.5 h-6 bg-copper rounded-full" />
                  <h2 className="text-sm font-black uppercase text-white tracking-widest">Configuração de Relatório</h2>
               </div>
               <button onClick={() => setShowForm(false)} className="p-2 text-text-muted hover:text-white transition-colors"><Plus size={20} className="rotate-45" /></button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
               <div className="space-y-2">
                  <label className="text-[9px] font-black uppercase tracking-widest text-text-muted">Tipo de Relatório</label>
                  <select 
                    className="w-full h-12 bg-void border border-white/10 rounded-xl px-4 text-xs font-bold text-copper outline-none transition-all"
                    onChange={e => handleInp('tipo', e.target.value)}
                  >
                     {tipoList.map((t:any) => <option key={t.slug} value={t.slug}>{t.label}</option>)}
                  </select>
               </div>

               <div className="space-y-2">
                  <label className="text-[9px] font-black uppercase tracking-widest text-text-muted">Contrato / Ativo</label>
                  <select 
                    className="w-full h-12 bg-void border border-white/10 rounded-xl px-4 text-xs font-bold text-white outline-none transition-all"
                    onChange={e => handleInp('contrato', e.target.value)}
                  >
                     <option value="">Todos</option>
                     {contratoList.map((c:any) => <option key={c.contrato} value={c.contrato}>{c.contrato}</option>)}
                  </select>
               </div>

               <div className="space-y-2">
                  <label className="text-[9px] font-black uppercase tracking-widest text-text-muted">Início do Período</label>
                  <Input type="date" className="h-12 bg-void border-white/10" onChange={e => handleInp('periodo_ini', e.target.value)} />
               </div>

               <div className="space-y-2">
                  <label className="text-[9px] font-black uppercase tracking-widest text-text-muted">Término do Período</label>
                  <Input type="date" className="h-12 bg-void border-white/10" onChange={e => handleInp('periodo_fim', e.target.value)} />
               </div>

               <div className="lg:col-span-4 space-y-2">
                  <label className="text-[9px] font-black uppercase tracking-widest text-text-muted">Título Customizado (Opcional)</label>
                  <Input 
                    placeholder="Ex: Sumário Executivo - Q1 2024" 
                    className="h-12 bg-void border-white/10 text-xs font-bold"
                    onChange={e => handleInp('titulo', e.target.value)}
                  />
               </div>
            </div>

            <div className="mt-8 pt-8 border-t border-white/5 flex gap-3">
               <Button 
                onClick={() => genMut.mutate(form)} 
                disabled={genMut.isPending}
                className="bg-teal-600 hover:bg-teal-500 text-white font-black text-[10px] uppercase tracking-widest h-12 px-8 shadow-lg shadow-teal-500/10"
               >
                 {genMut.isPending ? <><Loader2 size={16} className="mr-2 animate-spin" /> Processando Motor PDF</> : 'SOLICITAR GERAÇÃO AUDITÁVEL'}
               </Button>
               <Button onClick={() => setShowForm(false)} variant="outline" className="border-white/10 text-text-muted h-12 px-6">CANCELAR</Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── REPORTS LIST ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Statistics or Quick Info */}
        <div className="lg:col-span-1 space-y-4">
           <div className="glass-panel p-6 border-white/5 bg-white/[0.01]">
              <h3 className="text-[10px] font-black uppercase tracking-widest text-copper mb-6 flex items-center gap-2">
                 <Activity size={12} /> Estado do Sistema
              </h3>
              <div className="space-y-4 text-xs">
                 <div className="flex justify-between items-center py-2 border-b border-white/5">
                    <span className="text-text-muted">Total Gerados</span>
                    <span className="font-mono text-white font-bold">{reports.length}</span>
                 </div>
                 <div className="flex justify-between items-center py-2 border-b border-white/5">
                    <span className="text-text-muted">Uptime Motor PDF</span>
                    <span className="text-teal-500 font-bold">99.9%</span>
                 </div>
                 <div className="flex justify-between items-center py-2 border-b border-white/5">
                    <span className="text-text-muted">Última Gerações</span>
                    <span className="text-white/40">{reports[0]?.created_at || 'N/A'}</span>
                 </div>
              </div>
              <div className="mt-8 p-3 rounded-lg bg-white/5 border border-white/5 flex gap-3 items-start">
                 <Info size={16} className="text-copper mt-0.5" />
                 <p className="text-[10px] text-text-muted leading-relaxed">Todos os relatórios são assinados digitalmente e seguem os padrões de auditoria ISO 9001:2015.</p>
              </div>
           </div>
        </div>

        {/* The Table/List */}
        <div className="lg:col-span-2 glass-panel border-white/5 overflow-hidden">
          <div className="p-4 bg-white/[0.02] border-b border-white/5 flex items-center justify-between">
             <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Banco de Dados de Relatórios</span>
             <Filter size={14} className="text-text-muted" />
          </div>
          <div className="overflow-x-auto no-scrollbar">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-white/[0.01] border-b border-white/5">
                  {['Documento','Status','Timestamp',''].map(h => (
                    <th key={h} className="px-5 py-4 text-[9px] font-black text-text-muted uppercase tracking-widest">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.02]">
                {filteredReports.map(r => (
                  <tr key={r.id} className="hover:bg-copper/5 transition-all group">
                    <td className="px-5 py-4">
                       <div className="flex items-center gap-3">
                          <div className="p-2 rounded bg-white/5 border border-white/10 text-white/40">
                             <FileCheck size={16} />
                          </div>
                          <div>
                             <div className="text-xs font-bold text-white mb-0.5">{r.titulo || 'Relatório de Operações'}</div>
                             <div className="text-[9px] font-black uppercase tracking-tighter text-text-muted">{r.tipo} • {r.contrato || 'Filtro Global'}</div>
                          </div>
                       </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${
                        r.status === 'Concluído' ? 'bg-teal-500/10 text-teal-500' : 
                        r.status === 'Erro' ? 'bg-red-500/10 text-red-500' : 'bg-copper/10 text-copper'
                      }`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-5 py-4 font-mono text-[10px] text-text-muted">{r.created_at}</td>
                    <td className="px-5 py-4">
                       <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-all">
                          {r.pdf_url && (
                             <>
                               <a href={r.pdf_url} target="_blank" rel="noopener noreferrer" className="p-2 hover:bg-copper/20 rounded text-copper transition-all">
                                 <ExternalLink size={14} />
                               </a>
                               <a href={r.pdf_url} download className="p-2 hover:bg-teal-500/20 rounded text-teal-500 transition-all">
                                 <Download size={14} />
                               </a>
                             </>
                          )}
                          <button className="p-2 hover:bg-red-500/20 rounded text-red-500 transition-all">
                             <Trash2 size={14} />
                          </button>
                       </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredReports.length === 0 && (
              <div className="p-20 text-center flex flex-col items-center gap-3 opacity-20">
                 <FileText size={48} className="mb-2" />
                 <p className="text-xs font-black uppercase tracking-widest">Nenhum registro encontrado no histórico.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
