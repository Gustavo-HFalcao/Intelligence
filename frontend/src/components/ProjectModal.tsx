import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Save, Briefcase, User, MapPin, DollarSign, Calendar, Info, Loader2, CheckCircle, AlertCircle, Search } from 'lucide-react'
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

type GeoState = 'idle' | 'searching' | 'found' | 'notfound' | 'confirmed'

export default function ProjectModal({ isOpen, onClose, editingProject }: ProjectModalProps) {
  const queryClient = useQueryClient()
  const geoTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [form, setForm] = useState<any>({
    contrato: '',
    projeto: '',
    cliente: '',
    gestor: '',
    localizacao: '',
    valor_contratado: 0,
    inicio: '',
    termino: '',
    status: 'Em Execução',
    latitude: 0,
    longitude: 0,
    potencia_kwp_contratada: 0,
    prioridade: 'Normal',
    terceirizado: false,
    dias_uteis_semana: 'seg,ter,qua,qui,sex',
    obs: '',
  })

  // Geocoding state
  const [geoState, setGeoState] = useState<GeoState>('idle')
  const [geoResult, setGeoResult] = useState<{ display: string; lat: number; lng: number } | null>(null)

  useEffect(() => {
    if (editingProject) {
      setForm({
        ...editingProject,
        inicio: editingProject.inicio || editingProject.data_inicio
          ? (editingProject.inicio || editingProject.data_inicio || '').slice(0, 10) : '',
        termino: editingProject.termino || editingProject.data_termino
          ? (editingProject.termino || editingProject.data_termino || '').slice(0, 10) : '',
        latitude: editingProject.latitude || 0,
        longitude: editingProject.longitude || 0,
        potencia_kwp_contratada: editingProject.potencia_kwp_contratada || editingProject.potencia_kwp || 0,
      })
      if (editingProject.localizacao && editingProject.latitude) {
        setGeoState('confirmed')
        setGeoResult({
          display: editingProject.localizacao,
          lat: editingProject.latitude,
          lng: editingProject.longitude,
        })
      }
    } else {
      setForm({
        contrato: '',
        projeto: '',
        cliente: '',
        gestor: '',
        localizacao: '',
        valor_contratado: 0,
        inicio: '',
        termino: '',
        status: 'Em Execução',
        latitude: 0,
        longitude: 0,
        potencia_kwp_contratada: 0,
        prioridade: 'Normal',
        terceirizado: false,
        dias_uteis_semana: 'seg,ter,qua,qui,sex',
        obs: '',
      })
      setGeoState('idle')
      setGeoResult(null)
    }
  }, [editingProject, isOpen])

  // Debounced geocoding when localizacao changes
  useEffect(() => {
    if (geoTimeout.current) clearTimeout(geoTimeout.current)
    const loc = form.localizacao?.trim()
    if (!loc || loc.length < 5) {
      if (geoState !== 'confirmed') { setGeoState('idle'); setGeoResult(null) }
      return
    }
    if (geoState === 'confirmed' && geoResult?.display === loc) return

    setGeoState('searching')
    geoTimeout.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(loc)}&format=json&limit=1`,
          { headers: { 'User-Agent': 'Bomtempo-Platform/1.0' } }
        )
        const data = await res.json()
        if (data?.length) {
          setGeoResult({ display: data[0].display_name, lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) })
          setGeoState('found')
        } else {
          setGeoResult(null)
          setGeoState('notfound')
        }
      } catch {
        setGeoState('notfound')
      }
    }, 800)
  }, [form.localizacao])

  function confirmGeo() {
    if (!geoResult) return
    setForm((f: any) => ({ ...f, latitude: geoResult.lat, longitude: geoResult.lng }))
    setGeoState('confirmed')
  }

  function rejectGeo() {
    setGeoResult(null)
    setGeoState('idle')
    setForm((f: any) => ({ ...f, localizacao: '', latitude: 0, longitude: 0 }))
  }

  const mutation = useMutation({
    mutationFn: async (data: any) => {
      const payload = {
        ...data,
        data_inicio: data.inicio,
        data_termino: data.termino,
      }
      const url = editingProject
        ? `/hub/contratos/${encodeURIComponent(editingProject.contrato)}`
        : '/hub/contratos'
      if (editingProject) {
        const result = await api.patch(url, payload).then(r => r.data)
        // Backend pode retornar 200 com {ok:false, error:"..."} — trata como erro
        if (result?.ok === false) throw new Error(result.error || 'Erro ao salvar projeto')
        return result
      }
      return api.post(url, payload).then(r => r.data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hub-contratos'] })
      queryClient.invalidateQueries({ queryKey: ['contratos-list'] })
      queryClient.invalidateQueries({ queryKey: ['hub-contratos-list'] })
      onClose()
    }
  })


  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    mutation.mutate(form)
  }

  const handleChange = (k: string, v: any) => {
    setForm((prev: any) => ({ ...prev, [k]: v }))
    // Reset geo confirmation if location is edited
    if (k === 'localizacao' && geoState === 'confirmed') setGeoState('idle')
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
                    <Info size={12} /> Código do Contrato *
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
                    <Briefcase size={12} /> Nome do Projeto *
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

                {/* Localização com geocoding */}
                <div className="space-y-2 md:col-span-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <MapPin size={12} /> Localização
                    {geoState === 'searching' && <span className="text-copper/60 text-[9px] ml-1">buscando...</span>}
                    {geoState === 'confirmed' && <span className="text-teal-400 text-[9px] ml-1">✓ coordenadas confirmadas</span>}
                  </label>
                  <div className="relative">
                    <Input
                      value={form.localizacao}
                      onChange={(e) => handleChange('localizacao', e.target.value)}
                      placeholder="Cidade/Estado ou endereço completo"
                      className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all pr-10"
                    />
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      {geoState === 'searching' && <Loader2 size={14} className="animate-spin text-copper/60" />}
                      {geoState === 'confirmed' && <CheckCircle size={14} className="text-teal-400" />}
                      {geoState === 'notfound' && <AlertCircle size={14} className="text-red-400" />}
                    </div>
                  </div>

                  {/* Geocoding result card */}
                  <AnimatePresence>
                    {geoState === 'found' && geoResult && (
                      <motion.div
                        initial={{ opacity: 0, y: -6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        className="p-3 rounded-xl border"
                        style={{ background: `${TEAL}08`, borderColor: `${TEAL}30` }}
                      >
                        <div className="flex items-start gap-3">
                          <MapPin size={14} style={{ color: TEAL }} className="shrink-0 mt-0.5" />
                          <div className="flex-1 min-w-0">
                            <div className="text-[10px] font-bold uppercase tracking-widest mb-1" style={{ color: TEAL }}>
                              Localização encontrada — confirme:
                            </div>
                            <div className="text-xs text-white/80 leading-relaxed">{geoResult.display}</div>
                            <div className="text-[9px] font-mono text-white/30 mt-1">
                              {geoResult.lat.toFixed(6)}, {geoResult.lng.toFixed(6)}
                            </div>
                          </div>
                        </div>
                        <div className="flex gap-2 mt-3">
                          <button
                            type="button"
                            onClick={confirmGeo}
                            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-widest transition-all"
                            style={{ background: TEAL, color: '#000' }}
                          >
                            <CheckCircle size={11} /> Sim, confirmar
                          </button>
                          <button
                            type="button"
                            onClick={rejectGeo}
                            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-widest transition-all"
                            style={{ background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.25)', color: '#f87171' }}
                          >
                            <X size={11} /> Não, reescrever
                          </button>
                        </div>
                      </motion.div>
                    )}
                    {geoState === 'notfound' && (
                      <motion.div
                        initial={{ opacity: 0, y: -6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="p-3 rounded-xl border border-red-500/20 bg-red-500/5 text-xs text-red-400"
                      >
                        <AlertCircle size={12} className="inline mr-1.5" />
                        Localização não encontrada. Tente ser mais específico (ex: "São Paulo, SP" ou um endereço completo).
                      </motion.div>
                    )}
                  </AnimatePresence>
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

                {/* Potência Contratada */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Info size={12} /> Potência Contratada (kWp)
                  </label>
                  <Input
                    type="number"
                    step="0.1"
                    value={form.potencia_kwp_contratada || 0}
                    onChange={(e) => handleChange('potencia_kwp_contratada', parseFloat(e.target.value))}
                    className="bg-black/40 border-white/10 h-12 text-sm focus:border-copper transition-all font-mono"
                  />
                  <p className="text-[9px] text-text-muted">Potência instalada iniciará em 0 e será atualizada via O&M.</p>
                </div>

                {/* Datas */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Calendar size={12} /> Data de Início (Baseline) *
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
                    <Calendar size={12} /> Data de Término (Deadline) *
                  </label>
                  <Input
                    type="date"
                    required
                    value={form.termino}
                    onChange={(e) => handleChange('termino', e.target.value)}
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

                {/* Regime */}
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <Info size={12} /> Regime de Execução
                  </label>
                  <div className="flex items-center gap-3 h-12">
                    <input
                      type="checkbox"
                      checked={!!form.terceirizado}
                      onChange={(e) => handleChange('terceirizado', e.target.checked)}
                      className="w-5 h-5 rounded border-white/10 bg-black/40"
                      style={{ accentColor: COPPER }}
                    />
                    <span className="text-sm text-white">Projeto Terceirizado</span>
                  </div>
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
                            background: isActive ? COPPER : 'rgba(255,255,255,0.04)',
                            border: `1px solid ${isActive ? COPPER : 'rgba(255,255,255,0.08)'}`,
                            color: isActive ? '#000' : 'rgba(255,255,255,0.6)',
                            borderRadius: 8, padding: '8px 16px', fontSize: 12,
                            fontWeight: 700, cursor: 'pointer', transition: 'all 0.15s', letterSpacing: '0.05em',
                          }}
                        >
                          {LABELS[dia]}
                        </button>
                      )
                    })}
                  </div>
                  <p className="text-[9px] text-text-muted italic">Usado nos cálculos de prazo e SPI.</p>
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
                  Erro: {(mutation.error as any)?.message || 'Erro desconhecido'}
                </div>
              )}
            </form>

            {/* Footer */}
            <div className="p-6 bg-white/[0.02] border-t border-white/5 flex justify-end gap-3">
              <Button variant="ghost" onClick={onClose} className="text-text-muted hover:text-white">
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
                  <><Save size={18} className="mr-2" /> Salvar Projeto</>
                )}
              </Button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
