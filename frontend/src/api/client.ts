// Client HTTP typé. Les types viennent de schema.d.ts, généré depuis contract/openapi.json :
// ne jamais les écrire à la main, lancer `npm run gen:api`.
import type { components } from './schema'

type Schemas = components['schemas']
export type HealthResponse = Schemas['HealthResponse']
export type PredictRequest = Schemas['PredictRequest']
export type PredictResponse = Schemas['PredictResponse']
export type ErrorResponse = Schemas['ErrorResponse']

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    const body = (await response
      .json()
      .catch(() => null)) as ErrorResponse | null
    throw new ApiError(
      response.status,
      body?.error.code ?? 'unknown_error',
      body?.error.message ?? response.statusText,
    )
  }
  return (await response.json()) as T
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health')
}

export function predict(body: PredictRequest): Promise<PredictResponse> {
  return request<PredictResponse>('/api/predict', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
