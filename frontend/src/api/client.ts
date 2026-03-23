import axios from 'axios'
import { supabase } from '@/lib/supabase'

const API_BASE = import.meta.env.VITE_API_URL || ''

// Cache session token — onAuthStateChange fires INITIAL_SESSION immediately
// on setup, so no separate getSession() call needed. Interceptor stays sync.
let _cachedToken: string | null = null
supabase.auth.onAuthStateChange((_event, session) => {
  _cachedToken = session?.access_token ?? null
})

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
})

// Attach Supabase JWT to every request — synchronous, no blocking getSession()
api.interceptors.request.use((config) => {
  if (_cachedToken) {
    config.headers.Authorization = `Bearer ${_cachedToken}`
  }
  return config
})

export interface ValueOpportunity {
  ticker: string
  company_name: string
  current_price: number
  value_score: number
  conviction_grade?: string
  conviction_score?: number
  conviction_reasons?: string
  conviction_positives?: number
  conviction_red_flags?: number
  sector?: string
  target_price_analyst?: number
  analyst_upside_pct?: number
  analyst_count?: number
  fcf_yield_pct?: number
  risk_reward_ratio?: number
  dividend_yield_pct?: number
  buyback_active?: boolean
  days_to_earnings?: number
  earnings_warning?: boolean
  market?: string
  entry_price?: number
  stop_loss?: number
  target_price?: number
  thesis?: string
  proximity_to_52w_high?: number
  // Piotroski F-Score (Proven: +13.4% annual alpha)
  piotroski_score?: number
  piotroski_label?: string
  // Magic Formula (Greenblatt) + PEG (Lynch)
  ebit_ev_yield?: number
  roic_greenblatt?: number
  magic_formula_rank?: number
  peg_ratio?: number
  // Hedge Fund 13F consensus
  hedge_fund_count?: number
  hedge_fund_names?: string
  // Health/earnings metrics (from global CSV)
  roe_pct?: number
  profit_margin_pct?: number
  revenue_growth_pct?: number
  pe_forward?: number
  pe_trailing?: number
  // Cerebro IA synthesized signal (written by cerebro.py → read by super_score_integrator)
  cerebro_signal?: string
  cerebro_score_adj?: number
}

export interface MomentumOpportunity {
  ticker: string
  company_name: string
  current_price: number
  momentum_score: number
  vcp_score?: number
  proximity_to_52w_high?: number
  trend_template_score?: number
  target_price_analyst?: number
  analyst_upside_pct?: number
}

export interface InsiderData {
  ticker: string
  company_name?: string
  company?: string          // US CSV field name
  purchase_count: number
  unique_insiders: number
  days_span: number
  first_purchase?: string
  last_purchase: string
  total_qty?: number
  confidence_score: number
  confidence_label?: string // EU field
  market?: string
}

export interface OptionsFlowItem {
  ticker: string
  company_name?: string
  sentiment: string
  flow_score: number
  quality: string
  current_price?: number
  total_premium?: number
  put_call_ratio?: number
  unusual_calls?: number
  unusual_puts?: number
  sentiment_emoji?: string
}

export interface MeanReversionItem {
  ticker: string
  company_name?: string
  strategy: string
  quality: string
  reversion_score: number
  current_price?: number
  entry_zone?: string
  target?: number
  stop_loss?: number
  rsi?: number
  drawdown_pct?: number
  risk_reward?: number
  support_level?: number
  resistance_level?: number
  distance_to_support_pct?: number
  volume_ratio?: number
  detected_date?: string
}

export interface SectorRotationData {
  results: Array<{
    sector: string
    status: string
    velocity: number
    relative_strength: number
  }>
  alerts: Array<{
    type: string
    sector: string
    message: string
  }>
  opportunities: Array<Record<string, unknown>>
  timestamp?: string
}

export interface PortfolioSummary {
  total_signals?: number
  unique_tickers?: number
  date_range?: string
  active_signals?: number
  completed_signals?: number
  overall?: {
    '7d': { count: number; win_rate: number; avg_return: number }
    '14d': { count: number; win_rate: number; avg_return: number }
    '30d': { count: number; win_rate: number; avg_return: number }
  }
  top_performers?: Array<Record<string, unknown>>
  worst_performers?: Array<Record<string, unknown>>
  recent_signals?: Array<Record<string, unknown>>
  avg_max_drawdown?: number
  score_correlation?: number
}

export interface MarketRegime {
  us: Record<string, unknown>
  eu: Record<string, unknown>
}

export const fetchValueOpportunities = () =>
  api.get<{ data: ValueOpportunity[]; count: number; source: string }>('/api/value-opportunities')

export const fetchEUValueOpportunities = () =>
  api.get<{ data: ValueOpportunity[]; count: number; source: string }>('/api/eu-value-opportunities')

// Simple quoted-CSV parser (handles commas inside "..." fields)
function parseCsvRows(text: string): Record<string, string>[] {
  const lines = text.trim().split('\n')
  if (lines.length < 2) return []
  const splitRow = (line: string): string[] => {
    const out: string[] = []
    let cur = '', inQ = false
    for (let i = 0; i < line.length; i++) {
      const ch = line[i]
      if (ch === '"') { if (inQ && line[i + 1] === '"') { cur += '"'; i++ } else inQ = !inQ }
      else if (ch === ',' && !inQ) { out.push(cur); cur = '' }
      else cur += ch
    }
    out.push(cur)
    return out
  }
  const headers = splitRow(lines[0])
  return lines.slice(1).filter(l => l.trim()).map(line => {
    const vals = splitRow(line)
    const obj: Record<string, string> = {}
    headers.forEach((h, i) => { obj[h.trim()] = vals[i] ?? '' })
    return obj
  })
}

const GLOBAL_NUMERIC = new Set([
  'current_price','value_score','conviction_score','conviction_positives','conviction_red_flags',
  'market_cape','target_price_analyst','analyst_upside_pct','analyst_count',
  'fcf_yield_pct','risk_reward_ratio','dividend_yield_pct','roe_pct',
  'pe_forward','pe_trailing','profit_margin_pct','revenue_growth_pct','pct_from_52w_high',
])

export const fetchGlobalValueOpportunities = async (): Promise<{
  data: { data: ValueOpportunity[]; count: number; source: string }
}> => {
  const csvBase = import.meta.env.VITE_CSV_BASE as string | undefined
  if (csvBase) {
    // Production: read CSV directly from GitHub Pages (always up-to-date)
    const url = `${csvBase}/global_value_opportunities.csv`
    const res = await fetch(url)
    if (!res.ok) throw new Error(`CSV fetch failed: ${res.status}`)
    const text = await res.text()
    const rawRows = parseCsvRows(text)
    const data = rawRows.map(row => {
      const obj: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(row)) {
        if (GLOBAL_NUMERIC.has(k)) obj[k] = v === '' ? null : Number(v)
        else if (k === 'buyback_active') obj[k] = v.toLowerCase() === 'true'
        else obj[k] = v === '' ? undefined : v
      }
      return obj as unknown as ValueOpportunity
    })
    return { data: { data, count: data.length, source: 'github-pages' } }
  }
  // Development: Railway API reads local docs/ folder
  const res = await api.get<{ data: ValueOpportunity[]; count: number; source: string }>('/api/global-value')
  return { data: res.data }
}

export const fetchMomentumOpportunities = () =>
  api.get<{ data: MomentumOpportunity[]; count: number; source: string }>('/api/momentum-opportunities')

export const fetchSectorRotation = () =>
  api.get<SectorRotationData>('/api/sector-rotation')

export const fetchOptionsFlow = () =>
  api.get('/api/options-flow')

export const fetchMeanReversion = () =>
  api.get('/api/mean-reversion')

export const fetchRecurringInsiders = () =>
  api.get<{ data: InsiderData[]; count: number; source: string }>('/api/recurring-insiders')

export const fetchPortfolioTracker = () =>
  api.get<PortfolioSummary>('/api/portfolio-tracker')

export interface BreadthData {
  total: number
  trend_pass?: number; trend_pass_pct?: number
  rs_at_high?: number; rs_at_high_pct?: number
  positive_upside?: number; positive_upside_pct?: number
  earnings_warnings?: number
}
export const fetchMarketBreadth = () =>
  api.get<{ us: BreadthData; eu: BreadthData }>('/api/market-breadth')

// ── Cerebro AI agent ─────────────────────────────────────────────────────────
export interface CerebroTier {
  label: string
  win_rate_7d: number
  avg_return_7d: number
  n: number
  vs_baseline_wr: number
  vs_baseline_ret: number
}
export interface CerebroInsights {
  generated_at: string
  total_analyzed: number
  baseline_win_rate_7d: number
  baseline_avg_return_7d: number
  score_tiers: CerebroTier[]
  market_regimes: CerebroTier[]
  sectors: CerebroTier[]
  fcf_tiers: CerebroTier[]
  best_combos: CerebroTier[]
  period_stats: Record<string, { win_rate: number | null; avg_return: number; n: number }>
  narrative: string | null
}
export interface CerebroSignal {
  ticker: string
  company_name: string
  sector: string
  strategies: string[]
  strategy_count: number
  convergence_score: number
  value_score: number | null
  conviction_grade: string
  analyst_upside_pct: number | null
  fcf_yield_pct: number | null
  current_price: number | null
  analysis: string | null
}
export interface CerebroAlert {
  ticker: string
  type: string
  severity: 'HIGH' | 'MEDIUM' | 'LOW'
  title: string
  message: string
  date: string
  data?: Record<string, unknown>
}
export interface CerebroCalibration {
  generated_at: string
  recommendations: Array<{ type: string; factor: string; insight: string; n: number }>
  narrative: string | null
  total_recommendations: number
}

export interface EntrySignal {
  ticker: string
  company_name: string
  region: string
  sector: string
  value_score: number
  conviction_grade: string
  current_price: number | null
  analyst_upside_pct: number | null
  fcf_yield_pct: number | null
  risk_reward_ratio: number | null
  days_in_value: number
  streak_days: number
  entry_score: number
  signal: 'STRONG_BUY' | 'BUY' | 'MONITOR' | 'WAIT'
  signals_fired: string[]
  signals_pts: Array<{ name: string; pts: number }>
  signals_missing: string[]
  rsi: number | null
  earnings_warning: boolean
  days_to_earnings: number | null
}

export const fetchCerebroInsights    = () => api.get<CerebroInsights>('/api/cerebro/insights')
export const fetchCerebroConvergence = () => api.get<{ generated_at: string; total_convergences: number; triple_or_more: number; convergences: CerebroSignal[] }>('/api/cerebro/convergence')
export const fetchCerebroAlerts      = () => api.get<{ generated_at: string; total: number; high_count: number; alerts: CerebroAlert[] }>('/api/cerebro/alerts')
export const fetchCerebroCalibration = () => api.get<CerebroCalibration>('/api/cerebro/calibration')
export const fetchCerebroEntrySignals = () => api.get<{ generated_at: string; total: number; strong_buy: number; buy: number; monitor: number; wait: number; narrative: string | null; signals: EntrySignal[] }>('/api/cerebro/entry-signals')

export interface ExitSignal {
  ticker: string
  severity: 'HIGH' | 'MEDIUM' | 'LOW'
  entry_score: number
  current_score: number | null
  signal_date: string | null
  reasons: string[]
}
export const fetchCerebroExitSignals = () => api.get<{ generated_at: string; total: number; high_count: number; narrative: string | null; exits: ExitSignal[] }>('/api/cerebro/exit-signals')

export interface ValueTrap {
  ticker: string
  company_name: string
  severity: 'HIGH' | 'MEDIUM'
  trap_score: number
  value_score: number
  flags: string[]
  piotroski: number | null
  fcf_yield_pct: number | null
  fundamental_score: number | null
}
export const fetchCerebroValueTraps = () => api.get<{ generated_at: string; total: number; high_count: number; narrative: string | null; traps: ValueTrap[] }>('/api/cerebro/value-traps')

export interface SmartMoneySignal {
  ticker: string
  company_name: string
  sector: string
  value_score: number | null
  n_hedge_funds: number
  hedge_funds: string[]
  n_insiders: number
  insider_purchases: number
  convergence_score: number
  in_value: boolean
}
export const fetchCerebroSmartMoney = () => api.get<{ generated_at: string; total: number; narrative: string | null; signals: SmartMoneySignal[] }>('/api/cerebro/smart-money')

export interface InsiderCluster {
  sector: string
  ticker_count: number
  tickers: string[]
  total_purchases: number
  total_insiders: number
  cluster_score: number
  signal: 'STRONG' | 'MODERATE'
}
export const fetchCerebroInsiderClusters = () => api.get<{ generated_at: string; total: number; narrative: string | null; clusters: InsiderCluster[] }>('/api/cerebro/insider-clusters')

export interface DividendSafety {
  ticker: string
  company_name: string
  div_yield: number
  payout_ratio: number | null
  fcf_yield_pct: number | null
  interest_coverage: number | null
  safety_score: number
  rating: 'AT_RISK' | 'WATCH' | 'SAFE'
  risk_flags: string[]
  value_score: number
}
export const fetchCerebroDividendSafety = () => api.get<{ generated_at: string; total: number; at_risk: number; narrative: string | null; dividends: DividendSafety[] }>('/api/cerebro/dividend-safety')

export interface PiotroskiCandidate {
  ticker: string
  company_name: string
  piotroski_current: number
  piotroski_prev: number | null
  delta: number
  trend: 'IMPROVING' | 'SLIGHT_UP' | 'STABLE' | 'SLIGHT_DOWN' | 'DETERIORATING'
  signal: 'STRONG' | 'NEUTRAL' | 'WEAK'
  value_score: number
}
export const fetchCerebroPiotroski = () => api.get<{ generated_at: string; total: number; improving: number; narrative: string | null; candidates: PiotroskiCandidate[] }>('/api/cerebro/piotroski')

export interface StressRisk {
  type: string
  severity: 'HIGH' | 'MEDIUM' | 'LOW'
  message: string
  detail: Record<string, unknown>
}
export const fetchCerebroStressTest = () => api.get<{ generated_at: string; total_positions: number; risks: StressRisk[]; narrative: string | null; sector_breakdown: Array<{ sector: string; count: number; pct: number }>; region_breakdown: Record<string, number> }>('/api/cerebro/stress-test')

export interface CerebroBriefing {
  generated_at: string
  regime: string
  narrative: string
  sections: {
    regime: string
    strong_buy_count: number
    buy_count: number
    top_entries: [string, number][]
    top_convergences: [string, number][]
    high_alerts: [string, string][]
    traps_warning: [string, number][]
    exit_warnings: [string, string][]
    smart_money: [string, number][]
  }
}
export const fetchCerebroBriefing = () => api.get<CerebroBriefing>('/api/cerebro/briefing')

export interface ShortSqueezeSetup {
  ticker: string
  company_name: string
  sector: string
  severity: 'HIGH' | 'MEDIUM'
  squeeze_score: number
  short_pct_float: number
  piotroski: number | null
  value_score: number
  insider_buying: boolean
  hf_present: boolean
  flags: string[]
}
export const fetchCerebroShortSqueeze = () => api.get<{ generated_at: string; total: number; high_count: number; narrative: string | null; setups: ShortSqueezeSetup[] }>('/api/cerebro/short-squeeze')

export interface QualityDecay {
  ticker: string
  company_name: string
  severity: 'HIGH' | 'MEDIUM'
  decay_score: number
  value_score: number
  snapshot_date: string
  roe_prev: number | null
  roe_curr: number | null
  margin_prev: number | null
  margin_curr: number | null
  fcf_prev: number | null
  fcf_curr: number | null
  flags: string[]
}
export const fetchCerebroQualityDecay = () => api.get<{ generated_at: string; total: number; high_count: number; narrative: string | null; decays: QualityDecay[] }>('/api/cerebro/quality-decay')

export interface SectorStandout {
  ticker: string
  company_name: string
  sector: string
  label: 'BEST_IN_SECTOR' | 'PRICEY_VS_PEERS'
  fcf_yield_pct: number
  fcf_rank: number
  fcf_rank_of: number
  value_score: number
  analyst_upside_pct: number | null
  sector_avg_fcf: number | null
  peers_in_sector: number
}
export interface SectorSummary {
  sector: string
  count: number
  avg_value_score: number
  avg_fcf_yield: number | null
  rerate_potential: boolean
  tickers: string[]
}
export const fetchCerebroSectorRV = () => api.get<{ generated_at: string; total: number; rerate_sectors: number; narrative: string | null; standouts: SectorStandout[]; sector_summary: SectorSummary[] }>('/api/cerebro/sector-rv')

// ── Cerebro Daily Action Plan ─────────────────────────────────────────────────
export interface MacroPlay {
  instrument: string
  direction?: string
  thesis: string
  historical: string
  risk: string
  timeframe: string
  score: number
}

export interface DailyPlanAction {
  prioridad: number
  accion: string
  instrumento: string
  razon: string
  catalizador: string
  size_hint: string
  invalidacion: string
}

export interface DailyPlanEvitar {
  ticker: string
  razon: string
}

export interface AgendaEvent {
  fecha: string
  evento: string
  impacto: 'ALTO' | 'MEDIO' | 'BAJO'
  accion_sugerida?: string
}

export interface ValueEnEntorno {
  ticker: string
  score: number
  sector: string
  fcf_yield_pct?: number
  grade?: string
}

export interface DailyPlan {
  generated_at: string
  macro_regime: string
  composite_score: number
  sesgo: string
  confianza: number
  situacion: string
  narrativa: string
  acciones_inmediatas: DailyPlanAction[]
  macro_plays: MacroPlay[]
  macro_plays_commentary?: string
  value_en_entorno: ValueEnEntorno[]
  value_en_entorno_razon?: string
  evitar: DailyPlanEvitar[]
  agenda_semana: AgendaEvent[]
  frase_del_dia?: string
  mensaje_telegram?: string
  ai_powered: boolean
}

export async function fetchCerebroDailyPlan() {
  return api.get<DailyPlan>('/api/cerebro/daily-plan')
}

export interface LivePrice {
  symbol: string
  label: string
  kind: string
  current: number | null
  prev_close: number | null
  change_pct: number | null
}

export interface LivePricesData {
  prices: Record<string, LivePrice>
  market_open: boolean
  fetched_at: string
}

export async function fetchLivePrices() {
  return api.get<LivePricesData>('/api/live-prices')
}

export const fetchMarketRegime = () =>
  api.get<MarketRegime>('/api/market-regime')

export const fetchMacroRadar = () =>
  api.get('/api/macro-radar')

export const fetchMacroRadarHistory = () =>
  api.get<{ history: Array<{ date: string; composite_score: number; composite_pct: number; regime: string; regime_color: string }> }>('/api/macro-radar/history')

export const fetchDailyBriefing = () =>
  api.get<{ narrative: string | null; date: string | null; macro_regime?: string; picks_count?: number; top_picks?: unknown[] }>('/api/daily-briefing')

export const fetchInsidersInsight = () =>
  api.get<{ narrative: string | null; date: string | null; total_tickers?: number }>('/api/insiders-insight')

export const fetchIndustryGroupsInsight = () =>
  api.get<{ narrative: string | null; date: string | null; macro_regime?: string; top_sectors?: unknown[]; bottom_sectors?: unknown[] }>('/api/industry-groups-insight')

export const fetchOptionsFlowInsight = () =>
  api.get<{ narrative: string | null; date: string | null; total_flows?: number; sentiment_breakdown?: Record<string, number> }>('/api/options-flow-insight')

export const fetchValueEUInsight = () =>
  api.get<{ narrative: string | null; date: string | null; macro_regime?: string; picks_count?: number }>('/api/value-eu-insight')

export const fetchPortfolioInsight = () =>
  api.get<{ narrative: string | null; date: string | null; total_signals?: number; win_rate_7d?: number }>('/api/portfolio-insight')

export const analyzeTickerAI = (ticker: string) =>
  api.get<{ ticker: string; narrative: string | null; date?: string; error?: string }>(`/api/analyze-ai/${ticker}`)

export interface EarningsEntry {
  ticker: string
  company: string
  sector: string
  earnings_date: string
  days_to_earnings: number | null
  earnings_warning: boolean
  earnings_catalyst: boolean
  fundamental_score: number | null
  current_price: number | null
  analyst_upside_pct: number | null
}

export const fetchEarningsCalendar = () =>
  api.get<{ earnings: EarningsEntry[]; total: number; as_of: string }>('/api/earnings-calendar')

export interface EconEvent {
  date: string
  event: string
  type: 'FED' | 'CPI' | 'PCE' | 'JOBS' | 'EARNINGS'
  impact: 'HIGH' | 'MEDIUM'
  description: string
}

export const fetchEconomicCalendar = () =>
  api.get<{ events: EconEvent[]; total: number }>('/api/economic-calendar')

export interface DividendTrapEntry {
  ticker: string
  company: string
  sector: string
  current_price: number | null
  dividend_yield: number | null
  payout_ratio: number | null
  fcf_yield: number | null
  fundamental_score: number | null
  trap_score: number
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW'
  reasons: string[]
}

export interface DividendTrapsData {
  date: string
  total_scanned: number
  traps_high: number
  traps_medium: number
  safe_count: number
  traps: DividendTrapEntry[]
  safe_dividends: DividendTrapEntry[]
}

export const fetchDividendTraps = () =>
  api.get<DividendTrapsData>('/api/dividend-traps')

export interface DividendCalendarEvent {
  ticker: string
  company: string
  sector: string
  ex_dividend_date: string
  payment_date: string | null
  days_to_exdiv: number
  dividend_per_share: number | null
  current_price: number | null
  capture_yield_pct: number | null
  dividend_yield_annual: number | null
  fundamental_score: number | null
  value_score: number | null
  conviction_grade: string
  ai_verdict: string
  ai_confidence: string
  source: 'value_filtered'
}

export interface DividendCalendarData {
  events: DividendCalendarEvent[]
  total: number
  tickers_scanned: number
  as_of: string
}

export const fetchDividendCalendar = () =>
  api.get<DividendCalendarData>('/api/dividend-calendar')

export interface CorrelationData {
  tickers: string[]
  matrix: Record<string, number>[]
  days: number
  as_of: string
}

export const fetchCorrelationMatrix = () =>
  api.get<CorrelationData>('/api/correlation-matrix')

export interface SmartPortfolioPick {
  ticker: string
  company: string
  sector: string
  current_price: number | null
  value_score: number
  conviction_grade: string
  conviction_score: number | null
  analyst_upside_pct: number | null
  target_price_analyst: number | null
  fcf_yield_pct: number | null
  risk_reward_ratio: number | null
  dividend_yield_pct: number | null
  buyback_active: boolean
  days_to_earnings: number | null
  earnings_date: string | null
  earnings_catalyst: boolean
  stop_loss: number | null
  entry_price: number | null
  allocation_pct: number
  rank_score: number
}

export interface SmartPortfolioData {
  date: string
  timestamp: string
  regime: { name: string; color: string; description: string }
  regime_name: string
  picks: SmartPortfolioPick[]
  cash_pct: number
  total_picks: number
  invested_pct: number
  portfolio_thesis: string | null
  risk_notes: string[]
  params: { n_picks: number; min_score: number; cash_pct: number; require_rr: number }
  trap_tickers_excluded: string[]
}

export const fetchSmartPortfolio = () =>
  api.get<SmartPortfolioData>('/api/smart-portfolio')

export const fetchBacktest = () =>
  api.get('/api/backtest')

export const fetchThesis = (ticker: string) =>
  api.get<{ ticker: string; thesis: string | null }>(`/api/theses/${ticker}`)

export interface HedgeFundConsensusItem {
  ticker: string
  company_name: string
  funds_count: number
  funds_list: string
  total_value_m: number
  avg_portfolio_pct: number
  latest_date: string
}

export interface HedgeFundData {
  generated_at: string
  funds_scraped: string[]
  holdings_count: number
  top_consensus: HedgeFundConsensusItem[]
}

export const fetchHedgeFunds = () =>
  api.get<HedgeFundData>('/api/hedge-funds')

export const analyzeTicker = (ticker: string) =>
  api.get(`/api/analyze/${ticker}`)

export interface SearchResult {
  ticker: string
  company_name: string
  sector?: string
}

export const searchTickers = (q: string) =>
  api.get<{ results: SearchResult[] }>(`/api/search?q=${encodeURIComponent(q)}`)

// CSV filenames by dataset key
const CSV_FILES: Record<string, string> = {
  'value-us':       'value_opportunities.csv',
  'value-eu':       'european_value_opportunities.csv',
  'value-global':   'global_value_opportunities.csv',
  'value-us-full':  'value_conviction.csv',
  'value-eu-full':  'european_value_conviction.csv',
  'mean-reversion': 'mean_reversion_opportunities.csv',
  'insiders':       'recurring_insiders.csv',
  'insiders-eu':    'eu_recurring_insiders.csv',
  'options-flow':   'options_flow.csv',
  'momentum':       'momentum_opportunities.csv',
  'fundamental':    'fundamental_scores.csv',
  'fundamental-eu': 'european_fundamental_scores.csv',
}

export const downloadCsv = (dataset: string) => {
  const csvBase = import.meta.env.VITE_CSV_BASE as string | undefined
  const filename = CSV_FILES[dataset]
  if (!filename) return

  if (csvBase) {
    // Production: CSVs are served directly from GitHub Pages (always up-to-date)
    window.open(`${csvBase}/${filename}`, '_blank')
  } else {
    // Development: route through Vite proxy → local Flask API
    window.open(`/api/download/${dataset}`, '_blank')
  }
}

export const getCsvUrl = (dataset: string): string => {
  const csvBase = import.meta.env.VITE_CSV_BASE as string | undefined
  const filename = CSV_FILES[dataset]
  if (!filename) return ''
  if (csvBase) return `${csvBase}/${filename}`
  return `/api/download/${dataset}`
}

/** Fetch ticker→sector mapping from fundamental_scores CSVs (broad coverage) */
export const fetchTickerSectorMap = async (): Promise<Record<string, string>> => {
  const csvBase = import.meta.env.VITE_CSV_BASE as string | undefined
  const map: Record<string, string> = {}

  const fetchCsv = async (filename: string) => {
    try {
      const url = csvBase ? `${csvBase}/${filename}` : `/api/download/${filename.replace('.csv', '')}`
      const res = await fetch(url)
      if (!res.ok) return
      const rows = parseCsvRows(await res.text())
      for (const row of rows) {
        const ticker = (row.ticker || '').trim()
        const sector = (row.sector || '').trim()
        if (ticker && sector) map[ticker] = sector
      }
    } catch { /* ignore */ }
  }

  await Promise.all([
    fetchCsv('fundamental_scores.csv'),
    fetchCsv('european_fundamental_scores.csv'),
  ])
  return map
}

export interface ScoreHistoryPoint { date: string; score: number; grade: string | null }
export const fetchScoreHistory = (ticker: string) =>
  api.get<{ ticker: string; history: ScoreHistoryPoint[]; points: number }>(`/api/score-history/${ticker}`)

export interface PricePoint { date: string; close: number }
export const fetchPriceHistory = (ticker: string) =>
  api.get<{ ticker: string; prices: PricePoint[] }>(`/api/price-history/${ticker}`)

export default api

export interface FactorDetail {
  status: string
  score: number
  interpretation?: string
  academic_edge?: string
  opportunities?: number
  grade_a?: number
  grade_b?: number
  avg_upside_pct?: number
  avg_fcf_yield?: number
  avg_piotroski?: number
  pct_strong?: number
  pct_weak?: number
  avg_roic_pct?: number
  market_regime?: string
  avg_score?: number
  active_signals?: number
  cluster_buying?: number
  high_confidence?: number
  total_positions?: number
  consensus_2plus?: number
  consensus_3plus?: number
  funds_tracked?: number
  as_of?: string
  error?: string
}

export interface FactorStatusData {
  generated_at: string
  factors: {
    value?: FactorDetail
    quality?: FactorDetail
    momentum?: FactorDetail
    insider?: FactorDetail
    smart_money?: FactorDetail
  }
  combined_score: number
  factor_alignment: string
  recommendation: string
  value_momentum_correlation?: string
  value_momentum_note?: string
}

export const fetchFactorStatus = () =>
  api.get<FactorStatusData>('/api/factor-status')

export interface TechnicalSignal {
  ticker: string
  company_name: string
  source: string
  signal_name: string
  direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  timeframe: 'DAILY' | 'WEEKLY'
  triggered_date: string
  days_ago: number
  description: string
  strength: number
}

export interface TechnicalSummary {
  ticker: string
  company_name: string
  source: string
  sector: string
  bullish_count: number
  bearish_count: number
  net_signals: number
  net_score: number
  bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  top_bullish_signal: string
  top_bearish_signal: string
  most_recent_signal: string
  generated_at: string
}

const TECH_SUMMARY_NUMERIC = new Set(['bullish_count','bearish_count','net_signals','net_score'])

export const fetchTechnicalSignals = async (): Promise<{ signals: TechnicalSignal[]; summary: TechnicalSummary[] }> => {
  const csvBase = import.meta.env.VITE_CSV_BASE as string | undefined

  // Development: use local API endpoint
  if (!csvBase) {
    const res = await api.get<{ signals: TechnicalSignal[]; summary: TechnicalSummary[] }>('/api/technical-signals')
    return res.data
  }

  // Production: read CSVs directly from GitHub Pages
  const [resSig, resSum] = await Promise.all([
    fetch(`${csvBase}/technical_signals.csv`),
    fetch(`${csvBase}/technical_signals_summary.csv`)
  ])
  if (!resSig.ok || !resSum.ok) throw new Error('Technical signals CSV not available yet')
  const [textSig, textSum] = await Promise.all([resSig.text(), resSum.text()])

  const signals = parseCsvRows(textSig).map(row => {
    const obj: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(row)) {
      if (k === 'days_ago' || k === 'strength') obj[k] = v === '' ? 0 : Number(v)
      else obj[k] = v === '' ? '' : v
    }
    return obj as unknown as TechnicalSignal
  })
  const summary = parseCsvRows(textSum).map(row => {
    const obj: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(row)) {
      if (TECH_SUMMARY_NUMERIC.has(k)) obj[k] = v === '' ? 0 : Number(v)
      else obj[k] = v === '' ? '' : v
    }
    return obj as unknown as TechnicalSummary
  })
  return { signals, summary }
}
