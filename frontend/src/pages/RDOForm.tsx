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
  Zap, FileText, ArrowLeft, Download, X, ChevronLeft, ChevronRight, Edit2,
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

const FOTO_CATS = [
  { key: 'epi',         label: 'EPI / Equipe',              color: '#2A9D8F' },
  { key: 'evidencia',   label: 'Evidência de Obra',          color: '#C98B2A' },
  { key: 'ferramentas', label: 'Ferramentas / Organização',  color: '#3B82F6' },
] as const
type FotoCat = typeof FOTO_CATS[number]['key']

function statusFromPct(pct: number): string {
  if (pct === 0) return 'Não iniciada'
  if (pct >= 100) return 'Concluída'
  return 'Em andamento'
}

function statusColor(status: string): string {
  if (status === 'Concluída') return GREEN
  if (status === 'Em andamento') return COPPER
  // 'Não iniciada', 'Pendente', etc → mesmo tom neutro
  return 'rgba(255,255,255,0.25)'
}

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
  const [showAtividades, setShowAtividades] = useState(false)
  const [showNaoMapeada, setShowNaoMapeada] = useState(false)
  const [previstasHoje, setPrevistasHoje]   = useState<any[]>([])
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [draftWarning, setDraftWarning]     = useState(false)

  // Lightbox state for evidências
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null)

  const [form, setForm] = useState<Record<string, any>>({
    contrato: initialContrato,
    data: (() => {
      // Usa data local (não UTC) para evitar desvio de fuso
      const now = new Date()
      return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`
    })(),
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
  const [selectedCronAt, setSelectedCronAt] = useState<any>(null)
  const [uploadingCat, setUploadingCat] = useState<FotoCat | null>(null)
  const [editingAtId, setEditingAtId] = useState<string | null>(null)

  const [newAt, setNewAt] = useState({
    atividade_id: '',
    descricao: '',
    pct: 0,
    qtd_executada: '',
    unidade: '',
    efetivo: '',
    is_marco: false,
    marco_concluido: false,
  })

  // ── Queries ──────────────────────────────────────────────────────────────

  const { data: contratosData } = useQuery({
    queryKey: ['hub-contratos'],
    queryFn:  () => api.get('/hub/contratos').then(r => r.data),
    staleTime: Infinity,
  })
  const contratos: any[] = contratosData?.contratos ?? []

  const { data: cronogramaData } = useQuery({
    queryKey: ['cronograma-atividades', form.contrato],
    queryFn:  () => api.get(`/hub/cronograma?contrato=${encodeURIComponent(form.contrato)}`).then(r => r.data),
    enabled:  !!form.contrato,
    staleTime: Infinity,
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
          // Só mostra o warning se não veio de um link direto (urlDraftId vazio)
          if (!urlDraftId) setDraftWarning(true)
        } else if (!urlDraftId) {
          // Sem rascunho: busca último RDO submetido e calcula próximo dia útil
          api.get(`/rdo/historico?contrato=${encodeURIComponent(form.contrato)}&page_size=1`)
            .then(hr => {
              const lastRdos: any[] = hr.data?.rdos ?? []
              if (lastRdos.length > 0) {
                const lastDate = lastRdos[0].data?.slice(0, 10)
                if (lastDate) {
                  const next = new Date(lastDate + 'T12:00:00')
                  // Avança para o próximo dia útil (segunda a sexta)
                  do { next.setDate(next.getDate() + 1) } while ([0, 6].includes(next.getDay()))
                  const nextStr = `${next.getFullYear()}-${String(next.getMonth()+1).padStart(2,'0')}-${String(next.getDate()).padStart(2,'0')}`
                  setForm(f => ({ ...f, data: nextStr }))
                }
              }
            })
            .catch(() => {})
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

  // Compute previstas para hoje — apenas micros/subs (macros são fruto das filhas)
  useEffect(() => {
    if (!atividadesCronograma.length) { setPrevistasHoje([]); return }
    const today = new Date().toISOString().slice(0, 10)
    const previstas = atividadesCronograma.filter((a: any) => {
      if (a.nivel === 'macro') return false  // macros não são preenchidas pelo user
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
    if (!form.contrato) {
      // Show visible error instead of silent return
      setValidationErrors(['Selecione um contrato antes de salvar o rascunho.'])
      window.scrollTo({ top: 0, behavior: 'smooth' })
      return
    }
    setIsSaving(true)
    try {
      const body = { ...form, draft_id: draftId || undefined }
      const r = await api.post('/rdo/draft', body)
      const newId = r.data.draft_id
      if (newId && !draftId) setDraftId(newId)
      setSavedAt(new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }))
      setValidationErrors([])
    } catch (e: any) {
      setValidationErrors([`Erro ao salvar rascunho: ${e?.response?.data?.detail || e.message}`])
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

    // Geolocation requires HTTPS in modern browsers.
    // On HTTP (e.g. dev VM without TLS), we fall back to IP-based location.
    const isSecure = location.protocol === 'https:' || location.hostname === 'localhost'

    if (!isSecure || !navigator.geolocation) {
      // IP geolocation fallback via public API
      try {
        const r = await fetch('https://ipapi.co/json/')
        const d = await r.json()
        if (d.latitude && d.longitude) {
          const lat = parseFloat(d.latitude)
          const lng = parseFloat(d.longitude)
          const addr = [d.city, d.region, d.country_name].filter(Boolean).join(', ')
          const ts = new Date().toISOString()
          setForm(f => ({
            ...f,
            [`${tipo}_lat`]: lat,
            [`${tipo}_lng`]: lng,
            [`${tipo}_endereco`]: `[IP] ${addr}`,
            [`${tipo}_timestamp`]: ts,
          }))
        } else {
          alert('Não foi possível obter localização. Acesse via HTTPS para GPS preciso.')
        }
      } catch {
        alert('GPS indisponível em HTTP. Use HTTPS para localização precisa.')
      }
      setLoading(false)
      return
    }

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
        } catch {
          // geocode failed but we still have coordinates
          const ts = new Date().toISOString()
          setForm(f => ({
            ...f,
            [`${tipo}_lat`]: lat,
            [`${tipo}_lng`]: lng,
            [`${tipo}_endereco`]: `${lat.toFixed(6)}, ${lng.toFixed(6)}`,
            [`${tipo}_timestamp`]: ts,
          }))
        }
        setLoading(false)
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          alert('Permissão de GPS negada. Permita o acesso à localização no navegador.')
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          alert('Localização indisponível. Verifique se o GPS está ativo.')
        } else {
          alert('Timeout ao obter GPS. Tente novamente.')
        }
        setLoading(false)
      },
      { enableHighAccuracy: true, timeout: 15000 }
    )
  }

  // ── Atividades RDO ───────────────────────────────────────────────────────

  async function addAtividade() {
    if (!newAt.descricao.trim()) return

    // Para atividades vinculadas ao cronograma: qtd_executada é a produção DO DIA
    // O backend fará append ao exec_qty acumulado e recalculará o % automaticamente
    const pct = newAt.is_marco ? (newAt.marco_concluido ? 100 : 0) : 0  // pct nunca editável pelo user
    const payload = {
      descricao:       newAt.descricao,
      pct,
      status:          statusFromPct(pct),
      ordem:           atividadesRDO.length,
      qtd_executada:   newAt.qtd_executada || null,
      unidade:         newAt.unidade || null,
      efetivo:         Number(newAt.efetivo) || 0,
      is_marco:        newAt.is_marco,
      marco_concluido: newAt.is_marco ? newAt.marco_concluido : false,
      atividade_id:    newAt.atividade_id || null,
      is_extra:        !newAt.atividade_id,
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

    // Validação de efetivo — soma de todos ≤ equipe_alocada
    const equipeTotal = Number(form.equipe_alocada || 0)
    if (equipeTotal > 0 && newAt.efetivo) {
      const efetivoExistente = atividadesRDO.reduce((sum, a) => sum + Number(a.efetivo || 0), 0)
      const novoEfetivo = Number(newAt.efetivo || 0)
      if (efetivoExistente + novoEfetivo > equipeTotal) {
        const msg = `⚠️ Efetivo insuficiente: você alocou ${efetivoExistente + novoEfetivo} pessoas, mas só há ${equipeTotal} na equipe do dia. Reduza as pessoas desta atividade ou ajuste o campo "Equipe Alocada" acima.`
        setValidationErrors([msg])
        // Scroll para o banner de erro para que o user veja
        setTimeout(() => document.getElementById('validation-banner')?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100)
        return
      }
    }

    const r = await api.post(`/rdo/${currentDraftId}/atividades`, payload)
    const novaAt = r.data.row || { ...payload, id: Date.now().toString() }
    setAtividadesRDO(a => [...a, novaAt])

    // Remove da lista de previstas após adicionar
    if (newAt.atividade_id) {
      setPrevistasHoje(p => p.filter(a => a.id !== newAt.atividade_id))
    }

    setSelectedCronAt(null)
    setValidationErrors([])
    setNewAt({ atividade_id: '', descricao: '', pct: 0, qtd_executada: '', unidade: '', efetivo: '', is_marco: false, marco_concluido: false })
  }

  async function removeAtividade(id: string) {
    if (draftId) await api.delete(`/rdo/${draftId}/atividades/${id}`)
    setAtividadesRDO(a => a.filter(x => x.id !== id))
  }

  async function updateAtividade(id: string, patch: Record<string, any>) {
    if (draftId) {
      await api.patch(`/rdo/${draftId}/atividades/${id}`, patch)
    }
    setAtividadesRDO(a => a.map(x => x.id === id ? { ...x, ...patch } : x))
    setEditingAtId(null)
  }

  function preencherDoCronograma(at: any) {
    const isMarco = !!at.is_marco || at.unidade === 'marco' || at.tipo_medicao === 'marco'
    setSelectedCronAt(at)
    setNewAt({
      atividade_id: at.id,
      descricao: at.atividade,
      pct: 0,               // não editável pelo user — calculado pelo backend
      qtd_executada: '',    // user preenche apenas o que fez HOJE
      unidade: at.unidade || 'un',
      efetivo: '',
      is_marco: isMarco,
      marco_concluido: false,
    })
  }

  // ── Upload foto ───────────────────────────────────────────────────────────

  async function handlePhotoUpload(file: File, categoria: FotoCat) {
    if (!draftId) { await saveDraft(); return }
    setUploadingCat(categoria)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('legenda', '')
      fd.append('tipo', categoria)
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
      setUploadingCat(null)
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
      // Invalida TODOS os caches relevantes — o hub de projetos atualiza em tempo real
      // para qualquer usuário que já está na página
      qc.invalidateQueries({ queryKey: ['rdo-historico'] })
      qc.invalidateQueries({ queryKey: ['rdo-drafts'] })
      qc.invalidateQueries({ queryKey: ['hub-contratos'] })
      qc.invalidateQueries({ queryKey: ['cronograma-atividades'] })
      qc.invalidateQueries({ queryKey: ['hub-kpis'] })
      qc.invalidateQueries({ queryKey: ['dashboard-kpis'] })
      qc.invalidateQueries({ queryKey: ['rdo-insights'] })
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

  // Sincroniza projeto/cliente/localizacao do contrato selecionado no form
  // para que sejam salvos no draft e apareçam no RDO View
  useEffect(() => {
    if (!contratoInfo) return
    setForm(f => ({
      ...f,
      projeto:     contratoInfo.projeto    || f.projeto    || '',
      cliente:     contratoInfo.cliente    || f.cliente    || '',
      localizacao: contratoInfo.localizacao || f.localizacao || '',
    }))
  }, [contratoInfo?.contrato])


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
          id="validation-banner"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ background: `${RED}10`, border: `1px solid ${RED}35`, borderRadius: 10 }}
          className="p-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={14} style={{ color: RED }} />
            <span className="text-xs font-black uppercase tracking-widest" style={{ color: RED }}>Atenção</span>
          </div>
          <ul className="list-disc list-inside space-y-1">
            {validationErrors.map((e, i) => (
              <li key={i} className="text-xs" style={{ color: '#f87171' }}>{e}</li>
            ))}
          </ul>
        </motion.div>
      )}


      {/* Banner: rascunho existente encontrado */}
      <AnimatePresence>
        {draftWarning && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            style={{ background: `${COPPER}10`, border: `1px solid ${COPPER}35`, borderRadius: 10 }}
            className="p-4 flex items-start gap-3"
          >
            <AlertTriangle size={16} style={{ color: COPPER, flexShrink: 0, marginTop: 1 }} />
            <div className="flex-1">
              <div className="text-xs font-black uppercase tracking-widest mb-1" style={{ color: COPPER }}>
                Rascunho encontrado
              </div>
              <div className="text-xs text-white/60">
                Encontramos um rascunho em aberto para este contrato. Você está continuando de onde parou.
                Para começar um novo RDO, descarte o rascunho.
              </div>
            </div>
            <button
              onClick={() => setDraftWarning(false)}
              style={{ color: 'rgba(255,255,255,0.3)', background: 'none', border: 'none', cursor: 'pointer', flexShrink: 0 }}
            >
              <X size={14} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

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

        {/* Previstas para hoje — micros/subs agrupadas por macro pai */}
        {previstasHoje.length > 0 && (() => {
          const today = new Date().toISOString().slice(0, 10)
          // Agrupar por macro pai
          const grupos: Record<string, { macroLabel: string; items: any[] }> = {}
          for (const a of previstasHoje) {
            const macroId = a.parent_id || '__sem_macro__'
            if (!grupos[macroId]) {
              const macro = atividadesCronograma.find((m: any) => m.id === macroId)
              grupos[macroId] = {
                macroLabel: macro ? `${macro.fase ? `[${macro.fase}] ` : ''}${macro.atividade}` : 'Sem macro',
                items: [],
              }
            }
            grupos[macroId].items.push(a)
          }
          return (
            <motion.div
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{ background: `${COPPER}08`, border: `1px solid ${COPPER}35`, borderRadius: 10 }}
              className="p-3 mb-4"
            >
              <div className="flex items-center gap-2 mb-3">
                <Zap size={13} style={{ color: COPPER }} />
                <span className="text-[11px] font-black uppercase tracking-widest" style={{ color: COPPER }}>
                  Previstas para Hoje — {previstasHoje.length} atividade{previstasHoje.length !== 1 ? 's' : ''}
                </span>
              </div>
              <div className="flex flex-col gap-3">
                {Object.entries(grupos).map(([macroId, grupo]) => (
                  <div key={macroId}>
                    {/* Header da macro — não clicável, apenas informativo */}
                    <div className="flex items-center gap-2 mb-1.5">
                      <div style={{ width: 3, height: 12, background: COPPER, borderRadius: 2, opacity: 0.5 }} />
                      <span className="text-[9px] font-black uppercase tracking-widest" style={{ color: 'rgba(201,139,42,0.6)' }}>
                        {grupo.macroLabel}
                      </span>
                    </div>
                    {/* Micros/subs clicáveis */}
                    <div className="flex flex-wrap gap-1.5 pl-3">
                      {grupo.items.map((a: any) => {
                        const isLate = (a.termino_previsto?.slice(0, 10) ?? '') < today
                        return (
                          <button
                            key={a.id}
                            onClick={() => preencherDoCronograma(a)}
                            style={{
                              background: isLate ? `${RED}12` : `${COPPER}18`,
                              border: `1px solid ${isLate ? RED : COPPER}35`,
                              color: isLate ? '#f87171' : '#e2c87a',
                              borderRadius: 6, padding: '4px 10px',
                              fontSize: 11, cursor: 'pointer', fontWeight: 600,
                              display: 'flex', alignItems: 'center', gap: 4,
                            }}
                          >
                            {isLate && <span style={{ fontSize: 9 }}>⚠</span>}
                            {a.fase ? <span style={{ fontSize: 9, opacity: 0.6 }}>[{a.fase}]</span> : null}
                            {a.atividade?.slice(0, 35)}
                            {a.total_qty > 0 && (
                              <span style={{ fontSize: 9, opacity: 0.5, marginLeft: 2 }}>
                                · {a.exec_qty || 0}/{a.total_qty} {a.unidade || ''}
                              </span>
                            )}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )
        })()}

        {/* Painel informativo da atividade selecionada do cronograma */}
        {selectedCronAt && (() => {
          const totalQty   = Number(selectedCronAt.total_qty || 0)
          const execQty    = Number(selectedCronAt.exec_qty  || 0)
          const today      = new Date().toISOString().slice(0, 10)
          const inicio     = selectedCronAt.inicio_previsto?.slice(0, 10)
          const termino    = selectedCronAt.termino_previsto?.slice(0, 10)
          const isLate     = termino && termino < today
          const pctAcum    = Number(selectedCronAt.conclusao_pct || 0)

          // Calculate day position and expected daily rate
          let diaInfo = ''
          let esperadoHoje = 0
          if (inicio && termino && totalQty > 0) {
            const msDay    = 86_400_000
            const totalDays = Math.max(1, Math.round((new Date(termino).getTime() - new Date(inicio).getTime()) / msDay) + 1)
            const daysDone  = Math.max(0, Math.round((new Date(today).getTime() - new Date(inicio).getTime()) / msDay) + 1)
            esperadoHoje    = Math.round(totalQty / totalDays)
            diaInfo         = `Dia ${Math.min(daysDone, totalDays)} de ${totalDays}`
          }

          // Card unificado: info + input em um só lugar
          return (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              style={{ background: isLate ? `${RED}08` : `${TEAL}08`, border: `1px solid ${isLate ? RED : TEAL}30`, borderRadius: 10 }}
              className="p-3 mb-3 text-xs"
            >
              {/* Header: nome + badge + fechar */}
              <div className="flex items-start justify-between mb-2 gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-black text-sm" style={{ color: isLate ? RED : TEAL }}>{selectedCronAt.atividade}</span>
                  {newAt.is_marco && <span style={{ fontSize: 9, color: COPPER, border: `1px solid ${COPPER}40`, borderRadius: 3, padding: '1px 5px', fontWeight: 700 }}>MARCO</span>}
                  {isLate && <span style={{ fontSize: 9, color: RED, fontWeight: 700 }}>⚠ ATRASADA</span>}
                  {diaInfo && <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)' }}>{diaInfo}</span>}
                </div>
                <button onClick={() => { setSelectedCronAt(null); setNewAt(a => ({ ...a, atividade_id: '', descricao: '', qtd_executada: '', unidade: '', is_marco: false, marco_concluido: false })) }}
                  style={{ color: 'rgba(255,255,255,0.3)', background: 'none', border: 'none', cursor: 'pointer', flexShrink: 0 }}>✕</button>
              </div>

              {/* Stats row */}
              <div className="flex flex-wrap gap-x-5 gap-y-1 mb-3 text-[10px]">
                {totalQty > 0 ? <>
                  <span><span className="text-white/40">Acumulado </span><span style={{ color: COPPER }} className="font-bold">{execQty}/{totalQty} {selectedCronAt.unidade || ''} ({pctAcum}%)</span></span>
                  <span><span className="text-white/40">Esperado hoje </span><span className="text-white/80 font-bold">{esperadoHoje} {selectedCronAt.unidade || ''}</span></span>
                </> : <>
                  <span><span className="text-white/40">Conclusão </span><span style={{ color: COPPER }} className="font-bold">{pctAcum}%</span></span>
                </>}
                {termino && (
                  <span>
                    <span className="text-white/40">Prazo </span>
                    <span className={isLate ? 'text-red-400 font-bold' : 'text-white/70'}>
                      {new Date(termino + 'T12:00:00').toLocaleDateString('pt-BR')}
                      {isLate && ` (−${Math.round((new Date(today).getTime() - new Date(termino).getTime()) / 86_400_000)}d)`}
                    </span>
                  </span>
                )}
              </div>
            </motion.div>
          )
        })()}

        {/* Form adicionar atividade */}
        <div style={{ background: 'rgba(13,17,23,0.5)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10 }} className="p-3 mb-3">
          {newAt.atividade_id ? (
            /* ── Atividade vinculada ao cronograma: inputs apenas ── */
            <div className="flex flex-col gap-3">

              {newAt.is_marco ? (
                /* Marco: só toggle de conclusão */
                <div className="flex items-center gap-3 py-1">
                  <input
                    type="checkbox"
                    id="marco-concluido"
                    checked={newAt.marco_concluido}
                    onChange={e => setNewAt(a => ({ ...a, marco_concluido: e.target.checked }))}
                    style={{ width: 18, height: 18, accentColor: COPPER }}
                  />
                  <label htmlFor="marco-concluido" className="text-sm cursor-pointer font-semibold" style={{ color: COPPER }}>
                    Concluído neste RDO
                  </label>
                </div>
              ) : (
                /* Quantidade: user informa apenas o que fez HOJE */
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[9px] font-bold uppercase tracking-widest mb-1" style={{ color: 'rgba(255,255,255,0.3)' }}>
                      Quantidade feita hoje
                    </label>
                    <input
                      type="number" min={0}
                      placeholder="Ex: 80"
                      value={newAt.qtd_executada}
                      onChange={e => setNewAt(a => ({ ...a, qtd_executada: e.target.value }))}
                      style={{ ...inputStyle, fontSize: 14, fontWeight: 700 }}
                      autoFocus
                    />
                  </div>
                  <div>
                    <label className="block text-[9px] font-bold uppercase tracking-widest mb-1" style={{ color: 'rgba(255,255,255,0.3)' }}>
                      Unidade
                    </label>
                    {/* Unidade travada — pré-cadastrada na atividade */}
                    <div style={{ ...inputStyle, opacity: 0.7, cursor: 'not-allowed', display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                      <span style={{ color: COPPER, fontSize: 10 }}>🔒</span>
                      {newAt.unidade || 'un'}
                    </div>
                  </div>
                </div>
              )}

              {/* Barra de progresso — calculada, não editável */}
              {!newAt.is_marco && selectedCronAt && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[9px] font-bold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.3)' }}>Progresso acumulado (calculado)</span>
                    <span className="text-[10px] font-bold font-mono" style={{ color: COPPER }}>
                      {(() => {
                        const acum = Number(selectedCronAt.exec_qty || 0) + Number(newAt.qtd_executada || 0)
                        const total = Number(selectedCronAt.total_qty || 0)
                        return total > 0 ? `${acum}/${total} ${newAt.unidade || ''} · ${Math.min(100, Math.round(acum / total * 100))}%` : `${selectedCronAt.conclusao_pct || 0}%`
                      })()}
                    </span>
                  </div>
                  <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 99 }}>
                    <div style={{
                      width: `${(() => {
                        const acum = Number(selectedCronAt.exec_qty || 0) + Number(newAt.qtd_executada || 0)
                        const total = Number(selectedCronAt.total_qty || 0)
                        return total > 0 ? Math.min(100, Math.round(acum / total * 100)) : Number(selectedCronAt.conclusao_pct || 0)
                      })()}%`,
                      height: '100%', background: COPPER, borderRadius: 99, transition: 'width 0.3s'
                    }} />
                  </div>
                  <div className="text-[9px] mt-1" style={{ color: 'rgba(255,255,255,0.2)' }}>
                    Acumulado anterior: {selectedCronAt.exec_qty || 0} {newAt.unidade || ''} · A barra é atualizada automaticamente após envio
                  </div>
                </div>
              )}

              {/* Pessoas alocadas */}
              <div>
                <label className="block text-[9px] font-bold uppercase tracking-widest mb-1" style={{ color: 'rgba(255,255,255,0.3)' }}>
                  Pessoas alocadas nesta atividade
                </label>
                <input
                  type="number" min={0}
                  placeholder="Nº de pessoas"
                  value={newAt.efetivo}
                  onChange={e => setNewAt(a => ({ ...a, efetivo: e.target.value }))}
                  style={inputStyle}
                />
              </div>
            </div>
          ) : (
            /* ── Atividade não mapeada (colapsável por padrão) ── */
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={() => setShowNaoMapeada(s => !s)}
                style={{ background: 'rgba(239,68,68,0.06)', border: `1px solid rgba(239,68,68,0.2)`, borderRadius: 8, padding: '7px 12px', cursor: 'pointer', color: 'rgba(255,255,255,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12 }}
              >
                <span className="flex items-center gap-2">
                  <AlertTriangle size={12} style={{ color: RED }} />
                  Atividade não mapeada no cronograma
                </span>
                {showNaoMapeada ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              <AnimatePresence>
                {showNaoMapeada && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="flex flex-col gap-2 overflow-hidden"
                  >
                    <div style={{ background: `rgba(239,68,68,0.06)`, border: `1px solid rgba(239,68,68,0.2)`, borderRadius: 6, padding: '6px 10px' }} className="flex items-center gap-2">
                      <AlertTriangle size={11} style={{ color: RED }} />
                      <span className="text-[10px]" style={{ color: 'rgba(255,255,255,0.4)' }}>
                        Aparecerá para aprovação e preenchimento do gestor no Hub.
                      </span>
                    </div>
                    <input
                      placeholder="Descreva a atividade executada..."
                      value={newAt.descricao}
                      onChange={e => setNewAt(a => ({ ...a, descricao: e.target.value }))}
                      style={{ ...inputStyle, fontSize: 13 }}
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="number" min={0}
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
                    <input
                      type="number" min={0}
                      placeholder="Pessoas alocadas"
                      value={newAt.efetivo}
                      onChange={e => setNewAt(a => ({ ...a, efetivo: e.target.value }))}
                      style={inputStyle}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}

          <button
            onClick={addAtividade}
            disabled={!newAt.descricao.trim()}
            style={{ background: newAt.descricao ? COPPER : 'rgba(201,139,42,0.2)', color: newAt.descricao ? '#0d1117' : '#888', border: 'none', borderRadius: 8, padding: '7px 16px', fontSize: 13, fontWeight: 700, cursor: newAt.descricao ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', gap: 6, marginTop: 10 }}
          >
            <Plus size={13} /> {newAt.atividade_id ? 'Registrar no RDO' : 'Adicionar Atividade Não Mapeada'}
          </button>
        </div>

        {/* Lista de atividades adicionadas */}
        {atividadesRDO.length === 0 && (
          <div className="text-center py-4 text-text-muted text-xs">Nenhuma atividade adicionada ainda</div>
        )}
        {atividadesRDO.map((a, i) => {
          const status = a.status || statusFromPct(a.pct || 0)
          const isEditing = editingAtId === a.id
          return (
            <div
              key={a.id || i}
              className="mb-2 rounded-lg"
              style={{ background: 'rgba(13,17,23,0.4)', border: `1px solid ${isEditing ? `${COPPER}40` : 'rgba(255,255,255,0.04)'}` }}
            >
              {/* Summary row */}
              <div className="flex items-center gap-3 p-3">
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: statusColor(status), flexShrink: 0 }} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="text-sm text-text-primary font-semibold truncate">{a.descricao}</div>
                    {a.is_marco && <span style={{ fontSize: 9, color: COPPER, border: `1px solid ${COPPER}30`, borderRadius: 3, padding: '1px 4px', fontWeight: 700, flexShrink: 0 }}>MARCO</span>}
                    {a.is_extra && <span style={{ fontSize: 9, color: RED, border: `1px solid ${RED}30`, borderRadius: 3, padding: '1px 4px', fontWeight: 700, flexShrink: 0 }}>NÃO MAPEADA</span>}
                  </div>
                  <div className="text-[10px] text-text-muted flex items-center gap-2">
                    <span style={{ color: statusColor(status) }}>{status}</span>
                    {a.quantidade > 0 && a.unidade !== '%' ? <span>· {a.quantidade} {a.unidade || ''}</span> : null}
                    {a.efetivo ? <span>· <Users size={9} className="inline" /> {a.efetivo} pessoas</span> : null}
                  </div>
                </div>
                <div className="shrink-0 text-center">
                  {a.is_marco ? (
                    <span style={{ fontSize: 11, color: a.marco_concluido ? GREEN : COPPER }}>{a.marco_concluido ? '✓ Concluído' : 'Pendente'}</span>
                  ) : (
                    <div style={{ color: statusColor(status), fontWeight: 700, fontSize: 14 }}>{a.pct}%</div>
                  )}
                </div>
                <button
                  onClick={() => setEditingAtId(isEditing ? null : a.id)}
                  style={{ color: isEditing ? COPPER : 'rgba(255,255,255,0.3)', background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
                  title="Editar"
                >
                  <Edit2 size={13} />
                </button>
                <button
                  onClick={() => removeAtividade(a.id)}
                  style={{ color: RED, background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
                >
                  <Trash2 size={13} />
                </button>
              </div>

              {/* Inline edit panel */}
              <AnimatePresence>
                {isEditing && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    style={{ borderTop: `1px solid ${COPPER}20`, overflow: 'hidden' }}
                  >
                    <div className="p-3 flex gap-2 flex-wrap">
                      {!a.is_marco && (
                        <div className="flex gap-2 flex-1">
                          <input
                            type="number" min={0}
                            placeholder="Qtd hoje"
                            defaultValue={a.quantidade || ''}
                            onBlur={e => {
                              const val = e.target.value
                              if (val !== String(a.quantidade || ''))
                                updateAtividade(a.id, { qtd_executada: val, quantidade: parseFloat(val) || 0 })
                            }}
                            style={{ ...inputStyle, fontSize: 12, flex: 1 }}
                          />
                          <div style={{ ...inputStyle, flex: 1, opacity: 0.6, fontSize: 12, display: 'flex', alignItems: 'center' }}>
                            {a.unidade || 'un'}
                          </div>
                        </div>
                      )}
                      {a.is_marco && (
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={!!a.marco_concluido}
                            onChange={e => updateAtividade(a.id, { marco_concluido: e.target.checked, pct: e.target.checked ? 100 : 0, is_marco: true })}
                            style={{ width: 16, height: 16, accentColor: COPPER }}
                          />
                          <span className="text-xs" style={{ color: COPPER }}>Marco concluído</span>
                        </label>
                      )}
                      <input
                        type="number" min={0}
                        placeholder="Pessoas"
                        defaultValue={a.efetivo || ''}
                        onBlur={e => {
                          const val = Number(e.target.value)
                          if (val !== a.efetivo)
                            updateAtividade(a.id, { efetivo: val })
                        }}
                        style={{ ...inputStyle, fontSize: 12, width: 90 }}
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </Section>

      {/* EVIDÊNCIAS FOTOGRÁFICAS */}
      <Section title="Evidências Fotográficas" icon={Camera} accent={TEAL}>

        {/* 3-category upload buttons */}
        <div className="flex flex-wrap gap-2 mb-5">
          {FOTO_CATS.map(cat => {
            const uploading = uploadingCat === cat.key
            const count = evidencias.filter(e => e.tipo === cat.key).length
            return (
              <label
                key={cat.key}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 7,
                  background: uploading ? cat.color : `${cat.color}15`,
                  border: `1px solid ${cat.color}50`,
                  color: uploading ? '#0d1117' : cat.color,
                  borderRadius: 8, padding: '8px 14px', fontSize: 12,
                  cursor: 'pointer', fontWeight: 700, transition: 'all .15s',
                }}
              >
                {uploading ? <RefreshCw size={13} className="animate-spin" /> : <Camera size={13} />}
                {uploading ? 'Processando...' : cat.label}
                {count > 0 && !uploading && (
                  <span style={{ background: cat.color, color: '#0d1117', borderRadius: 99, fontSize: 10, fontWeight: 900, minWidth: 18, textAlign: 'center', padding: '0 5px' }}>
                    {count}
                  </span>
                )}
                <input
                  type="file" accept="image/*" capture="environment" multiple
                  style={{ display: 'none' }}
                  onChange={async e => {
                    const files = Array.from(e.target.files || [])
                    for (const file of files) await handlePhotoUpload(file, cat.key)
                    e.target.value = ''
                  }}
                />
              </label>
            )
          })}
          <span className="text-[10px] text-text-muted self-center ml-1">Watermark GPS + hora aplicado automaticamente</span>
        </div>

        {evidencias.length === 0 && (
          <div className="flex flex-col items-center py-8 text-text-muted text-xs border border-dashed border-white/10 rounded-xl">
            <ImageIcon size={28} className="mb-2 opacity-20" />
            Nenhuma foto adicionada ainda
          </div>
        )}

        {/* Photos grouped by category */}
        {FOTO_CATS.map(cat => {
          const catEvs = evidencias.filter(e => e.tipo === cat.key)
          if (catEvs.length === 0) return null
          return (
            <div key={cat.key} className="mb-5">
              <div className="flex items-center gap-2 mb-2">
                <div style={{ width: 3, height: 16, background: cat.color, borderRadius: 2 }} />
                <span className="text-[10px] font-black uppercase tracking-widest" style={{ color: cat.color }}>{cat.label}</span>
                <span className="text-[9px] text-white/20">({catEvs.length})</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {catEvs.map((ev: any) => {
                  const globalIdx = evidencias.findIndex(e => e.id === ev.id)
                  return (
                    <div key={ev.id} style={{ background: 'rgba(13,17,23,0.6)', border: `1px solid ${cat.color}20`, borderRadius: 10 }} className="overflow-hidden relative">
                      <div className="relative cursor-pointer" onClick={() => openLightbox(globalIdx)}>
                        <img
                          src={ev.foto_url}
                          alt={ev.legenda || cat.label}
                          className="w-full object-cover hover:opacity-90 transition-opacity"
                          style={{ height: 130 }}
                        />
                        {/* category badge on photo */}
                        <span style={{ position: 'absolute', top: 6, left: 6, background: `${cat.color}dd`, color: '#0d1117', fontSize: 9, fontWeight: 900, borderRadius: 4, padding: '2px 6px', letterSpacing: '0.08em' }}>
                          {cat.label.split(' ')[0].toUpperCase()}
                        </span>
                        <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity" style={{ background: 'rgba(0,0,0,0.3)' }}>
                          <ExternalLink size={18} className="text-white" />
                        </div>
                      </div>
                      <div className="p-2">
                        <input
                          value={ev.legenda || ''}
                          onChange={e => updateLegenda(ev.id, e.target.value)}
                          placeholder="Legenda..."
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
                  )
                })}
              </div>
            </div>
          )
        })}

        {/* Uncategorized fallback */}
        {evidencias.filter(e => !FOTO_CATS.some(c => c.key === e.tipo)).length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {evidencias.filter(e => !FOTO_CATS.some(c => c.key === e.tipo)).map((ev: any) => {
              const globalIdx = evidencias.findIndex(e => e.id === ev.id)
              return (
                <div key={ev.id} style={{ background: 'rgba(13,17,23,0.6)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10 }} className="overflow-hidden relative">
                  <div className="relative cursor-pointer" onClick={() => openLightbox(globalIdx)}>
                    <img src={ev.foto_url} alt={ev.legenda || 'Evidência'} className="w-full object-cover" style={{ height: 130 }} />
                  </div>
                  <div className="p-2">
                    <input value={ev.legenda || ''} onChange={e => updateLegenda(ev.id, e.target.value)} placeholder="Legenda..." style={{ ...inputStyle, fontSize: 11, padding: '4px 8px' }} />
                  </div>
                  <button onClick={() => deleteEvidencia(ev.id)} className="absolute top-2 right-2"
                    style={{ background: `${RED}cc`, border: 'none', borderRadius: 6, padding: '4px 6px', cursor: 'pointer', color: '#fff' }}>
                    <Trash2 size={11} />
                  </button>
                </div>
              )
            })}
          </div>
        )}
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
