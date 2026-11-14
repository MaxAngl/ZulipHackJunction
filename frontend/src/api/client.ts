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
export type TypingSignals = Schemas['TypingSignals']
export type ErrorResponse = Schemas['ErrorResponse']
export type AppUser = Schemas['AppUser']
export type AccountRole = AppUser['role']
export type Role = Schemas['SignupRequest']['role']
export type SessionResponse = Schemas['SessionResponse']
export type SignupRequest = Schemas['SignupRequest']
export type ProfileUpdate = Schemas['ProfileUpdate']
export type PublicProfile = Schemas['PublicProfile']
export type OpenNeed = Schemas['OpenNeed']
export type Thread = Schemas['Thread']
export type ThreadMessage = Schemas['ThreadMessage']
export type ThreadsResponse = Schemas['ThreadsResponse']
export type Attachment = Schemas['Attachment']
export type FeedbackCategory = Schemas['FeedbackRequest']['category']
export type ClinicianHome = Schemas['ClinicianHome']
export type ClinicianPatient = Schemas['ClinicianPatient']
export type ClinicianNotes = Schemas['ClinicianNotes']
export type AdminHome = Schemas['AdminHome']
export type AdminMember = Schemas['AdminMember']
export type AdminExchange = Schemas['AdminExchange']
export type AdminFeedback = Schemas['AdminFeedback']
export type HelperHome = Schemas['HelperHome']
export type PatientHome = Schemas['PatientHome']
export type AppRequest = Schemas['AppRequest']
export type AppProposal = Schemas['AppProposal']
export type WatchStatus = Schemas['WatchStatus']
export type WatchReading = Schemas['WatchReading']

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

// `token` identifie la session dans la vraie app. La console de démo n'en a pas besoin.
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

function sendJson<T>(
  method: 'POST' | 'PUT' | 'PATCH',
  path: string,
  body?: unknown,
  token?: string,
): Promise<T> {
  return request<T>(
    path,
    { method, body: body === undefined ? undefined : JSON.stringify(body) },
    token,
  )
}

function post<T>(path: string, body?: unknown, token?: string): Promise<T> {
  return sendJson<T>('POST', path, body, token)
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

// Étapes 9 à 12 : réponse du patient, puis apprentissage. `typing` : la frappe relevée
// pendant qu'il écrivait (voir src/typing.ts), si l'écran la mesure.
export function respond(
  action: PatientAction,
  typing?: TypingSignals,
): Promise<LoopState> {
  return post<LoopState>('/api/loop/respond', { action, typing })
}

export function reset(): Promise<LoopState> {
  return post<LoopState>('/api/loop/reset')
}

// --- Vraie app -------------------------------------------------------------------------

// --- Comptes : inscription, connexion, profil ------------------------------------------

export function signup(body: SignupRequest): Promise<SessionResponse> {
  return post<SessionResponse>('/api/app/signup', body)
}

// Tout compte se connecte ici : aidant, patient, clinicien ou admin.
export function login(
  email: string,
  password: string,
): Promise<SessionResponse> {
  return post<SessionResponse>('/api/app/login', { email, password })
}

export function logout(token: string): Promise<unknown> {
  return post<unknown>('/api/app/logout', undefined, token)
}

export function getMe(token: string): Promise<AppUser> {
  return request<AppUser>('/api/app/me', undefined, token)
}

export function updateMe(token: string, body: ProfileUpdate): Promise<AppUser> {
  return sendJson<AppUser>('PATCH', '/api/app/me', body, token)
}

// Message à l'équipe ; `token` facultatif : un visiteur peut écrire aussi.
export function sendFeedback(
  token: string | null,
  category: FeedbackCategory,
  message: string,
): Promise<unknown> {
  return post<unknown>(
    '/api/app/feedback',
    { category, message },
    token ?? undefined,
  )
}

// --- Fils de discussion : demandes et besoins ------------------------------------------

export function getThreads(token: string): Promise<ThreadsResponse> {
  return request<ThreadsResponse>('/api/app/threads', undefined, token)
}

// Patient face à une demande : c'est sa réponse, avec la frappe relevée.
// Aidant après la réponse : son premier message est son merci.
export function postMessage(
  token: string,
  threadId: string,
  text: string,
  attachments: Attachment[] = [],
  typing?: TypingSignals,
): Promise<ThreadsResponse> {
  return post<ThreadsResponse>(
    `/api/app/threads/${encodeURIComponent(threadId)}/messages`,
    { text, attachments, typing },
    token,
  )
}

export function declineThread(
  token: string,
  threadId: string,
): Promise<ThreadsResponse> {
  return post<ThreadsResponse>(
    `/api/app/threads/${encodeURIComponent(threadId)}/decline`,
    undefined,
    token,
  )
}

export function postNeed(
  token: string,
  text: string,
): Promise<ThreadsResponse> {
  return post<ThreadsResponse>('/api/app/patient/needs', { text }, token)
}

export function takeNeed(
  token: string,
  needId: string,
): Promise<ThreadsResponse> {
  return post<ThreadsResponse>(
    `/api/app/helper/needs/${encodeURIComponent(needId)}/take`,
    undefined,
    token,
  )
}

// --- Portails : clinicien et admin -----------------------------------------------------

export function getClinicianHome(token: string): Promise<ClinicianHome> {
  return request<ClinicianHome>('/api/clinician', undefined, token)
}

export function saveClinicianNotes(
  token: string,
  patientId: string,
  notes: ClinicianNotes,
): Promise<ClinicianHome> {
  return sendJson<ClinicianHome>(
    'PUT',
    `/api/clinician/patients/${encodeURIComponent(patientId)}/notes`,
    notes,
    token,
  )
}

export function getAdminHome(token: string): Promise<AdminHome> {
  return request<AdminHome>('/api/admin', undefined, token)
}

export function resolveFeedback(
  token: string,
  feedbackId: string,
  resolved: boolean,
): Promise<AdminHome> {
  return post<AdminHome>(
    `/api/admin/feedback/${encodeURIComponent(feedbackId)}`,
    { resolved },
    token,
  )
}

// --- Écrans d'origine : aidant et patient ----------------------------------------------

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

// `typing` est facultatif : la frappe relevée par `useTypingSignals` (src/typing.ts).
export function replyToRequest(
  token: string,
  requestId: string,
  text: string,
  typing?: TypingSignals,
): Promise<PatientHome> {
  return post<PatientHome>(
    '/api/app/patient/reply',
    { request_id: requestId, text, typing },
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

// --- Montre Garmin du patient ----------------------------------------------------------

export function getWatch(token: string): Promise<WatchStatus> {
  return request<WatchStatus>('/api/app/patient/watch', undefined, token)
}

// `code` : les six chiffres qu'affiche l'app Needed sur la montre.
export function linkWatch(token: string, code: string): Promise<WatchStatus> {
  return post<WatchStatus>('/api/app/patient/watch', { code }, token)
}

export function unlinkWatch(token: string): Promise<WatchStatus> {
  return request<WatchStatus>(
    '/api/app/patient/watch',
    { method: 'DELETE' },
    token,
  )
}
