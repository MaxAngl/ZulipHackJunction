// Client HTTP typé. Les types viennent de schema.d.ts, généré depuis contract/openapi.json :
// ne jamais les écrire à la main, lancer `npm run gen:api`.
import type { components } from './schema'

type Schemas = components['schemas']
export type HealthResponse = Schemas['HealthResponse']
export type LoopState = Schemas['LoopState']
export type ZoneState = Schemas['ZoneState']
export type FormatState = Schemas['FormatState']
export type CandidateState = Schemas['CandidateState']
export type MessageState = Schemas['MessageState']
export type HistoryEntry = Schemas['HistoryEntry']
export type Person = Schemas['Person']
export type SendRequest = Schemas['SendRequest']
export type PatientAction = Schemas['RespondRequest']['action']
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

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health')
}

export function getLoop(): Promise<LoopState> {
  return request<LoopState>('/api/loop')
}

// Étape 1 : nouvelle mesure de l'état du patient.
export function setTheta(theta: number): Promise<LoopState> {
  return post<LoopState>('/api/loop/theta', { theta })
}

// Étapes 2 à 6 : zone, génération, mesure, trois propositions.
export function propose(): Promise<LoopState> {
  return post<LoopState>('/api/loop/propose')
}

// Étapes 7 et 8 : l'aidant envoie une demande.
export function send(body: SendRequest): Promise<LoopState> {
  return post<LoopState>('/api/loop/send', body)
}

export function skip(): Promise<LoopState> {
  return post<LoopState>('/api/loop/skip')
}

// Étapes 9 à 12 : réponse du patient, puis apprentissage.
export function respond(action: PatientAction): Promise<LoopState> {
  return post<LoopState>('/api/loop/respond', { action })
}

export function reset(): Promise<LoopState> {
  return post<LoopState>('/api/loop/reset')
}
