/**
 * RDOForm — Formulário completo de RDO (Relatório Diário de Obra)
 */
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MapPin, Camera, PenLine, Send, Trash2, Plus, Save, CheckCircle,
  Clock, CloudRain, Users, AlertTriangle, ChevronDown, ChevronUp,
  ExternalLink, RefreshCw, Navigation, LogOut, Image as ImageIcon,
  Zap, FileText, ArrowLeft, Download, X, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import api from '@/services/api'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const GREEN  = '#22c55e'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

const CLIMA_OPTIONS  = ['Ensolarado','Nublado','Chuvoso','Parcialmente nublado','Tempestade','Ventoso']
const TURNO_OPTIONS  = ['Diurno','Noturno','Integral']
const STATUS_AT_OPT  = ['Concluída','Em andamento','Não iniciada','Impedida']

// ── Sort atividades by fase hierarchy (1 > 1.1 > 1.2 > 2 ...) ────────────────
function faseSortKey(fase: string): number[] {
  if (!fase) return [9999]
  return fase.split('.').map(p => parseInt(p, 10) || 0)
}

function compareFase(a: any, b: any): number {
  const ka = faseSortKey(a.fase || a.ordem?.toString() || '')
  const kb = faseSortKey(b.fase || b.ordem?.toString() || '')
  for (let i = 0; i < Math.max(ka.length, kb.length); i++) {
    const diff = (ka[i] ?? 0) - (kb[i] ?? 0)
    if (diff !== 0) return diff
  }
  return 0
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function Field({ label, children, col2 = false }: { label: string; children: React.ReactNode; col2?: boolean }) {
  return (
    <div className={col2 ? 'col-span-2' : ''}>
      <label className="block text-[10px] font-bold uppercase tracking-widest text-white/40 mb-1">{label}</label>
      {children}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  background: 'rgba(13,17,23,0.8)',
  border: '1px solid rgba(201,139,42,0.25)',
  color: '#e2c87a',
  borderRadius: 8,
  padding: '8px 12px',
  width: '100%',
  fontSize: 13,
  outline: 'none',
}

function Section({ title, icon: Icon, children, accent = COPPER }: {
  title: string; icon: React.ElementType; children: React.ReactNode; accent?: string
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      style={{ background: GLASS, border: BORDER, borderRadius: 14 }}
      className="p-5"
    >
      <h2 className="text-xs font-black uppercase tracking-[0.2em] mb-4 flex items-center gap-2" style={{ color: accent }}>
        <Icon size={14} /> {title}
      </h2>
      {children}
    </motion.div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function RDOForm() {
  const navigate      = useNavigate()
  const qc            = useQueryClient()
  const { user }      = useAuth()
  const sigCanvasRef  = useRef<HTMLCanvasElement>(null)
  const sigPadRef     = useRef<any>(null)

  const [searchParams] = useSearchParams()
  const urlContrato    = searchParams.get('contrato') || ''
  const urlDraftId     = searchParams.get('draft_id') || ''

  // Pre-fill contract from user's linked contract or URL param
  const userContrato = (user as any)?.contrato || ''
  const initialContrato = urlContrato || userContrato || ''

  const [draftId, setDraftId]           = useState(urlDraftId)
  const [isSaving, setIsSaving]         = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [savedAt, setSavedAt]           = useState('')
  const [checkinLoading, setCheckinLoading]   = useState(false)
  const [checkoutLoading, setCheckoutLoading] = useState(false)
  const [evidencias, setEvidencias]     = useState<any[]>([])
  const [uploadingPhoto, setUploadingPhoto] = useState(false)
  const [showAtividades, setShowAtividades] = useState(true)
  const [previstasHoje, setPrevistasHoje]   = useState<any[]>([])
  const [validationErrors, setValidationErrors] = useState<string[]>([])

  // Lightbox state for evidências
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null)

  const [form, setForm] = useState<Record<string, any>>({
    contrato: initialContrato,
    data: new Date().toISOString().slice(0, 10),
    clima: 'Ensolarado',
    turno: 'Diurno',
    tipo_tarefa: 'Diário de Obra',
    hora_inicio: '',
    hora_termino: '',
    houve_interrupcao: false,
    motivo_interrupcao: '',
    orientacao: '',
    observacoes: '',
    equipe_alocada: '',
    km_percorrido: '',
    localizacao: '',
    projeto: '',
    cliente: '',
    houve_chuva: false,
    quantidade_chuva: '',
    houve_acidente: false,
    descricao_acidente: '',
    checkin_lat: 0,
    checkin_lng: 0,
    checkin_endereco: '',
    checkin_timestamp: '',
    checkout_lat: 0,
    checkout_lng: 0,
    checkout_endereco: '',
    checkout_timestamp: '',
    signatory_name: '',
    signatory_doc: '',
  })

  const [atividadesRDO, setAtividadesRDO] = useState<any[]>([])

  const [newAt, setNewAt] = useState({
    atividade_id: '',
    descricao: '',
    pct: 0,
    status: 'Em andamento',
    qtd_executada: '',
    unidade: '',
    is_marco: false,
    marco_concluido: false,
  })

  // ── Queries ──────────────────────────────────────────────────────────────

  const { data: contratosData } = useQuery({
    queryKey: ['hub-contratos'],
    queryFn:  () => api.get('/hub/contratos').then(r => r.data),
    staleTime: 60_000,
  })
  const contratos: any[] = contratosData?.contratos ?? []

  const { data: cronogramaData } = useQuery({
    queryKey: ['cronograma-atividades', form.contrato],
    queryFn:  () => api.get(`/hub/cronograma?contrato=${encodeURIComponent(form.contrato)}`).then(r => r.data),
    enabled:  !!form.contrato,
    staleTime: 30_000,
  })
  const atividadesCronogramaRaw: any[] = cronogramaData?.atividades ?? []
  // Sort by fase hierarchy
  const atividadesCronograma = [...atividadesCronogramaRaw].sort(compareFase)

  // ── Draft load ───────────────────────────────────────────────────────────

  useEffect(() => {
    if (!form.contrato) return

    const loadUrl = urlDraftId
      ? `/rdo/draft?contrato=${encodeURIComponent(form.contrato)}&draft_id=${urlDraftId}`
      : `/rdo/draft?contrato=${encodeURIComponent(form.contrato)}`

    api.get(loadUrl)
      .then(r => {
        const { draft, atividades: ats, evidencias: evs } = r.data
        if (draft) {
          setDraftId(draft.id)
          setForm(f => ({ ...f, ...draft }))
          setAtividadesRDO(ats || [])
          setEvidencias(evs || [])
        } else if (!urlDraftId) {
          setDraftId('')
          setAtividadesRDO([])
          setEvidencias([])
        }
      })
      .catch(() => {})
  }, [form.contrato])

  // Pre-fill hora_inicio/hora_termino from GPS timestamps
  useEffect(() => {
    if (form.checkin_timestamp && !form.hora_inicio) {
      const d = new Date(form.checkin_timestamp)
      const hh = String(d.getHours()).padStart(2, '0')
      const mm = String(d.getMinutes()).padStart(2, '0')
      setForm(f => ({ ...f, hora_inicio: `${hh}:${mm}` }))
    }
  }, [form.checkin_timestamp])

  useEffect(() => {
    if (form.checkout_timestamp && !form.hora_termino) {
      const d = new Date(form.checkout_timestamp)
      const hh = String(d.getHours()).padStart(2, '0')
      const mm = String(d.getMinutes()).padStart(2, '0')
      setForm(f => ({ ...f, hora_termino: `${hh}:${mm}` }))
    }
  }, [form.checkout_timestamp])

  // Compute previstas para hoje
  useEffect(() => {
    if (!atividadesCronograma.length) { setPrevistasHoje([]); return }
    const today = new Date().toISOString().slice(0, 10)
    const previstas = atividadesCronograma.filter((a: any) => {
      const ini  = a.inicio_previsto?.slice(0, 10)
      const ter  = a.termino_previsto?.slice(0, 10)
      const pct  = Number(a.conclusao_pct || 0)
      if (pct >= 100) return false
      if (!ini || !ter) return false
      if (ini <= today && ter >= today) return true
      if (ter < today) return true
      return false
    })
    previstas.sort((a: any, b: any) => {
      const aLate = (a.termino_previsto?.slice(0, 10) ?? '') < today
      const bLate = (b.termino_previsto?.slice(0, 10) ?? '') < today
      if (aLate && !bLate) return -1
      if (!aLate && bLate) return 1
      return compareFase(a, b)
    })
    setPrevistasHoje(previstas)
  }, [atividadesCronogramaRaw])

  // ── Save draft ───────────────────────────────────────────────────────────

  const saveDraft = useCallback(async () => {
    if (!form.contrato) return
    setIsSaving(true)
    try {
      const body = { ...form, draft_id: draftId || undefined }
      const r = await api.post('/rdo/draft', body)
      const newId = r.data.draft_id
      if (newId && !draftId) setDraftId(newId)
      setSavedAt(new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }))
    } finally {
      setIsSaving(false)
    }
  }, [form, draftId])

  useEffect(() => {
    const t = setInterval(() => { if (form.contrato) saveDraft() }, 60_000)
    return () => clearInterval(t)
  }, [saveDraft, form.contrato])

  // ── GPS ──────────────────────────────────────────────────────────────────

  async function captureGPS(tipo: 'checkin' | 'checkout') {
    const setLoading = tipo === 'checkin' ? setCheckinLoading : setCheckoutLoading
    setLoading(true)
    navigator.geolocation.getCurrentPosition(
      async pos => {
        const { latitude: lat, longitude: lng } = pos.coords
        try {
          const r = await api.post('/rdo/geocode/reverse', { lat, lng })
          const ts = new Date().toISOString()
          setForm(f => ({
            ...f,
            [`${tipo}_lat`]: lat,
            [`${tipo}_lng`]: lng,
            [`${tipo}_endereco`]: r.data.address,
            [`${tipo}_timestamp`]: ts,
          }))
        } catch {}
        setLoading(false)
      },
      () => setLoading(false),
      { enableHighAccuracy: true, timeout: 15000 }
    )
  }

  // ── Atividades RDO ───────────────────────────────────────────────────────

  async function addAtividade() {
    if (!newAt.descricao.trim()) return
    const payload = {
      descricao:      newAt.descricao,
      pct:            newAt.is_marco ? (newAt.marco_concluido ? 100 : 0) : Number(newAt.pct),
      status:         newAt.status,
      ordem:          atividadesRDO.length,
      qtd_executada:  newAt.qtd_executada || null,
      unidade:        newAt.unidade || null,
      is_marco:       newAt.is_marco,
    }

    let currentDraftId = draftId
    if (!currentDraftId) {
      if (!form.contrato) return
      setIsSaving(true)
      try {
        const body = { ...form, draft_id: undefined }
        const r = await api.post('/rdo/draft', body)
        currentDraftId = r.data.draft_id || ''
        if (currentDraftId) setDraftId(currentDraftId)
      } finally {
        setIsSaving(false)
      }
    }

    if (!currentDraftId) return

    const r = await api.post(`/rdo/${currentDraftId}/atividades`, payload)
    setAtividadesRDO(a => [...a, r.data.row || { ...payload, id: Date.now().toString() }])
    setNewAt({ atividade_id: '', descricao: '', pct: 0, status: 'Em andamento', qtd_executada: '', unidade: '', is_marco: false, marco_concluido: false })
  }

  async function removeAtividade(id: string) {
    if (draftId) await api.delete(`/rdo/${draftId}/atividades/${id}`)
    setAtividadesRDO(a => a.filter(x => x.id !== id))
  }

  function preencherDoCronograma(at: any) {
    const isMarco = !!at.is_marco
    setNewAt({
      atividade_id: at.id,
      descricao: at.atividade,
      pct: Number(at.conclusao_pct || 0),
      status: 'Em andamento',
      qtd_executada: at.exec_qty || '',
      unidade: at.unidade || '',
      is_marco: isMarco,
      marco_concluido: false,
    })
  }

  // ── Upload foto ───────────────────────────────────────────────────────────

  async function handlePhotoUpload(file: File) {
    if (!draftId) { await saveDraft(); return }
    setUploadingPhoto(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('legenda', '')
      fd.append('checkin_lat', String(form.checkin_lat || 0))
      fd.append('checkin_lng', String(form.checkin_lng || 0))
      fd.append('contrato', form.contrato)
      const r = await fetch(`/api/rdo/${draftId}/evidencias`, {
        method: 'POST',
        credentials: 'include',
        body: fd,
      })
      const data = await r.json()
      if (data.row) setEvidencias(ev => [...ev, data.row])
    } finally {
      setUploadingPhoto(false)
    }
  }

  async function deleteEvidencia(id: string) {
    if (draftId) await api.delete(`/rdo/${draftId}/evidencias/${id}`)
    setEvidencias(ev => ev.filter(e => e.id !== id))
    if (lightboxIdx !== null && evidencias[lightboxIdx]?.id === id) setLightboxIdx(null)
  }

  async function updateLegenda(id: string, legenda: string) {
    if (draftId) await api.patch(`/rdo/${draftId}/evidencias/${id}`, { legenda })
    setEvidencias(ev => ev.map(e => e.id === id ? { ...e, legenda } : e))
  }

  // ── Signature pad ────────────────────────────────────────────────────────

  function initSigPad(canvas: HTMLCanvasElement | null) {
    if (!canvas || sigPadRef.current) return
    import('signature_pad').then(m => {
      sigPadRef.current = new m.default(canvas, {
        penColor: '#0d1117',
        backgroundColor: '#ffffff',
      })
    })
  }

  // ── Submit ───────────────────────────────────────────────────────────────

  async function handleSubmit() {
    // Validate required fields
    const errors: string[] = []
    if (!form.contrato) errors.push('Contrato é obrigatório')
    if (!form.data) errors.push('Data é obrigatória')
    if (!form.turno) errors.push('Turno é obrigatório')
    if (atividadesRDO.length === 0) errors.push('Adicione ao menos uma atividade executada')
    if (!form.signatory_name.trim()) errors.push('Nome do responsável pela assinatura é obrigatório')

    if (errors.length > 0) {
      setValidationErrors(errors)
      window.scrollTo({ top: 0, behavior: 'smooth' })
      return
    }
    setValidationErrors([])

    setIsSubmitting(true)
    try {
      if (!draftId) await saveDraft()
      if (!draftId) { setIsSubmitting(false); return }

      const sig = sigPadRef.current?.toDataURL('image/jpeg') ?? ''
      await api.post(`/rdo/${draftId}/submit`, {
        signatory_name: form.signatory_name,
        signatory_doc: form.signatory_doc,
        signatory_sig_b64: sig,
      })
      qc.invalidateQueries({ queryKey: ['rdo-historico'] })
      navigate('/rdo-historico')
    } finally {
      setIsSubmitting(false)
    }
  }

  // ── Helpers UI ───────────────────────────────────────────────────────────

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  const setCheck = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [k]: e.target.checked }))

  const contratoInfo = contratos.find(c => c.contrato === form.contrato)
  const gpsCheckinOk  = !!form.checkin_lat && !!form.checkin_timestamp
  const gpsCheckoutOk = !!form.checkout_lat && !!form.checkout_timestamp
  const hasLinkedContract = !!userContrato

  // ── Lightbox nav ─────────────────────────────────────────────────────────

  function openLightbox(idx: number) { setLightboxIdx(idx) }
  function closeLightbox() { setLightboxIdx(null) }
  function prevPhoto() { setLightboxIdx(i => i !== null && i > 0 ? i - 1 : i) }
  function nextPhoto() { setLightboxIdx(i => i !== null && i < evidencias.length - 1 ? i + 1 : i) }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (lightboxIdx === null) return
      if (e.key === 'Escape') closeLightbox()
      if (e.key === 'ArrowLeft') prevPhoto()
      if (e.key === 'ArrowRight') nextPhoto()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [lightboxIdx])

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-5 max-w-3xl mx-auto">

      {/* Lightbox */}
      <AnimatePresence>
        {lightboxIdx !== null && evidencias[lightboxIdx] && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[300] flex flex-col"
            style={{ background: 'rgba(0,0,0,0.95)' }}
            onClick={closeLightbox}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 shrink-0" onClick={e => e.stopPropagation()}>
              <div>
                <div className="text-sm font-semibold text-white">{evidencias[lightboxIdx].legenda || 'Sem legenda'}</div>
                <div className="text-[10px] text-white/40 font-mono">{lightboxIdx + 1} / {evidencias.length}</div>
              </div>
              <div className="flex items-center gap-3">
                <a
                  href={evidencias[lightboxIdx].foto_url}
                  download
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest px-3 py-1.5 rounded-lg"
                  style={{ background: `${COPPER}20`, border: `1px solid ${COPPER}40`, color: COPPER }}
                  onClick={e => e.stopPropagation()}
                >
                  <Download size={13} /> Download
                </a>
                <button onClick={closeLightbox} style={{ background: 'rgba(255,255,255,0.07)', border: 'none', borderRadius: 8, padding: 8, cursor: 'pointer', color: '#fff' }}>
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Image */}
            <div className="flex-1 flex items-center justify-center relative px-16" onClick={e => e.stopPropagation()}>
              {lightboxIdx > 0 && (
                <button onClick={prevPhoto} className="absolute left-4 top-1/2 -translate-y-1/2"
                  style={{ background: 'rgba(255,255,255,0.08)', border: 'none', borderRadius: 10, padding: '12px 10px', cursor: 'pointer', color: '#fff' }}>
                  <ChevronLeft size={22} />
                </button>
              )}
              <motion.img
                key={lightboxIdx}
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                src={evidencias[lightboxIdx].foto_url}
                alt={evidencias[lightboxIdx].legenda || 'Evidência'}
                className="max-w-full max-h-full object-contain rounded-xl"
                style={{ maxHeight: 'calc(100vh - 140px)' }}
              />
              {lightboxIdx < evidencias.length - 1 && (
                <button onClick={nextPhoto} className="absolute right-4 top-1/2 -translate-y-1/2"
                  style={{ background: 'rgba(255,255,255,0.08)', border: 'none', borderRadius: 10, padding: '12px 10px', cursor: 'pointer', color: '#fff' }}>
                  <ChevronRight size={22} />
                </button>
              )}
            </div>

            {/* Footer: address */}
            {evidencias[lightboxIdx].address && (
              <div className="text-center py-3 text-[10px] text-white/30 font-mono" onClick={e => e.stopPropagation()}>
                📍 {evidencias[lightboxIdx].address}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/rdo-historico')}
            style={{ background: GLASS, border: BORDER, color: '#e2c87a', borderRadius: 8, padding: '7px 12px', fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <ArrowLeft size={13} /> Voltar
          </button>
          <div>
            <h1 className="font-display text-2xl font-bold text-text-primary">Novo RDO</h1>
            {savedAt && <span className="text-[10px] text-text-muted">Rascunho salvo às {savedAt}</span>}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={saveDraft}
            disabled={isSaving || !form.contrato}
            style={{ background: GLASS, border: BORDER, color: '#e2c87a', borderRadius: 8, padding: '7px 16px', fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            {isSaving ? <RefreshCw size={13} className="animate-spin" /> : <Save size={13} />}
            {isSaving ? 'Salvando...' : 'Salvar Rascunho'}
          </button>
        </div>
      </div>

      {/* Validation errors */}
      {validationErrors.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ background: `${RED}10`, border: `1px solid ${RED}35`, borderRadius: 10 }}
          className="p-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={14} style={{ color: RED }} />
            <span className="text-xs font-black uppercase tracking-widest" style={{ color: RED }}>Campos obrigatórios não preenchidos</span>
          </div>
          <ul className="list-disc list-inside space-y-1">
            {validationErrors.map((e, i) => (
              <li key={i} className="text-xs" style={{ color: '#f87171' }}>{e}</li>
            ))}
          </ul>
        </motion.div>
      )}

      {/* CABEÇALHO */}
      <Section title="Cabeçalho do RDO" icon={FileText}>
        <div className="grid grid-cols-2 gap-3">
          {/* Contract: read-only if user has linked contract */}
          <Field label="Contrato *" col2={false}>
            {hasLinkedContract ? (
              <div style={{ ...inputStyle, display: 'flex', alignItems: 'center', gap: 8, opacity: 0.8 }}>
                <span style={{ color: COPPER, fontSize: 11, fontWeight: 700 }}>●</span>
                {form.contrato}
                <span style={{ fontSize: 10, color: 'rgba(226,200,122,0.4)', marginLeft: 'auto' }}>vinculado ao seu perfil</span>
              </div>
            ) : (
              <select value={form.contrato} onChange={set('contrato')} style={inputStyle}>
                <option value="">Selecionar contrato...</option>
                {contratos.map((c: any) => (
                  <option key={c.contrato} value={c.contrato}>
                    {c.contrato}{c.projeto ? ` — ${c.projeto}` : ''}
                  </option>
                ))}
              </select>
            )}
          </Field>

          <Field label="Data">
            <input type="date" value={form.data} onChange={set('data')} style={inputStyle} />
          </Field>

          {contratoInfo && (
            <>
              <Field label="Projeto">
                <input value={contratoInfo.projeto || ''} readOnly style={{ ...inputStyle, opacity: 0.6 }} />
              </Field>
              <Field label="Cliente">
                <input value={contratoInfo.cliente || ''} readOnly style={{ ...inputStyle, opacity: 0.6 }} />
              </Field>
            </>
          )}

          <Field label="Condição Climática">
            <select value={form.clima} onChange={set('clima')} style={inputStyle}>
              {CLIMA_OPTIONS.map(c => <option key={c}>{c}</option>)}
            </select>
          </Field>

          <Field label="Turno">
            <select value={form.turno} onChange={set('turno')} style={inputStyle}>
              {TURNO_OPTIONS.map(t => <option key={t}>{t}</option>)}
            </select>
          </Field>

          <Field label="Tipo de Registro">
            <input value={form.tipo_tarefa} onChange={set('tipo_tarefa')} style={inputStyle} />
          </Field>

          <Field label="KM Percorrido">
            <input type="number" value={form.km_percorrido} onChange={set('km_percorrido')} style={inputStyle} placeholder="0" />
          </Field>

          <Field label="Hora Início">
            <input type="time" value={form.hora_inicio} onChange={set('hora_inicio')} style={inputStyle} />
          </Field>

          <Field label="Hora Término">
            <input type="time" value={form.hora_termino} onChange={set('hora_termino')} style={inputStyle} />
          </Field>

          <Field label="Equipe Alocada (nº pessoas)" col2={false}>
            <input type="number" min={0} value={form.equipe_alocada} onChange={set('equipe_alocada')} style={inputStyle} placeholder="Nº de trabalhadores no campo" />
          </Field>

          <Field label="Localização / Frente de Obra">
            <input value={form.localizacao} onChange={set('localizacao')} style={inputStyle} placeholder="Ex: KM 12+500" />
          </Field>

          <Field label="Orientação Técnica" col2={true}>
            <textarea value={form.orientacao} onChange={set('orientacao')} rows={2}
              style={{ ...inputStyle, resize: 'vertical' }} placeholder="Diretrizes técnicas do dia..." />
          </Field>

          <Field label="Observações Gerais" col2={true}>
            <textarea value={form.observacoes} onChange={set('observacoes')} rows={2}
              style={{ ...inputStyle, resize: 'vertical' }} placeholder="Ocorrências, registros relevantes..." />
          </Field>

          <div className="col-span-2 grid grid-cols-2 gap-3 pt-1">
            <div className="flex items-center gap-3">
              <input type="checkbox" id="interrupcao" checked={!!form.houve_interrupcao} onChange={setCheck('houve_interrupcao')} style={{ width: 16, height: 16, accentColor: COPPER }} />
              <label htmlFor="interrupcao" className="text-sm text-text-muted cursor-pointer">Houve interrupção?</label>
            </div>
            <div className="flex items-center gap-3">
              <input type="checkbox" id="chuva" checked={!!form.houve_chuva} onChange={setCheck('houve_chuva')} style={{ width: 16, height: 16, accentColor: TEAL }} />
              <label htmlFor="chuva" className="text-sm text-text-muted cursor-pointer">Houve chuva?</label>
            </div>
            <div className="flex items-center gap-3">
              <input type="checkbox" id="acidente" checked={!!form.houve_acidente} onChange={setCheck('houve_acidente')} style={{ width: 16, height: 16, accentColor: RED }} />
              <label htmlFor="acidente" className="text-sm text-text-muted cursor-pointer">Houve acidente?</label>
            </div>
          </div>

          {form.houve_interrupcao && (
            <Field label="Motivo da Interrupção" col2={true}>
              <input value={form.motivo_interrupcao} onChange={set('motivo_interrupcao')} style={inputStyle}
                placeholder="Ex: Chuva intensa, falta de material, problema elétrico..." />
            </Field>
          )}

          {form.houve_chuva && (
            <Field label="Quantidade de Chuva" col2={false}>
              <input value={form.quantidade_chuva} onChange={set('quantidade_chuva')} style={inputStyle} placeholder="Ex: 15mm" />
            </Field>
          )}

          {form.houve_acidente && (
            <Field label="Descrição do Acidente" col2={true}>
              <textarea value={form.descricao_acidente} onChange={set('descricao_acidente')} rows={2}
                style={{ ...inputStyle, resize: 'vertical' }} placeholder="Descreva o ocorrido, vítimas, procedimentos adotados..." />
            </Field>
          )}
        </div>
      </Section>

      {/* GPS CHECK-IN */}
      <Section title="GPS — Check-in / Check-out" icon={MapPin} accent={TEAL}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="flex flex-col gap-3">
            <button
              onClick={() => captureGPS('checkin')}
              disabled={checkinLoading}
              style={{
                background: gpsCheckinOk ? `${GREEN}15` : GLASS,
                border: `1px solid ${gpsCheckinOk ? GREEN : 'rgba(201,139,42,0.3)'}`,
                color: gpsCheckinOk ? GREEN : '#e2c87a',
                borderRadius: 10, padding: '12px 16px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600,
              }}
            >
              {checkinLoading ? <RefreshCw size={14} className="animate-spin" /> : gpsCheckinOk ? <CheckCircle size={14} /> : <Navigation size={14} />}
              {checkinLoading ? 'Obtendo localização...' : gpsCheckinOk ? 'Check-in Registrado' : 'Registrar Check-in'}
            </button>
            {gpsCheckinOk && (
              <div style={{ background: `${GREEN}08`, border: `1px solid ${GREEN}20`, borderRadius: 8 }} className="p-3 text-xs">
                <div className="text-green-400 font-bold mb-1">📍 {form.checkin_endereco || 'Endereço obtido'}</div>
                <div className="text-white/40 font-mono">{form.checkin_lat?.toFixed(6)}, {form.checkin_lng?.toFixed(6)}</div>
                <div className="text-white/30 mt-1">{form.checkin_timestamp ? new Date(form.checkin_timestamp).toLocaleString('pt-BR') : ''}</div>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3">
            <button
              onClick={() => captureGPS('checkout')}
              disabled={checkoutLoading || !gpsCheckinOk}
              style={{
                background: gpsCheckoutOk ? `${TEAL}15` : GLASS,
                border: `1px solid ${gpsCheckoutOk ? TEAL : 'rgba(201,139,42,0.2)'}`,
                color: gpsCheckoutOk ? TEAL : 'rgba(226,200,122,0.5)',
                borderRadius: 10, padding: '12px 16px',
                cursor: gpsCheckinOk ? 'pointer' : 'not-allowed',
                display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600,
              }}
            >
              {checkoutLoading ? <RefreshCw size={14} className="animate-spin" /> : gpsCheckoutOk ? <CheckCircle size={14} /> : <LogOut size={14} />}
              {checkoutLoading ? 'Obtendo localização...' : gpsCheckoutOk ? 'Check-out Registrado' : 'Registrar Check-out'}
            </button>
            {gpsCheckoutOk && (
              <div style={{ background: `${TEAL}08`, border: `1px solid ${TEAL}20`, borderRadius: 8 }} className="p-3 text-xs">
                <div style={{ color: TEAL }} className="font-bold mb-1">📍 {form.checkout_endereco || 'Endereço obtido'}</div>
                <div className="text-white/40 font-mono">{form.checkout_lat?.toFixed(6)}, {form.checkout_lng?.toFixed(6)}</div>
                <div className="text-white/30 mt-1">{form.checkout_timestamp ? new Date(form.checkout_timestamp).toLocaleString('pt-BR') : ''}</div>
              </div>
            )}
          </div>
        </div>
      </Section>

      {/* ATIVIDADES DO DIA */}
      <Section title="Atividades Executadas" icon={CheckCircle}>
        {/* Schedule picker */}
        {atividadesCronograma.length > 0 && (
          <div className="mb-4">
            <button
              onClick={() => setShowAtividades(s => !s)}
              style={{ background: `${COPPER}10`, border: `1px solid ${COPPER}25`, borderRadius: 8, padding: '6px 14px', fontSize: 12, color: COPPER, cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
            >
              {showAtividades ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              Selecionar do Cronograma ({atividadesCronograma.filter(a => Number(a.conclusao_pct || 0) < 100).length} pendentes)
            </button>

            <AnimatePresence>
              {showAtividades && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="mt-3 max-h-56 overflow-y-auto custom-scrollbar"
                  style={{ border: '1px solid rgba(201,139,42,0.1)', borderRadius: 8 }}
                >
                  {atividadesCronograma
                    .filter(a => Number(a.conclusao_pct || 0) < 100)
                    .map((a: any) => {
                      const today = new Date().toISOString().slice(0, 10)
                      const isLate = (a.termino_previsto?.slice(0, 10) ?? '') < today && (a.termino_previsto?.slice(0, 10) ?? '') !== ''
                      const isToday = !isLate && a.inicio_previsto?.slice(0, 10) <= today && a.termino_previsto?.slice(0, 10) >= today
                      return (
                        <button
                          key={a.id}
                          onClick={() => preencherDoCronograma(a)}
                          className="w-full text-left hover:bg-white/5 transition-colors"
                          style={{ padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.03)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', background: 'none', border: 'none', color: 'inherit' }}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            {isLate && <span style={{ color: RED, fontSize: 10, fontWeight: 700, flexShrink: 0 }}>ATRASADA</span>}
                            {isToday && <span style={{ color: TEAL, fontSize: 10, fontWeight: 700, flexShrink: 0 }}>HOJE</span>}
                            <div className="min-w-0">
                              <div className="text-xs font-semibold text-text-primary truncate">{a.atividade}</div>
                              <div className="text-[10px] text-text-muted">{a.fase} · {a.responsavel || '—'} · {a.unidade || ''}</div>
                            </div>
                          </div>
                          <div className="text-right shrink-0 ml-3">
                            <div style={{ color: COPPER, fontSize: 12, fontWeight: 700 }}>{a.conclusao_pct || 0}%</div>
                            <div className="text-[9px] text-white/30">{a.total_qty ? `${a.exec_qty || 0}/${a.total_qty} ${a.unidade || ''}` : ''}</div>
                          </div>
                        </button>
                      )
                    })}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Previstas para hoje — placed just above the input form */}
        {previstasHoje.length > 0 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{ background: `${COPPER}10`, border: `1px solid ${COPPER}40`, borderRadius: 10 }}
            className="p-3 mb-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <Zap size={13} style={{ color: COPPER }} />
              <span className="text-[11px] font-black uppercase tracking-widest" style={{ color: COPPER }}>
                Previstas para Hoje — {previstasHoje.length} atividade{previstasHoje.length !== 1 ? 's' : ''}
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {previstasHoje.slice(0, 8).map((a: any) => {
                const today = new Date().toISOString().slice(0, 10)
                const isLate = (a.termino_previsto?.slice(0, 10) ?? '') < today
                return (
                  <button
                    key={a.id}
                    onClick={() => preencherDoCronograma(a)}
                    style={{ background: isLate ? `${RED}10` : `${COPPER}15`, border: `1px solid ${isLate ? RED : COPPER}30`, color: '#e2c87a', borderRadius: 5, padding: '3px 9px', fontSize: 11, cursor: 'pointer', fontWeight: 600 }}
                  >
                    {isLate && '⚠ '}{a.fase ? `[${a.fase}] ` : ''}{a.atividade?.slice(0, 30)}
                  </button>
                )
              })}
              {previstasHoje.length > 8 && (
                <span style={{ fontSize: 11, color: 'rgba(226,200,122,0.4)', padding: '3px 9px' }}>+{previstasHoje.length - 8} mais</span>
              )}
            </div>
          </motion.div>
        )}

        {/* Form adicionar atividade */}
        <div style={{ background: 'rgba(13,17,23,0.5)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10 }} className="p-3 mb-3">
          <div className="grid grid-cols-2 gap-2 mb-2">
            <div className="col-span-2">
              <input
                placeholder="Descrição da atividade executada..."
                value={newAt.descricao}
                onChange={e => setNewAt(a => ({ ...a, descricao: e.target.value }))}
                style={{ ...inputStyle, fontSize: 13 }}
              />
            </div>

            {/* Marco: checkbox instead of % input */}
            {newAt.is_marco ? (
              <div className="col-span-2 flex items-center gap-3 py-2">
                <input
                  type="checkbox"
                  id="marco-concluido"
                  checked={newAt.marco_concluido}
                  onChange={e => setNewAt(a => ({ ...a, marco_concluido: e.target.checked }))}
                  style={{ width: 16, height: 16, accentColor: COPPER }}
                />
                <label htmlFor="marco-concluido" className="text-sm cursor-pointer" style={{ color: COPPER }}>
                  Marco concluído neste RDO
                </label>
                <span style={{ marginLeft: 'auto', fontSize: 10, color: 'rgba(226,200,122,0.4)', border: `1px solid ${COPPER}30`, borderRadius: 4, padding: '2px 6px' }}>
                  MARCO
                </span>
              </div>
            ) : (
              <>
                <select
                  value={newAt.status}
                  onChange={e => setNewAt(a => ({ ...a, status: e.target.value }))}
                  style={inputStyle}
                >
                  {STATUS_AT_OPT.map(s => <option key={s}>{s}</option>)}
                </select>
                <input
                  type="number"
                  min={0}
                  max={100}
                  placeholder="% Concluída hoje"
                  value={newAt.pct}
                  onChange={e => setNewAt(a => ({ ...a, pct: Number(e.target.value) }))}
                  style={inputStyle}
                />
              </>
            )}

            <input
              placeholder="Qtd. executada"
              value={newAt.qtd_executada}
              onChange={e => setNewAt(a => ({ ...a, qtd_executada: e.target.value }))}
              style={inputStyle}
            />
            <input
              placeholder="Unidade (m², und, km...)"
              value={newAt.unidade}
              onChange={e => setNewAt(a => ({ ...a, unidade: e.target.value }))}
              style={inputStyle}
            />
          </div>

          {newAt.atividade_id && (
            <div className="text-[10px] mb-2 flex items-center gap-2" style={{ color: COPPER }}>
              ✓ Vinculada ao cronograma: ID {newAt.atividade_id.slice(0, 8)}...
              {newAt.is_marco && <span style={{ background: `${COPPER}20`, border: `1px solid ${COPPER}40`, borderRadius: 3, padding: '1px 5px', fontSize: 9, fontWeight: 700 }}>MARCO</span>}
            </div>
          )}

          <button
            onClick={addAtividade}
            disabled={!newAt.descricao.trim()}
            style={{ background: newAt.descricao ? COPPER : 'rgba(201,139,42,0.2)', color: newAt.descricao ? '#0d1117' : '#888', border: 'none', borderRadius: 8, padding: '7px 16px', fontSize: 13, fontWeight: 700, cursor: newAt.descricao ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Plus size={13} /> Adicionar Atividade
          </button>
        </div>

        {/* Lista de atividades adicionadas */}
        {atividadesRDO.length === 0 && (
          <div className="text-center py-4 text-text-muted text-xs">
            Nenhuma atividade adicionada ainda
          </div>
        )}
        {atividadesRDO.map((a, i) => (
          <div
            key={a.id || i}
            className="flex items-center gap-3 mb-2 rounded-lg p-3"
            style={{ background: 'rgba(13,17,23,0.4)', border: '1px solid rgba(255,255,255,0.04)' }}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <div className="text-sm text-text-primary font-semibold truncate">{a.descricao}</div>
                {a.is_marco && <span style={{ fontSize: 9, color: COPPER, border: `1px solid ${COPPER}30`, borderRadius: 3, padding: '1px 4px', fontWeight: 700, flexShrink: 0 }}>MARCO</span>}
              </div>
              <div className="text-[10px] text-text-muted">{a.status}{a.qtd_executada ? ` · ${a.qtd_executada} ${a.unidade || ''}` : ''}</div>
            </div>
            <div className="shrink-0 text-center">
              {a.is_marco ? (
                <span style={{ fontSize: 11, color: a.pct >= 100 ? GREEN : COPPER }}>{a.pct >= 100 ? '✓ Concluído' : 'Pendente'}</span>
              ) : (
                <div style={{ color: a.status === 'Concluída' ? GREEN : COPPER, fontWeight: 700, fontSize: 14 }}>{a.pct}%</div>
              )}
            </div>
            <button
              onClick={() => removeAtividade(a.id)}
              style={{ color: RED, background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </Section>

      {/* EVIDÊNCIAS FOTOGRÁFICAS */}
      <Section title="Evidências Fotográficas" icon={Camera} accent={TEAL}>
        <div className="mb-4">
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: COPPER, color: '#0d1117', borderRadius: 8, padding: '8px 16px', fontSize: 13, cursor: 'pointer', fontWeight: 700 }}>
            {uploadingPhoto ? <RefreshCw size={14} className="animate-spin" /> : <Camera size={14} />}
            {uploadingPhoto ? 'Processando watermark...' : 'Adicionar Foto'}
            <input
              type="file"
              accept="image/*"
              capture="environment"
              multiple
              style={{ display: 'none' }}
              onChange={async e => {
                const files = Array.from(e.target.files || [])
                for (const file of files) await handlePhotoUpload(file)
                e.target.value = ''
              }}
            />
          </label>
          <span className="text-[10px] text-text-muted ml-3">Watermark GPS + hora aplicada automaticamente</span>
        </div>

        {evidencias.length === 0 && (
          <div className="flex flex-col items-center py-8 text-text-muted text-xs border border-dashed border-white/10 rounded-xl">
            <ImageIcon size={28} className="mb-2 opacity-20" />
            Nenhuma foto adicionada ainda
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {evidencias.map((ev: any, idx: number) => (
            <div key={ev.id} style={{ background: 'rgba(13,17,23,0.6)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10 }} className="overflow-hidden relative">
              <div className="relative cursor-pointer" onClick={() => openLightbox(idx)}>
                <img
                  src={ev.foto_url}
                  alt={ev.legenda || 'Evidência'}
                  className="w-full object-cover hover:opacity-90 transition-opacity"
                  style={{ height: 140 }}
                />
                <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity" style={{ background: 'rgba(0,0,0,0.35)' }}>
                  <ExternalLink size={20} className="text-white" />
                </div>
              </div>
              <div className="p-2">
                <input
                  value={ev.legenda || ''}
                  onChange={e => updateLegenda(ev.id, e.target.value)}
                  placeholder="Legenda da foto..."
                  style={{ ...inputStyle, fontSize: 11, padding: '4px 8px' }}
                />
                {ev.address && (
                  <div className="text-[9px] text-text-muted mt-1 truncate">📍 {ev.address}</div>
                )}
              </div>
              <button
                onClick={() => deleteEvidencia(ev.id)}
                className="absolute top-2 right-2"
                style={{ background: `${RED}cc`, border: 'none', borderRadius: 6, padding: '4px 6px', cursor: 'pointer', color: '#fff' }}
              >
                <Trash2 size={11} />
              </button>
            </div>
          ))}
        </div>
      </Section>

      {/* ASSINATURA */}
      <Section title="Assinatura Digital" icon={PenLine}>
        <div className="grid grid-cols-2 gap-3 mb-4">
          <Field label="Nome do Responsável *">
            <input value={form.signatory_name} onChange={set('signatory_name')} style={inputStyle} placeholder="Nome completo..." />
          </Field>
          <Field label="CPF / Documento">
            <input value={form.signatory_doc} onChange={set('signatory_doc')} style={inputStyle} placeholder="000.000.000-00" />
          </Field>
        </div>

        <div style={{ background: '#fff', borderRadius: 10, display: 'inline-block', border: '2px solid rgba(201,139,42,0.3)' }}>
          <canvas
            ref={el => { (sigCanvasRef as any).current = el; initSigPad(el) }}
            width={420}
            height={140}
            style={{ display: 'block', borderRadius: 8 }}
          />
        </div>
        <div className="mt-2">
          <button
            onClick={() => sigPadRef.current?.clear()}
            style={{ color: '#888', background: 'none', border: 'none', fontSize: 12, cursor: 'pointer' }}
          >
            Limpar assinatura
          </button>
        </div>
      </Section>

      {/* SUBMIT */}
      <div className="flex gap-3">
        <button
          onClick={() => navigate('/rdo-historico')}
          style={{ background: GLASS, border: BORDER, color: '#e2c87a', borderRadius: 12, padding: '14px 20px', fontSize: 14, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}
        >
          <ArrowLeft size={15} /> Voltar
        </button>
        <motion.button
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          onClick={handleSubmit}
          disabled={!form.contrato || isSubmitting}
          style={{
            flex: 1,
            background: form.contrato && !isSubmitting ? COPPER : 'rgba(201,139,42,0.2)',
            color: form.contrato && !isSubmitting ? '#0d1117' : '#888',
            border: 'none',
            borderRadius: 12,
            padding: '14px',
            fontSize: 15,
            fontWeight: 800,
            cursor: form.contrato ? 'pointer' : 'not-allowed',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
          }}
        >
          {isSubmitting
            ? <><RefreshCw size={16} className="animate-spin" /> Submetendo RDO...</>
            : <><Send size={16} /> Submeter RDO</>}
        </motion.button>
      </div>

      {!gpsCheckinOk && form.contrato && (
        <div style={{ background: `${RED}10`, border: `1px solid ${RED}30`, borderRadius: 8, color: '#f87171' }} className="p-3 text-xs text-center">
          <AlertTriangle size={12} className="inline mr-1 text-red-400" />
          <span className="text-red-400">Recomendado: registre o GPS Check-in antes de submeter</span>
        </div>
      )}
    </div>
  )
}
