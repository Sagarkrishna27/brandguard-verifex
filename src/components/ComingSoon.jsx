/*
  ComingSoon.jsx
  --------------
  An honest "not built yet" screen for sections that exist in the
  navigation but have no functionality yet (Trust Passport, Settings).
*/

function ComingSoon({ title, description, onNavigate }) {
  return (
    <>
      <header className="page-header">
        <button className="back-button" onClick={() => onNavigate('dashboard')}>
          ← Back to Dashboard
        </button>
        <h1>{title}</h1>
      </header>

      <section className="coming-soon-card">
        <span className="coming-soon-icon" aria-hidden="true">🔧</span>
        <h2>Coming Soon</h2>
        <p>{description}</p>
        <p className="coming-soon-note">
          This section has not been implemented yet, so no buttons or data are
          shown here to avoid pretending features exist.
        </p>
      </section>

      <footer className="footer">
        <p>BrandGuard © 2026 · Built by Team Verifex</p>
        <span>Human review is required for final approval.</span>
      </footer>
    </>
  )
}

export default ComingSoon
