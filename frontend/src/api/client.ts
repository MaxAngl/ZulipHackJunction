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
export type AppUser = Schemas['AppUser']
export type Role = AppUser['role']
export type SessionResponse = Schemas['SessionResponse']
export type HelperHome = Schemas['HelperHome']
export type PatientHome = Schemas['PatientHome']
export type AppRequest = Schemas['AppRequest']
export type AppProposal = Schemas['AppProposal']

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

// `token` identifie l'appareil dans la vraie app. La console de démo n'en a pas besoin.
async function request<T>(
  path: string,
  init?: RequestInit,
  token?: string,
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['X-Needed-Token'] = token
  const response = await fetch(path, { ...init, headers })
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

function post<T>(path: string, body?: unknown, token?: string): Promise<T> {
  return request<T>(
    path,
    {
      method: 'POST',
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    token,
  )
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health')
}

// --- Console de démo -------------------------------------------------------------------

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

// --- Vraie app -------------------------------------------------------------------------

export function join(
  role: Role,
  name: string,
  interests: string[],
): Promise<SessionResponse> {
  return post<SessionResponse>('/api/app/join', { role, name, interests })
}

export function getHelperHome(token: string): Promise<HelperHome> {
  return request<HelperHome>('/api/app/helper', undefined, token)
}

export function suggest(token: string): Promise<HelperHome> {
  return post<HelperHome>('/api/app/helper/suggest', undefined, token)
}

export function sendToPatient(
  token: string,
  body: SendRequest,
): Promise<HelperHome> {
  return post<HelperHome>('/api/app/helper/send', body, token)
}

export function skipSuggestions(token: string): Promise<HelperHome> {
  return post<HelperHome>('/api/app/helper/skip', undefined, token)
}

export function sayThanks(
  token: string,
  requestId: string,
  text: string,
): Promise<HelperHome> {
  return post<HelperHome>(
    '/api/app/helper/thanks',
    { request_id: requestId, text },
    token,
  )
}

export function getPatientHome(token: string): Promise<PatientHome> {
  return request<PatientHome>('/api/app/patient', undefined, token)
}

export function replyToRequest(
  token: string,
  requestId: string,
  text: string,
): Promise<PatientHome> {
  return post<PatientHome>(
    '/api/app/patient/reply',
    { request_id: requestId, text },
    token,
  )
}

export function declineRequest(
  token: string,
  requestId: string,
): Promise<PatientHome> {
  return post<PatientHome>(
    '/api/app/patient/decline',
    { request_id: requestId },
    token,
  )
}
