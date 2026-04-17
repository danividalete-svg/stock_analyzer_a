import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'

export type Theme = 'dark' | 'light' | 'noir'

interface ThemeCtx {
  theme: Theme
  toggle: () => void
  setTheme: (t: Theme) => void
}

const Ctx = createContext<ThemeCtx>({ theme: 'dark', toggle: () => {}, setTheme: () => {} })

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    try { return (localStorage.getItem('sa-theme') as Theme) || 'dark' }
    catch { return 'dark' }
  })

  useEffect(() => {
    const root = document.documentElement
    // dark class — required by shadcn tokens
    if (theme === 'light') root.classList.remove('dark')
    else root.classList.add('dark')
    // noir attribute — activates noir-theme.css overrides
    if (theme === 'noir') root.setAttribute('data-theme', 'noir')
    else root.removeAttribute('data-theme')
    try { localStorage.setItem('sa-theme', theme) } catch { /* ignore */ }
  }, [theme])

  const setTheme = (t: Theme) => setThemeState(t)
  const toggle = () => setThemeState(t => t === 'dark' ? 'light' : t === 'light' ? 'dark' : 'dark')

  return <Ctx.Provider value={{ theme, toggle, setTheme }}>{children}</Ctx.Provider>
}

export const useTheme = () => useContext(Ctx)
