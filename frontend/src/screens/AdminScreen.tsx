import { useCallback, useEffect, useState } from 'react'
import {
  type AdminHome,
  ApiError,
  getAdminHome,
  resolveFeedback,
} from '../api/client'
import Logo from '../components/Logo'

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

type AdminContactMessage = {
  id: string
  senderName: string
  senderRole?: 'helper' | 'patient' | 'visitor'
  category: 'bug' | 'question' | 'suggestion' | 'other'
  message: string
  timestamp: string
  resolved: boolean
}

type AdminScreenProps = {
  token: string
  onLeave: () => void
}

function when(seconds: number): string {
  return new Date(seconds * 1000).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// Ce que renvoie le backend, mis dans la forme que l'écran affiche.
function adminView(home: AdminHome) {
  const avatars = new Map(
    home.members.map((member) => [member.name, member.avatar_url ?? undefined]),
  )
  const users: AdminUser[] = home.members
    .filter((member) => member.role === 'helper' || member.role === 'patient')
    .map((member) => ({
      id: member.id,
      name: member.name,
      role: member.role as 'helper' | 'patient',
      city: member.city || undefined,
      interests: member.interests,
      avatarUrl: member.avatar_url ?? undefined,
      status: member.activity > 0 ? 'active' : 'idle',
    }))
  const questions: AdminQuestion[] = home.exchanges.map((exchange) => {
    const isNeed = exchange.kind === 'need'
    const toName = exchange.to_name ?? 'Helpers Circle'
    return {
      id: exchange.id,
      fromName: exchange.from_name,
      fromRole: isNeed ? 'patient' : 'helper',
      fromAvatar: avatars.get(exchange.from_name),
      toName,
      toRole: isNeed ? 'helper' : 'patient',
      toAvatar: avatars.get(toName),
      text: exchange.text,
      status:
        exchange.status === 'answered' || exchange.status === 'taken'
          ? 'resolved'
          : 'in_progress',
      timestamp: when(exchange.created_at),
      replyText: exchange.reply ?? undefined,
      isCommunityNeed: isNeed,
    }
  })
  const messages: AdminContactMessage[] = home.feedback.map((item) => ({
    id: item.id,
    senderName: item.sender_name,
    senderRole:
      item.sender_role === 'helper' || item.sender_role === 'patient'
        ? item.sender_role
        : 'visitor',
    category: item.category,
    message: item.message,
    timestamp: when(item.created_at),
    resolved: item.resolved,
  }))
  return { users, questions, messages }
}

// Le portail de l'équipe (`#/admin`) : la communauté, les échanges et les messages reçus.
function AdminScreen({ token, onLeave }: AdminScreenProps) {
  const [home, setHome] = useState<AdminHome | null>(null)
  const [error, setError] = useState<string | null>(null)
  const data = home
    ? adminView(home)
    : { users: [], questions: [], messages: [] }
  const users = data.users
  const questions = data.questions
  const adminMessages = data.messages

  const fail = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) onLeave()
      else
        setError(
          err instanceof ApiError
            ? err.message
            : 'The server is not responding.',
        )
    },
    [onLeave],
  )

  useEffect(() => {
    getAdminHome(token).then(setHome).catch(fail)
  }, [token, fail])
  const [filter, setFilter] = useState<'all' | 'in_progress' | 'resolved'>(
    'all',
  )
  const [search, setSearch] = useState('')

  useEffect(() => {
    document.title = 'Needed · Administrator Portal'
    return () => {
      document.title = 'Needed'
    }
  }, [])

  function handleToggleMessageResolved(id: string, currentStatus: boolean) {
    resolveFeedback(token, id, !currentStatus).then(setHome).catch(fail)
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
      {/* Administrator Header */}
      <header className="topbar">
        <a className="brand" href="#/">
          <Logo size={36} />
          <span className="brand-name">Needed</span>
        </a>
        <div className="topbar-actions">
          <button
            type="button"
            className="button button-ghost button-small"
            onClick={onLeave}
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="stack screen-body admin-body">
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {/* Clean hero header */}
        <section className="admin-hero">
          <h1>Administrator Portal</h1>
        </section>

        {/* Global metrics */}
        <div className="admin-metrics-grid">
          <div className="admin-stat-card">
            <span className="admin-stat-number">{users.length}</span>
            <span className="admin-stat-label">Community Users</span>
          </div>
          <div className="admin-stat-card">
            <span className="admin-stat-number stat-in-progress">
              {inProgressCount}
            </span>
            <span className="admin-stat-label">In Progress</span>
          </div>
          <div className="admin-stat-card">
            <span className="admin-stat-number stat-resolved">
              {resolvedCount}
            </span>
            <span className="admin-stat-label">Resolved</span>
          </div>
          <div className="admin-stat-card">
            <span
              className="admin-stat-number"
              style={{ color: 'var(--cyan-deep)' }}
            >
              {adminMessages.length}
            </span>
            <span className="admin-stat-label">Admin Inbox</span>
          </div>
        </div>

        {/* SECTION 1 : Users */}
        <section className="admin-card stack">
          <div className="flex-between">
            <h2>Community Members ({users.length})</h2>
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
                  <span className="user-status-dot" title="Online" />
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
                      {u.role === 'helper' ? 'Helper' : 'Patient'}
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

        {/* SECTION 2 : Questions in progress & resolved */}
        <section className="admin-card stack">
          <div className="flex-between">
            <h2>Questions & Exchanges ({filteredQuestions.length})</h2>
          </div>

          {/* Filter and Search */}
          <div className="admin-filter-bar">
            <div
              className="segmented-control"
              role="tablist"
              aria-label="Filter questions"
            >
              <button
                type="button"
                className={`segmented-btn ${filter === 'all' ? 'active' : ''}`}
                onClick={() => setFilter('all')}
              >
                All ({questions.length})
              </button>
              <button
                type="button"
                className={`segmented-btn ${
                  filter === 'in_progress' ? 'active' : ''
                }`}
                onClick={() => setFilter('in_progress')}
              >
                In Progress ({inProgressCount})
              </button>
              <button
                type="button"
                className={`segmented-btn ${
                  filter === 'resolved' ? 'active' : ''
                }`}
                onClick={() => setFilter('resolved')}
              >
                Resolved ({resolvedCount})
              </button>
            </div>

            <input
              type="text"
              value={search}
              placeholder="Search by member name or content..."
              className="admin-search-input"
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {/* Questions list with From ➜ To link */}
          <div className="admin-questions-list stack">
            {filteredQuestions.length === 0 ? (
              <p className="quiet font-small text-center py-4">
                No questions match this filter.
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
                  {/* Link banner: From WHO to WHO */}
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
                          {q.fromRole === 'helper' ? 'Helper' : 'Patient'}
                        </span>
                      </div>
                    </div>

                    <div className="relation-arrow-box" title="Connected with">
                      <span className="relation-arrow">➜</span>
                      <span className="relation-label">requests help from</span>
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
                          {q.toRole === 'helper' ? 'Helper' : 'Patient'}
                        </span>
                      </div>
                    </div>

                    <div className="relation-status-badge">
                      {q.status === 'in_progress' ? (
                        <span className="badge-status-in-progress">
                          ● In Progress
                        </span>
                      ) : (
                        <span className="badge-status-resolved">
                          ✓ Resolved
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Question content */}
                  <div className="question-content-box">
                    <span className="question-timestamp">
                      Exchange time: {q.timestamp}
                      {q.isCommunityNeed && ' · Community need'}
                    </span>
                    <p className="question-text">« {q.text} »</p>

                    {/* Possible reply */}
                    {q.replyText && (
                      <div className="question-reply-box">
                        <span className="reply-label">
                          Reply provided by {q.toName}:
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

        {/* SECTION 3 : Admin Messages & Reports */}
        <section className="admin-card stack">
          <div className="flex-between">
            <h2>Admin Inbox ({adminMessages.length})</h2>
            <span className="quiet font-small">
              {adminMessages.filter((m) => !m.resolved).length} pending
            </span>
          </div>

          <div className="admin-messages-list stack" style={{ gap: '10px' }}>
            {adminMessages.length === 0 ? (
              <p className="quiet font-small text-center py-4">
                No messages received yet.
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
                        {msg.category === 'other' && 'Note'}
                      </span>
                      <strong>{msg.senderName}</strong>
                      {msg.senderRole && (
                        <span className="quiet font-small">
                          (
                          {msg.senderRole === 'helper'
                            ? 'Helper'
                            : msg.senderRole === 'patient'
                              ? 'Patient'
                              : 'Visitor'}
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
                        {msg.resolved ? 'Reopen' : 'Mark resolved'}
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

        {/* Navigation links */}
        <div className="admin-footer-links">
          <a href="#/" className="button button-wide">
            Back to Home
          </a>
          <a href="#/clinician" className="button button-ghost button-wide">
            Clinician Portal
          </a>
        </div>
      </main>
    </div>
  )
}

export default AdminScreen
