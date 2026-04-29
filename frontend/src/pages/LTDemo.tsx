import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { UploadCloud, X, MapPin, Zap, Activity, Info, Navigation, Layers, Wind, CloudLightning, ShieldAlert, Cpu, Sun, CloudRain, Droplets, Thermometer, Calendar, Play, Pause } from 'lucide-react'
import { Link } from 'react-router-dom'

// Cores premium da identidade
const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'

interface TowerData {
  name: string;
  coords: [number, number]; // lat, lng
  type?: string;
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
  };
  daily: {
    time: string[];
    temperature_max: number[];
    precipitation_sum: number[];
    weathercode: number[];
  };
}

export default function LTDemo() {
  const [kmlData, setKmlData] = useState<{ towers: TowerData[], segments: SegmentData[] } | null>(null)
  const [loading, setLoading] = useState(false)
  const [mapLoaded, setMapLoaded] = useState(false)
  const [selectedElement, setSelectedElement] = useState<any>(null)
  const [weatherData, setWeatherData] = useState<WeatherData | null>(null)
  const [weatherLoading, setWeatherLoading] = useState(false)
  
  // RainViewer Animation
  const [radarFrames, setRadarFrames] = useState<any[]>([])
  const [currentFrame, setCurrentFrame] = useState(0)
  const [isPlaying, setIsPlaying] = useState(true)

  const mapRef = useRef<HTMLDivElement>(null)
  const leafletMap = useRef<any>(null)
  const radarLayer = useRef<any>(null)

  // 1. Injetar Leaflet via CDN dinamicamente
  useEffect(() => {
    if (!document.getElementById('leaflet-css')) {
      const link = document.createElement('link')
      link.id = 'leaflet-css'
      link.rel = 'stylesheet'
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
      document.head.appendChild(link)
    }

    if (!document.getElementById('leaflet-js')) {
      const script = document.createElement('script')
      script.id = 'leaflet-js'
      script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
      script.onload = () => setMapLoaded(true)
      document.head.appendChild(script)
    } else {
      setMapLoaded(true)
    }

    // Buscar frames do radar
    fetch('https://api.rainviewer.com/public/weather-maps.json')
      .then(res => res.json())
      .then(data => {
        if (data && data.radar && data.radar.past) {
          const frames = [...data.radar.past]
          if (data.radar.nowcast) frames.push(...data.radar.nowcast)
          setRadarFrames(frames)
          setCurrentFrame(frames.length - 1)
        }
      })
      .catch(console.error)

    return () => {
      if (leafletMap.current) leafletMap.current.remove()
    }
  }, [])

  // 2. Loop de animação do Radar
  useEffect(() => {
    let interval: any;
    if (isPlaying && radarFrames.length > 0) {
      interval = setInterval(() => {
        setCurrentFrame(prev => (prev + 1) % radarFrames.length)
      }, 1500) // 1.5s por frame para dar tempo de carregar os tiles
    }
    return () => clearInterval(interval)
  }, [isPlaying, radarFrames])

  // 3. Atualizar mapa e camada de radar
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return
    const L = (window as any).L

    if (!leafletMap.current) {
      leafletMap.current = L.map(mapRef.current, {
        zoomControl: false,
        attributionControl: false
      }).setView([-12.5, -38.5], 8)

      L.control.zoom({ position: 'bottomright' }).addTo(leafletMap.current)

      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19
      }).addTo(leafletMap.current)
    }

    const map = leafletMap.current

    // Atualizar camada do RainViewer animado
    if (radarFrames.length > 0) {
      const frame = radarFrames[currentFrame]
      const url = `https://tilecache.rainviewer.com${frame.path}/256/{z}/{x}/{y}/2/1_1.png`
      
      if (!radarLayer.current) {
        radarLayer.current = L.tileLayer(url, { opacity: 0.6, zIndex: 10 }).addTo(map)
      } else {
        radarLayer.current.setUrl(url)
      }
    }

  }, [mapLoaded, radarFrames, currentFrame])

  // 4. Renderizar o KML quando disponível
  useEffect(() => {
    if (!mapLoaded || !kmlData || !leafletMap.current) return
    const L = (window as any).L
    const map = leafletMap.current

    // Limpar elementos KML antigos
    map.eachLayer((layer: any) => {
      if (layer.options && (layer.options.className === 'custom-tower-marker' || layer.options.className === 'lt-polyline-glow')) {
        map.removeLayer(layer)
      }
    })

    const bounds = L.latLngBounds()
    
    kmlData.segments.forEach(seg => {
      const polyline = L.polyline(seg.coords, {
        color: TEAL,
        weight: 3,
        opacity: 0.8,
        dashArray: '5, 5',
        lineCap: 'round',
        className: 'lt-polyline-glow'
      }).addTo(map)

      polyline.on('click', () => handleElementClick({ type: 'Segmento', name: seg.name, distance: `${(seg.coords.length * 0.1).toFixed(1)} km est.`, coords: seg.coords[0] }))
      seg.coords.forEach(c => bounds.extend(c))
    })

    const towerIcon = L.divIcon({
      className: 'custom-tower-marker',
      html: `<div style="width: 14px; height: 14px; background: ${COPPER}; border: 2px solid #000; border-radius: 50%; box-shadow: 0 0 10px ${COPPER};"></div>`,
      iconSize: [14, 14],
      iconAnchor: [7, 7]
    })

    kmlData.towers.forEach(tower => {
      const marker = L.marker(tower.coords, { icon: towerIcon, zIndexOffset: 100 }).addTo(map)
      bounds.extend(tower.coords)
      
      marker.on('click', () => handleElementClick({ type: 'Torre de Transmissão', name: tower.name, coords: tower.coords }))

      marker.bindTooltip(`
        <div style="background: rgba(10,15,14,0.95); border: 1px solid ${COPPER}40; padding: 8px 12px; border-radius: 8px; font-family: Outfit, sans-serif; color: #fff;">
          <div style="font-size: 10px; font-weight: 800; color: ${COPPER}; letter-spacing: 1px; text-transform: uppercase;">Torre ${tower.name}</div>
          <div style="font-size: 11px; color: rgba(255,255,255,0.7); margin-top: 4px;">Clique para prever o clima local</div>
        </div>
      `, { direction: 'top', className: 'custom-leaflet-tooltip' })
    })

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50] })
    }

  }, [kmlData, mapLoaded])

  // 5. Tratar clique e buscar clima real na API
  const handleElementClick = async (el: any) => {
    setSelectedElement(el)
    setWeatherData(null)
    if (!el.coords) return
    
    setWeatherLoading(true)
    try {
      const lat = el.coords[0]
      const lng = el.coords[1]
      const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&current_weather=true&daily=temperature_2m_max,precipitation_sum,weathercode&timezone=auto`)
      const data = await res.json()
      
      if (data && data.current_weather && data.daily) {
        setWeatherData({
          current: {
            temperature: data.current_weather.temperature,
            windspeed: data.current_weather.windspeed,
            weathercode: data.current_weather.weathercode
          },
          daily: {
            time: data.daily.time,
            temperature_max: data.daily.temperature_2m_max,
            precipitation_sum: data.daily.precipitation_sum,
            weathercode: data.daily.weathercode
          }
        })
      }
    } catch (err) {
      console.error("Erro ao buscar clima", err)
    } finally {
      setWeatherLoading(false)
    }
  }

  // Processador de KML
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setLoading(true)
    const reader = new FileReader()
    reader.onload = (event) => {
      try {
        const text = event.target?.result as string
        const parser = new DOMParser()
        const xmlDoc = parser.parseFromString(text, "text/xml")
        
        const placemarks = xmlDoc.getElementsByTagName('Placemark')
        const parsedTowers: TowerData[] = []
        const parsedSegments: SegmentData[] = []

        for (let i = 0; i < placemarks.length; i++) {
          const pm = placemarks[i]
          const name = pm.getElementsByTagName('name')[0]?.textContent || `Ativo ${i}`
          
          const lineString = pm.getElementsByTagName('LineString')[0]
          if (lineString) {
            const coordsText = lineString.getElementsByTagName('coordinates')[0]?.textContent
            if (coordsText) {
              const coordsStr = coordsText.trim().split(/\s+/)
              const coords: [number, number][] = []
              coordsStr.forEach(c => {
                const parts = c.split(',')
                if (parts.length >= 2) coords.push([parseFloat(parts[1]), parseFloat(parts[0])])
              })
              if (coords.length > 0) {
                parsedSegments.push({ name, coords })
                parsedTowers.push({ name: `${name} (A)`, coords: coords[0] })
              }
            }
          }

          const point = pm.getElementsByTagName('Point')[0]
          if (point) {
            const coordsText = point.getElementsByTagName('coordinates')[0]?.textContent
            if (coordsText) {
              const parts = coordsText.trim().split(',')
              if (parts.length >= 2) parsedTowers.push({ name, coords: [parseFloat(parts[1]), parseFloat(parts[0])] })
            }
          }
        }

        setTimeout(() => {
          setKmlData({ towers: parsedTowers, segments: parsedSegments })
          setLoading(false)
        }, 800)
        
      } catch (err) {
        console.error("Erro ao fazer parse do KML", err)
        setLoading(false)
        alert("Erro ao ler o arquivo KML.")
      }
    }
    reader.readAsText(file)
  }

  // Utilitários de clima
  const getWeatherIcon = (code: number, size = 16) => {
    if (code === 0 || code === 1) return <Sun size={size} className="text-yellow-400" />
    if (code <= 3) return <Wind size={size} className="text-gray-400" />
    if (code >= 60 && code <= 69) return <CloudRain size={size} className="text-blue-400" />
    if (code >= 95) return <CloudLightning size={size} className="text-purple-400" />
    return <CloudRain size={size} className="text-blue-300" />
  }

  const getWeatherText = (code: number) => {
    if (code === 0 || code === 1) return "Céu Limpo"
    if (code <= 3) return "Parc. Nublado"
    if (code >= 60 && code <= 69) return "Chuva"
    if (code >= 95) return "Tempestade"
    return "Instável"
  }

  return (
    <div className="h-screen w-screen bg-[#050808] flex flex-col font-outfit text-white overflow-hidden relative">
      
      <style>{`
        .custom-leaflet-tooltip {
          background: transparent !important;
          border: none !important;
          box-shadow: none !important;
        }
        .custom-leaflet-tooltip::before { display: none !important; }
        .lt-polyline-glow {
          filter: drop-shadow(0 0 6px ${TEAL});
          animation: pulse-line 2s infinite;
        }
        @keyframes pulse-line {
          0% { filter: drop-shadow(0 0 6px ${TEAL}); }
          50% { filter: drop-shadow(0 0 12px ${TEAL}); }
          100% { filter: drop-shadow(0 0 6px ${TEAL}); }
        }
        .leaflet-container { background: #050808 !important; }
      `}</style>

      {/* Header Premium */}
      <header className="h-16 border-b border-white/5 bg-[#0a0f0e]/90 backdrop-blur-xl flex items-center justify-between px-6 z-20 absolute top-0 left-0 right-0">
        <div className="flex items-center gap-4">
          <Link to="/" className="p-2 bg-white/5 rounded-lg hover:bg-white/10 transition-colors">
            <X size={16} className="text-white/60" />
          </Link>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <Layers size={14} style={{ color: COPPER }} />
              <h1 className="text-sm font-black uppercase tracking-widest">Master Meteo-Grid</h1>
              <span className="text-[9px] px-2 py-0.5 rounded-full border border-teal-500/30 bg-teal-500/10 text-teal-400 uppercase font-bold tracking-widest ml-2">API Real-time</span>
            </div>
            <p className="text-[10px] text-white/40 uppercase tracking-widest">Radar Dinâmico & Open-Meteo</p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Controle de Radar */}
          {radarFrames.length > 0 && (
            <div className="flex items-center gap-3 bg-white/5 border border-white/10 px-4 py-1.5 rounded-full">
              <span className="text-[9px] font-bold uppercase tracking-widest text-blue-400 mr-2 flex items-center gap-1">
                <CloudRain size={10} /> Radar Loop
              </span>
              <button onClick={() => setIsPlaying(!isPlaying)} className="text-white hover:text-copper transition-colors">
                {isPlaying ? <Pause size={14} /> : <Play size={14} />}
              </button>
              <div className="w-24 h-1 bg-white/10 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-blue-500 transition-all duration-300" 
                  style={{ width: `${((currentFrame + 1) / radarFrames.length) * 100}%` }}
                />
              </div>
            </div>
          )}

          {kmlData && (
             <div className="flex items-center gap-4 border-l border-white/10 pl-6">
               <div className="flex items-center gap-2">
                 <div className="w-2 h-2 rounded-full" style={{ background: COPPER, boxShadow: `0 0 8px ${COPPER}` }} />
                 <span className="text-[10px] text-white/60 font-bold uppercase">{kmlData.towers.length} Torres</span>
               </div>
             </div>
          )}

          <label className="cursor-pointer bg-copper text-[#0d1117] px-4 py-2 rounded-lg font-bold text-xs uppercase tracking-widest flex items-center gap-2 hover:bg-opacity-90 transition-all shadow-[0_0_20px_rgba(201,139,42,0.3)] ml-4">
            <UploadCloud size={16} />
            {loading ? 'Lendo XML...' : 'Carregar XML / KML'}
            <input type="file" accept=".kml,.xml" className="hidden" onChange={handleFileUpload} />
          </label>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 relative mt-16 flex">
        
        {/* Mapa Container */}
        <div ref={mapRef} className="flex-1 h-full w-full bg-[#050808] z-0 relative">
          {!kmlData && !loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-[#050808]/80 backdrop-blur-sm z-10">
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center max-w-md text-center p-8 border border-white/5 bg-white/[0.02] rounded-3xl">
                <div className="w-16 h-16 rounded-2xl bg-copper/10 border border-copper/20 flex items-center justify-center mb-6">
                  <Wind size={32} className="text-copper" />
                </div>
                <h2 className="text-xl font-black uppercase tracking-widest mb-2">Simulador Geoespacial</h2>
                <p className="text-sm text-white/40 leading-relaxed mb-8">O radar meteorológico já está ativo. Carregue seu arquivo KML para cruzar os dados climáticos reais (Open-Meteo) com a malha da Linha de Transmissão.</p>
              </motion.div>
            </div>
          )}
        </div>

        {/* Sidebar Lateral Flutuante */}
        <AnimatePresence>
          {kmlData && selectedElement && (
            <motion.div
              initial={{ x: 400, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 400, opacity: 0 }}
              transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
              className="w-96 h-full bg-[#0a0f0e]/95 backdrop-blur-2xl border-l border-white/10 z-10 flex flex-col shadow-2xl absolute right-0 top-0 overflow-hidden"
            >
              <div className="p-6 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-teal-500/10 border border-teal-500/20 text-teal-400">
                    <Activity size={18} />
                  </div>
                  <div>
                    <h3 className="text-xs font-black uppercase tracking-widest text-white/90">Asset Telemetry</h3>
                    <p className="text-[9px] font-bold text-teal-500 uppercase tracking-widest">Live Open-Meteo API</p>
                  </div>
                </div>
                <button onClick={() => setSelectedElement(null)} className="p-1.5 rounded-md hover:bg-white/10 text-white/40">
                  <X size={14} />
                </button>
              </div>

              <div className="p-6 flex-1 overflow-y-auto space-y-6">
                <div>
                  <div className="text-[10px] text-white/30 uppercase tracking-[0.2em] font-bold mb-1">Identificação</div>
                  <div className="text-2xl font-display font-black text-white">{selectedElement.name}</div>
                  <div className="text-xs text-copper uppercase font-bold tracking-widest mt-1">{selectedElement.type}</div>
                </div>

                {selectedElement.coords && (
                  <div className="bg-white/5 border border-white/5 rounded-xl p-4 space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-[10px] uppercase font-bold tracking-widest text-white/40">Lat/Lng</span>
                      <span className="text-xs font-mono text-white/80">{selectedElement.coords[0].toFixed(5)}, {selectedElement.coords[1].toFixed(5)}</span>
                    </div>
                  </div>
                )}

                {weatherLoading ? (
                  <div className="h-40 flex flex-col items-center justify-center border border-white/5 rounded-xl bg-white/[0.02]">
                    <div className="w-8 h-8 rounded-full border-t-2 border-copper animate-spin mb-3"></div>
                    <span className="text-[10px] font-bold uppercase tracking-widest text-white/40">Sincronizando com Satélites...</span>
                  </div>
                ) : weatherData ? (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                    
                    {/* Clima Atual */}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-white/5 border border-white/5 rounded-xl p-4 flex flex-col items-center justify-center text-center">
                        <div className="text-[9px] text-white/40 uppercase tracking-widest font-bold mb-2 w-full text-left">Condição Real</div>
                        <div className="my-2">
                          {getWeatherIcon(weatherData.current.weathercode, 32)}
                        </div>
                        <span className="text-sm font-bold text-white/90">{getWeatherText(weatherData.current.weathercode)}</span>
                      </div>
                      
                      <div className="flex flex-col gap-3">
                        <div className="bg-white/5 border border-white/5 rounded-xl p-3 flex-1 flex flex-col justify-center">
                          <div className="flex items-center gap-2 mb-1">
                            <Thermometer size={12} className="text-copper" />
                            <span className="text-[9px] text-white/40 uppercase tracking-widest font-bold">Temperatura</span>
                          </div>
                          <span className="text-lg font-black">{weatherData.current.temperature}°C</span>
                        </div>
                        <div className="bg-white/5 border border-white/5 rounded-xl p-3 flex-1 flex flex-col justify-center">
                          <div className="flex items-center gap-2 mb-1">
                            <Wind size={12} className="text-blue-400" />
                            <span className="text-[9px] text-white/40 uppercase tracking-widest font-bold">Vento</span>
                          </div>
                          <span className="text-lg font-black">{weatherData.current.windspeed} <span className="text-xs text-white/40">km/h</span></span>
                        </div>
                      </div>
                    </div>

                    {/* Previsão 7 Dias */}
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <Calendar size={14} className="text-teal-400" />
                        <h4 className="text-[10px] uppercase font-black tracking-widest text-white/60">Previsão 7 Dias</h4>
                      </div>
                      <div className="space-y-2">
                        {weatherData.daily.time.slice(0, 5).map((dateStr, idx) => {
                          const date = new Date(dateStr)
                          const isToday = idx === 0
                          return (
                            <div key={dateStr} className={`flex items-center justify-between p-2 rounded-lg border ${isToday ? 'bg-teal-500/10 border-teal-500/20' : 'bg-white/5 border-white/5'}`}>
                              <span className={`text-xs font-bold ${isToday ? 'text-teal-400' : 'text-white/60'}`}>
                                {isToday ? 'Hoje' : date.toLocaleDateString('pt-BR', { weekday: 'short' }).toUpperCase()}
                              </span>
                              <div className="flex items-center gap-4">
                                <div className="flex items-center gap-1 w-12 justify-end">
                                  <Droplets size={10} className="text-blue-400" />
                                  <span className="text-[10px] text-white/70">{weatherData.daily.precipitation_sum[idx]}mm</span>
                                </div>
                                <div className="flex items-center justify-center w-6">
                                  {getWeatherIcon(weatherData.daily.weathercode[idx], 14)}
                                </div>
                                <span className="text-xs font-mono font-bold text-white/90 w-8 text-right">{weatherData.daily.temperature_max[idx]}°</span>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    {/* Alerta Inteligente Baseado na Chuva */}
                    {weatherData.daily.precipitation_sum[0] > 5 || weatherData.daily.precipitation_sum[1] > 5 ? (
                      <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
                        <div className="flex items-start gap-3">
                          <ShieldAlert size={16} className="text-red-400 shrink-0 mt-0.5" />
                          <div>
                            <h4 className="text-[10px] uppercase font-black tracking-widest text-red-400 mb-1">Risco Operacional</h4>
                            <p className="text-xs text-white/70 leading-relaxed">
                              Previsão de chuva forte na região deste ativo. Recomenda-se pausa técnica em fundações ou trabalhos em altura.
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="bg-teal-500/10 border border-teal-500/20 rounded-xl p-4">
                        <div className="flex items-start gap-3">
                          <Info size={16} className="text-teal-400 shrink-0 mt-0.5" />
                          <div>
                            <h4 className="text-[10px] uppercase font-black tracking-widest text-teal-400 mb-1">Janela Operacional</h4>
                            <p className="text-xs text-white/70 leading-relaxed">
                              Condições favoráveis para intervenção nesta torre nos próximos 3 dias.
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                  </motion.div>
                ) : null}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </div>
  )
}
