import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { SlidersHorizontal, Building2, ToggleRight, Zap, CreditCard, ClipboardList, Layers, Server } from 'lucide-react'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

const MODULE_STYLES: Record<string, { color: string; bg: string; border: string; label: string; icon: any }> = {
  reembolso: { color: COPPER,     bg: `${COPPER}10`,       border: `${COPPER}25`,       label: 'Reembolso', icon: CreditCard },
  rdo:       { color: TEAL,       bg: `${TEAL}10`,         border: `${TEAL}25`,         label: 'RDO',       icon: ClipboardList },
  ambos:     { color: '#8B6FBF',  bg: 'rgba(139,111,191,0.10)', border: 'rgba(139,111,191,0.25)', label: 'Ambos', icon: Layers },
  infra:     { color: '#E05252',  bg: 'rgba(224,82,82,0.10)',   border: 'rgba(224,82,82,0.25)',   label: 'Infra', icon: Server },
}

// Feature flag definitions (mirrored from Reflex FeatureFlagsState)
const FEATURE_DEFS = [
  // Infra
  { key: 'gps_enabled',        label: 'GPS / Geolocalização',       desc: 'Habilita captura de coordenadas GPS no app', module: 'infra' },
  { key: 'pdf_export_enabled', label: 'Exportação PDF',             desc: 'Geração assíncrona de PDFs via Celery',      module: 'infra' },
  { key: 'whisper_enabled',    label: 'Áudio / Whisper',            desc: 'Transcrição de voz via OpenAI Whisper',      module: 'infra' },
  { key: 'vision_enabled',     label: 'Visão Computacional',        desc: 'Análise de imagens via GPT-4 Vision',        module: 'infra' },
  // Reembolso
  { key: 'reembolso_enabled',  label: 'Módulo Reembolso',           desc: 'Formulário e dashboard de reembolso',        module: 'reembolso' },
  { key: 'reembolso_photos',   label: 'Fotos em Reembolso',         desc: 'Upload de comprovantes fotográficos',        module: 'reembolso' },
  { key: 'reembolso_approval', label: 'Fluxo de Aprovação',         desc: 'Aprovação em dois níveis para reembolsos',   module: 'reembolso' },
  // RDO
  { key: 'rdo_enabled',        label: 'Módulo RDO',                 desc: 'Relatório Diário de Obra completo',          module: 'rdo' },
  { key: 'rdo_gps_checkin',    label: 'Check-in GPS',               desc: 'Registro de localização no início do turno', module: 'rdo' },
  { key: 'rdo_signature',      label: 'Assinatura Digital',         desc: 'Captura de assinatura canvas no RDO',        module: 'rdo' },
  { key: 'rdo_ai_summary',     label: 'Resumo IA',                  desc: 'Geração automática de resumo IA no submit',  module: 'rdo' },
  { key: 'rdo_pdf',            label: 'PDF do RDO',                 desc: 'Exportação do RDO como PDF',                 module: 'rdo' },
  // Ambos
  { key: 'email_alerts',       label: 'Alertas por Email',          desc: 'Notificações automáticas por email',         module: 'ambos' },
  { key: 'ai_insights_hub',    label: 'Insights IA no Hub',         desc: 'Agente de IA gera insights do cronograma',   module: 'ambos' },
]

async function api(path: string, opts?: RequestInit) {
  const r = await fetch(path, { credentials: 'include', ...opts })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

function ModuleSection({ module: mod, features, flags, onToggle }: { module: string; features: typeof FEATURE_DEFS; flags: Record<string, boolean>; onToggle: (key: string, val: boolean) => void }) {
  const style = MODULE_STYLES[mod]
  const IconC = style.icon
  return (
    <div className="flex flex-col gap-2">
      {/* Section header */}
      <div className="flex items-center gap-3 py-1">
        <div className="p-1.5 rounded-lg" style={{ background: style.bg, border: `1px solid ${style.border}` }}>
          <IconC size={12} style={{ color: style.color }} />
        </div>
        <span style={{ fontSize: 11, fontWeight: 700, color: style.color, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{style.label}</span>
        <div className="flex-1 h-px" style={{ background: `linear-gradient(90deg, ${style.border}, transparent)` }} />
      </div>

      {features.map(f => {
        const isOn = flags[f.key] !== false // default true
        return (
          <div key={f.key}
            style={{
              background: isOn ? `${COPPER}05` : GLASS,
              border: `1px solid ${isOn ? `${COPPER}20` : 'rgba(255,255,255,0.05)'}`,
              borderRadius: 10, padding: '12px 16px',
              display: 'flex', alignItems: 'center', gap: 14,
              transition: 'all 0.15s ease',
            }}>
            {/* Toggle */}
            <button
              onClick={() => onToggle(f.key, !isOn)}
              style={{
                width: 36, height: 20, borderRadius: 10, border: 'none', cursor: 'pointer', flexShrink: 0,
                background: isOn ? TEAL : 'rgba(255,255,255,0.12)',
                position: 'relative', transition: 'background 0.2s ease',
              }}
            >
              <span style={{
                position: 'absolute', top: 2, left: isOn ? 18 : 2, width: 16, height: 16,
                borderRadius: '50%', background: '#fff', transition: 'left 0.2s ease',
              }} />
            </button>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div style={{ fontSize: 13, fontWeight: 600, color: isOn ? '#fff' : '#888' }}>{f.label}</div>
              <div style={{ fontSize: 10, color: '#555', marginTop: 2, fontFamily: 'monospace' }}>{f.key}</div>
            </div>

            {/* Module tag */}
            <span style={{ fontSize: 9, fontWeight: 700, color: style.color, background: style.bg, border: `1px solid ${style.border}`, borderRadius: 4, padding: '2px 7px', textTransform: 'uppercase', flexShrink: 0 }}>
              {style.label}
            </span>

            {/* Status dot */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: isOn ? TEAL : 'rgba(255,255,255,0.15)', boxShadow: isOn ? `0 0 6px ${TEAL}` : 'none' }} />
              <span style={{ fontSize: 9, fontWeight: 700, color: isOn ? TEAL : '#555', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{isOn ? 'Ativo' : 'Inativo'}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function FeatureFlags() {
  const qc = useQueryClient()
  const [selectedContract, setSelectedContract] = useState('')
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved'>('idle')

  const { data: contratos } = useQuery({ queryKey: ['hub-contratos'], queryFn: () => api('/api/hub/contratos'), staleTime: 60_000 })
  const { data: flagsData, isLoading } = useQuery({
    queryKey: ['feature-flags', selectedContract],
    queryFn: () => api(`/api/hub/contratos?search=${selectedContract}`).then(r => {
      const c = (r.contratos ?? []).find((x: any) => x.contrato === selectedContract)
      return c?.feature_flags ?? {}
    }),
    enabled: !!selectedContract,
  })

  const updateMut = useMutation({
    mutationFn: (body: any) => api(`/api/hub/contratos/${selectedContract}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feature_flags: body }),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feature-flags', selectedContract] })
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus('idle'), 2000)
    },
  })

  const clList: any[] = contratos?.contratos ?? []
  const flags: Record<string, boolean> = flagsData ?? {}

  function handleToggle(key: string, val: boolean) {
    const next = { ...flags, [key]: val }
    updateMut.mutate(next)
  }

  const MODULES = ['infra', 'reembolso', 'rdo', 'ambos'] as const

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
            <SlidersHorizontal size={22} className="text-copper" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-white uppercase tracking-tight">Feature Flags</h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">Controle de funcionalidades por contrato</p>
          </div>
        </div>
        {saveStatus === 'saved' && (
          <div style={{ background: `${TEAL}15`, border: `1px solid ${TEAL}40`, borderRadius: 8, padding: '6px 14px', fontSize: 12, color: TEAL, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
            ✅ Salvo com sucesso
          </div>
        )}
      </div>

      {/* Contract selector */}
      <div style={{ background: GLASS, border: BORDER, borderRadius: 14, padding: 20 }}>
        <div className="flex items-center gap-2 mb-3">
          <Building2 size={13} style={{ color: COPPER }} />
          <span style={{ fontSize: 10, fontWeight: 700, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Contrato</span>
          {selectedContract && <span style={{ fontSize: 11, fontWeight: 700, color: COPPER }}>· {selectedContract}</span>}
        </div>
        <select
          value={selectedContract}
          onChange={e => setSelectedContract(e.target.value)}
          style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, height: 42, padding: '0 14px', fontSize: 14, color: '#ccc', outline: 'none' }}
        >
          <option value="">Selecione um contrato…</option>
          {clList.map((c: any) => <option key={c.contrato} value={c.contrato}>{c.contrato} — {c.projeto}</option>)}
        </select>
      </div>

      {/* Features list */}
      {!selectedContract && (
        <div className="p-20 flex flex-col items-center gap-4 opacity-40">
          <SlidersHorizontal size={48} className="text-white/20" />
          <p className="text-sm font-bold uppercase tracking-widest text-text-muted">Selecione um contrato</p>
          <p className="text-xs text-text-muted">As flags de funcionalidades serão exibidas aqui</p>
        </div>
      )}

      {selectedContract && isLoading && (
        <div className="p-10 text-center text-text-muted animate-pulse text-sm">Carregando configurações...</div>
      )}

      {selectedContract && !isLoading && (
        <div style={{ background: GLASS, border: BORDER, borderRadius: 14, padding: 24 }} className="flex flex-col gap-6">
          {/* Legend */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ToggleRight size={14} style={{ color: '#555' }} />
              <span style={{ fontSize: 10, fontWeight: 700, color: '#555', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Módulos Ativos</span>
            </div>
            <div className="flex items-center gap-4">
              {MODULES.map(m => {
                const s = MODULE_STYLES[m]
                return (
                  <div key={m} className="flex items-center gap-1.5">
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: s.bg, border: `1px solid ${s.border}` }} />
                    <span style={{ fontSize: 10, color: s.color, fontWeight: 600 }}>{s.label}</span>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="flex flex-col gap-6">
            {MODULES.map(mod => {
              const features = FEATURE_DEFS.filter(f => f.module === mod)
              return <ModuleSection key={mod} module={mod} features={features} flags={flags} onToggle={handleToggle} />
            })}
          </div>

          {/* Footer info */}
          <div style={{ background: `${TEAL}06`, border: `1px solid ${TEAL}15`, borderRadius: 12, padding: '14px 16px' }}>
            <div className="flex items-center gap-2 mb-2">
              <Zap size={11} style={{ color: TEAL }} />
              <span style={{ fontSize: 9, fontWeight: 700, color: TEAL, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Como Funciona</span>
            </div>
            <ul className="space-y-1.5">
              {[
                'Alterações entram em vigor imediatamente — próxima carga do formulário já reflete.',
                'Features desligadas ocultam campos e gráficos — sem dados zerados no dashboard.',
                'Configurações são independentes por contrato — combinações distintas são possíveis.',
                'Flags de Infraestrutura têm padrão global. PDF desligado por padrão (1 GB RAM).',
              ].map((t, i) => (
                <li key={i} className="flex items-start gap-2">
                  <div style={{ width: 3, height: 3, borderRadius: '50%', background: TEAL, marginTop: 5, flexShrink: 0, opacity: 0.5 }} />
                  <span style={{ fontSize: 11, color: 'rgba(136,153,153,0.7)', lineHeight: 1.6 }}>{t}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
