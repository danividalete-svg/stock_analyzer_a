#!/usr/bin/env python3
"""
CONVICTION FILTER — Filtro final de conviccion para VALUE
Cruza todos los datos disponibles y produce un ranking de ALTA CONVICCION.

Lo que hace (exactamente lo que haria un analista humano):
1. ROE alto + deuda baja = empresa excepcional
2. FCF Yield alto = genera caja real
3. DCF vs precio = esta infravalorada o sobrevalorada?
4. Analistas: consenso + numero de cobertura
5. Revenue growth positivo = negocio creciendo
6. R:R >= 2 = buena relacion riesgo/recompensa
7. Buyback/dividendo = devuelve dinero al accionista
8. Payout sostenible = dividendo no en peligro
9. Sin earnings warning = timing seguro
10. Cross-validation: si DCF dice sobrevalorada, descarta

Output: conviction_score (0-100) + conviction_grade (A/B/C/D)
Solo pasan al dashboard las de grado A y B.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import ast
import argparse
from datetime import datetime


def extract_health_metrics(row) -> dict:
    """Extrae ROE, deuda, margenes de health_details y earnings_details"""
    result = {
        'roe': None,
        'debt_to_equity': None,
        'op_margin': None,
        'profit_margin': None,
        'current_ratio': None,
    }

    field_map = {
        'health_details': {
            'roe_pct': 'roe',
            'debt_to_equity': 'debt_to_equity',
            'operating_margin_pct': 'op_margin',
            'current_ratio': 'current_ratio',
        },
        'earnings_details': {
            'profit_margin_pct': 'profit_margin',
        },
    }

    for col, targets in field_map.items():
        raw = row.get(col, '{}')
        if raw and str(raw) not in ('', 'nan', 'None', '{}'):
            try:
                data = ast.literal_eval(str(raw)) if isinstance(raw, str) else raw
                if isinstance(data, dict):
                    for src_key, dst_key in targets.items():
                        val = data.get(src_key)
                        if val is not None:
                            result[dst_key] = val
            except:
                pass

    # Fallback: try direct columns
    if result['roe'] is None:
        result['roe'] = _sf(row.get('roe_pct'))
    if result['debt_to_equity'] is None:
        result['debt_to_equity'] = _sf(row.get('debt_to_equity'))

    return result


def _sf(val, default=None):
    """Safe float conversion"""
    if val is None or str(val).lower() in ('nan', 'none', '', 'n/a'):
        return default
    try:
        v = float(val)
        return v if not np.isnan(v) else default
    except (ValueError, TypeError):
        return default


def calculate_conviction_score(row) -> dict:
    """
    Calcula conviction score para una oportunidad VALUE.
    Returns dict con conviction_score, conviction_grade, conviction_reasons
    """
    score = 0.0
    max_score = 0.0
    reasons = []
    red_flags = []

    # Extract health metrics
    health = extract_health_metrics(row)
    roe = health['roe']
    debt_eq = health['debt_to_equity']
    op_margin = health['op_margin']
    profit_margin = health['profit_margin']

    # ─── HARD DISQUALIFIERS (Lynch/Graham value principles) ───────────────────
    # Rule 1: D/E > 5x → reject. High leverage inflates ROE and amplifies downside.
    if debt_eq is not None and debt_eq > 5:
        return {
            'conviction_score': 0.0,
            'conviction_grade': 'D',
            'conviction_reasons': f'HARD REJECT: Deuda {debt_eq:.1f}x D/E (>5x — apalancamiento excesivo)',
            'conviction_positives': 0,
            'conviction_red_flags': 1,
        }

    # Rule 2: Operating margin negative → reject. Core business is losing money.
    if op_margin is not None and op_margin < 0:
        return {
            'conviction_score': 0.0,
            'conviction_grade': 'D',
            'conviction_reasons': f'HARD REJECT: Margen operativo {op_margin:.1f}% (negativo — operacion pierde dinero)',
            'conviction_positives': 0,
            'conviction_red_flags': 1,
        }
    # ──────────────────────────────────────────────────────────────────────────

    # ─── 1. ROE (max 15pts) ───
    max_score += 15
    if roe is not None:
        if roe >= 25:
            score += 15
            reasons.append(f"ROE {roe:.0f}% (excelente)")
        elif roe >= 15:
            score += 10
            reasons.append(f"ROE {roe:.0f}% (bueno)")
        elif roe >= 10:
            score += 5
        elif roe < 5:
            red_flags.append(f"ROE bajo ({roe:.0f}%)")

    # ─── 2. Deuda (max 10pts) ───
    max_score += 10
    if debt_eq is not None:
        if debt_eq < 0.3:
            score += 10
            reasons.append(f"Deuda minima ({debt_eq:.2f})")
        elif debt_eq < 0.7:
            score += 7
        elif debt_eq < 1.5:
            score += 3
        elif debt_eq >= 2.5:
            score -= 3
            red_flags.append(f"Deuda alta ({debt_eq:.1f})")

    # ─── 3. FCF Yield (max 12pts) ───
    max_score += 12
    fcf = _sf(row.get('fcf_yield_pct'))
    if fcf is not None:
        if fcf >= 8:
            score += 12
            reasons.append(f"FCF Yield {fcf:.1f}% (excelente)")
        elif fcf >= 5:
            score += 9
            reasons.append(f"FCF Yield {fcf:.1f}% (bueno)")
        elif fcf >= 3:
            score += 5
        elif fcf < 0:
            score -= 5
            red_flags.append("FCF negativo (quema caja)")

    # ─── 4. DCF Valuation cross-check (max 15pts) ───
    # Skip DCF for London-listed stocks (.L suffix) — prices in pence, DCF in GBP → false negative
    max_score += 15
    price = _sf(row.get('current_price'))
    dcf = _sf(row.get('target_price_dcf'))
    ticker_str = str(row.get('ticker', ''))
    is_london = ticker_str.upper().endswith('.L')

    # Quality compounders (MSFT, SPGI, etc.) trade at justified high multiples that a
    # simple DCF undervalues. When 15+ analysts with strong_buy agree on >30% upside,
    # their models are more reliable than ours — reduce the DCF penalty accordingly.
    analyst_count_dcf = _sf(row.get('analyst_count'), 0)
    analyst_rec_dcf = str(row.get('analyst_recommendation', '')).lower()
    analyst_upside_dcf = _sf(row.get('analyst_upside_pct'), 0)
    strong_consensus = (
        analyst_count_dcf >= 15
        and analyst_rec_dcf in ('strong_buy', 'strongbuy', 'buy')
        and analyst_upside_dcf >= 30
    )

    if is_london:
        score += 5  # Neutral — don't penalise, don't reward (data units mismatch)
    elif price and dcf and price > 0:
        dcf_upside = (dcf - price) / price * 100
        if dcf_upside >= 50:
            score += 15
            reasons.append(f"DCF dice +{dcf_upside:.0f}% infravalorada")
        elif dcf_upside >= 20:
            score += 10
            reasons.append(f"DCF: +{dcf_upside:.0f}% margen")
        elif dcf_upside >= 0:
            score += 5
        elif dcf_upside < -20:
            penalty = 3 if strong_consensus else 10
            score -= penalty
            red_flags.append(f"DCF dice SOBREVALORADA ({dcf_upside:.0f}%)")
        elif dcf_upside < 0:
            penalty = 1 if strong_consensus else 3
            score -= penalty
            red_flags.append(f"DCF ligeramente por debajo ({dcf_upside:.0f}%)")

    # ─── 5. Analyst consensus (max 12pts) ───
    max_score += 12
    analyst_count = _sf(row.get('analyst_count'))
    analyst_rec = str(row.get('analyst_recommendation', '')).lower()
    analyst_upside = _sf(row.get('analyst_upside_pct'))
    if analyst_count and analyst_count >= 5:
        if analyst_rec in ('strong_buy', 'strongbuy'):
            score += 8
            reasons.append(f"Strong Buy ({int(analyst_count)} analistas)")
        elif analyst_rec in ('buy',):
            score += 6
            reasons.append(f"Buy ({int(analyst_count)} analistas)")
        elif analyst_rec in ('hold', 'neutral'):
            score += 2
        # Coverage bonus
        if analyst_count >= 15:
            score += 4
        elif analyst_count >= 8:
            score += 2
    elif analyst_count and analyst_count >= 3:
        score += 2  # Poca cobertura pero algo hay
    else:
        red_flags.append("Sin cobertura de analistas")

    # ─── 6. Revenue growth (max 8pts) ───
    max_score += 8
    rev_growth = _sf(row.get('rev_growth_yoy'))
    rev_accel = row.get('rev_accelerating')
    if rev_growth is not None:
        if rev_growth >= 20:
            score += 8
            reasons.append(f"Revenue +{rev_growth:.0f}%")
        elif rev_growth >= 10:
            score += 6
        elif rev_growth >= 3:
            score += 3
        elif rev_growth < -5:
            score -= 3
            red_flags.append(f"Revenue cayendo ({rev_growth:.0f}%)")
        if rev_accel == True:
            score += 2  # bonus aceleracion

    # ─── 7. Risk/Reward ratio (max 8pts) ───
    max_score += 8
    rr = _sf(row.get('risk_reward_ratio'))
    if rr is not None:
        if rr >= 4:
            score += 8
            reasons.append(f"R:R {rr:.1f}:1 (excelente)")
        elif rr >= 3:
            score += 6
            reasons.append(f"R:R {rr:.1f}:1 (bueno)")
        elif rr >= 2:
            score += 4
        elif rr < 1:
            score -= 3
            red_flags.append(f"R:R {rr:.1f}:1 (pobre)")

    # ─── 8. Shareholder returns: buyback + dividend (max 8pts) ───
    max_score += 8
    div = _sf(row.get('dividend_yield_pct'), 0)
    buyback = row.get('buyback_active')
    payout = _sf(row.get('payout_ratio_pct'), 0)

    if buyback == True:
        score += 3
        reasons.append("Buyback activo")
    if div and 1.0 < div <= 6.0:
        score += 3
        if payout and 0 < payout < 75:
            score += 2  # Sostenible
            reasons.append(f"Dividendo {div:.1f}% (payout {payout:.0f}%)")
        else:
            reasons.append(f"Dividendo {div:.1f}%")
    elif div and div > 8:
        red_flags.append(f"Dividendo sospechosamente alto ({div:.1f}%)")

    # ─── 9. Earnings safety (max 5pts) ───
    max_score += 5
    earnings_warning = row.get('earnings_warning')
    if earnings_warning == True:
        score -= 5
        red_flags.append("Earnings en <7 dias (riesgo)")
    else:
        score += 5

    # ─── 10. Margin quality (max 7pts) ───
    max_score += 7
    margin = profit_margin or op_margin
    if margin is not None:
        if margin >= 20:
            score += 7
            reasons.append(f"Margen {margin:.0f}% (premium)")
        elif margin >= 12:
            score += 4
        elif margin >= 5:
            score += 2
        elif margin < 0:
            score -= 5
            red_flags.append("Margen negativo")

    # ─── 11. "Fallen Angel" bonus ───────────────────────────────────────────────
    # Empresa de calidad que ha caído mucho sin motivo fundamental = oportunidad
    # Principio Lynch: comprar empresas sólidas en caídas de mercado, no de negocio
    proximity = _sf(row.get('proximity_to_52w_high'))  # negativo, ej: -32.3
    fundamentals_intact = (roe is not None and roe >= 15) and (fcf is not None and fcf >= 3)
    if proximity is not None:
        max_score += 12
    if proximity is not None and proximity <= -20:
        if fundamentals_intact:
            if proximity <= -35:
                score += 12
                reasons.append(f"Fallen Angel: -{abs(proximity):.0f}% desde max · fundamentos intactos")
            elif proximity <= -25:
                score += 9
                reasons.append(f"Gran caída: -{abs(proximity):.0f}% con ROE/FCF sólidos")
            else:
                score += 6
                reasons.append(f"Caída -{abs(proximity):.0f}% · oportunidad de entrada")
        else:
            # Caída grande SIN fundamentales — sí es una red flag
            if proximity <= -40:
                score -= 3
                red_flags.append(f"Caída -{abs(proximity):.0f}% sin fundamentos sólidos")
    elif proximity is not None and -10 <= proximity <= -5:
        # Cerca de máximos con buenos fundamentales: momentum confirmado
        if fundamentals_intact:
            score += 3

    # ─── Normalize to 0-100 ───
    conviction_score = max(0, min(100, (score / max_score) * 100)) if max_score > 0 else 0
    conviction_score = round(conviction_score, 1)

    # ─── Grade ───
    if conviction_score >= 75:
        grade = 'A'
    elif conviction_score >= 55:
        grade = 'B'
    elif conviction_score >= 40:
        grade = 'C'
    else:
        grade = 'D'

    # ─── Build summary ───
    top_reasons = reasons[:4]
    top_flags = red_flags[:3]

    summary = ' | '.join(top_reasons) if top_reasons else 'Sin razones claras'
    if top_flags:
        summary += ' || RED FLAGS: ' + ', '.join(top_flags)

    return {
        'conviction_score': conviction_score,
        'conviction_grade': grade,
        'conviction_reasons': summary,
        'conviction_positives': len(reasons),
        'conviction_red_flags': len(red_flags),
    }


def filter_by_conviction(input_path: str, output_path: str = None, min_grade: str = 'B'):
    """
    Aplica conviction filter a un CSV de oportunidades VALUE.

    Args:
        input_path: CSV con oportunidades (value_opportunities_filtered.csv o european)
        output_path: CSV de salida (si None, sobreescribe el input)
        min_grade: Grado minimo para pasar ('A', 'B', 'C', 'D')
    """
    input_p = Path(input_path)
    if not input_p.exists():
        print(f"  {input_path} no encontrado, saltando")
        return None

    df = pd.read_csv(input_p)
    # Remove any previous conviction columns to avoid duplicates
    for col in ['conviction_score', 'conviction_grade', 'conviction_reasons', 'conviction_positives', 'conviction_red_flags']:
        if col in df.columns:
            df.drop(columns=[col], inplace=True)
    print(f"\n{'='*80}")
    print(f"CONVICTION FILTER — {input_p.name}")
    print(f"{'='*80}")
    print(f"Input: {len(df)} oportunidades")

    if len(df) == 0:
        print("  Sin oportunidades para filtrar")
        if output_path:
            df.to_csv(output_path, index=False)
        return 0

    # Calculate conviction for each row
    results = []
    for _, row in df.iterrows():
        conv = calculate_conviction_score(row)
        results.append(conv)

    conv_df = pd.DataFrame(results)
    df = pd.concat([df.reset_index(drop=True), conv_df], axis=1)

    # Sort by conviction score
    df = df.sort_values('conviction_score', ascending=False)

    # Grade distribution
    for grade in ['A', 'B', 'C', 'D']:
        count = (df['conviction_grade'] == grade).sum()
        emoji = {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D'}[grade]
        print(f"  Grade {emoji}: {count} tickers")

    # Filter by minimum grade
    grade_order = {'A': 4, 'B': 3, 'C': 2, 'D': 1}
    min_grade_val = grade_order.get(min_grade, 3)
    df_filtered = df[df['conviction_grade'].map(grade_order) >= min_grade_val].copy()

    print(f"\nFiltrado (grade >= {min_grade}): {len(df_filtered)}/{len(df)}")

    # Show top results
    if len(df_filtered) > 0:
        print(f"\nTOP CONVICTION PICKS:")
        print("-" * 80)
        for _, row in df_filtered.head(15).iterrows():
            ticker = row['ticker']
            score = row['conviction_score']
            grade = row['conviction_grade']
            reasons = str(row.get('conviction_reasons', ''))[:70]
            value_s = row.get('value_score', 0)
            print(f"  [{grade}] {score:5.1f}  {ticker:<10} (value: {value_s:.0f})  {reasons}")

    # Save
    if output_path is None:
        output_path = input_path  # Overwrite
    df_filtered.to_csv(output_path, index=False)
    print(f"\nGuardado: {output_path} ({len(df_filtered)} oportunidades)")

    return len(df_filtered)


def main():
    parser = argparse.ArgumentParser(description='Conviction Filter for VALUE opportunities')
    parser.add_argument('--min-grade', default='B', choices=['A', 'B', 'C', 'D'],
                        help='Minimum conviction grade to pass (default: B)')
    parser.add_argument('--european-only', action='store_true',
                        help='Only filter European opportunities')
    parser.add_argument('--us-only', action='store_true',
                        help='Only filter US opportunities')
    args = parser.parse_args()

    print("=" * 80)
    print("CONVICTION FILTER — Filtro final de alta conviccion")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Grado minimo: {args.min_grade}")
    print("=" * 80)

    total = 0

    if not args.european_only:
        # US VALUE
        us_result = filter_by_conviction(
            'docs/value_opportunities_filtered.csv',
            output_path='docs/value_conviction.csv',
            min_grade=args.min_grade
        )
        if us_result:
            total += us_result

    if not args.us_only:
        # European VALUE — use fresh curated output (fallback to filtered if missing)
        eu_input = (
            'docs/european_value_opportunities.csv'
            if Path('docs/european_value_opportunities.csv').exists()
            else 'docs/european_value_opportunities_filtered.csv'
        )
        # EU: use grade D to keep all curated tickers with grades (table displays A/B/C/D)
        eu_result = filter_by_conviction(
            eu_input,
            output_path='docs/european_value_conviction.csv',
            min_grade='D'
        )
        if eu_result:
            total += eu_result

    print(f"\n{'='*80}")
    print(f"TOTAL oportunidades de alta conviccion: {total}")
    print("=" * 80)


if __name__ == '__main__':
    main()
