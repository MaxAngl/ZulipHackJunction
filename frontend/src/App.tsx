import { useState } from 'react'
import { ApiError, predict, type PredictResponse } from './api/client'

// Démo de bout en bout front -> backend -> ml. À remplacer par la vraie UI.
function App() {
  const [text, setText] = useState('')
  const [result, setResult] = useState<PredictResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function runPrediction() {
    setLoading(true)
    setError(null)
    try {
      setResult(await predict({ text }))
    } catch (err) {
      setResult(null)
      setError(
        err instanceof ApiError ? `${err.code} : ${err.message}` : String(err),
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <h1>Hackathon</h1>
      <form
        onSubmit={(event) => {
          event.preventDefault()
          void runPrediction()
        }}
      >
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Tape un texte…"
          rows={4}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Analyse…' : 'Analyser'}
        </button>
      </form>
      {result && (
        <p>
          Label : <strong>{result.label}</strong> (score {result.score})
        </p>
      )}
      {error && <p className="error">{error}</p>}
    </main>
  )
}

export default App
