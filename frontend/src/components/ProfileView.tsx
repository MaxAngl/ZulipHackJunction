import { type ReactNode, useState } from 'react'
import { ApiError, type AppUser, type Thread, updateMe } from '../api/client'
import { pickedImage } from '../images'

type ProfileViewProps = {
  user: AppUser
  token: string
  // Les fils de la personne : ses échanges des sept derniers jours en sont tirés.
  threads: Thread[]
  onUpdated: (user: AppUser) => void
  onLeave?: () => void
  // Cartes en plus, affichées avant les réglages (ex. la montre Garmin du patient).
  children?: ReactNode
}

const DAY_MS = 24 * 60 * 60 * 1000

// Les réponses données (patient) ou reçues (aidant), jour par jour sur la dernière semaine.
function lastSevenDays(threads: Thread[]) {
  const replies = threads.flatMap((thread) =>
    thread.messages.filter((message) => message.kind === 'reply'),
  )
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Array.from({ length: 7 }, (_, index) => {
    const start = today.getTime() - (6 - index) * DAY_MS
    const count = replies.filter((message) => {
      const at = message.created_at * 1000
      return at >= start && at < start + DAY_MS
    }).length
    const day = new Date(start).toLocaleDateString('en-GB', {
      weekday: 'short',
    })
    return { day, count }
  })
}

function ProfileView({
  user,
  token,
  threads,
  onUpdated,
  onLeave,
  children,
}: ProfileViewProps) {
  const role = user.role
  const name = `${user.first_name} ${user.last_name}`.trim()
  const [isEditing, setIsEditing] = useState(false)
  const [bioInput, setBioInput] = useState(user.bio)
  const [passionPhotos, setPassionPhotos] = useState<string[]>(
    user.passion_photos,
  )
  const [allowProfileView, setAllowProfileView] = useState(
    user.allow_profile_view,
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSaveProfileExtras() {
    setSaving(true)
    setError(null)
    try {
      const updated = await updateMe(token, {
        bio: bioInput.trim(),
        passion_photos: passionPhotos,
        allow_profile_view: allowProfileView,
      })
      onUpdated(updated)
      setIsEditing(false)
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'The server is not responding.',
      )
    } finally {
      setSaving(false)
    }
  }

  async function handleAddPassionPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    e.target.value = ''
    const room = 3 - passionPhotos.length
    for (const file of files.slice(0, Math.max(0, room))) {
      if (!file.type.startsWith('image/')) continue
      const photo = await pickedImage(file)
      setPassionPhotos((prev) => (prev.length >= 3 ? prev : [...prev, photo]))
    }
  }

  function handleRemovePassionPhoto(idx: number) {
    setPassionPhotos((prev) => prev.filter((_, i) => i !== idx))
  }

  // Services rendus (patient) ou reçus (aidant) : les demandes qui ont une réponse.
  const servicesCount = threads.filter(
    (thread) => thread.kind === 'request' && thread.status === 'answered',
  ).length
  const historyData = lastSevenDays(threads)
  const maxVal = Math.max(...historyData.map((d) => d.count), 1)
  const avatarUrl = user.avatar_url

  return (
    <section className="stack profile-view">
      {/* Identity hero card */}
      <div className="profile-hero-card">
        <div className="profile-avatar-large-wrap">
          {avatarUrl ? (
            <img src={avatarUrl} alt={name} className="profile-avatar-large" />
          ) : (
            <div className="profile-avatar-fallback">
              {name.charAt(0).toUpperCase()}
            </div>
          )}
        </div>
        <h2 className="profile-display-name">{name}</h2>
        <span className="profile-role-pill">
          {role === 'helper'
            ? 'Volunteer Helper · Community Helper'
            : 'Remission Patient · Clinic Member'}
        </span>
      </div>

      {/* --- ACHIEVEMENTS & IMPACT CARD --- */}
      <div className="profile-achievements-card stack">
        <div className="achievements-header">
          <div>
            <span className="eyebrow">Impact Dashboard</span>
            <h3>Mutual Support & Reciprocity</h3>
          </div>
          <div className="achievements-counter-badge">
            <span className="achievements-number">{servicesCount}</span>
            <span className="achievements-sub">acts</span>
          </div>
        </div>

        {/* Support evolution chart */}
        <div className="achievements-graph-wrap">
          <span className="quiet font-small block mb-1">
            Answers {role === 'patient' ? 'you gave' : 'you received'} over the
            last 7 days:
          </span>
          <div className="achievements-chart">
            {historyData.map((d, idx) => {
              const heightPct = Math.round((d.count / maxVal) * 100)
              return (
                <div key={idx} className="chart-bar-col">
                  <div className="chart-bar-track">
                    <div
                      className="chart-bar-fill"
                      style={{ height: `${heightPct}%` }}
                      title={`${d.count} act(s) on ${d.day}`}
                    />
                  </div>
                  <span className="chart-bar-label">{d.day}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Milestone badges */}
        <div className="achievements-badges-section">
          <span className="eyebrow">Milestones & Badges</span>
          <div className="badges-grid">
            {/* Badge 1 */}
            <div
              className={`badge-card ${servicesCount >= 1 ? 'badge-unlocked' : 'badge-locked'}`}
            >
              <div className="badge-icon-circle">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="8" r="6" />
                  <path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11" />
                </svg>
              </div>
              <strong className="badge-title">1st Support Act</strong>
              <span className="badge-desc">First step in peer support</span>
              {servicesCount >= 1 && (
                <span className="badge-status-tag">Unlocked</span>
              )}
            </div>

            {/* Badge 2 */}
            <div
              className={`badge-card ${servicesCount >= 5 ? 'badge-unlocked' : 'badge-locked'}`}
            >
              <div className="badge-icon-circle">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
              </div>
              <strong className="badge-title">5th Support Act</strong>
              <span className="badge-desc">Pillar of kindness</span>
              {servicesCount >= 5 ? (
                <span className="badge-status-tag">Unlocked</span>
              ) : (
                <span className="badge-status-tag tag-locked">
                  {servicesCount}/5
                </span>
              )}
            </div>

            {/* Badge 3 */}
            <div
              className={`badge-card ${servicesCount >= 10 ? 'badge-unlocked' : 'badge-locked'}`}
            >
              <div className="badge-icon-circle">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
                  <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
                  <path d="M4 22h16" />
                  <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" />
                  <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" />
                  <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" />
                </svg>
              </div>
              <strong className="badge-title">10th Support Act</strong>
              <span className="badge-desc">Community champion</span>
              {servicesCount >= 10 ? (
                <span className="badge-status-tag">Unlocked</span>
              ) : (
                <span className="badge-status-tag tag-locked">
                  {servicesCount}/10
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Passions, Bio and Hobbies Photos */}
      <div className="profile-details-card stack">
        <div className="flex-between">
          <span className="eyebrow">Passions & Interests</span>
          {!isEditing ? (
            <button
              type="button"
              className="button button-ghost button-small"
              onClick={() => {
                setBioInput(user.bio)
                setPassionPhotos(user.passion_photos)
                setAllowProfileView(user.allow_profile_view)
                setIsEditing(true)
              }}
            >
              Edit
            </button>
          ) : (
            <div className="row-align-center">
              <button
                type="button"
                className="link quiet font-small"
                onClick={() => setIsEditing(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button button-primary button-small"
                disabled={saving}
                onClick={() => void handleSaveProfileExtras()}
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          )}
        </div>

        {!isEditing ? (
          <div className="stack-compact">
            {user.bio ? (
              <p className="profile-bio-text">{user.bio}</p>
            ) : (
              <p className="quiet font-small italic">No bio provided yet.</p>
            )}

            {/* Passion photos */}
            <div className="profile-passion-photos-section">
              <span className="font-small quiet block mb-1">
                Passion photos ({user.passion_photos.length}/3):
              </span>
              {user.passion_photos.length > 0 ? (
                <div className="passion-photos-grid">
                  {user.passion_photos.map((pic, i) => (
                    <div key={i} className="passion-photo-card">
                      <img
                        src={pic}
                        alt={`Passion ${i + 1}`}
                        className="passion-photo-thumb"
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <p className="quiet font-small italic">
                  No passion photos added yet.
                </p>
              )}
            </div>

            {/* Profile privacy */}
            <div className="profile-privacy-status-pill">
              <span className="status-dot-indicator" />
              <span className="font-small">
                {user.allow_profile_view
                  ? 'Profile visible in your conversations'
                  : 'Private profile (peers cannot view details)'}
              </span>
            </div>
          </div>
        ) : (
          <div className="stack-compact">
            <label className="field">
              <span className="font-small">
                A few words about you & your passions
              </span>
              <textarea
                rows={3}
                value={bioInput}
                maxLength={300}
                placeholder="E.g., Sourdough baker, Nordic gardening and jazz enthusiast..."
                onChange={(e) => setBioInput(e.target.value)}
              />
            </label>

            <div className="field">
              <div className="flex-between">
                <span className="font-small">Passion photos (up to 3)</span>
                <span className="quiet font-small">
                  {passionPhotos.length}/3
                </span>
              </div>
              <div className="passion-photos-grid">
                {passionPhotos.map((photo, idx) => (
                  <div key={idx} className="passion-photo-card">
                    <img
                      src={photo}
                      alt={`Passion ${idx + 1}`}
                      className="passion-photo-thumb"
                    />
                    <button
                      type="button"
                      className="passion-photo-remove-btn"
                      title="Delete photo"
                      onClick={() => handleRemovePassionPhoto(idx)}
                    >
                      ×
                    </button>
                  </div>
                ))}
                {passionPhotos.length < 3 && (
                  <label className="passion-photo-add-box">
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      className="visually-hidden"
                      onChange={(event) => void handleAddPassionPhoto(event)}
                    />
                    <span className="passion-add-icon">+</span>
                    <span className="font-small quiet">Add</span>
                  </label>
                )}
              </div>
            </div>

            <label className="profile-privacy-toggle-card">
              <input
                type="checkbox"
                checked={allowProfileView}
                onChange={(e) => setAllowProfileView(e.target.checked)}
              />
              <div className="privacy-toggle-info">
                <strong>Allow chat partners to view my profile</strong>
                <p className="quiet font-small">
                  If unchecked, tapping your profile in conversations will
                  indicate that your profile is private.
                </p>
              </div>
            </label>
          </div>
        )}
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {/* Personal information */}
      <div className="profile-details-card stack-compact">
        <span className="eyebrow">Personal Information</span>
        <div className="profile-info-row">
          <span className="profile-info-label">Email</span>
          <strong className="profile-info-value">{user.email}</strong>
        </div>
        {user.birth_date && (
          <div className="profile-info-row">
            <span className="profile-info-label">Date of birth</span>
            <strong className="profile-info-value">{user.birth_date}</strong>
          </div>
        )}
        {user.city && (
          <div className="profile-info-row">
            <span className="profile-info-label">Location</span>
            <strong className="profile-info-value">{user.city}</strong>
          </div>
        )}
        <div className="profile-info-row">
          <span className="profile-info-label">Interests</span>
          <strong className="profile-info-value">
            {user.interests.join(', ')}
          </strong>
        </div>
        {role === 'patient' && user.clinician_email && (
          <div className="profile-info-row">
            <span className="profile-info-label">Referring clinician</span>
            <strong className="profile-info-value">
              {user.clinician_email}
            </strong>
          </div>
        )}
      </div>

      {children}

      <div className="profile-actions-stack stack">
        <a href="#/settings" className="button button-ghost button-wide">
          Settings & Privacy
        </a>
        {onLeave && (
          <button
            type="button"
            className="button button-wide"
            onClick={onLeave}
          >
            Sign out
          </button>
        )}
      </div>
    </section>
  )
}

export default ProfileView
