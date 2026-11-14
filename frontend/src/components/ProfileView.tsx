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

const SUGGESTED_HOBBIES = [
  'gardening',
  'cooking',
  'reading',
  'baking',
  'knitting',
  'jazz',
  'photography',
  'cycling',
  'hiking',
  'chess',
  'woodworking',
  'board games',
]
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
  const [interestsInput, setInterestsInput] = useState<string[]>(user.interests)
  const [avatarUrl, setAvatarUrl] = useState<string | null>(user.avatar_url)
  const [newHobby, setNewHobby] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function handleStartEditing() {
    setBioInput(user.bio)
    setPassionPhotos(user.passion_photos)
    setAllowProfileView(user.allow_profile_view)
    setInterestsInput(user.interests)
    setAvatarUrl(user.avatar_url)
    setNewHobby('')
    setError(null)
    setIsEditing(true)
  }

  function handleRemoveInterest(hobby: string) {
    if (interestsInput.length <= 1) {
      setError('Please keep at least one interest or hobby.')
      return
    }
    setError(null)
    setInterestsInput((prev) => prev.filter((h) => h !== hobby))
  }

  function handleAddCustomInterest() {
    const clean = newHobby.trim().toLowerCase()
    if (!clean) return
    if (interestsInput.includes(clean)) {
      setNewHobby('')
      return
    }
    if (interestsInput.length >= 8) {
      setError('Maximum 8 interests allowed.')
      return
    }
    setError(null)
    setInterestsInput((prev) => [...prev, clean])
    setNewHobby('')
  }

  function handleAddSuggestedInterest(hobby: string) {
    if (interestsInput.includes(hobby)) return
    if (interestsInput.length >= 8) {
      setError('Maximum 8 interests allowed.')
      return
    }
    setError(null)
    setInterestsInput((prev) => [...prev, hobby])
  }

  async function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !file.type.startsWith('image/')) return
    const photo = await pickedImage(file, 400)
    setAvatarUrl(photo)
  }

  async function handleSaveProfileExtras() {
    if (interestsInput.length === 0) {
      setError('Please keep at least one interest or hobby.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const updated = await updateMe(token, {
        bio: bioInput.trim(),
        interests: interestsInput,
        passion_photos: passionPhotos,
        allow_profile_view: allowProfileView,
        avatar_url: avatarUrl,
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

  const availableSuggestions = SUGGESTED_HOBBIES.filter(
    (h) => !interestsInput.includes(h),
  )

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
          {isEditing && (
            <label
              className="profile-avatar-edit-badge"
              title="Change profile picture"
            >
              <input
                type="file"
                accept="image/*"
                className="visually-hidden"
                onChange={(e) => void handleAvatarChange(e)}
              />
              📷
            </label>
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
              onClick={handleStartEditing}
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

            {/* Hobbies / Interests */}
            <div className="profile-hobbies-section">
              <span className="font-small quiet block mb-1">
                Hobbies & centres d’intérêt :
              </span>
              <div className="profile-hobbies-display">
                {user.interests.map((hobby) => (
                  <span key={hobby} className="hobby-chip-view">
                    #{hobby}
                  </span>
                ))}
              </div>
            </div>

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
                A few words about you & your passions (Description / Bio)
              </span>
              <textarea
                rows={3}
                value={bioInput}
                maxLength={300}
                placeholder="E.g., Sourdough baker, Nordic gardening and jazz enthusiast..."
                onChange={(e) => setBioInput(e.target.value)}
              />
            </label>

            {/* Hobbies / Interests editor */}
            <div className="field">
              <div className="flex-between">
                <span className="font-small font-bold">
                  Hobbies & centres d’intérêt ({interestsInput.length}/8)
                </span>
                <span className="quiet font-small">1 à 8 hobbies</span>
              </div>

              <div className="profile-hobbies-edit-wrap">
                {interestsInput.map((hobby) => (
                  <span key={hobby} className="hobby-edit-pill">
                    #{hobby}
                    <button
                      type="button"
                      className="hobby-edit-remove"
                      onClick={() => handleRemoveInterest(hobby)}
                      title={`Retirer ${hobby}`}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>

              {interestsInput.length < 8 && (
                <div className="add-hobby-input-row">
                  <input
                    type="text"
                    value={newHobby}
                    placeholder="Ajouter un hobby..."
                    maxLength={30}
                    className="input-small"
                    onChange={(e) => setNewHobby(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        handleAddCustomInterest()
                      }
                    }}
                  />
                  <button
                    type="button"
                    className="button button-small"
                    disabled={!newHobby.trim()}
                    onClick={handleAddCustomInterest}
                  >
                    + Ajouter
                  </button>
                </div>
              )}

              {availableSuggestions.length > 0 && interestsInput.length < 8 && (
                <div className="hobby-quick-suggestions">
                  <span className="quiet font-small">
                    Suggestions rapides :
                  </span>
                  <div className="hobby-suggestions-pills">
                    {availableSuggestions.slice(0, 6).map((sug) => (
                      <button
                        key={sug}
                        type="button"
                        className="hobby-suggestion-btn"
                        onClick={() => handleAddSuggestedInterest(sug)}
                      >
                        + {sug}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

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
