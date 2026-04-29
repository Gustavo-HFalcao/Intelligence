import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { UploadCloud, X, MapPin, Zap, Activity, Info, Navigation, Layers, Wind, CloudLightning, ShieldAlert, Cpu } from 'lucide-react'
import { Link } from 'react-router-dom'

// Cores premium da identidade
const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'

interface TowerData {
  name: string;
  coords: [number, number]; // lat, lng
  type?: string;
  details?: Record<string, string>;
}

interface SegmentData {
  name: string;
  coords: [number, number][];
}

export default function LTDemo() {
  const [kmlData, setKmlData] = useState<{ towers: TowerData[], segments: SegmentData[] } | null>(null)
  const [loading, setLoading] = useState(false)
  const [mapLoaded, setMapLoaded] = useState(false)
  const [selectedElement, setSelectedElement] = useState<any>(null)
  const mapRef = useRef<HTMLDivElement>(null)
  const leafletMap = useRef<any>(null)

  // Injetar Leaflet via CDN dinamicamente
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

    return () => {
      if (leafletMap.current) {
        leafletMap.current.remove()
      }
    }
  }, [])

  // Atualizar mapa quando os dados do KML ou o Leaflet estiverem carregados
  useEffect(() => {
    if (!mapLoaded || !kmlData || !mapRef.current) return
    const L = (window as any).L

    if (!leafletMap.current) {
      // Inicializar mapa
      leafletMap.current = L.map(mapRef.current, {
        zoomControl: false,
        attributionControl: false
      }).setView([-12.5, -38.5], 8) // Fallback center

      // Adicionar controle de zoom customizado
      L.control.zoom({ position: 'bottomright' }).addTo(leafletMap.current)

      // TileLayer escuro premium (CartoDB Dark Matter)
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19
      }).addTo(leafletMap.current)

      // Camada meteorológica de simulação (Precipitação do OpenWeatherMap - free genérico se disponível, ou uma camada de nuvens base)
      // Aqui usamos um tile de chuva público para dar o efeito "Windy"
      L.tileLayer('https://tile.openweathermap.org/map/precipitation_new/{z}/{x}/{y}.png?appid=9fd7a449d055dba26a982a3220f32aa2', {
        maxZoom: 19,
        opacity: 0.5
      }).addTo(leafletMap.current)
    }

    const map = leafletMap.current

    // Limpar camadas antigas
    map.eachLayer((layer: any) => {
      if (!layer._url) map.removeLayer(layer)
    })

    const bounds = L.latLngBounds()
    
    // Renderizar Segmentos (Linha de Transmissão)
    kmlData.segments.forEach(seg => {
      const polyline = L.polyline(seg.coords, {
        color: TEAL,
        weight: 3,
        opacity: 0.8,
        dashArray: '5, 5',
        lineCap: 'round',
        className: 'lt-polyline-glow' // Efeito CSS
      }).addTo(map)

      polyline.on('click', () => {
        setSelectedElement({ type: 'Segmento', name: seg.name, distance: `${(seg.coords.length * 0.1).toFixed(1)} km est.` })
      })

      seg.coords.forEach(c => bounds.extend(c))
    })

    // Ícone customizado estilo "Torre"
    const towerIcon = L.divIcon({
      className: 'custom-tower-marker',
      html: `<div style="width: 14px; height: 14px; background: ${COPPER}; border: 2px solid #000; border-radius: 50%; box-shadow: 0 0 10px ${COPPER};"></div>`,
      iconSize: [14, 14],
      iconAnchor: [7, 7]
    })

    // Renderizar Torres (Placemarks do tipo Ponto, ou o primeiro ponto de cada segmento se não houver pontos explícitos)
    kmlData.towers.forEach(tower => {
      const marker = L.marker(tower.coords, { icon: towerIcon }).addTo(map)
      bounds.extend(tower.coords)
      
      marker.on('click', () => {
        setSelectedElement({ type: 'Torre de Transmissão', name: tower.name, coords: tower.coords })
      })

      // Tooltip hover
      marker.bindTooltip(`
        <div style="background: rgba(10,15,14,0.95); border: 1px solid ${COPPER}40; padding: 8px 12px; border-radius: 8px; font-family: Outfit, sans-serif; color: #fff;">
          <div style="font-size: 10px; font-weight: 800; color: ${COPPER}; letter-spacing: 1px; text-transform: uppercase;">Torre ${tower.name}</div>
          <div style="font-size: 11px; color: rgba(255,255,255,0.7); margin-top: 4px;">Ativo Crítico</div>
        </div>
      `, { direction: 'top', className: 'custom-leaflet-tooltip' })
    })

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50] })
    }

  }, [kmlData, mapLoaded])

  // Processador de KML em memória
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
          
          // Buscar LineString
          const lineString = pm.getElementsByTagName('LineString')[0]
          if (lineString) {
            const coordsText = lineString.getElementsByTagName('coordinates')[0]?.textContent
            if (coordsText) {
              const coordsStr = coordsText.trim().split(/\s+/)
              const coords: [number, number][] = []
              coordsStr.forEach(c => {
                const parts = c.split(',')
                if (parts.length >= 2) {
                  // KML é lng, lat
                  coords.push([parseFloat(parts[1]), parseFloat(parts[0])])
                }
              })
              if (coords.length > 0) {
                parsedSegments.push({ name, coords })
                // Criar torres no início e fim do segmento para simulação se não houver pontos isolados
                parsedTowers.push({ name: `${name} (A)`, coords: coords[0] })
              }
            }
          }

          // Buscar Point (se existirem separadamente)
          const point = pm.getElementsByTagName('Point')[0]
          if (point) {
            const coordsText = point.getElementsByTagName('coordinates')[0]?.textContent
            if (coordsText) {
              const parts = coordsText.trim().split(',')
              if (parts.length >= 2) {
                parsedTowers.push({ name, coords: [parseFloat(parts[1]), parseFloat(parts[0])] })
              }
            }
          }
        }

        setTimeout(() => {
          setKmlData({ towers: parsedTowers, segments: parsedSegments })
          setLoading(false)
        }, 800) // Simular processamento pesado
        
      } catch (err) {
        console.error("Erro ao fazer parse do KML", err)
        setLoading(false)
        alert("Erro ao ler o arquivo KML.")
      }
    }
    reader.readAsText(file)
  }

  return (
    <div className="h-screen w-screen bg-[#050808] flex flex-col font-outfit text-white overflow-hidden relative">
      
      {/* Estilos injetados para o tooltip do Leaflet */}
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
      `}</style>

      {/* Header Premium */}
      <header className="h-16 border-b border-white/5 bg-white/[0.02] backdrop-blur-xl flex items-center justify-between px-6 z-20 absolute top-0 left-0 right-0">
        <div className="flex items-center gap-4">
          <Link to="/" className="p-2 bg-white/5 rounded-lg hover:bg-white/10 transition-colors">
            <X size={16} className="text-white/60" />
          </Link>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <ShieldAlert size={14} style={{ color: COPPER }} />
              <h1 className="text-sm font-black uppercase tracking-widest">Windy LT Integration</h1>
              <span className="text-[9px] px-2 py-0.5 rounded-full border border-teal-500/30 bg-teal-500/10 text-teal-400 uppercase font-bold tracking-widest ml-2">Demo Technique</span>
            </div>
            <p className="text-[10px] text-white/40 uppercase tracking-widest">Inteligência Geoespacial de Ativos Críticos</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {kmlData && (
             <div className="flex items-center gap-4 mr-4">
               <div className="flex items-center gap-2">
                 <div className="w-2 h-2 rounded-full" style={{ background: COPPER, boxShadow: `0 0 8px ${COPPER}` }} />
                 <span className="text-[10px] text-white/60 font-bold uppercase">{kmlData.towers.length} Torres</span>
               </div>
               <div className="flex items-center gap-2">
                 <div className="w-4 h-1" style={{ background: TEAL, boxShadow: `0 0 8px ${TEAL}` }} />
                 <span className="text-[10px] text-white/60 font-bold uppercase">{kmlData.segments.length} Segmentos</span>
               </div>
             </div>
          )}
          <label className="cursor-pointer bg-copper text-[#0d1117] px-4 py-2 rounded-lg font-bold text-xs uppercase tracking-widest flex items-center gap-2 hover:bg-opacity-90 transition-all shadow-[0_0_20px_rgba(201,139,42,0.3)]">
            <UploadCloud size={16} />
            {loading ? 'Processando...' : 'Carregar XML / KML'}
            <input type="file" accept=".kml,.xml" className="hidden" onChange={handleFileUpload} />
          </label>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 relative mt-16 flex">
        
        {/* Mapa Container */}
        <div ref={mapRef} className="flex-1 h-full w-full bg-[#0a0f0e] z-0 relative">
          {!kmlData && !loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-[#050808]/80 backdrop-blur-sm z-10">
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center max-w-md text-center p-8 border border-white/5 bg-white/[0.02] rounded-3xl">
                <div className="w-16 h-16 rounded-2xl bg-copper/10 border border-copper/20 flex items-center justify-center mb-6">
                  <Wind size={32} className="text-copper" />
                </div>
                <h2 className="text-xl font-black uppercase tracking-widest mb-2">Simulador Geoespacial</h2>
                <p className="text-sm text-white/40 leading-relaxed mb-8">Faça o upload do arquivo KML da Linha de Transmissão para visualizar o mapeamento de ativos críticos sobre a camada de radar meteorológico.</p>
                <label className="cursor-pointer border border-white/10 bg-white/5 hover:bg-white/10 text-white px-6 py-3 rounded-xl font-bold text-xs uppercase tracking-widest flex items-center gap-2 transition-all">
                  <UploadCloud size={16} className="text-copper" />
                  Selecionar Arquivo KML
                  <input type="file" accept=".kml,.xml" className="hidden" onChange={handleFileUpload} />
                </label>
              </motion.div>
            </div>
          )}
          
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-[#050808]/80 backdrop-blur-md z-10">
              <div className="flex flex-col items-center">
                <div className="relative w-16 h-16 flex items-center justify-center mb-4">
                  <div className="absolute inset-0 rounded-full border-t-2 border-copper animate-spin"></div>
                  <Cpu size={24} className="text-copper opacity-50" />
                </div>
                <div className="text-xs uppercase tracking-[0.3em] font-black text-copper animate-pulse">Processando Nodos Espaciais...</div>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar Lateral Flutuante com Metadados da Torre Selecionada */}
        <AnimatePresence>
          {kmlData && selectedElement && (
            <motion.div
              initial={{ x: 400, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 400, opacity: 0 }}
              transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
              className="w-80 h-full bg-[#0a0f0e]/95 backdrop-blur-2xl border-l border-white/10 z-10 flex flex-col shadow-2xl absolute right-0 top-0"
            >
              <div className="p-6 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-teal-500/10 border border-teal-500/20 text-teal-400">
                    <Activity size={18} />
                  </div>
                  <div>
                    <h3 className="text-xs font-black uppercase tracking-widest text-white/90">Asset Telemetry</h3>
                    <p className="text-[9px] font-bold text-teal-500 uppercase tracking-widest">Real-time status</p>
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

                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-white/5 border border-white/5 rounded-xl p-4">
                    <div className="text-[9px] text-white/40 uppercase tracking-widest font-bold mb-2">Clima Atual</div>
                    <div className="flex items-center gap-2">
                      <CloudLightning size={16} className="text-blue-400" />
                      <span className="text-sm font-bold">Chuva</span>
                    </div>
                  </div>
                  <div className="bg-white/5 border border-white/5 rounded-xl p-4">
                    <div className="text-[9px] text-white/40 uppercase tracking-widest font-bold mb-2">Risco</div>
                    <div className="flex items-center gap-2">
                      <ShieldAlert size={16} className="text-red-400" />
                      <span className="text-sm font-bold text-red-400">Alto</span>
                    </div>
                  </div>
                </div>

                {selectedElement.coords && (
                  <div className="bg-white/5 border border-white/5 rounded-xl p-4 space-y-3">
                    <div className="flex items-center gap-2 mb-2">
                      <Navigation size={14} className="text-white/40" />
                      <span className="text-[10px] uppercase font-bold tracking-widest text-white/40">Coordenadas Gps</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <span className="text-xs text-white/50">Latitude</span>
                      <span className="text-xs font-mono font-bold">{selectedElement.coords[0].toFixed(5)}°</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-white/50">Longitude</span>
                      <span className="text-xs font-mono font-bold">{selectedElement.coords[1].toFixed(5)}°</span>
                    </div>
                  </div>
                )}

                <div className="bg-copper/10 border border-copper/20 rounded-xl p-4">
                  <div className="flex items-start gap-3">
                    <Info size={16} className="text-copper shrink-0 mt-0.5" />
                    <div>
                      <h4 className="text-[10px] uppercase font-black tracking-widest text-copper mb-1">Insight Inteligente</h4>
                      <p className="text-xs text-white/70 leading-relaxed">
                        A previsão meteorológica para o quadrante desta estrutura indica alto volume pluviométrico nas próximas 48h. Aconselha-se suspender manutenções de fundação.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </div>
  )
}
