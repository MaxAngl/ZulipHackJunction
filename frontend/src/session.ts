import type { Role } from './api/client'

// Un jeton par rôle : le même navigateur peut tenir un compte aidant et un compte patient,
// ce qui permet d'essayer les deux côtés sur une seule machine.
function key(role: Role): string {
  return `needed.token.${role}`
}

export function readToken(role: Role): string | null {
  try {
    return window.localStorage.getItem(key(role))
  } catch {
    return null
  }
}

export function saveToken(role: Role, token: string): void {
  try {
    window.localStorage.setItem(key(role), token)
  } catch {
    // Stockage indisponible (navigation privée) : le compte ne survivra pas au rechargement.
  }
}

export function clearToken(role: Role): void {
  try {
    window.localStorage.removeItem(key(role))
  } catch {
    // Rien à effacer.
  }
}

export function saveClinicianEmail(email: string): void {
  try {
    window.localStorage.setItem('needed.clinician_email', email)
  } catch {
    // ignore
  }
}

export function readClinicianEmail(): string | null {
  try {
    return window.localStorage.getItem('needed.clinician_email')
  } catch {
    return null
  }
}

export type UserProfile = {
  firstName: string
  lastName: string
  birthDate: string
  city: string
  avatarUrl?: string
  clinicianEmail?: string
  bio?: string
  interests?: string[]
  passionPhotos?: string[]
  allowProfileView?: boolean
}

export function saveUserProfile(role: Role, profile: UserProfile): void {
  try {
    window.localStorage.setItem(
      `needed.profile.${role}`,
      JSON.stringify(profile),
    )
  } catch {
    // ignore
  }
}

export function readUserProfile(role: Role): UserProfile | null {
  try {
    const raw = window.localStorage.getItem(`needed.profile.${role}`)
    return raw ? (JSON.parse(raw) as UserProfile) : null
  } catch {
    return null
  }
}

export type ClinicianNotes = {
  mood: string
  whatMakesThemProud: string
  whatTheyLoveDoing: string
  updatedAt: string
}

export function saveClinicianNotes(notes: ClinicianNotes): void {
  try {
    window.localStorage.setItem('needed.clinician_notes', JSON.stringify(notes))
  } catch {
    // ignore
  }
}

export function readClinicianNotes(): ClinicianNotes {
  try {
    const raw = window.localStorage.getItem('needed.clinician_notes')
    if (raw) return JSON.parse(raw) as ClinicianNotes
  } catch {
    // ignore
  }
  return {
    mood: 'Calm, receptive, steady recovery pace',
    whatMakesThemProud:
      'Mastering sourdough baking; volunteering at the community greenhouse',
    whatTheyLoveDoing:
      'Gardening, listening to classic jazz vinyl, reading Scandinavian novels',
    updatedAt: new Date().toLocaleDateString('fr-FR'),
  }
}

export type ThemePreference = 'auto' | 'light' | 'dark'

export function saveThemePreference(pref: ThemePreference): void {
  try {
    window.localStorage.setItem('needed.theme', pref)
    applyTheme(pref)
  } catch {
    // ignore
  }
}

export function readThemePreference(): ThemePreference {
  try {
    const raw = window.localStorage.getItem('needed.theme')
    if (raw === 'light' || raw === 'dark' || raw === 'auto') return raw
  } catch {
    // ignore
  }
  return 'auto'
}

export function applyTheme(pref: ThemePreference): void {
  const isDark =
    pref === 'dark' ||
    (pref === 'auto' &&
      window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches)

  if (isDark) {
    document.documentElement.setAttribute('data-theme', 'dark')
  } else {
    document.documentElement.removeAttribute('data-theme')
  }
}

export type MessageAttachment = {
  type: 'image' | 'video' | 'file'
  name: string
  url: string
  size?: string
}

export type ConversationMessage = {
  id: string
  senderRole: Role
  senderName: string
  text: string
  timestamp: string
  attachments?: MessageAttachment[]
}

export type ConversationThread = {
  id: string
  peerName: string
  peerRole: Role
  peerAvatar?: string
  lastMessageText: string
  lastMessageTime: string
  isRead: boolean
  isFinished: boolean
  messages: ConversationMessage[]
  helperMessageCount: number
  peerProfile?: {
    firstName: string
    lastName: string
    birthDate?: string
    city?: string
    avatarUrl?: string
    bio?: string
    interests?: string[]
    passionPhotos?: string[]
    allowProfileView?: boolean
  }
}

function threadsStorageKey(role: Role): string {
  return `needed.threads.${role}`
}

export function readThreads(role: Role): ConversationThread[] {
  try {
    const raw = window.localStorage.getItem(threadsStorageKey(role))
    if (raw) return JSON.parse(raw) as ConversationThread[]
  } catch {
    // ignore
  }

  // Si l'utilisateur connecté sur ce navigateur a déjà son profil, on lie directement
  // les deux comptes pour une vraie interaction en miroir.
  const helperProfile = readUserProfile('helper')
  const patientProfile = readUserProfile('patient')

  if (role === 'helper') {
    const peerName = patientProfile
      ? `${patientProfile.firstName} ${patientProfile.lastName}`.trim()
      : 'Test1 Patient'

    return [
      {
        id: 'thread-patient-main',
        peerName,
        peerRole: 'patient',
        peerAvatar: patientProfile?.avatarUrl ?? '/moomins/Muumipeikko2.jpg',
        lastMessageText: 'Merci beaucoup ! Vos conseils m’ont beaucoup aidé.',
        lastMessageTime: '10:15',
        isRead: false,
        isFinished: false,
        helperMessageCount: 1,
        peerProfile: {
          firstName: patientProfile?.firstName ?? 'Test1',
          lastName: patientProfile?.lastName ?? 'Patient',
          birthDate: patientProfile?.birthDate ?? '1995-04-12',
          city: patientProfile?.city ?? 'Helsinki',
          avatarUrl: patientProfile?.avatarUrl ?? '/moomins/Muumipeikko2.jpg',
          bio:
            patientProfile?.bio ??
            'Membre patient de la communauté Needed. Passionné de pâtisserie, tricot et activités calmes.',
          interests: patientProfile?.interests ?? [
            'knitting',
            'baking',
            'ceremonie militaire',
          ],
          passionPhotos: patientProfile?.passionPhotos ?? [
            '/moomins/Muumipeikko2.jpg',
          ],
          allowProfileView: patientProfile?.allowProfileView ?? true,
        },
        messages: [
          {
            id: 'm1',
            senderRole: 'helper',
            senderName: helperProfile ? helperProfile.firstName : 'Vous',
            text: 'Bonjour ! Comment se passe votre journée aujourd’hui ? Avez-vous besoin d’un coup de main ?',
            timestamp: '09:45',
          },
          {
            id: 'm2',
            senderRole: 'patient',
            senderName: patientProfile ? patientProfile.firstName : 'Patient',
            text: 'Bonjour ! Tout va bien, merci. Vos conseils m’ont beaucoup aidé pour ma recette.',
            timestamp: '10:15',
          },
        ],
      },
    ]
  } else {
    const peerName = helperProfile
      ? `${helperProfile.firstName} ${helperProfile.lastName}`.trim()
      : 'Rami Chagnaud-Aidant'

    return [
      {
        id: 'thread-helper-main',
        peerName,
        peerRole: 'helper',
        peerAvatar: helperProfile?.avatarUrl,
        lastMessageText:
          'Bonjour ! Comment se passe votre journée aujourd’hui ? Avez-vous besoin d’un coup de main ?',
        lastMessageTime: '09:45',
        isRead: false,
        isFinished: false,
        helperMessageCount: 1,
        peerProfile: {
          firstName: helperProfile?.firstName ?? 'Rami',
          lastName: helperProfile?.lastName ?? 'Chagnaud-Aidant',
          birthDate: helperProfile?.birthDate ?? '1990-06-20',
          city: helperProfile?.city ?? 'Helsinki',
          avatarUrl: helperProfile?.avatarUrl,
          bio:
            helperProfile?.bio ??
            'Aidant bénévole engagé au sein de la communauté Needed. Passionné de cuisine, photographie et vidéo.',
          interests: helperProfile?.interests ?? [
            'cooking',
            'photography',
            'woodworking',
            'moovie-making',
            'video-games',
          ],
          passionPhotos: helperProfile?.passionPhotos ?? [],
          allowProfileView: helperProfile?.allowProfileView ?? true,
        },
        messages: [
          {
            id: 'p-m1',
            senderRole: 'helper',
            senderName: helperProfile ? helperProfile.firstName : 'Rami',
            text: 'Bonjour ! Comment se passe votre journée aujourd’hui ? Avez-vous besoin d’un coup de main ?',
            timestamp: '09:45',
          },
          {
            id: 'p-m2',
            senderRole: 'patient',
            senderName: patientProfile ? patientProfile.firstName : 'Vous',
            text: 'Bonjour ! Tout va bien, merci. Vos conseils m’ont beaucoup aidé pour ma recette.',
            timestamp: '10:15',
          },
        ],
      },
    ]
  }
}

export function saveThreads(role: Role, threads: ConversationThread[]): void {
  try {
    window.localStorage.setItem(
      threadsStorageKey(role),
      JSON.stringify(threads),
    )
  } catch {
    // ignore
  }
}

export type PatientCommunityNeed = {
  id: string
  patientName: string
  patientAvatar?: string
  text: string
  timestamp: string
  answered: boolean
}

export function savePatientCommunityNeed(need: PatientCommunityNeed): void {
  try {
    const existing = readPatientCommunityNeeds()
    window.localStorage.setItem(
      'needed.patient_community_needs',
      JSON.stringify([need, ...existing]),
    )
  } catch {
    // ignore
  }
}

export function readPatientCommunityNeeds(): PatientCommunityNeed[] {
  try {
    const raw = window.localStorage.getItem('needed.patient_community_needs')
    if (raw) return JSON.parse(raw) as PatientCommunityNeed[]
  } catch {
    // ignore
  }
  return []
}

export function dismissPatientCommunityNeed(id: string): void {
  try {
    const existing = readPatientCommunityNeeds()
    const updated = existing.filter((item) => item.id !== id)
    window.localStorage.setItem(
      'needed.patient_community_needs',
      JSON.stringify(updated),
    )
  } catch {
    // ignore
  }
}
