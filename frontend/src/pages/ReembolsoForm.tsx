import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Fuel, Camera, MapPin, Send, Loader2 } from 'lucide-react'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

export default function ReembolsoForm() {
  const navigate = useNavigate()
  const fileRef  = useRef<HTMLInputElement>(null)
  const [form, setForm]           = useState<Record<string,any>>({ combustivel:'Gasolina', data_abastecimento: new Date().toISOString().slice(0,10) })
  const [preview, setPreview]     = useState('')
  const [nfUrl, setNfUrl]         = useState('')
  const [aiData, setAiData]       = useState<any>(null)
  const [uploading, setUploading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [checkinLoading, setCheckinLoading] = useState(false)

  const inp = (k:string, type='text') => ({
    type, value: form[k] ?? '',
    onChange: (e:any) => setForm((f:any) => ({...f,[k]:e.target.value})),
    style: { background:'#0d1117', border:'1px solid rgba(201,139,42,0.3)', color:'#e2c87a', borderRadius:8, padding:'7px 10px', width:'100%', fontSize:13 },
  })

  async function handleUploadNF(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setPreview(URL.createObjectURL(file))
    const fd = new FormData()
    fd.append('file', file)
    fd.append('contrato', form.contrato ?? '')
    try {
      const r = await fetch('/api/reembolso/upload-nf', { method:'POST', credentials:'include', body:fd })
      const d = await r.json()
      setNfUrl(d.url)
      if (d.ai_extracted && Object.keys(d.ai_extracted).length > 0) {
        setAiData(d.ai_extracted)
        setForm((f:any) => ({
          ...f,
          combustivel:    d.ai_extracted.combustivel || f.combustivel,
          litros:         d.ai_extracted.litros || f.litros,
          valor_litro:    d.ai_extracted.valor_litro || f.valor_litro,
          valor_total:    d.ai_extracted.valor_total || f.valor_total,
          data_abastecimento: d.ai_extracted.data || f.data_abastecimento,
          cidade:         d.ai_extracted.cidade || f.cidade,
          estado:         d.ai_extracted.estado || f.estado,
        }))
      }
    } finally {
      setUploading(false)
    }
  }

  async function handleCheckin() {
    setCheckinLoading(true)
    navigator.geolocation.getCurrentPosition(async pos => {
      const { latitude:lat, longitude:lng } = pos.coords
      try {
        const r = await fetch('/api/rdo/geocode/reverse', { method:'POST', credentials:'include',
          headers:{'Content-Type':'application/json'}, body:JSON.stringify({lat,lng}) })
        const d = await r.json()
        setForm((f:any) => ({...f, checkin_lat:lat, checkin_lng:lng, checkin_endereco:d.address}))
      } catch {}
      setCheckinLoading(false)
    }, () => setCheckinLoading(false))
  }

  async function handleSubmit() {
    setSubmitting(true)
    try {
      await fetch('/api/reembolso/submit', { method:'POST', credentials:'include',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({ ...form, nf_url:nfUrl, ai_verified:!!aiData, ai_score:aiData ? 85 : 0 }) })
      navigate('/reembolso-dashboard')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-col gap-5 max-w-2xl">
      <div className="flex items-center gap-2">
        <Fuel size={20} style={{ color:COPPER }} />
        <h1 className="font-display text-xl font-bold text-text-primary">Formulário de Reembolso</h1>
      </div>

      {/* Upload NF */}
      <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="p-5">
        <h2 className="text-sm text-text-muted uppercase mb-3 flex items-center gap-2">
          <Camera size={14} style={{ color:COPPER }} /> Foto do Cupom Fiscal
        </h2>
        <input ref={fileRef} type="file" accept="image/*" capture="environment" className="hidden"
          onChange={handleUploadNF} />
        <button onClick={() => fileRef.current?.click()} disabled={uploading}
          style={{ background:GLASS, border:BORDER, color:'#e2c87a', borderRadius:8, padding:'8px 16px', fontSize:13, cursor:'pointer' }}>
          {uploading ? <><Loader2 size={13} className="inline animate-spin mr-1" />Enviando...</> : 'Foto da NF / Cupom'}
        </button>
        {preview && <img src={preview} alt="NF" style={{ marginTop:12, maxHeight:200, borderRadius:8 }} />}
        {aiData && (
          <div style={{ background:`${TEAL}15`, border:`1px solid ${TEAL}40`, borderRadius:8, padding:'8px 12px', marginTop:12 }}>
            <span className="text-xs" style={{ color:TEAL }}>✓ IA extraiu os dados automaticamente da NF</span>
          </div>
        )}
      </div>

      {/* Form fields */}
      <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="p-5">
        <h2 className="text-sm text-text-muted uppercase mb-4">Dados do Abastecimento</h2>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-text-muted">Combustível</label>
            <select {...inp('combustivel')} style={{ ...inp('combustivel').style }}>
              {['Gasolina','Gasolina Aditivada','Etanol','Diesel','Diesel S10','GNV'].map(c => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div><label className="text-xs text-text-muted">Data</label><input {...inp('data_abastecimento','date')} /></div>
          <div><label className="text-xs text-text-muted">Litros</label><input {...inp('litros','number')} step="0.001" /></div>
          <div><label className="text-xs text-text-muted">Valor/Litro (R$)</label><input {...inp('valor_litro','number')} step="0.001" /></div>
          <div><label className="text-xs text-text-muted">Valor Total (R$)</label><input {...inp('valor_total','number')} step="0.01" /></div>
          <div><label className="text-xs text-text-muted">Cidade</label><input {...inp('cidade')} /></div>
          <div><label className="text-xs text-text-muted">Estado</label><input {...inp('estado')} maxLength={2} /></div>
          <div><label className="text-xs text-text-muted">KM Inicial</label><input {...inp('km_inicial')} /></div>
          <div><label className="text-xs text-text-muted">KM Final</label><input {...inp('km_final')} /></div>
          <div className="col-span-2"><label className="text-xs text-text-muted">Rota / Destino</label><input {...inp('rota')} /></div>
          <div className="col-span-2"><label className="text-xs text-text-muted">Finalidade</label><input {...inp('finalidade')} /></div>
        </div>
      </div>

      {/* GPS */}
      <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="p-5">
        <h2 className="text-sm text-text-muted uppercase mb-3 flex items-center gap-2">
          <MapPin size={14} style={{ color:COPPER }} /> Localização
        </h2>
        <button onClick={handleCheckin} disabled={checkinLoading}
          style={{ background: form.checkin_lat ? `${TEAL}20` : GLASS, border:`1px solid ${form.checkin_lat ? TEAL:'rgba(201,139,42,0.3)'}`,
            color: form.checkin_lat ? TEAL:'#e2c87a', borderRadius:8, padding:'8px 16px', fontSize:13, cursor:'pointer' }}>
          {checkinLoading ? 'Obtendo localização...' : form.checkin_lat ? `✓ ${form.checkin_endereco}` : 'Capturar GPS'}
        </button>
      </div>

      <button onClick={handleSubmit} disabled={submitting || !nfUrl}
        style={{ background:COPPER, color:'#0d1117', border:'none', borderRadius:10, padding:'12px', fontSize:15, fontWeight:700,
          cursor: (!submitting && nfUrl) ? 'pointer':'not-allowed', opacity:(!submitting && nfUrl) ? 1:0.5 }}>
        {submitting ? <><Loader2 size={15} className="inline animate-spin mr-2" />Enviando...</> : <><Send size={15} className="inline mr-2" />Enviar Reembolso</>}
      </button>
    </div>
  )
}
