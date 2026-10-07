const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

let parsedApiBaseUrl: URL
try {
  parsedApiBaseUrl = new URL(configuredApiBaseUrl)
} catch {
  throw new Error('VITE_API_BASE_URL must be a valid absolute URL.')
}

if (parsedApiBaseUrl.protocol !== 'http:' && parsedApiBaseUrl.protocol !== 'https:') {
  throw new Error('VITE_API_BASE_URL must use HTTP or HTTPS.')
}

export const apiBaseUrl = parsedApiBaseUrl.toString().replace(/\/$/, '')
