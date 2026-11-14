import type { HistoryEntry } from '../api/client'

type HistoryPanelProps = {
  history: HistoryEntry[]
}

// La récompense va de 0 à 100 : 50 veut dire que l'état du patient n'a pas bougé.
const NEUTRAL_REWARD = 50

// Le journal des manches : c'est de lui que le vecteur du patient apprend.
function HistoryPanel({ history }: HistoryPanelProps) {
  if (history.length === 0) {
    return (
      <section className="history" aria-label="Loop history">
        <h2>What the loop has learned</h2>
        <p className="quiet">
          No answer yet. Each answer is scored a day later, from 0 to 100, and
          tunes this patient's personal vector.
        </p>
      </section>
    )
  }

  return (
    <section className="history" aria-label="Loop history">
      <h2>What the loop has learned</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Round</th>
              <th scope="col">From</th>
              <th scope="col">Request</th>
              <th scope="col" className="number">
                Position
              </th>
              <th scope="col">Patient</th>
              <th scope="col" className="number">
                State L
              </th>
              <th scope="col" className="number">
                Reward
              </th>
              <th scope="col" className="number">
                Zone centre
              </th>
            </tr>
          </thead>
          <tbody>
            {history
              .slice()
              .reverse()
              .map((entry, index) => (
                <tr key={`${entry.number}-${index}`}>
                  <td>{entry.number}</td>
                  <td>{entry.helper_name}</td>
                  <td className="request" title={entry.text}>
                    {entry.text}
                  </td>
                  <td className="number">{entry.lam.toFixed(2)}</td>
                  <td>{entry.action === 'helped' ? 'Helped' : 'Not now'}</td>
                  <td className="number">
                    {entry.theta_before.toFixed(2)} →{' '}
                    {entry.theta_after.toFixed(2)}
                  </td>
                  <td
                    className={
                      entry.reward >= NEUTRAL_REWARD
                        ? 'number gain'
                        : 'number loss'
                    }
                  >
                    {entry.reward.toFixed(0)}
                  </td>
                  <td className="number">
                    {entry.center_before.toFixed(2)} →{' '}
                    {entry.center_after.toFixed(2)}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default HistoryPanel
