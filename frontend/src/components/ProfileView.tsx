import { useState } from 'react'
import type { Role } from '../api/client'
import { readUserProfile, saveUserProfile, type UserProfile } from '../session'

type ProfileViewProps = {
  role: Role
  name: string
  onLeave?: () => void
}

function ProfileView({ role, name, onLeave }: ProfileViewProps) {
  const [profile, setProfile] = useState<UserProfile | null>(() =>
    readUserProfile(role),
  )
  const [isEditing, setIsEditing] = useState(false)
  const [bioInput, setBioInput] = useState(() => profile?.bio ?? '')
  const [passionPhotos, setPassionPhotos] = useState<string[]>(
    () => profile?.passionPhotos ?? [],
  )
  const [allowProfileView, setAllowProfileView] = useState<boolean>(
    () => profile?.allowProfileView ?? true,
  )

  const avatarUrl =
    profile?.avatarUrl ??
    (role === 'patient' ? '/moomins/Muumipeikko2.jpg' : undefined)

  function handleSaveProfileExtras() {
    if (!profile) return
    const updated: UserProfile = {
      ...profile,
      bio: bioInput.trim(),
      passionPhotos,
      allowProfileView,
    }
    saveUserProfile(role, updated)
    setProfile(updated)
    setIsEditing(false)
  }

  function handleAddPassionPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files || files.length === 0) return
    const remainingSlots = 3 - passionPhotos.length
    if (remainingSlots <= 0) return

    const toProcess = Math.min(files.length, remainingSlots)
    for (let i = 0; i < toProcess; i++) {
      const file = files[i]
      if (!file.type.startsWith('image/')) continue
      const reader = new FileReader()
      reader.onload = () => {
        if (typeof reader.result === 'string') {
          setPassionPhotos((prev) => {
            if (prev.length >= 3) return prev
            return [...prev, reader.result as string]
          })
        }
      }
      reader.readAsDataURL(file)
    }
    e.target.value = ''
  }

  function handleRemovePassionPhoto(idx: number) {
    setPassionPhotos((prev) => prev.filter((_, i) => i !== idx))
  }

  // Statistiques de services rendus (réalistes et inspirantes)
  const servicesCount = role === 'patient' ? 7 : 4
  const historyData = [
    { day: 'Lun', count: 1 },
    { day: 'Mar', count: 2 },
    { day: 'Mer', count: 1 },
    { day: 'Jeu', count: 3 },
    { day: 'Ven', count: 5 },
    { day: 'Sam', count: 6 },
    { day: 'Dim', count: 7 },
  ]
  const maxVal = Math.max(...historyData.map((d) => d.count), 1)

  return (
    <section className="stack profile-view">
      {/* Carte d'identité principale */}
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
        <h2 className="profile-display-name">
          {profile ? `${profile.firstName} ${profile.lastName}`.trim() : name}
        </h2>
        <span className="profile-role-pill">
          {role === 'helper'
            ? 'Aidant bénévole · Community Helper'
            : 'Patient en rémission · Clinic Member'}
        </span>
      </div>

      {/* --- TABLEAU DES ACHIEVEMENTS & IMPACT --- */}
      <div className="profile-achievements-card stack">
        <div className="achievements-header">
          <div>
            <span className="eyebrow">Tableau d'impact</span>
            <h3>Services & Réciprocité</h3>
          </div>
          <div className="achievements-counter-badge">
            <span className="achievements-number">{servicesCount}</span>
            <span className="achievements-sub">services</span>
          </div>
        </div>

        {/* Graphique d'évolution dans le temps (Sparkline / Bar chart SVG propre) */}
        <div className="achievements-graph-wrap">
          <span className="quiet font-small block mb-1">
            Évolution des échanges positifs (7 derniers jours) :
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
                      title={`${d.count} service(s) le ${d.day}`}
                    />
                  </div>
                  <span className="chart-bar-label">{d.day}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Médailles pour paliers (1er, 5e, 10e service, etc.) */}
        <div className="achievements-badges-section">
          <span className="eyebrow">Médailles & Paliers</span>
          <div className="badges-grid">
            {/* Médaille 1 : 1er service */}
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
              <strong className="badge-title">1er Service</strong>
              <span className="badge-desc">Premier pas dans l’entraide</span>
              {servicesCount >= 1 && (
                <span className="badge-status-tag">Débloqué</span>
              )}
            </div>

            {/* Médaille 2 : 5e service */}
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
              <strong className="badge-title">5e Service</strong>
              <span className="badge-desc">Pilier de bienveillance</span>
              {servicesCount >= 5 ? (
                <span className="badge-status-tag">Débloqué</span>
              ) : (
                <span className="badge-status-tag tag-locked">
                  {servicesCount}/5
                </span>
              )}
            </div>

            {/* Médaille 3 : 10e service */}
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
              <strong className="badge-title">10e Service</strong>
              <span className="badge-desc">Maître de la communauté</span>
              {servicesCount >= 10 ? (
                <span className="badge-status-tag">Débloqué</span>
              ) : (
                <span className="badge-status-tag tag-locked">
                  {servicesCount}/10
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Passions, Bio et Photos de hobbies */}
      <div className="profile-details-card stack">
        <div className="flex-between">
          <span className="eyebrow">Passions & Centres d'intérêt</span>
          {!isEditing ? (
            <button
              type="button"
              className="button button-ghost button-small"
              onClick={() => {
                setBioInput(profile?.bio ?? '')
                setPassionPhotos(profile?.passionPhotos ?? [])
                setAllowProfileView(profile?.allowProfileView ?? true)
                setIsEditing(true)
              }}
            >
              Modifier
            </button>
          ) : (
            <div className="row-align-center">
              <button
                type="button"
                className="link quiet font-small"
                onClick={() => setIsEditing(false)}
              >
                Annuler
              </button>
              <button
                type="button"
                className="button button-primary button-small"
                onClick={handleSaveProfileExtras}
              >
                Enregistrer
              </button>
            </div>
          )}
        </div>

        {!isEditing ? (
          <div className="stack-compact">
            {profile?.bio ? (
              <p className="profile-bio-text">{profile.bio}</p>
            ) : (
              <p className="quiet font-small italic">
                Aucune bio renseignée pour le moment.
              </p>
            )}

            {/* Photos de passion */}
            <div className="profile-passion-photos-section">
              <span className="font-small quiet block mb-1">
                Photos de passions ({profile?.passionPhotos?.length ?? 0}/3) :
              </span>
              {(profile?.passionPhotos?.length ?? 0) > 0 ? (
                <div className="passion-photos-grid">
                  {profile?.passionPhotos?.map((pic, i) => (
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
                  Aucune photo de passion ajoutée.
                </p>
              )}
            </div>

            {/* Confidentialité du profil */}
            <div className="profile-privacy-status-pill">
              <span className="status-dot-indicator" />
              <span className="font-small">
                {profile?.allowProfileView !== false
                  ? 'Profil partagé dans vos conversations'
                  : 'Profil masqué (vos correspondants ne peuvent pas le consulter)'}
              </span>
            </div>
          </div>
        ) : (
          <div className="stack-compact">
            <label className="field">
              <span className="font-small">
                Quelques mots sur vous & vos passions
              </span>
              <textarea
                rows={3}
                value={bioInput}
                maxLength={300}
                placeholder="Ex : Passionné de pain au levain, jardinage nordique et musique jazz..."
                onChange={(e) => setBioInput(e.target.value)}
              />
            </label>

            <div className="field">
              <div className="flex-between">
                <span className="font-small">
                  Photos de passion (jusqu'à 3)
                </span>
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
                      title="Supprimer la photo"
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
                      onChange={handleAddPassionPhoto}
                    />
                    <span className="passion-add-icon">+</span>
                    <span className="font-small quiet">Ajouter</span>
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
                <strong>Autoriser mes correspondants à voir mon profil</strong>
                <p className="quiet font-small">
                  Si décoché, cliquer sur votre profil dans la messagerie
                  indiquera que votre profil est privé.
                </p>
              </div>
            </label>
          </div>
        )}
      </div>

      {/* Informations personnelles */}
      <div className="profile-details-card stack-compact">
        <span className="eyebrow">Informations personnelles</span>
        {profile?.birthDate && (
          <div className="profile-info-row">
            <span className="profile-info-label">Date de naissance</span>
            <strong className="profile-info-value">{profile.birthDate}</strong>
          </div>
        )}
        {profile?.city && (
          <div className="profile-info-row">
            <span className="profile-info-label">Lieu de résidence</span>
            <strong className="profile-info-value">{profile.city}</strong>
          </div>
        )}
        {role === 'patient' && profile?.clinicianEmail && (
          <div className="profile-info-row">
            <span className="profile-info-label">Clinicien référent</span>
            <strong className="profile-info-value">
              {profile.clinicianEmail}
            </strong>
          </div>
        )}
      </div>

      <div className="profile-actions-stack stack">
        <a href="#/settings" className="button button-ghost button-wide">
          Paramètres & Confidentialité
        </a>
        {onLeave && (
          <button
            type="button"
            className="button button-wide"
            onClick={onLeave}
          >
            Déconnexion / Quitter ce compte
          </button>
        )}
      </div>
    </section>
  )
}

export default ProfileView
