import { useState } from 'react'
import {
  type AppUser,
  declineThread,
  getPatientHome,
  postMessage,
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

// L'écran du patient. Il répond aux demandes : sa réponse, sa frappe et ses refus nourrissent
// la boucle. Il ne demande rien lui-même : c'est lui qui rend service.
function PatientScreen({ token, onLeave }: PatientScreenProps) {
  const { home, error } = useHome(token, getPatientHome, onLeave)
  const chat = useThreads(token, 'patient', onLeave)
  const [activeTab, setActiveTab] = useState<TabType>('messages')
  const [openId, setOpenId] = useState<string | null>(null)
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
          withRequest={false}
        />
      }
    >
      <main className="stack">
        {(error || chat.error) && (
          <p className="error" role="alert">
            {error ?? chat.error}
          </p>
        )}

        {/* Onglet 1 : les fils, demandes reçues en tête */}
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
          />
        )}

        {/* Onglet 2 : mon profil, avec la montre Garmin */}
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
