import type { HistoryEntry } from '../api/client'

type HistoryPanelProps = {
  history: HistoryEntry[]
}

function signed(value: number): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}`
}

// Le journal des manches : c'est ce que le modèle apprend, et ce qu'un vrai modèle utiliserait.
function HistoryPanel({ history }: HistoryPanelProps) {
  if (history.length === 0) {
    return (
      <section className="history" aria-label="Loop history">
        <h2>What the loop has learned</h2>
        <p className="quiet">
          No answer yet. Each answer moves and narrows the zone for this
          patient.
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
                State θ
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
                      entry.reward >= 0 ? 'number gain' : 'number loss'
                    }
                  >
                    {signed(entry.reward)}
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
