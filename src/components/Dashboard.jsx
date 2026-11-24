function Dashboard({ onNavigate }) {
  return (
    <>
      <header className="topbar">
        <div>
          <p className="welcome-text">BRANDGUARD WORKSPACE</p>
          <h1>Overview</h1>
          <p className="dashboard-subtitle">Review advertising claims, supporting evidence and creative assets in one place.</p>
        </div>
        <div className="user-profile">
          <div className="user-avatar" aria-hidden="true">V</div>
          <span>Verifex Team</span>
        </div>
      </header>

      <section className="hero-section">
        <div className="hero-copy">
          <span className="hero-label">ADVERTISING INTEGRITY WORKSPACE</span>
          <h2>Make every claim<br />ready for scrutiny.</h2>
          <p>
            Review posters and videos, examine claims against supporting evidence,
            and prepare clearer advertisements. People remain responsible for final decisions.
          </p>
          <button className="hero-action" onClick={() => onNavigate('unified')}>
            Start an advertisement review <span aria-hidden="true">→</span>
          </button>
        </div>
        <div className="hero-symbol hero-brand-lockup" aria-label="VERIFEX — Innovate, Verify, Trust. Trust by Design.">
          <div className="hero-brand-main">
            <svg className="hero-symbol-logo" viewBox="0 0 100 100" role="img" aria-label="VERIFEX gradient V emblem">
              <defs>
                <linearGradient id="hero-verifex-gradient" x1="12" y1="8" x2="88" y2="92" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#8B5CF6" />
                  <stop offset="52%" stopColor="#3978F6" />
                  <stop offset="100%" stopColor="#22D3EE" />
                </linearGradient>
              </defs>
              <path d="M12 17h19l19 49 19-49h19L57 88h-14L12 17Z" fill="url(#hero-verifex-gradient)" />
            </svg>
            <div className="hero-brand-type">
              <strong>VERIFEX</strong>
              <span>INNOVATE <i>•</i> VERIFY <i>•</i> TRUST</span>
            </div>
          </div>
          <span className="hero-symbol-caption">TRUST BY DESIGN</span>
        </div>
      </section>

      <section className="workflow-section judge-access-section" aria-label="Judge access">
        <div className="section-heading">
          <h2>Judge access</h2>
          <p>No account, registration or demo credentials are required. The public evaluation workspace opens directly.</p>
        </div>
        <div className="workflow-grid">
          <article className="workflow-card workflow-card-featured">
            <div className="workflow-topline"><span className="workflow-number">START</span><span className="workflow-category">RECOMMENDED</span></div>
            <h3>Test the complete product</h3>
            <p>Upload a poster or video and review the consolidated analysis, module statuses and final report.</p>
            <button className="primary-button" onClick={() => onNavigate('unified')}>
              Open one-upload review <span aria-hidden="true">→</span>
            </button>
          </article>
          <article className="workflow-card">
            <div className="workflow-topline"><span className="workflow-number">NEXT</span><span className="workflow-category">CLAIM EVIDENCE</span></div>
            <h3>Explore evidence review</h3>
            <p>Submit advertisement text and supporting documents to inspect claim-to-evidence matching and review states.</p>
            <button className="secondary-button" onClick={() => onNavigate('evidence')}>
              Open evidence review <span aria-hidden="true">→</span>
            </button>
          </article>
          <article className="workflow-card">
            <div className="workflow-topline"><span className="workflow-number">EXPLORE</span><span className="workflow-category">TRUST PASSPORT</span></div>
            <h3>Inspect verification records</h3>
            <p>Explore public Trust Passport examples and see how a report's review status is presented.</p>
            <button className="secondary-button" onClick={() => onNavigate('passport')}>
              Open Trust Passport <span aria-hidden="true">→</span>
            </button>
          </article>
        </div>
        <p className="page-intro">Public submissions remain marked NEEDS REVIEW until an authorized reviewer updates them. Private reviewer credentials are not displayed on this page.</p>
      </section>

      <section className="dashboard-section" aria-label="Workspace activity">
        <div className="section-heading dashboard-section-heading">
          <div>
            <h2>Workspace activity</h2>
            <p>Live totals from this workspace. No activity has been recorded yet.</p>
          </div>
          <span className="activity-status"><span /> No activity yet</span>
        </div>
        <div className="stats-grid">
          <article className="stat-card">
            <span className="stat-label">TOTAL REVIEWS</span>
            <div className="stat-value-row"><h2>0</h2><span className="stat-index">01</span></div>
            <span className="stat-note">Reviews started in this workspace</span>
          </article>
          <article className="stat-card">
            <span className="stat-label">VERIFIED ADS</span>
            <div className="stat-value-row"><h2>0</h2><span className="stat-index">02</span></div>
            <span className="stat-note">Reports with a completed review record</span>
          </article>
          <article className="stat-card">
            <span className="stat-label">RISK FLAGS</span>
            <div className="stat-value-row"><h2>0</h2><span className="stat-index">03</span></div>
            <span className="stat-note">Flags recorded for human assessment</span>
          </article>
        </div>
      </section>

      <section className="workflow-section">
        <div className="section-heading">
          <h2>Review workflows</h2>
          <p>Choose the workflow that matches the material you need to review.</p>
        </div>
        <div className="workflow-grid">
          <article className="workflow-card workflow-card-featured">
            <div className="workflow-topline"><span className="workflow-number">01</span><span className="workflow-category">RECOMMENDED START</span></div>
            <div className="workflow-icon evaluate-icon" aria-hidden="true">↗</div>
            <h3>One-upload review</h3>
            <p>Submit a poster or video and run the applicable checks in a single consolidated report.</p>
            <button className="primary-button" onClick={() => onNavigate('unified')}>
              Start review <span aria-hidden="true">→</span>
            </button>
          </article>
          <article className="workflow-card">
            <div className="workflow-topline"><span className="workflow-number">02</span><span className="workflow-category">EVIDENCE</span></div>
            <div className="workflow-icon create-icon" aria-hidden="true">✓</div>
            <h3>Verify advertising claims</h3>
            <p>Review extracted claims and compare them with certificates, documents and expiry dates.</p>
            <button className="secondary-button" onClick={() => onNavigate('evidence')}>
              Open evidence review <span aria-hidden="true">→</span>
            </button>
          </article>
          <article className="workflow-card">
            <div className="workflow-topline"><span className="workflow-number">03</span><span className="workflow-category">CREATIVE REVIEW</span></div>
            <div className="workflow-icon create-icon" aria-hidden="true">⌕</div>
            <h3>Evaluate a poster</h3>
            <p>Inspect an existing advertisement image with OCR, claim analysis and available risk checks.</p>
            <button className="secondary-button" onClick={() => onNavigate('evaluate')}>
              Evaluate poster <span aria-hidden="true">→</span>
            </button>
          </article>
        </div>
      </section>

      <footer className="footer">
        <p>BrandGuard © 2026 · Team Verifex</p>
        <span>Analysis supports review; it does not replace human approval or legal advice.</span>
      </footer>
    </>
  )
}

export default Dashboard
