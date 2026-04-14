#!/usr/bin/env python3
"""
Script para analizar compras recurrentes de insiders en los últimos meses
Detecta patrones de múltiples compras que indican alta confianza
FILTRADO al universo curado (curated_tickers.py) — solo tickers que seguimos.
"""
import pandas as pd
import glob
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import json

try:
    from curated_tickers import ALL_TICKERS
    UNIVERSE = set(t.upper() for t in ALL_TICKERS)
except ImportError:
    UNIVERSE = None  # sin filtro si no está disponible

def load_insider_csvs(days_back=90):
    """Carga todos los CSVs de insider de los últimos N días"""
    print(f"📂 Cargando CSVs de insider de los últimos {days_back} días...")

    # Buscar todos los CSVs en docs/reports/daily/
    csv_pattern = "docs/reports/daily/report_*/data.csv"
    csv_files = glob.glob(csv_pattern)

    print(f"   Encontrados {len(csv_files)} archivos CSV")

    # Filtrar por fecha
    cutoff_date = datetime.now() - timedelta(days=days_back)
    recent_csvs = []

    for csv_file in csv_files:
        # Extraer fecha del path (report_YYYY-MM-DD)
        parts = csv_file.split('/')
        for part in parts:
            if part.startswith('report_'):
                date_str = part.replace('report_', '')
                try:
                    file_date = datetime.strptime(date_str, '%Y-%m-%d')
                    if file_date >= cutoff_date:
                        recent_csvs.append((csv_file, file_date))
                except:
                    pass

    recent_csvs.sort(key=lambda x: x[1], reverse=True)
    print(f"   ✅ {len(recent_csvs)} CSVs recientes seleccionados")

    # Cargar todos los CSVs
    all_data = []
    for csv_file, file_date in recent_csvs:
        try:
            df = pd.read_csv(csv_file)

            # Ajustar columnas (están corridas)
            # Ticker column = timestamp
            # Insider column = ticker real
            # Title column = compañía
            # Date column = insider title (Dir, CEO, etc)
            # Type column = transaction type

            # Crear dataframe corregido
            corrected_df = pd.DataFrame({
                'Date': file_date.strftime('%Y-%m-%d'),
                'Ticker': df['Insider'],
                'Company': df['Title'],
                'InsiderTitle': df['Date'],
                'TransactionType': df['Type'],
                'Price': df['Price'],
                'Qty': df['Qty'],
                'Owned': df['Owned']
            })

            # Filtrar solo compras (P - Purchase)
            purchases = corrected_df[corrected_df['TransactionType'].str.contains('P -', na=False)]

            if not purchases.empty:
                all_data.append(purchases)
        except Exception as e:
            print(f"   ⚠️  Error leyendo {csv_file}: {e}")

    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        print(f"   ✅ Total transacciones de compra (universo completo): {len(combined_df)}")
        if UNIVERSE:
            before = len(combined_df)
            combined_df = combined_df[combined_df['Ticker'].str.upper().isin(UNIVERSE)]
            print(f"   🎯 Filtrado a universo curado: {len(combined_df)}/{before} transacciones ({combined_df['Ticker'].nunique()} tickers únicos)")
        return combined_df
    else:
        print("   ❌ No se encontraron datos")
        return pd.DataFrame()

def analyze_recurring_purchases(df):
    """Analiza compras recurrentes por ticker e insider"""
    print("\n🔍 ANALIZANDO COMPRAS RECURRENTES")
    print("=" * 60)

    # Análisis por ticker
    ticker_counts = defaultdict(lambda: {'count': 0, 'dates': [], 'insiders': set(), 'total_qty': 0, 'company': ''})

    for _, row in df.iterrows():
        ticker = row['Ticker']
        date = row['Date']
        insider_title = row['InsiderTitle']
        qty = row['Qty']
        company = row.get('Company', ticker)

        ticker_counts[ticker]['count'] += 1
        ticker_counts[ticker]['dates'].append(date)
        ticker_counts[ticker]['insiders'].add(insider_title)
        ticker_counts[ticker]['company'] = company  # Guardar nombre de empresa
        try:
            ticker_counts[ticker]['total_qty'] += float(qty)
        except:
            pass

    # Filtrar tickers con múltiples compras (>=2)
    recurring_tickers = []
    for ticker, data in ticker_counts.items():
        if data['count'] >= 2:
            # Calcular días entre primera y última compra
            dates = sorted(data['dates'])
            first_date = datetime.strptime(dates[0], '%Y-%m-%d')
            last_date = datetime.strptime(dates[-1], '%Y-%m-%d')
            days_span = (last_date - first_date).days

            # Número de insiders únicos
            unique_insiders = len(data['insiders'])

            recurring_tickers.append({
                'ticker': ticker,
                'company': data['company'],
                'purchase_count': data['count'],
                'unique_insiders': unique_insiders,
                'days_span': days_span,
                'first_purchase': dates[0],
                'last_purchase': dates[-1],
                'total_qty': data['total_qty'],
                'confidence_score': data['count'] * 20 + unique_insiders * 10  # Score simple
            })

    # Ordenar por score de confianza
    recurring_tickers.sort(key=lambda x: x['confidence_score'], reverse=True)

    print(f"✅ Encontrados {len(recurring_tickers)} tickers con compras recurrentes")

    # Top 10
    print(f"\n🏆 TOP 10 COMPRAS RECURRENTES (Alta Confianza):")
    print("-" * 60)
    for i, item in enumerate(recurring_tickers[:10], 1):
        print(f"{i:2}. {item['ticker']:6} - {item['purchase_count']} compras, "
              f"{item['unique_insiders']} insiders, "
              f"{item['days_span']} días, "
              f"Score: {item['confidence_score']}")

    return recurring_tickers

def generate_recurring_insiders_report(df, recurring_tickers):
    """Genera reporte HTML de compras recurrentes"""
    print("\n📊 GENERANDO REPORTE HTML")
    print("=" * 60)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Generar tabla HTML
    rows_html = ""
    for i, item in enumerate(recurring_tickers[:50], 1):
        confidence_color = "#48bb78" if item['confidence_score'] >= 60 else "#f6ad55" if item['confidence_score'] >= 40 else "#4299e1"
        confidence_label = "🟢 MUY ALTA" if item['confidence_score'] >= 60 else "🟡 ALTA" if item['confidence_score'] >= 40 else "🔵 MODERADA"

        rows_html += f"""
        <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
            <td style="padding: 1rem; text-align: center;">{i}</td>
            <td style="padding: 1rem;">
                <div style="font-weight: 700; color: var(--glass-accent); font-size: 1.1rem;">{item['ticker']}</div>
                <div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.25rem;">{item['company']}</div>
            </td>
            <td style="padding: 1rem; text-align: center; font-weight: 700;">{item['purchase_count']}</td>
            <td style="padding: 1rem; text-align: center;">{item['unique_insiders']}</td>
            <td style="padding: 1rem; text-align: center;">{item['days_span']}</td>
            <td style="padding: 1rem; font-size: 0.9rem;">{item['first_purchase']}</td>
            <td style="padding: 1rem; font-size: 0.9rem;">{item['last_purchase']}</td>
            <td style="padding: 1rem; text-align: center; color: {confidence_color}; font-weight: 700;">{item['confidence_score']}</td>
            <td style="padding: 1rem; color: {confidence_color}; font-weight: 600;">{confidence_label}</td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔁 Recurring Insider Purchases | High Confidence Signals</title>
    <style>
        :root {{
            --glass-primary: rgba(99, 102, 241, 0.8);
            --glass-secondary: rgba(139, 92, 246, 0.7);
            --glass-accent: rgba(59, 130, 246, 0.9);
            --glass-bg: rgba(255, 255, 255, 0.03);
            --glass-border: rgba(255, 255, 255, 0.1);
            --text-primary: rgba(255, 255, 255, 0.95);
            --text-secondary: rgba(255, 255, 255, 0.7);
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
            background: #020617;
            color: var(--text-primary);
            line-height: 1.6;
            padding: 2rem;
        }}

        .container {{ max-width: 1800px; margin: 0 auto; }}

        .glass-card {{
            background: var(--glass-bg);
            backdrop-filter: blur(20px) saturate(180%);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}

        h1 {{
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, var(--glass-primary), var(--glass-accent));
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 1rem;
            text-align: center;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin: 2rem 0;
        }}

        .stat-box {{
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 1.5rem;
            text-align: center;
        }}

        .stat-number {{
            font-size: 2.5rem;
            font-weight: 900;
            background: linear-gradient(135deg, var(--glass-accent), var(--glass-primary));
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}

        .stat-label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th {{
            padding: 1rem;
            text-align: left;
            border-bottom: 2px solid var(--glass-border);
            color: var(--text-primary);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85rem;
            letter-spacing: 0.5px;
        }}

        .back-link {{
            display: inline-block;
            padding: 0.75rem 1.5rem;
            background: linear-gradient(135deg, var(--glass-primary), var(--glass-accent));
            color: white;
            text-decoration: none;
            border-radius: 12px;
            font-weight: 600;
            margin-bottom: 2rem;
            transition: all 0.3s ease;
        }}

        .back-link:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(99, 102, 241, 0.3);
        }}
    </style>
</head>
<body>
    <div class="container">
        <a href="https://tantancansado.github.io/stock_analyzer_a" class="back-link">🏠 Volver al Dashboard</a>

        <div class="glass-card">
            <h1>🔁 Recurring Insider Purchases</h1>
            <p style="text-align: center; color: var(--text-secondary); margin-bottom: 1rem;">
                High Confidence Signals - Múltiples Compras en los Últimos 3 Meses
            </p>
            <p style="text-align: center; color: var(--text-secondary); font-size: 0.9rem;">
                📅 {timestamp}
            </p>
        </div>

        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-number">{len(df)}</div>
                <div class="stat-label">Total Compras</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{len(recurring_tickers)}</div>
                <div class="stat-label">Tickers Recurrentes</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{len([x for x in recurring_tickers if x['confidence_score'] >= 60])}</div>
                <div class="stat-label">Confianza MUY ALTA</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{len([x for x in recurring_tickers if x['purchase_count'] >= 3])}</div>
                <div class="stat-label">3+ Compras</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{len([x for x in recurring_tickers if x['unique_insiders'] >= 2])}</div>
                <div class="stat-label">Múltiples Insiders</div>
            </div>
        </div>

        <div class="glass-card">
            <h2 style="color: var(--text-primary); margin-bottom: 1.5rem;">🏆 Top Compras Recurrentes</h2>
            <p style="color: var(--text-secondary); margin-bottom: 2rem;">
                Estos tickers han tenido múltiples compras de insiders en los últimos 90 días,
                indicando alta confianza por parte de ejecutivos y directores.
            </p>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th style="text-align: center;">#</th>
                            <th>Ticker</th>
                            <th style="text-align: center;">Compras</th>
                            <th style="text-align: center;">Insiders</th>
                            <th style="text-align: center;">Días</th>
                            <th>Primera Compra</th>
                            <th>Última Compra</th>
                            <th style="text-align: center;">Score</th>
                            <th>Confianza</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="glass-card" style="text-align: center; color: var(--text-secondary);">
            <h3 style="color: var(--text-primary); margin-bottom: 1rem;">💡 Cómo Interpretar Este Análisis</h3>
            <div style="text-align: left; max-width: 1000px; margin: 0 auto;">
                <p style="margin-bottom: 1rem;">
                    <strong style="color: var(--text-primary);">🟢 Confianza MUY ALTA (Score ≥60):</strong>
                    Múltiples compras (3+) o múltiples insiders comprando. Señal muy fuerte de confianza interna.
                </p>
                <p style="margin-bottom: 1rem;">
                    <strong style="color: var(--text-primary);">🟡 Confianza ALTA (Score ≥40):</strong>
                    2-3 compras recientes. Patrón positivo que merece seguimiento.
                </p>
                <p style="margin-bottom: 1rem;">
                    <strong style="color: var(--text-primary);">🔵 Confianza MODERADA (Score <40):</strong>
                    Compras recurrentes pero con menor frecuencia. Vigilar evolución.
                </p>
                <p style="margin-top: 2rem; font-size: 0.9rem;">
                    ⚠️ Nota: Este análisis es informativo. Siempre realiza tu propia investigación antes de invertir.
                </p>
            </div>
        </div>

        <div class="glass-card" style="text-align: center; color: var(--text-secondary);">
            <p>🔁 Recurring Insider Purchases Analysis • Powered by Advanced Pattern Detection</p>
            <p style="font-size: 0.85rem; margin-top: 0.5rem;">
                Sistema completo: Insider Trading • DJ Sectorial • Market Breadth • Enhanced Opportunities • VCP Scanner
            </p>
        </div>
    </div>
</body>
</html>"""

    # Guardar HTML
    output_path = Path("docs/recurring_insiders.html")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ Reporte HTML generado: {output_path}")

    # Guardar CSV
    csv_output_path = Path("docs/recurring_insiders.csv")
    recurring_df = pd.DataFrame(recurring_tickers)
    recurring_df.to_csv(csv_output_path, index=False)
    print(f"✅ Datos CSV guardados: {csv_output_path}")

    return str(output_path)

if __name__ == "__main__":
    # Cargar datos de los últimos 90 días
    df = load_insider_csvs(days_back=90)

    if not df.empty:
        # Analizar compras recurrentes
        recurring_tickers = analyze_recurring_purchases(df)

        if recurring_tickers:
            # Generar reporte
            html_path = generate_recurring_insiders_report(df, recurring_tickers)

            print("\n🎉 ANÁLISIS COMPLETADO")
            print(f"   📊 Reporte HTML: {html_path}")
            print(f"   📈 {len(recurring_tickers)} tickers con compras recurrentes identificados")
            print(f"   🟢 {len([x for x in recurring_tickers if x['confidence_score'] >= 60])} con confianza MUY ALTA")
        else:
            print("\n⚠️  No se encontraron compras recurrentes")
    else:
        print("\n❌ No se pudieron cargar datos")
