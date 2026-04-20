/**
 * AppMobile — shell mobile-first para obra em campo.
 * 3 abas: RDO rápido, Reembolso, Chat IA voz.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ClipboardList, Mic, Receipt, ChevronRight, Map, Camera } from 'lucide-react'

const TABS = [
  { id: 'rdo',       label: 'RDO',       Icon: ClipboardList },
  { id: 'chat',      label: 'Chat IA',   Icon: Mic           },
  { id: 'reembolso', label: 'Reembolso', Icon: Receipt       },
]

function RDOQuickCard({ onNavigate }: { onNavigate: () => void }) {
  return (
    <div className="space-y-3 p-4">
      <h2 className="text-lg font-semibold text-text-primary">Relatório Diário</h2>

      <button
        onClick={onNavigate}
        className="w-full flex items-center justify-between rounded-xl bg-glass border border-glass-border p-4 hover:bg-white/5 transition"
      >
        <div className="flex items-center gap-3">
          <ClipboardList size={20} className="text-copper" />
          <div className="text-left">
            <div className="text-sm font-medium text-text-primary">Preencher RDO</div>
            <div className="text-xs text-text-muted">Atividades, fotos, assinatura</div>
          </div>
        </div>
        <ChevronRight size={16} className="text-text-muted" />
      </button>

      <button className="w-full flex items-center justify-between rounded-xl bg-glass border border-glass-border p-4 hover:bg-white/5 transition">
        <div className="flex items-center gap-3">
          <Camera size={20} className="text-copper" />
          <div className="text-left">
            <div className="text-sm font-medium text-text-primary">Adicionar Evidência</div>
            <div className="text-xs text-text-muted">Foto com GPS e marca d'água</div>
          </div>
        </div>
        <ChevronRight size={16} className="text-text-muted" />
      </button>

      <button className="w-full flex items-center justify-between rounded-xl bg-glass border border-glass-border p-4 hover:bg-white/5 transition">
        <div className="flex items-center gap-3">
          <Map size={20} className="text-copper" />
          <div className="text-left">
            <div className="text-sm font-medium text-text-primary">Localização Atual</div>
            <div className="text-xs text-text-muted">Registrar presença no canteiro</div>
          </div>
        </div>
        <ChevronRight size={16} className="text-text-muted" />
      </button>
    </div>
  )
}

function ReembolsoQuickCard({ onNavigate }: { onNavigate: () => void }) {
  return (
    <div className="space-y-3 p-4">
      <h2 className="text-lg font-semibold text-text-primary">Reembolso de Campo</h2>

      <button
        onClick={onNavigate}
        className="w-full flex items-center justify-between rounded-xl bg-glass border border-glass-border p-4 hover:bg-white/5 transition"
      >
        <div className="flex items-center gap-3">
          <Receipt size={20} className="text-copper" />
          <div className="text-left">
            <div className="text-sm font-medium text-text-primary">Nova Solicitação</div>
            <div className="text-xs text-text-muted">Foto da NF + leitura IA automática</div>
          </div>
        </div>
        <ChevronRight size={16} className="text-text-muted" />
      </button>

      <div className="rounded-xl bg-glass border border-glass-border p-4">
        <div className="text-xs text-text-muted mb-2">COMO FUNCIONA</div>
        <ol className="space-y-2 text-sm text-text-secondary">
          <li className="flex gap-2"><span className="text-copper font-bold">1.</span> Fotografe a nota fiscal</li>
          <li className="flex gap-2"><span className="text-copper font-bold">2.</span> IA extrai valor, litros, data</li>
          <li className="flex gap-2"><span className="text-copper font-bold">3.</span> GPS registra localização</li>
          <li className="flex gap-2"><span className="text-copper font-bold">4.</span> Envio para aprovação</li>
        </ol>
      </div>
    </div>
  )
}

export default function AppMobile() {
  const [activeTab, setActiveTab] = useState<'rdo' | 'chat' | 'reembolso'>('rdo')
  const navigate = useNavigate()

  return (
    <div className="flex flex-col h-full max-w-md mx-auto">
      {/* Header */}
      <div className="px-4 pt-4 pb-2">
        <h1 className="text-xl font-bold text-copper">Campo</h1>
        <p className="text-xs text-text-muted">Modo mobile — acesso rápido para obra</p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 px-4 py-2">
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id as typeof activeTab)}
            className={`flex-1 flex flex-col items-center gap-1 py-2 rounded-xl text-xs font-medium transition ${
              activeTab === id
                ? 'bg-copper text-white'
                : 'bg-glass border border-glass-border text-text-muted hover:text-text-primary'
            }`}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'rdo'       && <RDOQuickCard       onNavigate={() => navigate('/rdo-form')} />}
        {activeTab === 'chat'      && <div className="p-4"><MobileChatEmbed /></div>}
        {activeTab === 'reembolso' && <ReembolsoQuickCard onNavigate={() => navigate('/reembolso-form')} />}
      </div>
    </div>
  )
}

/* Embedded mini chat inside AppMobile */
function MobileChatEmbed() {
  const navigate = useNavigate()
  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-text-primary">Assistente IA</h2>
      <p className="text-sm text-text-muted">
        Consulte KPIs, atividades e dados do contrato usando voz ou texto.
      </p>
      <button
        onClick={() => navigate('/mobile-chat')}
        className="w-full flex items-center justify-center gap-2 rounded-xl bg-copper text-white py-4 font-medium hover:bg-copper/90 transition"
      >
        <Mic size={20} />
        Abrir Chat com Voz
      </button>
    </div>
  )
}
