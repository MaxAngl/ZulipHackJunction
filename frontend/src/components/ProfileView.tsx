import { type ReactNode, useState } from 'react'
import { ApiError, type AppUser, type Thread, updateMe } from '../api/client'
import { pickedImage } from '../images'
import BadgesPanel from './BadgesPanel'

type ProfileViewProps = {
  user: AppUser
  token: string
  // Les fils de la personne : ses badges en sont tirés.
  threads: Thread[]
  onUpdated: (user: AppUser) => void
  onLeave?: () => void
  // Cartes en plus, affichées avant les réglages (ex. la montre Garmin du patient).
  children?: ReactNode
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

      {/* Tableau de bord : les badges seulement (issue #61) */}
      <div className="profile-achievements-card stack">
        <BadgesPanel role={role} userId={user.id} threads={threads} />
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
