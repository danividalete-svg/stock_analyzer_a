import { fetchSectorRotation, type SectorRotationData } from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import { Badge } from '@/components/ui/badge'
import InfoTooltip from '../components/InfoTooltip'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

export default function SectorRotation() {
  const { data, loading, error } = useApi(() => fetchSectorRotation(), [])

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />

  const sr = (data as SectorRotationData) || { results: [], alerts: [] }
  const results = sr.results || []
  const alerts = sr.alerts || []

  const leading = results.filter(r => r.status === 'LEADING')
  const improving = results.filter(r => r.status === 'IMPROVING')
  const weakening = results.filter(r => r.status === 'WEAKENING')
  const lagging = results.filter(r => r.status === 'LAGGING')

  const alertVariant = (type: string): 'green' | 'red' | 'yellow' => {
    if (type.includes('IN')) return 'green'
    if (type.includes('OUT')) return 'red'
    return 'yellow'
  }

  const rotationIn = alerts.filter(a => a.type?.includes('IN')).length
  const rotationOut = alerts.filter(a => a.type?.includes('OUT')).length

  type SRResult = typeof results[0]
  const QuadrantItems = ({ items, colorCls }: { items: SRResult[], colorCls: string }) => (
    <>
      {items.map(r => (
        <div key={r.sector} className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
          <span className="text-sm font-medium">{r.sector}</span>
          <span className={`text-xs font-semibold ${colorCls}`}>
            RS {r.relative_strength?.toFixed(1)}
            {r.velocity != null && <span className="ml-1.5 opacity-70">{r.velocity > 0 ? '+' : ''}{Number(r.velocity).toFixed(1)}</span>}
          </span>
        </div>
      ))}
      {items.length === 0 && <div className="text-sm text-muted-foreground italic py-2">Ninguno</div>}
    </>
  )

  return (
    <>
      <div className="mb-7 animate-fade-in-up">
        <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Rotacion Sectorial</h2>
        <p className="text-sm text-muted-foreground">Modelo de rotacion de sectores — identifica liderazgo y debilidad relativa</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Sectores', value: results.length, sub: 'analizados', idx: 1 },
          { label: 'Leading', value: leading.length, sub: 'momentum positivo', color: 'text-emerald-400', idx: 2 },
          { label: 'Improving', value: improving.length, sub: 'ganando fuerza', color: 'text-blue-400', idx: 3 },
          { label: 'Alertas', value: alerts.length, sub: `${rotationIn} rotacion IN, ${rotationOut} OUT`, idx: 4 },
        ].map(({ label, value, sub, color, idx }) => (
          <Card key={label} className={`glass p-5 stagger-${idx}`}>
            <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">{label}</div>
            <div className={`text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2 ${color ?? ''}`}>{value}</div>
            <div className="text-[0.66rem] text-muted-foreground">{sub}</div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 mb-5">
        <Card className="glass p-5 border-emerald-500/20">
          <h4 className="text-xs font-bold uppercase tracking-widest text-emerald-400 mb-3 flex items-center">
            Leading ({leading.length})
            <InfoTooltip text="RS alta y momentum positivo (acelerando). Sectores líderes del mercado — buscar oportunidades de compra." />
          </h4>
          <QuadrantItems items={leading} colorCls="text-emerald-400" />
        </Card>
        <Card className="glass p-5 border-blue-500/20">
          <h4 className="text-xs font-bold uppercase tracking-widest text-blue-400 mb-3 flex items-center">
            Improving ({improving.length})
            <InfoTooltip text="RS baja pero momentum positivo (ganando fuerza). Sectores que empiezan a rotar al alza — posibles candidatos emergentes." />
          </h4>
          <QuadrantItems items={improving} colorCls="text-blue-400" />
        </Card>
        <Card className="glass p-5 border-amber-500/20">
          <h4 className="text-xs font-bold uppercase tracking-widest text-amber-400 mb-3 flex items-center">
            Weakening ({weakening.length})
            <InfoTooltip text="RS alta pero momentum negativo (perdiendo fuerza). Sectores que fueron líderes pero empiezan a girar — considerar reducir exposición." />
          </h4>
          <QuadrantItems items={weakening} colorCls="text-amber-400" />
        </Card>
        <Card className="glass p-5 border-red-500/20">
          <h4 className="text-xs font-bold uppercase tracking-widest text-red-400 mb-3 flex items-center">
            Lagging ({lagging.length})
            <InfoTooltip text="RS baja y momentum negativo. Sectores rezagados — evitar nuevas posiciones largas." side="bottom" />
          </h4>
          <QuadrantItems items={lagging} colorCls="text-red-400" />
        </Card>
      </div>

      {alerts.length > 0 && (
        <Card className="glass animate-fade-in-up">
          <div className="px-5 py-3 border-b border-border/50">
            <h3 className="text-sm font-semibold">Alertas de Rotacion</h3>
          </div>
          <Table>
            <TableHeader>
              <TableRow className="border-border/50 hover:bg-transparent">
                <TableHead>Tipo</TableHead>
                <TableHead>Sector</TableHead>
                <TableHead>Mensaje</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {alerts.map((a, i) => (
                <TableRow key={i}>
                  <TableCell><Badge variant={alertVariant(a.type)}>{a.type}</Badge></TableCell>
                  <TableCell className="font-mono font-bold text-primary text-[0.8rem]">{a.sector}</TableCell>
                  <TableCell className="whitespace-normal max-w-sm text-muted-foreground text-xs">{a.message}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {results.length === 0 && (
        <Card className="glass">
          <CardContent className="py-16 text-center">
            <div className="text-4xl mb-4 opacity-20">🔄</div>
            <p className="font-medium text-muted-foreground">Sin datos de rotacion sectorial</p>
          </CardContent>
        </Card>
      )}
    </>
  )
}
