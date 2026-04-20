import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ScatterChart, Scatter } from 'recharts'
import { BarChart3 } from 'lucide-react'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

async function api(path: string) {
  const r = await fetch(path, { credentials:'include' })
  if (!r.ok) throw new Error()
  return r.json()
}

export default function Analytics() {
  const { data, isLoading } = useQuery({
    queryKey:['analytics-kpis'],
    queryFn:()=>api('/api/dashboard/kpis'),
    staleTime:60_000,
  })

  if (isLoading) return (
    <div className="flex flex-col gap-3 animate-pulse">
      {[...Array(4)].map((_,i) => <div key={i} style={{ height:120, background:GLASS, borderRadius:12 }} />)}
    </div>
  )

  const kpis = data ?? {}

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-2">
        <BarChart3 size={20} style={{ color:COPPER }} />
        <h1 className="font-display text-xl font-bold text-text-primary">Analytics</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {kpis.faturamento_por_cliente?.length > 0 && (
          <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="p-5">
            <h2 className="text-sm text-text-muted uppercase mb-4">Faturamento por Cliente</h2>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={kpis.faturamento_por_cliente} layout="vertical">
                <XAxis type="number" tick={{ fill:'#888', fontSize:10 }} tickFormatter={v=>`R$${(v/1000).toFixed(0)}k`} />
                <YAxis type="category" dataKey="name" tick={{ fill:'#aaa', fontSize:11 }} width={100} />
                <Tooltip contentStyle={{ background:'#0d1117', border:`1px solid ${COPPER}`, borderRadius:8 }}
                  formatter={(v:number) => [`R$ ${v.toLocaleString('pt-BR',{minimumFractionDigits:2})}`]} />
                <Bar dataKey="value" fill={COPPER} radius={[0,4,4,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {kpis.status_contratos_dist?.length > 0 && (
          <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="p-5">
            <h2 className="text-sm text-text-muted uppercase mb-4">Distribuição de Status</h2>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={kpis.status_contratos_dist}>
                <XAxis dataKey="name" tick={{ fill:'#888', fontSize:11 }} />
                <YAxis tick={{ fill:'#888', fontSize:10 }} />
                <Tooltip contentStyle={{ background:'#0d1117', border:`1px solid ${COPPER}`, borderRadius:8 }} />
                <Bar dataKey="value" fill={TEAL} radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {kpis.contratos_progress?.length > 0 && (
          <div style={{ background:GLASS, border:BORDER, borderRadius:12 }} className="p-5 lg:col-span-2">
            <h2 className="text-sm text-text-muted uppercase mb-4">Progresso dos Contratos</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={kpis.contratos_progress} layout="vertical">
                <XAxis type="number" domain={[0,100]} tick={{ fill:'#888', fontSize:10 }} tickFormatter={v=>`${v}%`} />
                <YAxis type="category" dataKey="contrato" tick={{ fill:'#aaa', fontSize:11 }} width={120} />
                <Tooltip contentStyle={{ background:'#0d1117', border:`1px solid ${COPPER}`, borderRadius:8 }}
                  formatter={(v:number) => [`${v}%`, 'Progresso']} />
                <Bar dataKey="pct" fill={COPPER} radius={[0,4,4,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
