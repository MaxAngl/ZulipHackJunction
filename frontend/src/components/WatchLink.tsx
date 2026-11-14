import { useState } from 'react'
import {
  getWatch,
  linkWatch,
  unlinkWatch,
  type WatchReading,
} from '../api/client'
import { useHome } from '../screens/useHome'

type WatchLinkProps = {
  token: string
  onSignedOut: () => void
}

// Les mesures montrées au patient : les siennes, telles que la montre les envoie. Jamais θ :
// on ne lui renvoie pas une note de son état.
function readingRows(reading: WatchReading): [string, string][] {
  const rows: [string, number | null | undefined, string][] = [
    ['Heart rate', reading.heart_rate, ' bpm'],
    ['Stress', reading.stress, ' / 100'],
    ['Body Battery', reading.body_battery, ' / 100'],
    ['Steps today', reading.steps_today, ''],
  ]
  return rows
    .filter(([, value]) => value != null)
    .map(([label, value, unit]) => [
      label,
      `${Math.round(value as number).toLocaleString('en')}${unit}`,
    ])
}

function seenText(lastSeen: number | null): string {
  if (lastSeen == null) return 'Linked, waiting for data'
  const minutes = Math.floor((Date.now() / 1000 - lastSeen) / 60)
  return minutes < 1 ? 'Data received just now' : `Data ${minutes} min ago`
}

// La montre Garmin du patient, dans son profil : il la lie avec le code qu'affiche l'app Needed
// sur la montre, puis voit arriver ses mesures. La montre lui montre aussi ses demandes.
function WatchLink({ token, onSignedOut }: WatchLinkProps) {
  const {
    home: watch,
    error,
    busy,
    run,
  } = useHome(token, getWatch, onSignedOut)
  const [code, setCode] = useState('')

  if (!watch) return null

  return (
    <div className="profile-details-card stack-compact">
      <span className="eyebrow">Garmin watch</span>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {watch.linked ? (
        <>
          <div className="profile-info-row">
            <span className="profile-info-label">Status</span>
            <strong className="profile-info-value">
              {seenText(watch.last_seen)}
            </strong>
          </div>
          {watch.last_reading &&
            readingRows(watch.last_reading).map(([label, value]) => (
              <div key={label} className="profile-info-row">
                <span className="profile-info-label">{label}</span>
                <strong className="profile-info-value">{value}</strong>
              </div>
            ))}
          <button
            type="button"
            className="button button-ghost button-small"
            disabled={busy}
            onClick={() => void run(() => unlinkWatch(token))}
          >
            Unlink watch
          </button>
        </>
      ) : (
        <>
          <p className="quiet">
            Open Needed on your Garmin watch: it shows a 6-digit code.
          </p>
          <div className="row">
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="123456"
              aria-label="Code shown on your watch"
              value={code}
              onChange={(event) =>
                setCode(event.target.value.replace(/\D/g, '').slice(0, 6))
              }
            />
            <button
              type="button"
              className="button button-primary"
              disabled={busy || code.length !== 6}
              onClick={() => void run(() => linkWatch(token, code))}
            >
              Link watch
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export default WatchLink
