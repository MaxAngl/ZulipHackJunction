import { useEffect, useRef, useState } from 'react'
import {
  type AppUser,
  getHelperHome,
  type OpenNeed,
  postMessage,
  type SendRequest,
  sendToPatient,
  skipSuggestions,
  suggest,
  takeNeed,
} from '../api/client'
import BottomNav, { type TabType } from '../components/BottomNav'
import ChatView from '../components/ChatView'
import ProfileView from '../components/ProfileView'
import ScreenFrame from './ScreenFrame'
import { useHome } from './useHome'
import { useThreads } from './useThreads'

type HelperScreenProps = {
  token: string
  onLeave: () => void
}

function clock(seconds: number): string {
  return new Date(seconds * 1000).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

// L'écran de l'aidant. La boucle choisit la personne et écrit trois demandes à sa mesure ;
// l'aidant en envoie une, la modifie, écrit la sienne, ou en demande d'autres.
// Il peut aussi prendre le besoin qu'un patient a confié à la communauté.
function HelperScreen({ token, onLeave }: HelperScreenProps) {
  const { home, error, busy, run, refresh } = useHome(
    token,
    getHelperHome,
    onLeave,
  )
  const chat = useThreads(token, 'helper', onLeave)
  const [activeTab, setActiveTab] = useState<TabType>('request')
  const [openId, setOpenId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [ownText, setOwnText] = useState('')
  const [updatedUser, setUpdatedUser] = useState<AppUser | null>(null)
  const asked = useRef(false)

  // Rien à proposer en ouvrant l'onglet : on demande une fois à la boucle de chercher.
  const hasProposals = (home?.proposals.length ?? 0) > 0
  useEffect(() => {
    if (!home || activeTab !== 'request' || hasProposals || asked.current) {
      return
    }
    asked.current = true
    void run(() => suggest(token))
  }, [home, activeTab, hasProposals, run, token])

  async function sendRequest(body: SendRequest) {
    const next = await run(() => sendToPatient(token, body))
    if (!next) return
    setEditingId(null)
    setOwnText('')
    asked.current = false // au retour sur l'onglet, une nouvelle personne
    await chat.refresh()
    setOpenId(next.requests[0]?.id ?? null)
    setActiveTab('messages')
  }

  async function otherIdeas() {
    setEditingId(null)
    await run(async () => {
      await skipSuggestions(token)
      return suggest(token)
    })
  }

  async function pickUpNeed(need: OpenNeed) {
    const taken = await chat.run(() => takeNeed(token, need.id))
    void refresh()
    if (!taken) return
    setOpenId(need.id)
    setActiveTab('messages')
  }

  if (!home) {
    return (
      <ScreenFrame>
        <p className="quiet">{error ?? 'Loading…'}</p>
      </ScreenFrame>
    )
  }

  const me = updatedUser ?? home.user
  const threads = chat.threads ?? []
  const patient = home.patient
  const needs = home.needs ?? []
  const toThank = threads.filter(
    (thread) =>
      thread.kind === 'request' &&
      thread.status === 'answered' &&
      !thread.thanked,
  ).length

  return (
    <ScreenFrame
      name={me.first_name}
      avatarUrl={me.avatar_url ?? undefined}
      onLeave={onLeave}
      bottomNav={
        <BottomNav
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          unreadBadge={toThank}
        />
      }
    >
      <main className="stack">
        {(error || chat.error) && (
          <p className="error" role="alert">
            {error ?? chat.error}
          </p>
        )}

        {activeTab === 'request' && (
          <div className="helper-screen-content">
            {needs.length > 0 && (
              <section className="stack patient-needs-banner-section">
                <p className="eyebrow">Direct patient requests</p>
                {needs.map((need) => (
                  <div key={need.id} className="card-patient-need-banner">
                    <div className="patient-need-header">
                      <div className="row-align-center-tight">
                        {need.patient.avatar_url ? (
                          <img
                            src={need.patient.avatar_url}
                            alt={need.patient.name}
                            className="patient-need-avatar"
                          />
                        ) : (
                          <div className="thread-avatar-fallback">
                            {need.patient.name.charAt(0).toUpperCase()}
                          </div>
                        )}
                        <div>
                          <strong>{need.patient.name}</strong>
                          <span className="quiet font-small block">
                            {clock(need.created_at)}
                          </span>
                        </div>
                      </div>
                    </div>
                    <p className="patient-need-body">{need.text}</p>
                    <div className="row">
                      <button
                        type="button"
                        className="button button-primary button-small"
                        disabled={chat.busy}
                        onClick={() => void pickUpNeed(need)}
                      >
                        Reply to {need.patient.name}
                      </button>
                    </div>
                  </div>
                ))}
              </section>
            )}

            <section className="stack">
              <div className="helper-screen-header">
                <h1 className="helper-screen-title">Someone you could ask</h1>
              </div>
            </section>

            {!patient && (
              <section className="card-helper-patient stack text-center">
                <p className="quiet">
                  {busy
                    ? 'Finding someone who would enjoy your question…'
                    : 'Nobody to suggest right now.'}
                </p>
                {!busy && (
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => void run(() => suggest(token))}
                  >
                    Try again
                  </button>
                )}
              </section>
            )}

            {patient && (
              <section className="card-helper-patient">
                <div className="helper-patient-top">
                  {patient.avatar_url ? (
                    <img
                      src={patient.avatar_url}
                      alt={patient.name}
                      className="helper-patient-avatar-large"
                    />
                  ) : (
                    <div className="thread-avatar-fallback">
                      {patient.name.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <div className="helper-patient-meta">
                    <h2 className="helper-patient-name">
                      {`${patient.name} ${patient.last_name}`.trim()}
                    </h2>
                    {patient.city && (
                      <span className="helper-patient-city">
                        {patient.city}
                      </span>
                    )}
                  </div>
                </div>

                {patient.bio && (
                  <p className="helper-patient-bio">{patient.bio}</p>
                )}

                {patient.interests.length > 0 ? (
                  <div className="helper-hobbies-section">
                    <div className="helper-hobbies-chips">
                      {patient.interests.map((hobby) => (
                        <span key={hobby} className="helper-hobby-chip">
                          {hobby}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="quiet font-small">
                    {patient.name} keeps their profile private.
                  </p>
                )}
              </section>
            )}

            {patient && (
              <section className="helper-ai-section">
                <div className="helper-ai-header">
                  <h2 className="helper-ai-title">
                    Suggestions to write to {patient.name}
                  </h2>
                </div>

                <div className="proposals">
                  {home.proposals.map((proposal) => (
                    <div key={proposal.id} className="helper-proposal-card">
                      {editingId === proposal.id ? (
                        <>
                          <textarea
                            value={editText}
                            rows={3}
                            maxLength={600}
                            aria-label="Edit request"
                            onChange={(e) => setEditText(e.target.value)}
                          />
                          <div className="row">
                            <button
                              type="button"
                              className="button button-primary"
                              disabled={busy || editText.trim() === ''}
                              onClick={() =>
                                void sendRequest({
                                  proposal_id: proposal.id,
                                  text: editText.trim(),
                                })
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
                          <p className="helper-proposal-text">
                            {proposal.text}
                          </p>
                          <div className="row">
                            <button
                              type="button"
                              className="button button-primary"
                              disabled={busy}
                              onClick={() =>
                                void sendRequest({ proposal_id: proposal.id })
                              }
                            >
                              Ask {patient.name}
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
                <div className="button-center-wrap">
                  <button
                    type="button"
                    className="button button-ghost"
                    disabled={busy}
                    onClick={() => void otherIdeas()}
                  >
                    {busy ? 'Thinking…' : 'Other ideas'}
                  </button>
                </div>
              </section>
            )}

            {patient && (
              <section className="helper-own-section">
                <h2 className="helper-own-title">Or ask in your own words</h2>
                <textarea
                  value={ownText}
                  rows={3}
                  maxLength={600}
                  placeholder={`Something you would like to ask ${patient.name}...`}
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
                    onClick={() => void sendRequest({ text: ownText.trim() })}
                  >
                    Send mine
                  </button>
                </div>
              </section>
            )}
          </div>
        )}

        {activeTab === 'messages' && (
          <ChatView
            role="helper"
            userId={me.id}
            threads={threads}
            busy={chat.busy}
            openId={openId}
            onOpen={setOpenId}
            onSend={(threadId, text, attachments) =>
              chat.run(() => postMessage(token, threadId, text, attachments))
            }
            onStartNewRequest={() => {
              setOpenId(null)
              setActiveTab('request')
            }}
          />
        )}

        {activeTab === 'profile' && (
          <ProfileView
            user={me}
            token={token}
            threads={threads}
            onUpdated={setUpdatedUser}
            onLeave={onLeave}
          />
        )}
      </main>
    </ScreenFrame>
  )
}

export default HelperScreen
