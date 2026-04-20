import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Clock, Plus, MessageSquare, AlertTriangle, 
  Calendar, CheckCircle, DollarSign, FileText, 
  ChevronLeft, ChevronRight, X, Send, User
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'

interface TimelineEntry {
  id: string
  tipo: string
  titulo: string
  descricao: string
  autor: string
  created_at: string
  is_cost: boolean
  custo_valor?: string
}

interface TimelineSidebarProps {
  contrato: string
  isOpen: boolean
  onToggle: () => void
}

const EVENT_TYPES = [
  { label: 'Atualização', icon: MessageSquare, color: '#3B82F6' },
  { label: 'Atraso', icon: AlertTriangle, color: '#EF4444' },
  { label: 'Reunião', icon: Calendar, color: '#A855F7' },
  { label: 'Decisão', icon: CheckCircle, color: '#10B981' },
  { label: 'Custo Extra', icon: DollarSign, color: '#C98B2A' },
  { label: 'Documento', icon: FileText, color: '#64748B' },
]

export default function TimelineSidebar({ contrato, isOpen, onToggle }: TimelineSidebarProps) {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    tipo: 'Atualização',
    titulo: '',
    descricao: '',
    valor: ''
  })

  const { data, isLoading } = useQuery({
    queryKey: ['hub-timeline', contrato],
    queryFn: () => api.get(`/hub/timeline?contrato=${encodeURIComponent(contrato)}`).then(r => r.data),
    enabled: !!contrato && isOpen
  })

  const mutation = useMutation({
    mutationFn: (newEntry: any) => api.post('/hub/timeline', { ...newEntry, contrato }).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hub-timeline'] })
      setShowForm(false)
      setFormData({ tipo: 'Atualização', titulo: '', descricao: '', valor: '' })
    }
  })

  const events: TimelineEntry[] = data?.eventos ?? []

  return (
    <div className={`fixed top-0 left-0 bottom-0 z-50 flex transition-transform duration-500 ease-in-out ${isOpen ? 'translate-x-[0]' : '-translate-x-full'}`}>
      <div className="w-[380px] h-full bg-[#081210]/95 backdrop-blur-2xl border-r border-white/10 shadow-[20px_0_50px_rgba(0,0,0,0.5)] flex flex-col pointer-events-auto">
        {/* Header */}
        <div className="p-6 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center justify-between mb-4">
             <div>
                <h3 className="text-sm font-black uppercase tracking-[0.2em] text-copper">Timeline do Projeto</h3>
                <p className="text-[10px] text-text-muted font-bold uppercase tracking-widest mt-1">Registros de Campo & Histórico</p>
             </div>
             <Button variant="ghost" size="icon" onClick={onToggle} className="text-white/40 hover:text-white">
                <X size={20} />
             </Button>
          </div>
          <Button 
            onClick={() => setShowForm(true)}
            className="w-full h-12 bg-copper text-void font-black uppercase tracking-wider rounded-xl shadow-[0_0_20px_rgba(201,139,42,0.2)]"
          >
            <Plus size={18} className="mr-2" /> Novo Registro
          </Button>
        </div>

        {/* Feed */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-6">
          <AnimatePresence mode="popLayout">
            {showForm && (
              <motion.div 
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-white/5 border border-copper/30 rounded-2xl p-5 mb-8"
              >
                <div className="flex flex-col gap-4">
                  <div className="grid grid-cols-2 gap-2">
                    {EVENT_TYPES.map(t => (
                      <button 
                        key={t.label}
                        onClick={() => setFormData({...formData, tipo: t.label})}
                        className={`p-2 rounded-lg border text-[9px] font-black uppercase tracking-tighter flex flex-col items-center gap-1 transition-all ${formData.tipo === t.label ? 'bg-copper border-copper text-void' : 'bg-white/5 border-white/10 text-white/40 hover:border-white/20'}`}
                      >
                        <t.icon size={14} />
                        {t.label}
                      </button>
                    ))}
                  </div>
                  <input 
                    placeholder="Título do Evento..."
                    className="bg-black/40 border border-white/10 rounded-xl px-4 h-10 text-xs text-white outline-none focus:border-copper transition-all"
                    value={formData.titulo}
                    onChange={e => setFormData({...formData, titulo: e.target.value})}
                  />
                  {formData.tipo === 'Custo Extra' && (
                    <div className="relative">
                      <span className="absolute left-4 top-1/2 -translate-y-1/2 text-[10px] text-copper">R$</span>
                      <input 
                        placeholder="0,00"
                        className="w-full bg-black/40 border border-white/10 rounded-xl pl-10 pr-4 h-10 text-xs text-white outline-none focus:border-copper transition-all font-mono"
                        value={formData.valor}
                        onChange={e => setFormData({...formData, valor: e.target.value})}
                      />
                    </div>
                  )}
                  <textarea 
                    placeholder="Descrição detalhada..."
                    className="bg-black/40 border border-white/10 rounded-xl p-4 text-xs text-white outline-none focus:border-copper transition-all min-h-[100px] resize-none"
                    value={formData.descricao}
                    onChange={e => setFormData({...formData, descricao: e.target.value})}
                  />
                  <div className="flex gap-2 pt-2">
                    <Button variant="ghost" className="flex-1 text-white/60 font-bold uppercase text-[10px]" onClick={() => setShowForm(false)}>Cancelar</Button>
                    <Button 
                      className="flex-1 bg-copper text-void font-black uppercase text-[10px]" 
                      onClick={() => mutation.mutate(formData)}
                      disabled={mutation.isPending}
                    >
                      {mutation.isPending ? 'Salvando...' : 'Registrar'}
                    </Button>
                  </div>
                </div>
              </motion.div>
            )}

            {events.length > 0 ? (
              events.map((e, idx) => (
                <motion.div 
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  key={e.id} 
                  className="flex gap-4 group"
                >
                  <div className="flex flex-col items-center">
                    <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-copper group-hover:border-copper/40 transition-colors">
                      {(() => {
                        const type = EVENT_TYPES.find(t => t.label === e.tipo) || EVENT_TYPES[0]
                        return <type.icon size={18} />
                      })()}
                    </div>
                    <div className="w-[1px] flex-1 bg-white/10 mt-2" />
                  </div>
                  <div className="flex-1 pb-8">
                     <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] font-black uppercase text-copper/80 tracking-widest">{e.tipo}</span>
                        <span className="text-[9px] text-text-muted font-mono">{e.created_at}</span>
                     </div>
                     <h4 className="text-xs font-bold text-white uppercase mb-2 group-hover:text-copper transition-colors">{e.titulo}</h4>
                     <p className="text-xs text-text-muted leading-relaxed mb-3 line-clamp-3 group-hover:line-clamp-none transition-all">{e.descricao}</p>
                     {e.is_cost && e.custo_valor && (
                        <div className="inline-flex items-center gap-2 px-3 py-1 bg-red-500/10 border border-red-500/20 rounded-lg text-red-500 mb-3">
                           <DollarSign size={10} />
                           <span className="text-[9px] font-black font-mono">R$ {parseFloat(e.custo_valor).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
                        </div>
                     )}
                     <div className="flex items-center gap-2">
                        <User size={10} className="text-copper/40" />
                        <span className="text-[9px] text-text-muted font-bold italic">@{e.autor}</span>
                     </div>
                  </div>
                </motion.div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center h-40 opacity-20">
                <Clock size={32} className="mb-2" />
                <span className="text-[10px] font-black uppercase tracking-widest">Sem registros</span>
              </div>
            )}
          </AnimatePresence>
        </div>
      </div>
      
      {/* Toggle Button (visible when closed) */}
      <button 
        onClick={onToggle}
        className={`absolute left-full top-[50%] -translate-y-1/2 p-2 bg-[#081210]/95 border border-white/10 border-l-0 rounded-r-xl text-copper hover:text-white transition-all shadow-[10px_0_20px_rgba(0,0,0,0.3)] ${isOpen ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}
      >
        <ChevronRight size={24} />
      </button>
    </div>
  )
}
