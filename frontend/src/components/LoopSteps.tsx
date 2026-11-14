// Les douze étapes de la boucle, rangées selon les trois temps du challenge.
const PHASES = [
  { name: 'Sense', steps: [{ n: 1, label: 'Measure state' }] },
  {
    name: 'Respond',
    steps: [
      { n: 2, label: 'Set the zone' },
      { n: 3, label: 'Pick helper' },
      { n: 4, label: 'Generate' },
      { n: 5, label: 'Measure, filter' },
      { n: 6, label: 'Propose three' },
      { n: 7, label: 'Helper decides' },
      { n: 8, label: 'Check message' },
      { n: 9, label: 'Patient receives' },
    ],
  },
  {
    name: 'Learn',
    steps: [
      { n: 10, label: 'Measure again' },
      { n: 11, label: 'Reward' },
      { n: 12, label: 'Update model' },
    ],
  },
]

type LoopStepsProps = {
  current: number
  // À l'étape 12, tout est fait : la boucle est bouclée.
  complete: boolean
}

function LoopSteps({ current, complete }: LoopStepsProps) {
  return (
    <ol className="steps" aria-label="Loop steps">
      {PHASES.map((phase) => (
        <li key={phase.name} className="phase">
          <span className="phase-name">{phase.name}</span>
          <ol className="phase-steps">
            {phase.steps.map((step) => {
              const done = complete || step.n < current
              const active = !complete && step.n === current
              const state = active ? 'active' : done ? 'done' : 'todo'
              return (
                <li
                  key={step.n}
                  className={`step step-${state}`}
                  aria-current={active ? 'step' : undefined}
                >
                  <span className="step-number">{step.n}</span>
                  <span className="step-label">{step.label}</span>
                </li>
              )
            })}
          </ol>
        </li>
      ))}
    </ol>
  )
}

export default LoopSteps
