import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Globe, Plus, Loader2, Users, DollarSign } from 'lucide-react'

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

export default function MasterConsole() {
  const [tab, setTab]       = useState<'tenants'|'users'|'ai'>('tenants')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm]         = useState<Record<string,string>>({ ai_budget:'100' })
  const qc = useQueryClient()

  const { data }    = useQuery({ queryKey:['master-tenants'], queryFn:()=>api('/api/master/tenants') })
  const { data:users } = useQuery({ queryKey:['master-users'], queryFn:()=>api('/api/master/users'), enabled:tab==='users' })
  const { data:ai }    = useQuery({ queryKey:['master-ai'], queryFn:()=>api('/api/master/ai-usage'), enabled:tab==='ai' })

  const createMut = useMutation({
    mutationFn:(body:any) => api('/api/master/tenants', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }),
    onSuccess:() => { qc.invalidateQueries({queryKey:['master-tenants']}); setShowForm(false); setForm({ai_budget:'100'}) },
  })

  const tenants: any[] = data?.tenants ?? []
  const inp = (k:string) => ({
    value: form[k] ?? '',
    onChange: (e:any) => setForm((f:any) => ({...f,[k]:e.target.value})),
    style: { background:'#0d1117', border:'1px solid rgba(201,139,42,0.3)', color:'#e2c87a', borderRadius:8, padding:'6px 10px', width:'100%', fontSize:13 },
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 mb-2">
        <Globe size={20} style={{ color:COPPER }} />
        <h1 className="font-display text-xl font-bold text-text-primary">Master Console</h1>
        <span style={{ background:`${RED}20`, color:RED, borderRadius:6, padding:'2px 8px', fontSize:11, fontWeight:700 }}>BTP MASTER</span>
      </div>

      <div style={{ borderBottom:'1px solid rgba(201,139,42,0.15)' }} className="flex gap-1">
        {[['tenants','Tenants'],['users','Usuários'],['ai','AI Budget']].map(([t,l]) => (
          <button key={t} onClick={() => setTab(t as any)}
            style={{ color:tab===t ? COPPER:'#888', borderBottom:tab===t ? `2px solid ${COPPER}`:'2px solid transparent',
              background:'none', border:'none', padding:'8px 16px', fontSize:13, fontWeight:tab===t?700:400, cursor:'pointer' }}>
            {l}
          </button>
        ))}
      </div>

      {tab === 'tenants' && (
        <div className="flex flex-col gap-3">
          <div className="flex justify-end">
            <button onClick={() => setShowForm(true)}
              style={{ background:COPPER, color:'#0d1117', border:'none', borderRadius:8, padding:'6px 14px', fontSize:13, fontWeight:700, cursor:'pointer' }}>
              <Plus size={13} className="inline mr-1" />Novo Tenant
            </button>
          </div>

          {showForm && (
            <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="p-4">
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-xs text-text-muted">Nome da Empresa *</label><input {...inp('name')} /></div>
                <div><label className="text-xs text-text-muted">Budget AI (US$)</label><input {...inp('ai_budget')} type="number" /></div>
                <div><label className="text-xs text-text-muted">Login Admin *</label><input {...inp('admin_username')} /></div>
                <div><label className="text-xs text-text-muted">Senha Admin *</label><input {...inp('admin_password')} type="password" style={{ ...inp('admin_password').style }} /></div>
              </div>
              <div className="flex gap-2 mt-3">
                <button onClick={() => createMut.mutate(form)} disabled={createMut.isPending}
                  style={{ background:TEAL, color:'#fff', border:'none', borderRadius:8, padding:'6px 16px', cursor:'pointer', fontSize:13 }}>
                  {createMut.isPending ? <Loader2 size={13} className="inline animate-spin mr-1" /> : null}Criar Tenant
                </button>
                <button onClick={() => { setShowForm(false); setForm({ai_budget:'100'}) }}
                  style={{ background:GLASS, color:'#888', border:'1px solid #333', borderRadius:8, padding:'6px 16px', cursor:'pointer', fontSize:13 }}>Cancelar</button>
              </div>
            </div>
          )}

          <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom:'1px solid rgba(201,139,42,0.15)' }}>
                  {['Empresa','Status','Usuários','Budget AI','Logs',''].map(h => (
                    <th key={h} className="text-left px-3 py-2 text-xs text-text-muted uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tenants.map(t => (
                  <tr key={t.client_id} style={{ borderBottom:'1px solid rgba(255,255,255,0.04)' }} className="hover:bg-white/5">
                    <td className="px-3 py-2 font-semibold text-text-primary">{t.client_name}</td>
                    <td className="px-3 py-2">
                      <span style={{ fontSize:11, fontWeight:600, color:t.status==='active' ? TEAL:RED, background:`${t.status==='active'?TEAL:RED}20`, borderRadius:5, padding:'2px 8px' }}>
                        {t.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-text-muted text-xs">{t.user_count}</td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color:COPPER }}>US$ {t.ai_budget}</td>
                    <td className="px-3 py-2 text-text-muted text-xs">{t.total_logs}</td>
                    <td className="px-3 py-2">
                      {t.is_master && <span style={{ fontSize:10, color:RED, fontWeight:700 }}>MASTER</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {tenants.length === 0 && <div className="p-6 text-center text-text-muted">Nenhum tenant.</div>}
          </div>
        </div>
      )}

      {tab === 'users' && (
        <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom:'1px solid rgba(201,139,42,0.15)' }}>
                {['Login','Role','Empresa','Email','Status'].map(h => (
                  <th key={h} className="text-left px-3 py-2 text-xs text-text-muted uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(users?.users ?? []).map((u:any) => (
                <tr key={u.id} style={{ borderBottom:'1px solid rgba(255,255,255,0.04)' }} className="hover:bg-white/5">
                  <td className="px-3 py-2 font-mono text-xs text-text-primary">{u.login}</td>
                  <td className="px-3 py-2 text-xs" style={{ color:COPPER }}>{u.role}</td>
                  <td className="px-3 py-2 text-xs text-text-muted">{u.client_name}</td>
                  <td className="px-3 py-2 text-xs text-text-muted">{u.email || '—'}</td>
                  <td className="px-3 py-2 text-xs" style={{ color:u.is_active ? TEAL:RED }}>{u.is_active ? 'Ativo':'Inativo'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'ai' && (
        <div className="flex flex-col gap-4">
          {(ai?.by_tenant ?? []).map((t:any) => (
            <div key={t.client_id} style={{ background:GLASS, border:BORDER, borderRadius:10 }} className="p-4 flex items-center gap-4">
              <div className="flex-1">
                <div className="text-sm font-semibold text-text-primary">{t.client_name}</div>
                <div className="text-xs text-text-muted">{t.calls} chamadas · {t.tokens.toLocaleString()} tokens</div>
              </div>
              <div className="font-display text-lg font-bold" style={{ color:COPPER }}>US$ {t.cost_usd.toFixed(4)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
