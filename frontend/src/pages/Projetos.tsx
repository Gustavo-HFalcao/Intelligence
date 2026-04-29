import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import {
  Briefcase, Plus, Search, Filter,
  MoreVertical, Edit2, Copy, Trash2,
  ChevronRight, MapPin, Target, Activity
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import ProjectModal from '@/components/ProjectModal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import './Dashboard.css'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'

async function api(path: string, opts?: RequestInit) {
  const r = await fetch(path, { credentials: 'include', ...opts })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export default function Projetos() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  
  // States
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('Todos')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingProject, setEditingProject] = useState<any>(null)
  const [isMenuOpen, setIsMenuOpen] = useState<string | null>(null)

  // Queries
  const { data, isLoading } = useQuery({
    queryKey: ['contratos-list'],
    queryFn: () => api('/api/hub/contratos'),
    staleTime: Infinity,
    refetchInterval: 30_000,
  })

  // Mutations
  const duplicateMutation = useMutation({
    mutationFn: (code: string) => api(`/api/hub/contratos/${code}/duplicate`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contratos-list'] })
      setIsMenuOpen(null)
    }
  })

  const deleteMutation = useMutation({
    mutationFn: (code: string) => api(`/api/hub/contratos/${code}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contratos-list'] })
      setIsMenuOpen(null)
    }
  })

  const contratos: any[] = useMemo(() => {
    let list = data?.contratos ?? []
    if (searchTerm) {
      list = list.filter((c: any) => 
        c.contrato?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.projeto?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.cliente?.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }
    if (statusFilter !== 'Todos') {
      list = list.filter((c: any) => c.status === statusFilter)
    }
    return list
  }, [data, searchTerm, statusFilter])

  function handleOpenCreate() {
    setEditingProject(null)
    setIsModalOpen(true)
  }

  function handleOpenEdit(project: any) {
    setEditingProject(project)
    setIsModalOpen(true)
    setIsMenuOpen(null)
  }

  function handleDelete(code: string) {
    if (confirm(`Deseja realmente excluir o projeto ${code}? Todas as atividades associadas serão removidas.`)) {
      deleteMutation.mutate(code)
    }
  }

  function statusStyle(s: string) {
    const map: any = {
      'Em Execução': { color: TEAL, bg: `${TEAL}15` },
      'Em Planejamento': { color: COPPER, bg: `${COPPER}15` },
      'Concluído': { color: '#3B82F6', bg: 'rgba(59,130,246,0.15)' },
      'Pausado': { color: '#888', bg: 'rgba(136,136,136,0.15)' },
      'Cancelado': { color: RED, bg: `${RED}15` },
    }
    return map[s] ?? { color: COPPER, bg: `${COPPER}15` }
  }

  return (
    <div className="flex flex-col gap-8 animate-enter">
      {/* ── HEADER ────────────────────────────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
              <Briefcase size={22} className="text-copper" />
            </div>
            <h1 className="font-display text-3xl font-black text-white uppercase tracking-tight">
              Projetos <span className="text-copper/40 font-light">&</span> Contratos
            </h1>
          </div>
          <p className="text-text-muted text-[10px] uppercase font-bold tracking-[0.3em] ml-1">
            Gestão Centralizada de Células Operacionais
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center gap-3">
          <div className="relative w-full sm:w-[280px]">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
            <Input 
              placeholder="Pesquisar projetos..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 bg-black/40 border-white/10 h-11 text-sm focus:border-copper"
            />
          </div>
          
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:flex-none">
              <Filter size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
              <select 
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="pl-9 pr-8 bg-black/40 border border-white/10 rounded-md h-11 text-xs text-white/80 focus:border-copper outline-none appearance-none cursor-pointer min-w-[140px]"
              >
                <option value="Todos">Todos Status</option>
                <option value="Em Execução">Em Execução</option>
                <option value="Em Planejamento">Em Planejamento</option>
                <option value="Concluído">Concluído</option>
                <option value="Pausado">Pausado</option>
              </select>
            </div>

            <Button 
              onClick={handleOpenCreate}
              className="bg-copper hover:bg-copper/90 text-void font-bold h-11 px-6 shadow-[0_0_20px_rgba(201,139,42,0.2)]"
            >
              <Plus className="mr-2" size={18} />
              Novo Projeto
            </Button>
          </div>
        </div>
      </div>

      {/* ── GRID ──────────────────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
           {[...Array(6)].map((_, i) => (
             <div key={i} className="h-[280px] bg-white/[0.02] border border-white/5 rounded-2xl animate-pulse" />
           ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {contratos.map((c) => {
            const style = statusStyle(c.status)
            const showActions = isMenuOpen === c.contrato

            return (
              <div 
                key={c.contrato}
                className="project-card-glow glass-panel rounded-2xl p-6 flex flex-col group border-white/5"
              >
                {/* Status & Code */}
                <div className="flex items-center justify-between mb-4">
                  <span className="status-badge" style={{ color: style.color, background: style.bg, borderColor: `${style.color}30` }}>
                    {c.status}
                  </span>
                  
                  <div className="relative">
                    <button 
                      onClick={(e) => {
                        e.stopPropagation()
                        setIsMenuOpen(showActions ? null : c.contrato)
                      }}
                      className="p-1.5 hover:bg-white/10 rounded-md text-text-muted transition-colors"
                    >
                      <MoreVertical size={16} />
                    </button>

                    {showActions && (
                      <div className="absolute right-0 top-8 w-48 bg-[#0e1a17] border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden py-1 animate-in fade-in slide-in-from-top-2 duration-200">
                        <button onClick={() => handleOpenEdit(c)} className="w-full flex items-center gap-3 px-4 py-2.5 text-[11px] font-bold uppercase tracking-widest text-white/70 hover:text-white hover:bg-white/5 transition-colors">
                          <Edit2 size={13} className="text-copper" /> Editar
                        </button>
                        <button 
                          onClick={() => duplicateMutation.mutate(c.contrato)} 
                          className="w-full flex items-center gap-3 px-4 py-2.5 text-[11px] font-bold uppercase tracking-widest text-white/70 hover:text-white hover:bg-white/5 transition-colors"
                        >
                          <Copy size={13} className="text-teal-500" /> Duplicar
                        </button>
                        <div className="h-[1px] bg-white/5 my-1" />
                        <button onClick={() => handleDelete(c.contrato)} className="w-full flex items-center gap-3 px-4 py-2.5 text-[11px] font-bold uppercase tracking-widest text-red-500/70 hover:text-red-500 hover:bg-red-500/5 transition-colors">
                          <Trash2 size={13} /> Excluir
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Title */}
                <div className="mb-6">
                  <h3 className="text-lg font-bold text-white uppercase tracking-tight leading-tight group-hover:text-copper transition-colors">
                    {c.projeto || 'Sem Nome'}
                  </h3>
                  <div className="flex items-center gap-2 mt-1 text-[10px] font-mono text-text-muted">
                    <span className="text-copper/60">ID:</span> {c.contrato}
                  </div>
                </div>

                {/* Info Blocks */}
                <div className="grid grid-cols-2 gap-4 mb-8">
                  <div className="space-y-1">
                    <span className="text-[9px] font-bold text-text-muted uppercase tracking-[0.15em] flex items-center gap-1.5">
                      <Target size={10} className="text-copper" /> Cliente
                    </span>
                    <p className="text-xs text-white/80 font-medium truncate">{c.cliente || '—'}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-[9px] font-bold text-text-muted uppercase tracking-[0.15em] flex items-center gap-1.5">
                      <MapPin size={10} className="text-copper" /> Localização
                    </span>
                    <p className="text-xs text-white/80 font-medium truncate">{c.localizacao || '—'}</p>
                  </div>
                </div>

                {/* Progress */}
                <div className="space-y-2 mb-8">
                  <div className="flex justify-between items-end">
                    <span className="text-[9px] font-bold text-text-muted uppercase tracking-[0.15em]">Progresso Realizado</span>
                    <span className="text-xs font-mono font-bold text-copper">{c.progress ?? 0}%</span>
                  </div>
                  <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                    <motion.div 
                      initial={{ width: 0 }}
                      animate={{ width: `${c.progress ?? 0}%` }}
                      transition={{ duration: 1, ease: 'easeOut' }}
                      className="h-full bg-gradient-to-r from-copper to-[#E0A63B] shadow-[0_0_8px_rgba(201,139,42,0.4)]"
                    />
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-2 mt-auto">
                  <div className="bg-white/[0.03] border border-white/[0.05] rounded-xl p-3">
                    <div className="text-[8px] font-bold text-text-muted uppercase mb-1">Saúde</div>
                    <div className="text-sm font-black" style={{ color: c.saude_color || TEAL }}>{c.saude || 'OK'}</div>
                  </div>
                  <div className="bg-white/[0.03] border border-white/[0.05] rounded-xl p-3">
                    <div className="text-[8px] font-bold text-text-muted uppercase mb-1">Prazo</div>
                    <div className="text-[10px] font-mono text-white/80">
                      {c.termino ? new Date(c.termino).toLocaleDateString('pt-BR') : '—'}
                    </div>
                  </div>
                  <div className="bg-white/[0.03] border border-white/[0.05] rounded-xl p-3">
                    <div className="text-[8px] font-bold text-text-muted uppercase mb-1">Desvio</div>
                    <div className="text-sm font-black" style={{ color: (c.desvio_pct || 0) > 0 ? TEAL : (c.desvio_pct || 0) < 0 ? RED : '#888' }}>
                      {(c.desvio_pct || 0) > 0 ? '+' : ''}{c.desvio_pct || 0}%
                    </div>
                  </div>
                </div>

                <Button 
                  onClick={() => navigate(`/hub?contrato=${c.contrato}`)}
                  className="w-full mt-6 bg-[#0e1a17] hover:bg-copper hover:text-void border border-copper/30 group-hover:border-copper transition-all font-bold text-[10px] uppercase tracking-widest h-10"
                >
                  Entrar no Hub
                  <ChevronRight size={14} className="ml-1" />
                </Button>
              </div>
            )
          })}
        </div>
      )}

      {!isLoading && contratos.length === 0 && (
        <div className="p-20 glass-panel rounded-3xl flex flex-col items-center text-center gap-4">
          <div className="p-8 rounded-full bg-white/5 border border-white/10">
            <Activity size={48} className="text-text-muted opacity-20" />
          </div>
          <p className="text-text-muted font-mono uppercase tracking-widest text-sm">Nenhum projeto encontrado no radar.</p>
          <Button onClick={handleOpenCreate} variant="outline" className="border-copper/40 text-copper hover:bg-copper/10">
            Criar Primeiro Projeto
          </Button>
        </div>
      )}

      {/* ── MODAL ────────────────────────────────────────────────────────── */}
      <ProjectModal 
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        editingProject={editingProject}
      />
    </div>
  )
}
