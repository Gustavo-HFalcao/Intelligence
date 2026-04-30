import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X, Save, Activity, User, Calendar, Info, Loader2, Target,
  AlertTriangle, Layers, TrendingUp, Hash, Ruler, Link,
  CheckCircle2, AlertCircle, DollarSign, Clock, Flag
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

function workingDaysBetween(a: string, b: string): number {
  if (!a || !b) return 0
  try {
    let d0 = new Date(a + 'T12:00:00')
    let d1 = new Date(b + 'T12:00:00')
    if (d1 < d0) return 0
    let count = 0
    const cur = new Date(d0)
    while (cur <= d1) {
      const wd = cur.getDay()
      if (wd !== 0 && wd !== 6) count++
      cur.setDate(cur.getDate() + 1)
    }
    return count
  } catch { return 0 }
}

function addWorkingDays(start: string, days: number): string {
  if (!start || days <= 0) return start
  try {
    const d = new Date(start + 'T12:00:00')
    let added = 0
    while (added < days - 1) {
      d.setDate(d.getDate() + 1)
      if (d.getDay() !== 0 && d.getDay() !== 6) added++
    }
    return d.toISOString().slice(0, 10)
  } catch { return start }
}

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
    dias_planejados: 0,
    conclusao_pct: 0,
    peso_pct: 1,
    peso_valor: 0,
    critico: 'Nao',
    observacoes: '',
    contrato: contrato,
    nivel: 'macro',
    parent_id: '',
    dependencia_id: '',
    dep_tipo: 'sem_dependencia',
    total_qty: 0,
    exec_qty: 0,
    unidade: 'un',
    tipo_medicao: 'quantidade',  // 'marco' | 'porcentagem' | 'quantidade'
    status_atividade: 'Pendente'
  })

  // Nível derivado do pai — não mutável após criação
  const derivedNivel = parentActivity
    ? (parentActivity.nivel === 'macro' || !parentActivity.nivel ? 'micro' : 'sub')
    : 'macro'

  const isEditing = !!editingActivity

  // Query for dependency options only
  const { data: cronData } = useQuery({
    queryKey: ['hub-cronograma', contrato],
    queryFn: () => api.get(`/hub/cronograma?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    enabled: isOpen
  })

  useEffect(() => {
    if (editingActivity) {
      const tm = editingActivity.tipo_medicao || (
        editingActivity.unidade === 'marco' ? 'marco' :
        editingActivity.unidade === '%' ? 'porcentagem' : 'quantidade'
      )
      setForm({
        ...editingActivity,
        tipo_medicao: tm,
        dep_tipo: editingActivity.dep_tipo || 'sem_dependencia',
        inicio_previsto: editingActivity.inicio_previsto ? editingActivity.inicio_previsto.slice(0, 10) : '',
        termino_previsto: editingActivity.termino_previsto ? editingActivity.termino_previsto.slice(0, 10) : '',
        dias_planejados: editingActivity.dias_planejados || 0,
      })
    } else {
      setForm({
        atividade: '',
        fase: parentActivity?.fase || 'Geral',
        fase_macro: parentActivity?.fase_macro || 'Execução',
        responsavel: '',
        inicio_previsto: '',
        termino_previsto: '',
        dias_planejados: 0,
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
        tipo_medicao: 'quantidade',
        status_atividade: 'Pendente'
      })
    }
    setActiveTab('Geral')
    setPropagateImpact(false)
  }, [editingActivity, parentActivity, isOpen, contrato])

  const mutation = useMutation({
    mutationFn: (data: any) => {
      const payload = { ...data, propagar_impacto: propagateImpact, old_termino: editingActivity?.termino_previsto }
      // Enforce: when tipo_medicao === 'marco', use 'marco' as unidade and remove qty
      if (payload.tipo_medicao === 'marco') {
        payload.unidade = 'marco'
        payload.total_qty = 1
      } else if (payload.tipo_medicao === 'porcentagem') {
        payload.unidade = '%'
      }
      if (isEditing) {
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

  function handleChange(k: string, v: any) {
    setForm((prev: any) => {
      const next = { ...prev, [k]: v }
      // Dias planejados calculado dinamicamente
      if (k === 'inicio_previsto' && next.termino_previsto) {
        next.dias_planejados = workingDaysBetween(v, next.termino_previsto)
      } else if (k === 'termino_previsto' && next.inicio_previsto) {
        next.dias_planejados = workingDaysBetween(next.inicio_previsto, v)
      } else if (k === 'dias_planejados' && next.inicio_previsto && v > 0) {
        next.termino_previsto = addWorkingDays(next.inicio_previsto, Number(v))
      }
      return next
    })
  }

  const allAtivs = cronData?.atividades ?? []
  const depOptions = allAtivs.filter((a: any) => a.id !== editingActivity?.id)

  const nivelLabel = isEditing
    ? (editingActivity.nivel || 'macro').toUpperCase()
    : derivedNivel.toUpperCase()

  const parentLabel = isEditing
    ? allAtivs.find((a: any) => a.id === editingActivity?.parent_id)?.atividade || 'Raiz (Macro)'
    : parentActivity?.atividade || 'Raiz (Macro)'

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
                    {isEditing ? 'Editar Atividade' : parentActivity ? `Nova ${derivedNivel.toUpperCase()} em "${parentActivity.atividade?.slice(0,30)}"` : 'Nova Atividade Macro'}
                  </h3>
                  <div className="flex items-center gap-2 mt-0.5">
                    {/* Nível + pai sempre visíveis mas nunca editáveis */}
                    <span className="text-[9px] text-teal-400 font-black uppercase tracking-widest px-1.5 py-0.5 bg-teal-400/10 rounded border border-teal-400/20">
                      {nivelLabel}
                    </span>
                    <span className="text-[9px] text-white/30 font-bold">↑ {parentLabel.slice(0, 25)}</span>
                    <span className="text-[9px] text-white/20 uppercase tracking-widest font-bold">HUB CRONOGRAMA</span>
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

                  {/* Nível — sempre travado, exibido como info */}
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Nível Hierárquico</label>
                    <div className="px-4 h-11 flex items-center bg-black/40 border border-teal-400/20 rounded-xl gap-2">
                      <span className="text-[11px] font-black uppercase text-teal-400">{nivelLabel}</span>
                      <span className="text-[9px] text-white/20">· não editável após criação</span>
                    </div>
                  </div>

                  {/* Pai — sempre travado */}
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Atividade Pai</label>
                    <div className="px-4 h-11 flex items-center bg-black/40 border border-white/5 rounded-xl gap-2">
                      <span className="text-[11px] text-white/60 truncate">{parentLabel.slice(0, 35)}</span>
                      <span className="text-[9px] text-white/20 shrink-0">· travado</span>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Fase / Código</label>
                    <Input value={form.fase} onChange={e => handleChange('fase', e.target.value)} placeholder="Ex: 1.1" className="bg-black/40 border-white/10 h-11 text-sm" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Disciplina (Fase Macro)</label>
                    <select value={form.fase_macro} onChange={e => handleChange('fase_macro', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded-xl px-3 h-11 text-[11px] text-white/80 focus:border-copper/50 outline-none">
                      {DISCIPLINAS.map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest flex items-center gap-2"><User size={12} /> Responsável</label>
                    <Input value={form.responsavel} onChange={e => handleChange('responsavel', e.target.value)} placeholder="Nome do responsável" className="bg-black/40 border-white/10 h-11 text-sm" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Criticidade</label>
                    <div className="grid grid-cols-2 gap-1 bg-black/40 p-1 rounded-xl border border-white/5">
                      {[['Nao', 'Normal'], ['Sim', 'Crítico']].map(([v, l]) => (
                        <button key={v} type="button" onClick={() => handleChange('critico', v)} className={`py-2 text-[9px] font-black uppercase rounded-lg transition-all ${form.critico === v ? (v === 'Sim' ? 'bg-red-500/80 text-white' : 'bg-copper text-void') : 'text-white/20 hover:bg-white/5'}`}>{l}</button>
                      ))}
                    </div>
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
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest flex items-center gap-2"><Clock size={12} className="text-copper" /> Dias Planejados (úteis)</label>
                    <Input
                      type="number" min={1}
                      value={form.dias_planejados}
                      onChange={e => handleChange('dias_planejados', parseInt(e.target.value) || 0)}
                      className="bg-black/40 border-white/10 h-12 text-sm font-mono focus:border-copper/50"
                      placeholder="Calculado por início + término"
                    />
                    <p className="text-[9px] text-white/20 font-mono">Alterar dias recalcula o término. Alterar datas recalcula os dias.</p>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Peso (%)</label>
                    <Input type="number" min={0} max={100} step={0.1} value={form.peso_pct} onChange={e => handleChange('peso_pct', parseFloat(e.target.value))} className="bg-black/40 border-white/10 h-12 text-sm font-mono" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest flex items-center gap-2"><Link size={12} /> Dependência Antecessora</label>
                    <select value={form.dependencia_id || ''} onChange={e => handleChange('dependencia_id', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded-xl px-3 h-11 text-[11px] text-white/80 focus:border-copper/50 outline-none appearance-none">
                      <option value="">Nenhuma</option>
                      {depOptions.map((a: any) => <option key={a.id} value={a.id}>{a.atividade}</option>)}
                    </select>
                  </div>
                  <div className="space-y-2 col-span-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Tipo de Dependência</label>
                    <div className="grid grid-cols-2 gap-1.5 bg-black/40 p-1.5 rounded-xl border border-white/5">
                      {[
                        { v: 'sem_dependencia',  l: 'Sem Dep.',          sub: 'Independente' },
                        { v: 'depende_termino',  l: 'FS · Fim→Início',   sub: 'Só inicia após término' },
                        { v: 'depende_inicio',   l: 'SS · Início→Início',sub: 'Inicia junto com a anterior' },
                        { v: 'depende_progresso',l: 'QS · Produção 1:1', sub: 'Avanço limitado pelo executado' },
                      ].map(({ v, l, sub }) => (
                        <button key={v} type="button"
                          onClick={() => handleChange('dep_tipo', v)}
                          disabled={!form.dependencia_id && v !== 'sem_dependencia'}
                          className={`py-2.5 px-3 text-left rounded-lg transition-all ${form.dep_tipo === v ? 'bg-copper text-void' : 'text-white/30 hover:bg-white/5 disabled:opacity-20 disabled:cursor-not-allowed'}`}
                        >
                          <div className="text-[9px] font-black uppercase leading-tight">{l}</div>
                          <div className={`text-[8px] mt-0.5 leading-tight ${form.dep_tipo === v ? 'text-void/60' : 'text-white/20'}`}>{sub}</div>
                        </button>
                      ))}
                    </div>
                    {/* Descrição do tipo selecionado */}
                    {form.dep_tipo === 'depende_progresso' && form.dependencia_id && (
                      <p className="text-[9px] text-copper/80 font-bold italic">
                        O avanço desta atividade fica limitado ao percentual executado da predecessora (regra 1:1).
                        Ex: se foram perfurados 500 de 1000 furos, só se pode vedar até 500.
                      </p>
                    )}
                    {form.dependencia_id && form.dep_tipo === 'sem_dependencia' && (
                      <p className="text-[9px] text-amber-400/80 font-bold">
                        ⚠ Antecessora selecionada mas sem tipo de dependência. Selecione FS, SS ou QS para ativar a restrição.
                      </p>
                    )}
                  </div>
                  <div className="col-span-2 p-6 bg-white/[0.02] border border-white/10 rounded-2xl flex items-center justify-between">
                    <div>
                      <h4 className="text-[10px] font-black uppercase text-white mb-1 flex items-center gap-2"><TrendingUp size={14} className="text-copper" /> Propagação Automática de Cronograma</h4>
                      <p className="text-[9px] text-text-muted font-bold uppercase tracking-widest">Desloca datas de todos os sucessores ao salvar</p>
                    </div>
                    <button type="button" onClick={() => setPropagateImpact(!propagateImpact)} className={`w-14 h-7 rounded-full p-1 transition-all ${propagateImpact ? 'bg-copper' : 'bg-white/10'}`}>
                      <div className={`w-5 h-5 rounded-full bg-white transition-all ${propagateImpact ? 'translate-x-7 shadow-[0_0_15px_white]' : 'translate-x-0 opacity-40'}`} />
                    </button>
                  </div>
                </div>
              )}

              {activeTab === 'Quantitativos' && (
                <div className="grid grid-cols-1 gap-6 animate-enter">
                  {/* Tipo de medição — define o comportamento */}
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Tipo de Medição</label>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { v: 'marco', l: 'Marco', desc: 'Concluído ou não — binário', icon: Flag },
                        { v: 'porcentagem', l: 'Porcentagem', desc: 'Avanço em % livre', icon: Activity },
                        { v: 'quantidade', l: 'Quantidade', desc: 'Medido por unidade física', icon: Hash },
                      ].map(({ v, l, desc, icon: Icon }) => (
                        <button
                          key={v} type="button"
                          onClick={() => handleChange('tipo_medicao', v)}
                          className={`p-4 rounded-xl border text-left transition-all ${form.tipo_medicao === v ? 'border-copper/60 bg-copper/10' : 'border-white/5 bg-black/30 hover:bg-white/5'}`}
                        >
                          <Icon size={16} className={form.tipo_medicao === v ? 'text-copper mb-2' : 'text-white/30 mb-2'} />
                          <div className={`text-[11px] font-black uppercase ${form.tipo_medicao === v ? 'text-copper' : 'text-white/50'}`}>{l}</div>
                          <div className="text-[9px] text-white/30 mt-0.5">{desc}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Marco: apenas status visual */}
                  {form.tipo_medicao === 'marco' && (
                    <div className="p-5 bg-copper/5 border border-copper/20 rounded-2xl flex items-center gap-4">
                      <Flag size={20} className="text-copper shrink-0" />
                      <div>
                        <div className="text-[11px] font-black uppercase text-copper">Marco de Projeto</div>
                        <div className="text-[10px] text-white/40 mt-0.5">
                          Sem quantidade. O progresso é 0% (pendente) ou 100% (concluído). Marcado como concluído via RDO.
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Porcentagem: só o % */}
                  {form.tipo_medicao === 'porcentagem' && (
                    <div className="space-y-2">
                      <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Avanço Atual (%)</label>
                      <div className="flex items-center gap-4">
                        <input
                          type="range" min={0} max={100} step={5}
                          value={form.conclusao_pct}
                          onChange={e => handleChange('conclusao_pct', Number(e.target.value))}
                          style={{ flex: 1, accentColor: '#C98B2A' }}
                        />
                        <span className="text-lg font-black font-mono text-copper w-16 text-right">{form.conclusao_pct}%</span>
                      </div>
                    </div>
                  )}

                  {/* Quantidade: total + unidade */}
                  {form.tipo_medicao === 'quantidade' && (
                    <div className="grid grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Quantidade Total</label>
                        <Input type="number" value={form.total_qty} onChange={e => handleChange('total_qty', parseFloat(e.target.value))} className="bg-black/40 border-white/10 h-11 text-xs font-mono" placeholder="Ex: 1456" />
                      </div>
                      <div className="space-y-2">
                        <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Executado (acumulado)</label>
                        <Input type="number" value={form.exec_qty} onChange={e => handleChange('exec_qty', parseFloat(e.target.value))} className="bg-black/40 border-white/10 h-11 text-xs font-mono text-copper" placeholder="0" />
                      </div>
                      <div className="space-y-2">
                        <label className="text-[10px] font-black text-white/40 uppercase tracking-widest">Unidade</label>
                        <select value={form.unidade} onChange={e => handleChange('unidade', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded-xl px-3 h-11 text-[11px] text-white/80 outline-none">
                          {['un', 'und', 'm', 'm²', 'm³', 'kg', 'ton', 'vb', 'cj', 'perf', 'pç', 'hr'].map(u => <option key={u} value={u}>{u}</option>)}
                        </select>
                      </div>
                      {form.total_qty > 0 && (
                        <div className="col-span-3">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[9px] text-white/30 uppercase font-bold">Progresso calculado</span>
                            <span className="text-[11px] font-black text-copper font-mono">
                              {form.exec_qty}/{form.total_qty} {form.unidade} · {Math.min(100, Math.round(form.exec_qty / form.total_qty * 100))}%
                            </span>
                          </div>
                          <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 99 }}>
                            <div style={{ width: `${Math.min(100, Math.round((form.exec_qty / form.total_qty) * 100))}%`, height: '100%', background: '#C98B2A', borderRadius: 99 }} />
                          </div>
                          <p className="text-[9px] text-white/20 mt-1">Barra calculada automaticamente. Não editável pelo operador de campo.</p>
                        </div>
                      )}
                    </div>
                  )}
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
                <span className="text-[9px] text-white/20 uppercase font-black tracking-widest">
                  {nivelLabel} · {form.tipo_medicao?.toUpperCase() || 'QUANTIDADE'}
                  {form.dias_planejados > 0 && ` · ${form.dias_planejados}d úteis`}
                </span>
                <span className="text-[10px] text-copper font-mono font-bold uppercase">{form.atividade || 'Nova Atividade'}</span>
              </div>
              <div className="flex gap-4">
                <Button variant="ghost" onClick={onClose} className="text-white/40 hover:text-white uppercase text-[10px] font-black tracking-widest">Cancelar</Button>
                <Button
                  onClick={() => mutation.mutate(form)} disabled={mutation.isPending}
                  className="bg-copper hover:bg-copper/90 text-void font-black px-12 h-12 rounded-xl shadow-[0_0_30px_rgba(201,139,42,0.3)] uppercase text-[10px] tracking-widest transition-all hover:-translate-y-1"
                >
                  {mutation.isPending ? <Loader2 className="animate-spin" size={18} /> : <><Save size={18} className="mr-2" /> Salvar</>}
                </Button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
