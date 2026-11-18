/*
  Dashboard.jsx
  -------------
  The home page. It only shows HONEST numbers: everything is 0 because
  no reviews have happened yet. It also offers two entry points:
  creating a poster, and evaluating an existing one.
*/

function Dashboard({ onNavigate }) {
  return (
    <>
      {/* Top bar */}
      <header className="topbar">
        <div>
          <p className="welcome-text">WELCOME TO BRANDGUARD</p>
          <h1>Advertisement Dashboard</h1>
        </div>
        <div className="user-profile">
          <div className="user-avatar" aria-hidden="true">V</div>
          <span>Verifex Team</span>
        </div>
      </header>

      {/* Welcome banner */}
      <section className="hero-section">
        <div>
          <span className="hero-label">SMART ADVERTISEMENT REVIEW</span>
          <h2>Create with confidence.<br />Advertise with trust.</h2>
          <p>
            Create promotional posters or evaluate existing advertisements
            using evidence-based brand and claim checks. Human reviewers
            always make the final approval decision.
          </p>
        </div>
        <div className="hero-symbol" aria-hidden="true">✓</div>
      </section>

      {/* Stat cards — all zeros / clearly-labelled placeholders, no fake data */}
      <section className="stats-grid" aria-label="Review statistics">
        <div className="stat-card">
          <span className="stat-icon" aria-hidden="true">▣</span>
          <p>Total Reviews</p>
          <h2>0</h2>
          <span className="stat-note">No reviews performed yet</span>
        </div>
        <div className="stat-card">
          <span className="stat-icon" aria-hidden="true">◈</span>
          <p>Verified Ads</p>
          <h2>0</h2>
          <span className="stat-note">Awaiting first human review</span>
        </div>
        <div className="stat-card">
          <span className="stat-icon stat-icon-alert" aria-hidden="true">⚠</span>
          <p>Risk Alerts</p>
          <h2>0</h2>
          <span className="stat-note">No alerts recorded yet</span>
        </div>
      </section>

      {/* Two workflow cards */}
      <section className="workflow-section">
        <div className="section-heading">
          <h2>What would you like to do?</h2>
          <p>Run one advertisement through applicable checks, or open a focused review tool.</p>
        </div>

        <div className="workflow-grid">
          <div className="workflow-card">
            <div className="workflow-icon evaluate-icon" aria-hidden="true">✦</div>
            <h3>Review one upload</h3>
            <p>Upload one poster or video to run existing checks and collect their results in one report.</p>
            <button className="primary-button" onClick={() => onNavigate('unified')}>
              Start One-Upload Review <span aria-hidden="true">→</span>
            </button>
          </div>
          <div className="workflow-card">
            <div className="workflow-icon create-icon" aria-hidden="true">✦</div>
            <h3>Verify claims with evidence</h3>
            <p>
              Extract advertising claims and compare them with certificates,
              documents and expiry dates before approval.
            </p>
            <button className="primary-button" onClick={() => onNavigate('evidence')}>
              Check Evidence <span aria-hidden="true">→</span>
            </button>
          </div>

          <div className="workflow-card">
            <div className="workflow-icon evaluate-icon" aria-hidden="true">⌕</div>
            <h3>Evaluate an Existing Poster</h3>
            <p>
              Upload an existing advertisement image to review it.
              OCR, claim analysis and risk signals remain available for poster review.
            </p>
            <button className="secondary-button" onClick={() => onNavigate('evaluate')}>
              Evaluate Poster <span aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      </section>

      <footer className="footer">
        <p>BrandGuard © 2026 · Built by Team Verifex</p>
        <span>Human review is required for final approval.</span>
      </footer>
    </>
  )
}

export default Dashboard
