import { useEffect, useState } from 'react'
import Logo from '../components/Logo'
import {
  type AdminContactMessage,
  type ConversationThread,
  type PatientCommunityNeed,
  SIMULATION_ACCOUNTS,
  readAdminContactMessages,
  readPatientCommunityNeeds,
  readThreads,
  readUserProfile,
  updateAdminContactMessageStatus,
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

  // 1. Charger les 6 profils simulés officiels (3 aidants, 3 patients)
  const loadedUsers: AdminUser[] = SIMULATION_ACCOUNTS.map((acc) => ({
    id: acc.id,
    name: `${acc.firstName} ${acc.lastName}`.trim(),
    role: acc.role,
    city: acc.city,
    interests: acc.interests,
    bio: acc.bio,
    avatarUrl: acc.avatarUrl,
    status: 'active' as const,
  }))

  // S'il existe des profils personnalisés enregistrés localement avec un nom différent, on les inclut
  if (helperProfile) {
    const fullName =
      `${helperProfile.firstName} ${helperProfile.lastName}`.trim()
    if (
      !loadedUsers.some((u) => u.name.toLowerCase() === fullName.toLowerCase())
    ) {
      loadedUsers.push({
        id: 'u-custom-helper',
        name: fullName,
        role: 'helper',
        city: helperProfile.city,
        interests: helperProfile.interests ?? [],
        bio: helperProfile.bio,
        avatarUrl: helperProfile.avatarUrl,
        status: 'active',
      })
    }
  }

  if (patientProfile) {
    const fullName =
      `${patientProfile.firstName} ${patientProfile.lastName}`.trim()
    if (
      !loadedUsers.some((u) => u.name.toLowerCase() === fullName.toLowerCase())
    ) {
      loadedUsers.push({
        id: 'u-custom-patient',
        name: fullName,
        role: 'patient',
        city: patientProfile.city,
        interests: patientProfile.interests ?? [],
        bio: patientProfile.bio,
        avatarUrl: patientProfile.avatarUrl,
        status: 'active',
      })
    }
  }

  // 2. Questions & Interactions entre les 3 aidants et 3 patients
  const allQuestions: AdminQuestion[] = [
    {
      id: 'req-sim-1',
      fromName: 'Clara Fontaine',
      fromRole: 'helper',
      fromAvatar: '/moomins/Characters-04-2.svg',
      toName: 'Julien Mercier',
      toRole: 'patient',
      toAvatar: '/moomins/Muumipeikko2.jpg',
      text: 'Aurais-tu des astuces de jardinage pour rempoter des plantes d’intérieur en automne ?',
      status: 'resolved',
      timestamp: '10:15',
      replyText:
        'Avec plaisir ! Il faut surtout choisir un pot percé avec un lit de billes d’argile au fond et un terreau léger.',
    },
    {
      id: 'req-sim-2',
      fromName: 'Thomas Lindqvist',
      fromRole: 'helper',
      fromAvatar: '/moomins/Muumipappa2.jpg',
      toName: 'Sofia Hakala',
      toRole: 'patient',
      toAvatar: '/moomins/Nuuskamuikkunen.png',
      text: 'Je cherche des recommandations d’albums de jazz nordique pour une ambiance de lecture apaisante, as-tu des pépites ?',
      status: 'in_progress',
      timestamp: '11:30',
    },
    {
      id: 'req-sim-3',
      fromName: 'Elena Sjöberg',
      fromRole: 'helper',
      fromAvatar: '/moomins/Nuuskamuikkunen.png',
      toName: 'Lucas Virtanen',
      toRole: 'patient',
      toAvatar: '/moomins/Characters-04-2.svg',
      text: 'Je prépare une écharpe en laine mérinos pour l’hiver, quel type de maille conseilles-tu pour débuter sans stress ?',
      status: 'resolved',
      timestamp: '14:20',
      replyText:
        'Le point mousse ou les côtes 1/1 sont idéales et très relaxantes !',
    },
  ]

  // Questions issues des fils de discussion (ChatView)
  const helperThreads: ConversationThread[] = readThreads('helper')
  helperThreads.forEach((t) => {
    if (!allQuestions.some((q) => q.id === t.id || q.id === `thread-${t.id}`)) {
      const isResolved = t.isFinished
      allQuestions.push({
        id: `thread-${t.id}`,
        fromName: helperProfile
          ? `${helperProfile.firstName} ${helperProfile.lastName}`.trim()
          : 'Clara Fontaine',
        fromRole: 'helper',
        fromAvatar: helperProfile?.avatarUrl ?? '/moomins/Characters-04-2.svg',
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
    }
  })

  // Demandes directes de patients à la communauté (PatientCommunityNeed)
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
  const [adminMessages, setAdminMessages] = useState<AdminContactMessage[]>(
    () => readAdminContactMessages(),
  )
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

  function handleToggleMessageResolved(id: string, currentStatus: boolean) {
    const nextStatus = !currentStatus
    updateAdminContactMessageStatus(id, nextStatus)
    setAdminMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, resolved: nextStatus } : m)),
    )
  }

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
          <div className="admin-stat-card">
            <span
              className="admin-stat-number"
              style={{ color: 'var(--cyan-deep)' }}
            >
              {adminMessages.length}
            </span>
            <span className="admin-stat-label">Messages</span>
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

        {/* SECTION 3 : Messagerie & Signalements Administrateur */}
        <section className="admin-card stack">
          <div className="flex-between">
            <h2>Messagerie Administrateur ({adminMessages.length})</h2>
            <span className="quiet font-small">
              {adminMessages.filter((m) => !m.resolved).length} non traité(s)
            </span>
          </div>

          <div className="admin-messages-list stack" style={{ gap: '10px' }}>
            {adminMessages.length === 0 ? (
              <p className="quiet font-small text-center py-4">
                Aucun message reçu pour le moment.
              </p>
            ) : (
              adminMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`admin-msg-item ${
                    msg.resolved ? 'msg-resolved' : 'msg-open'
                  }`}
                  style={{
                    padding: '12px 14px',
                    borderRadius: '12px',
                    background: msg.resolved
                      ? 'var(--bg)'
                      : 'rgba(0, 216, 255, 0.05)',
                    border: msg.resolved
                      ? '1px solid var(--line)'
                      : '1px solid rgba(0, 216, 255, 0.35)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                  }}
                >
                  <div
                    className="flex-between"
                    style={{
                      alignItems: 'flex-start',
                      flexWrap: 'wrap',
                      gap: '8px',
                    }}
                  >
                    <div
                      className="row-align-center-tight"
                      style={{ gap: '8px', flexWrap: 'wrap' }}
                    >
                      <span
                        style={{
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '6px',
                          background:
                            msg.category === 'bug'
                              ? '#ffebee'
                              : msg.category === 'suggestion'
                                ? '#e0f7fa'
                                : '#f3e5f5',
                          color:
                            msg.category === 'bug'
                              ? '#c62828'
                              : msg.category === 'suggestion'
                                ? '#00838f'
                                : '#6a1b9a',
                        }}
                      >
                        {msg.category === 'bug' && 'Bug'}
                        {msg.category === 'question' && 'Question'}
                        {msg.category === 'suggestion' && 'Suggestion'}
                        {msg.category === 'other' && 'Remarque'}
                      </span>
                      <strong>{msg.senderName}</strong>
                      {msg.senderRole && (
                        <span className="quiet font-small">
                          (
                          {msg.senderRole === 'helper'
                            ? 'Aidant'
                            : msg.senderRole === 'patient'
                              ? 'Patient'
                              : 'Visiteur'}
                          )
                        </span>
                      )}
                    </div>
                    <div
                      className="row-align-center-tight"
                      style={{ gap: '8px' }}
                    >
                      <span className="quiet font-small">{msg.timestamp}</span>
                      <button
                        type="button"
                        className="button button-ghost button-small"
                        style={{ fontSize: '0.78rem', padding: '4px 8px' }}
                        onClick={() =>
                          handleToggleMessageResolved(msg.id, msg.resolved)
                        }
                      >
                        {msg.resolved ? 'Rouvrir' : 'Marquer traité'}
                      </button>
                    </div>
                  </div>

                  <p
                    style={{
                      margin: 0,
                      fontSize: '0.92rem',
                      lineHeight: 1.45,
                      color: 'var(--ink)',
                    }}
                  >
                    « {msg.message} »
                  </p>
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
