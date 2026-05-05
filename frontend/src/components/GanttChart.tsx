import { useMemo, useState, useRef } from 'react'
import { format, differenceInDays, addDays, eachDayOfInterval, isWeekend, isSameDay } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { AlertTriangle, CheckCircle, Clock, TrendingDown, TrendingUp, Minus } from 'lucide-react'

interface GanttRow {
  label: string
  start_iso: string
  end_iso: string
  forecast_start?: string
  forecast_end?: string
  pct: string
  critico: string
  nivel: 'macro' | 'micro' | 'sub'
  color?: string
  responsavel?: string
  fase?: string
}

interface GanttChartProps {
  data: GanttRow[]
  referenceDate?: string
}

// Layout constants
const ROW_HEIGHT  = 56

const LABEL_W     = 280
const DAY_W       = 38

const COPPER = '#C98B2A'
const TEAL   = '#2A9D8F'
const RED    = '#EF4444'

function safeDate(iso: string | null | undefined): Date | null {
  if (!iso) return null
  // Parse YYYY-MM-DD as local date to avoid UTC midnight → -3h shifting the day
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (m) return new Date(+m[1], +m[2] - 1, +m[3])
  const d = new Date(iso)
  return isNaN(d.getTime()) ? null : d
}

function isCriticoFlag(v: any): boolean {
  if (!v) return false
  if (typeof v === 'boolean') return v
  return String(v).toLowerCase() === 'sim' || String(v) === '1' || String(v).toLowerCase() === 'true'
}

// Floating tooltip rendered via portal-like absolute positioning relative to chart
interface TooltipState {
  visible: boolean
  x: number
  y: number
  row: GanttRow
  s_plan: Date
  e_plan: Date
  s_real: Date
  e_real: Date
  pct: number
  isCritico: boolean
  desvio: number
}

export default function GanttChart({ data, referenceDate }: GanttChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  // Use last_rdo_d as reference date when provided; fall back to real today only if absent
  const refToday = referenceDate ? (safeDate(referenceDate) ?? new Date()) : new Date()

  // Filter rows with valid dates
  const validData = useMemo(() =>
    data.filter(d => {
      const s = safeDate(d.start_iso)
      const e = safeDate(d.end_iso)
      return s && e && differenceInDays(e, s) >= 0
    }),
  [data])

  // Compute timeline range
  const { startDate, daysCount, timelineDays } = useMemo(() => {
    const today = refToday
    if (validData.length === 0) {
      const end = addDays(today, 30)
      return { startDate: today, daysCount: 31, timelineDays: eachDayOfInterval({ start: today, end }) }
    }
    const allDates: Date[] = []
    validData.forEach(d => {
      const s = safeDate(d.start_iso); const e = safeDate(d.end_iso)
      const fs = safeDate(d.forecast_start ?? null); const fe = safeDate(d.forecast_end ?? null)
      if (s) allDates.push(s); if (e) allDates.push(e)
      if (fs) allDates.push(fs); if (fe) allDates.push(fe)
    })
    if (allDates.length === 0) {
      const end = addDays(today, 30)
      return { startDate: today, daysCount: 31, timelineDays: eachDayOfInterval({ start: today, end }) }
    }
    const minTs = Math.min(...allDates.map(d => d.getTime()))
    const maxTs = Math.max(...allDates.map(d => d.getTime()))
    const start = addDays(new Date(minTs), -4)
    const end   = addDays(new Date(maxTs), 12)
    const days  = differenceInDays(end, start) + 1
    return { startDate: start, daysCount: days, timelineDays: eachDayOfInterval({ start, end }) }
  }, [validData])

  // Group months for header
  const monthGroups = useMemo(() => {
    const groups: { label: string; count: number }[] = []
    let cur = ''
    let count = 0
    timelineDays.forEach((d: Date) => {
      const label = format(d, 'MMM yyyy', { locale: ptBR }).toUpperCase()
      if (label === cur) { count++ }
      else {
        if (cur) groups.push({ label: cur, count })
        cur = label; count = 1
      }
    })
    if (cur) groups.push({ label: cur, count })
    return groups
  }, [timelineDays])

  if (validData.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3 text-white/20">
        <Clock size={32} className="opacity-30" />
        <span className="text-sm font-black uppercase tracking-widest">Nenhuma atividade com datas definidas</span>
        <span className="text-xs">Cadastre início e término nas atividades para visualizar o Gantt</span>
      </div>
    )
  }

  const chartW  = daysCount * DAY_W
  const bodyH   = validData.length * ROW_HEIGHT
  const todayX  = differenceInDays(refToday, startDate) * DAY_W + DAY_W

  function handleMouseMove(e: React.MouseEvent, row: GanttRow, _rowIdx: number) {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const s_plan = safeDate(row.start_iso)!
    const e_plan = safeDate(row.end_iso)!
    const s_real = safeDate(row.forecast_start ?? null) ?? s_plan
    const e_real = safeDate(row.forecast_end ?? null) ?? e_plan
    const pct    = Math.min(100, Math.max(0, parseInt(row.pct) || 0))
    const isCrit = isCriticoFlag(row.critico)
    const today  = refToday
    const planned_days = differenceInDays(e_plan, s_plan) + 1
    const elapsed      = Math.max(0, differenceInDays(today, s_plan))
    const pct_esperado = planned_days > 0 ? Math.min(100, Math.round(elapsed / planned_days * 100)) : 0
    const desvio       = pct - pct_esperado
    // Position tooltip so it never clips outside container
    const cx = e.clientX - rect.left
    const cy = e.clientY - rect.top
    const tipW = 280
    const tipH = 220
    const x = cx + tipW + 16 > rect.width ? cx - tipW - 8 : cx + 16
    const y = cy + tipH > rect.height ? cy - tipH : cy

    setTooltip({ visible: true, x, y, row, s_plan, e_plan, s_real, e_real, pct, isCritico: isCrit, desvio })
  }

  function handleMouseLeave() {
    setTooltip(null)
  }

  return (
    <div ref={containerRef} className="relative select-none" style={{ fontFamily: 'Outfit, sans-serif' }}>
      {/* ── FLOATING TOOLTIP ───────────────────────────────────────────────── */}
      {tooltip?.visible && (
        <div
          style={{
            position: 'absolute',
            left: tooltip.x,
            top: tooltip.y,
            zIndex: 9999,
            pointerEvents: 'none',
            width: 280,
          }}
        >
          <div style={{
            background: 'linear-gradient(135deg, #0a1510 0%, #081210 100%)',
            border: `1px solid ${tooltip.isCritico ? 'rgba(239,68,68,0.4)' : 'rgba(201,139,42,0.35)'}`,
            borderRadius: 14,
            padding: '14px 16px',
            boxShadow: `0 20px 60px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.04), 0 0 24px ${tooltip.isCritico ? 'rgba(239,68,68,0.08)' : 'rgba(201,139,42,0.06)'}`,
          }}>
            {/* Title row */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10, gap: 8 }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 800, color: '#fff', textTransform: 'uppercase', letterSpacing: '0.08em', lineHeight: 1.3 }}>
                  {tooltip.row.label}
                </div>
                {tooltip.row.fase && (
                  <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.15em', marginTop: 2 }}>
                    {tooltip.row.fase}
                  </div>
                )}
              </div>
              {tooltip.isCritico && (
                <span style={{ fontSize: 9, fontWeight: 800, color: RED, background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 6, padding: '2px 7px', whiteSpace: 'nowrap', textTransform: 'uppercase' }}>
                  CRÍTICO
                </span>
              )}
            </div>

            {/* Progress bar */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
                <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.12em' }}>Progresso Realizado</span>
                <span style={{ fontSize: 14, fontWeight: 900, color: tooltip.pct >= 100 ? TEAL : COPPER, fontFamily: 'monospace' }}>{tooltip.pct}%</span>
              </div>
              <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
                <div style={{
                  height: '100%',
                  width: `${tooltip.pct}%`,
                  background: tooltip.pct >= 100 ? TEAL : tooltip.isCritico ? RED : COPPER,
                  borderRadius: 99,
                  transition: 'width 0.3s ease',
                }} />
              </div>
            </div>

            {/* Date grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px', marginBottom: 10 }}>
              <InfoLine label="Início Baseline" value={format(tooltip.s_plan, 'dd/MM/yy')} mono />
              <InfoLine label="Término Baseline" value={format(tooltip.e_plan, 'dd/MM/yy')} mono />
              {!isSameDay(tooltip.s_real, tooltip.s_plan) && (
                <InfoLine label="Início Previsto" value={format(tooltip.s_real, 'dd/MM/yy')} mono accent={COPPER} />
              )}
              <InfoLine
                label="Conclusão EAC"
                value={format(tooltip.e_real, 'dd/MM/yy')}
                mono
                accent={differenceInDays(tooltip.e_real, tooltip.e_plan) > 0 ? RED : TEAL}
              />
              <InfoLine
                label="Duração"
                value={`${differenceInDays(tooltip.e_plan, tooltip.s_plan) + 1} dias`}
                mono
              />
              {tooltip.row.responsavel && (
                <InfoLine label="Responsável" value={tooltip.row.responsavel} />
              )}
            </div>

            {/* Desvio badge */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '7px 10px',
              borderRadius: 8,
              background: tooltip.desvio >= 0 ? 'rgba(42,157,143,0.1)' : 'rgba(239,68,68,0.08)',
              border: `1px solid ${tooltip.desvio >= 0 ? 'rgba(42,157,143,0.25)' : 'rgba(239,68,68,0.2)'}`,
            }}>
              {tooltip.desvio > 5
                ? <TrendingUp size={13} style={{ color: TEAL, flexShrink: 0 }} />
                : tooltip.desvio < -5
                  ? <TrendingDown size={13} style={{ color: RED, flexShrink: 0 }} />
                  : <Minus size={13} style={{ color: '#888', flexShrink: 0 }} />
              }
              <span style={{ fontSize: 10, fontWeight: 700, color: tooltip.desvio >= 0 ? TEAL : RED }}>
                {tooltip.desvio >= 0 ? '+' : ''}{tooltip.desvio}% vs planejado
              </span>
              <span style={{ marginLeft: 'auto', fontSize: 9, color: 'rgba(255,255,255,0.3)', fontWeight: 700, textTransform: 'uppercase' }}>
                {tooltip.desvio > 5 ? 'ADIANTADO' : tooltip.desvio < -10 ? 'EM RISCO' : tooltip.desvio < 0 ? 'ATENÇÃO' : 'NO PRAZO'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── GANTT FRAME ────────────────────────────────────────────────────── */}
      <div style={{
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 16,
        background: '#07100e',
        overflow: 'hidden',
        boxShadow: '0 4px 40px rgba(0,0,0,0.4)',
      }}>

        {/* DOUBLE HEADER: Month row + Day row */}
        <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
          {/* Label column header */}
          <div style={{
            width: LABEL_W, flexShrink: 0,
            borderRight: '1px solid rgba(255,255,255,0.07)',
            background: 'rgba(255,255,255,0.02)',
            display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', padding: '8px 20px 6px',
          }}>
            <span style={{ fontSize: 9, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.2em', color: COPPER }}>Atividades</span>
            <span style={{ fontSize: 8, color: 'rgba(255,255,255,0.2)', marginTop: 2, fontWeight: 600 }}>{validData.length} entradas</span>
          </div>

          {/* Timeline scrollable header */}
          <div style={{ flex: 1, overflowX: 'auto', overflowY: 'hidden' }} id="gantt-header-scroll">
            <div style={{ width: chartW }}>
              {/* Month row */}
              <div style={{ display: 'flex', height: 28, borderBottom: '1px solid rgba(255,255,255,0.04)', background: 'rgba(255,255,255,0.01)' }}>
                {monthGroups.map((g, i) => (
                  <div key={i} style={{ width: g.count * DAY_W, flexShrink: 0, display: 'flex', alignItems: 'center', paddingLeft: 8, borderRight: '1px solid rgba(255,255,255,0.04)' }}>
                    <span style={{ fontSize: 9, fontWeight: 900, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.12em', whiteSpace: 'nowrap' }}>{g.label}</span>
                  </div>
                ))}
              </div>
              {/* Day row */}
              <div style={{ display: 'flex', height: 36 }}>
                {timelineDays.map((day: Date, i: number) => {
                  const weekend = isWeekend(day)
                  const todayDay = isSameDay(day, refToday)
                  return (
                    <div key={i} style={{
                      width: DAY_W, flexShrink: 0, height: '100%',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                      borderRight: '1px solid rgba(255,255,255,0.025)',
                      background: todayDay ? 'rgba(201,139,42,0.12)' : weekend ? 'rgba(255,255,255,0.012)' : 'transparent',
                      position: 'relative',
                    }}>
                      <span style={{
                        fontSize: 11, fontWeight: todayDay ? 900 : 600,
                        color: todayDay ? COPPER : weekend ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.45)',
                        lineHeight: 1,
                      }}>
                        {format(day, 'd')}
                      </span>
                      <span style={{
                        fontSize: 8, fontWeight: 800,
                        color: todayDay ? `${COPPER}90` : 'rgba(255,255,255,0.15)',
                        textTransform: 'uppercase', letterSpacing: '0.05em',
                      }}>
                        {format(day, 'eee', { locale: ptBR })}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        {/* BODY */}
        <div style={{ display: 'flex', height: bodyH }}>
          {/* Labels column */}
          <div style={{
            width: LABEL_W, flexShrink: 0, height: bodyH,
            borderRight: '1px solid rgba(255,255,255,0.06)',
            background: 'rgba(0,0,0,0.2)',
            overflow: 'hidden',
          }}>
            {validData.map((row, i) => {
              const pct    = Math.min(100, Math.max(0, parseInt(row.pct) || 0))
              const isCrit = isCriticoFlag(row.critico)
              const isMacro = row.nivel === 'macro'
              const isSubrow = row.nivel === 'sub'
              return (
                <div key={i} style={{
                  height: ROW_HEIGHT,
                  display: 'flex', alignItems: 'center',
                  paddingLeft: isMacro ? 16 : isSubrow ? 36 : 28,
                  paddingRight: 12,
                  borderBottom: '1px solid rgba(255,255,255,0.03)',
                  background: i % 2 === 0 ? 'rgba(255,255,255,0.005)' : 'transparent',
                  gap: 8,
                }}>
                  {/* Level indicator */}
                  {isMacro && (
                    <div style={{ width: 3, height: 26, borderRadius: 2, background: isCrit ? RED : COPPER, flexShrink: 0 }} />
                  )}
                  {!isMacro && (
                    <div style={{ width: 2, height: 16, borderRadius: 2, background: 'rgba(255,255,255,0.1)', flexShrink: 0 }} />
                  )}

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: isMacro ? 11 : 10,
                      fontWeight: isMacro ? 800 : 600,
                      color: isCrit ? '#fca5a5' : isMacro ? '#ffffff' : 'rgba(255,255,255,0.7)',
                      textTransform: 'uppercase',
                      letterSpacing: isMacro ? '0.05em' : '0.03em',
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      lineHeight: 1.2,
                    }}>
                      {row.label}
                    </div>
                    {/* Mini progress bar under label */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 4 }}>
                      <div style={{ flex: 1, height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
                        <div style={{
                          width: `${pct}%`, height: '100%',
                          background: pct >= 100 ? TEAL : isCrit ? RED : COPPER,
                          borderRadius: 99,
                        }} />
                      </div>
                      <span style={{ fontSize: 8, fontWeight: 800, color: pct >= 100 ? TEAL : isCrit ? RED : COPPER, fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                        {pct}%
                      </span>
                      {pct >= 100 && <CheckCircle size={9} style={{ color: TEAL, flexShrink: 0 }} />}
                      {isCrit && pct < 100 && <AlertTriangle size={9} style={{ color: RED, flexShrink: 0 }} />}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Chart scrollable area */}
          <div style={{ flex: 1, overflowX: 'auto', overflowY: 'hidden' }} id="gantt-body-scroll">
            <div style={{ width: chartW, height: bodyH, position: 'relative' }}>

              {/* Vertical grid lines */}
              {timelineDays.map((day: Date, i: number) => {
                const weekend = isWeekend(day)
                const todayDay = isSameDay(day, refToday)
                if (!weekend && !todayDay && i % 7 !== 0) return null
                return (
                  <div key={i} style={{
                    position: 'absolute', left: i * DAY_W, top: 0, width: DAY_W, height: bodyH,
                    background: todayDay ? 'rgba(201,139,42,0.06)' : weekend ? 'rgba(255,255,255,0.008)' : undefined,
                    borderRight: i % 7 === 0 ? '1px solid rgba(255,255,255,0.04)' : undefined,
                    pointerEvents: 'none',
                  }} />
                )
              })}

              {/* Today vertical line */}
              {todayX > 0 && todayX < chartW && (
                <div style={{
                  position: 'absolute', left: todayX, top: 0, width: 2, height: bodyH,
                  background: `linear-gradient(180deg, ${COPPER}00 0%, ${COPPER}80 15%, ${COPPER}80 85%, ${COPPER}00 100%)`,
                  zIndex: 4, pointerEvents: 'none',
                }}>
                  <div style={{
                    position: 'absolute', top: 6, left: '50%', transform: 'translateX(-50%)',
                    background: COPPER, color: '#0d1117', fontSize: 8, fontWeight: 900,
                    padding: '2px 5px', borderRadius: 4, whiteSpace: 'nowrap', letterSpacing: '0.05em',
                  }}>
                    HOJE
                  </div>
                </div>
              )}

              {/* Rows */}
              {validData.map((row, i) => {
                const s_plan = safeDate(row.start_iso)!
                const e_plan = safeDate(row.end_iso)!
                const s_real = safeDate(row.forecast_start ?? null) ?? s_plan
                const e_real = safeDate(row.forecast_end ?? null) ?? e_plan

                const x_plan = differenceInDays(s_plan, startDate) * DAY_W
                const w_plan = Math.max(DAY_W * 0.8, (differenceInDays(e_plan, s_plan) + 1) * DAY_W)
                const x_real = differenceInDays(s_real, startDate) * DAY_W
                const w_real = Math.max(DAY_W * 0.8, (differenceInDays(e_real, s_real) + 1) * DAY_W)

                const pct      = Math.min(100, Math.max(0, parseInt(row.pct) || 0))
                const isCrit   = isCriticoFlag(row.critico)
                const isMacro  = row.nivel === 'macro'
                const barColor = isCrit ? RED : (row.color || COPPER)
                const rowTop   = i * ROW_HEIGHT

                const hasDelay = differenceInDays(e_real, e_plan) > 0
                const isLate   = refToday > e_plan && pct < 100

                return (
                  <div
                    key={i}
                    style={{
                      position: 'absolute', top: rowTop, left: 0, right: 0, height: ROW_HEIGHT,
                      cursor: 'crosshair',
                      background: i % 2 === 0 ? 'rgba(255,255,255,0.004)' : 'transparent',
                      borderBottom: '1px solid rgba(255,255,255,0.025)',
                    }}
                    onMouseMove={e => handleMouseMove(e, row, i)}
                    onMouseLeave={handleMouseLeave}
                  >
                    {/* Baseline bar (ghost background) */}
                    <div style={{
                      position: 'absolute',
                      left: x_plan, top: '50%', marginTop: -4,
                      width: w_plan, height: 8,
                      background: 'rgba(255,255,255,0.05)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: 4,
                    }} />

                    {/* Main bar (actual/forecast) */}
                    <div style={{
                      position: 'absolute',
                      left: x_real,
                      top: '50%', marginTop: isMacro ? -10 : -8,
                      width: w_real,
                      height: isMacro ? 20 : 16,
                      background: isLate
                        ? 'rgba(239,68,68,0.12)'
                        : `${barColor}15`,
                      border: `1.5px solid ${isLate ? 'rgba(239,68,68,0.5)' : barColor + '55'}`,
                      borderRadius: isMacro ? 5 : 4,
                      overflow: 'hidden',
                      boxShadow: pct >= 100 ? `0 0 8px ${TEAL}30` : isCrit ? `0 0 6px ${RED}20` : undefined,
                    }}>
                      {/* Progress fill */}
                      <div style={{
                        width: `${pct}%`,
                        height: '100%',
                        background: pct >= 100
                          ? `linear-gradient(90deg, ${TEAL}cc, ${TEAL})`
                          : isLate
                            ? `linear-gradient(90deg, ${RED}cc, ${RED})`
                            : `linear-gradient(90deg, ${barColor}99, ${barColor}cc)`,
                        transition: 'width 0.6s ease',
                      }} />

                      {/* % text inside bar (only if bar is wide enough) */}
                      {w_real > 50 && (
                        <div style={{
                          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                          display: 'flex', alignItems: 'center', paddingLeft: 6,
                        }}>
                          <span style={{
                            fontSize: isMacro ? 9 : 8,
                            fontWeight: 900,
                            color: pct >= 100 ? '#fff' : barColor,
                            fontFamily: 'monospace',
                            textShadow: '0 1px 3px rgba(0,0,0,0.6)',
                          }}>
                            {pct}%
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Delay arrow (if forecast end > baseline end) */}
                    {hasDelay && !isSameDay(e_real, e_plan) && (
                      <div style={{
                        position: 'absolute',
                        left: x_plan + w_plan - 2,
                        top: '50%', marginTop: -4,
                        width: Math.max(4, (differenceInDays(e_real, e_plan)) * DAY_W),
                        height: 8,
                        background: 'rgba(239,68,68,0.25)',
                        borderTop: '1px dashed rgba(239,68,68,0.5)',
                        borderBottom: '1px dashed rgba(239,68,68,0.5)',
                        borderRight: '1px dashed rgba(239,68,68,0.5)',
                        borderRadius: '0 4px 4px 0',
                      }} />
                    )}

                    {/* Done checkmark at end of completed bar */}
                    {pct >= 100 && (
                      <div style={{
                        position: 'absolute',
                        left: x_real + w_real + 4,
                        top: '50%', marginTop: -6,
                      }}>
                        <CheckCircle size={12} style={{ color: TEAL }} />
                      </div>
                    )}

                    {/* Late indicator */}
                    {isLate && pct < 100 && (
                      <div style={{
                        position: 'absolute',
                        left: x_real + w_real + 4,
                        top: '50%', marginTop: -6,
                      }}>
                        <AlertTriangle size={11} style={{ color: RED }} />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* FOOTER — legend + stats */}
        <div style={{
          borderTop: '1px solid rgba(255,255,255,0.05)',
          background: 'rgba(255,255,255,0.015)',
          padding: '10px 20px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12,
        }}>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            {[
              { color: 'rgba(255,255,255,0.15)', label: 'Baseline Original', dashed: false },
              { color: COPPER,                   label: 'Progresso Realizado', dashed: false },
              { color: TEAL,                     label: 'Concluído',           dashed: false },
              { color: RED,                      label: 'Atrasado / Em Risco', dashed: true  },
            ].map(l => (
              <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{
                  width: 18, height: l.dashed ? 4 : 8,
                  borderRadius: 3,
                  background: l.dashed ? 'transparent' : l.color + '90',
                  border: l.dashed ? `1.5px dashed ${l.color}` : `1px solid ${l.color}60`,
                  borderTop: l.dashed ? `1.5px dashed ${l.color}` : undefined,
                }} />
                <span style={{ fontSize: 9, fontWeight: 700, color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{l.label}</span>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'rgba(255,255,255,0.2)' }}>
            <Clock size={11} />
            <span style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              {validData.filter(r => parseInt(r.pct) >= 100).length}/{validData.length} concluídas
              · {validData.filter(r => isCriticoFlag(r.critico)).length} críticas
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

// Helper sub-component for tooltip info lines
function InfoLine({ label, value, mono, accent }: { label: string; value: string; mono?: boolean; accent?: string }) {
  return (
    <>
      <span style={{ fontSize: 8, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.1em' }}>{label}</span>
      <span style={{ fontSize: 10, color: accent || 'rgba(255,255,255,0.85)', fontWeight: 700, fontFamily: mono ? 'monospace' : undefined }}>{value}</span>
    </>
  )
}
