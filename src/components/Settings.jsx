import { useState } from 'react'
import { API_BASE_URL } from '../lib/api.js'

const STORAGE_KEY = 'brandguard-settings'

const DEFAULT_SETTINGS = {
  reviewerName: 'Team Verifex',
  defaultLanguage: 'eng',
}

function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    return { ...DEFAULT_SETTINGS, ...saved }
  } catch {
    return DEFAULT_SETTINGS
  }
}

function Settings({ onNavigate }) {
  const [settings, setSettings] = useState(loadSettings)
  const [saved, setSaved] = useState(false)

  const update = (field) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setSettings((current) => ({ ...current, [field]: value }))
    setSaved(false)
  }

  const handleSave = (event) => {
    event.preventDefault()
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    setSaved(true)
  }

  const handleReset = () => {
    localStorage.removeItem(STORAGE_KEY)
    setSettings(DEFAULT_SETTINGS)
    setSaved(true)
  }

  return (
    <>
      <header className="page-header">
        <button className="back-button" onClick={() => onNavigate('dashboard')}>
          ← Back to Dashboard
        </button>
        <h1>Settings</h1>
      </header>

      <p className="page-intro">
        Configure local review preferences for this browser. Server security,
        reviewer authorization and API credentials are never stored here.
      </p>

      <div className="evaluator-layout">
        <section className="evaluator-card" aria-label="Review preferences">
          <h2>Review preferences</h2>
          <form onSubmit={handleSave}>
            <div className="form-field">
              <label htmlFor="settingsReviewerName">Reviewer display name</label>
              <input id="settingsReviewerName" value={settings.reviewerName} onChange={update('reviewerName')} maxLength="80" />
              <small className="tool-note">Used as a local display preference only. It does not authorize Trust Passport approval.</small>
            </div>

            <div className="form-field">
              <label htmlFor="settingsLanguage">Default OCR language</label>
              <select id="settingsLanguage" value={settings.defaultLanguage} onChange={update('defaultLanguage')}>
                <option value="eng">English</option>
                <option value="hin">Hindi</option>
                <option value="ben">Bengali</option>
                <option value="kan">Kannada</option>
                <option value="tam">Tamil</option>
                <option value="tel">Telugu</option>
              </select>
            </div>

            <div className="settings-actions">
              <button className="primary-button" type="submit">Save preferences</button>
              <button className="secondary-button" type="button" onClick={handleReset}>Reset</button>
            </div>
            {saved && <p className="success-note" role="status">Preferences saved locally in this browser.</p>}
          </form>
        </section>

        <section className="evaluator-card" aria-label="Connection status">
          <h2>Connection status</h2>
          <dl className="passport-details">
            <dt>Frontend API base URL</dt>
            <dd className="hash-text">{API_BASE_URL}</dd>
            <dt>Storage</dt>
            <dd>Browser local storage for preferences only</dd>
            <dt>Trust Passport review</dt>
            <dd>Public submissions remain NEEDS REVIEW until authorized review is performed server-side.</dd>
          </dl>
          <p className="tool-note">Set deployment URLs through environment variables. Never paste API keys or passwords into this page.</p>
        </section>
      </div>

      <footer className="footer">
        <p>BrandGuard © 2026 · Built by Team Verifex</p>
        <span>Human review is required for final approval.</span>
      </footer>
    </>
  )
}

export default Settings
