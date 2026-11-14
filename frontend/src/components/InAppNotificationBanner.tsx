import { useEffect, useState } from 'react'
import Logo from './Logo'
import {
  type AppNotification,
  dismissNotification,
  readNotifications,
} from '../session'

function getInitialNotification(): {
  notif: AppNotification | null
  visible: boolean
} {
  const notifs = readNotifications()
  if (notifs.length > 0 && notifs[0].read === false) {
    return { notif: notifs[0], visible: true }
  }
  return { notif: null, visible: false }
}

function InAppNotificationBanner() {
  const [initial] = useState(getInitialNotification)
  const [currentNotif, setCurrentNotif] = useState<AppNotification | null>(
    initial.notif,
  )
  const [visible, setVisible] = useState(initial.visible)

  useEffect(() => {
    function handleNewNotif(e: Event) {
      const customEvent = e as CustomEvent<AppNotification>
      if (customEvent.detail) {
        setCurrentNotif(customEvent.detail)
        setVisible(true)
      }
    }

    function handleStorage(e: StorageEvent) {
      if (e.key === 'needed.notifications' && e.newValue) {
        try {
          const list = JSON.parse(e.newValue) as AppNotification[]
          if (list.length > 0) {
            setCurrentNotif(list[0])
            setVisible(true)
          }
        } catch {
          // ignore
        }
      }
    }

    window.addEventListener('needed:notification', handleNewNotif)
    window.addEventListener('storage', handleStorage)

    return () => {
      window.removeEventListener('needed:notification', handleNewNotif)
      window.removeEventListener('storage', handleStorage)
    }
  }, [])

  useEffect(() => {
    if (!visible) return
    const timer = setTimeout(() => {
      setVisible(false)
    }, 6000)
    return () => clearTimeout(timer)
  }, [visible, currentNotif])

  if (!visible || !currentNotif) return null

  function handleDismiss(e: React.MouseEvent) {
    e.stopPropagation()
    setVisible(false)
    if (currentNotif) {
      dismissNotification(currentNotif.id)
    }
  }

  function handleClick() {
    setVisible(false)
    if (currentNotif) {
      dismissNotification(currentNotif.id)
      if (currentNotif.linkHash) {
        window.location.hash = currentNotif.linkHash
      }
    }
  }

  return (
    <div
      className="inapp-notification-banner"
      role="alert"
      onClick={handleClick}
      style={{
        position: 'fixed',
        top: '12px',
        left: '16px',
        right: '16px',
        maxWidth: '430px',
        margin: '0 auto',
        zIndex: 9999,
        background: 'var(--surface-soft)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid var(--line)',
        borderRadius: '16px',
        padding: '12px 14px',
        boxShadow:
          '0 12px 28px -6px rgba(0, 0, 0, 0.2), 0 4px 12px rgba(0, 0, 0, 0.08)',
        cursor: 'pointer',
        animation: 'slideDownBanner 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Logo size={18} />
          <span
            style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: 'var(--cyan-deep)',
            }}
          >
            Needed
          </span>
          <span className="quiet" style={{ fontSize: '0.72rem' }}>
            · {currentNotif.timestamp}
          </span>
        </div>
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="Dismiss notification"
          style={{
            border: 'none',
            background: 'transparent',
            color: 'var(--muted)',
            cursor: 'pointer',
            fontSize: '13px',
            padding: '2px 6px',
            borderRadius: '4px',
            lineHeight: 1,
          }}
        >
          ✕
        </button>
      </div>

      <div style={{ paddingLeft: '2px', paddingRight: '6px' }}>
        <strong
          style={{
            fontSize: '0.88rem',
            display: 'block',
            color: 'var(--ink)',
            marginBottom: '2px',
          }}
        >
          {currentNotif.title}
        </strong>
        <p
          style={{
            margin: 0,
            fontSize: '0.82rem',
            lineHeight: 1.35,
            color: 'var(--muted)',
          }}
        >
          {currentNotif.body}
        </p>
      </div>
    </div>
  )
}

export default InAppNotificationBanner
