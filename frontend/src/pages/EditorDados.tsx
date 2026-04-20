import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { 
  Database, Save, RefreshCw, Trash2, Plus, 
  Search, Filter, Edit3, X, Check, ChevronRight,
  DatabaseIcon, Layers, Zap, Info, ArrowRight
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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

const TABLES = [
  { key:'contratos',  label:'Malha de Contratos', icon: DatabaseIcon, endpoint:'/api/hub/contratos' },
  { key:'atividades', label:'Atividades Operacionais', icon: Layers,  endpoint:'/api/hub/cronograma' },
  { key:'om',         label:'Gerações O&M',       icon: Zap,     endpoint:'/api/om' },
]

export default function EditorDados() {
  const [activeTable, setActiveTable] = useState('contratos')
  const [search, setSearch]           = useState('')
  const [isEditing, setIsEditing]     = useState(false)
  const [editingRecord, setEditingRecord] = useState<any>(null)
  const [isInvalidating, setIsInvalidating] = useState(false)
  const qc = useQueryClient()

  // Fetching logic for the selected table
  const { data, isLoading } = useQuery({
    queryKey: ['editor', activeTable],
    queryFn:  () => {
        const t = TABLES.find(x => x.key === activeTable)
        // If OM, we might need a general list or a default contract
        const url = activeTable === 'om' ? '/api/om/ALL' : t?.endpoint
        return api(url || '')
    },
    staleTime: 30_000,
  })

  const records: any[] = activeTable === 'contratos' 
    ? (data?.contratos ?? []) 
    : (activeTable === 'om' ? (data?.geracoes ?? []) : (data?.atividades ?? []))

  const filteredRecords = records.filter(r => {
      const target = activeTable === 'contratos' ? (r.projeto || r.contrato) : (r.atividade || r.periodo || r.descricao)
      return target?.toLowerCase().includes(search.toLowerCase())
  })

  // Mutations
  const deleteMut = useMutation({
    mutationFn: (id: string) => {
        const path = activeTable === 'contratos' ? `/api/hub/contratos/${id}` : (activeTable === 'om' ? `/api/om/${id}` : `/api/hub/cronograma/${id}`)
        return api(path, { method: 'DELETE' })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['editor', activeTable] })
  })

  const invalidateCache = async () => {
     setIsInvalidating(true)
     try {
        await api('/api/dashboard/invalidate-cache', { method: 'POST', body: '{}' })
        await qc.invalidateQueries()
        alert('Cache global invalidado com sucesso.')
     } finally {
        setIsInvalidating(false)
     }
  }

  const handleEdit = (record: any) => {
      setEditingRecord(record)
      setIsEditing(true)
  }

  return (
    <div className="flex flex-col gap-6 animate-enter">
      {/* ── HEADER ────────────────────────────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row justify-between lg:items-center gap-6 pb-6 border-b border-white/5">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-2xl bg-copper/10 border border-copper/30 shadow-[0_0_15px_rgba(201,139,42,0.1)]">
            <Database size={26} className="text-copper" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-white uppercase tracking-tight">Governança de Dados</h1>
            <div className="flex items-center gap-3 mt-0.5">
               <span className="text-[10px] text-text-muted font-bold uppercase tracking-widest flex items-center gap-1.5 animation-pulse">
                  <span className="w-1 h-1 rounded-full bg-teal-500 animate-pulse" /> Direct DB Access
               </span>
               <div className="w-[1px] h-3 bg-white/10" />
               <button onClick={invalidateCache} disabled={isInvalidating} className="text-[10px] text-copper/60 hover:text-copper font-black uppercase tracking-widest flex items-center gap-1.5 transition-colors">
                  {isInvalidating ? <RefreshCw size={10} className="animate-spin" /> : <RefreshCw size={10} />} Invalidar Cache
               </button>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
           <div className="relative group">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-copper transition-colors" />
              <Input 
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Localizar registro..." 
                className="h-11 pl-10 bg-white/5 border-white/10 w-72 text-xs font-bold focus:border-copper/40"
              />
           </div>
           <Button className="bg-white/5 border border-white/10 text-white hover:bg-white/10 h-11 px-5">
              <Filter size={16} />
           </Button>
        </div>
      </div>

      {/* ── TABLE SELECTOR ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {TABLES.map(t => (
          <button 
            key={t.key} 
            onClick={() => { setActiveTable(t.key); setSearch('') }}
            className={`flex items-center justify-between p-5 rounded-2xl border transition-all relative overflow-hidden group ${
              activeTable === t.key 
                ? 'bg-copper text-void border-copper shadow-[0_10px_30px_rgba(201,139,42,0.1)]' 
                : 'bg-white/[0.02] border-white/5 text-text-muted hover:border-white/10'
            }`}
          >
            <div className="flex items-center gap-4 z-10">
              <t.icon size={20} className={activeTable === t.key ? 'text-void' : 'text-copper'} />
              <div className="text-left">
                 <div className="text-[10px] font-black uppercase tracking-widest opacity-60">Dataset</div>
                 <div className="text-sm font-bold">{t.label}</div>
              </div>
            </div>
            <ChevronRight size={18} className={`z-10 transition-transform ${activeTable === t.key ? 'translate-x-0' : '-translate-x-4 opacity-0 group-hover:opacity-100 group-hover:translate-x-0'}`} />
            <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:opacity-10 transition-opacity">
               <t.icon size={80} />
            </div>
          </button>
        ))}
      </div>

      {/* ── TABLE VIEW ───────────────────────────────────────────────────── */}
      <div className="glass-panel border-white/5 overflow-hidden">
        <div className="overflow-x-auto no-scrollbar">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-white/[0.01] border-b border-white/5">
                {activeTable === 'contratos' ? (
                   ['Identificador','Projeto Técnico','Cliente','Posição','Ações'].map(h => <th key={h} className="px-6 py-4 text-[10px] font-black text-text-muted uppercase tracking-widest">{h}</th>)
                ) : activeTable === 'atividades' ? (
                   ['Atividade','Período','Critico','%','Ações'].map(h => <th key={h} className="px-6 py-4 text-[10px] font-black text-text-muted uppercase tracking-widest">{h}</th>)
                ) : (
                   ['Período','Data','kWh','Status','Ações'].map(h => <th key={h} className="px-6 py-4 text-[10px] font-black text-text-muted uppercase tracking-widest">{h}</th>)
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.02]">
              {filteredRecords.map((r, i) => (
                <tr key={i} className="hover:bg-copper/[0.03] transition-colors group">
                  {activeTable === 'contratos' && (
                    <>
                      <td className="px-6 py-4 font-mono text-xs font-black text-copper">{r.contrato}</td>
                      <td className="px-6 py-4">
                         <div className="text-xs font-bold text-white mb-0.5">{r.projeto}</div>
                         <div className="text-[9px] font-black uppercase text-text-muted tracking-tight">{r.localizacao || 'BRASIL'}</div>
                      </td>
                      <td className="px-6 py-4 text-xs text-text-muted">{r.cliente}</td>
                      <td className="px-6 py-4">
                         <div className="flex items-center gap-3">
                            <div className="w-12 h-1 bg-white/5 rounded-full overflow-hidden">
                               <div className="h-full bg-copper" style={{ width: `${r.realizado_pct}%` }} />
                            </div>
                            <span className="text-xs font-mono font-bold text-white">{r.realizado_pct}%</span>
                         </div>
                      </td>
                    </>
                  )}
                  
                  {activeTable === 'atividades' && (
                    <>
                      <td className="px-6 py-4">
                         <div className="text-xs font-bold text-white mb-0.5">{r.atividade}</div>
                         <div className="text-[9px] font-black uppercase text-text-muted italic">{r.fase}</div>
                      </td>
                      <td className="px-6 py-4 font-mono text-[10px] text-text-muted">{r.inicio_br} <ArrowRight size={8} className="inline mx-1" /> {r.termino_br}</td>
                      <td className="px-6 py-4">
                         <span className={`text-[9px] font-black uppercase px-2 py-0.5 rounded ${r.critico === 'Sim' ? 'bg-red-500/10 text-red-500' : 'text-text-muted bg-white/5'}`}>{r.critico || 'NÃO'}</span>
                      </td>
                      <td className="px-6 py-4 font-mono text-xs font-bold text-teal-500">{r.conclusao_pct}%</td>
                    </>
                  )}

                  {activeTable === 'om' && (
                    <>
                      <td className="px-6 py-4 text-xs font-black text-white">{r.periodo}</td>
                      <td className="px-6 py-4 font-mono text-[10px] text-text-muted">{r.data}</td>
                      <td className="px-6 py-4 font-mono text-xs font-bold text-copper">{r.kwh_gerado} kWh</td>
                      <td className="px-6 py-4">
                         <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${r.status === 'concluido' ? 'bg-teal-500/10 text-teal-500' : 'bg-copper/10 text-copper'}`}>{r.status}</span>
                      </td>
                    </>
                  )}

                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
                       <button onClick={() => handleEdit(r)} className="p-2.5 hover:bg-copper/20 rounded-xl text-copper transition-all">
                          <Edit3 size={15} />
                       </button>
                       <button onClick={() => deleteMut.mutate(r.id || r.contrato)} className="p-2.5 hover:bg-red-500/20 rounded-xl text-red-500 transition-all">
                          <Trash2 size={15} />
                       </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filteredRecords.length === 0 && !isLoading && (
            <div className="p-24 text-center flex flex-col items-center gap-4 opacity-20">
               <Layers size={48} className="mb-2" />
               <p className="text-xs font-black uppercase tracking-widest">Nenhum registro auditado neste dataset.</p>
            </div>
          )}
        </div>
      </div>

      {/* ── INFO FOOTER ───────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 p-4 rounded-2xl bg-white/[0.01] border border-white/5">
         <Info size={16} className="text-copper" />
         <p className="text-[10px] text-text-muted leading-relaxed uppercase font-bold tracking-tight">
            A Governança de Dados permite alterações diretas no banco de produção. Use com cautela. Alterações podem levar até 60s para refletir no cache global caso o botão de invalidação não seja acionado.
         </p>
      </div>

      {/* ── SIDE DRAWER (EDITING) ────────────────────────────────────────── */}
      <AnimatePresence>
         {isEditing && (
            <div className="fixed inset-0 z-[100] flex justify-end p-4 bg-void/80 backdrop-blur-sm">
               <motion.div 
                 initial={{ x: '100%' }}
                 animate={{ x: 0 }}
                 exit={{ x: '100%' }}
                 transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                 className="w-full max-w-lg h-full bg-[#0D1117] border-l border-white/10 p-10 shadow-2xl flex flex-col"
               >
                  <div className="flex items-center justify-between mb-10">
                    <div className="flex items-center gap-3">
                       <div className="w-2 h-2 rounded-full bg-copper shadow-[0_0_8px_#C98B2A]" />
                       <h2 className="text-lg font-black uppercase text-white tracking-widest">Editor de Registro</h2>
                    </div>
                    <button onClick={() => setIsEditing(false)} className="p-2 text-text-muted hover:text-white transition-colors"><X size={24} /></button>
                  </div>

                  <div className="flex-1 space-y-6 overflow-y-auto pr-4 custom-scrollbar">
                     <div className="p-4 rounded-xl bg-white/5 border border-white/5 mb-8">
                        <div className="text-[9px] font-black text-copper uppercase tracking-widest mb-1 italic">MetaData Pointer</div>
                        <div className="text-xs font-mono text-white/40">{JSON.stringify(editingRecord)}</div>
                     </div>
                     
                     <p className="text-sm text-text-muted italic">A edição detalhada de campos via UI administrativa está sendo normalizada. Sugestão: Use o formulário original do módulo Hub ou O&M para melhor experiência.</p>
                  </div>

                  <div className="mt-10 pt-10 border-t border-white/5 flex gap-4">
                     <Button className="flex-1 bg-copper text-void font-black text-xs h-14" onClick={() => setIsEditing(false)}>SALVAR REVISÃO</Button>
                     <Button variant="outline" className="flex-1 border-white/10 text-white/40 h-14 font-black text-xs" onClick={() => setIsEditing(false)}>DESCARTAR</Button>
                  </div>
               </motion.div>
            </div>
         )}
      </AnimatePresence>
    </div>
  )
}
