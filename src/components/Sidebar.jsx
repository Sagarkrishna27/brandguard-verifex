/*
  Sidebar.jsx
  ----------
  The dark navy navigation bar shown on the left of every page.
  It receives two pieces of information from App.jsx:
    - activePage: which page is currently open (highlights that button)
    - onNavigate: the function to call when a nav button is clicked
*/

// Each entry: the page "id" App.jsx understands, plus the label + icon shown.
const NAV_ITEMS = [
  { id: 'unified', label: 'One-Upload Review', icon: '✦' },
  { id: 'dashboard', label: 'Dashboard', icon: '▦' },
  { id: 'create', label: 'Create Poster', icon: '✦' },
  { id: 'generator', label: 'AI Poster Generator', icon: '✧' },
  { id: 'evaluate', label: 'Evaluate Poster', icon: '⌕' },
  { id: 'evidence', label: 'Claim Evidence', icon: '✓' },
  { id: 'video', label: 'Video Analysis', icon: '▶' },
  { id: 'tools', label: 'Ad Tools', icon: '⚒' },
  { id: 'passport', label: 'Trust Passport', icon: '◈' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
]

function Sidebar({ activePage, onNavigate }) {
  const visibleNavItems = NAV_ITEMS.filter((item) => item.id !== 'create')
  return (
    <aside className="sidebar">
      {/* Brand / logo area */}
      <div className="brand">
        <div className="brand-logo">B</div>
        <div>
          <h2>BrandGuard</h2>
          <p>Advertisement Trust Platform</p>
        </div>
      </div>

      {/* Navigation buttons. aria-current tells screen readers which page is open. */}
      <nav className="navigation" aria-label="Main navigation">
        {visibleNavItems.map((item) => (
          <button
            key={item.id}
            className={item.id === activePage ? 'nav-item active' : 'nav-item'}
            aria-current={item.id === activePage ? 'page' : undefined}
            onClick={() => onNavigate(item.id)}
          >
            <span className="nav-icon" aria-hidden="true">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <p>VERIFEX TEAM</p>
        <span>BrandGuard Project</span>
      </div>
    </aside>
  )
}

export default Sidebar
