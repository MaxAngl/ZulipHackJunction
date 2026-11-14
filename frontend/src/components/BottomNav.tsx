export type TabType = 'request' | 'messages' | 'profile'

type BottomNavProps = {
  activeTab: TabType
  onSelectTab: (tab: TabType) => void
  unreadBadge?: number
}

// Bottom navigation bar, slightly translucent with cream glassmorphism.
// Three primary actions: New Request (left), Messages (middle), Profile (right).
function BottomNav({
  activeTab,
  onSelectTab,
  unreadBadge = 0,
}: BottomNavProps) {
  return (
    <nav className="bottom-nav" aria-label="Main navigation">
      <button
        type="button"
        className={`bottom-nav-item ${
          activeTab === 'request' ? 'bottom-nav-item-active' : ''
        }`}
        aria-selected={activeTab === 'request'}
        onClick={() => onSelectTab('request')}
      >
        <svg
          className="bottom-nav-icon"
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="16" />
          <line x1="8" y1="12" x2="16" y2="12" />
        </svg>
        <span className="bottom-nav-label">New Request</span>
      </button>

      <button
        type="button"
        className={`bottom-nav-item ${
          activeTab === 'messages' ? 'bottom-nav-item-active' : ''
        }`}
        aria-selected={activeTab === 'messages'}
        onClick={() => onSelectTab('messages')}
      >
        <div className="bottom-nav-icon-wrap">
          <svg
            className="bottom-nav-icon"
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          {unreadBadge > 0 && (
            <span className="bottom-nav-badge">{unreadBadge}</span>
          )}
        </div>
        <span className="bottom-nav-label">Messages</span>
      </button>

      <button
        type="button"
        className={`bottom-nav-item ${
          activeTab === 'profile' ? 'bottom-nav-item-active' : ''
        }`}
        aria-selected={activeTab === 'profile'}
        onClick={() => onSelectTab('profile')}
      >
        <svg
          className="bottom-nav-icon"
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
        <span className="bottom-nav-label">Profile</span>
      </button>
    </nav>
  )
}

export default BottomNav
