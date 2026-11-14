import { useState } from 'react'
import {
  type AppUser,
  declineThread,
  getPatientHome,
  postMessage,
  postNeed,
} from '../api/client'
import BottomNav, { type TabType } from '../components/BottomNav'
import ChatView from '../components/ChatView'
import ProfileView from '../components/ProfileView'
import WatchLink from '../components/WatchLink'
import ScreenFrame from './ScreenFrame'
import { useHome } from './useHome'
import { useThreads } from './useThreads'

type PatientScreenProps = {
  token: string
  onLeave: () => void
}

// L'écran du patient. Il répond aux demandes (sa réponse, sa frappe et ses refus nourrissent
// la boucle) et peut aussi confier un besoin à la communauté.
function PatientScreen({ token, onLeave }: PatientScreenProps) {
  const { home, error } = useHome(token, getPatientHome, onLeave)
  const chat = useThreads(token, 'patient', onLeave)
  const [activeTab, setActiveTab] = useState<TabType>('messages')
  const [openId, setOpenId] = useState<string | null>(null)
  const [patientNeed, setPatientNeed] = useState('')
  const [sentNeedFeedback, setSentNeedFeedback] = useState(false)
  const [updatedUser, setUpdatedUser] = useState<AppUser | null>(null)

  if (!home) {
    return (
      <ScreenFrame>
        <p className="quiet">{error ?? 'Loading…'}</p>
      </ScreenFrame>
    )
  }

  const me = updatedUser ?? home.user
  const threads = chat.threads ?? []
  const toAnswer = threads.filter(
    (thread) => thread.status === 'to_answer',
  ).length
  const myNeeds = threads.filter((thread) => thread.kind === 'need')

  async function handleSendNeed() {
    const text = patientNeed.trim()
    if (!text) return
    const sent = await chat.run(() => postNeed(token, text))
    if (!sent) return
    setPatientNeed('')
    setSentNeedFeedback(true)
    window.setTimeout(() => setSentNeedFeedback(false), 3000)
  }

  async function handleDecline(threadId: string) {
    const done = await chat.run(() => declineThread(token, threadId))
    if (done) setOpenId(null)
  }

  return (
    <ScreenFrame
      name={me.first_name}
      avatarUrl={me.avatar_url ?? undefined}
      onLeave={onLeave}
      bottomNav={
        <BottomNav
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          unreadBadge={toAnswer}
        />
      }
    >
      <main className="stack">
        {(error || chat.error) && (
          <p className="error" role="alert">
            {error ?? chat.error}
          </p>
        )}

        {/* Onglet 1 : demander un coup de main à la communauté */}
        {activeTab === 'request' && (
          <section className="stack text-center section-centered">
            <h1 className="text-center">Need a hand for something?</h1>
            <p className="quiet text-center">
              Share a small question, ask for a tip, or request a quick hand. A
              helper from the community will pick it up.
            </p>

            <div className="card-patient-ask stack">
              <textarea
                rows={4}
                value={patientNeed}
                maxLength={600}
                placeholder="e.g. Could someone recommend a quiet park walk in Helsinki, or give a tip on sourdough starter?"
                aria-label="Your request to community"
                onChange={(e) => setPatientNeed(e.target.value)}
              />
              <div className="button-center-wrap">
                <button
                  type="button"
                  className="button button-primary button-wide"
                  disabled={chat.busy || patientNeed.trim() === ''}
                  onClick={() => void handleSendNeed()}
                >
                  Share with community
                </button>
              </div>
              {sentNeedFeedback && (
                <span className="success-pill">
                  ✓ Shared. You will find the conversation in Messages.
                </span>
              )}
            </div>

            {myNeeds.length > 0 && (
              <div className="stack text-left">
                <p className="eyebrow">Your requests to the community</p>
                {myNeeds.map((need) => (
                  <button
                    key={need.id}
                    type="button"
                    className="card-patient-need-banner text-left"
                    onClick={() => {
                      setOpenId(need.id)
                      setActiveTab('messages')
                    }}
                  >
                    <p className="patient-need-body">
                      « {need.messages[0]?.text} »
                    </p>
                    <span className="quiet font-small">
                      {need.status === 'open'
                        ? 'Waiting for a helper'
                        : `Picked up by ${need.peer?.name ?? 'a helper'}`}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Onglet 2 : les fils, demandes reçues en tête */}
        {activeTab === 'messages' && (
          <ChatView
            role="patient"
            userId={me.id}
            threads={threads}
            busy={chat.busy}
            openId={openId}
            onOpen={setOpenId}
            onSend={(threadId, text, attachments, typing) =>
              chat.run(() =>
                postMessage(token, threadId, text, attachments, typing),
              )
            }
            onDecline={handleDecline}
            onStartNewRequest={() => setActiveTab('request')}
          />
        )}

        {/* Onglet 3 : mon profil, avec la montre Garmin */}
        {activeTab === 'profile' && (
          <ProfileView
            user={me}
            token={token}
            threads={threads}
            onUpdated={setUpdatedUser}
            onLeave={onLeave}
          >
            <WatchLink token={token} onSignedOut={onLeave} />
          </ProfileView>
        )}
      </main>
    </ScreenFrame>
  )
}

export default PatientScreen
