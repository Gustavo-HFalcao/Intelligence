import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  X, Save, Activity, User, Calendar, Info, Loader2, Target, 
  AlertTriangle, Layers, TrendingUp, Hash, Ruler, Link,
  CheckCircle2, AlertCircle, DollarSign, Clock
} from 'lucide-react'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'

interface ActivityModalProps {
  isOpen: boolean
  onClose: () => void
  contrato: string
  editingActivity?: any
  parentActivity?: any  // quando passado, nivel e parent_id ficam travados
}

const DISCIPLINAS = ['Civil', 'Elétrica', 'Hidráulica', 'Estrutural', 'Mecânica', 'Terraplanagem', 'Infraestrutura', 'Geral', 'Licenciamento', 'Aprovações']
const SECTIONS = ['Geral', 'Engenharia', 'Quantitativos', 'Análise']

export default function ActivityModal({ isOpen, onClose, contrato, editingActivity, parentActivity }: ActivityModalProps) {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('Geral')
  const [propagateImpact, setPropagateImpact] = useState(false)
  
  const [form, setForm] = useState<any>({
    atividade: '',
    fase: 'Geral',
    fase_macro: 'Execução',
    responsavel: '',
    inicio_previsto: '',
    termino_previsto: '',
    conclusao_pct: 0,
    peso_pct: 1,
    peso_valor: 0,
    critico: 'Nao',
    observacoes: '',
    contrato: contrato,
    nivel: 'sub',
    parent_id: '',
    dependencia_id: '',
    dep_tipo: 'sem_dependencia',
    total_qty: 0,
    exec_qty: 0,
    unidade: 'un',
    dias_planejados: 0,
    status_atividade: 'Pendente'
  })

  // List activities for parent/dependency selection
  const { data: cronData } = useQuery({
    queryKey: ['hub-cronograma', contrato],
    queryFn: () => api.get(`/hub/cronograma?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    enabled: isOpen
  })

  // Nível derivado do pai — macro cria micro, micro cria sub
  const derivedNivel = parentActivity
    ? (parentActivity.nivel === 'macro' || !parentActivity.nivel ? 'micro' : 'sub')
    : 'macro'

  useEffect(() => {
    if (editingActivity) {
      setForm({
        ...editingActivity,
        dep_tipo: editingActivity.dep_tipo || 'sem_dependencia',
        inicio_previsto: editingActivity.inicio_previsto ? editingActivity.inicio_previsto.slice(0, 10) : '',
        termino_previsto: editingActivity.termino_previsto ? editingActivity.termino_previsto.slice(0, 10) : ''
      })
    } else {
      setForm({
        atividade: '',
        fase: parentActivity?.fase || 'Geral',
        fase_macro: parentActivity?.fase_macro || 'Execução',
        responsavel: '',
        inicio_previsto: '',
        termino_previsto: '',
        conclusao_pct: 0,
        peso_pct: 1,
        peso_valor: 0,
        critico: 'Nao',
        observacoes: '',
        contrato: contrato,
        nivel: derivedNivel,
        parent_id: parentActivity?.id || '',
        dependencia_id: '',
        dep_tipo: 'sem_dependencia',
        total_qty: 0,
        exec_qty: 0,
        unidade: 'un',
        dias_planejados: 0,
        status_atividade: 'Pendente'
      })
    }
    setActiveTab('Geral')
    setPropagateImpact(false)
  }, [editingActivity, parentActivity, isOpen, contrato])

  const mutation = useMutation({
    mutationFn: (data: any) => {
      const payload = { ...data, propagar_impacto: propagateImpact, old_termino: editingActivity?.termino_previsto }
      if (editingActivity) {
        return api.patch(`/hub/cronograma/${editingActivity.id}`, payload).then(r => r.data)
      }
      return api.post('/hub/cronograma', payload).then(r => r.data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hub-cronograma', contrato] })
      queryClient.invalidateQueries({ queryKey: ['hub-dashboard', contrato] })
      queryClient.invalidateQueries({ queryKey: ['hub-visao-geral', contrato] })
      onClose()
    }
  })

  const handleChange = (k: string, v: any) => setForm((prev: any) => ({ ...prev, [k]: v }))

  const allAtivs = cronData?.atividades ?? []
  const parentOptions = allAtivs.filter((a: any) => a.id !== editingActivity?.id && (a.nivel === 'macro' || a.nivel === 'micro'))
  const depOptions = allAtivs.filter((a: any) => a.id !== editingActivity?.id)

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} className="absolute inset-0 bg-black/90 backdrop-blur-xl" />
          
          <motion.div
            initial={{ opacity: 0, scale: 0.98, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.98, y: 20 }}
            className="relative w-full max-w-4xl bg-[#070d0b] border border-white/10 rounded-2xl overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.5)] flex flex-col max-h-[90vh]"
          >
            {/* Header */}
            <div className="px-8 py-6 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-copper/10 to-transparent">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-xl bg-copper/20 border border-copper/40 text-copper">
                  <Layers size={24} />
                </div>
                <div>
                  <h3 className="text-lg font-black uppercase tracking-tight text-white">
                    {editingActivity ? 'Editar Atividade' : parentActivity ? `Nova ${derivedNivel.toUpperCase()} em "${parentActivity.atividade?.slice(0,30)}"` : 'Nova Atividade Macro'}
                  </h3>
                  <div className="flex items-center gap-2 mt-0.5">
                    {parentActivity && !editingActivity && (
                      <span className="text-[9px] text-teal-400 font-black uppercase tracking-widest px-1.5 py-0.5 bg-teal-400/10 rounded border border-teal-400/20">
                        Pai travado: {parentActivity.atividade?.slice(0,20)}
                      </span>
                    )}
                    <span className="text-[9px] text-white/40 uppercase tracking-widest font-bold">HUB CRONOGRAMA</span>
                  </div>
                </div>
              </div>
              <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full text-white/20 transition-all"><X size={20} /></button>
            </div>

            {/* Navigation */}
            <div className="px-8 flex border-b border-white/5 bg-black/40">
              {SECTIONS.map(s => (
                <button
                  key={s} onClick={() => setActiveTab(s)}
                  className={`px-6 py-4 text-[10px] font-black uppercase tracking-widest transition-all relative ${activeTab === s ? 'text-copper' : 'text-white/20 hover:text-white/40'}`}
                >
                  {s}
                  {activeTab === s && <motion.div layoutId="tab-active" className="absolute bottom-0 left-0 right-0 h-0.5 bg-copper" />}
                </button>
              ))}
            </div>

            {/* Form Body */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-8 space-y-8">
              {activeTab === 'Geral' && (
                <div className="grid grid-cols-2 gap-x-8 gap-y-6 animate-enter">
                  <div className="col-span-2 space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest flex items-center gap-2"><Target size={12} /> Título da Atividade</label>
                    <Input value={form.atividade} onChange={e => handleChange('atividade', e.target.value)} placeholder="Ex: Fundações Bloco A" className="bg-black/40 border-white/10 h-14 text-sm font-bold placeholder:text-white/10 focus:border-copper/50 transition-all" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Nível</label>
                    {parentActivity && !editingActivity ? (
                      <div className="px-4 h-11 flex items-center bg-black/40 border border-teal-400/30 rounded-xl">
                        <span className="text-[11px] font-black uppercase text-teal-400">{derivedNivel}</span>
                        <span className="text-[9px] text-white/20 ml-2">(travado pelo pai)</span>
                      </div>
                    ) : (
                      <div className="grid grid-cols-3 gap-1 bg-black/40 p-1 rounded-xl border border-white/5">
                        {['macro', 'micro', 'sub'].map(n => (
                          <button key={n} type="button" onClick={() => handleChange('nivel', n)} className={`py-2 text-[9px] font-black uppercase rounded-lg transition-all ${form.nivel === n ? 'bg-copper text-void' : 'text-white/20 hover:bg-white/5'}`}>{n}</button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Atividade Pai</label>
                    {parentActivity && !editingActivity ? (
                      <div className="px-4 h-11 flex items-center bg-black/40 border border-teal-400/30 rounded-xl">
                        <span className="text-[11px] font-bold text-white/70 truncate">{parentActivity.atividade}</span>
                        <span className="text-[9px] text-white/20 ml-2 shrink-0">(travado)</span>
                      </div>
                    ) : (
                      <select value={form.parent_id || ''} onChange={e => handleChange('parent_id', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded-xl px-3 h-11 text-[11px] text-white/80 focus:border-copper/50 outline-none appearance-none">
                        <option value="">Sem Pai (Raiz — Macro)</option>
                        {parentOptions.map((a: any) => <option key={a.id} value={a.id}>{a.nivel.toUpperCase()}: {a.atividade}</option>)}
                      </select>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'Engenharia' && (
                <div className="grid grid-cols-2 gap-x-8 gap-y-6 animate-enter">
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest flex items-center gap-2"><Calendar size={12} className="text-copper" /> Início Baseline</label>
                    <Input type="date" value={form.inicio_previsto} onChange={e => handleChange('inicio_previsto', e.target.value)} className="bg-black/40 border-white/10 h-12 text-sm font-mono focus:border-copper/50 transition-all" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest flex items-center gap-2"><Calendar size={12} className="text-copper" /> Término Baseline</label>
                    <Input type="date" value={form.termino_previsto} onChange={e => handleChange('termino_previsto', e.target.value)} className="bg-black/40 border-white/10 h-12 text-sm font-mono focus:border-copper/50 transition-all" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest flex items-center gap-2"><Link size={12} /> Dependência Antecessora</label>
                    <select value={form.dependencia_id || ''} onChange={e => handleChange('dependencia_id', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded-xl px-3 h-11 text-[11px] text-white/80 focus:border-copper/50 outline-none appearance-none">
                      <option value="">Nenhuma</option>
                      {depOptions.map((a: any) => <option key={a.id} value={a.id}>{a.atividade}</option>)}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Tipo de Dependência</label>
                    <div className="grid grid-cols-3 gap-1 bg-black/40 p-1 rounded-xl border border-white/5">
                      {[
                        { v: 'sem_dependencia', l: 'Sem dep.' },
                        { v: 'depende_termino', l: 'Término→Início' },
                        { v: 'depende_progresso', l: 'Por progresso' },
                      ].map(({ v, l }) => (
                        <button
                          key={v} type="button"
                          onClick={() => handleChange('dep_tipo', v)}
                          disabled={!form.dependencia_id && v !== 'sem_dependencia'}
                          className={`py-2 px-1 text-[8px] font-black uppercase rounded-lg transition-all leading-tight ${form.dep_tipo === v ? 'bg-copper text-void' : 'text-white/20 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed'}`}
                        >{l}</button>
                      ))}
                    </div>
                  </div>
                  <div className="col-span-2 p-6 bg-white/[0.02] border border-white/10 rounded-2xl flex items-center justify-between group">
                    <div>
                      <h4 className="text-[10px] font-black uppercase text-white mb-1 flex items-center gap-2">
                         <TrendingUp size={14} className="text-copper" /> Propagação Automática de Cronograma
                      </h4>
                      <p className="text-[9px] text-text-muted font-bold uppercase tracking-widest">Shifting dates for all successors on save</p>
                    </div>
                    <button type="button" onClick={() => setPropagateImpact(!propagateImpact)} className={`w-14 h-7 rounded-full p-1 transition-all ${propagateImpact ? 'bg-copper' : 'bg-white/10'}`}>
                      <div className={`w-5 h-5 rounded-full bg-white transition-all ${propagateImpact ? 'translate-x-7 shadow-[0_0_15px_white]' : 'translate-x-0 opacity-40'}`} />
                    </button>
                  </div>
                </div>
              )}

              {activeTab === 'Quantitativos' && (
                <div className="grid grid-cols-3 gap-x-6 gap-y-6 animate-enter">
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Total Qty</label>
                    <Input type="number" value={form.total_qty} onChange={e => handleChange('total_qty', parseFloat(e.target.value))} className="bg-black/40 border-white/10 h-11 text-xs font-mono" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Exec Qty</label>
                    <Input type="number" value={form.exec_qty} onChange={e => handleChange('exec_qty', parseFloat(e.target.value))} className="bg-black/40 border-white/10 h-11 text-xs font-mono text-copper" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Unidade</label>
                    <select value={form.unidade} onChange={e => handleChange('unidade', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded-xl px-3 h-11 text-[11px] text-white/80 outline-none">
                      {['un', 'm', 'm²', 'm³', 'kg', 'ton', 'vb', 'cj'].map(u => <option key={u} value={u}>{u}</option>)}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Avanço (%)</label>
                    <Input type="number" value={form.conclusao_pct} onChange={e => handleChange('conclusao_pct', parseFloat(e.target.value))} className="bg-black/40 border-white/10 h-11 text-sm font-black text-copper" />
                  </div>
                </div>
              )}

              {activeTab === 'Análise' && (
                <div className="space-y-6 animate-enter">
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest flex items-center gap-2"><Info size={14} /> Notas de Campo / Impedimentos</label>
                    <textarea value={form.observacoes} onChange={e => handleChange('observacoes', e.target.value)} rows={5} className="w-full bg-black/40 border border-white/10 rounded-2xl p-4 text-xs text-white/80 focus:border-copper/50 outline-none transition-all resize-none" />
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-8 bg-black/60 border-t border-white/5 flex justify-between items-center">
              <div className="flex flex-col">
                <span className="text-[9px] text-white/20 uppercase font-black tracking-widest">Configuração Técnica</span>
                <span className="text-[10px] text-copper font-mono font-bold uppercase">{form.atividade || 'Nova Atividade'}</span>
              </div>
              <div className="flex gap-4">
                <Button variant="ghost" onClick={onClose} className="text-white/40 hover:text-white uppercase text-[10px] font-black tracking-widest">Cancelar</Button>
                <Button 
                  onClick={() => mutation.mutate(form)} disabled={mutation.isPending}
                  className="bg-copper hover:bg-copper/90 text-void font-black px-12 h-12 rounded-xl shadow-[0_0_30px_rgba(201,139,42,0.3)] uppercase text-[10px] tracking-widest transition-all hover:-translate-y-1"
                >
                  {mutation.isPending ? <Loader2 className="animate-spin" size={18} /> : <><Save size={18} className="mr-2" /> Salvar Configuração</>}
                </Button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
