import type { ReactNode } from 'react'
import type { Person } from '../api/client'

type PhoneFrameProps = {
  role: 'Helper' | 'Patient'
  person: Person
  children: ReactNode
}

// Cadre commun aux deux téléphones de la démo.
function PhoneFrame({ role, person, children }: PhoneFrameProps) {
  return (
    <section
      className={`phone phone-${role.toLowerCase()}`}
      aria-label={`${role} phone`}
    >
      <header className="phone-header">
        <span className="avatar" aria-hidden="true">
          {person.name.charAt(0)}
        </span>
        <div className="phone-who">
          <span className="phone-role">{role}</span>
          <span className="phone-name">{person.name}</span>
        </div>
      </header>
      <ul className="chips" aria-label={`${person.name}'s interests`}>
        {person.interests.map((interest) => (
          <li key={interest} className="chip">
            {interest}
          </li>
        ))}
      </ul>
      <div className="phone-body">{children}</div>
    </section>
  )
}

export default PhoneFrame
