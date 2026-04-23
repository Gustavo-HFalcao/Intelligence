import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ClipboardList, ExternalLink, Play, Edit2, Trash2,
  ChevronLeft, ChevronRight, Filter, Mail, Plus, X,
  CheckCircle, FileText, Clock, AlertCircle, Building2,
} from 'lucide-react'
import api from '@/services/api'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

function statusColor(s: string) {
  if (s === 'Submetido' || s === 'Aprovado') return TEAL
  if (s === 'Rejeitado') return RED
  return COPPER
}

function statusIcon(s: string) {
  if (s === 'Submetido' || s === 'Aprovado') return <CheckCircle size={11} />
  if (s === 'Rejeitado') return <AlertCircle size={11} />
  if (s === 'Rascunho') return <Clock size={11} />
  return <FileText size={11} />
}

export default function RDOHistorico() {
  const navigate = useNavigate()
  const qc       = useQueryClient()

  const [statusFilter, setStatus] = useState('Todos')
  const [dateFrom, setDateFrom]   = useState('')
  const [dateTo, setDateTo]       = useState('')
  const [page, setPage]           = useState(1)
  const [emailPanel, setEmailPanel] = useState(false)
  const [emailContrato, setEmailContrato] = useState('')
  const [newEmail, setNewEmail]   = useState('')
  const PAGE_SIZE = 20

  // Load ALL rdos (no contract required)
  const { data, isLoading } = useQuery({
    queryKey: ['rdo-historico', page, statusFilter, dateFrom, dateTo],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) })
      if (statusFilter !== 'Todos') params.set('status', statusFilter)
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)
      return api.get(`/rdo/historico?${params}`).then(r => r.data)
    },
    staleTime: Infinity,
  })

  // Email subscribers — load when panel open for selected contract
  const { data: subData, refetch: refetchSubs } = useQuery({
    queryKey: ['rdo-subscribers', emailContrato],
    queryFn: () => api.get(`/rdo/subscribers?contrato=${encodeURIComponent(emailContrato)}`).then(r => r.data),
    enabled: !!emailContrato,
    staleTime: Infinity,
  })
  const subscribers: any[] = subData?.subscribers ?? []

  const addSubMut = useMutation({
    mutationFn: (email: string) => api.post('/rdo/subscribers', { contrato: emailContrato, email }),
    onSuccess: () => { refetchSubs(); setNewEmail('') },
  })
  const delSubMut = useMutation({
    mutationFn: (id: string) => api.delete(`/rdo/subscribers/${id}`),
    onSuccess: () => refetchSubs(),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/rdo/draft/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rdo-historico'] }),
  })

  const rdos: any[] = data?.rdos ?? []
  const hasNext     = data?.has_next ?? false
  const hasPrev     = page > 1

  // Get unique contracts from rdos for email filter
  const contratos = Array.from(new Set(rdos.map((r: any) => r.contrato).filter(Boolean)))

  return (
    <div className="flex flex-col gap-6 animate-enter">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
            <ClipboardList size={20} style={{ color: COPPER }} />
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold text-white uppercase tracking-tight">Histórico de RDOs</h1>
            <p className="text-[10px] text-white/30 font-bold uppercase tracking-widest">Relatórios Diários de Obra</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setEmailPanel(p => !p)}
            style={{ background: emailPanel ? `${TEAL}20` : GLASS, border: `1px solid ${emailPanel ? TEAL : 'rgba(255,255,255,0.08)'}`, color: emailPanel ? TEAL : '#e2c87a', borderRadius: 8, padding: '8px 14px', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}
          >
            <Mail size={13} /> Notificações
          </button>
          <button
            onClick={() => navigate('/rdo-form')}
            style={{ background: COPPER, color: '#0d1117', borderRadius: 10, padding: '9px 20px', fontSize: 13, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Plus size={14} /> Novo RDO
          </button>
        </div>
      </div>

      {/* Email notifications panel */}
      <AnimatePresence>
        {emailPanel && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{ background: `${TEAL}06`, border: `1px solid ${TEAL}30`, borderRadius: 12 }}
            className="overflow-hidden"
          >
            <div className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <Mail size={14} style={{ color: TEAL }} />
                <span className="text-xs font-black uppercase tracking-widest" style={{ color: TEAL }}>Destinatários de Notificação por RDO</span>
              </div>

              {/* Contract selector for email */}
              <div className="flex flex-wrap gap-2 mb-4">
                {contratos.length > 0 ? contratos.map(c => (
                  <button key={c} onClick={() => setEmailContrato(c)}
                    style={{ background: emailContrato === c ? `${TEAL}25` : 'rgba(255,255,255,0.04)', border: `1px solid ${emailContrato === c ? TEAL : 'rgba(255,255,255,0.08)'}`, color: emailContrato === c ? TEAL : '#e2c87a', borderRadius: 6, padding: '4px 12px', fontSize: 12, cursor: 'pointer', fontWeight: 600 }}>
                    <Building2 size={10} style={{ display: 'inline', marginRight: 4 }} />{c}
                  </button>
                )) : (
                  <span style={{ fontSize: 12, color: '#555' }}>Carregue RDOs para ver contratos</span>
                )}
              </div>

              {emailContrato && (
                <>
                  <div className="flex gap-2 mb-3">
                    <input
                      type="email"
                      placeholder="email@empresa.com"
                      value={newEmail}
                      onChange={e => setNewEmail(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && newEmail && addSubMut.mutate(newEmail)}
                      style={{ background: 'rgba(13,17,23,0.8)', border: `1px solid ${TEAL}40`, color: '#e2c87a', borderRadius: 8, padding: '8px 12px', fontSize: 13, flex: 1, outline: 'none' }}
                    />
                    <button
                      onClick={() => newEmail && addSubMut.mutate(newEmail)}
                      disabled={!newEmail || addSubMut.isPending}
                      style={{ background: TEAL, color: '#0d1117', borderRadius: 8, padding: '8px 16px', fontWeight: 700, fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                    >
                      <Plus size={14} /> Adicionar
                    </button>
                  </div>
                  {subscribers.length === 0 ? (
                    <p className="text-xs text-white/30 py-1">Nenhum destinatário cadastrado para {emailContrato}.</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {subscribers.map((s: any) => (
                        <div key={s.id} style={{ background: `${TEAL}15`, border: `1px solid ${TEAL}30`, borderRadius: 20, padding: '4px 12px', fontSize: 12, color: TEAL, display: 'flex', alignItems: 'center', gap: 6 }}>
                          {s.email}
                          <button onClick={() => delSubMut.mutate(s.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.3)', padding: 0, display: 'flex' }}>
                            <X size={11} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Filter size={13} style={{ color: COPPER }} />
        <select
          value={statusFilter}
          onChange={e => { setStatus(e.target.value); setPage(1) }}
          style={{ background: 'rgba(13,17,23,0.8)', border: BORDER, color: '#e2c87a', borderRadius: 8, padding: '6px 12px', fontSize: 12, outline: 'none' }}
        >
          {['Todos', 'Rascunho', 'Submetido', 'Aprovado', 'Rejeitado'].map(s => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <input
          type="date" value={dateFrom}
          onChange={e => { setDateFrom(e.target.value); setPage(1) }}
          style={{ background: 'rgba(13,17,23,0.8)', border: BORDER, color: '#e2c87a', borderRadius: 8, padding: '6px 10px', fontSize: 12, outline: 'none' }}
        />
        <span style={{ color: 'rgba(255,255,255,0.2)', fontSize: 12 }}>até</span>
        <input
          type="date" value={dateTo}
          onChange={e => { setDateTo(e.target.value); setPage(1) }}
          style={{ background: 'rgba(13,17,23,0.8)', border: BORDER, color: '#e2c87a', borderRadius: 8, padding: '6px 10px', fontSize: 12, outline: 'none' }}
        />
        {(dateFrom || dateTo || statusFilter !== 'Todos') && (
          <button onClick={() => { setDateFrom(''); setDateTo(''); setStatus('Todos'); setPage(1) }}
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: RED, borderRadius: 8, padding: '6px 12px', fontSize: 12, cursor: 'pointer' }}>
            Limpar filtros
          </button>
        )}
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="text-white/30 text-sm animate-pulse p-6 text-center">Carregando RDOs...</div>
      ) : (
        <div style={{ background: GLASS, border: BORDER, borderRadius: 12 }} className="overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(201,139,42,0.12)', background: 'rgba(255,255,255,0.02)' }}>
                {['Data', 'Contrato', 'Clima', 'Turno', 'Equipe', 'Status', 'Ações'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-[10px] font-black text-white/30 uppercase tracking-widest">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rdos.map((r: any, idx: number) => (
                <motion.tr
                  key={r.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: idx * 0.02 }}
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}
                  className="hover:bg-white/[0.02]"
                >
                  <td className="px-4 py-3 font-mono text-xs text-white/80">{r.data}</td>
                  <td className="px-4 py-3">
                    <span style={{ fontSize: 10, fontWeight: 700, color: COPPER, background: `${COPPER}12`, borderRadius: 4, padding: '2px 6px' }}>{r.contrato || '—'}</span>
                  </td>
                  <td className="px-4 py-3 text-xs text-white/50">{r.clima || '—'}</td>
                  <td className="px-4 py-3 text-xs text-white/50">{r.turno || '—'}</td>
                  <td className="px-4 py-3 text-xs text-white/50">{r.equipe_alocada || '—'}</td>
                  <td className="px-4 py-3">
                    <span style={{ fontSize: 11, fontWeight: 700, color: statusColor(r.status), background: `${statusColor(r.status)}18`, borderRadius: 6, padding: '3px 8px', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      {statusIcon(r.status)} {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      {r.view_token && (
                        <a href={`/rdo/${r.view_token}`} target="_blank" rel="noopener noreferrer" title="Visualizar RDO"
                          style={{ background: `${COPPER}15`, border: `1px solid ${COPPER}30`, color: COPPER, borderRadius: 6, padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 600, textDecoration: 'none' }}>
                          <ExternalLink size={11} /> Ver
                        </a>
                      )}
                      {r.status === 'Rascunho' && (
                        <>
                          <button
                            onClick={() => navigate(`/rdo-form?contrato=${encodeURIComponent(r.contrato)}&draft_id=${r.id}`)}
                            style={{ background: `${TEAL}15`, border: `1px solid ${TEAL}30`, color: TEAL, borderRadius: 6, padding: '4px 8px', fontSize: 11, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                            <Play size={11} /> Continuar
                          </button>
                          <button
                            onClick={() => confirm(`Excluir rascunho?`) && deleteMut.mutate(r.id)}
                            style={{ background: `${RED}10`, border: `1px solid ${RED}25`, color: RED, borderRadius: 6, padding: '4px 8px', fontSize: 11, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                            <Trash2 size={11} /> Excluir
                          </button>
                        </>
                      )}
                      {r.status === 'Submetido' && (
                        <button
                          onClick={() => navigate(`/rdo-form?contrato=${encodeURIComponent(r.contrato)}&draft_id=${r.id}&edit=1`)}
                          style={{ background: `${COPPER}12`, border: `1px solid ${COPPER}25`, color: COPPER, borderRadius: 6, padding: '4px 8px', fontSize: 11, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                          <Edit2 size={11} /> Editar
                        </button>
                      )}
                    </div>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>

          {rdos.length === 0 && (
            <div className="p-10 text-center text-white/20 text-sm">
              Nenhum RDO encontrado.
            </div>
          )}

          {(hasPrev || hasNext) && (
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }} className="flex items-center justify-between px-4 py-3">
              <button disabled={!hasPrev} onClick={() => setPage(p => p - 1)}
                style={{ background: hasPrev ? GLASS : 'transparent', border: hasPrev ? BORDER : 'none', color: hasPrev ? '#e2c87a' : 'rgba(255,255,255,0.1)', borderRadius: 8, padding: '6px 14px', fontSize: 12, cursor: hasPrev ? 'pointer' : 'default', display: 'flex', alignItems: 'center', gap: 4 }}>
                <ChevronLeft size={13} /> Anterior
              </button>
              <span className="text-[11px] text-white/30 font-mono">Página {page}</span>
              <button disabled={!hasNext} onClick={() => setPage(p => p + 1)}
                style={{ background: hasNext ? GLASS : 'transparent', border: hasNext ? BORDER : 'none', color: hasNext ? '#e2c87a' : 'rgba(255,255,255,0.1)', borderRadius: 8, padding: '6px 14px', fontSize: 12, cursor: hasNext ? 'pointer' : 'default', display: 'flex', alignItems: 'center', gap: 4 }}>
                Próxima <ChevronRight size={13} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
