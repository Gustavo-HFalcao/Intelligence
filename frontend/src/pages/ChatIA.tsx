import { useState, useRef, useEffect } from 'react'
import { 
  Send, Bot, User, Loader2, Mic, ImageIcon, 
  Terminal, Sparkles, X, ChevronRight, Activity, 
  Cpu
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/ui/button'
import './Dashboard.css'

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'

interface Message { 
  role: 'user' | 'assistant'; 
  content: string; 
  ts: string; 
  isAgentic?: boolean;
  toolInfo?: string;
  image?: string;
}

export default function ChatIA() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [mode, setMode]         = useState<'direct' | 'agentic'>('agentic')
  const [isRecording, setIsRecording] = useState(false)
  const [selectedImage, setSelectedImage] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  
  const [sessionId] = useState(() => {
    try { return crypto.randomUUID() } catch { return Math.random().toString(36).slice(2) }
  })
  const bottomRef   = useRef<HTMLDivElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // ── Voice Handling ───────────────────────────────────────────────────────────

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      mediaRecorderRef.current = recorder
      audioChunksRef.current = []

      recorder.ondataavailable = (e) => audioChunksRef.current.push(e.data)
      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        await handleTranscription(audioBlob)
      }

      recorder.start()
      setIsRecording(true)
    } catch (e) {
      console.error('Mic access denied', e)
    }
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    setIsRecording(false)
  }

  const handleTranscription = async (blob: Blob) => {
    setLoading(true)
    const formData = new FormData()
    formData.append('file', blob, 'voice.webm')
    
    try {
      const res = await fetch('/api/ai/whisper', {
        method: 'POST',
        body: formData,
        credentials: 'include'
      })
      const data = await res.json()
      if (data.ok) {
        setInput(data.text)
      }
    } catch (e) {
      console.error('Transcription error', e)
    } finally {
      setLoading(false)
    }
  }

  // ── Image Handling ───────────────────────────────────────────────────────────

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedImage(file)
      setImagePreview(URL.createObjectURL(file))
    }
  }

  // ── Chat Logic ──────────────────────────────────────────────────────────────

  async function sendMessage() {
    const text = input.trim()
    if ((!text && !selectedImage) || loading) return
    
    const ts = new Date().toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})
    const userMsg: Message = { 
      role: 'user', 
      content: text || "Analisar imagem anexa.", 
      ts,
      image: imagePreview || undefined
    }
    
    setMessages(m => [...m, userMsg])
    setInput('')
    setSelectedImage(null)
    setImagePreview(null)
    setLoading(true)

    try {
      if (selectedImage) {
        // Vision Mode
        const formData = new FormData()
        formData.append('file', selectedImage)
        formData.append('prompt', text || 'Analise esta imagem sob o contexto de engenharia.')
        
        const res = await fetch('/api/ai/vision', { method: 'POST', body: formData, credentials: 'include' })
        const data = await res.json()
        setMessages(m => [...m, { 
          role: 'assistant', 
          content: data.ok ? data.result : `Erro: ${data.error}`, 
          ts 
        }])
      } else if (mode === 'agentic') {
        // Agentic Mode (Polling)
        const res = await fetch('/api/ai/chat/agentic', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, session_id: sessionId, history: messages.slice(-5) }),
          credentials: 'include'
        })
        const initData = await res.json()
        
        // Polling loop
        let done = false
        while (!done) {
          await new Promise(r => setTimeout(r, 1500))
          const pollRes = await fetch(`/api/ai/stream/${initData.session_id}`, { credentials: 'include' })
          const pollData = await pollRes.json()
          
          if (pollData.status === 'done') {
            setMessages(m => [...m, { 
              role: 'assistant', 
              content: pollData.content, 
              ts, 
              isAgentic: true 
            }])
            done = true
          } else if (pollData.status === 'error') {
            throw new Error(pollData.error)
          }
        }
      } else {
        // Streaming Direct Mode
        const resp = await fetch('/api/ai/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, session_id: sessionId, history: messages.slice(-5) }),
          credentials: 'include'
        })
        if (!resp.ok || !resp.body) throw new Error('Falha no motor de IA')

        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let aiContent = ''

        setMessages(m => [...m, { role: 'assistant', content: '', ts }])

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const chunk = decoder.decode(value)
          const lines = chunk.split('\n')
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6)
              if (dataStr === '[DONE]') break
              try {
                const json = JSON.parse(dataStr)
                aiContent += json.choices?.[0]?.delta?.content ?? ''
                setMessages(m => {
                  const arr = [...m]
                  arr[arr.length-1].content = aiContent
                  return arr
                })
              } catch {}
            }
          }
        }
      }
    } catch (e: any) {
      setMessages(m => [...m, { role: 'assistant', content: `Ocorreu um erro técnico: ${e.message}`, ts }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] animate-enter relative">
      {/* ── HEADER ────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-copper/10 border border-copper/30 shadow-[0_0_15px_rgba(201,139,42,0.1)]">
            <Cpu size={22} className="text-copper animate-pulse" />
          </div>
          <div>
            <h1 className="font-display text-xl font-black text-white uppercase tracking-tight">Intelligence Agent</h1>
            <div className="flex items-center gap-2 mt-0.5">
               <span className="text-[9px] text-teal-500 font-black uppercase tracking-widest bg-teal-500/10 px-1.5 rounded">Neural L4</span>
               <span className="text-[9px] text-text-muted font-mono">ID: {sessionId.slice(0,8)}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1 bg-white/[0.03] border border-white/5 p-1 rounded-lg">
           <button 
             onClick={() => setMode('direct')}
             className={`px-3 py-1.5 rounded-md flex items-center gap-2 text-[9px] font-bold uppercase tracking-widest transition-all ${mode === 'direct' ? 'bg-copper text-void shadow-lg' : 'text-text-muted hover:text-white'}`}
           >
             Chat Rápido
           </button>
           <button 
             onClick={() => setMode('agentic')}
             className={`px-3 py-1.5 rounded-md flex items-center gap-2 text-[9px] font-bold uppercase tracking-widest transition-all ${mode === 'agentic' ? 'bg-copper text-void shadow-lg' : 'text-text-muted hover:text-white'}`}
           >
             <Sparkles size={12} /> Análise Agêntica
           </button>
        </div>
      </div>

      {/* ── MESSAGES ──────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto pr-4 custom-scrollbar space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-20 opacity-30">
            <Bot size={64} className="mb-4 text-copper" />
            <h2 className="text-xl font-bold text-white mb-2 uppercase tracking-tighter">Sistemas Online</h2>
            <p className="max-w-xs text-sm">Olá, sou o Agente Bomtempo. Posso analisar cronogramas, prever gargalos e realizar auditorias visuais em tempo real. Como posso ajudar?</p>
          </div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <motion.div 
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-4 ${m.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
            >
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-lg ${m.role === 'user' ? 'bg-copper border border-copper/30' : 'bg-void border border-white/10'}`}>
                {m.role === 'user' ? <User size={18} className="text-void" /> : <Bot size={18} className="text-copper" />}
              </div>

              <div className={`max-w-[80%] space-y-2 ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                <div className={`p-5 rounded-2xl glass-panel relative overflow-hidden ${m.role === 'user' ? 'border-copper/20 bg-copper/5' : 'border-white/5 bg-white/[0.02]'}`}>
                  {m.image && (
                    <div className="mb-3 rounded-lg overflow-hidden border border-white/10">
                       <img src={m.image} alt="User upload" className="max-w-xs w-full object-cover" />
                    </div>
                  )}
                  {m.isAgentic && (
                    <div className="flex items-center gap-2 mb-2 p-2 rounded bg-teal-500/5 border border-teal-500/10">
                       <Terminal size={12} className="text-teal-500" />
                       <span className="text-[9px] font-black uppercase text-teal-500 tracking-widest italic">Raciocínio Lógico Concluído</span>
                    </div>
                  )}
                  <div className="text-sm font-light leading-relaxed text-[#e2c87a] whitespace-pre-wrap">
                    {m.content ? m.content : (loading && i === messages.length-1 && m.role === 'assistant') ? (
                      <span className="flex items-center gap-2" style={{ color: COPPER }}>
                        <span style={{ display: 'flex', gap: 4 }}>
                          {[0,1,2].map(d => (
                            <span key={d} style={{ width: 6, height: 6, borderRadius: '50%', background: COPPER, display: 'inline-block', animation: `bounce 1.2s ease-in-out ${d * 0.2}s infinite` }} />
                          ))}
                        </span>
                        <span style={{ fontSize: 11, opacity: 0.7 }}>pensando...</span>
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-3 flex items-center justify-between">
                     <span className="text-[8px] font-mono text-white/20">{m.ts}</span>
                     {m.isAgentic && <Activity size={10} className="text-copper/40" />}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* ── INPUT BAR ──────────────────────────────────────────────────────── */}
      <div className="mt-6 pt-6 border-t border-white/5">
        
        {/* Preview Image */}
        {imagePreview && (
          <div className="mb-4 relative w-20 h-20 rounded-lg overflow-hidden border border-copper shadow-lg">
            <img src={imagePreview} className="w-full h-full object-cover" />
            <button onClick={() => { setSelectedImage(null); setImagePreview(null); }} className="absolute top-1 right-1 bg-red-500 p-1 rounded-full text-white">
              <X size={10} />
            </button>
          </div>
        )}

        {loading && (
          <div className="mb-4 flex items-center gap-3 p-3 rounded-xl animate-pulse"
            style={{ background: mode === 'agentic' ? 'rgba(42,157,143,0.08)' : 'rgba(201,139,42,0.06)', border: `1px solid ${mode === 'agentic' ? 'rgba(42,157,143,0.2)' : 'rgba(201,139,42,0.15)'}` }}>
            <Loader2 className="animate-spin shrink-0" size={14} style={{ color: mode === 'agentic' ? TEAL : COPPER }} />
            <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: mode === 'agentic' ? TEAL : COPPER }}>
              {mode === 'agentic' ? 'Acessando ferramentas e auditando base de dados...' : 'Analisando e gerando resposta...'}
            </span>
          </div>
        )}

        <div className="flex items-center gap-3 bg-white/[0.03] border border-white/10 p-2 rounded-2xl shadow-inner group focus-within:border-copper/40 transition-all">
          <input 
            type="file" 
            id="ai-image-upload" 
            hidden 
            accept="image/*" 
            onChange={handleImageSelect} 
          />
          <label htmlFor="ai-image-upload" className="p-3 text-text-muted hover:text-white cursor-pointer hover:bg-white/5 rounded-xl transition-all">
            <ImageIcon size={20} />
          </label>
          
          <button 
            onClick={isRecording ? stopRecording : startRecording}
            className={`p-3 rounded-xl transition-all ${isRecording ? 'bg-red-500 text-white animate-pulse' : 'text-text-muted hover:text-white hover:bg-white/5'}`}
          >
            <Mic size={20} />
          </button>

          <input 
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), sendMessage())}
            placeholder={isRecording ? "Gravando áudio..." : "Fale com a inteligência Bomtempo..."}
            className="flex-1 bg-transparent border-none outline-none text-sm text-[#e2c87a] placeholder:text-white/20 px-2"
            disabled={isRecording}
          />

          <Button 
            onClick={sendMessage}
            disabled={(!input.trim() && !selectedImage) || loading}
            className="bg-copper hover:bg-copper/90 text-void font-bold h-12 w-12 rounded-xl shadow-lg hover:shadow-copper/30 transition-all"
          >
            {loading ? <Loader2 className="animate-spin" size={20} /> : <Send size={20} />}
          </Button>
        </div>
        
        <div className="mt-3 flex justify-center gap-4">
           <span className="text-[8px] text-white/20 uppercase tracking-widest flex items-center gap-1.5"><Terminal size={10} /> Latência: 240ms</span>
           <span className="text-[8px] text-white/20 uppercase tracking-widest flex items-center gap-1.5"><Activity size={10} /> Contexto: Global</span>
        </div>
      </div>
    </div>
  )
}
