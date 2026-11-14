import { useState } from 'react'
import {
  getHelperHome,
  sendToPatient,
  skipSuggestions,
  suggest,
} from '../api/client'
import BottomNav, { type TabType } from '../components/BottomNav'
import ChatView from '../components/ChatView'
import ProfileView from '../components/ProfileView'
import {
  dismissPatientCommunityNeed,
  readPatientCommunityNeeds,
  readThreads,
  readUserProfile,
  saveThreads,
  type ConversationThread,
} from '../session'
import ScreenFrame from './ScreenFrame'
import { useHome } from './useHome'

type HelperScreenProps = {
  token: string
  onLeave: () => void
}

// L'écran de l'aidant, dans la vraie app. Il choisit une demande, la modifie ou écrit la
// sienne, puis lit la réponse et dit merci.
function HelperScreen({ token, onLeave }: HelperScreenProps) {
  const { home, error, busy, run } = useHome(token, getHelperHome, onLeave)
  const [activeTab, setActiveTab] = useState<TabType>('request')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [ownText, setOwnText] = useState('')
  const [patientNeeds, setPatientNeeds] = useState(() =>
    readPatientCommunityNeeds(),
  )

  function handleAcceptPatientNeed(need: {
    id: string
    patientName: string
    patientAvatar?: string
    text: string
  }) {
    // Insérer un fil de discussion ou ajouter le message à la conversation existante
    const existingThreads = readThreads('helper')
    const threadId = `thread-patient-${need.patientName.toLowerCase().replace(/\s+/g, '-')}`
    const existingThread = existingThreads.find((t) => t.id === threadId)

    const timeStr = new Date().toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
    })

    const newMsg = {
      id: `msg-${Date.now()}`,
      senderRole: 'patient' as const,
      senderName: need.patientName,
      text: need.text,
      timestamp: timeStr,
    }

    let updatedThreads: ConversationThread[]
    if (existingThread) {
      updatedThreads = existingThreads.map((t) =>
        t.id === threadId
          ? {
              ...t,
              lastMessageText: need.text,
              lastMessageTime: timeStr,
              isRead: false,
              isFinished: false,
              messages: [...t.messages, newMsg],
            }
          : t,
      )
    } else {
      const newThread: ConversationThread = {
        id: threadId,
        peerName: need.patientName,
        peerRole: 'patient',
        peerAvatar: need.patientAvatar,
        lastMessageText: need.text,
        lastMessageTime: timeStr,
        isRead: false,
        isFinished: false,
        helperMessageCount: 0,
        messages: [newMsg],
        peerProfile: {
          firstName: need.patientName.split(' ')[0] || need.patientName,
          lastName: need.patientName.split(' ')[1] || '',
          avatarUrl: need.patientAvatar,
          bio: 'Membre patient de la communauté Needed.',
          interests: ['jardinage', 'lecture', 'nature'],
          allowProfileView: true,
        },
      }
      updatedThreads = [newThread, ...existingThreads]
    }

    saveThreads('helper', updatedThreads)
    dismissPatientCommunityNeed(need.id)
    setPatientNeeds((prev) => prev.filter((item) => item.id !== need.id))
    setActiveTab('messages')
  }

  function handleDismissPatientNeed(id: string) {
    dismissPatientCommunityNeed(id)
    setPatientNeeds((prev) => prev.filter((item) => item.id !== id))
  }

  if (!home) {
    return (
      <ScreenFrame>
        <p className="quiet">{error ?? 'Loading…'}</p>
      </ScreenFrame>
    )
  }

  const hasProposals = home.patient_name != null
  const profile = readUserProfile('helper')

  const pendingRepliesCount = home.requests.filter(
    (r) => r.status === 'answered' && !r.thanks,
  ).length

  return (
    <ScreenFrame
      name={home.user.name}
      avatarUrl={profile?.avatarUrl}
      onLeave={onLeave}
      bottomNav={
        <BottomNav
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          unreadBadge={pendingRepliesCount}
        />
      }
    >
      <main className="stack">
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {/* Onglet 1 : Faire une demande */}
        {activeTab === 'request' && (
          <>
            {/* Demandes directes de patients de la communauté */}
            {patientNeeds.length > 0 && (
              <section className="stack patient-needs-banner-section">
                <div className="flex-between">
                  <p className="eyebrow">Demandes directes de patients</p>
                  <span className="badge-highlight">
                    {patientNeeds.length} besoin(s) exprimé(s)
                  </span>
                </div>
                {patientNeeds.map((need) => (
                  <div key={need.id} className="card-patient-need-banner">
                    <div className="patient-need-header">
                      <div className="row-align-center-tight">
                        <img
                          src={
                            need.patientAvatar ?? '/moomins/Muumipeikko2.jpg'
                          }
                          alt={need.patientName}
                          className="patient-need-avatar"
                        />
                        <div>
                          <strong>{need.patientName}</strong>
                          <span className="quiet font-small block">
                            Patient · {need.timestamp}
                          </span>
                        </div>
                      </div>
                      <span className="patient-need-tag">Besoin patient</span>
                    </div>

                    <p className="patient-need-body">« {need.text} »</p>

                    <div className="row">
                      <button
                        type="button"
                        className="button button-primary button-small"
                        onClick={() => handleAcceptPatientNeed(need)}
                      >
                        Répondre à {need.patientName}
                      </button>
                      <button
                        type="button"
                        className="button button-ghost button-small"
                        onClick={() => handleDismissPatientNeed(need.id)}
                      >
                        Passer
                      </button>
                    </div>
                  </div>
                ))}
              </section>
            )}

            {hasProposals ? (
              <section className="stack">
                <p className="eyebrow">For you today</p>
                <h1>{home.patient_name} could help you.</h1>
                <p className="quiet">Pick one, change it, or write your own.</p>
                {home.proposals.length === 0 && (
                  <p className="quiet">
                    No suggestion fits right now. You can still write your own.
                  </p>
                )}
                <ul className="proposals">
                  {home.proposals.map((proposal) => (
                    <li key={proposal.id} className="proposal">
                      {editingId === proposal.id ? (
                        <>
                          <textarea
                            value={editText}
                            rows={4}
                            aria-label="Edit the request"
                            onChange={(event) =>
                              setEditText(event.target.value)
                            }
                          />
                          <div className="row">
                            <button
                              type="button"
                              className="button button-primary"
                              disabled={busy || editText.trim() === ''}
                              onClick={() => {
                                setEditingId(null)
                                void run(() =>
                                  sendToPatient(token, {
                                    proposal_id: proposal.id,
                                    text: editText,
                                  }),
                                ).then(() => setActiveTab('messages'))
                              }}
                            >
                              Send
                            </button>
                            <button
                              type="button"
                              className="button"
                              onClick={() => setEditingId(null)}
                            >
                              Cancel
                            </button>
                          </div>
                        </>
                      ) : (
                        <>
                          <p className="proposal-text">{proposal.text}</p>
                          <div className="row">
                            <button
                              type="button"
                              className="button button-primary"
                              disabled={busy}
                              onClick={() =>
                                void run(() =>
                                  sendToPatient(token, {
                                    proposal_id: proposal.id,
                                  }),
                                ).then(() => setActiveTab('messages'))
                              }
                            >
                              Ask {home.patient_name}
                            </button>
                            <button
                              type="button"
                              className="button"
                              disabled={busy}
                              onClick={() => {
                                setEditingId(proposal.id)
                                setEditText(proposal.text)
                              }}
                            >
                              Edit
                            </button>
                          </div>
                        </>
                      )}
                    </li>
                  ))}
                </ul>

                <h2>Or ask in your own words</h2>
                <textarea
                  value={ownText}
                  rows={3}
                  placeholder={`Something you would like to ask ${home.patient_name}`}
                  aria-label="Your own request"
                  onChange={(event) => setOwnText(event.target.value)}
                />
                <div className="row">
                  <button
                    type="button"
                    className="button button-primary"
                    disabled={busy || ownText.trim() === ''}
                    onClick={() => {
                      const text = ownText.trim()
                      setOwnText('')
                      void run(() => sendToPatient(token, { text })).then(() =>
                        setActiveTab('messages'),
                      )
                    }}
                  >
                    Send mine
                  </button>
                  <button
                    type="button"
                    className="button button-ghost"
                    disabled={busy}
                    onClick={() => void run(() => skipSuggestions(token))}
                  >
                    Not now
                  </button>
                </div>
              </section>
            ) : (
              <section className="stack text-center section-centered">
                <h1 className="text-center">Need a hand for something?</h1>
                <p className="quiet text-center">
                  We will suggest a few things you could ask someone who would
                  enjoy helping.
                </p>
                <div className="button-center-wrap">
                  <button
                    type="button"
                    className="button button-primary button-wide"
                    disabled={busy}
                    onClick={() => void run(() => suggest(token))}
                  >
                    {busy ? 'Looking…' : 'Who could help me?'}
                  </button>
                </div>
              </section>
            )}
          </>
        )}

        {/* Onglet 2 : Messagerie dynamique & multimédia */}
        {activeTab === 'messages' && (
          <ChatView
            role="helper"
            userName={home.user.name}
            onStartNewRequest={() => setActiveTab('request')}
          />
        )}

        {/* Onglet 3 : Mon profil */}
        {activeTab === 'profile' && (
          <ProfileView role="helper" name={home.user.name} onLeave={onLeave} />
        )}
      </main>
    </ScreenFrame>
  )
}

export default HelperScreen
