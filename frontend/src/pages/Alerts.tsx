import { useState, useEffect } from 'react'
import { Bell, Plus, Trash2, ToggleLeft, ToggleRight, AlertTriangle, TrendingDown, TrendingUp, CalendarDays, Loader2 } from 'lucide-react'
import { supabase } from '@/lib/supabase'
import { useAuth } from '@/context/AuthContext'
import TickerLogo from '../components/TickerLogo'
import { useToast } from '../components/Toast'

// ── Types ─────────────────────────────────────────────────────────────────────

type AlertType = 'price_below' | 'price_above' | 'drop_pct' | 'earnings_soon'

interface PriceAlert {
  id: string
  ticker: string
  alert_type: AlertType
  threshold: number | null
  email: string
  active: boolean
  last_fired: string | null
  created_at: string
}

// ── Config ────────────────────────────────────────────────────────────────────

const ALERT_TYPES: { value: AlertType; label: string; icon: typeof Bell; description: string; needs_threshold: boolean }[] = [
  { value: 'price_below',   label: 'Precio baja de',      icon: TrendingDown,  description: 'Alerta cuando el precio cae por debajo del umbral',    needs_threshold: true },
  { value: 'price_above',   label: 'Precio sube de',      icon: TrendingUp,    description: 'Alerta cuando el precio supera el umbral',             needs_threshold: true },
  { value: 'drop_pct',      label: 'Caída diaria ≥',      icon: AlertTriangle, description: 'Alerta si la acción cae ese % en el día',              needs_threshold: true },
  { value: 'earnings_soon', label: 'Earnings en 7 días',  icon: CalendarDays,  description: 'Aviso cuando hay earnings en menos de 7 días',         needs_threshold: false },
]

const TYPE_STYLES: Record<AlertType, string> = {
  price_below:   'bg-red-500/10 border-red-500/20 text-red-400',
  price_above:   'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
  drop_pct:      'bg-amber-500/10 border-amber-500/20 text-amber-400',
  earnings_soon: 'bg-blue-500/10 border-blue-500/20 text-blue-400',
}

// ── Add Alert Form ────────────────────────────────────────────────────────────

function AddAlertForm({ onAdd, userEmail }: { onAdd: () => void; userEmail: string }) {
  const { user } = useAuth()
  const { toast } = useToast()
  const [ticker,    setTicker]    = useState('')
  const [alertType, setAlertType] = useState<AlertType>('price_below')
  const [threshold, setThreshold] = useState('')
  const [email,     setEmail]     = useState(userEmail)
  const [saving,    setSaving]    = useState(false)
  const [error,     setError]     = useState('')

  const typeConfig = ALERT_TYPES.find(t => t.value === alertType)!

  const submit = async () => {
    const t = ticker.trim().toUpperCase()
    if (!t) return setError('Introduce el ticker')
    if (!email.trim()) return setError('Introduce un email')
    if (typeConfig.needs_threshold && (!threshold || parseFloat(threshold) <= 0))
      return setError('Introduce un umbral válido')
    setError(''); setSaving(true)
    const { error: err } = await supabase.from('price_alerts').insert({
      user_id: user!.id,
      ticker: t,
      alert_type: alertType,
      threshold: typeConfig.needs_threshold ? parseFloat(threshold) : null,
      email: email.trim(),
      active: true,
    })
    setSaving(false)
    if (err) { setError(err.message); toast(err.message, 'error'); return }
    setTicker(''); setThreshold('')
    toast(`Alerta creada para ${t} · ${typeConfig.label}`, 'success')
    onAdd()
  }

  return (
    <div className="glass rounded-2xl p-5 space-y-4">
      <h2 className="text-sm font-bold text-foreground flex items-center gap-2">
        <Plus size={14} className="text-primary" />
        Nueva alerta
      </h2>

      {/* Alert type */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {ALERT_TYPES.map(at => {
          const Icon = at.icon
          const active = alertType === at.value
          return (
            <button
              key={at.value}
              onClick={() => setAlertType(at.value)}
              className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border text-center transition-all text-xs font-semibold ${
                active
                  ? `${TYPE_STYLES[at.value]} border-current`
                  : 'bg-muted/20 border-border/30 text-muted-foreground hover:bg-muted/40'
              }`}
            >
              <Icon size={16} />
              {at.label}
            </button>
          )
        })}
      </div>

      <p className="text-[0.72rem] text-muted-foreground">{typeConfig.description}</p>

      {/* Fields */}
      <div className="flex flex-wrap gap-2 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">Ticker</label>
          <input
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && submit()}
            placeholder="AAPL"
            className="w-24 px-3 py-2 rounded-lg bg-muted/30 border border-border/40 text-sm font-mono font-bold text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/50"
          />
        </div>

        {typeConfig.needs_threshold && (
          <div className="flex flex-col gap-1">
            <label className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">
              {alertType === 'drop_pct' ? 'Caída (%)' : 'Precio ($)'}
            </label>
            <input
              value={threshold}
              onChange={e => setThreshold(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submit()}
              placeholder={alertType === 'drop_pct' ? '5' : '150.00'}
              type="number"
              min="0"
              step={alertType === 'drop_pct' ? '0.5' : '0.01'}
              className="w-28 px-3 py-2 rounded-lg bg-muted/30 border border-border/40 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/50"
            />
          </div>
        )}

        <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
          <label className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">Email</label>
          <input
            value={email}
            onChange={e => setEmail(e.target.value)}
            type="email"
            placeholder="tu@email.com"
            className="px-3 py-2 rounded-lg bg-muted/30 border border-border/40 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/50"
          />
        </div>

        <button
          onClick={submit}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {saving ? <Loader2 size={13} className="animate-spin" /> : <Bell size={13} />}
          Crear alerta
        </button>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}

// ── Alert Row ─────────────────────────────────────────────────────────────────

function AlertRow({ alert, onToggle, onDelete }: {
  alert: PriceAlert
  onToggle: () => void
  onDelete: () => void
}) {
  const typeConfig = ALERT_TYPES.find(t => t.value === alert.alert_type)!
  const Icon = typeConfig.icon

  const label = alert.alert_type === 'drop_pct'
    ? `Caída diaria ≥ ${alert.threshold}%`
    : alert.alert_type === 'earnings_soon'
    ? 'Earnings en 7 días'
    : alert.alert_type === 'price_below'
    ? `Precio baja de $${alert.threshold}`
    : `Precio sube de $${alert.threshold}`

  return (
    <div className={`flex items-center gap-3 p-4 rounded-xl border transition-opacity ${
      alert.active ? '' : 'opacity-50'
    } ${TYPE_STYLES[alert.alert_type]}`}>
      <TickerLogo ticker={alert.ticker} size="xs" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-sm">{alert.ticker}</span>
          <span className={`text-[0.6rem] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wide ${TYPE_STYLES[alert.alert_type]}`}>
            <Icon size={9} className="inline mr-0.5" />
            {typeConfig.label}
          </span>
        </div>
        <div className="text-[0.72rem] text-muted-foreground mt-0.5 flex items-center gap-2 flex-wrap">
          <span>{label}</span>
          <span>→ {alert.email}</span>
          {alert.last_fired && (
            <span className="text-muted-foreground/50">último aviso: {new Date(alert.last_fired).toLocaleDateString('es-ES')}</span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <button onClick={onToggle} className="text-muted-foreground hover:text-foreground transition-colors" title={alert.active ? 'Desactivar' : 'Activar'}>
          {alert.active ? <ToggleRight size={22} className="text-primary" /> : <ToggleLeft size={22} />}
        </button>
        <button onClick={onDelete} className="p-1 rounded-lg text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors">
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Alerts() {
  const { user } = useAuth()
  const [alerts,  setAlerts]  = useState<PriceAlert[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    if (!user) return
    const { data } = await supabase
      .from('price_alerts')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false })
    setAlerts((data ?? []) as PriceAlert[])
    setLoading(false)
  }

  useEffect(() => { load() }, [user]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = async (alert: PriceAlert) => {
    await supabase.from('price_alerts').update({ active: !alert.active }).eq('id', alert.id)
    setAlerts(prev => prev.map(a => a.id === alert.id ? { ...a, active: !a.active } : a))
  }

  const del = async (id: string) => {
    await supabase.from('price_alerts').delete().eq('id', id)
    setAlerts(prev => prev.filter(a => a.id !== id))
  }

  const userEmail = user?.email ?? ''
  const active = alerts.filter(a => a.active).length

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-foreground flex items-center gap-2">
          <Bell size={22} className="text-primary" />
          Alertas por Email
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          El pipeline diario comprueba tus alertas cada mañana y te envía un email cuando se cumple la condición.
        </p>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-blue-500/8 border border-blue-500/20">
        <Bell size={14} className="text-blue-400 mt-0.5 shrink-0" />
        <div className="text-[0.75rem] text-blue-300/80 space-y-1">
          <p><strong className="text-blue-300">Las alertas se comprueban cada mañana</strong> junto con el pipeline diario de análisis (~8:30 AM).</p>
          <p>Requiere que <code className="bg-blue-500/20 px-1 rounded">RESEND_API_KEY</code> esté configurado en los secretos de GitHub Actions.</p>
          {active > 0 && <p className="text-blue-400">{active} alerta{active > 1 ? 's' : ''} activa{active > 1 ? 's' : ''}.</p>}
        </div>
      </div>

      {/* Add form */}
      <AddAlertForm onAdd={load} userEmail={userEmail} />

      {/* Alert list */}
      {loading ? (
        <div className="flex justify-center py-8">
          <Loader2 size={20} className="animate-spin text-muted-foreground" />
        </div>
      ) : alerts.length === 0 ? (
        <div className="glass rounded-2xl p-12 text-center">
          <Bell size={40} className="mx-auto text-muted-foreground/30 mb-4" />
          <p className="text-foreground font-semibold mb-1">Sin alertas todavía</p>
          <p className="text-sm text-muted-foreground">Crea tu primera alerta arriba.</p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="text-[0.65rem] font-bold uppercase tracking-widest text-muted-foreground/50 px-1">
            {alerts.length} alerta{alerts.length > 1 ? 's' : ''} · {active} activa{active > 1 ? 's' : ''}
          </div>
          {alerts.map(alert => (
            <AlertRow key={alert.id} alert={alert} onToggle={() => toggle(alert)} onDelete={() => del(alert.id)} />
          ))}
        </div>
      )}
    </div>
  )
}
