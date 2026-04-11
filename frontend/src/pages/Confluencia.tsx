import { useMemo } from 'react'
import { fetchMeanReversion, fetchUnusualFlow } from '../api/client'
import { useApi } from '../hooks/useApi'
import TickerLogo from '../components/TickerLogo'
import Loading from '../components/Loading'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

// ── Types ─────────────────────────────────────────────────────────────────────

interface BounceSignal {
  rsi: number
  conf: number
  dp: string | null
  score: number
  tier: number
  price: number
  rr: number
}

interface FlowSignal {
  signal: 'BULLISH' | 'BEARISH' | 'MIXED'
  interpretation: string   // PUT_COVERING | FRESH_BULLISH | STANDARD | ...
  premium: number
  call_pct: number
  drawdown: number | null
  reason: string
}

interface ConfluenceTicker {
  ticker: string
  bounce:    BounceSignal | null
  value_us:  { score: number; grade: string; sector: string } | null
  value_eu:  { score: number; grade: string; sector: string } | null
  flow:      FlowSignal | null
  score:     number      // 0–10
  signals:   string[]    // labels shown as badges
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmtPremium = (v: number) => {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`
  return `$${v}`
}

function ScoreCircle({ score }: { score: number }) {
  const color =
    score >= 7 ? 'text-emerald-400 border-emerald-500/50' :
    score >= 4 ? 'text-cyan-400 border-cyan-500/40' :
    'text-muted-foreground border-border/40'
  return (
    <div className={`w-9 h-9 rounded-full border-2 flex items-center justify-center text-sm font-extrabold tabular-nums ${color}`}>
      {score}
    </div>
  )
}

function SignalPill({ label, variant }: { label: string; variant: 'bounce' | 'value' | 'flow' | 'covering' }) {
  const cls = {
    bounce:   'bg-purple-500/15 text-purple-300 border-purple-500/30',
    value:    'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    flow:     'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    covering: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
  }[variant]
  return (
    <span className={`inline-flex items-center text-[0.6rem] font-bold px-1.5 py-0.5 rounded border ${cls}`}>
      {label}
    </span>
  )
}

// ── Data merging ──────────────────────────────────────────────────────────────

function useCsvRows(filename: string): Record<string, string>[] {
  const csvBase = (import.meta.env.VITE_CSV_BASE as string | undefined) || ''
  const url = csvBase ? `${csvBase}/${filename}` : `/docs/${filename}`
  const { data } = useApi(async () => {
    const res = await fetch(url)
    if (!res.ok) return { data: null }
    const text = await res.text()
    const lines = text.trim().split('\n')
    if (lines.length < 2) return { data: null }
    const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''))
    const rows = lines.slice(1).map(line => {
      const vals = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''))
      const obj: Record<string, string> = {}
      headers.forEach((h, i) => { obj[h] = vals[i] ?? '' })
      return obj
    })
    return { data: rows }
  }, [url])
  const inner = (data as { data: Record<string, string>[] | null } | null)
  return inner?.data ?? []
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Confluencia() {
  const { data: mrRaw,   loading: mrLoading }   = useApi(() => fetchMeanReversion(), [])
  const { data: flowRaw, loading: flowLoading }  = useApi(() => fetchUnusualFlow(), [])
  const valueUsRows = useCsvRows('value_opportunities_filtered.csv')
  const valueEuRows = useCsvRows('european_value_opportunities_filtered.csv')

  const loading = mrLoading || flowLoading

  const confluence = useMemo<ConfluenceTicker[]>(() => {
    const map = new Map<string, ConfluenceTicker>()

    const get = (ticker: string): ConfluenceTicker => {
      if (!map.has(ticker)) {
        map.set(ticker, { ticker, bounce: null, value_us: null, value_eu: null, flow: null, score: 0, signals: [] })
      }
      return map.get(ticker)!
    }

    // ── Bounce setups ──────────────────────────────────────────────────────
    const mrData = mrRaw as Record<string, unknown> | null
    const ops = (mrData?.opportunities ?? []) as Record<string, unknown>[]
    for (const o of ops) {
      if (o.strategy !== 'Oversold Bounce') continue
      const rsi   = Number(o.rsi ?? 0)
      const conf  = Number(o.bounce_confidence ?? 0)
      const dp    = (o.dark_pool_signal as string) || null
      const price = Number(o.current_price ?? 0)
      const rr    = Number(o.risk_reward ?? 0)
      // Apply same frontend quality filters
      if (rsi >= 30 || rsi === 0) continue
      if (conf < 40) continue
      if (price < 1.0) continue
      if (dp === 'DISTRIBUTION' && conf < 60) continue
      if (rr !== 0 && rr < 1.0) continue
      const ticker = String(o.ticker)
      get(ticker).bounce = {
        rsi, conf, dp, price, rr,
        score: Number(o.reversion_score ?? 0),
        tier:  Number(o.conviction_tier ?? 1),
      }
    }

    // ── Value US ──────────────────────────────────────────────────────────
    for (const r of valueUsRows) {
      const ticker = r.ticker?.trim()
      if (!ticker) continue
      const score = parseFloat(r.value_score || '0')
      if (score < 50) continue
      get(ticker).value_us = { score, grade: r.grade || '', sector: r.sector || '' }
    }

    // ── Value EU ──────────────────────────────────────────────────────────
    for (const r of valueEuRows) {
      const ticker = r.ticker?.trim()
      if (!ticker) continue
      const score = parseFloat(r.value_score || '0')
      if (score < 50) continue
      get(ticker).value_eu = { score, grade: r.grade || '', sector: r.sector || '' }
    }

    // ── Unusual flow (only BULLISH or PUT_COVERING) ────────────────────────
    const flowData = flowRaw as Record<string, unknown> | null
    const results = (flowData?.results ?? []) as Record<string, unknown>[]
    for (const r of results) {
      const sig    = r.signal as string
      const interp = (r.flow_interpretation as string) || 'STANDARD'
      const prem   = Number(r.total_premium ?? 0)
      if (prem < 25_000) continue
      // Include: bullish flow OR PUT_COVERING (institutional profit-taking = potential bottom)
      if (sig !== 'BULLISH' && interp !== 'PUT_COVERING') continue
      const ticker = String(r.ticker)
      get(ticker).flow = {
        signal:         sig as 'BULLISH' | 'BEARISH' | 'MIXED',
        interpretation: interp,
        premium:        prem,
        call_pct:       Number(r.call_pct ?? 50),
        drawdown:       r.drawdown_from_high_pct != null ? Number(r.drawdown_from_high_pct) : null,
        reason:         (r.interpretation_reason as string) || '',
      }
    }

    // ── Score & signal labels ─────────────────────────────────────────────
    for (const item of map.values()) {
      let sc = 0
      const labels: string[] = []

      if (item.bounce) {
        sc += item.bounce.tier === 2 ? 4 : 3
        labels.push('🎯 Bounce')
      }
      if (item.value_us) {
        sc += item.value_us.score >= 70 ? 3 : 2
        labels.push('💎 VALUE US')
      }
      if (item.value_eu) {
        sc += item.value_eu.score >= 70 ? 3 : 2
        labels.push('🇪🇺 VALUE EU')
      }
      if (item.flow) {
        if (item.flow.interpretation === 'PUT_COVERING') {
          sc += 1
          labels.push('🔄 Suelo probable')
        } else {
          sc += item.flow.premium > 100_000 ? 3 : 2
          labels.push('⚡ Flow alcista')
        }
      }
      item.score   = sc
      item.signals = labels
    }

    return [...map.values()]
      .filter(t => t.score >= 2)
      .sort((a, b) => b.score - a.score)
  }, [mrRaw, flowRaw, valueUsRows, valueEuRows])

  // Only show tickers with ≥2 systems aligned, max 10 (highest conviction first)
  const highConviction = confluence.filter(t => t.score >= 4).slice(0, 10)
  const midConviction  = confluence.filter(t => t.score >= 2 && t.score < 4).slice(0, 10)

  // Count how many distinct systems are present
  const bounceCount = confluence.filter(t => t.bounce).length
  const valueCount  = confluence.filter(t => t.value_us || t.value_eu).length
  const flowCount   = confluence.filter(t => t.flow).length

  if (loading) return <Loading />

  return (
    <>
      <div className="mb-6 animate-fade-in-up">
        <h2 className="text-2xl font-extrabold tracking-tight mb-1 gradient-title">Signal Confluence</h2>
        <p className="text-sm text-muted-foreground">
          Tickers donde Bounce + Value + Flow coinciden — top 10 por convicción
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        {[
          { label: 'Alta convicción', value: highConviction.length, sub: '≥2 sistemas alineados', color: 'text-emerald-400', idx: 1 },
          { label: 'Bounce activos', value: bounceCount, sub: 'RSI<30 + conf≥40', color: 'text-purple-400', idx: 2 },
          { label: 'Value + Flow', value: valueCount + flowCount, sub: 'señales en universo', color: 'text-cyan-400', idx: 3 },
        ].map(({ label, value, sub, color, idx }) => (
          <Card key={label} className={`glass p-4 stagger-${idx}`}>
            <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-1">{label}</div>
            <div className={`text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-1 ${color}`}>{value}</div>
            <div className="text-[0.62rem] text-muted-foreground">{sub}</div>
          </Card>
        ))}
      </div>

      {confluence.length === 0 ? (
        <Card className="glass">
          <CardContent className="py-16 text-center">
            <div className="text-4xl mb-4 opacity-20">🔭</div>
            <p className="font-medium text-muted-foreground">Sin confluencia de señales ahora mismo</p>
            <p className="text-xs text-muted-foreground/60 mt-2 max-w-sm mx-auto">
              La sección requiere que ≥2 sistemas coincidan en el mismo ticker
              (Bounce RSI&lt;30 + Value score≥50 + Options flow alcista).
              Con VIX elevado o mercado en corrección, el bounce scanner apenas genera setups.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {highConviction.length > 0 && (
            <SectionTable title="🏆 Alta Convicción" subtitle="≥2 sistemas coinciden · top 10" rows={highConviction} />
          )}
          {midConviction.length > 0 && (
            <SectionTable title="📡 Señal Única" subtitle="1 sistema con score≥2" rows={midConviction} dim />
          )}
        </>
      )}
    </>
  )
}

// ── Section table ─────────────────────────────────────────────────────────────

function SectionTable({ title, subtitle, rows, dim = false }: {
  title: string
  subtitle: string
  rows: ConfluenceTicker[]
  dim?: boolean
}) {
  return (
    <div className={`mb-6 ${dim ? 'opacity-60' : ''}`}>
      <div className="flex items-baseline gap-2 mb-2">
        <h3 className="text-sm font-bold">{title}</h3>
        <span className="text-[0.6rem] text-muted-foreground">{subtitle}</span>
      </div>
      <Card className="glass">
        <Table>
          <TableHeader>
            <TableRow className="border-border/50 hover:bg-transparent">
              <TableHead className="w-10">Score</TableHead>
              <TableHead>Ticker</TableHead>
              <TableHead>Señales</TableHead>
              <TableHead>Bounce</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>Flow</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(t => (
              <TableRow key={t.ticker} className="hover:bg-muted/5 transition-colors">
                <TableCell><ScoreCircle score={t.score} /></TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <TickerLogo ticker={t.ticker} size="xs" />
                    <span className="font-mono font-bold text-primary">{t.ticker}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {t.signals.map(s => {
                      const v = s.includes('Bounce') ? 'bounce'
                        : s.includes('VALUE') || s.includes('EU') ? 'value'
                        : s.includes('Suelo') ? 'covering'
                        : 'flow'
                      return <SignalPill key={s} label={s} variant={v as any} />
                    })}
                  </div>
                </TableCell>
                <TableCell>
                  {t.bounce ? (
                    <div className="text-[0.65rem] text-muted-foreground space-y-0.5">
                      <div>RSI <span className="text-orange-400 font-semibold">{t.bounce.rsi.toFixed(0)}</span></div>
                      <div>conf <span className="font-semibold">{t.bounce.conf}%</span></div>
                      {t.bounce.tier === 2 && <div className="text-cyan-400 font-bold text-[0.58rem]">VALUE-BACKED</div>}
                    </div>
                  ) : <span className="text-muted-foreground/30 text-xs">—</span>}
                </TableCell>
                <TableCell>
                  {(t.value_us || t.value_eu) ? (
                    <div className="text-[0.65rem] text-muted-foreground space-y-0.5">
                      {t.value_us && (
                        <div>
                          <span className="text-cyan-400 font-bold">{t.value_us.score.toFixed(0)}</span>
                          <span className="ml-1 opacity-60">{t.value_us.grade}</span>
                          <span className="ml-1 text-[0.58rem] text-muted-foreground/50">US</span>
                        </div>
                      )}
                      {t.value_eu && (
                        <div>
                          <span className="text-cyan-400 font-bold">{t.value_eu.score.toFixed(0)}</span>
                          <span className="ml-1 opacity-60">{t.value_eu.grade}</span>
                          <span className="ml-1 text-[0.58rem] text-muted-foreground/50">EU</span>
                        </div>
                      )}
                    </div>
                  ) : <span className="text-muted-foreground/30 text-xs">—</span>}
                </TableCell>
                <TableCell>
                  {t.flow ? (
                    <div className="text-[0.65rem] text-muted-foreground space-y-0.5">
                      <div className="font-semibold">
                        {t.flow.interpretation === 'PUT_COVERING'
                          ? <span className="text-yellow-400">🔄 Suelo</span>
                          : <span className="text-emerald-400">⚡ {t.flow.signal}</span>
                        }
                      </div>
                      <div>{fmtPremium(t.flow.premium)}</div>
                      {t.flow.drawdown != null && (
                        <div className="text-[0.58rem] opacity-60">{t.flow.drawdown.toFixed(0)}% vs máx</div>
                      )}
                    </div>
                  ) : <span className="text-muted-foreground/30 text-xs">—</span>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
