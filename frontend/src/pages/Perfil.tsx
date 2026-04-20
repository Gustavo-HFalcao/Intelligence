import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { User, Save } from 'lucide-react'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

async function api(path: string, opts?: RequestInit) {
  const r = await fetch(path, { credentials:'include', ...opts })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export default function Perfil() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [form, setForm] = useState<Record<string,string>>({})
  const [saved, setSaved] = useState(false)

  const { data } = useQuery({ queryKey:['perfil'], queryFn:()=>api('/api/usuarios/perfil') })

  const updateMut = useMutation({
    mutationFn:(body:any) => api('/api/usuarios/perfil', { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({queryKey:['perfil']}); setSaved(true); setTimeout(()=>setSaved(false),2000) },
  })

  const u = data?.user ?? {}
  const inp = (k:string, type='text') => ({
    type, value: form[k] ?? u[k] ?? '',
    onChange: (e:any) => setForm((f:any) => ({...f,[k]:e.target.value})),
    style: { background:'#0d1117', border:'1px solid rgba(201,139,42,0.3)', color:'#e2c87a', borderRadius:8, padding:'7px 10px', width:'100%', fontSize:13 },
  })

  return (
    <div className="flex flex-col gap-5 max-w-lg">
      <div className="flex items-center gap-3">
        <div style={{ width:48, height:48, borderRadius:'50%', background:`${COPPER}30`, border:`2px solid ${COPPER}`,
          display:'flex', alignItems:'center', justifyContent:'center' }}>
          <span style={{ color:COPPER, fontWeight:700, fontSize:18 }}>{(u.login||user?.login||'?')[0]?.toUpperCase()}</span>
        </div>
        <div>
          <div className="font-display text-xl font-bold text-text-primary">{u.nome || u.login}</div>
          <div className="text-xs text-text-muted">{u.role}</div>
        </div>
      </div>

      <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="p-5">
        <h2 className="text-sm text-text-muted uppercase mb-4">Informações Pessoais</h2>
        <div className="flex flex-col gap-3">
          <div><label className="text-xs text-text-muted">Nome</label><input {...inp('nome')} /></div>
          <div><label className="text-xs text-text-muted">Email</label><input {...inp('email','email')} /></div>
          <div><label className="text-xs text-text-muted">Nova Senha (deixar vazio para manter)</label><input {...inp('password','password')} /></div>
        </div>
        <button onClick={() => updateMut.mutate(form)}
          style={{ background:saved ? TEAL : COPPER, color:'#0d1117', border:'none', borderRadius:8, padding:'8px 20px', fontSize:14, fontWeight:700, cursor:'pointer', marginTop:16 }}>
          <Save size={14} className="inline mr-1" />
          {saved ? 'Salvo!' : 'Salvar Alterações'}
        </button>
      </div>

      <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="p-5">
        <h2 className="text-sm text-text-muted uppercase mb-3">Informações da Conta</h2>
        {[['Login', u.login],['Role', u.role],['Contrato', u.contrato || '—'],['Membro desde', u.created_at || '—']].map(([l,v]) => (
          <div key={l} className="flex justify-between py-2" style={{ borderBottom:'1px solid rgba(255,255,255,0.05)' }}>
            <span className="text-xs text-text-muted">{l}</span>
            <span className="text-xs text-text-primary font-mono">{v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
