import { Component, type ReactNode, type ErrorInfo } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-[60vh] flex flex-col items-center justify-center p-8 text-center">
          <div className="text-5xl mb-4 opacity-30">⚠️</div>
          <h2 className="text-lg font-bold text-foreground mb-2">Algo salió mal</h2>
          <p className="text-sm text-muted-foreground mb-4 max-w-md">
            {this.state.error.message || 'Error inesperado en esta sección.'}
          </p>
          <button
            onClick={() => this.setState({ error: null })}
            className="text-xs px-4 py-2 rounded border border-primary/40 text-primary hover:bg-primary/10 transition-colors"
          >
            Reintentar
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
