import { type CSSProperties, useEffect, useState } from 'react'
import type { AccountRole, Thread } from '../api/client'
import { readUnlockedBadges, saveUnlockedBadges } from '../session'
import './BadgesPanel.css'

type BadgesPanelProps = {
  role: AccountRole
  userId: string
  threads: Thread[]
}

type Icon =
  | 'heart'
  | 'star'
  | 'medal'
  | 'trophy'
  | 'zap'
  | 'users'
  | 'calendar'
  | 'chat'
  | 'camera'
  | 'send'
  | 'sparkles'
  | 'smile'

type Badge = {
  key: string
  title: string
  hint: string
  icon: Icon
  value: number
  goal: number
}

const HOUR = 3600

// Ce que la personne a fait, lu dans ses fils : rien n'est compté à part.
function activity(threads: Thread[]) {
  const mine = threads.flatMap((thread) =>
    thread.messages.filter((message) => message.mine),
  )
  const days = (kind: string) =>
    new Set(
      mine
        .filter((message) => message.kind === kind)
        .map((message) => new Date(message.created_at * 1000).toDateString()),
    ).size
  const quickAnswers = threads.filter((thread) => {
    const request = thread.messages.find(
      (message) => message.kind === 'request',
    )
    const reply = thread.messages.find((message) => message.kind === 'reply')
    return request && reply && reply.created_at - request.created_at <= HOUR
  }).length
  return {
    requests: mine.filter((message) => message.kind === 'request').length,
    replies: mine.filter((message) => message.kind === 'reply').length,
    answersReceived: threads.filter((thread) =>
      thread.messages.some(
        (message) => message.kind === 'reply' && !message.mine,
      ),
    ).length,
    thanked: threads.filter((thread) => thread.thanked).length,
    chats: mine.filter((message) => message.kind === 'message').length,
    photos: mine.filter((message) => message.attachments.length > 0).length,
    people: new Set(
      threads
        .filter((thread) => thread.status === 'answered' && thread.peer)
        .map((thread) => thread.peer!.id),
    ).size,
    requestDays: days('request'),
    replyDays: days('reply'),
    quickAnswers,
  }
}

// Les badges du patient : c'est lui qui rend service.
function patientBadges(a: ReturnType<typeof activity>): Badge[] {
  return [
    {
      key: 'first-hand',
      title: 'First helping hand',
      hint: 'Answer your first request',
      icon: 'heart',
      value: a.replies,
      goal: 1,
    },
    {
      key: 'hat-trick',
      title: 'Hat-trick',
      hint: 'Answer 3 requests',
      icon: 'star',
      value: a.replies,
      goal: 3,
    },
    {
      key: 'pillar',
      title: 'Pillar of kindness',
      hint: 'Answer 5 requests',
      icon: 'medal',
      value: a.replies,
      goal: 5,
    },
    {
      key: 'champion',
      title: 'Community champion',
      hint: 'Answer 10 requests',
      icon: 'trophy',
      value: a.replies,
      goal: 10,
    },
    {
      key: 'warm-thanks',
      title: 'Warm thanks',
      hint: 'Get thanked for a reply',
      icon: 'smile',
      value: a.thanked,
      goal: 1,
    },
    {
      key: 'quick-spark',
      title: 'Quick spark',
      hint: 'Answer within an hour',
      icon: 'zap',
      value: a.quickAnswers,
      goal: 1,
    },
    {
      key: 'many-faces',
      title: 'Many faces',
      hint: 'Help 3 different people',
      icon: 'users',
      value: a.people,
      goal: 3,
    },
    {
      key: 'regular',
      title: 'Regular',
      hint: 'Answer on 3 different days',
      icon: 'calendar',
      value: a.replyDays,
      goal: 3,
    },
    {
      key: 'good-company',
      title: 'Good company',
      hint: 'Send 3 messages after a reply',
      icon: 'chat',
      value: a.chats,
      goal: 3,
    },
    {
      key: 'show-and-tell',
      title: 'Show and tell',
      hint: 'Share a photo',
      icon: 'camera',
      value: a.photos,
      goal: 1,
    },
  ]
}

// Les badges de l'aidant : demander, écouter, remercier.
function helperBadges(a: ReturnType<typeof activity>): Badge[] {
  return [
    {
      key: 'first-ask',
      title: 'First request',
      hint: 'Send your first request',
      icon: 'send',
      value: a.requests,
      goal: 1,
    },
    {
      key: 'curious',
      title: 'Curious mind',
      hint: 'Send 5 requests',
      icon: 'sparkles',
      value: a.requests,
      goal: 5,
    },
    {
      key: 'builder',
      title: 'Community builder',
      hint: 'Send 10 requests',
      icon: 'trophy',
      value: a.requests,
      goal: 10,
    },
    {
      key: 'first-answer',
      title: 'First answer',
      hint: 'Get your first reply',
      icon: 'chat',
      value: a.answersReceived,
      goal: 1,
    },
    {
      key: 'grateful',
      title: 'Grateful heart',
      hint: 'Say thank you 3 times',
      icon: 'heart',
      value: a.thanked,
      goal: 3,
    },
    {
      key: 'connector',
      title: 'Connector',
      hint: 'Hear back from 3 people',
      icon: 'users',
      value: a.people,
      goal: 3,
    },
    {
      key: 'regular',
      title: 'Regular',
      hint: 'Ask on 3 different days',
      icon: 'calendar',
      value: a.requestDays,
      goal: 3,
    },
    {
      key: 'good-company',
      title: 'Good company',
      hint: 'Send 3 messages after a reply',
      icon: 'smile',
      value: a.chats,
      goal: 3,
    },
    {
      key: 'show-and-tell',
      title: 'Show and tell',
      hint: 'Share a photo',
      icon: 'camera',
      value: a.photos,
      goal: 1,
    },
  ]
}

function icon(name: Icon) {
  const paths: Record<Icon, React.ReactNode> = {
    heart: (
      <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />
    ),
    star: (
      <polygon points="12 3 14.6 9 21 9.3 16 13.4 17.6 20 12 16.5 6.4 20 8 13.4 3 9.3 9.4 9" />
    ),
    medal: (
      <>
        <circle cx="12" cy="15" r="5" />
        <path d="M8.5 3h7l-2 7h-3z" />
      </>
    ),
    trophy: (
      <>
        <path d="M8 4h8v5a4 4 0 0 1-8 0z" />
        <path d="M8 6H5a2.5 2.5 0 0 0 3 4" />
        <path d="M16 6h3a2.5 2.5 0 0 1-3 4" />
        <path d="M12 13v4M8 20h8" />
      </>
    ),
    zap: <polygon points="13 2 4 14 11 14 10 22 20 9 13 9" />,
    users: (
      <>
        <circle cx="9" cy="8" r="3" />
        <path d="M3 20a6 6 0 0 1 12 0" />
        <circle cx="17" cy="9" r="2.5" />
        <path d="M15.5 14.2A5 5 0 0 1 21 19" />
      </>
    ),
    calendar: (
      <>
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M3 10h18M8 3v4M16 3v4" />
      </>
    ),
    chat: <path d="M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z" />,
    camera: (
      <>
        <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
        <circle cx="12" cy="13.5" r="3.5" />
      </>
    ),
    send: (
      <>
        <path d="M22 2 11 13" />
        <polygon points="22 2 15 22 11 13 2 9" />
      </>
    ),
    sparkles: (
      <>
        <path d="M11 3l1.8 5.2L18 10l-5.2 1.8L11 17l-1.8-5.2L4 10l5.2-1.8z" />
        <path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z" />
      </>
    ),
    smile: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M8.5 14a4 4 0 0 0 7 0M9 9.5h.01M15 9.5h.01" />
      </>
    ),
  }
  return (
    <svg
      viewBox="0 0 24 24"
      width="26"
      height="26"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  )
}

// Les badges du profil, calculés sur l'activité réelle. Un badge débloqué depuis la dernière
// visite du profil a droit à une petite fête, une seule fois (mémoire du navigateur).
function BadgesPanel({ role, userId, threads }: BadgesPanelProps) {
  const counts = activity(threads)
  const badges =
    role === 'patient' ? patientBadges(counts) : helperBadges(counts)
  const unlocked = badges.filter((badge) => badge.value >= badge.goal)
  const [known] = useState(() => readUnlockedBadges(userId))
  const unlockedKeys = unlocked.map((badge) => badge.key).join(',')

  useEffect(() => {
    if (unlockedKeys) saveUnlockedBadges(userId, unlockedKeys.split(','))
  }, [userId, unlockedKeys])

  const share = badges.length ? unlocked.length / badges.length : 0

  return (
    <div className="badges-panel">
      <div className="badges-head">
        <span className="eyebrow">Milestones & Badges</span>
        <span className="badges-count">
          {unlocked.length}
          <small>/{badges.length}</small>
        </span>
      </div>
      <div
        className="badges-meter"
        role="progressbar"
        aria-valuenow={unlocked.length}
        aria-valuemin={0}
        aria-valuemax={badges.length}
        aria-label="Badges unlocked"
      >
        <span style={{ '--share': share } as CSSProperties} />
      </div>

      <ul className="badges-list">
        {badges.map((badge, index) => {
          const done = badge.value >= badge.goal
          const fresh = done && !known.includes(badge.key)
          const progress = Math.min(1, badge.value / badge.goal)
          return (
            <li
              key={badge.key}
              className={`badge ${done ? 'badge-done' : 'badge-todo'} ${fresh ? 'badge-fresh' : ''}`}
              style={{ '--i': index, '--p': progress } as CSSProperties}
            >
              <div className="badge-tile">
                {icon(badge.icon)}
                {done && <span className="badge-shine" aria-hidden="true" />}
                {fresh && (
                  <span className="badge-burst" aria-hidden="true">
                    {Array.from({ length: 8 }, (_, ray) => (
                      <i key={ray} style={{ '--r': ray } as CSSProperties} />
                    ))}
                  </span>
                )}
              </div>
              <strong className="badge-name">{badge.title}</strong>
              <span className="badge-hint">{badge.hint}</span>
              {fresh && <span className="badge-tag">New!</span>}
              {!done && (
                <span className="badge-progress">
                  {badge.value} / {badge.goal}
                </span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default BadgesPanel
