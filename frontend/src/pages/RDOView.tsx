import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { ClipboardList, MapPin, Camera, Sparkles, AlertTriangle, CheckCircle } from 'lucide-react'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

async function fetchPublic(path: string) {
  const r = await fetch(path)
  if (!r.ok) throw new Error()
  return r.json()
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '10px 14px' }}>
      <div style={{ fontSize: 10, color: '#666', textTransform: 'uppercase', marginBottom: 4, letterSpacing: '0.15em' }}>{label}</div>
      <div style={{ fontSize: 14, color: '#e2c87a', fontWeight: 600 }}>{value || '—'}</div>
    </div>
  )
}

function InsightPill({ priority, title, body }: { priority: string; title: string; body: string }) {
  const colors: Record<string, { border: string; badge: string; text: string }> = {
    High:   { border: `1px solid ${RED}40`,    badge: `${RED}20`,    text: RED },
    Medium: { border: `1px solid ${COPPER}40`, badge: `${COPPER}15`, text: COPPER },
    Low:    { border: `1px solid ${TEAL}30`,   badge: `${TEAL}15`,   text: TEAL },
  }
  const cfg = colors[priority] || colors.Low
  return (
    <div style={{ background: GLASS, border: cfg.border, borderRadius: 10, padding: '12px 14px', marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 10, fontWeight: 800, color: cfg.text, background: cfg.badge, padding: '2px 8px', borderRadius: 10, textTransform: 'uppercase' }}>
          {priority === 'High' ? 'CRÍTICO' : priority === 'Medium' ? 'MÉDIO' : 'BAIXO'}
        </span>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#e2c87a' }}>{title}</span>
      </div>
      <p style={{ fontSize: 12, color: '#888', lineHeight: 1.6 }}>{body}</p>
    </div>
  )
}

export default function RDOView() {
  const { token } = useParams<{ token: string }>()

  const { data, isLoading, error } = useQuery({
    queryKey: ['rdo-view', token],
    queryFn: () => fetchPublic(`/api/rdo/view/${token}`),
    enabled: !!token,
  })

  if (isLoading) return (
    <div style={{ minHeight: '100vh', background: '#0d1117', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ color: COPPER, fontSize: 16 }}>Carregando RDO...</span>
    </div>
  )

  if (error || !data?.rdo) return (
    <div style={{ minHeight: '100vh', background: '#0d1117', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ color: RED }}>RDO não encontrado ou link inválido.</span>
    </div>
  )

  const r    = data.rdo
  const ats: any[]      = data.atividades ?? []
  const evs: any[]      = data.evidencias ?? []
  const insights: any[] = data.insights ?? []
  const aiSummary: string = r.ai_summary || ''

  return (
    <div style={{ minHeight: '100vh', background: '#0d1117', color: '#e2c87a', fontFamily: 'Outfit, sans-serif', padding: '32px 24px', maxWidth: 820, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ borderBottom: `2px solid ${COPPER}`, paddingBottom: 20, marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <ClipboardList size={24} style={{ color: COPPER }} />
          <div style={{ color: COPPER, fontFamily: 'Rajdhani, sans-serif', fontSize: 24, fontWeight: 800, letterSpacing: '0.05em' }}>
            BOMTEMPO INTELLIGENCE — RDO
          </div>
        </div>
        <div style={{ fontSize: 13, color: '#666' }}>
          Relatório Diário de Obra · Contrato <strong style={{ color: '#e2c87a' }}>{r.contrato}</strong> · {r.data}
        </div>
        <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: r.status === 'Submetido' ? TEAL : COPPER, background: `${r.status === 'Submetido' ? TEAL : COPPER}20`, padding: '3px 10px', borderRadius: 6 }}>
            {r.status}
          </span>
          {r.turno && <span style={{ fontSize: 11, color: '#555' }}>Turno: {r.turno}</span>}
        </div>
      </div>

      {/* Info grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
        <InfoBlock label="Projeto" value={r.projeto} />
        <InfoBlock label="Cliente" value={r.cliente} />
        <InfoBlock label="Data" value={r.data} />
        <InfoBlock label="Clima" value={r.clima} />
        <InfoBlock label="Turno" value={r.turno} />
        <InfoBlock label="Equipe Alocada" value={r.equipe_alocada} />
        {r.localizacao && <InfoBlock label="Localização" value={r.localizacao} />}
        {r.km_percorrido && <InfoBlock label="KM Percorrido" value={r.km_percorrido} />}
        {r.tipo_tarefa && <InfoBlock label="Tipo de Registro" value={r.tipo_tarefa} />}
      </div>

      {/* Observações */}
      {r.observacoes && (
        <div style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '14px 16px', marginBottom: 20 }}>
          <div style={{ fontSize: 10, color: '#666', textTransform: 'uppercase', marginBottom: 6, letterSpacing: '0.15em' }}>Observações Gerais</div>
          <p style={{ fontSize: 13, color: '#ccc', lineHeight: 1.6 }}>{r.observacoes}</p>
        </div>
      )}

      {/* Orientação técnica */}
      {r.orientacao && (
        <div style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '14px 16px', marginBottom: 20 }}>
          <div style={{ fontSize: 10, color: '#666', textTransform: 'uppercase', marginBottom: 6, letterSpacing: '0.15em' }}>Orientação Técnica</div>
          <p style={{ fontSize: 13, color: '#ccc', lineHeight: 1.6 }}>{r.orientacao}</p>
        </div>
      )}

      {/* Interrupção */}
      {r.houve_interrupcao && (
        <div style={{ background: `${RED}08`, border: `1px solid ${RED}30`, borderRadius: 10, padding: '12px 16px', marginBottom: 20, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <AlertTriangle size={14} style={{ color: RED, marginTop: 2, flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: RED, textTransform: 'uppercase', marginBottom: 4 }}>Houve interrupção das atividades</div>
            <p style={{ fontSize: 13, color: '#ccc' }}>{r.motivo_interrupcao || '—'}</p>
          </div>
        </div>
      )}

      {/* GPS Check-in */}
      {r.checkin_lat !== 0 && (
        <div style={{ background: GLASS, border: BORDER, borderRadius: 10, padding: '12px 16px', marginBottom: 12 }}>
          <div style={{ fontSize: 10, color: '#666', textTransform: 'uppercase', marginBottom: 6, display: 'flex', gap: 6, alignItems: 'center', letterSpacing: '0.12em' }}>
            <MapPin size={11} style={{ color: '#22c55e' }} /> Localização — Check-in
          </div>
          <div style={{ fontSize: 13, color: '#ccc' }}>{r.checkin_endereco || 'Endereço registrado'}</div>
          <div style={{ fontSize: 11, color: '#555', fontFamily: 'monospace', marginTop: 4 }}>
            {r.checkin_lat?.toFixed(6)}, {r.checkin_lng?.toFixed(6)}
            {r.checkin_timestamp && <span style={{ marginLeft: 12, color: '#444' }}>{new Date(r.checkin_timestamp).toLocaleString('pt-BR')}</span>}
          </div>
        </div>
      )}

      {/* GPS Check-out */}
      {r.checkout_lat !== 0 && (
        <div style={{ background: GLASS, border: `1px solid ${TEAL}25`, borderRadius: 10, padding: '12px 16px', marginBottom: 20 }}>
          <div style={{ fontSize: 10, color: '#666', textTransform: 'uppercase', marginBottom: 6, display: 'flex', gap: 6, alignItems: 'center', letterSpacing: '0.12em' }}>
            <MapPin size={11} style={{ color: TEAL }} /> Localização — Check-out
          </div>
          <div style={{ fontSize: 13, color: '#ccc' }}>{r.checkout_endereco || 'Endereço registrado'}</div>
          <div style={{ fontSize: 11, color: '#555', fontFamily: 'monospace', marginTop: 4 }}>
            {r.checkout_lat?.toFixed(6)}, {r.checkout_lng?.toFixed(6)}
            {r.checkout_timestamp && <span style={{ marginLeft: 12, color: '#444' }}>{new Date(r.checkout_timestamp).toLocaleString('pt-BR')}</span>}
          </div>
        </div>
      )}

      {/* Atividades */}
      {ats.length > 0 && (
        <div style={{ marginBottom: 28 }}>
          <h3 style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', marginBottom: 12, letterSpacing: '0.2em', display: 'flex', alignItems: 'center', gap: 6 }}>
            <CheckCircle size={12} style={{ color: COPPER }} /> Atividades Executadas
          </h3>
          {ats.map((a: any) => (
            <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', borderBottom: '1px solid rgba(255,255,255,0.04)', background: GLASS, borderRadius: 8, marginBottom: 4 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, color: '#e2c87a', fontWeight: 600 }}>{a.descricao}</div>
                {(a.qtd_executada || a.unidade) && (
                  <div style={{ fontSize: 11, color: '#555', marginTop: 2 }}>
                    {a.qtd_executada} {a.unidade}
                  </div>
                )}
              </div>
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div style={{ fontSize: 13, color: COPPER, fontWeight: 700 }}>{a.pct}%</div>
                <div style={{ fontSize: 10, color: '#555' }}>{a.status}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Evidências */}
      {evs.length > 0 && (
        <div style={{ marginBottom: 28 }}>
          <h3 style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', marginBottom: 12, letterSpacing: '0.2em', display: 'flex', gap: 6, alignItems: 'center' }}>
            <Camera size={12} style={{ color: COPPER }} /> Evidências Fotográficas
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
            {evs.map((e: any) => (
              <div key={e.id} style={{ borderRadius: 10, overflow: 'hidden', background: GLASS, border: BORDER }}>
                <img src={e.foto_url} alt={e.legenda || ''} style={{ width: '100%', aspectRatio: '4/3', objectFit: 'cover', display: 'block' }} />
                {(e.legenda || e.address) && (
                  <div style={{ padding: '8px 10px' }}>
                    {e.legenda && <div style={{ fontSize: 11, color: '#888' }}>{e.legenda}</div>}
                    {e.address && <div style={{ fontSize: 10, color: '#555', marginTop: 2 }}>📍 {e.address}</div>}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Daily Analysis */}
      {aiSummary && (
        <div style={{ background: `${TEAL}08`, border: `1px solid ${TEAL}30`, borderRadius: 12, padding: '20px', marginBottom: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Sparkles size={16} style={{ color: TEAL }} />
            <span style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.2em', color: TEAL }}>Análise de IA — Obra do Dia</span>
          </div>
          <p style={{ fontSize: 13, color: '#ccc', lineHeight: 1.7, margin: 0 }}>{aiSummary}</p>
        </div>
      )}

      {/* AI Insights */}
      {insights.length > 0 && (
        <div style={{ background: `${COPPER}06`, border: `1px solid ${COPPER}25`, borderRadius: 12, padding: '20px', marginBottom: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <Sparkles size={16} style={{ color: COPPER }} />
            <span style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.2em', color: COPPER }}>Insights do Agente IA</span>
          </div>
          {insights.map((ins: any, i: number) => (
            <InsightPill key={i} priority={ins.priority} title={ins.title} body={ins.body} />
          ))}
        </div>
      )}

      {/* Assinatura digital */}
      {r.signatory_name && (
        <div style={{ borderTop: `1px solid rgba(201,139,42,0.2)`, marginTop: 32, paddingTop: 20 }}>
          <div style={{ fontSize: 10, color: '#555', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 8 }}>Responsável pela Aprovação</div>
          <div style={{ fontSize: 14, color: '#e2c87a', fontWeight: 600 }}>{r.signatory_name}</div>
          {r.signatory_doc && <div style={{ fontSize: 12, color: '#555', marginTop: 2 }}>Documento: {r.signatory_doc}</div>}
          {r.signatory_sig_b64 && r.signatory_sig_b64.startsWith('data:') && (
            <div style={{ marginTop: 12, background: '#fff', borderRadius: 8, display: 'inline-block', padding: 8 }}>
              <img src={r.signatory_sig_b64} alt="Assinatura" style={{ maxWidth: 280, height: 80, objectFit: 'contain', display: 'block' }} />
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: 40, fontSize: 10, color: '#333', textAlign: 'center', borderTop: '1px solid rgba(255,255,255,0.04)', paddingTop: 20 }}>
        Bomtempo Intelligence · Relatório Diário de Obra · Gerado em {new Date().toLocaleDateString('pt-BR')}
      </div>
    </div>
  )
}
