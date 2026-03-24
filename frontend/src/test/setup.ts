import '@testing-library/jest-dom'

// Vitest 4.x persistent localStorage feature can provide a broken localStorage
// when --localstorage-file has no valid path. Ensure a full in-memory implementation.
const makeStorage = () => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = String(value) },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { store = {} },
    get length() { return Object.keys(store).length },
    key: (i: number) => Object.keys(store)[i] ?? null,
  }
}

Object.defineProperty(globalThis, 'localStorage', { value: makeStorage(), writable: true })
Object.defineProperty(globalThis, 'sessionStorage', { value: makeStorage(), writable: true })
