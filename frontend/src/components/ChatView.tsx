import { useEffect, useRef, useState } from 'react'
import type {
  Attachment,
  PublicProfile,
  Role,
  Thread,
  TypingSignals,
} from '../api/client'
import { pickedImage, readAsDataUrl } from '../images'
import { markSeen, readSeen } from '../session'
import { useTypingSignals } from '../typing'
import PeerProfileModal from './PeerProfileModal'

const MAX_FILE_BYTES = 2_000_000
const QUICK_THANKS = 'Thank you, that really helped!'

type ChatViewProps = {
  role: Role
  userId: string
  threads: Thread[]
  busy: boolean
  // Fil ouvert, piloté par l'écran (pour ouvrir le fil qui vient de naître).
  openId: string | null
  onOpen: (threadId: string | null) => void
  // Renvoie vrai si le message est parti.
  onSend: (
    threadId: string,
    text: string,
    attachments: Attachment[],
    typing?: TypingSignals,
  ) => Promise<boolean>
  onDecline?: (threadId: string) => Promise<void>
  onStartNewRequest?: () => void
}

function clock(seconds: number): string {
  const date = new Date(seconds * 1000)
  const sameDay = date.toDateString() === new Date().toDateString()
  return sameDay
    ? date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

function peerName(thread: Thread): string {
  if (thread.peer) {
    return `${thread.peer.name} ${thread.peer.last_name}`.trim()
  }
  return 'The community'
}

function lastIncoming(thread: Thread): number {
  const incoming = thread.messages.filter((message) => !message.mine)
  return incoming.length ? incoming[incoming.length - 1].created_at : 0
}

// Où en est un fil, en deux ou trois mots, dans la liste.
function badge(thread: Thread, role: Role): string | null {
  if (thread.kind === 'need') {
    return thread.status === 'open' ? 'Waiting for a helper' : null
  }
  if (thread.status === 'to_answer') return 'Needs your answer'
  if (thread.status === 'on_its_way') return 'On its way'
  if (thread.thanked) return 'Service completed'
  return role === 'helper' ? 'Answered' : null
}

function avatar(
  profile: PublicProfile | null,
  name: string,
  className: string,
) {
  return profile?.avatar_url ? (
    <img src={profile.avatar_url} alt={name} className={className} />
  ) : (
    <div className="thread-avatar-fallback">{name.charAt(0).toUpperCase()}</div>
  )
}

// Les fils de la vraie app : une demande (avec sa réponse et le merci) ou un besoin de patient.
function ChatView({
  role,
  userId,
  threads,
  busy,
  openId,
  onOpen,
  onSend,
  onDecline,
  onStartNewRequest,
}: ChatViewProps) {
  // Fils déjà lus : relus à chaque rendu (l'écran se rafraîchit toutes les 4 secondes).
  const seen = readSeen(userId)
  const [viewingPeer, setViewingPeer] = useState<PublicProfile | null>(null)
  const [privateNotice, setPrivateNotice] = useState<string | null>(null)
  const [inputText, setInputText] = useState('')
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [fileError, setFileError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const activeThread = threads.find((thread) => thread.id === openId) ?? null
  const answering =
    role === 'patient' && activeThread?.status === 'to_answer'
      ? activeThread.id
      : null
  const { onInput, collect } = useTypingSignals(answering)

  // Un fil ouvert est lu, y compris les messages qui arrivent pendant qu'on le regarde.
  const activeLast = activeThread ? lastIncoming(activeThread) : 0
  useEffect(() => {
    if (!activeThread || activeLast === 0) return
    markSeen(userId, activeThread.id, activeLast)
  }, [activeThread, activeLast, userId])

  const messageCount = activeThread?.messages.length ?? 0
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messageCount, openId])

  function isUnread(thread: Thread): boolean {
    const last = lastIncoming(thread)
    return last > 0 && last > (seen[thread.id] ?? 0)
  }

  function openThread(thread: Thread | null) {
    setInputText('')
    setAttachments([])
    setFileError(null)
    setPrivateNotice(null)
    onOpen(thread ? thread.id : null)
  }

  function openPeer(thread: Thread) {
    if (!thread.peer) return
    if (!thread.peer.visible) {
      setPrivateNotice(
        `${thread.peer.name} chose to keep their profile private.`,
      )
      return
    }
    setPrivateNotice(null)
    setViewingPeer(thread.peer)
  }

  async function handleFiles(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''
    setFileError(null)
    for (const file of files.slice(0, 4 - attachments.length)) {
      try {
        const isImage = file.type.startsWith('image/')
        if (!isImage && file.size > MAX_FILE_BYTES) {
          setFileError(`${file.name} is too large (2 MB at most).`)
          continue
        }
        const url = isImage
          ? await pickedImage(file, 1200)
          : await readAsDataUrl(file)
        const type = isImage
          ? 'image'
          : file.type.startsWith('video/')
            ? 'video'
            : 'file'
        setAttachments((current) => [
          ...current,
          {
            type,
            name: file.name.slice(0, 120),
            url,
            size: `${Math.max(1, Math.round(file.size / 1024))} KB`,
          },
        ])
      } catch {
        setFileError(`${file.name} could not be read.`)
      }
    }
  }

  async function submit(text: string) {
    if (!activeThread) return
    if (!text.trim() && attachments.length === 0) return
    const typing = answering ? collect() : undefined
    const sent = await onSend(activeThread.id, text.trim(), attachments, typing)
    if (sent) {
      setInputText('')
      setAttachments([])
    }
  }

  const privateToast = privateNotice && (
    <div className="profile-private-toast" role="alert">
      <div className="flex-between">
        <div className="row-align-center-tight">
          <span className="private-toast-icon">🔒</span>
          <span className="font-small">{privateNotice}</span>
        </div>
        <button
          type="button"
          className="private-toast-close"
          onClick={() => setPrivateNotice(null)}
        >
          ✕
        </button>
      </div>
    </div>
  )

  // --- Vue 1 : la liste des fils ---
  if (!activeThread) {
    return (
      <section className="stack chat-list-section">
        <div className="chat-list-header">
          <h2>Messages</h2>
        </div>

        {threads.length === 0 ? (
          <div className="empty-state stack text-center">
            <p className="quiet">
              {role === 'patient'
                ? 'No requests yet. When someone in the community needs you, it shows up here.'
                : 'No conversations yet. Send a first request to start one.'}
            </p>
            {onStartNewRequest && (
              <button
                type="button"
                className="button button-primary button-wide"
                onClick={onStartNewRequest}
              >
                {role === 'patient' ? 'Ask the community' : 'New request'}
              </button>
            )}
          </div>
        ) : (
          <div className="threads-list" role="list">
            {threads.map((thread) => {
              const name = peerName(thread)
              const last = thread.messages[thread.messages.length - 1]
              const unreadThread = isUnread(thread)
              return (
                <div
                  key={thread.id}
                  role="listitem"
                  className={`thread-row-item ${unreadThread ? 'thread-row-unread' : ''}`}
                  onClick={() => openThread(thread)}
                >
                  <div
                    className="thread-avatar-wrapper thread-avatar-clickable"
                    title={
                      thread.peer?.visible === false
                        ? 'Private profile'
                        : 'View profile'
                    }
                    onClick={(event) => {
                      event.stopPropagation()
                      openPeer(thread)
                    }}
                  >
                    {avatar(thread.peer, name, 'thread-row-avatar')}
                    {unreadThread && <span className="thread-unread-dot" />}
                  </div>

                  <div className="thread-row-center">
                    <div className="thread-row-top">
                      <strong className="thread-row-name">{name}</strong>
                      <span className="thread-row-time">
                        {clock(thread.updated_at)}
                      </span>
                    </div>
                    <div className="thread-row-bottom">
                      <p className="thread-row-snippet">
                        {last.text || 'Shared a file'}
                      </p>
                      {badge(thread, role) && (
                        <span className="thread-status-badge">
                          {badge(thread, role)}
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
        {privateToast}
        {viewingPeer && (
          <PeerProfileModal
            profile={viewingPeer}
            onClose={() => setViewingPeer(null)}
          />
        )}
      </section>
    )
  }

  // --- Vue 2 : un fil ---
  const name = peerName(activeThread)
  const helperMustThank =
    role === 'helper' &&
    activeThread.kind === 'request' &&
    activeThread.status === 'answered' &&
    !activeThread.thanked
  const placeholder = answering
    ? 'Write your answer…'
    : helperMustThank
      ? `Tell ${activeThread.peer?.name ?? 'them'} what it brought you…`
      : 'Write a message...'

  return (
    <section className="stack chat-conversation-wrap">
      <div className="chat-conv-header">
        <button
          type="button"
          className="chat-back-btn"
          aria-label="Back to conversations"
          onClick={() => openThread(null)}
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
          onClick={() => openPeer(activeThread)}
          title="View profile"
          aria-label={`View ${name}'s profile`}
        >
          {avatar(activeThread.peer, name, 'chat-conv-avatar')}
          <div className="text-left">
            <div className="row-align-center-tight">
              <strong>{name}</strong>
            </div>
            <span className="quiet font-small block">
              {activeThread.peer
                ? activeThread.peer.role === 'patient'
                  ? 'Community member · Patient'
                  : 'Community helper'
                : 'Waiting for a helper'}
            </span>
          </div>
        </button>

        {helperMustThank && (
          <button
            type="button"
            className="button button-ghost button-small"
            disabled={busy}
            onClick={() => void submit(QUICK_THANKS)}
          >
            ✓ Helped me
          </button>
        )}
        {role === 'helper' &&
          activeThread.kind === 'request' &&
          activeThread.thanked &&
          onStartNewRequest && (
            <button
              type="button"
              className="button button-primary button-small"
              onClick={onStartNewRequest}
            >
              + New request
            </button>
          )}
      </div>

      {activeThread.kind === 'request' && activeThread.thanked && (
        <div className="chat-finished-notice">
          <span>
            {role === 'helper'
              ? '✓ You said thank you. The conversation stays open if you want to keep chatting.'
              : `✓ ${activeThread.peer?.name ?? 'Your helper'} said thank you. You helped someone today.`}
          </span>
        </div>
      )}

      <div className="chat-messages-scroll" ref={scrollRef}>
        {activeThread.messages.map((message) => (
          <div
            key={message.id}
            className={`chat-bubble-row ${message.mine ? 'chat-row-me' : 'chat-row-peer'}`}
          >
            <div
              className={`chat-bubble ${message.mine ? 'chat-bubble-me' : 'chat-bubble-peer'}`}
            >
              {message.kind === 'thanks' && (
                <span className="eyebrow">Thank you</span>
              )}
              {message.text && <p className="chat-text">{message.text}</p>}
              {message.attachments.length > 0 && (
                <div className="chat-attachments-grid">
                  {message.attachments.map((attachment, index) => (
                    <div key={index} className="chat-attachment-item">
                      {attachment.type === 'image' && (
                        <img
                          src={attachment.url}
                          alt={attachment.name}
                          className="chat-attached-media"
                        />
                      )}
                      {attachment.type === 'video' && (
                        <video
                          src={attachment.url}
                          controls
                          className="chat-attached-media"
                        />
                      )}
                      {attachment.type === 'file' && (
                        <a
                          className="chat-file-card"
                          href={attachment.url}
                          download={attachment.name}
                        >
                          <span>📄 {attachment.name}</span>
                          <small className="quiet">{attachment.size}</small>
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <span className="chat-time">{clock(message.created_at)}</span>
            </div>
          </div>
        ))}
      </div>

      {fileError && (
        <p className="error font-small" role="alert">
          {fileError}
        </p>
      )}

      {attachments.length > 0 && (
        <div className="chat-staged-attachments">
          {attachments.map((attachment, index) => (
            <div key={index} className="staged-pill">
              <span>
                {attachment.type === 'image'
                  ? '📷'
                  : attachment.type === 'video'
                    ? '🎥'
                    : '📄'}{' '}
                {attachment.name}
              </span>
              <button
                type="button"
                className="staged-remove"
                onClick={() =>
                  setAttachments((current) =>
                    current.filter((_, i) => i !== index),
                  )
                }
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {activeThread.can_write ? (
        <>
          <form
            className="chat-composer-form"
            onSubmit={(event) => {
              event.preventDefault()
              void submit(inputText)
            }}
          >
            <input
              type="file"
              ref={fileInputRef}
              multiple
              accept="image/*,video/*,.pdf,.doc,.docx,.txt"
              className="visually-hidden"
              onChange={(event) => void handleFiles(event)}
            />
            {!answering && (
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
            )}
            <input
              type="text"
              value={inputText}
              maxLength={1000}
              placeholder={placeholder}
              aria-label={answering ? 'Your answer' : 'Message'}
              className="chat-input-field"
              onInput={answering ? onInput : undefined}
              onChange={(event) => setInputText(event.target.value)}
            />
            <button
              type="submit"
              className="chat-send-btn"
              disabled={busy || (!inputText.trim() && attachments.length === 0)}
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
          {answering && onDecline && (
            <button
              type="button"
              className="link quiet"
              disabled={busy}
              onClick={() => void onDecline(activeThread.id)}
            >
              Not now
            </button>
          )}
        </>
      ) : (
        <p className="quiet font-small text-center" role="status">
          {activeThread.kind === 'need'
            ? 'Shared with the community. A helper will pick it up soon.'
            : `Sent. ${activeThread.peer?.name ?? 'They'} will answer when they can.`}
        </p>
      )}

      {privateToast}
      {viewingPeer && (
        <PeerProfileModal
          profile={viewingPeer}
          onClose={() => setViewingPeer(null)}
        />
      )}
    </section>
  )
}

export default ChatView
