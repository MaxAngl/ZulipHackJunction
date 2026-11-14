import { useEffect, useState } from 'react'
import Logo from '../components/Logo'
import {
  type ConversationThread,
  type PatientCommunityNeed,
  readPatientCommunityNeeds,
  readThreads,
  readUserProfile,
} from '../session'

type AdminUser = {
  id: string
  name: string
  role: 'helper' | 'patient'
  city?: string
  interests: string[]
  bio?: string
  avatarUrl?: string
  status: 'active' | 'idle'
}

type AdminQuestion = {
  id: string
  fromName: string
  fromRole: 'helper' | 'patient'
  fromAvatar?: string
  toName: string
  toRole: 'helper' | 'patient'
  toAvatar?: string
  text: string
  status: 'in_progress' | 'resolved'
  timestamp: string
  replyText?: string
  isCommunityNeed?: boolean
}

function getInitialAdminData() {
  const helperProfile = readUserProfile('helper')
  const patientProfile = readUserProfile('patient')

  const loadedUsers: AdminUser[] = []

  if (helperProfile) {
    loadedUsers.push({
      id: 'u-helper',
      name: `${helperProfile.firstName} ${helperProfile.lastName}`.trim(),
      role: 'helper',
      city: helperProfile.city,
      interests: helperProfile.interests ?? [
        'cooking',
        'photography',
        'woodworking',
        'moovie-making',
        'video-games',
      ],
      bio: helperProfile.bio,
      avatarUrl: helperProfile.avatarUrl,
      status: 'active',
    })
  } else {
    loadedUsers.push({
      id: 'u-helper-default',
      name: 'Rami Chagnaud-Aidant',
      role: 'helper',
      city: 'Helsinki',
      interests: [
        'cooking',
        'photography',
        'woodworking',
        'moovie-making',
        'video-games',
      ],
      bio: 'Aidant bénévole engagé au sein de la communauté Needed.',
      status: 'active',
    })
  }

  if (patientProfile) {
    loadedUsers.push({
      id: 'u-patient',
      name: `${patientProfile.firstName} ${patientProfile.lastName}`.trim(),
      role: 'patient',
      city: patientProfile.city,
      interests: patientProfile.interests ?? [
        'knitting',
        'baking',
        'ceremonie militaire',
      ],
      bio: patientProfile.bio,
      avatarUrl: patientProfile.avatarUrl ?? '/moomins/Muumipeikko2.jpg',
      status: 'active',
    })
  } else {
    loadedUsers.push({
      id: 'u-patient-default',
      name: 'Test1 Patient',
      role: 'patient',
      city: 'Helsinki',
      interests: ['knitting', 'baking', 'ceremonie militaire'],
      avatarUrl: '/moomins/Muumipeikko2.jpg',
      bio: 'Membre patient de la communauté Needed.',
      status: 'active',
    })
  }

  // Chargement de l'ensemble des questions (en cours et résolues)
  const allQuestions: AdminQuestion[] = []

  // 1. Questions backend de l'aidant vers le patient (Requête SQL/API enregistrée)
  allQuestions.push({
    id: 'req-backend-1',
    fromName: helperProfile
      ? `${helperProfile.firstName} ${helperProfile.lastName}`.trim()
      : 'Rami Chagnaud-Aidant',
    fromRole: 'helper',
    fromAvatar: helperProfile?.avatarUrl,
    toName: patientProfile
      ? `${patientProfile.firstName} ${patientProfile.lastName}`.trim()
      : 'Test1 Patient',
    toRole: 'patient',
    toAvatar: patientProfile?.avatarUrl ?? '/moomins/Muumipeikko2.jpg',
    text: 'I need a recipe of cookies for a family gathering? Could you help me with your favorite one?',
    status: 'resolved',
    timestamp: '11:15',
    replyText:
      'Bien sûr ! Je te conseille des cookies aux pépites de chocolat et fleur de sel.',
  })

  // 2. Questions issues des fils de discussion (ChatView)
  const helperThreads: ConversationThread[] = readThreads('helper')
  helperThreads.forEach((t) => {
    const isResolved = t.isFinished
    allQuestions.push({
      id: `thread-${t.id}`,
      fromName: helperProfile
        ? `${helperProfile.firstName} ${helperProfile.lastName}`.trim()
        : 'Rami Chagnaud-Aidant',
      fromRole: 'helper',
      fromAvatar: helperProfile?.avatarUrl,
      toName: t.peerName,
      toRole: t.peerRole,
      toAvatar: t.peerAvatar,
      text:
        t.messages.find((m) => m.senderRole === 'helper')?.text ??
        t.lastMessageText,
      status: isResolved ? 'resolved' : 'in_progress',
      timestamp: t.lastMessageTime,
      replyText:
        t.messages.find((m) => m.senderRole === 'patient')?.text ?? undefined,
    })
  })

  // 3. Demandes directes de patients à la communauté (PatientCommunityNeed)
  const communityNeeds: PatientCommunityNeed[] = readPatientCommunityNeeds()
  communityNeeds.forEach((need) => {
    allQuestions.push({
      id: need.id,
      fromName: need.patientName,
      fromRole: 'patient',
      fromAvatar: need.patientAvatar,
      toName: 'Cercle des Aidants',
      toRole: 'helper',
      text: need.text,
      status: need.answered ? 'resolved' : 'in_progress',
      timestamp: need.timestamp,
      isCommunityNeed: true,
    })
  })

  // Déduplication par ID
  const uniqueQuestionsMap = new Map<string, AdminQuestion>()
  allQuestions.forEach((q) => {
    if (!uniqueQuestionsMap.has(q.id)) {
      uniqueQuestionsMap.set(q.id, q)
    }
  })

  return {
    users: loadedUsers,
    questions: Array.from(uniqueQuestionsMap.values()),
  }
}

function AdminScreen() {
  const [data] = useState(() => getInitialAdminData())
  const users = data.users
  const questions = data.questions
  const [filter, setFilter] = useState<'all' | 'in_progress' | 'resolved'>(
    'all',
  )
  const [search, setSearch] = useState('')

  useEffect(() => {
    document.title = 'Needed · Espace Administrateur'
    return () => {
      document.title = 'Needed'
    }
  }, [])

  const filteredQuestions = questions.filter((q) => {
    if (filter === 'in_progress' && q.status !== 'in_progress') return false
    if (filter === 'resolved' && q.status !== 'resolved') return false
    if (search.trim()) {
      const s = search.toLowerCase()
      const matchText = q.text.toLowerCase().includes(s)
      const matchFrom = q.fromName.toLowerCase().includes(s)
      const matchTo = q.toName.toLowerCase().includes(s)
      return matchText || matchFrom || matchTo
    }
    return true
  })

  const inProgressCount = questions.filter(
    (q) => q.status === 'in_progress',
  ).length
  const resolvedCount = questions.filter((q) => q.status === 'resolved').length

  return (
    <div className="screen admin-screen">
      {/* Header Administrateur */}
      <header className="topbar">
        <a className="brand" href="#/">
          <Logo size={36} />
          <span className="brand-name">Needed</span>
        </a>
        <div className="topbar-actions">
          <a
            href="#/"
            className="button button-ghost button-small"
            title="Retour à l'accueil"
          >
            Quitter
          </a>
        </div>
      </header>

      <main className="stack screen-body admin-body">
        {/* Titre épuré */}
        <section className="admin-hero">
          <h1>Espace Administrateur</h1>
        </section>

        {/* Métriques globales */}
        <div className="admin-metrics-grid">
          <div className="admin-stat-card">
            <span className="admin-stat-number">{users.length}</span>
            <span className="admin-stat-label">Utilisateurs</span>
          </div>
          <div className="admin-stat-card">
            <span className="admin-stat-number stat-in-progress">
              {inProgressCount}
            </span>
            <span className="admin-stat-label">En cours</span>
          </div>
          <div className="admin-stat-card">
            <span className="admin-stat-number stat-resolved">
              {resolvedCount}
            </span>
            <span className="admin-stat-label">Résolues</span>
          </div>
        </div>

        {/* SECTION 1 : Utilisateurs */}
        <section className="admin-card stack">
          <div className="flex-between">
            <h2>Utilisateurs ({users.length})</h2>
          </div>

          <div className="admin-users-list">
            {users.map((u) => (
              <div key={u.id} className="admin-user-row">
                <div className="admin-user-avatar-wrap">
                  {u.avatarUrl ? (
                    <img
                      src={u.avatarUrl}
                      alt={u.name}
                      className="admin-user-avatar"
                    />
                  ) : (
                    <div className="admin-user-avatar-fallback">
                      {u.name.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <span className="user-status-dot" title="En ligne" />
                </div>

                <div className="admin-user-info">
                  <div className="row-align-center-tight">
                    <strong className="admin-user-name">{u.name}</strong>
                    <span
                      className={`role-badge ${
                        u.role === 'helper'
                          ? 'role-badge-helper'
                          : 'role-badge-patient'
                      }`}
                    >
                      {u.role === 'helper' ? 'Aidant' : 'Patient'}
                    </span>
                  </div>
                  {u.city && (
                    <span className="quiet font-small block">📍 {u.city}</span>
                  )}
                  {u.bio && <p className="admin-user-bio">« {u.bio} »</p>}
                  <div className="admin-user-tags">
                    {u.interests.map((int) => (
                      <span key={int} className="admin-tag-chip">
                        #{int}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* SECTION 2 : Questions en cours & résolues */}
        <section className="admin-card stack">
          <div className="flex-between">
            <h2>Questions ({filteredQuestions.length})</h2>
          </div>

          {/* Filtres d'état et Recherche */}
          <div className="admin-filter-bar">
            <div
              className="segmented-control"
              role="tablist"
              aria-label="Filtrer les questions"
            >
              <button
                type="button"
                className={`segmented-btn ${filter === 'all' ? 'active' : ''}`}
                onClick={() => setFilter('all')}
              >
                Toutes ({questions.length})
              </button>
              <button
                type="button"
                className={`segmented-btn ${
                  filter === 'in_progress' ? 'active' : ''
                }`}
                onClick={() => setFilter('in_progress')}
              >
                En cours ({inProgressCount})
              </button>
              <button
                type="button"
                className={`segmented-btn ${
                  filter === 'resolved' ? 'active' : ''
                }`}
                onClick={() => setFilter('resolved')}
              >
                Résolues ({resolvedCount})
              </button>
            </div>

            <input
              type="text"
              value={search}
              placeholder="Rechercher par nom ou contenu..."
              className="admin-search-input"
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {/* Liste des questions avec lien émetteur ➜ destinataire */}
          <div className="admin-questions-list stack">
            {filteredQuestions.length === 0 ? (
              <p className="quiet font-small text-center py-4">
                Aucune question ne correspond à ce filtre.
              </p>
            ) : (
              filteredQuestions.map((q) => (
                <div
                  key={q.id}
                  className={`admin-question-card ${
                    q.status === 'in_progress'
                      ? 'card-in-progress'
                      : 'card-resolved'
                  }`}
                >
                  {/* Bannière du lien : De QUI vers QUI */}
                  <div className="relation-header">
                    <div className="relation-party">
                      {q.fromAvatar ? (
                        <img
                          src={q.fromAvatar}
                          alt={q.fromName}
                          className="party-avatar"
                        />
                      ) : (
                        <div className="party-avatar-fallback">
                          {q.fromName.charAt(0).toUpperCase()}
                        </div>
                      )}
                      <div>
                        <strong className="party-name">{q.fromName}</strong>
                        <span className="party-role">
                          {q.fromRole === 'helper' ? 'Aidant' : 'Patient'}
                        </span>
                      </div>
                    </div>

                    <div className="relation-arrow-box" title="En lien avec">
                      <span className="relation-arrow">➜</span>
                      <span className="relation-label">sollicite</span>
                    </div>

                    <div className="relation-party">
                      {q.toAvatar ? (
                        <img
                          src={q.toAvatar}
                          alt={q.toName}
                          className="party-avatar"
                        />
                      ) : (
                        <div className="party-avatar-fallback">
                          {q.toName.charAt(0).toUpperCase()}
                        </div>
                      )}
                      <div>
                        <strong className="party-name">{q.toName}</strong>
                        <span className="party-role">
                          {q.toRole === 'helper' ? 'Aidant' : 'Patient'}
                        </span>
                      </div>
                    </div>

                    <div className="relation-status-badge">
                      {q.status === 'in_progress' ? (
                        <span className="badge-status-in-progress">
                          ● En cours
                        </span>
                      ) : (
                        <span className="badge-status-resolved">✓ Résolue</span>
                      )}
                    </div>
                  </div>

                  {/* Contenu de la question */}
                  <div className="question-content-box">
                    <span className="question-timestamp">
                      Heure de l'échange : {q.timestamp}
                      {q.isCommunityNeed && ' · Besoin communautaire'}
                    </span>
                    <p className="question-text">« {q.text} »</p>

                    {/* Réponse éventuelle */}
                    {q.replyText && (
                      <div className="question-reply-box">
                        <span className="reply-label">
                          Réponse apportée par {q.toName} :
                        </span>
                        <p className="reply-text">« {q.replyText} »</p>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        {/* Liens de navigation retour */}
        <div className="admin-footer-links">
          <a href="#/" className="button button-wide">
            Retour à l'accueil
          </a>
          <a href="#/clinician" className="button button-ghost button-wide">
            Portail Clinicien
          </a>
        </div>
      </main>
    </div>
  )
}

export default AdminScreen
