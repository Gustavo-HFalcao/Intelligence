import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { UploadCloud, X, MapPin, Zap, Activity, Info, Navigation, Layers, Wind, CloudLightning, ShieldAlert, Cpu, Sun, CloudRain, Droplets, Thermometer, Calendar, Play, Pause, CheckCircle2, AlertTriangle, Clock, HardHat, TrendingUp, Filter, BrainCircuit, FastForward } from 'lucide-react'

// Cores premium da identidade
const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'

interface TowerData {
  id: string;
  name: string;
  coords: [number, number];
  type?: string;
  status: 'Concluída' | 'Em andamento' | 'Atrasada' | 'Bloqueada' | 'Planejada';
  progress: number;
  team: string;
  startDate: string;
  plannedDate: string;
  riskLevel: number;
  productivity: number;
}

interface SegmentData {
  name: string;
  coords: [number, number][];
}

interface WeatherData {
  current: {
    temperature: number;
    windspeed: number;
    weathercode: number;
    rain: number;
  };
  forecast: any[];
}

// Simulador de Dados Inteligentes
const injectMockData = (towers: any[]): TowerData[] => {
  const teams = ['Equipe Alpha', 'Equipe Bravo', 'Equipe Charlie', 'Equipe Delta']
  return towers.map((t, index) => {
    const r = Math.random()
    let status: TowerData['status'] = 'Planejada'
    let progress = 0
    if (r < 0.60) { status = 'Concluída'; progress = 100; }
    else if (r < 0.85) { status = 'Em andamento'; progress = Math.floor(Math.random() * 80) + 10; }
    else if (r < 0.95) { status = 'Atrasada'; progress = Math.floor(Math.random() * 60) + 5; }
    else { status = 'Bloqueada'; progress = Math.floor(Math.random() * 40); }

    const team = teams[Math.floor(Math.random() * teams.length)]
    const riskLevel = status === 'Bloqueada' ? Math.floor(Math.random() * 20) + 80 : 
                      status === 'Atrasada' ? Math.floor(Math.random() * 30) + 50 : 
                      Math.floor(Math.random() * 20);

    return {
      ...t,
      id: `TWR-${index}`,
      status,
      progress,
      team,
      startDate: '2026-03-01',
      plannedDate: '2026-05-15',
      riskLevel,
      productivity: Math.random() * 2 + 0.5
    } as TowerData
  })
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'Concluída': return '#10B981'; // Green
    case 'Em andamento': return '#F59E0B'; // Yellow
    case 'Atrasada': return '#F97316'; // Orange
    case 'Bloqueada': return '#EF4444'; // Red
    default: return '#3B82F6'; // Blue
  }
}

export default function LTDemo() {
  const [kmlData, setKmlData] = useState<{ towers: TowerData[], segments: SegmentData[] } | null>(null)
  const [displayTowers, setDisplayTowers] = useState<TowerData[]>([]) // Usado para simulação
  const [loading, setLoading] = useState(false)
  const [mapLoaded, setMapLoaded] = useState(false)
  const [selectedElement, setSelectedElement] = useState<any>(null)
  const [weatherData, setWeatherData] = useState<WeatherData | null>(null)
  const [weatherLoading, setWeatherLoading] = useState(false)
  const [windyError, setWindyError] = useState(false)
  const [windyReady, setWindyReady] = useState(false)
  const [activeLayer, setActiveLayer] = useState('wind')
  
  // Filter State
  const [filterStatus, setFilterStatus] = useState<string>('Todos')
  const [filterTeam, setFilterTeam] = useState<string>('Todas')

  const mapRef = useRef<HTMLDivElement>(null)
  const leafletMap = useRef<any>(null)
  const windyStore = useRef<any>(null)
  const markersRef = useRef<any[]>([])

  // 1. Injetar Windy API
  useEffect(() => {
    const loadWindy = async () => {
      if (!document.getElementById('windy-leaflet-css')) {
        const link = document.createElement('link')
        link.id = 'windy-leaflet-css'
        link.rel = 'stylesheet'
        link.href = 'https://unpkg.com/leaflet@1.4.0/dist/leaflet.css'
        document.head.appendChild(link)
      }
      if (!document.getElementById('windy-leaflet-js')) {
        const script = document.createElement('script')
        script.id = 'windy-leaflet-js'
        script.src = 'https://unpkg.com/leaflet@1.4.0/dist/leaflet.js'
        document.head.appendChild(script)
        await new Promise(r => script.onload = r)
      }
      if (!document.getElementById('windy-api-js')) {
        const script = document.createElement('script')
        script.id = 'windy-api-js'
        script.src = 'https://api.windy.com/assets/map-forecast/libBoot.js'
        document.head.appendChild(script)
        await new Promise(r => script.onload = r)
      }
      setMapLoaded(true)
    }
    loadWindy()
  }, [])

  // 2. Inicializar Windy API
  useEffect(() => {
    if (!mapLoaded || !mapRef.current || leafletMap.current) return

    const options = {
      key: 't2K5Xp7E0OQAcKhyf3HT2o9hM2MsojqF',
      lat: -12.5,
      lon: -38.5,
      zoom: 7,
    };

    const errorTimer = setTimeout(() => {
      if (!leafletMap.current) setWindyError(true)
    }, 15000)

    try {
      (window as any).windyInit(options, (windyAPI: any) => {
        clearTimeout(errorTimer)
        setWindyError(false)
        const { map, store } = windyAPI;
        leafletMap.current = map;
        windyStore.current = store;
        setWindyReady(true);
      });
    } catch (e) {
      clearTimeout(errorTimer)
      setWindyError(true)
      console.error("Erro ao inicializar Windy API", e)
    }

    return () => clearTimeout(errorTimer)
  }, [mapLoaded])

  // Função Auxiliar: Renderizar Torres no Mapa
  const renderTowersOnMap = (towers: TowerData[]) => {
    if (!leafletMap.current || !windyReady) return;
    const L = (window as any).L
    const map = leafletMap.current

    // Limpar marcadores antigos
    markersRef.current.forEach(m => map.removeLayer(m))
    markersRef.current = []

    towers.forEach(t => {
      const color = getStatusColor(t.status)
      const glow = t.status === 'Bloqueada' || t.status === 'Atrasada' ? `box-shadow: 0 0 15px ${color}; animation: pulse 2s infinite;` : `box-shadow: 0 0 8px ${color};`
      
      const iconHtml = `<div style="width: 12px; height: 12px; background: ${color}; border: 2px solid #000; border-radius: 50%; ${glow}"></div>`
      
      const towerIcon = L.divIcon({
        className: 'custom-tower-marker',
        html: iconHtml,
        iconSize: [12, 12],
        iconAnchor: [6, 6]
      })

      const marker = L.marker(t.coords, { icon: towerIcon }).addTo(map)
      marker.on('click', () => handleElementClick(t))
      markersRef.current.push(marker)
    })
  }

  // 3. Renderizar o KML base e Segmentos
  useEffect(() => {
    if (!windyReady || !kmlData || !leafletMap.current) return
    const L = (window as any).L
    const map = leafletMap.current

    // Render Segmentos (Linha da LT)
    kmlData.segments.forEach(seg => {
      const polyline = L.polyline(seg.coords, {
        color: 'rgba(255, 255, 255, 0.3)',
        weight: 2,
        dashArray: '5, 5',
        lineCap: 'round',
        className: 'lt-polyline-glow'
      }).addTo(map)
    })

    // Zoom extent apenas na primeira carga
    if (displayTowers.length === 0) {
      const bounds = L.latLngBounds()
      kmlData.towers.forEach(t => bounds.extend(t.coords))
      map.fitBounds(bounds, { padding: [50, 50] })
    }

  }, [kmlData, windyReady])

  // Lógica de Filtros Integrada
  useEffect(() => {
    if (!kmlData) return
    let filtered = kmlData.towers
    if (filterStatus !== 'Todos') filtered = filtered.filter(t => t.status === filterStatus)
    if (filterTeam !== 'Todas') filtered = filtered.filter(t => t.team === filterTeam)
    setDisplayTowers(filtered)
  }, [kmlData, filterStatus, filterTeam])

  // 4. Re-renderizar Torres quando displayTowers mudar
  useEffect(() => {
    if (displayTowers.length > 0 || kmlData) {
      renderTowersOnMap(displayTowers)
    }
  }, [displayTowers])

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setLoading(true)
    const reader = new FileReader()
    reader.onload = (event) => {
      try {
        const text = event.target?.result as string
        const parser = new DOMParser()
        const xmlDoc = parser.parseFromString(text, 'text/xml')
        
        const placemarks = Array.from(xmlDoc.getElementsByTagName('Placemark'))
        const newTowers: any[] = []
        const newSegments: SegmentData[] = []

        placemarks.forEach(pm => {
          const name = pm.getElementsByTagName('name')[0]?.textContent || 'Sem Nome'
          const point = pm.getElementsByTagName('Point')[0]
          const lineString = pm.getElementsByTagName('LineString')[0]

          if (point) {
            const coordsText = point.getElementsByTagName('coordinates')[0]?.textContent?.trim()
            if (coordsText) {
              const [lng, lat] = coordsText.split(',').map(Number)
              newTowers.push({ name, coords: [lat, lng], type: 'Estrutura' })
            }
          } else if (lineString) {
            const coordsText = lineString.getElementsByTagName('coordinates')[0]?.textContent?.trim()
            if (coordsText) {
              const coords: [number, number][] = coordsText.split(/\s+/).map(c => {
                const [lng, lat] = c.split(',').map(Number)
                return [lat, lng]
              })
              newSegments.push({ name, coords })
            }
          }
        })

        // Injetar Mock Data Inteligente
        const mockTowers = injectMockData(newTowers)

        setKmlData({ towers: mockTowers, segments: newSegments })
        setLoading(false)
      } catch (error) {
        console.error("Erro ao ler KML:", error)
        setLoading(false)
        alert("Erro ao processar o arquivo. Verifique o formato.")
      }
    }
    reader.readAsText(file)
  }

  const fetchWeatherData = async (lat: number, lng: number) => {
    setWeatherLoading(true)
    try {
      const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&current_weather=true&daily=temperature_2m_max,precipitation_sum,weathercode&timezone=auto`)
      const data = await res.json()
      
      const forecast = data.daily.time.map((t: string, i: number) => ({
        date: t,
        tempMax: data.daily.temperature_2m_max[i],
        rain: data.daily.precipitation_sum[i],
        code: data.daily.weathercode[i]
      }))

      setWeatherData({
        current: {
          temperature: data.current_weather.temperature,
          windspeed: data.current_weather.windspeed,
          weathercode: data.current_weather.weathercode,
          rain: data.daily.precipitation_sum[0]
        },
        forecast
      })
    } catch (error) {
      console.error("Erro na API Open-Meteo", error)
    } finally {
      setWeatherLoading(false)
    }
  }

  const handleElementClick = (element: TowerData) => {
    setSelectedElement(element)
    fetchWeatherData(element.coords[0], element.coords[1])
    
    if (leafletMap.current) {
      // Usa panTo para preservar o zoom atual e evitar travamentos no Leaflet do Windy
      leafletMap.current.panTo(element.coords, { animate: true })
    }
  }

  const handleLayerChange = (layer: string) => {
    setActiveLayer(layer)
    if (windyStore.current) {
      windyStore.current.set('overlay', layer)
    }
  }

  // --- GERADOR DE INSIGHTS IA DINÂMICO ---
  const getInsights = () => {
    if (!kmlData || kmlData.towers.length === 0) return []
    const towers = kmlData.towers
    const teams = ['Equipe Alpha', 'Equipe Bravo', 'Equipe Charlie', 'Equipe Delta']
    
    let slowestTeam = 'Nenhuma'
    let lowestProgress = 100
    teams.forEach(team => {
      const teamTowers = towers.filter(t => t.team === team)
      if (teamTowers.length > 0) {
        const avg = teamTowers.reduce((acc, t) => acc + t.progress, 0) / teamTowers.length
        if (avg < lowestProgress) {
          lowestProgress = avg
          slowestTeam = team
        }
      }
    })

    const blocked = towers.filter(t => t.status === 'Bloqueada').length
    
    return [
      { title: 'Análise Logística', text: `A ${slowestTeam} possui a menor média de progresso (${lowestProgress.toFixed(1)}%). Avalie gargalos no trecho de atuação.` },
      { title: 'Risco Operacional', text: blocked > 0 ? `Identificadas ${blocked} torres bloqueadas. Risco climático e de acesso nos próximos 3 dias.` : 'O fluxo operacional está regular. Sem bloqueios críticos detectados.' }
    ]
  }

  const insights = getInsights()

  // KPIs Calculados
  const totalTowers = displayTowers.length
  const completed = displayTowers.filter(t => t.status === 'Concluída').length
  const inProgress = displayTowers.filter(t => t.status === 'Em andamento').length
  const blocked = displayTowers.filter(t => t.status === 'Bloqueada').length
  const late = displayTowers.filter(t => t.status === 'Atrasada').length
  const globalProgress = totalTowers > 0 ? ((completed / totalTowers) * 100).toFixed(1) : 0

  const getWeatherIcon = (code: number, size = 16) => {
    if (code === 0 || code === 1) return <Sun size={size} />
    if (code >= 2 && code <= 45) return <CloudRain size={size} />
    if (code >= 51 && code <= 67) return <Droplets size={size} />
    if (code >= 95) return <CloudLightning size={size} />
    return <CloudRain size={size} />
  }

  return (
    <div className="h-screen w-screen bg-[#050808] flex flex-col font-outfit text-white overflow-hidden relative">
      <style>{`
        @keyframes pulse {
          0% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.5); opacity: 0.5; }
          100% { transform: scale(1); opacity: 1; }
        }
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
      `}</style>

      {/* HEADER: COMMAND CENTER KPIs */}
      <header className="absolute top-0 left-0 w-full h-[70px] bg-[#0a0f0e]/80 backdrop-blur-3xl border-b border-white/5 z-30 flex items-center justify-between px-6 shadow-2xl">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3 border-r border-white/10 pr-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-copper/20 to-copper/5 border border-copper/30 flex items-center justify-center">
              <Layers size={20} className="text-copper" />
            </div>
            <div className="flex flex-col">
              <h1 className="text-sm font-black uppercase tracking-[0.2em] leading-tight">Master Meteo-Grid</h1>
              <span className="text-[9px] text-white/40 font-bold uppercase tracking-widest mt-0.5">Command Center V2</span>
            </div>
          </div>

          {/* KPIs Globais */}
          {totalTowers > 0 && (
            <div className="flex items-center gap-8">
              <div className="flex flex-col">
                <span className="text-[9px] text-white/40 uppercase font-bold tracking-widest mb-1">Progresso Global</span>
                <div className="flex items-end gap-2">
                  <span className="text-xl font-black text-white leading-none">{globalProgress}%</span>
                  <div className="w-24 h-1.5 bg-white/10 rounded-full mb-1 overflow-hidden">
                    <div className="h-full bg-teal-500 rounded-full transition-all duration-1000" style={{ width: `${globalProgress}%` }}></div>
                  </div>
                </div>
              </div>

              <div className="flex gap-6">
                <div className="flex flex-col">
                  <span className="text-[9px] text-white/40 uppercase font-bold tracking-widest flex items-center gap-1 mb-1"><CheckCircle2 size={10} className="text-emerald-500"/> Concluídas</span>
                  <span className="text-lg font-black text-emerald-400">{completed} <span className="text-xs text-white/30 font-medium">/ {totalTowers}</span></span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[9px] text-white/40 uppercase font-bold tracking-widest flex items-center gap-1 mb-1"><Activity size={10} className="text-yellow-500"/> Em Andamento</span>
                  <span className="text-lg font-black text-yellow-500">{inProgress}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[9px] text-white/40 uppercase font-bold tracking-widest flex items-center gap-1 mb-1"><AlertTriangle size={10} className="text-red-500"/> Bloqueadas/Atrasadas</span>
                  <span className="text-lg font-black text-red-400">{blocked + late}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-4">
          <label className="cursor-pointer bg-white/5 border border-white/10 text-white px-4 py-2 rounded-xl font-bold text-[10px] uppercase tracking-widest flex items-center gap-2 hover:bg-white/10 transition-all">
            <UploadCloud size={14} />
            {loading ? 'Carregando...' : 'KML Malha'}
            <input type="file" accept=".kml,.xml" className="hidden" onChange={handleFileUpload} />
          </label>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 relative flex overflow-hidden">
        
        {/* Painel Lateral Esquerdo (Filtros & IA) */}
        {windyReady && kmlData && (
          <div className="absolute left-6 top-[94px] z-20 flex flex-col gap-4 w-[280px]">
            {/* Camadas do Windy */}
            <div className="bg-[#0a0f0e]/80 backdrop-blur-2xl border border-white/5 rounded-2xl p-2 flex gap-1 shadow-2xl">
              {[
                { id: 'wind', label: 'Vento', icon: Wind },
                { id: 'rain', label: 'Chuva', icon: CloudRain },
                { id: 'temp', label: 'Temp', icon: Thermometer },
              ].map(layer => {
                const Icon = layer.icon
                const isActive = activeLayer === layer.id
                return (
                  <button
                    key={layer.id}
                    onClick={() => handleLayerChange(layer.id)}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-xl transition-all text-[10px] font-bold uppercase tracking-widest ${
                      isActive ? 'bg-teal-500/20 text-teal-400 border border-teal-500/30' : 'text-white/40 hover:text-white/80 hover:bg-white/5 border border-transparent'
                    }`}
                  >
                    <Icon size={12} />
                    {layer.label}
                  </button>
                )
              })}
            </div>

            {/* Command Panel (Filtros e Insights) */}
            <div className="bg-[#0a0f0e]/80 backdrop-blur-2xl border border-copper/20 rounded-2xl p-4 shadow-[0_0_30px_rgba(201,139,42,0.1)] flex flex-col relative overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-copper/0 via-copper to-copper/0 opacity-50"></div>
              
              {/* Filtros Cockpit */}
              <div className="mb-5 pb-5 border-b border-white/5 space-y-3">
                <div className="flex items-center gap-2 mb-2">
                  <Filter size={12} className="text-copper" />
                  <h3 className="text-[9px] font-black uppercase tracking-[0.2em] text-copper">Cockpit Filters</h3>
                </div>
                
                <div className="flex flex-col gap-1">
                  <label className="text-[8px] uppercase tracking-widest text-white/40 font-bold">Status da Torre</label>
                  <select 
                    value={filterStatus} 
                    onChange={e => setFilterStatus(e.target.value)}
                    className="bg-black/50 border border-white/10 text-white text-[10px] rounded-lg px-2 py-1.5 outline-none focus:border-copper/50 uppercase font-bold"
                  >
                    <option value="Todos">Todas as Torres</option>
                    <option value="Concluída">🟢 Concluídas</option>
                    <option value="Em andamento">🟡 Em Andamento</option>
                    <option value="Atrasada">🟠 Atrasadas</option>
                    <option value="Bloqueada">🔴 Bloqueadas</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[8px] uppercase tracking-widest text-white/40 font-bold">Equipe Responsável</label>
                  <select 
                    value={filterTeam} 
                    onChange={e => setFilterTeam(e.target.value)}
                    className="bg-black/50 border border-white/10 text-white text-[10px] rounded-lg px-2 py-1.5 outline-none focus:border-copper/50 uppercase font-bold"
                  >
                    <option value="Todas">Todas as Equipes</option>
                    <option value="Equipe Alpha">Equipe Alpha</option>
                    <option value="Equipe Bravo">Equipe Bravo</option>
                    <option value="Equipe Charlie">Equipe Charlie</option>
                    <option value="Equipe Delta">Equipe Delta</option>
                  </select>
                </div>
              </div>

              {/* Insights IA */}
              <div className="flex items-center gap-2 mb-4">
                <BrainCircuit size={12} className="text-teal-400" />
                <h3 className="text-[9px] font-black uppercase tracking-[0.2em] text-teal-400">Insights IA da Malha</h3>
              </div>

              <div className="space-y-3">
                {insights.map((insight, idx) => (
                  <div key={idx} className="bg-white/5 border border-white/5 rounded-lg p-3">
                    <span className="text-[8px] text-white/50 uppercase tracking-widest font-bold block mb-1.5">{insight.title}</span>
                    <p className="text-[11px] text-white/80 leading-snug">{insight.text}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Mapa Container do Windy */}
        <div id="windy" ref={mapRef} className="flex-1 h-full w-full bg-[#050808] z-0 absolute inset-0 pt-[70px]"></div>
          
        {/* Overlays posicionados por cima do mapa */}
        <div className="absolute inset-0 pointer-events-none z-10 flex items-center justify-center pt-[70px]">
          {windyError && (
            <div className="absolute inset-0 flex items-center justify-center bg-[#050808]/95 backdrop-blur-md z-50 pointer-events-auto">
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center max-w-lg text-center p-8 border border-red-500/20 bg-red-500/5 rounded-3xl relative">
                <button onClick={() => setWindyError(false)} className="absolute top-4 right-4 p-2 text-white/40 hover:text-white bg-white/5 rounded-full transition-colors">
                  <X size={16} />
                </button>
                <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-6">
                  <ShieldAlert size={32} className="text-red-400" />
                </div>
                <h2 className="text-xl font-black uppercase tracking-widest mb-2 text-white">Aviso de Conexão Windy</h2>
                <p className="text-sm text-white/60 leading-relaxed mb-6">
                  Rate Limit: Aguarde uns segundos e tente novamente.
                </p>
              </motion.div>
            </div>
          )}

          {!kmlData && !loading && !windyError && (
            <div className="absolute inset-0 flex items-center justify-center bg-[#050808]/60 backdrop-blur-sm pointer-events-none">
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center max-w-md text-center p-8 border border-white/5 bg-white/[0.02] rounded-3xl">
                <div className="w-16 h-16 rounded-2xl bg-copper/10 border border-copper/20 flex items-center justify-center mb-6">
                  <Wind size={32} className="text-copper" />
                </div>
                <h2 className="text-xl font-black uppercase tracking-widest mb-2">Simulador Geoespacial</h2>
                <p className="text-sm text-white/40 leading-relaxed mb-8">O mapa está exibindo a camada de ventos real-time. Carregue seu KML para acessar o Command Center de Inteligência.</p>
              </motion.div>
            </div>
          )}
        </div>

        {/* Sidebar Direita Flutuante Premium - Dados da Torre */}
        <AnimatePresence>
          {kmlData && selectedElement && (
            <motion.div
              initial={{ x: 400, opacity: 0, scale: 0.95 }}
              animate={{ x: 0, opacity: 1, scale: 1 }}
              exit={{ x: 400, opacity: 0, scale: 0.95 }}
              transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
              className="w-[360px] max-h-[calc(100vh-120px)] bg-[#0a0f0e]/85 backdrop-blur-3xl border border-white/10 z-20 flex flex-col shadow-[0_0_50px_rgba(0,0,0,0.6)] absolute right-6 top-[94px] rounded-3xl overflow-hidden pointer-events-auto"
            >
              <div className="p-5 border-b border-white/5 flex items-center justify-between bg-white/[0.02] shrink-0">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-teal-500/10 border border-teal-500/20 flex items-center justify-center shrink-0">
                    <Activity size={14} className="text-teal-400" />
                  </div>
                  <div className="flex flex-col">
                    <h2 className="text-xs font-black uppercase tracking-widest text-white leading-tight">Torre Telemetry</h2>
                    <span className="text-[8px] text-teal-400 font-bold uppercase tracking-widest leading-none mt-1">Live Sync • Open-Meteo</span>
                  </div>
                </div>
                <button onClick={() => setSelectedElement(null)} className="text-white/40 hover:text-white transition-colors w-6 h-6 flex items-center justify-center bg-white/5 hover:bg-white/10 rounded-full">
                  <X size={12} />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-5 space-y-6 custom-scrollbar">
                
                {/* Identificação e Status */}
                <div>
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="text-[9px] font-bold text-copper tracking-[2px] uppercase mb-1">Identificação</div>
                      <h3 className="text-xl font-black leading-tight break-all">{selectedElement.name}</h3>
                    </div>
                    <div className="bg-white/5 border border-white/10 px-2 py-1 rounded text-[9px] font-mono text-white/60">
                      {selectedElement.coords[0].toFixed(4)}, {selectedElement.coords[1].toFixed(4)}
                    </div>
                  </div>

                  {/* Barra de Progresso e Equipe */}
                  <div className="bg-white/5 border border-white/5 rounded-xl p-4 mt-4 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <HardHat size={14} className="text-white/40" />
                        <span className="text-xs font-bold text-white/80 uppercase">{selectedElement.team || 'N/A'}</span>
                      </div>
                      <span className="text-[9px] px-2 py-0.5 rounded-full uppercase font-bold tracking-widest" style={{ backgroundColor: `${getStatusColor(selectedElement.status || 'Planejada')}20`, color: getStatusColor(selectedElement.status || 'Planejada'), border: `1px solid ${getStatusColor(selectedElement.status || 'Planejada')}40` }}>
                        {selectedElement.status || 'Planejada'}
                      </span>
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex justify-between text-[10px] font-bold uppercase tracking-widest">
                        <span className="text-white/40">Progresso Físico</span>
                        <span className="text-white">{selectedElement.progress?.toFixed(1) || 0}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-black rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${selectedElement.progress || 0}%`, backgroundColor: getStatusColor(selectedElement.status || 'Planejada') }}></div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Weather Intelligence */}
                {weatherLoading ? (
                  <div className="h-32 flex items-center justify-center border border-white/5 rounded-2xl bg-white/[0.01]">
                    <div className="w-6 h-6 border-2 border-copper border-t-transparent rounded-full animate-spin"></div>
                  </div>
                ) : weatherData ? (
                  <div className="space-y-4">
                    
                    <div className="flex items-center gap-2">
                      <CloudLightning size={14} className="text-blue-400" />
                      <h4 className="text-[10px] font-black uppercase tracking-widest text-white/60">Inteligência Climática</h4>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-3 flex items-center gap-3">
                        <Thermometer size={14} className="text-copper" />
                        <div>
                          <div className="text-[8px] text-white/40 font-bold uppercase tracking-widest">Temp. Real</div>
                          <div className="text-sm font-black">{weatherData.current.temperature}°C</div>
                        </div>
                      </div>
                      <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-3 flex items-center gap-3">
                        <Wind size={14} className="text-teal-400" />
                        <div>
                          <div className="text-[8px] text-white/40 font-bold uppercase tracking-widest">Vento Real</div>
                          <div className="text-sm font-black">{weatherData.current.windspeed} <span className="text-[9px] text-white/50">km/h</span></div>
                        </div>
                      </div>
                    </div>

                    {/* Janela Operacional IA */}
                    {weatherData.current.rain > 2 || weatherData.current.windspeed > 25 ? (
                      <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
                        <div className="flex items-start gap-3">
                          <ShieldAlert size={16} className="text-red-400 shrink-0 mt-0.5" />
                          <div>
                            <h4 className="text-[9px] uppercase font-black tracking-[0.1em] text-red-400 mb-1">Bloqueio Recomendado</h4>
                            <p className="text-[11px] text-white/70 leading-relaxed font-medium">
                              Condições severas na torre. {weatherData.current.rain}mm chuva / {weatherData.current.windspeed}km/h vento. Operações de içamento suspensas.
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="bg-teal-500/10 border border-teal-500/20 rounded-xl p-4">
                        <div className="flex items-start gap-3">
                          <CheckCircle2 size={16} className="text-teal-400 shrink-0 mt-0.5" />
                          <div>
                            <h4 className="text-[9px] uppercase font-black tracking-[0.1em] text-teal-400 mb-1">Janela Ideal Encontrada</h4>
                            <p className="text-[11px] text-white/70 leading-relaxed font-medium">
                              Clima favorável. Janela sugerida para concretagem/içamento: <strong className="text-white">Hoje, 08:00 – 16:30</strong>.
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Mini Forecast */}
                    <div className="pt-2">
                      <div className="bg-white/[0.02] border border-white/5 rounded-xl overflow-hidden divide-y divide-white/5">
                        {weatherData.forecast.slice(0, 4).map((f: any, i: number) => {
                          const d = new Date(f.date)
                          const dayName = i === 0 ? 'Hoje' : d.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', '')
                          return (
                            <div key={i} className={`flex items-center justify-between p-2.5 ${i === 0 ? 'bg-white/5' : ''}`}>
                              <div className="w-12 text-[10px] font-bold uppercase text-white/80">{dayName}</div>
                              <div className="flex items-center gap-1.5 text-right">
                                <Droplets size={10} className={f.rain > 0 ? "text-blue-400" : "text-white/20"} />
                                <span className="text-[10px] text-white/60 font-mono w-8">{f.rain.toFixed(1)}</span>
                              </div>
                              <div className="flex items-center gap-1.5 justify-end">
                                <span className="text-[11px] font-bold">{Math.round(f.tempMax)}°</span>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                  </div>
                ) : null}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </div>
  )
}
