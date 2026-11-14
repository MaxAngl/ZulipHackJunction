import { useState } from 'react'
import { getPatientHome } from '../api/client'
import BottomNav, { type TabType } from '../components/BottomNav'
import ChatView from '../components/ChatView'
import ProfileView from '../components/ProfileView'
import WatchLink from '../components/WatchLink'
import { readUserProfile, savePatientCommunityNeed } from '../session'
import ScreenFrame from './ScreenFrame'
import { useHome } from './useHome'

type PatientScreenProps = {
  token: string
  onLeave: () => void
}

// L'écran du patient, dans la vraie app. Il répond aux demandes et peut aussi exprimer un besoin.
function PatientScreen({ token, onLeave }: PatientScreenProps) {
  const { home, error } = useHome(token, getPatientHome, onLeave)
  const [activeTab, setActiveTab] = useState<TabType>('messages')
  const [patientNeed, setPatientNeed] = useState('')
  const [sentNeedFeedback, setSentNeedFeedback] = useState(false)

  if (!home) {
    return (
      <ScreenFrame>
        <p className="quiet">{error ?? 'Loading…'}</p>
      </ScreenFrame>
    )
  }

  const profile = readUserProfile('patient')
  const unreadCount = home.inbox.length

  function handleSendNeed() {
    if (!patientNeed.trim()) return
    const needText = patientNeed.trim()
    savePatientCommunityNeed({
      id: `need-${Date.now()}`,
      patientName:
        profile && `${profile.firstName} ${profile.lastName}`.trim()
          ? `${profile.firstName} ${profile.lastName}`.trim()
          : (home?.user.name ?? 'Julien Mercier'),
      patientAvatar: profile?.avatarUrl ?? '/moomins/Muumipeikko2.jpg',
      text: needText,
      timestamp: new Date().toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }),
      answered: false,
    })
    setSentNeedFeedback(true)
    setPatientNeed('')
    setTimeout(() => {
      setSentNeedFeedback(false)
      setActiveTab('messages')
    }, 2000)
  }

  return (
    <ScreenFrame
      name={home.user.name}
      avatarUrl={profile?.avatarUrl}
      onLeave={onLeave}
      bottomNav={
        <BottomNav
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          unreadBadge={unreadCount}
        />
      }
    >
      <main className="stack">
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {/* Onglet 1 : Faire une demande (côté patient) */}
        {activeTab === 'request' && (
          <section className="stack text-center section-centered">
            <h1 className="text-center">Need a hand for something?</h1>
            <p className="quiet text-center">
              You can also share a small question, ask for a recipe tip, or
              request a quick hand from your trusted community circle.
            </p>

            <div className="card-patient-ask stack">
              <textarea
                rows={4}
                value={patientNeed}
                placeholder="e.g. Could someone recommend a quiet park walk in Helsinki, or give a tip on sourdough starter?"
                aria-label="Your request to community"
                onChange={(e) => setPatientNeed(e.target.value)}
              />
              <div className="button-center-wrap">
                <button
                  type="button"
                  className="button button-primary button-wide"
                  disabled={patientNeed.trim() === ''}
                  onClick={handleSendNeed}
                >
                  Share with community
                </button>
              </div>
              {sentNeedFeedback && (
                <span className="success-pill">
                  ✓ Your request was discreetly shared with your helper circle!
                </span>
              )}
            </div>
          </section>
        )}

        {/* Onglet 2 : Messagerie libre & multimédia */}
        {activeTab === 'messages' && (
          <ChatView
            role="patient"
            userName={home.user.name}
            onStartNewRequest={() => setActiveTab('request')}
          />
        )}

        {/* Onglet 3 : Mon profil, avec la montre Garmin */}
        {activeTab === 'profile' && (
          <ProfileView role="patient" name={home.user.name} onLeave={onLeave}>
            <WatchLink token={token} onSignedOut={onLeave} />
          </ProfileView>
        )}
      </main>
    </ScreenFrame>
  )
}

export default PatientScreen
