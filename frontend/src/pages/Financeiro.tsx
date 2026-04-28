import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend,
  BarChart, Bar, ReferenceLine,
} from 'recharts'
import {
  Plus, Trash2, Edit2, X, Check, DollarSign, TrendingUp,
  ArrowUpRight, PieChart, Wallet, ShieldCheck, Calculator,
  AlertTriangle, FileText, ChevronDown, ChevronRight, Activity,
  Zap, Info, Clock, Building2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import './Dashboard.css'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'
const AMBER  = '#F59E0B'
const GLASS  = 'rgba(255,255,255,0.04)'
const BORDER = '1px solid rgba(201,139,42,0.15)'

// EVM descriptions for tooltips
const EVM_DESC: Record<string, { full: string; formula: string; good: string }> = {
  CPI: {
    full:    'Cost Performance Index — Índice de Desempenho de Custo',
    formula: 'CPI = EV ÷ AC',
    good:    '≥ 1.0 significa que você está gastando menos do que o valor entregue',
  },
  SPI: {
    full:    'Schedule Performance Index — Índice de Desempenho de Prazo',
    formula: 'SPI = EV ÷ PV',
    good:    '≥ 1.0 significa que o avanço físico está à frente do planejado',
  },
  EAC: {
    full:    'Estimate at Completion — Estimativa de Custo Final',
    formula: 'EAC = BAC ÷ CPI',
    good:    'Projeção do custo total ao fim da obra com base na eficiência atual',
  },
  VAC: {
    full:    'Variance at Completion — Desvio no Término',
    formula: 'VAC = BAC − EAC',
    good:    'Positivo = economia projetada. Negativo = estouro orçamentário projetado',
  },
  TCPI: {
    full:    'To-Complete Performance Index — Eficiência Necessária para Terminar',
    formula: 'TCPI = (BAC − EV) ÷ (BAC − AC)',
    good:    '≤ 1.0 é meta alcançável. > 1.2 indica necessidade de recuperação urgente',
  },
  PV: {
    full:    'Planned Value — Valor Planejado até hoje',
    formula: 'Soma do orçamento das atividades planejadas até a data atual',
    good:    'Baseline do quanto deveria ter sido gasto até hoje',
  },
  EV: {
    full:    'Earned Value — Valor Agregado',
    formula: 'EV = BAC × % Avanço Físico',
    good:    'Quanto do orçamento foi efetivamente "ganho" pelo avanço físico real',
  },
  AC: {
    full:    'Actual Cost — Custo Real',
    formula: 'Soma de todos os lançamentos de execução',
    good:    'Total desembolsado até o momento',
  },
  CV: {
    full:    'Cost Variance — Desvio de Custo',
    formula: 'CV = EV − AC',
    good:    'Positivo = sob controle. Negativo = gastando mais do que entregou',
  },
  BAC: {
    full:    'Budget at Completion — Orçamento Total da Obra',
    formula: 'Soma de todos os valores previstos dos custos',
    good:    'Referência máxima de orçamento aprovado',
  },
}

async function apiFetch(path: string, opts?: RequestInit) {
  const r = await fetch(path, { credentials: 'include', ...opts })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

function fmtBRL(v: any) {
  const n = typeof v === 'number' ? v : parseFloat(String(v || '0').replace(/[^\d.,-]/g, '').replace(',', '.'))
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(isNaN(n) ? 0 : n)
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    previsto:    'bg-white/5 text-white/40 border-white/10',
    em_andamento:'bg-amber-500/10 text-amber-400 border-amber-500/20',
    parcial:     'bg-blue-500/10 text-blue-400 border-blue-500/20',
    concluido:   'bg-teal-500/10 text-teal-400 border-teal-500/20',
    executado:   'bg-teal-500/10 text-teal-400 border-teal-500/20',
    cancelado:   'bg-red-500/10 text-red-400 border-red-500/20',
  }
  const cls = map[status] ?? 'bg-white/5 text-white/40'
  return (
    <span className={`px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-wider border ${cls}`}>
      {status.replace('_', ' ')}
    </span>
  )
}

function EVMTooltip({ metric }: { metric: string }) {
  const [open, setOpen] = useState(false)
  const desc = EVM_DESC[metric]
  if (!desc) return null
  return (
    <div className="relative inline-block">
      <button
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="p-0.5 rounded text-white/20 hover:text-white/60 transition-colors"
      >
        <Info size={11} />
      </button>
      {open && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 bg-[#0d1117] border border-white/10 rounded-xl p-3 shadow-2xl text-left pointer-events-none">
          <div className="text-[10px] font-black text-copper uppercase tracking-widest mb-1">{metric}</div>
          <div className="text-[10px] text-white/70 mb-2 leading-relaxed">{desc.full}</div>
          <div className="font-mono text-[9px] text-teal-400 bg-teal-500/5 border border-teal-500/20 rounded px-2 py-1 mb-2">{desc.formula}</div>
          <div className="text-[9px] text-white/40 leading-relaxed">{desc.good}</div>
        </div>
      )}
    </div>
  )
}

// ── Modal: Novo Custo ──────────────────────────────────────────────────────────
function ModalNovoCusto({ contrato, cats, atividades, onClose, onSaved }: {
  contrato: string; cats: any[]; atividades: any[]; onClose: () => void; onSaved: () => void
}) {
  const [form, setForm] = useState<Record<string, any>>({ status: 'previsto' })
  const qc = useQueryClient()

  const mut = useMutation({
    mutationFn: (b: any) => apiFetch(`/api/financeiro/${contrato}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['financeiro', contrato] }); onSaved(); onClose() },
  })

  const f = (k: string, v: any) => setForm(p => ({ ...p, [k]: v }))
  const catNome = cats.find(c => c.id === form.categoria_id)?.nome ?? ''

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-2xl bg-[#0d1117] border border-white/10 rounded-2xl shadow-2xl">
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-copper/10 border border-copper/20">
              <DollarSign size={16} className="text-copper" />
            </div>
            <span className="text-sm font-black uppercase tracking-widest text-white">Novo Item de Custo</span>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 text-white/40 hover:text-white transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Categoria *</label>
            <select
              className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-copper focus:border-copper/50 outline-none"
              onChange={e => { f('categoria_id', e.target.value); f('categoria_nome', cats.find(c => c.id === e.target.value)?.nome ?? '') }}
            >
              <option value="">Selecionar categoria...</option>
              {cats.map((c: any) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Empresa / Fornecedor</label>
            <Input className="bg-void border-white/10 text-sm h-10 text-white" placeholder="Nome do fornecedor" onChange={e => f('empresa', e.target.value)} />
          </div>

          <div className="md:col-span-2 space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Descrição *</label>
            <Input className="bg-void border-white/10 text-sm h-10 text-white" placeholder="Descreva o item de custo" onChange={e => f('descricao', e.target.value)} />
          </div>

          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Valor Previsto (R$) *</label>
            <Input type="number" min="0" step="0.01" className="bg-void border-white/10 text-sm h-10 text-copper font-mono" placeholder="0,00" onChange={e => f('valor_previsto', parseFloat(e.target.value) || 0)} />
          </div>

          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Data de Referência</label>
            <Input type="date" className="bg-void border-white/10 text-sm h-10 text-white" onChange={e => f('data_custo', e.target.value)} />
          </div>

          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Atividade Vinculada</label>
            <select
              className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white/60 focus:border-copper/50 outline-none"
              onChange={e => f('atividade_id', e.target.value)}
            >
              <option value="">Nenhuma</option>
              {atividades.map((a: any) => (
                <option key={a.id} value={a.id}>{a.atividade ?? a.nome ?? a.id}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Status</label>
            <select
              className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white/60 focus:border-copper/50 outline-none"
              defaultValue="previsto"
              onChange={e => f('status', e.target.value)}
            >
              {['previsto','em_andamento','parcial','concluido','cancelado'].map(s => (
                <option key={s} value={s}>{s.replace('_', ' ')}</option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2 space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Observações</label>
            <Input className="bg-void border-white/10 text-sm h-10 text-white/60" placeholder="Notas opcionais" onChange={e => f('observacoes', e.target.value)} />
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/5">
          <Button onClick={onClose} variant="outline" className="border-white/10 text-white/40 hover:text-white text-xs h-9">Cancelar</Button>
          <Button
            onClick={() => mut.mutate({ ...form, categoria_nome: catNome })}
            disabled={mut.isPending || !form.categoria_id || !form.descricao || !form.valor_previsto}
            className="bg-copper text-void font-black text-xs h-9 px-6 hover:bg-copper/90 disabled:opacity-40"
          >
            {mut.isPending ? 'Salvando...' : 'Criar Item'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ── Modal: Avançar Custo (lançamento) ─────────────────────────────────────────
function ModalAvanco({ custo, contrato, onClose, onSaved }: {
  custo: any; contrato: string; onClose: () => void; onSaved: () => void
}) {
  const [valor, setValor]  = useState('')
  const [data, setData]    = useState(new Date().toISOString().slice(0, 10))
  const [obs, setObs]      = useState('')
  const qc = useQueryClient()

  const { data: lancData } = useQuery({
    queryKey: ['lancamentos', custo.id],
    queryFn: () => apiFetch(`/api/financeiro/${contrato}/lancamentos/${custo.id}`),
    staleTime: 30_000,
  })
  const lancamentos: any[] = lancData?.lancamentos ?? []

  const deleteMut = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/financeiro/lancamentos/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lancamentos', custo.id] })
      qc.invalidateQueries({ queryKey: ['financeiro', contrato] })
    },
  })

  const mut = useMutation({
    mutationFn: (b: any) => apiFetch(`/api/financeiro/${contrato}/lancamentos/${custo.id}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lancamentos', custo.id] })
      qc.invalidateQueries({ queryKey: ['financeiro', contrato] })
      setValor(''); setObs('')
      onSaved()
    },
  })

  const saldo = custo.valor_previsto - custo.valor_executado

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-lg bg-[#0d1117] border border-white/10 rounded-2xl shadow-2xl">
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/5">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <Zap size={14} className="text-teal-400" />
              <span className="text-sm font-black uppercase tracking-widest text-white">Avançar Execução</span>
            </div>
            <p className="text-[10px] text-white/40 ml-5">{custo.descricao}</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 text-white/40 hover:text-white transition-colors"><X size={16} /></button>
        </div>

        {/* Barra de progresso */}
        <div className="px-6 pt-5 pb-4">
          <div className="flex justify-between text-[9px] font-black uppercase tracking-widest mb-2">
            <span className="text-white/40">Executado</span>
            <span className="text-teal-400">{fmtBRL(custo.valor_executado)} / {fmtBRL(custo.valor_previsto)}</span>
          </div>
          <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full bg-teal-500 transition-all duration-700 rounded-full"
              style={{ width: `${Math.min(100, custo.valor_previsto > 0 ? (custo.valor_executado / custo.valor_previsto) * 100 : 0)}%` }}
            />
          </div>
          <div className="text-[9px] text-white/30 mt-1.5">Saldo: {fmtBRL(saldo)}</div>
        </div>

        {/* Form lançamento */}
        <div className="px-6 pb-4 grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Valor Executado (R$) *</label>
            <Input
              type="number" min="0.01" step="0.01"
              value={valor}
              className="bg-void border-white/10 text-sm h-10 text-teal-400 font-mono"
              placeholder="0,00"
              onChange={e => setValor(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Data do Avanço</label>
            <Input type="date" value={data} className="bg-void border-white/10 text-sm h-10 text-white" onChange={e => setData(e.target.value)} />
          </div>
          <div className="col-span-2 space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Observação</label>
            <Input value={obs} className="bg-void border-white/10 text-sm h-10 text-white/60" placeholder="Opcional" onChange={e => setObs(e.target.value)} />
          </div>
        </div>

        <div className="flex justify-end gap-3 px-6 pb-4">
          <Button onClick={onClose} variant="outline" className="border-white/10 text-white/40 text-xs h-9">Cancelar</Button>
          <Button
            onClick={() => mut.mutate({ valor: parseFloat(valor), data, observacoes: obs })}
            disabled={mut.isPending || !valor || parseFloat(valor) <= 0}
            className="bg-teal-600 hover:bg-teal-500 text-white font-black text-xs h-9 px-6 disabled:opacity-40"
          >
            {mut.isPending ? 'Registrando...' : 'Registrar Avanço'}
          </Button>
        </div>

        {/* Histórico de lançamentos */}
        {lancamentos.length > 0 && (
          <div className="border-t border-white/5 px-6 py-4">
            <div className="text-[9px] font-black uppercase tracking-widest text-white/30 mb-3 flex items-center gap-2">
              <Clock size={10} /> Histórico de Avanços
            </div>
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1 custom-scroll">
              {lancamentos.map((lc: any) => (
                <div key={lc.id} className="flex items-center justify-between bg-white/[0.02] border border-white/5 rounded-lg px-3 py-2 group">
                  <div>
                    <span className="text-teal-400 font-mono text-xs font-black">{lc.valor_fmt}</span>
                    {lc.observacoes && <span className="text-white/30 text-[10px] ml-2">{lc.observacoes}</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] font-mono text-white/30">{lc.data}</span>
                    <button
                      onClick={() => deleteMut.mutate(lc.id)}
                      className="p-1 rounded hover:bg-red-500/20 text-red-400/50 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Modal: Editar custo ────────────────────────────────────────────────────────
function ModalEditar({ custo, cats, contrato, onClose }: {
  custo: any; cats: any[]; contrato: string; onClose: () => void
}) {
  const [form, setForm] = useState({
    categoria_id:   custo.categoria_id,
    categoria_nome: custo.categoria_nome,
    empresa:        custo.empresa,
    descricao:      custo.descricao,
    valor_previsto: custo.valor_previsto,
    data_custo:     custo.data_custo,
    observacoes:    custo.observacoes,
    status:         custo.status,
  })
  const qc = useQueryClient()
  const f = (k: string, v: any) => setForm(p => ({ ...p, [k]: v }))

  const mut = useMutation({
    mutationFn: (b: any) => apiFetch(`/api/financeiro/${custo.id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['financeiro', contrato] }); onClose() },
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-xl bg-[#0d1117] border border-white/10 rounded-2xl shadow-2xl">
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/5">
          <div className="flex items-center gap-3">
            <Edit2 size={14} className="text-copper" />
            <span className="text-sm font-black uppercase tracking-widest text-white">Editar Item</span>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 text-white/40 hover:text-white transition-colors"><X size={16} /></button>
        </div>
        <div className="p-6 grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Categoria</label>
            <select
              className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-copper outline-none"
              value={form.categoria_id}
              onChange={e => { f('categoria_id', e.target.value); f('categoria_nome', cats.find(c => c.id === e.target.value)?.nome ?? '') }}
            >
              {cats.map((c: any) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Empresa</label>
            <Input className="bg-void border-white/10 text-sm h-10 text-white" value={form.empresa} onChange={e => f('empresa', e.target.value)} />
          </div>
          <div className="col-span-2 space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Descrição</label>
            <Input className="bg-void border-white/10 text-sm h-10 text-white" value={form.descricao} onChange={e => f('descricao', e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Valor Previsto (R$)</label>
            <Input type="number" className="bg-void border-white/10 text-sm h-10 text-copper font-mono" value={form.valor_previsto} onChange={e => f('valor_previsto', parseFloat(e.target.value))} />
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Data de Referência</label>
            <Input type="date" className="bg-void border-white/10 text-sm h-10 text-white" value={form.data_custo} onChange={e => f('data_custo', e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Status</label>
            <select className="w-full bg-void border border-white/10 rounded-lg h-10 px-3 text-sm text-white/60 outline-none" value={form.status} onChange={e => f('status', e.target.value)}>
              {['previsto','em_andamento','parcial','concluido','cancelado'].map(s => <option key={s} value={s}>{s.replace('_',' ')}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-[9px] font-black uppercase tracking-wider text-white/40">Observações</label>
            <Input className="bg-void border-white/10 text-sm h-10 text-white/60" value={form.observacoes} onChange={e => f('observacoes', e.target.value)} />
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-white/5">
          <Button onClick={onClose} variant="outline" className="border-white/10 text-white/40 text-xs h-9">Cancelar</Button>
          <Button
            onClick={() => mut.mutate({ ...form, data: form.data_custo })}
            disabled={mut.isPending}
            className="bg-copper text-void font-black text-xs h-9 px-6 hover:bg-copper/90"
          >
            {mut.isPending ? 'Salvando...' : 'Salvar Alterações'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ── Grupo de categoria ─────────────────────────────────────────────────────────
function CategoriaGrupo({ nome, itens, contrato, cats, onAvanco, onEdit, onDelete }: {
  nome: string; itens: any[]; contrato: string; cats: any[];
  onAvanco: (c: any) => void; onEdit: (c: any) => void; onDelete: (id: string) => void
}) {
  const [open, setOpen] = useState(true)
  const totalPrev = itens.reduce((s, r) => s + r.valor_previsto, 0)
  const totalExec = itens.reduce((s, r) => s + r.valor_executado, 0)
  const pct = totalPrev > 0 ? Math.min(100, (totalExec / totalPrev) * 100) : 0

  return (
    <div className="rounded-2xl border border-white/5 overflow-hidden">
      {/* Header do grupo */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 bg-white/[0.02] hover:bg-white/[0.04] transition-colors"
      >
        <div className="flex items-center gap-3">
          {open ? <ChevronDown size={14} className="text-copper" /> : <ChevronRight size={14} className="text-white/30" />}
          <span className="text-[10px] font-black uppercase tracking-widest text-white">{nome}</span>
          <span className="text-[9px] text-white/30 font-mono">{itens.length} iten{itens.length !== 1 ? 's' : ''}</span>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-right hidden sm:block">
            <div className="text-[9px] text-white/30 uppercase tracking-widest">Previsto</div>
            <div className="text-xs font-mono font-black text-copper">{fmtBRL(totalPrev)}</div>
          </div>
          <div className="text-right hidden sm:block">
            <div className="text-[9px] text-white/30 uppercase tracking-widest">Executado</div>
            <div className="text-xs font-mono font-black text-teal-400">{fmtBRL(totalExec)}</div>
          </div>
          <div className="flex items-center gap-2 min-w-[80px]">
            <div className="h-1.5 flex-1 bg-white/5 rounded-full overflow-hidden">
              <div className="h-full bg-teal-500 rounded-full transition-all duration-700" style={{ width: `${pct}%` }} />
            </div>
            <span className="text-[9px] font-mono text-white/40 w-8 text-right">{pct.toFixed(0)}%</span>
          </div>
        </div>
      </button>

      {open && (
        <div className="divide-y divide-white/[0.02]">
          {itens.map(r => {
            const pctItem = r.valor_previsto > 0 ? Math.min(100, (r.valor_executado / r.valor_previsto) * 100) : 0
            return (
              <div key={r.id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-white/[0.015] transition-colors group">
                {/* Descrição + empresa */}
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-bold text-white truncate">{r.descricao}</div>
                  {r.empresa && (
                    <div className="flex items-center gap-1 mt-0.5">
                      <Building2 size={9} className="text-white/20" />
                      <span className="text-[9px] text-white/30">{r.empresa}</span>
                    </div>
                  )}
                </div>

                {/* Progresso */}
                <div className="flex items-center gap-2 w-28 shrink-0 hidden md:flex">
                  <div className="h-1 flex-1 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-teal-500 rounded-full" style={{ width: `${pctItem}%` }} />
                  </div>
                  <span className="text-[9px] font-mono text-white/30 w-7 text-right">{pctItem.toFixed(0)}%</span>
                </div>

                {/* Valores */}
                <div className="text-right shrink-0 hidden sm:block">
                  <div className="text-[9px] text-white/30">Prev</div>
                  <div className="text-xs font-mono text-copper">{r.valor_previsto_fmt}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-[9px] text-white/30">Exec</div>
                  <div className="text-xs font-mono text-teal-400">{r.valor_executado_fmt}</div>
                </div>

                {/* Status */}
                <div className="shrink-0 hidden lg:block">
                  <StatusBadge status={r.status} />
                </div>

                {/* Data */}
                <div className="text-[9px] font-mono text-white/20 shrink-0 hidden xl:block w-20 text-right">
                  {r.data_custo}
                </div>

                {/* Ações */}
                <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => onAvanco(r)}
                    className="p-1.5 rounded-lg hover:bg-teal-500/20 text-teal-400/50 hover:text-teal-400 transition-colors"
                    title="Avançar execução"
                  >
                    <Zap size={13} />
                  </button>
                  <button
                    onClick={() => onEdit(r)}
                    className="p-1.5 rounded-lg hover:bg-copper/20 text-copper/50 hover:text-copper transition-colors"
                    title="Editar"
                  >
                    <Edit2 size={13} />
                  </button>
                  <button
                    onClick={() => onDelete(r.id)}
                    className="p-1.5 rounded-lg hover:bg-red-500/20 text-red-400/40 hover:text-red-400 transition-colors"
                    title="Excluir"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── EVM Card ──────────────────────────────────────────────────────────────────
function EVMCard({ metric, value, fmt, good }: { metric: string; value: number; fmt: string; good: boolean }) {
  return (
    <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        <span className="text-[9px] font-black uppercase tracking-widest text-white/40">{metric}</span>
        <EVMTooltip metric={metric} />
      </div>
      <div className="text-lg font-black font-mono" style={{ color: good ? TEAL : RED }}>{fmt}</div>
      <div className="flex items-center gap-1 text-[9px]" style={{ color: good ? TEAL : RED }}>
        {good ? <TrendingUp size={9} /> : <AlertTriangle size={9} />}
        {good ? 'OK' : 'Atenção'}
      </div>
    </div>
  )
}

// ── Tooltip S-Curve ───────────────────────────────────────────────────────────
function SCurveTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-[#0d1117] border border-white/10 rounded-xl p-3 text-[10px] shadow-xl">
      <div className="font-mono text-white/40 mb-2">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
            <span className="text-white/60">{p.name}</span>
          </div>
          <span className="font-mono font-black" style={{ color: p.color }}>{fmtBRL(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Financeiro() {
  const [searchParams, setSearchParams] = useSearchParams()
  const contrato = searchParams.get('contrato') ?? ''
  const qc = useQueryClient()

  const [activeTab, setActiveTab]     = useState<'cockpit' | 'scurve' | 'bycat' | 'evm'>('cockpit')
  const [modalNovo, setModalNovo]     = useState(false)
  const [avancoItem, setAvancoItem]   = useState<any>(null)
  const [editItem, setEditItem]       = useState<any>(null)
  const [filterCat, setFilterCat]     = useState('')
  const [filterStatus, setFilterStatus] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['financeiro', contrato],
    queryFn:  () => contrato ? apiFetch(`/api/financeiro/${contrato}`) : apiFetch('/api/financeiro'),
    staleTime: 2 * 60_000,
    refetchOnWindowFocus: true,
  })

  const { data: contratosList } = useQuery({
    queryKey: ['hub-contratos'],
    queryFn:  () => apiFetch('/api/hub/contratos'),
    staleTime: Infinity,
  })

  const { data: ativData } = useQuery({
    queryKey: ['hub-atividades', contrato],
    queryFn:  () => contrato ? apiFetch(`/hub/cronograma?contrato=${encodeURIComponent(contrato)}`) : Promise.resolve(null),
    staleTime: Infinity,
    enabled: !!contrato,
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/financeiro/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['financeiro', contrato] }),
  })

  const contratos: any[] = contratosList?.contratos ?? []
  const kpis    = data?.kpis ?? {}
  const scurve  = data?.scurve ?? []
  const bycat   = data?.by_categoria ?? []
  const evm     = data?.evm ?? {}
  const cats: any[] = data?.categorias ?? []
  const atividades: any[] = ativData?.atividades ?? []

  const allCustos: any[] = data?.custos ?? []
  const custosFiltrados = useMemo(() => {
    return allCustos.filter(r => {
      if (filterCat && r.categoria_nome !== filterCat) return false
      if (filterStatus && r.status !== filterStatus) return false
      return true
    })
  }, [allCustos, filterCat, filterStatus])

  // Agrupar por categoria
  const grupos = useMemo(() => {
    const map: Record<string, any[]> = {}
    for (const r of custosFiltrados) {
      const cat = r.categoria_nome || '— Sem Categoria'
      if (!map[cat]) map[cat] = []
      map[cat].push(r)
    }
    return map
  }, [custosFiltrados])

  const totalPrev = allCustos.reduce((s, r) => s + r.valor_previsto, 0)
  const totalExec = allCustos.reduce((s, r) => s + r.valor_executado, 0)
  const burnPct   = totalPrev > 0 ? Math.min(100, (totalExec / totalPrev) * 100) : 0

  return (
    <div className="flex flex-col gap-6 animate-enter">
      {/* HEADER */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30">
            <DollarSign size={24} className="text-copper" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-white uppercase tracking-tight">Inteligência Financeira</h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">Gestão de Custos & EVM</p>
          </div>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
          <button
            onClick={() => setSearchParams({})}
            className={`px-4 py-2 rounded-lg text-xs font-black uppercase tracking-widest transition-all whitespace-nowrap border ${
              !contrato
                ? 'bg-copper text-void border-copper shadow-[0_0_20px_rgba(201,139,42,0.2)]'
                : 'bg-white/5 text-text-muted border-white/5 hover:border-copper/40 hover:text-white'
            }`}
          >Todos</button>
          {contratos.map((c: any) => (
            <button key={c.contrato}
              onClick={() => setSearchParams({ contrato: c.contrato })}
              className={`px-4 py-2 rounded-lg text-xs font-black uppercase tracking-widest transition-all whitespace-nowrap border ${
                contrato === c.contrato
                  ? 'bg-copper text-void border-copper shadow-[0_0_20px_rgba(201,139,42,0.2)]'
                  : 'bg-white/5 text-text-muted border-white/5 hover:border-copper/40 hover:text-white'
              }`}
            >{c.contrato}</button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 bg-white/[0.03] rounded-2xl border border-white/5 animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="glass-panel p-5 border-white/5">
              <div className="flex items-center gap-2 mb-3">
                <div className="p-1.5 rounded-lg bg-white/5"><Wallet size={14} className="text-white/60" /></div>
                <span className="text-[9px] font-black uppercase tracking-widest text-white/40">Total Previsto</span>
              </div>
              <div className="text-xl font-black font-mono text-white">{fmtBRL(totalPrev)}</div>
              <div className="text-[9px] text-white/20 mt-1">{allCustos.length} itens de custo</div>
            </div>
            <div className="glass-panel p-5 border-white/5">
              <div className="flex items-center gap-2 mb-3">
                <div className="p-1.5 rounded-lg bg-teal-500/10"><TrendingUp size={14} className="text-teal-400" /></div>
                <span className="text-[9px] font-black uppercase tracking-widest text-white/40">Executado</span>
              </div>
              <div className="text-xl font-black font-mono text-teal-400">{fmtBRL(totalExec)}</div>
              <div className="text-[9px] text-teal-400/40 mt-1">{kpis.concluidos ?? 0} concluídos</div>
            </div>
            <div className="glass-panel p-5 border-white/5">
              <div className="flex items-center gap-2 mb-3">
                <div className="p-1.5 rounded-lg bg-copper/10"><ShieldCheck size={14} className="text-copper" /></div>
                <span className="text-[9px] font-black uppercase tracking-widest text-white/40">Saldo</span>
              </div>
              <div className="text-xl font-black font-mono text-copper">{fmtBRL(totalPrev - totalExec)}</div>
              <div className="text-[9px] text-white/20 mt-1">Remanescente</div>
            </div>
            <div className="glass-panel p-5 border-white/5">
              <div className="flex items-center gap-2 mb-3">
                <div className="p-1.5 rounded-lg bg-amber-500/10"><Activity size={14} className="text-amber-400" /></div>
                <span className="text-[9px] font-black uppercase tracking-widest text-white/40">Burn Rate</span>
              </div>
              <div className="text-xl font-black font-mono" style={{ color: burnPct > 90 ? RED : burnPct > 70 ? AMBER : TEAL }}>
                {burnPct.toFixed(1)}%
              </div>
              <div className="h-1.5 w-full bg-white/5 rounded-full mt-2 overflow-hidden">
                <div className="h-full rounded-full transition-all duration-700" style={{
                  width: `${burnPct}%`,
                  background: burnPct > 90 ? RED : burnPct > 70 ? AMBER : TEAL,
                }} />
              </div>
            </div>
          </div>

          {/* TABS */}
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-1 bg-white/[0.02] border border-white/5 p-1 rounded-xl">
              {[
                { id: 'cockpit', label: 'Lançamentos', icon: FileText },
                { id: 'scurve',  label: 'Curva-S',     icon: TrendingUp },
                { id: 'bycat',   label: 'Por Categoria', icon: PieChart },
                { id: 'evm',     label: 'EVM',          icon: Calculator },
              ].map(t => (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id as any)}
                  className={`px-4 py-2 rounded-lg flex items-center gap-2 text-[10px] font-black uppercase tracking-widest transition-all ${
                    activeTab === t.id ? 'bg-copper text-void shadow-lg' : 'text-text-muted hover:text-white'
                  }`}
                >
                  <t.icon size={13} /> {t.label}
                </button>
              ))}
            </div>
            {activeTab === 'cockpit' && contrato && (
              <Button
                onClick={() => setModalNovo(true)}
                className="bg-void border border-copper/40 hover:border-copper text-copper font-black text-[10px] uppercase tracking-widest h-9 px-4"
              >
                <Plus size={14} className="mr-2" /> Novo Item
              </Button>
            )}
          </div>

          {/* ── COCKPIT ─────────────────────────────────────────────────── */}
          {activeTab === 'cockpit' && (
            <div className="flex flex-col gap-3 animate-enter">
              {/* Filtros */}
              {(cats.length > 0 || allCustos.length > 0) && (
                <div className="flex items-center gap-3 flex-wrap">
                  <select
                    className="bg-void border border-white/10 rounded-lg h-8 px-3 text-[10px] text-white/60 outline-none"
                    value={filterCat}
                    onChange={e => setFilterCat(e.target.value)}
                  >
                    <option value="">Todas categorias</option>
                    {cats.map((c: any) => <option key={c.id} value={c.nome}>{c.nome}</option>)}
                  </select>
                  <select
                    className="bg-void border border-white/10 rounded-lg h-8 px-3 text-[10px] text-white/60 outline-none"
                    value={filterStatus}
                    onChange={e => setFilterStatus(e.target.value)}
                  >
                    <option value="">Todos status</option>
                    {['previsto','em_andamento','parcial','concluido','cancelado'].map(s => (
                      <option key={s} value={s}>{s.replace('_',' ')}</option>
                    ))}
                  </select>
                  {(filterCat || filterStatus) && (
                    <button
                      onClick={() => { setFilterCat(''); setFilterStatus('') }}
                      className="text-[9px] text-white/30 hover:text-white flex items-center gap-1 transition-colors"
                    >
                      <X size={10} /> Limpar filtros
                    </button>
                  )}
                  <span className="text-[9px] text-white/20 ml-auto">{custosFiltrados.length} de {allCustos.length} itens</span>
                </div>
              )}

              {Object.keys(grupos).length === 0 ? (
                <div className="glass-panel p-20 text-center border-white/5">
                  <DollarSign size={32} className="text-white/10 mx-auto mb-4" />
                  <p className="text-white/20 text-sm font-bold">Nenhum item de custo cadastrado</p>
                  {contrato && (
                    <button onClick={() => setModalNovo(true)} className="mt-4 text-copper text-[10px] font-black uppercase tracking-widest hover:underline">
                      + Criar primeiro item
                    </button>
                  )}
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {Object.entries(grupos).map(([cat, itens]) => (
                    <CategoriaGrupo
                      key={cat}
                      nome={cat}
                      itens={itens}
                      contrato={contrato}
                      cats={cats}
                      onAvanco={setAvancoItem}
                      onEdit={setEditItem}
                      onDelete={(id) => {
                        if (confirm('Excluir este item e todos os seus lançamentos?')) deleteMut.mutate(id)
                      }}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── CURVA-S ─────────────────────────────────────────────────── */}
          {activeTab === 'scurve' && (
            <div className="glass-panel p-8 border-white/5 animate-enter">
              <div className="mb-8">
                <h3 className="text-xs font-black uppercase tracking-widest text-copper mb-1">Curva-S Acumulada — Linha do Tempo</h3>
                <p className="text-[10px] text-text-muted">Evolução diária acumulada: Baseline planejada vs. execução real</p>
              </div>
              {scurve.length === 0 ? (
                <div className="h-64 flex items-center justify-center text-white/20 text-sm">Sem dados temporais suficientes</div>
              ) : (
                <div className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={scurve} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                      <defs>
                        <linearGradient id="fp" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={COPPER} stopOpacity={0.12} />
                          <stop offset="95%" stopColor={COPPER} stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="fe" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={TEAL} stopOpacity={0.15} />
                          <stop offset="95%" stopColor={TEAL} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                      <XAxis
                        dataKey="data"
                        axisLine={false} tickLine={false}
                        tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9, fontWeight: 700 }}
                        interval={Math.max(0, Math.floor(scurve.length / 8) - 1)}
                        dy={10}
                      />
                      <YAxis
                        axisLine={false} tickLine={false}
                        tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9, fontWeight: 700 }}
                        tickFormatter={v => `R$${(v / 1000).toFixed(0)}k`}
                      />
                      <Tooltip content={<SCurveTip />} />
                      <Legend
                        formatter={(v) => <span className="text-[9px] font-black uppercase tracking-widest text-white/40">{v}</span>}
                        iconType="circle" iconSize={8}
                      />
                      <Area type="monotone" dataKey="previsto_acum"  stroke={COPPER} strokeWidth={2} fill="url(#fp)" name="Baseline Planejada" dot={false} />
                      <Area type="monotone" dataKey="executado_acum" stroke={TEAL}   strokeWidth={2.5} fill="url(#fe)" name="Execução Real" dot={{ r: 3, fill: TEAL, strokeWidth: 0 }} activeDot={{ r: 5 }} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}

          {/* ── POR CATEGORIA ───────────────────────────────────────────── */}
          {activeTab === 'bycat' && (
            <div className="flex flex-col gap-4 animate-enter">
              <div className="glass-panel p-8 border-white/5">
                <div className="mb-8">
                  <h3 className="text-xs font-black uppercase tracking-widest text-copper mb-1">Distribuição por Categoria</h3>
                  <p className="text-[10px] text-text-muted">Previsto vs. executado agrupado por categoria de custo</p>
                </div>
                {bycat.length === 0 ? (
                  <div className="h-48 flex items-center justify-center text-white/20 text-sm">Sem dados de categoria</div>
                ) : (
                  <div className="h-[320px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={bycat} layout="vertical" margin={{ left: 20, right: 30 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(255,255,255,0.03)" />
                        <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9 }} tickFormatter={v => `R$${(v/1000).toFixed(0)}k`} />
                        <YAxis type="category" dataKey="categoria" width={130} axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 10, fontWeight: 700 }} />
                        <Tooltip
                          contentStyle={{ background: '#0d1117', border: BORDER, borderRadius: 12 }}
                          formatter={(v: any) => fmtBRL(v)}
                        />
                        <Legend formatter={(v) => <span className="text-[9px] font-black uppercase tracking-widest text-white/40">{v}</span>} iconType="circle" iconSize={8} />
                        <Bar dataKey="previsto"  fill={COPPER} radius={[0, 4, 4, 0]} name="Previsto"  barSize={14} />
                        <Bar dataKey="executado" fill={TEAL}   radius={[0, 4, 4, 0]} name="Executado" barSize={14} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>

              {/* Tabela por categoria */}
              <div className="glass-panel border-white/5 overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="bg-white/[0.02] border-b border-white/5">
                      <th className="text-left px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">Categoria</th>
                      <th className="text-right px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">Previsto</th>
                      <th className="text-right px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">Executado</th>
                      <th className="text-right px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">%</th>
                      <th className="px-5 py-3 text-[9px] font-black uppercase tracking-widest text-white/30">Progresso</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.02]">
                    {bycat.map((r: any) => {
                      const pct = r.previsto > 0 ? Math.min(100, (r.executado / r.previsto) * 100) : 0
                      return (
                        <tr key={r.categoria} className="hover:bg-white/[0.015] transition-colors">
                          <td className="px-5 py-3 text-xs font-bold text-white">{r.categoria}</td>
                          <td className="px-5 py-3 text-right font-mono text-xs text-copper">{fmtBRL(r.previsto)}</td>
                          <td className="px-5 py-3 text-right font-mono text-xs text-teal-400">{fmtBRL(r.executado)}</td>
                          <td className="px-5 py-3 text-right text-[10px] font-mono text-white/40">{pct.toFixed(1)}%</td>
                          <td className="px-5 py-3 w-32">
                            <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                              <div className="h-full bg-teal-500 rounded-full" style={{ width: `${pct}%` }} />
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── EVM ─────────────────────────────────────────────────────── */}
          {activeTab === 'evm' && (
            <div className="flex flex-col gap-6 animate-enter">
              {Object.keys(evm).length === 0 ? (
                <div className="glass-panel p-20 text-center border-white/5">
                  <Calculator size={32} className="text-white/10 mx-auto mb-4" />
                  <p className="text-white/20 text-sm font-bold">Sem dados suficientes para calcular EVM</p>
                  <p className="text-white/10 text-xs mt-2">Adicione itens de custo com valores previstos</p>
                </div>
              ) : (
                <>
                  {/* Índices principais */}
                  <div>
                    <div className="text-[9px] font-black uppercase tracking-widest text-white/30 mb-3">Índices de Desempenho</div>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                      <EVMCard metric="CPI"  value={evm.CPI}  fmt={String(evm.CPI)}   good={evm.CPI >= 1} />
                      <EVMCard metric="SPI"  value={evm.SPI}  fmt={String(evm.SPI)}   good={evm.SPI >= 1} />
                      <EVMCard metric="TCPI" value={evm.TCPI} fmt={String(evm.TCPI)}  good={evm.TCPI <= 1} />
                      <EVMCard metric="CV"   value={evm.CV}   fmt={(evm.CV >= 0 ? '+' : '-') + evm.CV_fmt} good={evm.CV >= 0} />
                      <EVMCard metric="SV"   value={evm.SV}   fmt={(evm.SV >= 0 ? '+' : '-') + evm.SV_fmt} good={evm.SV >= 0} />
                    </div>
                  </div>

                  {/* Valores monetários */}
                  <div>
                    <div className="text-[9px] font-black uppercase tracking-widest text-white/30 mb-3">Valores de Referência</div>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                      {([
                        { metric: 'BAC', fmt: evm.BAC_fmt, good: true },
                        { metric: 'EAC', fmt: evm.EAC_fmt, good: !evm.is_overrun },
                        { metric: 'VAC', fmt: (evm.is_overrun ? '-' : '+') + evm.VAC_fmt, good: !evm.is_overrun },
                        { metric: 'PV',  fmt: evm.PV_fmt,  good: true },
                        { metric: 'EV',  fmt: evm.EV_fmt,  good: true },
                        { metric: 'AC',  fmt: evm.AC_fmt,  good: true },
                      ] as any[]).map(x => (
                        <div key={x.metric} className="bg-white/[0.02] border border-white/5 rounded-xl p-4">
                          <div className="flex items-center gap-1.5 mb-2">
                            <span className="text-[9px] font-black uppercase tracking-widest text-white/40">{x.metric}</span>
                            <EVMTooltip metric={x.metric} />
                          </div>
                          <div className="text-base font-black font-mono" style={{ color: x.good ? '#FFF' : RED }}>{x.fmt}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Progresso físico vs financeiro */}
                  <div className="glass-panel p-6 border-white/5">
                    <h3 className="text-[10px] font-black uppercase tracking-widest text-white/40 mb-6 flex items-center gap-2">
                      <Activity size={12} className="text-copper" /> Avanço Físico vs. Financeiro
                    </h3>
                    <div className="space-y-6">
                      <div>
                        <div className="flex justify-between text-[9px] font-black uppercase tracking-widest mb-2">
                          <span className="text-copper">Progresso Físico</span>
                          <span className="text-white">{evm.physical_pct}%</span>
                        </div>
                        <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                          <div className="h-full bg-copper rounded-full transition-all duration-1000" style={{ width: `${evm.physical_pct}%` }} />
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between text-[9px] font-black uppercase tracking-widest mb-2">
                          <span className="text-teal-400">Progresso Financeiro</span>
                          <span className="text-white">{evm.cost_pct}%</span>
                        </div>
                        <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                          <div className="h-full bg-teal-500 rounded-full transition-all duration-1000" style={{ width: `${evm.cost_pct}%` }} />
                        </div>
                      </div>
                    </div>

                    {evm.is_overrun && (
                      <div className="mt-6 flex items-start gap-3 bg-red-500/5 border border-red-500/20 rounded-xl p-4">
                        <AlertTriangle size={16} className="text-red-400 shrink-0 mt-0.5" />
                        <div>
                          <div className="text-xs font-black text-red-400 mb-1">Alerta de Estouro Orçamentário</div>
                          <div className="text-[10px] text-red-400/60">Projeção indica custo final {evm.VAC_fmt} acima do BAC. Revise a eficiência de execução.</div>
                        </div>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </>
      )}

      {/* Modals */}
      {modalNovo && (
        <ModalNovoCusto
          contrato={contrato}
          cats={cats}
          atividades={atividades}
          onClose={() => setModalNovo(false)}
          onSaved={() => {}}
        />
      )}
      {avancoItem && (
        <ModalAvanco
          custo={avancoItem}
          contrato={contrato}
          onClose={() => setAvancoItem(null)}
          onSaved={() => {}}
        />
      )}
      {editItem && (
        <ModalEditar
          custo={editItem}
          cats={cats}
          contrato={contrato}
          onClose={() => setEditItem(null)}
        />
      )}
    </div>
  )
}
