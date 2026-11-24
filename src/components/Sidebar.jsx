const NAV_GROUPS = [
  {
    label: 'WORKSPACE',
    items: [
      { id: 'dashboard', label: 'Overview', icon: '▦' },
      { id: 'unified', label: 'One-upload review', icon: '↗' },
    ],
  },
  {
    label: 'ANALYSIS',
    items: [
      { id: 'evaluate', label: 'Poster evaluation', icon: '⌕' },
      { id: 'evidence', label: 'Claim evidence', icon: '✓' },
      { id: 'video', label: 'Video analysis', icon: '▹' },
      { id: 'tools', label: 'Advertisement tools', icon: '⌘' },
    ],
  },
  {
    label: 'MANAGE',
    items: [
      { id: 'passport', label: 'Trust Passport', icon: '◇' },
      { id: 'generator', label: 'Poster generator', icon: '✳' },
      { id: 'settings', label: 'Settings', icon: '⚙' },
    ],
  },
]

function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-logo" aria-label="Verifex logo">
          <svg viewBox="0 0 48 48" width="30" height="30" role="img" aria-hidden="true">
            <defs>
              <linearGradient id="verifex-v-gradient" x1="7" y1="5" x2="40" y2="44" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#8B5CF6" />
                <stop offset="52%" stopColor="#3978F6" />
                <stop offset="100%" stopColor="#22D3EE" />
              </linearGradient>
            </defs>
            <path d="M7 9h9.2L24 29.2 31.8 9H41L26.5 42h-5L7 9Z" fill="url(#verifex-v-gradient)" />
            <path d="M29.5 9H41L33.4 26.2" fill="none" stroke="#DDFBFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" opacity=".9" />
          </svg>
        </div>
        <div className="brand-copy">
          <h2>BrandGuard</h2>
          <p>ADVERTISING INTEGRITY</p>
        </div>
      </div>

      <nav className="navigation" aria-label="Main navigation">
        {NAV_GROUPS.map((group) => (
          <div className="nav-group" key={group.label}>
            <p className="nav-group-label">{group.label}</p>
            {group.items.map((item) => (
              <button
                key={item.id}
                className={item.id === activePage ? 'nav-item active' : 'nav-item'}
                aria-current={item.id === activePage ? 'page' : undefined}
                onClick={() => onNavigate(item.id)}
              >
                <span className="nav-icon" aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <div className="sidebar-status-dot" />
        <div>
          <p>VERIFEX TEAM</p>
          <span>Human review stays in control</span>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
