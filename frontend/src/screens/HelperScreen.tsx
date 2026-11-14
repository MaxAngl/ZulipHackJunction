import { useMemo, useState } from 'react'
import { getHelperHome, sendToPatient } from '../api/client'
import BottomNav, { type TabType } from '../components/BottomNav'
import ChatView from '../components/ChatView'
import ProfileView from '../components/ProfileView'
import {
  dismissPatientCommunityNeed,
  readPatientCommunityNeeds,
  readThreads,
  readUserProfile,
  saveThreads,
  SIMULATION_ACCOUNTS,
  type ConversationThread,
} from '../session'
import ScreenFrame from './ScreenFrame'
import { useHome } from './useHome'

type HelperScreenProps = {
  token: string
  onLeave: () => void
}

type CommunityPatient = {
  id: string
  firstName: string
  lastName: string
  name: string
  city: string
  avatar: string
  interests: string[]
  bio: string
}

const DEFAULT_PATIENT_PROPOSALS: Record<
  string,
  Array<{ id: string; text: string; topic: string }>
> = {
  'p-julien': [
    {
      id: 'prop-julien-1',
      text: 'Could you share your favorite indoor herb care tip for basil or mint?',
      topic: 'gardening',
    },
    {
      id: 'prop-julien-2',
      text: 'Would you recommend a calming book to read on a quiet Sunday afternoon?',
      topic: 'reading',
    },
    {
      id: 'prop-julien-3',
      text: 'Do you have an easy sourdough or quick bread recipe I could try?',
      topic: 'baking',
    },
  ],
  'p-sofia': [
    {
      id: 'prop-sofia-1',
      text: 'Could you share your favorite comfort soup recipe for chilly evenings?',
      topic: 'cooking',
    },
    {
      id: 'prop-sofia-2',
      text: 'What is a soothing jazz or acoustic album you love listening to?',
      topic: 'jazz',
    },
    {
      id: 'prop-sofia-3',
      text: 'Do you have a simple tip for capturing warm light in city photography?',
      topic: 'photography',
    },
  ],
  'p-lucas': [
    {
      id: 'prop-lucas-1',
      text: 'What is your favorite scenic and peaceful cycling route around Helsinki?',
      topic: 'cycling',
    },
    {
      id: 'prop-lucas-2',
      text: 'Could you recommend an easy beginner knitting stitch for a warm scarf?',
      topic: 'knitting',
    },
    {
      id: 'prop-lucas-3',
      text: 'Any must-pack essentials for a peaceful nature walk in the forest?',
      topic: 'hiking',
    },
  ],
}

// L'écran de l'aidant, dans la vraie app. Il consulte les profils patients,
// découvre leurs centres d'intérêt, et leur adresse une demande adaptée.
function HelperScreen({ token, onLeave }: HelperScreenProps) {
  const { home, error, busy, run } = useHome(token, getHelperHome, onLeave)
  const [activeTab, setActiveTab] = useState<TabType>('request')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [ownText, setOwnText] = useState('')
  const [patientNeeds, setPatientNeeds] = useState(() =>
    readPatientCommunityNeeds(),
  )

  const communityPatients = useMemo<CommunityPatient[]>(() => {
    const list: CommunityPatient[] = SIMULATION_ACCOUNTS.filter(
      (acc) => acc.role === 'patient',
    ).map((acc) => ({
      id: acc.id,
      firstName: acc.firstName,
      lastName: acc.lastName,
      name: `${acc.firstName} ${acc.lastName}`,
      city: acc.city,
      interests: acc.interests,
      bio: acc.bio,
      avatar: acc.avatarUrl ?? '/moomins/Muumipeikko2.jpg',
    }))

    const registered = readUserProfile('patient')
    if (registered && registered.firstName) {
      const regFullName =
        `${registered.firstName} ${registered.lastName}`.trim()
      if (
        !list.some((p) => p.name.toLowerCase() === regFullName.toLowerCase())
      ) {
        const regInterests =
          registered.interests && registered.interests.length > 0
            ? registered.interests
            : ['gardening', 'baking', 'reading']
        list.unshift({
          id: 'p-registered',
          firstName: registered.firstName,
          lastName: registered.lastName,
          name: regFullName,
          city: registered.city || 'Helsinki',
          interests: regInterests,
          bio: registered.bio || 'Patient member of the Needed community.',
          avatar: registered.avatarUrl ?? '/moomins/Muumipeikko2.jpg',
        })
      }
    }

    if (home?.patient_name) {
      const matchedName = home.patient_name
      const found = list.find(
        (p) =>
          p.name.toLowerCase() === matchedName.toLowerCase() ||
          matchedName.toLowerCase().includes(p.firstName.toLowerCase()),
      )
      if (!found) {
        list.unshift({
          id: `p-${matchedName.toLowerCase().replace(/\s+/g, '-')}`,
          firstName: matchedName.split(' ')[0] || matchedName,
          lastName: matchedName.split(' ')[1] || '',
          name: matchedName,
          city: 'Helsinki',
          interests: home.proposals
            .map((p) => p.patient_interest)
            .filter(Boolean),
          bio: 'Patient member of the Needed community.',
          avatar: '/moomins/Muumipeikko2.jpg',
        })
      }
    }

    return list
  }, [home?.patient_name, home?.proposals])

  const [selectedPatientId, setSelectedPatientId] = useState<string>(() => {
    if (home?.patient_name) {
      const match = communityPatients.find(
        (p) =>
          p.name.toLowerCase() === home.patient_name!.toLowerCase() ||
          home.patient_name!.toLowerCase().includes(p.firstName.toLowerCase()),
      )
      if (match) return match.id
    }
    return communityPatients[0]?.id ?? 'p-julien'
  })

  const selectedPatient = useMemo(() => {
    return (
      communityPatients.find((p) => p.id === selectedPatientId) ??
      communityPatients[0]
    )
  }, [communityPatients, selectedPatientId])

  const activeProposals = useMemo(() => {
    if (!selectedPatient) return []

    if (
      home?.patient_name &&
      (home.patient_name.toLowerCase() === selectedPatient.name.toLowerCase() ||
        home.patient_name
          .toLowerCase()
          .includes(selectedPatient.firstName.toLowerCase())) &&
      home.proposals.length > 0
    ) {
      return home.proposals.map((p) => ({
        id: p.id,
        text: p.text,
        topic: p.patient_interest,
        isBackend: true,
      }))
    }

    const preset = DEFAULT_PATIENT_PROPOSALS[selectedPatient.id]
    if (preset) {
      return preset.map((p) => ({ ...p, isBackend: false }))
    }

    const t1 = selectedPatient.interests[0] || 'daily life'
    const t2 = selectedPatient.interests[1] || 'wellness'
    const t3 = selectedPatient.interests[2] || 'relaxation'
    return [
      {
        id: `prop-${selectedPatient.id}-1`,
        text: `Could you share a helpful tip or experience about ${t1}?`,
        topic: t1,
        isBackend: false,
      },
      {
        id: `prop-${selectedPatient.id}-2`,
        text: `What do you enjoy most when spending time on ${t2}?`,
        topic: t2,
        isBackend: false,
      },
      {
        id: `prop-${selectedPatient.id}-3`,
        text: `Do you have a good recommendation related to ${t3}?`,
        topic: t3,
        isBackend: false,
      },
    ]
  }, [selectedPatient, home?.patient_name, home?.proposals])

  function recordSentMessage(
    peerName: string,
    peerAvatar: string | undefined,
    text: string,
  ) {
    const existingThreads = readThreads('helper')
    const threadId = `thread-patient-${peerName.toLowerCase().replace(/\s+/g, '-')}`
    const existingThread = existingThreads.find((t) => t.id === threadId)

    const timeStr = new Date().toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
    })

    const newMsg = {
      id: `msg-${Date.now()}`,
      senderRole: 'helper' as const,
      senderName: home?.user.name ?? 'Helper',
      text: text,
      timestamp: timeStr,
    }

    let updatedThreads: ConversationThread[]
    if (existingThread) {
      updatedThreads = existingThreads.map((t) =>
        t.id === threadId
          ? {
              ...t,
              lastMessageText: text,
              lastMessageTime: timeStr,
              isRead: true,
              messages: [...t.messages, newMsg],
              helperMessageCount: (t.helperMessageCount || 0) + 1,
            }
          : t,
      )
    } else {
      const newThread: ConversationThread = {
        id: threadId,
        peerName: peerName,
        peerRole: 'patient',
        peerAvatar: peerAvatar,
        lastMessageText: text,
        lastMessageTime: timeStr,
        isRead: true,
        isFinished: false,
        helperMessageCount: 1,
        messages: [newMsg],
      }
      updatedThreads = [newThread, ...existingThreads]
    }
    saveThreads('helper', updatedThreads)
  }

  async function handleSendProposal(proposal: {
    id: string
    text: string
    isBackend: boolean
  }) {
    if (!selectedPatient) return
    recordSentMessage(
      selectedPatient.name,
      selectedPatient.avatar,
      proposal.text,
    )

    if (proposal.isBackend) {
      await run(() =>
        sendToPatient(token, {
          proposal_id: proposal.id,
        }),
      )
    } else {
      await run(() =>
        sendToPatient(token, {
          text: proposal.text,
        }),
      )
    }
    setActiveTab('messages')
  }

  async function handleSendEdited(
    proposalId: string,
    editedContent: string,
    isBackend: boolean,
  ) {
    if (!selectedPatient) return
    const textToSend = editedContent.trim()
    if (!textToSend) return
    setEditingId(null)
    recordSentMessage(selectedPatient.name, selectedPatient.avatar, textToSend)

    if (isBackend) {
      await run(() =>
        sendToPatient(token, {
          proposal_id: proposalId,
          text: textToSend,
        }),
      )
    } else {
      await run(() =>
        sendToPatient(token, {
          text: textToSend,
        }),
      )
    }
    setActiveTab('messages')
  }

  async function handleSendOwn() {
    if (!selectedPatient) return
    const textToSend = ownText.trim()
    if (!textToSend) return
    setOwnText('')
    recordSentMessage(selectedPatient.name, selectedPatient.avatar, textToSend)

    await run(() =>
      sendToPatient(token, {
        text: textToSend,
      }),
    )
    setActiveTab('messages')
  }

  function handleAcceptPatientNeed(need: {
    id: string
    patientName: string
    patientAvatar?: string
    text: string
  }) {
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
          bio: 'Patient member of the Needed community.',
          interests: ['gardening', 'reading', 'nature'],
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

        {/* Tab 1 : Make a request */}
        {activeTab === 'request' && (
          <div className="helper-screen-content">
            {/* Direct patient community requests */}
            {patientNeeds.length > 0 && (
              <section className="stack patient-needs-banner-section">
                <div className="flex-between">
                  <p className="eyebrow">Direct patient requests</p>
                  <span className="badge-highlight">
                    {patientNeeds.length} active request(s)
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
                      <span className="patient-need-tag">
                        Community request
                      </span>
                    </div>

                    <p className="patient-need-body">« {need.text} »</p>

                    <div className="row">
                      <button
                        type="button"
                        className="button button-primary button-small"
                        onClick={() => handleAcceptPatientNeed(need)}
                      >
                        Reply to {need.patientName}
                      </button>
                      <button
                        type="button"
                        className="button button-ghost button-small"
                        onClick={() => handleDismissPatientNeed(need.id)}
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                ))}
              </section>
            )}

            {/* Profile Selector */}
            <section className="stack">
              <div className="helper-screen-header">
                <h1 className="helper-screen-title">Community Members</h1>
                <p className="quiet" style={{ margin: 0, fontSize: '0.88rem' }}>
                  Select a member to discover their hobbies and send a friendly
                  request.
                </p>
              </div>

              <div
                className="helper-patient-selector"
                role="tablist"
                aria-label="Select community member"
              >
                {communityPatients.map((patient) => {
                  const isSelected = patient.id === selectedPatient?.id
                  return (
                    <button
                      key={patient.id}
                      type="button"
                      role="tab"
                      aria-selected={isSelected}
                      className={`helper-patient-pill ${isSelected ? 'active' : ''}`}
                      onClick={() => {
                        setSelectedPatientId(patient.id)
                        setEditingId(null)
                      }}
                    >
                      <img
                        src={patient.avatar}
                        alt={patient.name}
                        className="helper-pill-avatar"
                      />
                      <span>{patient.firstName}</span>
                    </button>
                  )
                })}
              </div>
            </section>

            {/* Selected Profile Card & Hobbies */}
            {selectedPatient && (
              <section className="card-helper-patient">
                <div className="helper-patient-top">
                  <img
                    src={selectedPatient.avatar}
                    alt={selectedPatient.name}
                    className="helper-patient-avatar-large"
                  />
                  <div className="helper-patient-meta">
                    <h2 className="helper-patient-name">
                      {selectedPatient.name}
                    </h2>
                    <span className="helper-patient-city">
                      {selectedPatient.city} · Patient
                    </span>
                  </div>
                </div>

                {selectedPatient.bio && (
                  <p className="helper-patient-bio">
                    « {selectedPatient.bio} »
                  </p>
                )}

                {/* HOBBIES OF THE PERSON */}
                <div className="helper-hobbies-section">
                  <div className="helper-hobbies-label">
                    <span>Hobbies & Interests</span>
                    <span className="badge-highlight-subtle">
                      {selectedPatient.interests.length} topics
                    </span>
                  </div>
                  <div className="helper-hobbies-chips">
                    {selectedPatient.interests.map((hobby) => (
                      <span key={hobby} className="helper-hobby-chip">
                        {hobby}
                      </span>
                    ))}
                  </div>
                </div>
              </section>
            )}

            {/* AI Proposals Section */}
            {selectedPatient && (
              <section className="helper-ai-section">
                <div className="helper-ai-header">
                  <h2 className="helper-ai-title">
                    AI Suggestions to write to {selectedPatient.firstName}
                  </h2>
                  <span className="badge-ai-pill">Gemini AI</span>
                </div>
                <p className="quiet font-small" style={{ margin: 0 }}>
                  Crafted to match {selectedPatient.firstName}&apos;s hobbies
                  and wellness pace.
                </p>

                <div className="proposals" style={{ marginTop: '4px' }}>
                  {activeProposals.map((proposal) => (
                    <div key={proposal.id} className="helper-proposal-card">
                      {editingId === proposal.id ? (
                        <>
                          <textarea
                            value={editText}
                            rows={3}
                            aria-label="Edit request"
                            onChange={(e) => setEditText(e.target.value)}
                          />
                          <div className="row">
                            <button
                              type="button"
                              className="button button-primary"
                              disabled={busy || editText.trim() === ''}
                              onClick={() =>
                                void handleSendEdited(
                                  proposal.id,
                                  editText,
                                  proposal.isBackend,
                                )
                              }
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
                          <div className="helper-proposal-header">
                            <span className="helper-proposal-topic">
                              {proposal.topic}
                            </span>
                          </div>
                          <p className="helper-proposal-text">
                            {proposal.text}
                          </p>
                          <div className="row">
                            <button
                              type="button"
                              className="button button-primary"
                              disabled={busy}
                              onClick={() => void handleSendProposal(proposal)}
                            >
                              Ask {selectedPatient.firstName}
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
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Or Ask in your own words with CENTERED "Send mine" button */}
            {selectedPatient && (
              <section className="helper-own-section">
                <h2 className="helper-own-title">Or ask in your own words</h2>
                <textarea
                  value={ownText}
                  rows={3}
                  placeholder={`Something you would like to ask ${selectedPatient.firstName}...`}
                  aria-label="Your own request"
                  onChange={(e) => setOwnText(e.target.value)}
                />
                <div
                  className="button-center-wrap"
                  style={{ marginTop: '6px' }}
                >
                  <button
                    type="button"
                    className="button button-primary"
                    style={{ minWidth: '180px' }}
                    disabled={busy || ownText.trim() === ''}
                    onClick={() => void handleSendOwn()}
                  >
                    Send mine
                  </button>
                </div>
              </section>
            )}
          </div>
        )}

        {/* Tab 2 : Messages & Conversation */}
        {activeTab === 'messages' && (
          <ChatView
            role="helper"
            userName={home.user.name}
            onStartNewRequest={() => setActiveTab('request')}
          />
        )}

        {/* Tab 3 : My Profile */}
        {activeTab === 'profile' && (
          <ProfileView role="helper" name={home.user.name} onLeave={onLeave} />
        )}
      </main>
    </ScreenFrame>
  )
}

export default HelperScreen
