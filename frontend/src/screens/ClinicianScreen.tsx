import { useEffect, useState } from 'react'
import Logo from '../components/Logo'
import {
  type ClinicianNotes,
  readClinicianEmail,
  readClinicianNotes,
  readToken,
  readUserProfile,
  saveClinicianNotes,
  type UserProfile,
} from '../session'

// Écran clinicien accessible via `#/clinician`.
// Permet au médecin / thérapeute de renseigner le profil thérapeutique et la personnalité
// du patient (mood, fiertés, centres d'intérêt) et de suivre sa stabilité post-TMS sans questionnaires.
function ClinicianScreen() {
  const [email] = useState(
    () => readClinicianEmail() ?? 'dr.virtanen@helsinki-tms.fi',
  )
  const hasPatientSession = readToken('patient') !== null
  const [patientProfile] = useState<UserProfile | null>(() =>
    readUserProfile('patient'),
  )

  const [notes, setNotes] = useState<ClinicianNotes>(() => readClinicianNotes())
  const [saveSuccess, setSaveSuccess] = useState(false)

  useEffect(() => {
    document.title = 'Needed · Clinician Portal'
    return () => {
      document.title = 'Needed'
    }
  }, [])

  function handleSaveNotes(e: React.FormEvent) {
    e.preventDefault()
    const updated: ClinicianNotes = {
      ...notes,
      updatedAt: new Date().toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }),
    }
    setNotes(updated)
    saveClinicianNotes(updated)
    setSaveSuccess(true)
    setTimeout(() => {
      setSaveSuccess(false)
    }, 3500)
  }

  const patientName = patientProfile
    ? `${patientProfile.firstName} ${patientProfile.lastName}`.trim()
    : hasPatientSession
      ? 'Patient Suivi'
      : 'Julien Mercier (Cohorte Suivie)'

  const patientAvatar = patientProfile?.avatarUrl ?? '/moomins/Muumipeikko2.jpg'
  const patientCity = patientProfile?.city ?? 'Helsinki, Punavuori'
  const patientBirth = patientProfile?.birthDate ?? '1994-05-14'

  return (
    <div className="screen clinician-screen">
      <header className="topbar">
        <div className="brand">
          <Logo size={36} />
          <div className="brand-text">
            <span className="brand-name">Needed</span>
            <span className="brand-tagline">Clinician Oversight Portal</span>
          </div>
        </div>
        <div className="topbar-actions">
          <span className="badge-clinic">Medical Portal</span>
          <a href="#/" className="button button-ghost button-small">
            Exit Portal
          </a>
        </div>
      </header>

      <main className="stack">
        <section className="clinician-hero">
          <p className="eyebrow">Passive Telemetry & Personality Insights</p>
          <h1>Post-TMS Patient Oversight</h1>
          <p className="quiet">
            Continuous remission tracking without invasive questionnaires.
            Well-being and emotional agency are inferred from spontaneous peer
            reciprocity.
          </p>
        </section>

        <div className="clinic-meta-box">
          <div>
            <span className="meta-label">Clinician on duty</span>
            <strong className="meta-value">{email}</strong>
          </div>
          <div>
            <span className="meta-label">Protocol</span>
            <strong className="meta-value">
              rTMS Post-Care · Junction Protocol
            </strong>
          </div>
        </div>

        {/* Fiche Patient : Identité & Avatar */}
        <section className="card-patient-oversight">
          <div className="patient-header">
            <div className="patient-identity-cluster">
              <img
                src={patientAvatar}
                alt={patientName}
                className="clinic-avatar-large"
              />
              <div>
                <span className="eyebrow">Monitored Patient</span>
                <h2>{patientName}</h2>
                <div className="patient-tags">
                  <span className="tag-quiet">Born: {patientBirth}</span>
                  <span className="tag-quiet">City: {patientCity}</span>
                  {patientProfile?.clinicianEmail && (
                    <span className="tag-quiet">
                      Assigned to: {patientProfile.clinicianEmail}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <span className="status-pill status-pill-active">
              <span className="status-dot"></span> Remission Stable
            </span>
          </div>

          <div className="clinical-grid">
            <div className="clinical-metric">
              <span className="metric-title">Behavioral State θ</span>
              <span className="metric-score">0.74</span>
              <span className="metric-trend text-gain">↑ Stable recovery</span>
            </div>

            <div className="clinical-metric">
              <span className="metric-title">Safety Zone λ(θ)</span>
              <span className="metric-score">0.45 – 0.68</span>
              <span className="metric-trend">Low-effort boundary</span>
            </div>

            <div className="clinical-metric">
              <span className="metric-title">Peer Exchanges</span>
              <span className="metric-score">3 completed</span>
              <span className="metric-trend">100% positive gratitude</span>
            </div>

            <div className="clinical-metric">
              <span className="metric-title">Survey Burden</span>
              <span className="metric-score">0 queries</span>
              <span className="metric-trend text-gain">
                Zero intrusive load
              </span>
            </div>
          </div>

          <div className="clinical-notice">
            <p className="note">
              <strong>Clinical Guardrail:</strong> The peer-matching algorithm
              automatically filters out high-effort tasks whenever behavioural
              signals dip below θ = 0.50. The patient experiences genuine
              community agency without therapeutic pressure.
            </p>
          </div>
        </section>

        {/* Section ÉDITION : Mood & Personnalité du patient */}
        <section className="card-notes-editor stack">
          <div className="editor-header">
            <div>
              <span className="eyebrow">Therapeutic Profile</span>
              <h2>Patient Personality & Mood Baseline</h2>
              <p className="quiet">
                Document what makes the patient proud and what brings them joy.
                These qualitative cues configure the matching engine to suggest
                delightful, low-friction interactions.
              </p>
            </div>
            <span className="last-saved-badge">
              Last saved: {notes.updatedAt}
            </span>
          </div>

          <form onSubmit={handleSaveNotes} className="stack">
            <label className="field">
              <span>
                <strong>Patient mood & emotional climate</strong>
              </span>
              <span className="quiet font-small">
                Current affect, receptivity, energy reserves and emotional
                stability.
              </span>
              <textarea
                rows={3}
                value={notes.mood}
                placeholder="e.g. Calm, receptive, gradual resurgence of daily motivation"
                onChange={(e) =>
                  setNotes((n) => ({ ...n, mood: e.target.value }))
                }
              />
            </label>

            <label className="field">
              <span>
                <strong>What makes them proud (ce qui la rend fier)</strong>
              </span>
              <span className="quiet font-small">
                Core competencies, meaningful achievements, craft, or personal
                victories that restore self-worth.
              </span>
              <textarea
                rows={3}
                value={notes.whatMakesThemProud}
                placeholder="e.g. Mastering sourdough baking; woodworking; volunteering at community greenhouse"
                onChange={(e) =>
                  setNotes((n) => ({
                    ...n,
                    whatMakesThemProud: e.target.value,
                  }))
                }
              />
            </label>

            <label className="field">
              <span>
                <strong>What they love doing (ce qu'elle aime faire)</strong>
              </span>
              <span className="quiet font-small">
                Soothing passions, comforting hobbies, and conversational topics
                that spark natural joy.
              </span>
              <textarea
                rows={3}
                value={notes.whatTheyLoveDoing}
                placeholder="e.g. Caring for houseplants, listening to classic jazz vinyl, Scandinavian literature"
                onChange={(e) =>
                  setNotes((n) => ({
                    ...n,
                    whatTheyLoveDoing: e.target.value,
                  }))
                }
              />
            </label>

            <div className="row-align-center">
              <button
                type="submit"
                className="button button-primary button-medium"
              >
                Save Clinical Notes
              </button>
              {saveSuccess && (
                <span className="success-pill">
                  ✓ Notes successfully saved to medical record
                </span>
              )}
            </div>
          </form>
        </section>

        {/* Journal d'activité récente */}
        <section className="stack">
          <h2>Recent Reciprocal Events</h2>
          <ul className="clinical-events">
            <li className="clinical-event-item">
              <span className="event-time">Today, 09:20</span>
              <div className="event-body">
                <strong>Gave advice on sourdough baking</strong> to Mikko.
                Received heartfelt thanks:{' '}
                <em>« Thanks so much, loaf turned out amazing! »</em>
              </div>
            </li>
            <li className="clinical-event-item">
              <span className="event-time">Yesterday, 14:15</span>
              <div className="event-body">
                <strong>Declined a photography request</strong> via « Not now »
                button. System recorded normal agency with zero clinical
                friction.
              </div>
            </li>
          </ul>
        </section>
      </main>
    </div>
  )
}

export default ClinicianScreen
