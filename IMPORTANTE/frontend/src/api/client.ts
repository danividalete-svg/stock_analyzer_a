/**
 * API client — standalone version, no Supabase auth.
 * Vite proxy forwards /api → http://localhost:5002 (api_server.py).
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '',   // empty: Vite dev proxy handles /api → localhost:5002
  timeout: 60000,
})

export default api
