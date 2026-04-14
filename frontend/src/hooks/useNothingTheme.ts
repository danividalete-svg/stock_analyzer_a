import { useState, useEffect } from 'react'

const KEY = 'sa-nothing-theme'

export function useNothingTheme() {
  const [enabled, setEnabled] = useState(() => localStorage.getItem(KEY) === 'true')

  useEffect(() => {
    if (enabled) {
      document.body.setAttribute('data-nothing-theme', 'true')
    } else {
      document.body.removeAttribute('data-nothing-theme')
    }
    localStorage.setItem(KEY, String(enabled))
  }, [enabled])

  return { enabled, toggle: () => setEnabled(p => !p) }
}
