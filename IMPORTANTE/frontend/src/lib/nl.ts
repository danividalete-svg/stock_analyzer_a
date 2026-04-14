/**
 * nl.ts — Natural Language Interpretation Engine
 *
 * Converts raw scores, signals, and metrics into plain Spanish sentences
 * for display across all pages. No AI calls — deterministic, instant.
 */

// ─── Value Score ──────────────────────────────────────────────────────────────

export function nlValueScore(score: number, grade?: string): string {
  const g = grade?.toUpperCase() ?? ''
  if (score >= 80) return `Puntuación excepcional (top 5%). ${g ? `Grado ${g}.` : ''} Fundamentos + momentum + flujo institucional alineados.`
  if (score >= 70) return `Puntuación muy alta (top 15%). ${g ? `Grado ${g}.` : ''} Fundamentos sólidos con señales técnicas favorables.`
  if (score >= 60) return `Puntuación alta (top 30%). ${g ? `Grado ${g}.` : ''} Oportunidad value con sesgo positivo.`
  if (score >= 50) return `Puntuación media-alta. Merece seguimiento pero con catalizador pendiente.`
  if (score >= 40) return `Puntuación media. Varios factores en rojo — esperar mejora de fundamentos.`
  return `Puntuación baja. No cumple los filtros mínimos para una entrada value.`
}

export function nlGrade(grade: string): string {
  const g = grade.toUpperCase()
  if (g === 'A+' || g === 'EXCELLENT') return 'Grado A+ — Alta convicción. Fundamentos + técnico + flujo alineados. Posición principal.'
  if (g === 'A' || g === 'STRONG')     return 'Grado A — Alta convicción. Fundamentos y técnico sólidos. Posición normal.'
  if (g === 'B+')                       return 'Grado B+ — Convicción media-alta. Buen perfil value con algún riesgo pendiente.'
  if (g === 'B' || g === 'MODERATE')   return 'Grado B — Convicción media. Válido con catalizador visible en 30–60 días.'
  if (g === 'C' || g === 'WEAK')       return 'Grado C — Convicción baja. Seguimiento únicamente, no entrada.'
  if (g === 'D')                        return 'Grado D — No recomendado. Fundamentales débiles o sobre-valorado.'
  return `Grado ${grade}`
}

// ─── Bounce / Mean Reversion ──────────────────────────────────────────────────

export function nlBounceSetup(opts: {
  ticker: string
  drawdown_pct: number
  rsi: number
  rsi_tier?: string
  bounce_confidence?: number
  value_score?: number | null
  days_to_earnings?: number | null
  earnings_warning?: boolean
  consecutive_down_days?: number
  dark_pool_signal?: string | null
  connors_signal?: boolean
  hammer_candle?: boolean
}): string {
  const parts: string[] = []

  // Caída
  const d = Math.abs(opts.drawdown_pct)
  if (opts.consecutive_down_days && opts.consecutive_down_days >= 3) {
    parts.push(`Caída del ${d.toFixed(0)}% en ${opts.consecutive_down_days} sesiones consecutivas`)
  } else {
    parts.push(`Caída del ${d.toFixed(0)}% desde máximos`)
  }

  // RSI
  if (opts.rsi_tier === 'EXTREMO') {
    parts.push(`RSI ${opts.rsi.toFixed(0)} — sobreventa extrema, zona de compra histórica`)
  } else if (opts.rsi_tier === 'ALTO') {
    parts.push(`RSI ${opts.rsi.toFixed(0)} — sobreventa significativa`)
  } else {
    parts.push(`RSI ${opts.rsi.toFixed(0)}`)
  }

  // VALUE base
  if (opts.value_score != null && opts.value_score >= 60) {
    parts.push(`empresa fundamentalmente sólida (VALUE ${opts.value_score.toFixed(0)}pts)`)
  } else if (opts.value_score != null && opts.value_score >= 40) {
    parts.push(`fundamentos aceptables`)
  }

  // Señales adicionales
  const extras: string[] = []
  if (opts.connors_signal) extras.push('señal Connors RSI2')
  if (opts.hammer_candle)  extras.push('vela de reversión')
  if (opts.dark_pool_signal === 'ACCUMULATION') extras.push('acumulación dark pool')
  if (extras.length) parts.push(extras.join(' + '))

  // Riesgo earnings
  if (opts.earnings_warning) {
    parts.push(`⚠️ earnings en ${opts.days_to_earnings ?? '?'} días — riesgo binario`)
  }

  return parts.join('. ') + '.'
}

export function nlBounceConfidence(score: number): string {
  if (score >= 75) return 'Muy alta probabilidad de rebote según señales históricas'
  if (score >= 60) return 'Alta probabilidad de rebote. Múltiples señales técnicas confirmadas'
  if (score >= 45) return 'Probabilidad moderada. Esperar confirmación de volumen'
  if (score >= 30) return 'Probabilidad baja. Solo para seguimiento'
  return 'Señal débil — no entrar todavía'
}

// ─── Portfolio Position ───────────────────────────────────────────────────────

export function nlPositionStatus(opts: {
  pl_pct: number
  action: string
  cerebro_exit?: boolean
  cerebro_trap?: boolean
  cerebro_smart_money?: boolean
  days_to_earnings?: number | null
  earnings_warning?: boolean
  optimal_size_pct?: number
  portfolio_pct?: number
  value_score?: number | null
}): string {
  const parts: string[] = []

  // P&L
  const pl = opts.pl_pct
  if (pl >= 12)       parts.push(`Ganancia del ${pl.toFixed(1)}% — cerca del objetivo de beneficios`)
  else if (pl >= 5)   parts.push(`Ganancia del ${pl.toFixed(1)}% — posición en terreno positivo`)
  else if (pl >= 0)   parts.push(`Ganancia del ${pl.toFixed(1)}% — inicio de posición correcto`)
  else if (pl >= -5)  parts.push(`Pérdida leve del ${Math.abs(pl).toFixed(1)}% — dentro del margen normal`)
  else if (pl >= -8)  parts.push(`Pérdida del ${Math.abs(pl).toFixed(1)}% — cerca del stop loss (-8%)`)
  else               parts.push(`⚠️ Pérdida del ${Math.abs(pl).toFixed(1)}% — stop loss superado, revisar tesis`)

  // Acción
  if (opts.action === 'AÑADIR')  parts.push('oportunidad para ampliar posición')
  if (opts.action === 'REDUCIR') parts.push('considerar reducir exposición')
  if (opts.action === 'VENDER')  parts.push('señal de salida activa')

  // Cerebro warnings
  if (opts.cerebro_exit)       parts.push('⚠️ Cerebro detectó señal de salida')
  if (opts.cerebro_trap)       parts.push('⚠️ Posible trampa de dividendo')
  if (opts.cerebro_smart_money) parts.push('Smart money activo en este ticker')

  // Earnings
  if (opts.earnings_warning && opts.days_to_earnings != null) {
    parts.push(`earnings en ${opts.days_to_earnings} días — riesgo binario`)
  }

  // Tamaño
  if (opts.portfolio_pct != null && opts.optimal_size_pct != null) {
    const ratio = opts.portfolio_pct / opts.optimal_size_pct
    if (ratio > 1.5)  parts.push('posición sobreponderada')
    else if (ratio < 0.5 && opts.optimal_size_pct > 1) parts.push('posición infraponderada')
  }

  return parts.join('. ') + '.'
}

// ─── Owner Earnings / Valuation ───────────────────────────────────────────────

export function nlValuation(opts: {
  ticker: string
  current_price: number
  intrinsic_value?: number | null
  upside_pct?: number | null
  ev_fcf?: number | null
  pe_ratio?: number | null
  fcf_yield_pct?: number | null
  sector?: string
}): string {
  const parts: string[] = []

  if (opts.intrinsic_value && opts.current_price) {
    const disc = ((opts.intrinsic_value - opts.current_price) / opts.current_price) * 100
    if (disc >= 25)      parts.push(`Cotiza con un descuento del ${disc.toFixed(0)}% sobre el valor intrínseco calculado — margen de seguridad amplio`)
    else if (disc >= 10) parts.push(`Descuento del ${disc.toFixed(0)}% sobre valor intrínseco — precio atractivo`)
    else if (disc >= 0)  parts.push(`Cotiza cerca del valor intrínseco — precio justo`)
    else                 parts.push(`Cotiza con prima del ${Math.abs(disc).toFixed(0)}% sobre valor intrínseco — requiere crecimiento futuro`)
  }

  if (opts.ev_fcf && opts.ev_fcf > 0) {
    if (opts.ev_fcf <= 15)       parts.push(`EV/FCF ${opts.ev_fcf.toFixed(1)}x — múltiplo bajo, negocio generador de caja`)
    else if (opts.ev_fcf <= 25)  parts.push(`EV/FCF ${opts.ev_fcf.toFixed(1)}x — valoración razonable`)
    else if (opts.ev_fcf <= 40)  parts.push(`EV/FCF ${opts.ev_fcf.toFixed(1)}x — precio ya incorpora crecimiento importante`)
    else                          parts.push(`EV/FCF ${opts.ev_fcf.toFixed(1)}x — valoración exigente`)
  }

  if (opts.fcf_yield_pct && opts.fcf_yield_pct > 0) {
    if (opts.fcf_yield_pct >= 8)  parts.push(`FCF yield del ${opts.fcf_yield_pct.toFixed(1)}% — la empresa genera mucha caja relativa al precio`)
    else if (opts.fcf_yield_pct >= 5) parts.push(`FCF yield del ${opts.fcf_yield_pct.toFixed(1)}% — rentabilidad de caja saludable`)
    else                               parts.push(`FCF yield del ${opts.fcf_yield_pct.toFixed(1)}%`)
  }

  if (!parts.length) {
    parts.push(`Análisis de valoración basado en Owner Earnings y FCF normalizado`)
  }

  return parts.join('. ') + '.'
}

// ─── Alerts ───────────────────────────────────────────────────────────────────

export function nlAlert(opts: {
  type: string
  ticker: string
  severity: string
  details?: string
}): string {
  const t = opts.type?.toLowerCase() ?? ''
  const ticker = opts.ticker.toUpperCase()

  if (t.includes('exit') || t.includes('salida'))  return `${ticker}: señal de salida activa. ${opts.details ?? 'Revisar posición.'}`
  if (t.includes('trap') || t.includes('trampa'))  return `${ticker}: posible trampa — dividendo o valoración engañosa. Precaución.`
  if (t.includes('mr_zone') || t.includes('reversion')) return `${ticker}: precio en zona de reversión técnica. Posible rebote en próximas sesiones.`
  if (t.includes('smart') || t.includes('money'))  return `${ticker}: actividad institucional inusual. Smart money tomando posición.`
  if (t.includes('insider'))                         return `${ticker}: compras significativas de insiders en los últimos 30 días.`
  if (t.includes('earnings') || t.includes('earn')) return `${ticker}: earnings próximos — riesgo binario elevado.`
  if (t.includes('breakdown') || t.includes('baja')) return `${ticker}: ruptura de soporte clave. Reevaluar tesis.`
  if (t.includes('upgrade'))                         return `${ticker}: analistas mejoran recomendación — catalizador positivo.`
  if (t.includes('downgrade'))                       return `${ticker}: analistas reducen recomendación — revisar fundamentos.`

  return opts.details ?? `${ticker}: señal activa de tipo ${opts.type}.`
}

// ─── Market Regime ────────────────────────────────────────────────────────────

export function nlMarketRegime(regime: string, score?: number): string {
  const r = regime?.toUpperCase() ?? ''
  if (r.includes('EXPANSION') || r.includes('BULL'))    return 'Mercado en expansión — condiciones favorables para estrategias VALUE y momentum'
  if (r.includes('CORRECTION') || r.includes('CORRECT')) return 'Mercado en corrección — priorizar posiciones con alto margen de seguridad'
  if (r.includes('BEAR'))                                 return 'Mercado bajista — reducir exposición, mantener solo alta convicción'
  if (r.includes('ACCUMULATION'))                         return 'Fase de acumulación — smart money tomando posición antes de próximo impulso'
  if (r.includes('DISTRIBUTION'))                         return 'Distribución detectada — institucionales reduciendo exposición, cautela'
  if (r.includes('NEUTRAL') || r.includes('SIDEWAYS'))   return 'Mercado lateral — selección de acciones más importante que el timing del mercado'
  if (score != null) {
    if (score >= 70) return 'Régimen técnicamente positivo — amplitud de mercado saludable'
    if (score >= 40) return 'Régimen mixto — discriminar entre sectores'
    return 'Régimen débil — posiciones defensivas'
  }
  return `Régimen de mercado: ${regime}`
}

// ─── Macro ────────────────────────────────────────────────────────────────────

export function nlMacroSignal(signal: string, value?: number): string {
  const s = signal?.toUpperCase() ?? ''
  if (s === 'BULLISH')      return 'Señal alcista — condiciones macroeconómicas favorables para renta variable'
  if (s === 'BEARISH')      return 'Señal bajista — presión macro sobre el mercado'
  if (s === 'NEUTRAL')      return 'Señal neutral — sin sesgo macro claro'
  if (s === 'RISK_ON')      return 'Modo risk-on activo — flujo hacia activos de riesgo'
  if (s === 'RISK_OFF')     return 'Modo risk-off — flujo hacia activos defensivos y liquidez'
  if (s === 'RATE_HIKE')    return 'Subida de tipos — presión sobre valoraciones growth, mejor value'
  if (s === 'RATE_CUT')     return 'Bajada de tipos — viento de cola para renta variable'
  if (s === 'INFLATION')    return `Inflación ${value != null ? `${value.toFixed(1)}%` : 'elevada'} — buscar negocios con poder de fijación de precios`
  return signal
}

// ─── Options Flow ─────────────────────────────────────────────────────────────

export function nlOptionsSignal(opts: {
  signal: string
  interpretation?: string
  premium?: number
  pcr?: number
}): string {
  const s = opts.signal?.toUpperCase() ?? ''
  const i = opts.interpretation?.toUpperCase() ?? ''
  const prem = opts.premium ? `${opts.premium > 1_000_000 ? `$${(opts.premium / 1_000_000).toFixed(1)}M` : `$${(opts.premium / 1_000).toFixed(0)}K`} en primas` : ''

  if (i === 'PUT_COVERING') return `Cobertura de puts — institucionales cerrando posiciones bajistas. ${prem}. Señal de suelo probable.`
  if (s === 'BULLISH')      return `Flujo de opciones alcista — ${prem}. Compras agresivas de calls por encima del dinero.`
  if (s === 'BEARISH')      return `Flujo bajista — ${prem}. Puts fuera del dinero con volumen inusual.`
  if (s === 'MIXED')        return `Flujo mixto — actividad en ambas direcciones. Sin sesgo claro.`
  return opts.signal
}

// ─── Insider Activity ─────────────────────────────────────────────────────────

export function nlInsiderActivity(opts: {
  confidence: number
  transaction_type?: string
  shares?: number
  value_usd?: number
}): string {
  const parts: string[] = []
  const t = opts.transaction_type?.toUpperCase() ?? ''

  if (opts.confidence >= 80) parts.push('Señal insider de muy alta convicción')
  else if (opts.confidence >= 60) parts.push('Señal insider de alta convicción')
  else if (opts.confidence >= 40) parts.push('Actividad insider moderada')
  else parts.push('Actividad insider leve')

  if (t.includes('BUY') || t.includes('COMPRA')) {
    if (opts.value_usd && opts.value_usd > 1_000_000) {
      parts.push(`compra por $${(opts.value_usd / 1_000_000).toFixed(1)}M — compromiso significativo de capital propio`)
    } else if (opts.value_usd) {
      parts.push(`compra por $${(opts.value_usd / 1_000).toFixed(0)}K — directivos comprando con dinero propio`)
    }
  } else if (t.includes('SELL') || t.includes('VENTA')) {
    parts.push('venta de directivos — puede ser rutinaria o señal de cautela')
  }

  return parts.join('. ') + '.'
}

// ─── Score color helpers ──────────────────────────────────────────────────────

export function scoreColor(score: number): string {
  if (score >= 70) return 'text-emerald-400'
  if (score >= 55) return 'text-green-400'
  if (score >= 40) return 'text-amber-400'
  if (score >= 25) return 'text-orange-400'
  return 'text-red-400'
}

export function plColor(pct: number): string {
  if (pct >= 10) return 'text-emerald-400'
  if (pct >= 3)  return 'text-green-400'
  if (pct >= 0)  return 'text-green-300'
  if (pct >= -5) return 'text-amber-400'
  if (pct >= -8) return 'text-orange-400'
  return 'text-red-400'
}

// ─── Generic helpers ──────────────────────────────────────────────────────────

export function pctLabel(pct: number, pos = '+'): string {
  return `${pct >= 0 ? pos : ''}${pct.toFixed(1)}%`
}

export function currencyLabel(val: number, currency = 'USD'): string {
  const sym = currency === 'EUR' ? '€' : '$'
  if (Math.abs(val) >= 1_000_000) return `${sym}${(val / 1_000_000).toFixed(1)}M`
  if (Math.abs(val) >= 1_000)     return `${sym}${(val / 1_000).toFixed(0)}K`
  return `${sym}${val.toFixed(0)}`
}
