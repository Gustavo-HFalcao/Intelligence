import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { motion } from 'framer-motion'
import { Users, Plus, Trash2, Edit2, Shield } from 'lucide-react'
import { Button } from '@/components/ui/button'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

async function api(path: string, opts?: RequestInit) {
  const r = await fetch(path, { credentials:'include', ...opts })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

const ROLES = ['Administrador','Engenheiro','Gestão-Mobile','Operário']

export default function Usuarios() {
  const [tab, setTab]         = useState<'usuarios'|'perfis'>('usuarios')
  const [showUserForm, setShowUserForm] = useState(false)
  const [showRoleForm, setShowRoleForm] = useState(false)
  const [editUser, setEditUser] = useState<any|null>(null)
  const [editRole, setEditRole] = useState<any|null>(null)
  const [userForm, setUserForm] = useState<Record<string,any>>({ is_active: true })
  const [roleForm, setRoleForm] = useState<Record<string,any>>({ modulos: [] })
  const qc = useQueryClient()

  const { data: userData }    = useQuery({ queryKey:['usuarios'],        queryFn:()=>api('/api/usuarios') })
  const { data: rolesData }   = useQuery({ queryKey:['roles'],           queryFn:()=>api('/api/usuarios/roles') })
  const { data: contratosData } = useQuery({ queryKey:['contratos-select'], queryFn:()=>api('/api/hub/contratos') })

  // User Mutations
  const createUserMut = useMutation({
    mutationFn: (body:any) => api('/api/usuarios', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({queryKey:['usuarios']}); setShowUserForm(false); setUserForm({ is_active: true }) },
  })

  const updateUserMut = useMutation({
    mutationFn: ({ id, body }:{id:string,body:any}) => api(`/api/usuarios/${id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({queryKey:['usuarios']}); setEditUser(null) },
  })

  const deleteUserMut = useMutation({
    mutationFn: (id:string) => api(`/api/usuarios/${id}`, { method:'DELETE' }),
    onSuccess: () => qc.invalidateQueries({queryKey:['usuarios']}),
  })

  // Role Mutations
  const createRoleMut = useMutation({
    mutationFn: (body:any) => api('/api/usuarios/roles', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({queryKey:['roles']}); setShowRoleForm(false); setRoleForm({ modulos: [] }) },
  })

  const updateRoleMut = useMutation({
    mutationFn: ({ id, body }:{id:string,body:any}) => api(`/api/usuarios/roles/${id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({queryKey:['roles']}); setEditRole(null) },
  })

  // Data helpers
  const users = userData?.users ?? []
  const roles = rolesData?.roles ?? []
  const availableModules = rolesData?.modules ?? []
  const landingOptions = rolesData?.landing_options ?? []
  const contratosList: any[] = contratosData?.contratos ?? []

  const toggleModule = (slug: string) => {
    setRoleForm(prev => {
      const current = prev.modulos || prev.modules || []
      const next = current.includes(slug)
        ? current.filter((s: string) => s !== slug)
        : [...current, slug]
      return { ...prev, modulos: next, modules: next }
    })
  }

  return (
    <div className="flex flex-col gap-6 animate-enter">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-copper/20 border border-copper/30">
            <Users size={20} className="text-copper" />
          </div>
          <div className="flex flex-col">
            <h1 className="font-display text-xl font-bold text-white uppercase tracking-tight">Governança & Identidade</h1>
            <p className="text-[10px] text-text-muted font-bold uppercase tracking-widest border-l border-copper/30 pl-2">Gestão de RBAC e Provisionamento</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/5 pb-px">
        {[
          { id: 'usuarios', label: 'Colaboradores Ativos', count: users.length },
          { id: 'perfis', label: 'Perfis de Acesso (RBAC)', count: roles.length }
        ].map(t => (
          <button 
            key={t.id}
            onClick={() => setTab(t.id as any)}
            className={`relative px-4 py-3 text-[10px] font-black uppercase tracking-widest transition-all ${tab === t.id ? 'text-copper' : 'text-text-muted hover:text-white'}`}
          >
            {t.label} <span className="ml-1 opacity-40">[{t.count}]</span>
            {tab === t.id && (
              <motion.div layoutId="userTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-copper" />
            )}
          </button>
        ))}
      </div>

      {/* USUÁRIOS TAB */}
      {tab === 'usuarios' && (
        <div className="flex flex-col gap-4">
          <div className="flex justify-end">
            <Button 
              onClick={() => { setEditUser(null); setUserForm({ is_active: true }); setShowUserForm(true); }}
              className="bg-copper text-void font-black text-[10px] uppercase tracking-widest h-9 px-6"
            >
              <Plus size={16} className="mr-2" /> Provisionar Usuário
            </Button>
          </div>

          {showUserForm && (
            <div style={{ background: GLASS, border: BORDER, borderRadius: 16 }} className="p-6 animate-enter mb-4 relative overflow-hidden">
              <div className="absolute top-0 right-0 p-4 opacity-5">
                 <Shield size={64} className="text-copper" />
              </div>
              <h3 className="text-[10px] font-black text-copper uppercase tracking-widest mb-4 border-b border-copper/10 pb-2">
                {editUser ? `Editar: ${editUser.login}` : 'Parâmetros de Provisionamento'}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {!editUser && (
                  <div className="flex flex-col gap-1.5">
                     <label className="text-[9px] font-black text-text-muted uppercase tracking-widest">Login de Acesso *</label>
                     <input
                      value={userForm.login || ''}
                      onChange={e => setUserForm(prev => ({...prev, login: e.target.value}))}
                      className="bg-void/50 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:border-copper outline-none transition-all"
                     />
                  </div>
                )}
                <div className="flex flex-col gap-1.5">
                   <label className="text-[9px] font-black text-text-muted uppercase tracking-widest">
                     {editUser ? 'Nova Senha (deixe em branco para não alterar)' : 'Senha Temporária *'}
                   </label>
                   <input
                    type="password"
                    value={userForm.password || ''}
                    onChange={e => setUserForm(prev => ({...prev, password: e.target.value}))}
                    className="bg-void/50 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:border-copper outline-none transition-all"
                   />
                </div>
                <div className="flex flex-col gap-1.5">
                   <label className="text-[9px] font-black text-text-muted uppercase tracking-widest">Perfil Operacional (RBAC)</label>
                   <select
                    value={userForm.role || ''}
                    onChange={e => setUserForm(prev => ({...prev, role: e.target.value}))}
                    className="bg-void/50 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:border-copper outline-none transition-all appearance-none"
                    style={{ colorScheme: 'dark' }}
                   >
                     <option value="">Selecione um Perfil...</option>
                     {roles.map((r: any) => (
                       <option key={r.id} value={r.nome}>{r.nome}</option>
                     ))}
                   </select>
                </div>
                <div className="flex flex-col gap-1.5">
                   <label className="text-[9px] font-black text-text-muted uppercase tracking-widest">Nome Completo</label>
                   <input
                    value={userForm.nome || ''}
                    onChange={e => setUserForm(prev => ({...prev, nome: e.target.value}))}
                    className="bg-void/50 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:border-copper outline-none transition-all"
                   />
                </div>
                <div className="flex flex-col gap-1.5">
                   <label className="text-[9px] font-black text-text-muted uppercase tracking-widest">Email Corporativo</label>
                   <input
                    value={userForm.email || ''}
                    onChange={e => setUserForm(prev => ({...prev, email: e.target.value}))}
                    className="bg-void/50 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:border-copper outline-none transition-all"
                   />
                </div>
                <div className="flex flex-col gap-1.5">
                   <label className="text-[9px] font-black text-text-muted uppercase tracking-widest">Unidade / Contrato</label>
                   <select
                    value={userForm.contrato || ''}
                    onChange={e => setUserForm(prev => ({...prev, contrato: e.target.value}))}
                    className="bg-void/50 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:border-copper outline-none transition-all appearance-none"
                    style={{ colorScheme: 'dark' }}
                   >
                     <option value="">Selecione um Contrato...</option>
                     {contratosList.map((c: any) => (
                       <option key={c.contrato} value={c.contrato}>{c.projeto ? `${c.projeto} (${c.contrato})` : c.contrato}</option>
                     ))}
                   </select>
                </div>
              </div>

              <div className="flex items-center gap-2 mt-6 pt-6 border-t border-white/5">
                 <Button
                    onClick={() => editUser
                      ? updateUserMut.mutate({ id: editUser.id, body: userForm })
                      : createUserMut.mutate(userForm)
                    }
                    disabled={createUserMut.isPending || updateUserMut.isPending}
                    className="bg-teal-500 hover:bg-teal-600 text-void font-black text-[10px] uppercase tracking-widest px-8"
                 >
                    {(createUserMut.isPending || updateUserMut.isPending) ? 'Salvando...' : editUser ? 'Salvar Alterações' : 'Efetivar Usuário'}
                 </Button>
                 <Button
                    variant="link"
                    onClick={() => { setShowUserForm(false); setEditUser(null); setUserForm({ is_active: true }); }}
                    className="text-text-muted hover:text-white text-[10px] font-bold uppercase tracking-widest"
                 >
                    Cancelar Operação
                 </Button>
              </div>
            </div>
          )}

          <div style={{ background: GLASS, border: BORDER, borderRadius: 16 }} className="overflow-hidden">
             <table className="w-full text-left border-collapse">
               <thead>
                 <tr className="bg-void/50 border-b border-white/5">
                   {['Login', 'Identidade', 'Perfil Atribuído', 'Status Ativo', 'Ações'].map(h => (
                     <th key={h} className="px-5 py-3 text-[9px] text-text-muted uppercase tracking-[0.2em] font-black">{h}</th>
                   ))}
                 </tr>
               </thead>
               <tbody className="divide-y divide-white/[0.02]">
                 {users.map((u: any) => (
                   <tr key={u.id} className="hover:bg-white/[0.02] transition-colors group">
                     <td className="px-5 py-4 font-mono text-xs text-copper">{u.login}</td>
                     <td className="px-5 py-4">
                        <div className="flex flex-col">
                           <span className="text-white font-bold text-xs uppercase tracking-tight">{u.nome}</span>
                           <span className="text-[9px] text-text-muted truncate max-w-[150px]">{u.email || 'not_configured@bomtempo.com'}</span>
                        </div>
                     </td>
                     <td className="px-5 py-4">
                        <span className="px-2 py-0.5 rounded text-[9px] font-black bg-copper/10 text-copper border border-copper/20 uppercase">
                          {u.role}
                        </span>
                     </td>
                     <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                           <div className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-teal-500' : 'bg-red-500'}`} />
                           <span className={`text-[9px] font-black uppercase ${u.is_active ? 'text-teal-500' : 'text-red-500'}`}>
                              {u.is_active ? 'Sincronizado' : 'Suspenso'}
                           </span>
                        </div>
                     </td>
                     <td className="px-5 py-4">
                        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                           <button
                             onClick={() => {
                               setEditUser(u)
                               setUserForm({ role: u.role, email: u.email, contrato: u.contrato, avatar_icon: u.avatar_icon })
                               setShowUserForm(true)
                             }}
                             className="p-1.5 hover:bg-white/10 rounded-lg text-white/40 hover:text-white transition-all"
                           ><Edit2 size={13} /></button>
                           <button onClick={() => { if(confirm('Excluir usuário?')) deleteUserMut.mutate(u.id); }} className="p-1.5 hover:bg-red-500/10 rounded-lg text-red-500/40 hover:text-red-500 transition-all"><Trash2 size={13} /></button>
                        </div>
                     </td>
                   </tr>
                 ))}
               </tbody>
             </table>
          </div>
        </div>
      )}

      {/* PERFIS TAB */}
      {tab === 'perfis' && (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* List of Roles */}
            <div className="lg:col-span-1 flex flex-col gap-3">
              <Button 
                variant="outline"
                onClick={() => { setEditRole(null); setRoleForm({ modulos: [] }); setShowRoleForm(true); }}
                className="w-full border-dashed border-white/20 text-white/40 hover:text-copper hover:border-copper text-[10px] font-black uppercase tracking-widest h-12"
              >
                <Plus size={16} className="mr-2" /> Novo Perfil Operacional
              </Button>

              {roles.map((r: any) => (
                <div 
                  key={r.id}
                  onClick={() => { setEditRole(r); setRoleForm(r); setShowRoleForm(true); }}
                  className={`p-4 rounded-xl border cursor-pointer transition-all ${editRole?.id === r.id ? 'bg-copper border-copper text-void' : 'bg-white/5 border-white/5 hover:border-copper/40 text-white'}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-black uppercase tracking-widest">{r.nome}</span>
                    <Shield size={12} className="opacity-40" />
                  </div>
                  <p className={`text-[9px] leading-relaxed ${editRole?.id === r.id ? 'text-void/60' : 'text-text-muted'}`}>
                    {r.modulos?.length || 0} módulos visíveis nesta matriz.
                  </p>
                </div>
              ))}
            </div>

            {/* Matrix Management */}
            <div className="lg:col-span-2 flex flex-col gap-4">
              {(showRoleForm || editRole) ? (
                <div style={{ background: GLASS, border: BORDER, borderRadius: 16 }} className="p-6 animate-enter">
                   <div className="flex flex-col gap-4">
                      <div className="grid grid-cols-2 gap-4">
                         <div className="flex flex-col gap-1.5">
                            <label className="text-[9px] font-black text-copper uppercase tracking-widest">Nome do Perfil</label>
                            <input
                              value={roleForm.nome || roleForm.name || ''}
                              onChange={e => setRoleForm(prev => ({...prev, nome: e.target.value, name: e.target.value}))}
                              className="bg-void/50 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:border-copper outline-none transition-all"
                            />
                         </div>
                         <div className="flex flex-col gap-1.5">
                            <label className="text-[9px] font-black text-copper uppercase tracking-widest">Descrição</label>
                            <input
                              value={roleForm.descricao || roleForm.icon || ''}
                              onChange={e => setRoleForm(prev => ({...prev, descricao: e.target.value, icon: e.target.value}))}
                              placeholder="Ex: Engenharia de Campo"
                              className="bg-void/50 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:border-copper outline-none transition-all"
                            />
                         </div>
                         <div className="flex flex-col gap-1.5 col-span-2">
                            <label className="text-[9px] font-black text-copper uppercase tracking-widest">Página Inicial (após login)</label>
                            <select
                              value={roleForm.landing_page || ''}
                              onChange={e => setRoleForm(prev => ({...prev, landing_page: e.target.value}))}
                              className="bg-void/50 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:border-copper outline-none transition-all appearance-none"
                            >
                              <option value="">Padrão (primeira rota permitida)</option>
                              {landingOptions.map((o: any) => (
                                <option key={o.path} value={o.path}>{o.label} — {o.path}</option>
                              ))}
                            </select>
                         </div>
                      </div>

                      <div className="flex flex-col gap-3 mt-4">
                         <label className="text-[10px] font-black text-white uppercase tracking-widest flex items-center gap-2">
                           <Shield size={14} className="text-copper" /> Matriz de Visibilidade de Módulos
                         </label>
                         <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
                            {availableModules.map((m: any) => (
                              <div 
                                key={m.slug}
                                onClick={() => toggleModule(m.slug)}
                                className={`p-3 rounded-lg border flex items-center gap-3 cursor-pointer transition-all ${(roleForm.modulos || roleForm.modules || []).includes(m.slug) ? 'bg-copper/20 border-copper/50 text-white' : 'bg-void/40 border-white/5 text-white/40'}`}
                              >
                                 <div className={`w-3 h-3 rounded border flex items-center justify-center ${(roleForm.modulos || roleForm.modules || []).includes(m.slug) ? 'bg-copper border-copper' : 'border-white/20'}`}>
                                    {(roleForm.modulos || roleForm.modules || []).includes(m.slug) && <div className="w-1.5 h-1.5 bg-void rounded-sm" />}
                                 </div>
                                 <span className="text-[10px] font-bold uppercase tracking-tight">{m.label}</span>
                              </div>
                            ))}
                         </div>
                      </div>

                      <div className="flex items-center gap-2 mt-6 pt-6 border-t border-white/5">
                         <Button 
                            onClick={() => editRole ? updateRoleMut.mutate({ id: editRole.id, body: roleForm }) : createRoleMut.mutate(roleForm)}
                            className="bg-copper text-void font-black text-[10px] uppercase tracking-widest px-8"
                         >
                            Confirmar Matriz
                         </Button>
                         <Button 
                            variant="link"
                            onClick={() => { setShowRoleForm(false); setEditRole(null); }}
                            className="text-text-muted hover:text-white text-[10px] font-bold uppercase tracking-widest"
                         >
                            Cancelar
                         </Button>
                      </div>
                   </div>
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center p-12 opacity-20 border border-dashed border-white/10 rounded-2xl">
                   <Shield size={48} className="mb-4" />
                   <p className="text-xs uppercase tracking-widest font-bold">Selecione ou crie um perfil<br/>para gerenciar a matriz de RBAC</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
