import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Fuel, DollarSign, Clock, CheckCircle } from 'lucide-react'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

async function api(path: string, opts?: RequestInit) {
  const r = await fetch(path, { credentials:'include', ...opts })
  if (!r.ok) throw new Error()
  return r.json()
}

export default function ReembolsoDashboard() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey:['reembolso-dash'], queryFn:()=>api('/api/reembolso/dashboard') })

  const updateMut = useMutation({
    mutationFn: ({ id, status }:{id:string,status:string}) =>
      api(`/api/reembolso/${id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status}) }),
    onSuccess: () => qc.invalidateQueries({queryKey:['reembolso-dash']}),
  })

  if (isLoading) return <div className="animate-pulse p-8 text-text-muted">Carregando...</div>
  const d = data ?? {}
  const items: any[] = d.items ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 mb-2">
        <Fuel size={20} style={{ color:COPPER }} />
        <h1 className="font-display text-xl font-bold text-text-primary">Reembolso de Combustível</h1>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { l:'Total Enviado', v:d.total_valor ?? 'R$ 0,00', icon:DollarSign },
          { l:'Pendentes', v:d.pendentes ?? 0, icon:Clock, color:COPPER },
          { l:'Aprovados', v:d.aprovados ?? 0, icon:CheckCircle, color:TEAL },
          { l:'Verificados IA', v:d.ai_verified ?? 0, icon:Fuel, color:TEAL },
        ].map(k => (
          <div key={k.l} style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="p-4">
            <div className="text-xs text-text-muted uppercase">{k.l}</div>
            <div className="font-display text-xl font-bold mt-1" style={{ color:k.color ?? '#e2c87a' }}>{k.v}</div>
          </div>
        ))}
      </div>

      <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom:'1px solid rgba(201,139,42,0.15)' }}>
              {['Usuário','Combustível','Litros','Valor','Data','Cidade','IA','Status',''].map(h => (
                <th key={h} className="text-left px-3 py-2 text-xs text-text-muted uppercase">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map(r => (
              <tr key={r.id} style={{ borderBottom:'1px solid rgba(255,255,255,0.04)' }} className="hover:bg-white/5">
                <td className="px-3 py-2 font-mono text-xs text-text-muted">{r.usuario_login}</td>
                <td className="px-3 py-2 text-text-primary text-xs">{r.combustivel}</td>
                <td className="px-3 py-2 text-text-muted text-xs">{r.litros}L</td>
                <td className="px-3 py-2 font-mono text-xs" style={{ color:COPPER }}>{r.valor_total_fmt}</td>
                <td className="px-3 py-2 font-mono text-xs text-text-muted">{r.data_abastecimento}</td>
                <td className="px-3 py-2 text-xs text-text-muted">{r.cidade}/{r.estado}</td>
                <td className="px-3 py-2 text-xs">
                  <span style={{ color:r.ai_verified ? TEAL:'#555' }}>{r.ai_score}%</span>
                </td>
                <td className="px-3 py-2">
                  <select value={r.status}
                    onChange={e => updateMut.mutate({ id:r.id, status:e.target.value })}
                    style={{ background:'#0d1117', border:'none', color: r.status==='Aprovado' ? TEAL : r.status==='Rejeitado' ? RED : COPPER,
                      fontSize:11, fontWeight:700, borderRadius:5, padding:'2px 6px', cursor:'pointer' }}>
                    {['Pendente','Aprovado','Rejeitado','Pago'].map(s => <option key={s}>{s}</option>)}
                  </select>
                </td>
                <td className="px-3 py-2">
                  {r.nf_url && <a href={r.nf_url} target="_blank" rel="noopener noreferrer" style={{ color:COPPER, fontSize:11 }}>NF</a>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <div className="p-6 text-center text-text-muted">Nenhum reembolso enviado.</div>}
      </div>
    </div>
  )
}
