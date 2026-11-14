import { useEffect, useState } from 'react'
import {
  ApiError,
  type ClinicianHome,
  type ClinicianNotes,
  type ClinicianPatient,
  getClinicianHome,
  saveClinicianNotes,
} from '../api/client'
import Logo from '../components/Logo'

type ClinicianScreenProps = {
  token: string
  onLeave: () => void
}

const EMPTY_NOTES: ClinicianNotes = { mood: '', proud: '', loves: '' }

function when(seconds: number): string {
  return new Date(seconds * 1000).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// Lecture indicative du bien-être que lisent les réseaux : jamais un diagnostic.
function climate(patient: ClinicianPatient): { label: string; gain: boolean } {
  if (patient.wellbeing >= 0.6) return { label: 'Steady', gain: true }
  if (patient.wellbeing >= 0.4) return { label: 'Watch gently', gain: false }
  return { label: 'Consider reaching out', gain: false }
}

function trendText(patient: ClinicianPatient): string {
  const points = patient.trend
  if (points.length < 2) return 'Not enough exchanges yet'
  const delta = points[points.length - 1].wellbeing - points[0].wellbeing
  if (delta > 0.02) return `↑ +${delta.toFixed(2)} since the first request`
  if (delta < -0.02) return `↓ ${delta.toFixed(2)} since the first request`
  return 'Stable since the first request'
}

// Le portail du clinicien (`#/clinician`) : les patients qui l'ont désigné à l'inscription,
// leur bien-être lu par les réseaux, leur activité et ses notes. Jamais le contenu des échanges.
function ClinicianScreen({ token, onLeave }: ClinicianScreenProps) {
  const [home, setHome] = useState<ClinicianHome | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  // Notes en cours d'écriture, par patient ; sinon celles enregistrées.
  const [drafts, setDrafts] = useState<Record<string, ClinicianNotes>>({})
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  useEffect(() => {
    document.title = 'Needed · Clinician Portal'
    return () => {
      document.title = 'Needed'
    }
  }, [])

  useEffect(() => {
    getClinicianHome(token)
      .then(setHome)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) onLeave()
        else
          setError(
            err instanceof ApiError
              ? err.message
              : 'The server is not responding.',
          )
      })
  }, [token, onLeave])

  const patient =
    home?.patients.find((item) => item.id === selectedId) ??
    home?.patients[0] ??
    null

  const saved = patient?.notes
  const notes: ClinicianNotes =
    (patient && drafts[patient.id]) ??
    (saved
      ? { mood: saved.mood, proud: saved.proud, loves: saved.loves }
      : EMPTY_NOTES)

  function setNotes(update: (current: ClinicianNotes) => ClinicianNotes) {
    if (!patient) return
    setDrafts((current) => ({ ...current, [patient.id]: update(notes) }))
  }

  async function handleSaveNotes(event: React.FormEvent) {
    event.preventDefault()
    if (!patient) return
    setSaving(true)
    setError(null)
    try {
      setHome(await saveClinicianNotes(token, patient.id, notes))
      setDrafts((current) => {
        const next = { ...current }
        delete next[patient.id]
        return next
      })
      setSaveSuccess(true)
      window.setTimeout(() => setSaveSuccess(false), 3500)
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'The server is not responding.',
      )
    } finally {
      setSaving(false)
    }
  }

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
          <button
            type="button"
            className="button button-ghost button-small"
            onClick={onLeave}
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="stack">
        <section className="clinician-hero">
          <p className="eyebrow">Passive Telemetry & Personality Insights</p>
          <h1>Post-TMS Patient Oversight</h1>
          <p className="quiet">
            Continuous remission tracking without questionnaires. Well-being is
            read from the watch and in-app signals; the content of exchanges
            stays private to the patient.
          </p>
        </section>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <div className="clinic-meta-box">
          <div>
            <span className="meta-label">Clinician on duty</span>
            <strong className="meta-value">
              {home ? `${home.user.first_name} ${home.user.last_name}` : '…'}
            </strong>
          </div>
          <div>
            <span className="meta-label">Followed patients</span>
            <strong className="meta-value">
              {home ? home.patients.length : '…'}
            </strong>
          </div>
        </div>

        {home && home.patients.length === 0 && (
          <p className="quiet">
            No patient has given your email ({home.user.email}) yet. Patients
            enter it when they join.
          </p>
        )}

        {home && home.patients.length > 1 && (
          <div
            className="helper-patient-selector"
            role="tablist"
            aria-label="Followed patients"
          >
            {home.patients.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={item.id === patient?.id}
                className={`helper-patient-pill ${item.id === patient?.id ? 'active' : ''}`}
                onClick={() => setSelectedId(item.id)}
              >
                <span>{item.first_name}</span>
              </button>
            ))}
          </div>
        )}

        {patient && (
          <section className="card-patient-oversight">
            <div className="patient-header">
              <div className="patient-identity-cluster">
                {patient.avatar_url ? (
                  <img
                    src={patient.avatar_url}
                    alt={patient.first_name}
                    className="clinic-avatar-large"
                  />
                ) : (
                  <div className="thread-avatar-fallback">
                    {patient.first_name.charAt(0)}
                  </div>
                )}
                <div>
                  <span className="eyebrow">Monitored Patient</span>
                  <h2>{`${patient.first_name} ${patient.last_name}`.trim()}</h2>
                  <div className="patient-tags">
                    {patient.birth_date && (
                      <span className="tag-quiet">
                        Born: {patient.birth_date}
                      </span>
                    )}
                    {patient.city && (
                      <span className="tag-quiet">City: {patient.city}</span>
                    )}
                    <span className="tag-quiet">
                      Joined: {when(patient.joined_at)}
                    </span>
                  </div>
                </div>
              </div>
              <span className="status-pill status-pill-active">
                <span className="status-dot"></span> {climate(patient).label}
              </span>
            </div>

            <div className="clinical-grid">
              <div className="clinical-metric">
                <span className="metric-title">Well-being reading</span>
                <span className="metric-score">
                  {patient.wellbeing.toFixed(2)}
                </span>
                <span
                  className={`metric-trend ${climate(patient).gain ? 'text-gain' : ''}`}
                >
                  {trendText(patient)}
                </span>
              </div>

              <div className="clinical-metric">
                <span className="metric-title">Peer Exchanges</span>
                <span className="metric-score">
                  {patient.answered} answered
                </span>
                <span className="metric-trend">
                  {patient.waiting > 0
                    ? `${patient.waiting} waiting for them`
                    : 'Nothing waiting'}
                </span>
              </div>

              <div className="clinical-metric">
                <span className="metric-title">Let pass</span>
                <span className="metric-score">{patient.declined}</span>
                <span className="metric-trend">
                  &laquo; Not now &raquo; is always allowed
                </span>
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
                <strong>Clinical Guardrail:</strong> the lower the well-being
                reading, the closer requests stay to the patient&apos;s own
                interests and the lighter they get. The reading is indicative,
                never a diagnosis.
              </p>
            </div>
          </section>
        )}

        {patient && (
          <section className="card-notes-editor stack">
            <div className="editor-header">
              <div>
                <span className="eyebrow">Therapeutic Profile</span>
                <h2>Patient Personality & Mood Baseline</h2>
                <p className="quiet">
                  Document what makes {patient.first_name} proud and what brings
                  them joy.
                </p>
              </div>
              <span className="last-saved-badge">
                {patient.notes
                  ? `Last saved: ${when(patient.notes.updated_at)}`
                  : 'Not saved yet'}
              </span>
            </div>

            <form onSubmit={handleSaveNotes} className="stack">
              <label className="field">
                <span>
                  <strong>Patient mood & emotional climate</strong>
                </span>
                <textarea
                  rows={3}
                  maxLength={300}
                  value={notes.mood}
                  placeholder="e.g. Calm, receptive, gradual return of daily motivation"
                  onChange={(e) =>
                    setNotes((n) => ({ ...n, mood: e.target.value }))
                  }
                />
              </label>

              <label className="field">
                <span>
                  <strong>What makes them proud</strong>
                </span>
                <textarea
                  rows={3}
                  maxLength={300}
                  value={notes.proud}
                  placeholder="e.g. Mastering sourdough baking; volunteering at the community greenhouse"
                  onChange={(e) =>
                    setNotes((n) => ({ ...n, proud: e.target.value }))
                  }
                />
              </label>

              <label className="field">
                <span>
                  <strong>What they love doing</strong>
                </span>
                <textarea
                  rows={3}
                  maxLength={300}
                  value={notes.loves}
                  placeholder="e.g. Houseplants, jazz records, Scandinavian novels"
                  onChange={(e) =>
                    setNotes((n) => ({ ...n, loves: e.target.value }))
                  }
                />
              </label>

              <div className="row-align-center">
                <button
                  type="submit"
                  className="button button-primary button-medium"
                  disabled={saving}
                >
                  {saving ? 'Saving…' : 'Save Clinical Notes'}
                </button>
                {saveSuccess && (
                  <span className="success-pill">✓ Notes saved</span>
                )}
              </div>
            </form>
          </section>
        )}

        {patient && (
          <section className="stack">
            <h2>Recent Reciprocal Events</h2>
            {patient.trend.length === 0 ? (
              <p className="quiet">No request handled yet.</p>
            ) : (
              <ul className="clinical-events">
                {[...patient.trend].reverse().map((point, index) => (
                  <li key={index} className="clinical-event-item">
                    <span className="event-time">{when(point.at)}</span>
                    <div className="event-body">
                      {index === patient.trend.length - 1 &&
                      patient.trend.length > 1 ? (
                        <strong>Before the first request</strong>
                      ) : (
                        <strong>Handled a community request</strong>
                      )}{' '}
                      · well-being {point.wellbeing.toFixed(2)}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </main>
    </div>
  )
}

export default ClinicianScreen
