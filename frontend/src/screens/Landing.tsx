import ScreenFrame from './ScreenFrame'

// Page d'entrée de la vraie app : deux chemins, et un lien vers la console de démo.
function Landing() {
  return (
    <ScreenFrame>
      <main className="stack hero">
        <h1>Ask for a hand. Give one back.</h1>
        <p className="lead">
          A community where people recovering from depression are the ones who
          help. Small, real favours between real people.
        </p>
        <div className="stack">
          <a className="button button-primary button-wide" href="#/helper">
            Join the community
          </a>
          <a className="button button-wide" href="#/patient">
            My clinic invited me
          </a>
        </div>
        <a className="link" href="#/demo">
          See how the loop works
        </a>
      </main>
    </ScreenFrame>
  )
}

export default Landing
