import type { Role } from './api/client'

// Un jeton par rôle : le même navigateur peut tenir un compte aidant et un compte patient,
// ce qui permet d'essayer les deux côtés sur une seule machine.
function key(role: Role): string {
  return `needed.token.${role}`
}

export type SimulationAccount = {
  id: string
  token: string
  role: Role
  firstName: string
  lastName: string
  city: string
  birthDate: string
  interests: string[]
  bio: string
  avatarUrl?: string
  passionPhotos?: string[]
}

export const SIMULATION_ACCOUNTS: SimulationAccount[] = [
  // 3 Aidants
  {
    id: 'h-clara',
    token: 'token-helper-clara-1234',
    role: 'helper',
    firstName: 'Clara',
    lastName: 'Fontaine',
    city: 'Helsinki, Punavuori',
    birthDate: '1992-07-14',
    interests: ['gardening', 'cooking', 'reading'],
    bio: 'Jardinière passionnée et amoureuse de cuisine saine du potager. Toujours ravie d’échanger des astuces.',
    avatarUrl: '/moomins/Characters-04-2.svg',
    passionPhotos: [
      '/moomins/Characters-04-2.svg',
      '/moomins/Muumipeikko2.jpg',
      '/moomins/Nuuskamuikkunen.png',
    ],
  },
  {
    id: 'h-thomas',
    token: 'token-helper-thomas-5678',
    role: 'helper',
    firstName: 'Thomas',
    lastName: 'Lindqvist',
    city: 'Espoo, Tapiola',
    birthDate: '1989-11-23',
    interests: ['photography', 'cycling', 'hiking'],
    bio: 'Photographe argentique et cycliste urbain. J’aime explorer les sentiers côtiers et les parcs nationaux.',
    avatarUrl: '/moomins/Muumipappa2.jpg',
    passionPhotos: [
      '/moomins/Muumipappa2.jpg',
      '/moomins/Nuuskamuikkunen.png',
      '/moomins/Characters-04-2.svg',
    ],
  },
  {
    id: 'h-elena',
    token: 'token-helper-elena-9012',
    role: 'helper',
    firstName: 'Elena',
    lastName: 'Sjöberg',
    city: 'Vantaa, Tikkurila',
    birthDate: '1995-03-08',
    interests: ['baking', 'knitting', 'jazz'],
    bio: 'Pâtissière amatrice de brioches à la cannelle (korvapuusti) et passionnée de disques vinyles.',
    avatarUrl: '/moomins/Nuuskamuikkunen.png',
    passionPhotos: [
      '/moomins/Nuuskamuikkunen.png',
      '/moomins/Muumipeikko2.jpg',
      '/moomins/Muumipappa2.jpg',
    ],
  },

  // 3 Patients
  {
    id: 'p-julien',
    token: 'token-patient-julien-1111',
    role: 'patient',
    firstName: 'Julien',
    lastName: 'Mercier',
    city: 'Helsinki, Töölö',
    birthDate: '1994-05-18',
    interests: ['gardening', 'baking', 'reading'],
    bio: 'En rémission douce. Cultive des herbes aromatiques et teste régulièrement des recettes de pain au levain.',
    avatarUrl: '/moomins/Muumipeikko2.jpg',
    passionPhotos: [
      '/moomins/Muumipeikko2.jpg',
      '/moomins/Muumipappa2.jpg',
      '/moomins/Characters-04-2.svg',
    ],
  },
  {
    id: 'p-sofia',
    token: 'token-patient-sofia-2222',
    role: 'patient',
    firstName: 'Sofia',
    lastName: 'Hakala',
    city: 'Helsinki, Kallio',
    birthDate: '1996-09-30',
    interests: ['cooking', 'jazz', 'photography'],
    bio: 'Amoureuse de musique acoustique, de balades au bord de l’eau et de bons petits plats réconfortants.',
    avatarUrl: '/moomins/Nuuskamuikkunen.png',
    passionPhotos: [
      '/moomins/Nuuskamuikkunen.png',
      '/moomins/Muumipeikko2.jpg',
      '/moomins/Characters-04-2.svg',
    ],
  },
  {
    id: 'p-lucas',
    token: 'token-patient-lucas-3333',
    role: 'patient',
    firstName: 'Lucas',
    lastName: 'Virtanen',
    city: 'Helsinki, Ullanlinna',
    birthDate: '1991-01-25',
    interests: ['cycling', 'hiking', 'knitting'],
    bio: 'Adepte de grand air et de tricot scandinave pour garder les idées claires et apaisées.',
    avatarUrl: '/moomins/Characters-04-2.svg',
    passionPhotos: [
      '/moomins/Characters-04-2.svg',
      '/moomins/Muumipappa2.jpg',
      '/moomins/Nuuskamuikkunen.png',
    ],
  },
]

export function readToken(role: Role): string | null {
  try {
    const t = window.localStorage.getItem(key(role))
    if (t) return t
  } catch {
    // ignore
  }
  const defaultAcc = SIMULATION_ACCOUNTS.find((a) => a.role === role)
  return defaultAcc ? defaultAcc.token : null
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

export function setSimulationAccount(accountId: string): void {
  const acc = SIMULATION_ACCOUNTS.find((a) => a.id === accountId)
  if (!acc) return
  saveToken(acc.role, acc.token)
  saveUserProfile(acc.role, {
    firstName: acc.firstName,
    lastName: acc.lastName,
    birthDate: acc.birthDate,
    city: acc.city,
    interests: acc.interests,
    bio: acc.bio,
    avatarUrl: acc.avatarUrl,
    passionPhotos: acc.passionPhotos,
    allowProfileView: true,
  })
}

export function readUserProfile(role: Role): UserProfile | null {
  try {
    const raw = window.localStorage.getItem(`needed.profile.${role}`)
    if (raw) return JSON.parse(raw) as UserProfile
  } catch {
    return null
  }
  const defaultAcc = SIMULATION_ACCOUNTS.find((a) => a.role === role)
  if (!defaultAcc) return null
  return {
    firstName: defaultAcc.firstName,
    lastName: defaultAcc.lastName,
    birthDate: defaultAcc.birthDate,
    city: defaultAcc.city,
    avatarUrl: defaultAcc.avatarUrl,
    bio: defaultAcc.bio,
    interests: defaultAcc.interests,
    passionPhotos: defaultAcc.passionPhotos,
    allowProfileView: true,
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

  const helperProfile = readUserProfile('helper')
  const patientProfile = readUserProfile('patient')

  if (role === 'helper') {
    return [
      {
        id: 'thread-sim-julien',
        peerName: 'Julien Mercier',
        peerRole: 'patient',
        peerAvatar: '/moomins/Muumipeikko2.jpg',
        lastMessageText:
          'Avec plaisir ! Il faut surtout choisir un pot percé avec un lit de billes d’argile au fond et un terreau léger.',
        lastMessageTime: '10:15',
        isRead: true,
        isFinished: true,
        helperMessageCount: 1,
        peerProfile: {
          firstName: 'Julien',
          lastName: 'Mercier',
          birthDate: '1994-05-18',
          city: 'Helsinki, Töölö',
          avatarUrl: '/moomins/Muumipeikko2.jpg',
          bio: 'En rémission douce. Cultive des herbes aromatiques et teste régulièrement des recettes de pain au levain.',
          interests: ['gardening', 'baking', 'reading'],
          passionPhotos: [
            '/moomins/Muumipeikko2.jpg',
            '/moomins/Muumipappa2.jpg',
            '/moomins/Characters-04-2.svg',
          ],
          allowProfileView: true,
        },
        messages: [
          {
            id: 'm-julien-1',
            senderRole: 'helper',
            senderName: helperProfile ? helperProfile.firstName : 'Clara',
            text: 'Bonjour Julien ! Aurais-tu des astuces de jardinage pour rempoter des plantes d’intérieur en automne ?',
            timestamp: '09:45',
          },
          {
            id: 'm-julien-2',
            senderRole: 'patient',
            senderName: 'Julien',
            text: 'Avec plaisir ! Il faut surtout choisir un pot percé avec un lit de billes d’argile au fond et un terreau léger.',
            timestamp: '10:15',
          },
        ],
      },
      {
        id: 'thread-sim-sofia',
        peerName: 'Sofia Hakala',
        peerRole: 'patient',
        peerAvatar: '/moomins/Nuuskamuikkunen.png',
        lastMessageText:
          'Bonjour Sofia, je cherche des recommandations d’albums de jazz nordique pour une ambiance de lecture apaisante, as-tu des pépites ?',
        lastMessageTime: '11:30',
        isRead: false,
        isFinished: false,
        helperMessageCount: 1,
        peerProfile: {
          firstName: 'Sofia',
          lastName: 'Hakala',
          birthDate: '1996-09-30',
          city: 'Helsinki, Kallio',
          avatarUrl: '/moomins/Nuuskamuikkunen.png',
          bio: 'Amoureuse de musique acoustique, de balades au bord de l’eau et de bons petits plats réconfortants.',
          interests: ['cooking', 'jazz', 'photography'],
          passionPhotos: [
            '/moomins/Nuuskamuikkunen.png',
            '/moomins/Muumipeikko2.jpg',
            '/moomins/Characters-04-2.svg',
          ],
          allowProfileView: true,
        },
        messages: [
          {
            id: 'm-sofia-1',
            senderRole: 'helper',
            senderName: helperProfile ? helperProfile.firstName : 'Thomas',
            text: 'Bonjour Sofia, je cherche des recommandations d’albums de jazz nordique pour une ambiance de lecture apaisante, as-tu des pépites ?',
            timestamp: '11:30',
          },
        ],
      },
      {
        id: 'thread-sim-lucas',
        peerName: 'Lucas Virtanen',
        peerRole: 'patient',
        peerAvatar: '/moomins/Characters-04-2.svg',
        lastMessageText:
          'Le point mousse ou les côtes 1/1 sont idéales et très relaxantes !',
        lastMessageTime: '14:20',
        isRead: true,
        isFinished: true,
        helperMessageCount: 1,
        peerProfile: {
          firstName: 'Lucas',
          lastName: 'Virtanen',
          birthDate: '1991-01-25',
          city: 'Helsinki, Ullanlinna',
          avatarUrl: '/moomins/Characters-04-2.svg',
          bio: 'Adepte de grand air et de tricot scandinave pour garder les idées claires et apaisées.',
          interests: ['cycling', 'hiking', 'knitting'],
          passionPhotos: [
            '/moomins/Characters-04-2.svg',
            '/moomins/Muumipappa2.jpg',
            '/moomins/Nuuskamuikkunen.png',
          ],
          allowProfileView: true,
        },
        messages: [
          {
            id: 'm-lucas-1',
            senderRole: 'helper',
            senderName: helperProfile ? helperProfile.firstName : 'Elena',
            text: 'Bonjour Lucas, je prépare une écharpe en laine mérinos pour l’hiver, quel type de maille conseilles-tu pour débuter sans stress ?',
            timestamp: '13:50',
          },
          {
            id: 'm-lucas-2',
            senderRole: 'patient',
            senderName: 'Lucas',
            text: 'Le point mousse ou les côtes 1/1 sont idéales et très relaxantes !',
            timestamp: '14:20',
          },
        ],
      },
    ]
  } else {
    return [
      {
        id: 'thread-sim-clara',
        peerName: 'Clara Fontaine',
        peerRole: 'helper',
        peerAvatar: '/moomins/Characters-04-2.svg',
        lastMessageText:
          'Avec plaisir ! Il faut surtout choisir un pot percé avec un lit de billes d’argile au fond et un terreau léger.',
        lastMessageTime: '10:15',
        isRead: true,
        isFinished: true,
        helperMessageCount: 1,
        peerProfile: {
          firstName: 'Clara',
          lastName: 'Fontaine',
          birthDate: '1992-07-14',
          city: 'Helsinki, Punavuori',
          avatarUrl: '/moomins/Characters-04-2.svg',
          bio: 'Jardinière passionnée et amoureuse de cuisine saine du potager. Toujours ravie d’échanger des astuces.',
          interests: ['gardening', 'cooking', 'reading'],
          passionPhotos: [
            '/moomins/Characters-04-2.svg',
            '/moomins/Muumipeikko2.jpg',
            '/moomins/Nuuskamuikkunen.png',
          ],
          allowProfileView: true,
        },
        messages: [
          {
            id: 'p-m-clara-1',
            senderRole: 'helper',
            senderName: 'Clara',
            text: 'Bonjour Julien ! Aurais-tu des astuces de jardinage pour rempoter des plantes d’intérieur en automne ?',
            timestamp: '09:45',
          },
          {
            id: 'p-m-clara-2',
            senderRole: 'patient',
            senderName: patientProfile ? patientProfile.firstName : 'Julien',
            text: 'Avec plaisir ! Il faut surtout choisir un pot percé avec un lit de billes d’argile au fond et un terreau léger.',
            timestamp: '10:15',
          },
        ],
      },
      {
        id: 'thread-sim-thomas',
        peerName: 'Thomas Lindqvist',
        peerRole: 'helper',
        peerAvatar: '/moomins/Muumipappa2.jpg',
        lastMessageText:
          'Bonjour ! Ravi de faire votre connaissance. N’hésitez pas si vous avez besoin d’un coup de main pour vos promenades ou courses.',
        lastMessageTime: '11:00',
        isRead: true,
        isFinished: false,
        helperMessageCount: 1,
        peerProfile: {
          firstName: 'Thomas',
          lastName: 'Lindqvist',
          birthDate: '1989-11-23',
          city: 'Espoo, Tapiola',
          avatarUrl: '/moomins/Muumipappa2.jpg',
          bio: 'Photographe argentique et cycliste urbain. J’aime explorer les sentiers côtiers et les parcs nationaux.',
          interests: ['photography', 'cycling', 'hiking'],
          passionPhotos: [
            '/moomins/Muumipappa2.jpg',
            '/moomins/Nuuskamuikkunen.png',
            '/moomins/Characters-04-2.svg',
          ],
          allowProfileView: true,
        },
        messages: [
          {
            id: 'p-m-thomas-1',
            senderRole: 'helper',
            senderName: 'Thomas',
            text: 'Bonjour ! Ravi de faire votre connaissance. N’hésitez pas si vous avez besoin d’un coup de main pour vos promenades ou courses.',
            timestamp: '11:00',
          },
        ],
      },
      {
        id: 'thread-sim-elena',
        peerName: 'Elena Sjöberg',
        peerRole: 'helper',
        peerAvatar: '/moomins/Nuuskamuikkunen.png',
        lastMessageText:
          'Bonjour ! Je prépare une fournée de brioches à la cannelle, j’espère que vous passez une belle journée ensoleillée.',
        lastMessageTime: '13:10',
        isRead: false,
        isFinished: false,
        helperMessageCount: 1,
        peerProfile: {
          firstName: 'Elena',
          lastName: 'Sjöberg',
          birthDate: '1995-03-08',
          city: 'Vantaa, Tikkurila',
          avatarUrl: '/moomins/Nuuskamuikkunen.png',
          bio: 'Pâtissière amatrice de brioches à la cannelle (korvapuusti) et passionnée de disques vinyles.',
          interests: ['baking', 'knitting', 'jazz'],
          passionPhotos: [
            '/moomins/Nuuskamuikkunen.png',
            '/moomins/Muumipeikko2.jpg',
            '/moomins/Muumipappa2.jpg',
          ],
          allowProfileView: true,
        },
        messages: [
          {
            id: 'p-m-elena-1',
            senderRole: 'helper',
            senderName: 'Elena',
            text: 'Bonjour ! Je prépare une fournée de brioches à la cannelle, j’espère que vous passez une belle journée ensoleillée.',
            timestamp: '13:10',
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

export type AdminContactMessage = {
  id: string
  senderName: string
  senderRole?: 'helper' | 'patient' | 'visitor'
  category: 'bug' | 'question' | 'suggestion' | 'other'
  message: string
  timestamp: string
  resolved: boolean
}

export function saveAdminContactMessage(msg: AdminContactMessage): void {
  try {
    const list = readAdminContactMessages()
    window.localStorage.setItem(
      'needed.admin_contact_messages',
      JSON.stringify([msg, ...list]),
    )
  } catch {
    // ignore
  }
}

export function readAdminContactMessages(): AdminContactMessage[] {
  try {
    const raw = window.localStorage.getItem('needed.admin_contact_messages')
    if (raw) return JSON.parse(raw) as AdminContactMessage[]
  } catch {
    // ignore
  }
  return [
    {
      id: 'admin-msg-1',
      senderName: 'Julien Mercier',
      senderRole: 'patient',
      category: 'bug',
      message:
        'Le temps de chargement des photos de passion a pris quelques secondes ce matin lors du passage au profil.',
      timestamp: '14:05',
      resolved: false,
    },
    {
      id: 'admin-msg-2',
      senderName: 'Clara Fontaine',
      senderRole: 'helper',
      category: 'suggestion',
      message:
        'Serait-il possible de rajouter un filtre par quartier pour l’entraide de proximité dans Helsinki ?',
      timestamp: '11:45',
      resolved: true,
    },
  ]
}

export function updateAdminContactMessageStatus(
  id: string,
  resolved: boolean,
): void {
  try {
    const list = readAdminContactMessages().map((m) =>
      m.id === id ? { ...m, resolved } : m,
    )
    window.localStorage.setItem(
      'needed.admin_contact_messages',
      JSON.stringify(list),
    )
  } catch {
    // ignore
  }
}
