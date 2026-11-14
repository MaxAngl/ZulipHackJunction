import { useRef, useState } from 'react'
import type { Role } from '../api/client'
import {
  type ConversationThread,
  type MessageAttachment,
  readThreads,
  saveThreads,
} from '../session'

type ChatViewProps = {
  role: Role
  userName: string
  onStartNewRequest?: () => void
}

function ChatView({ role, userName, onStartNewRequest }: ChatViewProps) {
  const [threads, setThreads] = useState<ConversationThread[]>(() =>
    readThreads(role),
  )
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [viewingPeerProfile, setViewingPeerProfile] =
    useState<ConversationThread | null>(null)
  const [privateProfileNotice, setPrivateProfileNotice] = useState<
    string | null
  >(null)
  const [inputText, setInputText] = useState('')
  const [attachments, setAttachments] = useState<MessageAttachment[]>([])
  const [limitWarning, setLimitWarning] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const activeThread = threads.find((t) => t.id === activeThreadId) ?? null

  function selectThread(t: ConversationThread) {
    setActiveThreadId(t.id)
    setLimitWarning(null)
    setPrivateProfileNotice(null)
    if (!t.isRead) {
      const updated = threads.map((item) =>
        item.id === t.id ? { ...item, isRead: true } : item,
      )
      setThreads(updated)
      saveThreads(role, updated)
    }
  }

  function handleOpenPeerProfile(t: ConversationThread) {
    if (t.peerProfile && t.peerProfile.allowProfileView === false) {
      setPrivateProfileNotice(
        `${t.peerName} a choisi de ne pas rendre son profil consultable.`,
      )
      return
    }
    setPrivateProfileNotice(null)
    setViewingPeerProfile(t)
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files || files.length === 0) return

    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const reader = new FileReader()
      const isImg = file.type.startsWith('image/')
      const isVid = file.type.startsWith('video/')
      const type: 'image' | 'video' | 'file' = isImg
        ? 'image'
        : isVid
          ? 'video'
          : 'file'

      reader.onload = () => {
        if (typeof reader.result === 'string') {
          const newAtt: MessageAttachment = {
            type,
            name: file.name,
            url: reader.result,
            size: `${(file.size / 1024).toFixed(0)} Ko`,
          }
          setAttachments((prev) => [...prev, newAtt])
        }
      }
      reader.readAsDataURL(file)
    }
    e.target.value = ''
  }

  function handleSendMessage(e: React.FormEvent) {
    e.preventDefault()
    if (!activeThread) return
    if (!inputText.trim() && attachments.length === 0) return

    // Check anti-spam limit for helper (max 5 messages per cycle)
    if (role === 'helper' && activeThread.helperMessageCount >= 5) {
      setLimitWarning(
        'Limit of 5 messages reached to prevent spam. Please wait for your peer to reply or start a new request cycle.',
      )
      return
    }

    const timeStr = new Date().toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })

    const newMsg = {
      id: `msg-${Date.now()}`,
      senderRole: role,
      senderName: userName || (role === 'helper' ? 'Helper' : 'Patient'),
      text: inputText.trim(),
      timestamp: timeStr,
      attachments: attachments.length > 0 ? attachments : undefined,
    }

    const updatedThreads = threads.map((th) => {
      if (th.id === activeThread.id) {
        return {
          ...th,
          lastMessageText: newMsg.text || 'Shared file',
          lastMessageTime: timeStr,
          messages: [...th.messages, newMsg],
          helperMessageCount:
            role === 'helper'
              ? th.helperMessageCount + 1
              : th.helperMessageCount,
        }
      }
      return th
    })

    setThreads(updatedThreads)
    saveThreads(role, updatedThreads)
    setInputText('')
    setAttachments([])
    setLimitWarning(null)
  }

  function handleMarkFinished() {
    if (!activeThread) return
    const updatedThreads = threads.map((th) => {
      if (th.id === activeThread.id) {
        return {
          ...th,
          isFinished: true,
        }
      }
      return th
    })
    setThreads(updatedThreads)
    saveThreads(role, updatedThreads)
  }

  function handleRestartHelp() {
    if (!activeThread) return
    const updatedThreads = threads.map((th) => {
      if (th.id === activeThread.id) {
        return {
          ...th,
          isFinished: false,
          helperMessageCount: 0, // Nouveau cycle
        }
      }
      return th
    })
    setThreads(updatedThreads)
    saveThreads(role, updatedThreads)
    if (onStartNewRequest) {
      onStartNewRequest()
    }
  }

  // --- VIEW 1 : Conversations List ---
  if (!activeThread) {
    return (
      <section className="stack chat-list-section">
        <div className="chat-list-header">
          <h2>Messages</h2>
          <span className="quiet font-small">
            {threads.filter((t) => !t.isRead).length} unread
          </span>
        </div>

        {threads.length === 0 ? (
          <div className="empty-state stack text-center">
            <p className="quiet">No active conversations yet.</p>
            {onStartNewRequest && (
              <button
                type="button"
                className="button button-primary button-wide"
                onClick={onStartNewRequest}
              >
                New Request
              </button>
            )}
          </div>
        ) : (
          <div className="threads-list" role="list">
            {threads.map((t) => {
              const avatar =
                t.peerAvatar ??
                (t.peerRole === 'patient'
                  ? '/moomins/Muumipeikko2.jpg'
                  : undefined)

              return (
                <div
                  key={t.id}
                  role="listitem"
                  className={`thread-row-item ${!t.isRead ? 'thread-row-unread' : ''}`}
                  onClick={() => selectThread(t)}
                >
                  <div
                    className="thread-avatar-wrapper thread-avatar-clickable"
                    title={
                      t.peerProfile?.allowProfileView === false
                        ? 'Private profile'
                        : 'View profile'
                    }
                    onClick={(e) => {
                      e.stopPropagation()
                      handleOpenPeerProfile(t)
                    }}
                  >
                    {avatar ? (
                      <img
                        src={avatar}
                        alt={t.peerName}
                        className="thread-row-avatar"
                      />
                    ) : (
                      <div className="thread-avatar-fallback">
                        {t.peerName.charAt(0).toUpperCase()}
                      </div>
                    )}
                    {!t.isRead && <span className="thread-unread-dot" />}
                  </div>

                  <div className="thread-row-center">
                    <div className="thread-row-top">
                      <strong className="thread-row-name">{t.peerName}</strong>
                      <span className="thread-row-time">
                        {t.lastMessageTime}
                      </span>
                    </div>
                    <div className="thread-row-bottom">
                      <p className="thread-row-snippet">{t.lastMessageText}</p>
                      {t.isFinished && (
                        <span className="thread-status-badge">
                          Service completed
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="thread-row-arrow">
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>
    )
  }

  // --- VIEW 2 : Active multimedia conversation ---
  const currentAvatar =
    activeThread.peerAvatar ??
    (activeThread.peerRole === 'patient'
      ? '/moomins/Muumipeikko2.jpg'
      : undefined)

  return (
    <section className="stack chat-conversation-wrap">
      {/* Header */}
      <div className="chat-conv-header">
        <button
          type="button"
          className="chat-back-btn"
          aria-label="Back to conversations"
          onClick={() => setActiveThreadId(null)}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        <button
          type="button"
          className="chat-conv-peer chat-conv-peer-clickable"
          onClick={() => handleOpenPeerProfile(activeThread)}
          title="View profile"
          aria-label={`View ${activeThread.peerName}'s profile`}
        >
          {currentAvatar ? (
            <img
              src={currentAvatar}
              alt={activeThread.peerName}
              className="chat-conv-avatar"
            />
          ) : (
            <div className="thread-avatar-fallback">
              {activeThread.peerName.charAt(0).toUpperCase()}
            </div>
          )}
          <div className="text-left">
            <div className="row-align-center-tight">
              <strong>{activeThread.peerName}</strong>
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="peer-info-icon"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
            </div>
            <span className="quiet font-small block">
              {activeThread.peerRole === 'patient'
                ? 'Remission Patient'
                : 'Volunteer Helper'}
            </span>
          </div>
        </button>

        {/* Action to finish or restart help */}
        {role === 'helper' && (
          <div>
            {!activeThread.isFinished ? (
              <button
                type="button"
                className="button button-ghost button-small"
                onClick={handleMarkFinished}
              >
                ✓ Helped me
              </button>
            ) : (
              <button
                type="button"
                className="button button-primary button-small"
                onClick={handleRestartHelp}
              >
                + New request
              </button>
            )}
          </div>
        )}
      </div>

      {activeThread.isFinished && (
        <div className="chat-finished-notice">
          <span>
            ✓ You confirmed the help received. The conversation remains open if
            you wish to continue chatting or send a new request.
          </span>
        </div>
      )}

      {/* Flux de messages */}
      <div className="chat-messages-scroll">
        {activeThread.messages.map((m) => {
          const isMe = m.senderRole === role
          return (
            <div
              key={m.id}
              className={`chat-bubble-row ${isMe ? 'chat-row-me' : 'chat-row-peer'}`}
            >
              <div
                className={`chat-bubble ${isMe ? 'chat-bubble-me' : 'chat-bubble-peer'}`}
              >
                {m.text && <p className="chat-text">{m.text}</p>}

                {m.attachments && m.attachments.length > 0 && (
                  <div className="chat-attachments-grid">
                    {m.attachments.map((att, idx) => (
                      <div key={idx} className="chat-attachment-item">
                        {att.type === 'image' && (
                          <img
                            src={att.url}
                            alt={att.name}
                            className="chat-attached-media"
                          />
                        )}
                        {att.type === 'video' && (
                          <video
                            src={att.url}
                            controls
                            className="chat-attached-media"
                          />
                        )}
                        {att.type === 'file' && (
                          <div className="chat-file-card">
                            <span>📄 {att.name}</span>
                            <small className="quiet">{att.size}</small>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                <span className="chat-time">{m.timestamp}</span>
              </div>
            </div>
          )
        })}
      </div>

      {limitWarning && (
        <p className="error font-small" role="alert">
          {limitWarning}
        </p>
      )}

      {/* Prévisualisation des pièces jointes en attente */}
      {attachments.length > 0 && (
        <div className="chat-staged-attachments">
          {attachments.map((att, index) => (
            <div key={index} className="staged-pill">
              <span>
                {att.type === 'image'
                  ? '📷'
                  : att.type === 'video'
                    ? '🎥'
                    : '📄'}{' '}
                {att.name}
              </span>
              <button
                type="button"
                className="staged-remove"
                onClick={() =>
                  setAttachments((prev) => prev.filter((_, i) => i !== index))
                }
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Boîte de saisie libre et actions multimédias */}
      <form onSubmit={handleSendMessage} className="chat-composer-form">
        <input
          type="file"
          ref={fileInputRef}
          multiple
          accept="image/*,video/*,.pdf,.doc,.docx,.txt"
          className="visually-hidden"
          onChange={handleFileUpload}
        />

        <button
          type="button"
          className="chat-attach-btn"
          title="Attach photo, video, or file"
          aria-label="Attach file"
          onClick={() => fileInputRef.current?.click()}
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
          </svg>
        </button>

        <input
          type="text"
          value={inputText}
          placeholder="Write a message..."
          className="chat-input-field"
          onChange={(e) => setInputText(e.target.value)}
        />

        <button
          type="submit"
          className="chat-send-btn"
          disabled={!inputText.trim() && attachments.length === 0}
          aria-label="Send"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </form>

      {/* Warning when profile is private */}
      {privateProfileNotice && (
        <div className="profile-private-toast" role="alert">
          <div className="flex-between">
            <div className="row-align-center-tight">
              <span className="private-toast-icon">🔒</span>
              <span className="font-small">{privateProfileNotice}</span>
            </div>
            <button
              type="button"
              className="private-toast-close"
              onClick={() => setPrivateProfileNotice(null)}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* --- PEER PROFILE MODAL --- */}
      {viewingPeerProfile && (
        <div
          className="peer-profile-modal-backdrop"
          onClick={() => setViewingPeerProfile(null)}
        >
          <div
            className="peer-profile-modal-card"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="peer-profile-title"
          >
            <div className="peer-profile-modal-header">
              <span className="eyebrow">Member Profile</span>
              <button
                type="button"
                className="peer-profile-modal-close"
                onClick={() => setViewingPeerProfile(null)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div className="peer-profile-content-scroll stack">
              {/* Identity hero */}
              <div className="peer-profile-hero">
                <div className="peer-avatar-xlarge-wrap">
                  {viewingPeerProfile.peerProfile?.avatarUrl ||
                  viewingPeerProfile.peerAvatar ? (
                    <img
                      src={
                        viewingPeerProfile.peerProfile?.avatarUrl ??
                        viewingPeerProfile.peerAvatar
                      }
                      alt={viewingPeerProfile.peerName}
                      className="peer-avatar-xlarge"
                    />
                  ) : (
                    <div className="peer-avatar-xlarge-fallback">
                      {viewingPeerProfile.peerName.charAt(0).toUpperCase()}
                    </div>
                  )}
                </div>

                <h2 id="peer-profile-title" className="peer-profile-fullname">
                  {viewingPeerProfile.peerProfile
                    ? `${viewingPeerProfile.peerProfile.firstName} ${viewingPeerProfile.peerProfile.lastName}`
                    : viewingPeerProfile.peerName}
                </h2>

                <div className="peer-profile-sub-badges">
                  <span className="peer-role-tag">
                    {viewingPeerProfile.peerRole === 'patient'
                      ? 'Remission Patient'
                      : 'Volunteer Helper'}
                  </span>
                </div>
              </div>

              {/* Interests & Bio */}
              <div className="peer-profile-section stack-compact">
                <span className="eyebrow">Interests & Bio</span>
                <p className="peer-bio-text">
                  {viewingPeerProfile.peerProfile?.bio ||
                    (viewingPeerProfile.peerRole === 'patient'
                      ? 'Passionate about sourdough baking, nature, and Nordic gardening.'
                      : 'Dedicated volunteer, passionate about analog photography and urban cycling.')}
                </p>

                {/* Chips */}
                <div className="peer-interests-chips">
                  {(
                    viewingPeerProfile.peerProfile?.interests ?? [
                      'baking',
                      'gardening',
                      'jazz',
                      'reading',
                    ]
                  ).map((tag) => (
                    <span key={tag} className="peer-interest-pill">
                      #{tag}
                    </span>
                  ))}
                </div>
              </div>

              {/* Up to 3 passion photos */}
              <div className="peer-profile-section stack-compact">
                <span className="eyebrow">
                  Passion photos (
                  {viewingPeerProfile.peerProfile?.passionPhotos?.length ?? 2}
                  /3)
                </span>
                <div className="passion-photos-grid">
                  {(
                    viewingPeerProfile.peerProfile?.passionPhotos ?? [
                      '/moomins/Muumipeikko2.jpg',
                      '/moomins/Characters-04-2.svg',
                    ]
                  ).map((pic, idx) => (
                    <div key={idx} className="passion-photo-card">
                      <img
                        src={pic}
                        alt={`Passion ${idx + 1}`}
                        className="passion-photo-thumb"
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* Back button */}
              <button
                type="button"
                className="button button-primary button-wide mt-2"
                onClick={() => setViewingPeerProfile(null)}
              >
                Back to conversation
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

export default ChatView
