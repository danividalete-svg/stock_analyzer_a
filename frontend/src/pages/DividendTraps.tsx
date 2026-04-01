import { useState, useEffect } from 'react'
import { fetchDividendTraps, fetchDividendCalendar, fetchValueOpportunities, fetchEUValueOpportunities } from '../api/client'
import type { DividendTrapEntry, DividendCalendarEvent } from '../api/client'
import { useApi } from '../hooks/useApi'
import { usePersonalPortfolio } from '../context/PersonalPortfolioContext'
import Loading, { ErrorState } from '../components/Loading'
import { Card, CardContent } from '@/components/ui/card'
import { AlertTriangle, ShieldCheck, ChevronDown, ChevronUp, Briefcase, Zap, CalendarClock, Clock, DollarSign, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import TickerLogo from '../components/TickerLogo'
import OwnedBadge from '../components/OwnedBadge'

type Tab = 'traps' | 'safe' | 'timing'

const RISK_CONFIG = {
  HIGH:   { label: 'ALTO',   bg: 'bg-red-500/10 border-red-500/25',    text: 'text-red-400',    dot: 'bg-red-400' },
  MEDIUM: { label: 'MEDIO',  bg: 'bg-orange-500/10 border-orange-500/25', text: 'text-orange-400', dot: 'bg-orange-400' },
  LOW:    { label: 'BAJO',   bg: 'bg-yellow-500/10 border-yellow-500/25', text: 'text-yellow-400', dot: 'bg-yellow-400' },
}

function TrapScoreBar({ score }: { score: number }) {
  const color = score >= 50 ? '#ef4444' : score >= 25 ? '#f97316' : '#f59e0b'
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 rounded-full bg-muted/30 overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${score}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs font-bold" style={{ color }}>{score}</span>
    </div>
  )
}

function TrapCard({ entry }: { entry: DividendTrapEntry }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = RISK_CONFIG[entry.risk_level]

  return (
    <Card className={`glass border ${cfg.bg} hover:shadow-lg transition-all`}>
      <CardContent className="p-4">
        <div
          className="flex items-start gap-3 flex-wrap cursor-pointer active:scale-[0.98] transition-transform"
          onClick={() => setExpanded(!expanded)}
        >
          {/* Ticker */}
          <div className="flex items-center gap-1.5 min-w-[72px]">
            <TickerLogo ticker={entry.ticker} size="xs" />
            <div>
              <div className="font-mono font-bold text-sm text-primary flex items-center gap-1.5">{entry.ticker}<OwnedBadge ticker={entry.ticker} /></div>
              <div className="text-[0.62rem] text-muted-foreground truncate max-w-[80px]">{entry.sector}</div>
            </div>
          </div>

          {/* Company */}
          <div className="flex-1 min-w-0">
            <div className="text-xs text-foreground/80 truncate">{entry.company}</div>
            {entry.current_price != null && (
              <div className="text-[0.62rem] text-muted-foreground">${entry.current_price.toFixed(2)}</div>
            )}
          </div>

          {/* Metrics */}
          <div className="flex items-center gap-3 text-xs flex-wrap">
            {entry.dividend_yield != null && (
              <div className="text-center">
                <div className={`font-bold ${cfg.text}`}>{entry.dividend_yield.toFixed(1)}%</div>
                <div className="text-muted-foreground/60 text-[0.6rem]">Yield</div>
              </div>
            )}
            {entry.payout_ratio != null && (
              <div className="text-center">
                <div className={`font-bold ${entry.payout_ratio > 100 ? 'text-red-400' : entry.payout_ratio > 80 ? 'text-orange-400' : 'text-yellow-400'}`}>
                  {entry.payout_ratio.toFixed(0)}%
                </div>
                <div className="text-muted-foreground/60 text-[0.6rem]">Payout</div>
              </div>
            )}
            {entry.fcf_yield != null && (
              <div className="text-center">
                <div className={`font-bold ${entry.fcf_yield < 0 ? 'text-red-400' : entry.fcf_yield < (entry.dividend_yield ?? 0) ? 'text-orange-400' : 'text-green-400'}`}>
                  {entry.fcf_yield.toFixed(1)}%
                </div>
                <div className="text-muted-foreground/60 text-[0.6rem]">FCF</div>
              </div>
            )}
            <div>
              <TrapScoreBar score={entry.trap_score} />
              <div className="text-muted-foreground/60 text-[0.6rem] mt-0.5">Riesgo</div>
            </div>
          </div>

          {/* Expand button */}
          <div className="w-8 h-8 rounded-full bg-muted/20 flex items-center justify-center hover:bg-muted/40 transition-colors flex-shrink-0">
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </div>
        </div>

        {/* Reasons */}
        {expanded && entry.reasons.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border/30 space-y-1.5">
            {entry.reasons.map((r, i) => (
              <div key={i} className="flex items-start gap-1.5 text-[0.7rem] text-muted-foreground">
                <AlertTriangle size={10} className="text-red-400 flex-shrink-0 mt-0.5" />
                {r}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function SafeCard({ entry }: { entry: DividendTrapEntry }) {
  return (
    <Card className="glass border border-emerald-500/15 bg-emerald-500/5 hover:border-emerald-500/30 hover:shadow-lg transition-all">
      <CardContent className="p-3">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="min-w-[64px]">
            <div className="font-mono font-bold text-sm text-primary">{entry.ticker}</div>
            <div className="text-[0.6rem] text-muted-foreground truncate max-w-[70px]">{entry.sector}</div>
          </div>
          <div className="flex-1 text-xs text-foreground/70 truncate">{entry.company}</div>
          <div className="flex items-center gap-3 text-xs">
            {entry.dividend_yield != null && (
              <div className="text-center">
                <div className="font-bold text-emerald-400">{entry.dividend_yield.toFixed(1)}%</div>
                <div className="text-muted-foreground/60 text-[0.6rem]">Yield</div>
              </div>
            )}
            {entry.payout_ratio != null && (
              <div className="text-center">
                <div className="font-bold text-foreground/70">{entry.payout_ratio.toFixed(0)}%</div>
                <div className="text-muted-foreground/60 text-[0.6rem]">Payout</div>
              </div>
            )}
            {entry.fcf_yield != null && (
              <div className="text-center">
                <div className="font-bold text-green-400">{entry.fcf_yield.toFixed(1)}%</div>
                <div className="text-muted-foreground/60 text-[0.6rem]">FCF</div>
              </div>
            )}
            {entry.fundamental_score != null && (
              <div className="text-center">
                <div className="font-bold text-foreground/60">{entry.fundamental_score.toFixed(0)}</div>
                <div className="text-muted-foreground/60 text-[0.6rem]">Fund</div>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function DividendTraps() {
  const { data, loading, error } = useApi(() => fetchDividendTraps(), [])
  const { positions: myPositions, isOwned } = usePersonalPortfolio()
  const [tab, setTab] = useState<Tab>('traps')
  const [riskFilter, setRiskFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM'>('ALL')

  // Fetch VALUE recommendations to cross-reference
  const [valueRecs, setValueRecs] = useState<Set<string>>(new Set())
  useEffect(() => {
    Promise.all([
      fetchValueOpportunities().then(r => r.data.data.map(v => v.ticker)).catch(() => [] as string[]),
      fetchEUValueOpportunities().then(r => r.data.data.map(v => v.ticker)).catch(() => [] as string[]),
    ]).then(([us, eu]) => setValueRecs(new Set([...us, ...eu])))
  }, [])

  // Dividend calendar (lazy-loaded when tab clicked)
  const [divCalendar, setDivCalendar] = useState<DividendCalendarEvent[]>([])
  const [divCalLoading, setDivCalLoading] = useState(false)
  const [divCalLoaded, setDivCalLoaded] = useState(false)
  const loadDivCalendar = () => {
    if (divCalLoaded) return
    setDivCalLoading(true)
    fetchDividendCalendar()
      .then(r => { setDivCalendar(r.data.events); setDivCalLoaded(true) })
      .catch(() => setDivCalLoaded(true))
      .finally(() => setDivCalLoading(false))
  }

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  if (!data) return <ErrorState message="Sin datos de dividend traps" />

  // Portfolio tickers that appear in traps or safe lists
  const myTraps = data.traps.filter(t => isOwned(t.ticker))
  const mySafe = data.safe_dividends.filter(t => isOwned(t.ticker))

  // VALUE recommendations that appear in traps (warning!)
  const recTraps = data.traps.filter(t => valueRecs.has(t.ticker))

  const filteredTraps = tab === 'traps'
    ? (riskFilter === 'ALL' ? data.traps : data.traps.filter(t => t.risk_level === riskFilter))
    : data.safe_dividends

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 animate-fade-in-up">
        <div>
          <h1 className="text-2xl font-bold gradient-title mb-1">Dividend Trap Radar</h1>
          <p className="text-sm text-muted-foreground">
            Análisis de sostenibilidad de dividendos · detecta trampas antes de que recorten
          </p>
        </div>
        <span className="text-xs text-muted-foreground self-start">{data.date} · {data.total_scanned} tickers analizados</span>
      </div>

      {/* Portfolio alert */}
      {myPositions.length > 0 && (myTraps.length > 0 || mySafe.length > 0) && (
        <Card className={`glass border ${myTraps.length > 0 ? 'border-red-500/30 bg-red-500/5' : 'border-primary/20 bg-primary/3'}`}>
          <CardContent className="p-4">
            <h4 className="text-xs font-bold uppercase tracking-widest text-primary mb-3 flex items-center gap-2">
              <Briefcase size={14} />
              Tu Cartera — Dividend Check
            </h4>
            {myTraps.length > 0 && (
              <div className="mb-3">
                <div className="text-xs font-semibold text-red-400 mb-2 flex items-center gap-1.5">
                  <AlertTriangle size={12} />
                  {myTraps.length} posicion{myTraps.length > 1 ? 'es' : ''} con dividendo en riesgo
                </div>
                <div className="space-y-1.5">
                  {myTraps.map(t => (
                    <div key={t.ticker} className="flex items-center gap-3 py-1.5 px-3 bg-red-500/5 rounded-lg border border-red-500/10">
                      <TickerLogo ticker={t.ticker} size="xs" />
                      <span className="font-mono font-bold text-sm text-primary">{t.ticker}</span>
                      <span className="text-xs text-muted-foreground truncate flex-1">{t.company}</span>
                      <span className="text-xs font-bold text-red-400">Yield {t.dividend_yield?.toFixed(1)}%</span>
                      <span className={`text-[0.6rem] font-bold px-1.5 py-0.5 rounded ${RISK_CONFIG[t.risk_level].bg} ${RISK_CONFIG[t.risk_level].text}`}>
                        {RISK_CONFIG[t.risk_level].label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {mySafe.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-emerald-400 mb-2 flex items-center gap-1.5">
                  <ShieldCheck size={12} />
                  {mySafe.length} posicion{mySafe.length > 1 ? 'es' : ''} con dividendo seguro
                </div>
                <div className="flex flex-wrap gap-2">
                  {mySafe.map(t => (
                    <div key={t.ticker} className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-500/10 rounded-lg border border-emerald-500/15">
                      <TickerLogo ticker={t.ticker} size="xs" />
                      <span className="font-mono font-bold text-xs text-primary">{t.ticker}</span>
                      <span className="text-xs font-semibold text-emerald-400">{t.dividend_yield?.toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* VALUE recommendations in traps */}
      {recTraps.length > 0 && (
        <Card className="glass border border-amber-500/30 bg-amber-500/5">
          <CardContent className="p-4">
            <h4 className="text-xs font-bold uppercase tracking-widest text-amber-400 mb-3 flex items-center gap-2">
              <Zap size={14} />
              Recomendaciones VALUE con dividendo en riesgo ({recTraps.length})
            </h4>
            <div className="space-y-1.5">
              {recTraps.map(t => (
                <div key={t.ticker} className="flex items-center gap-3 py-1.5 px-3 bg-amber-500/5 rounded-lg border border-amber-500/10">
                  <TickerLogo ticker={t.ticker} size="xs" />
                  <span className="font-mono font-bold text-sm text-primary">{t.ticker}</span>
                  <span className="text-xs text-muted-foreground truncate flex-1">{t.company}</span>
                  <span className="text-xs text-amber-400">Yield {t.dividend_yield?.toFixed(1)}% · Payout {t.payout_ratio?.toFixed(0)}%</span>
                  <span className={`text-[0.6rem] font-bold px-1.5 py-0.5 rounded ${RISK_CONFIG[t.risk_level].bg} ${RISK_CONFIG[t.risk_level].text}`}>
                    {RISK_CONFIG[t.risk_level].label}
                  </span>
                </div>
              ))}
            </div>
            <p className="text-[0.65rem] text-muted-foreground/60 mt-2">Estas acciones aparecen como oportunidades VALUE pero su dividendo puede estar en riesgo de recorte.</p>
          </CardContent>
        </Card>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="glass border border-red-500/20">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertTriangle size={18} className="text-red-400 flex-shrink-0" />
            <div>
              <div className="text-xl font-bold text-red-400">{data.traps_high}</div>
              <div className="text-xs text-muted-foreground">Riesgo ALTO</div>
            </div>
          </CardContent>
        </Card>
        <Card className="glass border border-orange-500/20">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertTriangle size={18} className="text-orange-400 flex-shrink-0" />
            <div>
              <div className="text-xl font-bold text-orange-400">{data.traps_medium}</div>
              <div className="text-xs text-muted-foreground">Riesgo MEDIO</div>
            </div>
          </CardContent>
        </Card>
        <Card className="glass border border-emerald-500/20">
          <CardContent className="p-4 flex items-center gap-3">
            <ShieldCheck size={18} className="text-emerald-400 flex-shrink-0" />
            <div>
              <div className="text-xl font-bold text-emerald-400">{data.safe_count}</div>
              <div className="text-xs text-muted-foreground">Dividendo seguro</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1 p-1 bg-muted/20 rounded-xl border border-border/30 w-fit">
          {([
            { key: 'traps', label: `⚠ Trampas (${data.traps.length})` },
            { key: 'safe',  label: `✓ Seguros (${data.safe_count})` },
            { key: 'timing', label: `📅 Timing${divCalLoaded ? ` (${divCalendar.length})` : ''}` },
          ] as { key: Tab; label: string }[]).map(({ key, label }) => (
            <button
              key={key}
              onClick={() => { setTab(key); if (key === 'timing') loadDivCalendar() }}
              className={`text-xs font-semibold px-4 py-1.5 rounded-lg transition-all ${
                tab === key
                  ? 'bg-background shadow-sm text-foreground border border-border/40'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === 'traps' && (
          <div className="flex gap-1">
            {(['ALL', 'HIGH', 'MEDIUM'] as const).map(r => (
              <button
                key={r}
                onClick={() => setRiskFilter(r)}
                className={`text-[0.68rem] px-2.5 py-0.5 rounded-full border transition-colors ${riskFilter === r ? 'border-primary/60 bg-primary/15 text-primary' : 'border-border/40 text-muted-foreground hover:text-foreground'}`}
              >
                {r === 'ALL' ? 'Todos' : r}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Tab summary row */}
      {tab === 'traps' && (
        <p className="text-xs text-muted-foreground">
          {data.traps.length} trampas detectadas · <span className="text-red-400 font-semibold">{data.traps_high} ALTO riesgo</span> · <span className="text-orange-400 font-semibold">{data.traps_medium} MEDIO</span>
        </p>
      )}
      {tab === 'safe' && (
        <p className="text-xs text-muted-foreground">
          {data.safe_count} dividendos sostenibles
          {data.safe_dividends.length > 0 && data.safe_dividends.some(s => s.dividend_yield != null) && (
            <> · dividendo medio <span className="text-emerald-400 font-semibold">
              {(data.safe_dividends.reduce((acc, s) => acc + (s.dividend_yield ?? 0), 0) / data.safe_dividends.filter(s => s.dividend_yield != null).length).toFixed(1)}%
            </span></>
          )}
        </p>
      )}
      {tab === 'timing' && divCalLoaded && (
        <p className="text-xs text-muted-foreground">
          Próximos <span className="text-blue-400 font-semibold">{divCalendar.filter(e => e.days_to_exdiv <= 30).length}</span> dividendos en 30 días
        </p>
      )}

      {/* List */}
      {tab === 'traps' ? (
        <>
          {filteredTraps.length === 0 ? (
            <Card className="glass border border-border/40">
              <CardContent className="p-10 text-center">
                <ShieldCheck size={32} className="text-emerald-400/40 mx-auto mb-3" />
                <p className="text-sm font-medium text-foreground/70">Sin trampas con los filtros actuales</p>
                <p className="text-xs text-muted-foreground mt-1">Prueba cambiando el filtro de riesgo</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {(filteredTraps as DividendTrapEntry[]).map(entry => (
                <TrapCard key={entry.ticker} entry={entry} />
              ))}
            </div>
          )}
        </>
      ) : tab === 'safe' ? (
        <>
          {data.safe_dividends.length === 0 ? (
            <Card className="glass border border-border/40">
              <CardContent className="p-10 text-center">
                <AlertTriangle size={32} className="text-orange-400/40 mx-auto mb-3" />
                <p className="text-sm font-medium text-foreground/70">No hay dividendos calificados como seguros</p>
                <p className="text-xs text-muted-foreground mt-1">El escáner no encontró dividendos con suficiente cobertura de FCF</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {(filteredTraps as DividendTrapEntry[]).map(entry => (
                <SafeCard key={entry.ticker} entry={entry} />
              ))}
            </div>
          )}
        </>
      ) : (
        /* Dividend Timing tab */
        <div className="space-y-4">
          {divCalLoading && (
            <Card className="glass border border-border/40">
              <CardContent className="p-8 text-center">
                <Loader2 size={24} className="animate-spin text-primary mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">Escaneando ex-dividend dates...</p>
                <p className="text-xs text-muted-foreground/50 mt-1">Primera carga puede tardar ~30s</p>
              </CardContent>
            </Card>
          )}

          {divCalLoaded && divCalendar.length === 0 && (
            <Card className="glass border border-border/40">
              <CardContent className="p-10 text-center">
                <CalendarClock size={32} className="text-blue-400/40 mx-auto mb-3" />
                <p className="text-sm font-medium text-foreground/70">Sin ex-dividend dates próximos</p>
                <p className="text-xs text-muted-foreground mt-1">No hay acciones de calidad con ex-div en los próximos 45 días</p>
              </CardContent>
            </Card>
          )}

          {divCalLoaded && divCalendar.length > 0 && (() => {
            // Group by urgency
            const urgent = divCalendar.filter(e => e.days_to_exdiv <= 7)
            const soon = divCalendar.filter(e => e.days_to_exdiv > 7 && e.days_to_exdiv <= 21)
            const later = divCalendar.filter(e => e.days_to_exdiv > 21)

            const EventCard = ({ event }: { event: DividendCalendarEvent }) => (
              <Card className={`glass border transition-all hover:shadow-lg active:scale-[0.98] cursor-pointer ${isOwned(event.ticker) ? 'border-primary/30 bg-primary/5' : 'border-border/30'}`}>
                <CardContent className="p-4">
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-1.5 min-w-[72px]">
                      <TickerLogo ticker={event.ticker} size="xs" />
                      <div>
                        <div className="font-mono font-bold text-sm text-primary flex items-center gap-1.5">
                          {event.ticker}
                          <OwnedBadge ticker={event.ticker} />
                        </div>
                        <div className="text-[0.62rem] text-muted-foreground truncate max-w-[80px]">{event.sector}</div>
                      </div>
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-foreground/80 truncate">{event.company}</div>
                      {event.current_price != null && (
                        <div className="text-[0.62rem] text-muted-foreground">${event.current_price.toFixed(2)}</div>
                      )}
                    </div>

                    <div className="flex items-center gap-3 text-xs flex-wrap">
                      <div className="text-center">
                        <div className={`font-bold ${event.days_to_exdiv <= 7 ? 'text-amber-400' : 'text-blue-400'}`}>
                          {event.days_to_exdiv}d
                        </div>
                        <div className="text-muted-foreground/60 text-[0.6rem]">Ex-Div</div>
                      </div>

                      <div className="text-center">
                        <div className="font-bold text-foreground/80">{event.ex_dividend_date.slice(5)}</div>
                        <div className="text-muted-foreground/60 text-[0.6rem]">Fecha</div>
                      </div>

                      {event.dividend_per_share != null && (
                        <div className="text-center">
                          <div className="font-bold text-emerald-400">${event.dividend_per_share.toFixed(2)}</div>
                          <div className="text-muted-foreground/60 text-[0.6rem]">$/Accion</div>
                        </div>
                      )}

                      {event.capture_yield_pct != null && (
                        <div className="text-center">
                          <div className="font-bold text-emerald-400">{event.capture_yield_pct.toFixed(2)}%</div>
                          <div className="text-muted-foreground/60 text-[0.6rem]">Capture</div>
                        </div>
                      )}

                      {event.dividend_yield_annual != null && (
                        <div className="text-center">
                          <div className="font-bold text-foreground/70">{event.dividend_yield_annual.toFixed(1)}%</div>
                          <div className="text-muted-foreground/60 text-[0.6rem]">Yield anual</div>
                        </div>
                      )}

                      {event.fundamental_score != null && (
                        <div className="text-center">
                          <div className={`font-bold ${event.fundamental_score >= 65 ? 'text-emerald-400' : event.fundamental_score >= 50 ? 'text-foreground/60' : 'text-red-400'}`}>
                            {event.fundamental_score.toFixed(0)}
                          </div>
                          <div className="text-muted-foreground/60 text-[0.6rem]">Fund</div>
                        </div>
                      )}

                      <div className="flex gap-1">
                        <Badge variant="green" className="text-[0.55rem]">IA VERIFIED</Badge>
                        {event.conviction_grade && (
                          <Badge variant={event.conviction_grade === 'A' || event.conviction_grade === 'A+' ? 'blue' : 'gray'} className="text-[0.55rem]">
                            {event.conviction_grade}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )

            return (
              <>
                {urgent.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-widest text-amber-400 mb-2 flex items-center gap-1.5">
                      <Clock size={12} />
                      Esta semana — comprar antes del ex-div ({urgent.length})
                    </h4>
                    <div className="space-y-2">
                      {urgent.map(e => <EventCard key={e.ticker} event={e} />)}
                    </div>
                  </div>
                )}

                {soon.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-widest text-blue-400 mb-2 flex items-center gap-1.5">
                      <CalendarClock size={12} />
                      Proximas 2-3 semanas ({soon.length})
                    </h4>
                    <div className="space-y-2">
                      {soon.map(e => <EventCard key={e.ticker} event={e} />)}
                    </div>
                  </div>
                )}

                {later.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2 flex items-center gap-1.5">
                      <DollarSign size={12} />
                      Mas adelante ({later.length})
                    </h4>
                    <div className="space-y-2">
                      {later.map(e => <EventCard key={e.ticker} event={e} />)}
                    </div>
                  </div>
                )}
              </>
            )
          })()}

          {/* Timing explanation */}
          {divCalLoaded && (
            <Card className="glass border border-border/30">
              <CardContent className="p-3 space-y-1 text-xs text-muted-foreground">
                <div className="font-semibold text-foreground/70 mb-2">Estrategia de Dividend Timing</div>
                <div>• Solo muestra empresas <span className="text-emerald-400">filtradas por IA</span> — recomendaciones VALUE verificadas con calidad confirmada</div>
                <div>• <span className="text-blue-400">Comprar antes del ex-dividend date</span> para capturar el dividendo y quedarte en cartera</div>
                <div>• <span className="text-amber-400">Capture yield</span> = dividendo por accion / precio actual (lo que capturas por holding 1 dia)</div>
                <div>• El precio suele caer ~dividendo el dia ex-div, pero en empresas de calidad con tendencia alcista se recupera rapido</div>
                <div>• Ideal: combinar con analisis VALUE — si ya te gusta la empresa, el dividendo es un bonus</div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Legend (only for trap/safe tabs) */}
      {tab !== 'timing' && (
        <Card className="glass border border-border/30">
          <CardContent className="p-3 space-y-1 text-xs text-muted-foreground">
            <div className="font-semibold text-foreground/70 mb-2">Criterios de trampa</div>
            <div>• <span className="text-red-400">Payout &gt;100%</span> — el dividendo supera los beneficios</div>
            <div>• <span className="text-red-400">FCF yield &lt; dividend yield</span> — la caja libre no cubre el dividendo</div>
            <div>• <span className="text-orange-400">Yield &gt;6–8%</span> — el mercado ya descuenta un recorte</div>
            <div>• <span className="text-orange-400">Deuda/equity &gt;2x</span> — el dividendo compite con el pago de deuda</div>
            <div>• <span className="text-yellow-400">ROE negativo</span> — empresa pierde dinero mientras paga dividendo</div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
