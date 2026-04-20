/**
 * MobileChat — chat IA otimizado para mobile com entrada de voz (Whisper).
 * Envia áudio via POST /api/ai/whisper → transcrito → enviado ao /api/ai/chat SSE.
 */
import { useState, useRef, useEffect } from 'react'
import { Mic, MicOff, Send, ArrowLeft, Loader2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
// auth cookie is sent automatically via credentials:'include' (same-origin proxy)

interface Message { role: 'user' | 'assistant'; content: string }

export default function MobileChat() {
  const navigate    = useNavigate()
  const [messages, setMessages]   = useState<Message[]>([])
  const [input, setInput]         = useState('')
  const [streaming, setStreaming] = useState(false)
  const [recording, setRecording] = useState(false)
  const [recStatus, setRecStatus] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const mediaRef  = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage(text: string) {
    if (!text.trim() || streaming) return
    const userMsg: Message = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setStreaming(true)

    const history = messages.map(m => ({ role: m.role, content: m.content }))
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    try {
      const resp  = await fetch('/api/ai/chat', {
        method:      'POST',
        credentials: 'include',
        headers:     { 'Content-Type': 'application/json' },
        body:        JSON.stringify({ message: text, history }),
      })
      if (!resp.body) throw new Error('No body')
      const reader = resp.body.getReader()
      const dec    = new TextDecoder()
      let   buf    = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') break
          try {
            const obj   = JSON.parse(payload)
            const token = obj?.choices?.[0]?.delta?.content
            if (token) {
              setMessages(prev => {
                const copy = [...prev]
                copy[copy.length - 1] = {
                  role:    'assistant',
                  content: copy[copy.length - 1].content + token,
                }
                return copy
              })
            }
          } catch { /* skip malformed */ }
        }
      }
    } catch (e: any) {
      setMessages(prev => {
        const copy = [...prev]
        copy[copy.length - 1] = { role: 'assistant', content: `Erro: ${e.message}` }
        return copy
      })
    } finally {
      setStreaming(false)
    }
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setRecStatus('Microfone não disponível')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr     = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        setRecStatus('Transcrevendo...')
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const form = new FormData()
        form.append('file', blob, 'audio.webm')
        form.append('language', 'pt')
        try {
          const res  = await fetch('/api/ai/whisper', { method: 'POST', credentials: 'include', body: form })
          const data = await res.json()
          if (data.ok && data.text) {
            setInput(data.text)
            setRecStatus('')
          } else {
            setRecStatus('Não foi possível transcrever')
          }
        } catch {
          setRecStatus('Erro na transcrição')
        }
      }
      mr.start()
      mediaRef.current = mr
      setRecording(true)
      setRecStatus('Gravando… toque para parar')
    } catch {
      setRecStatus('Permissão de microfone negada')
    }
  }

  function stopRecording() {
    mediaRef.current?.stop()
    setRecording(false)
  }

  return (
    <div className="flex flex-col h-screen bg-bg-void max-w-md mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-glass-border bg-glass">
        <button onClick={() => navigate('/app-mobile')} className="text-text-muted hover:text-text-primary">
          <ArrowLeft size={20} />
        </button>
        <div>
          <div className="text-sm font-semibold text-text-primary">Chat IA</div>
          <div className="text-xs text-text-muted">Bomtempo Intelligence</div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-text-muted text-sm py-12">
            Olá! Pergunte sobre contratos, KPIs ou atividades.<br />
            Use o microfone para falar.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'bg-copper text-white rounded-br-sm'
                  : 'bg-glass border border-glass-border text-text-primary rounded-bl-sm'
              }`}
            >
              {m.content || (m.role === 'assistant' && streaming ? <span className="animate-pulse">▋</span> : '')}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Recording status */}
      {recStatus && (
        <div className="px-4 py-1 text-xs text-center text-copper">{recStatus}</div>
      )}

      {/* Input bar */}
      <div className="flex items-center gap-2 px-4 py-3 border-t border-glass-border bg-glass">
        <button
          onPointerDown={startRecording}
          onPointerUp={stopRecording}
          disabled={streaming}
          className={`p-3 rounded-full transition ${
            recording
              ? 'bg-red-500 text-white animate-pulse'
              : 'bg-glass border border-glass-border text-text-muted hover:text-copper'
          }`}
          title="Segurar para gravar"
        >
          {recording ? <MicOff size={18} /> : <Mic size={18} />}
        </button>

        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input) } }}
          placeholder="Digite ou use o microfone…"
          disabled={streaming}
          className="flex-1 rounded-xl bg-bg-void border border-glass-border px-4 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-copper"
        />

        <button
          onClick={() => sendMessage(input)}
          disabled={!input.trim() || streaming}
          className="p-3 rounded-full bg-copper text-white hover:bg-copper/90 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {streaming ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </div>
    </div>
  )
}
