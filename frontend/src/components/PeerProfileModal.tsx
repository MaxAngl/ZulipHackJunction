import type { PublicProfile } from '../api/client'

// Le profil d'un autre membre, ouvert depuis un fil ; seulement ce qu'il accepte de montrer.
function PeerProfileModal({
  profile,
  onClose,
}: {
  profile: PublicProfile
  onClose: () => void
}) {
  const fullName = `${profile.name} ${profile.last_name}`.trim()
  return (
    <div className="peer-profile-modal-backdrop" onClick={onClose}>
      <div
        className="peer-profile-modal-card"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="peer-profile-title"
      >
        <div className="peer-profile-modal-header">
          <span className="eyebrow">Member Profile</span>
          <button
            type="button"
            className="peer-profile-modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="peer-profile-content-scroll stack">
          <div className="peer-profile-hero">
            <div className="peer-avatar-xlarge-wrap">
              {profile.avatar_url ? (
                <img
                  src={profile.avatar_url}
                  alt={fullName}
                  className="peer-avatar-xlarge"
                />
              ) : (
                <div className="peer-avatar-xlarge-fallback">
                  {fullName.charAt(0).toUpperCase()}
                </div>
              )}
            </div>
            <h2 id="peer-profile-title" className="peer-profile-fullname">
              {fullName}
            </h2>
            <div className="peer-profile-sub-badges">
              <span className="peer-role-tag">
                {profile.role === 'patient'
                  ? 'Community member · Patient'
                  : 'Community helper'}
              </span>
              {profile.city && (
                <span className="peer-role-tag">{profile.city}</span>
              )}
            </div>
          </div>

          <div className="peer-profile-section stack-compact">
            <span className="eyebrow">Interests & Bio</span>
            {profile.bio ? (
              <p className="peer-bio-text">{profile.bio}</p>
            ) : (
              <p className="quiet font-small">No bio yet.</p>
            )}
            <div className="peer-interests-chips">
              {profile.interests.map((tag) => (
                <span key={tag} className="peer-interest-pill">
                  #{tag}
                </span>
              ))}
            </div>
          </div>

          {profile.passion_photos.length > 0 && (
            <div className="peer-profile-section stack-compact">
              <span className="eyebrow">
                Passion photos ({profile.passion_photos.length}/3)
              </span>
              <div className="passion-photos-grid">
                {profile.passion_photos.map((picture, index) => (
                  <div key={index} className="passion-photo-card">
                    <img
                      src={picture}
                      alt={`Passion ${index + 1}`}
                      className="passion-photo-thumb"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          <button
            type="button"
            className="button button-primary button-wide mt-2"
            onClick={onClose}
          >
            Back to conversation
          </button>
        </div>
      </div>
    </div>
  )
}

export default PeerProfileModal
