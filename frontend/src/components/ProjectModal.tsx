import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Save, Briefcase, User, MapPin, DollarSign, Calendar, Info, Loader2 } from 'lucide-react'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'

interface ProjectModalProps {
  isOpen: boolean
  onClose: () => void
  editingProject?: any
}

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'

export default function ProjectModal({ isOpen, onClose, editingProject }: ProjectModalProps) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<any>({
    contrato: '',
    projeto: '',
    cliente: '',
    localizacao: '',
    valor_contratado: 0,
    inicio: '',
    termino: '',
    status: 'Em Execução',
    latitude: 0,
    longitude: 0
  })

  useEffect(() => {
    if (editingProject) {
      setForm({
        ...editingProject,
        inicio: editingProject.inicio ? editingProject.inicio.slice(0, 10) : '',
        termino: editingProject.termino ? editingProject.termino.slice(0, 10) : '',
        latitude: editingProject.latitude || 0,
        longitude: editingProject.longitude || 0
      })
    } else {
      setForm({
        contrato: '',
        projeto: '',
        cliente: '',
        localizacao: '',
        valor_contratado: 0,
        inicio: '',
        termino: '',
        status: 'Em Execução',
        latitude: 0,
        longitude: 0
      })
    }
  }, [editingProject, isOpen])

  const mutation = useMutation({
    mutationFn: (data: any) => {
      const url = editingProject 
        ? `/api/hub/contratos/${editingProject.contrato}` 
        : '/api/hub/contratos'
      const method = editingProject ? 'PATCH' : 'POST'
      if (editingProject) return api.patch(url, data).then(r => r.data)
      return api.post(url, data).then(r => r.data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hub-contratos'] })
      onClose()
    }
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    mutation.mutate(form)
  }

  const handleChange = (k: string, v: any) => {
    setForm((prev: any) => ({ ...prev, [k]: v }))
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
          />
          
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="relative w-full max-w-2xl bg-[#081210] border border-white/10 rounded-2xl overflow-hidden shadow-2xl shadow-copper/10"
          >
            {/* Header */}
            <div className="p-6 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-copper/10 border border-copper/30">
                  <Briefcase className="text-copper" size={20} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white uppercase tracking-tight">
                    {editingProject ? 'Editar Projeto' : 'Novo Projeto'}
                  </h3>
                  <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">
                    Configuração de Célula Operacional
                  </p>
                </div>
              </div>
              <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-full text-text-muted transition-colors">
                <X size={20} />
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="p-8 space-y-6 max-h-[70vh] overflow-y-auto custom-scrollbar">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                
                {/* Código do Contrato */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Info size={12} /> Código do Contrato
                  </label>
                  <Input 
                    required
                    disabled={!!editingProject}
                    value={form.contrato}
                    onChange={(e) => handleChange('contrato', e.target.value)}
                    placeholder="Ex: CON-030-2026"
                    className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all font-mono"
                  />
                </div>

                {/* Nome do Projeto */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Briefcase size={12} /> Nome do Projeto
                  </label>
                  <Input 
                    required
                    value={form.projeto}
                    onChange={(e) => handleChange('projeto', e.target.value)}
                    placeholder="Nome da Obra/Contrato"
                    className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all"
                  />
                </div>

                {/* Cliente */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <User size={12} /> Cliente
                  </label>
                  <Input 
                    value={form.cliente}
                    onChange={(e) => handleChange('cliente', e.target.value)}
                    placeholder="Nome do Cliente"
                    className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all"
                  />
                </div>

                {/* Localização */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <MapPin size={12} /> Localização
                  </label>
                  <Input 
                    value={form.localizacao}
                    onChange={(e) => handleChange('localizacao', e.target.value)}
                    placeholder="Cidade/Estado"
                    className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all"
                  />
                </div>

                {/* Valor Contratado */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <DollarSign size={12} /> Valor Contratado (R$)
                  </label>
                  <Input 
                    type="number"
                    step="0.01"
                    value={form.valor_contratado}
                    onChange={(e) => handleChange('valor_contratado', parseFloat(e.target.value))}
                    className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all font-mono"
                  />
                </div>

                {/* Gestor */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <User size={12} /> Gestor Responsável
                  </label>
                  <Input 
                    value={form.gestor || ''}
                    onChange={(e) => handleChange('gestor', e.target.value)}
                    placeholder="Nome do Gestor"
                    className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all"
                  />
                </div>

                {/* Datas Baseline */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Calendar size={12} /> Data de Início (Project Baseline)
                  </label>
                  <Input 
                    type="date"
                    required
                    value={form.inicio}
                    onChange={(e) => handleChange('inicio', e.target.value)}
                    className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all font-mono"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Calendar size={12} /> Data de Término (Deadline Final)
                  </label>
                  <Input 
                    type="date"
                    required
                    value={form.termino}
                    onChange={(e) => handleChange('termino', e.target.value)}
                    className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all font-mono"
                  />
                </div>

                {/* Contato */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Info size={12} /> Contato / Telefone
                  </label>
                  <Input 
                    value={form.contato || ''}
                    onChange={(e) => handleChange('contato', e.target.value)}
                    placeholder="(00) 00000-0000"
                    className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all font-mono"
                  />
                </div>

                {/* Prioridade */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Info size={12} /> Prioridade
                  </label>
                  <select 
                    value={form.prioridade || 'Normal'}
                    onChange={(e) => handleChange('prioridade', e.target.value)}
                    className="w-full bg-black/40 border border-white/10 rounded-md px-3 h-12 text-sm text-white focus:border-copper outline-none appearance-none cursor-pointer"
                  >
                    <option value="Baixa">Baixa</option>
                    <option value="Normal">Normal</option>
                    <option value="Alta">Alta</option>
                    <option value="Crítica">Crítica</option>
                  </select>
                </div>

                {/* Terceirizado */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Info size={12} /> Regime de Execução
                  </label>
                  <div className="flex items-center gap-3 h-12">
                    <input 
                      type="checkbox"
                      checked={!!form.terceirizado}
                      onChange={(e) => handleChange('terceirizado', e.target.checked)}
                      className="w-5 h-5 rounded border-white/10 bg-black/40 text-copper focus:ring-copper"
                    />
                    <span className="text-sm text-white">Projeto Terceirizado</span>
                  </div>
                </div>

                {/* Potência kWp */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Info size={12} /> Potência Instalada (kWp)
                  </label>
                  <Input 
                    type="number"
                    step="0.1"
                    value={form.potencia_kwp || 0}
                    onChange={(e) => handleChange('potencia_kwp', parseFloat(e.target.value))}
                    className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all font-mono"
                  />
                </div>

                {/* Meta de Produtividade Diária */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Info size={12} /> Meta Diária (Unidades)
                  </label>
                  <Input 
                    type="number"
                    value={form.meta_prod_diaria || 0}
                    onChange={(e) => handleChange('meta_prod_diaria', parseInt(e.target.value))}
                    className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all font-mono"
                  />
                </div>

                {/* Dias Úteis */}
                <div className="space-y-2 md:col-span-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Calendar size={12} /> Dias Úteis da Semana
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {(['seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom'] as const).map((dia) => {
                      const ORDER = ['seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom']
                      const current = (form.dias_uteis_semana || 'seg,ter,qua,qui,sex')
                        .split(',').map((d: string) => d.trim()).filter(Boolean)
                      const isActive = current.includes(dia)
                      const LABELS: Record<string, string> = {
                        seg: 'Seg', ter: 'Ter', qua: 'Qua', qui: 'Qui',
                        sex: 'Sex', sab: 'Sáb', dom: 'Dom',
                      }
                      const toggle = () => {
                        const next = isActive
                          ? current.filter((d: string) => d !== dia)
                          : [...current, dia]
                        const sorted = ORDER.filter(d => next.includes(d))
                        handleChange('dias_uteis_semana', sorted.join(','))
                      }
                      return (
                        <button
                          key={dia}
                          type="button"
                          onClick={toggle}
                          style={{
                            background: isActive ? '#C98B2A' : 'rgba(255,255,255,0.04)',
                            border: `1px solid ${isActive ? '#C98B2A' : 'rgba(255,255,255,0.08)'}`,
                            color: isActive ? '#000' : 'rgba(255,255,255,0.6)',
                            borderRadius: 8,
                            padding: '8px 16px',
                            fontSize: 12,
                            fontWeight: 700,
                            cursor: 'pointer',
                            transition: 'all 0.15s',
                            letterSpacing: '0.05em',
                          }}
                        >
                          {LABELS[dia]}
                        </button>
                      )
                    })}
                  </div>
                  <p className="text-[9px] text-text-muted italic">Clique nos dias para ativar/desativar. Usado nos cálculos de prazo.</p>
                </div>

                {/* Observações */}
                <div className="space-y-2 md:col-span-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Info size={12} /> Observações Adicionais
                  </label>
                  <textarea 
                    value={form.obs || ''}
                    onChange={(e) => handleChange('obs', e.target.value)}
                    rows={3}
                    className="w-full bg-black/40 border border-white/10 rounded-md p-3 text-sm text-white focus:border-copper outline-none transition-all resize-none"
                    placeholder="Notas técnicas, financeiras ou operacionais..."
                  />
                </div>
              </div>

              {mutation.isError && (
                <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-500 text-xs font-mono">
                  Erro: {mutation.error.message}
                </div>
              )}
            </form>

            {/* Footer */}
            <div className="p-6 bg-white/[0.02] border-t border-white/5 flex justify-end gap-3">
              <Button 
                variant="ghost" 
                onClick={onClose}
                className="text-text-muted hover:text-white"
              >
                Cancelar
              </Button>
              <Button 
                onClick={handleSubmit}
                disabled={mutation.isPending}
                className="bg-copper hover:bg-copper/90 text-void font-bold px-8 shadow-[0_0_15px_rgba(201,139,42,0.2)]"
              >
                {mutation.isPending ? (
                  <Loader2 className="animate-spin" size={18} />
                ) : (
                  <>
                    <Save size={18} className="mr-2" />
                    Salvar Projeto
                  </>
                )}
              </Button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
