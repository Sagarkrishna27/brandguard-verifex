/*
  PosterGenerator.jsx
  -------------------
  Frontend for the real offline poster generator (backend endpoint:
  POST /api/generate-poster). The user provides a natural-language brief
  plus structured fields; the backend composes a genuine PNG and returns
  it as base64, which we render and offer as a download.

  The generator preserves the user's exact wording and invents nothing.
*/

import { useState } from 'react'
import { apiUrl } from '../lib/api.js'

const API = apiUrl('/api/generate-poster')

const STYLES = [
  { value: 'bold_splash', label: 'Bold Splash' },
  { value: 'clean_minimal', label: 'Clean Minimal' },
  { value: 'festive_warm', label: 'Festive Warm' },
  { value: 'corporate_trust', label: 'Corporate Trust' },
  { value: 'eco_natural', label: 'Eco Natural' },
]

const SIZES = [
  { value: 'square', label: 'Square (1080×1080)' },
  { value: 'story', label: 'Story (1080×1920)' },
  { value: 'poster', label: 'Poster (1080×1527)' },
  { value: 'banner', label: 'Banner (1200×628)' },
]

const THEMES = [
  { value: 'navy', label: 'Navy' },
  { value: 'crimson', label: 'Crimson' },
  { value: 'teal', label: 'Teal' },
  { value: 'royal', label: 'Royal' },
  { value: 'sunset', label: 'Sunset' },
  { value: 'charcoal', label: 'Charcoal' },
]

function PosterGenerator({ onNavigate }) {
  const [brief, setBrief] = useState('')
  const [brandName, setBrandName] = useState('')
  const [headline, setHeadline] = useState('')
  const [description, setDescription] = useState('')
  const [offer, setOffer] = useState('')
  const [cta, setCta] = useState('Learn More')
  const [disclaimer, setDisclaimer] = useState('')
  const [style, setStyle] = useState('corporate_trust')
  const [size, setSize] = useState('poster')
  const [colourTheme, setColourTheme] = useState('navy')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [poster, setPoster] = useState(null)
  const [approved, setApproved] = useState(false)

  const update = (setter) => (event) => setter(event.target.value)

  const generate = async (event) => {
    event.preventDefault()
    setError('')
    setPoster(null)
    setApproved(false)
    setLoading(true)

    try {
      const response = await fetch(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brand_name: brandName,
          headline,
          description,
          offer,
          cta,
          disclaimer,
          prompt: brief,
          style,
          size,
          colour_theme: colourTheme,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Poster generation failed. Please try again.')
      }

      setPoster(data)
    } catch (err) {
      setError(err.message || 'Cannot reach the BrandGuard backend.')
    } finally {
      setLoading(false)
    }
  }

  const download = () => {
    if (!poster || !approved) return

    const link = document.createElement('a')
    link.href = `data:image/png;base64,${poster.image_base64}`
    link.download = 'brandguard-poster.png'
    link.click()
  }

  return (
    <>
      <header className="page-header">
        <button className="back-button" onClick={() => onNavigate('dashboard')}>
          ← Back to Dashboard
        </button>
        <h1>AI Poster Generator</h1>
      </header>

      <p className="page-intro">
        Describe the poster you want — the generator composes it offline and
        keeps your exact wording. It never invents awards, certifications,
        prices, testimonials or government approvals. Human approval is
        required before publishing.
      </p>

      <div className="creator-layout">
        <form className="creator-form" onSubmit={generate}>
          <div className="poster-form-row poster-form-row-full">
            <div className="form-field">
              <label htmlFor="brief">Poster prompt (natural language)</label>
              <textarea
                id="brief"
                rows="3"
                value={brief}
                onChange={update(setBrief)}
                placeholder="e.g. A festive navy square poster for a Diwali electronics sale"
              />
            </div>
          </div>

          <div className="poster-form-row">
            <div className="form-field">
              <label htmlFor="genBrand">Brand Name</label>
              <input id="genBrand" type="text" value={brandName} onChange={update(setBrandName)} />
            </div>
            <div className="form-field">
              <label htmlFor="genHeadline">Headline</label>
              <input id="genHeadline" type="text" value={headline} onChange={update(setHeadline)} />
            </div>
            <div className="form-field">
              <label htmlFor="genDesc">Description</label>
              <textarea id="genDesc" rows="2" value={description} onChange={update(setDescription)} />
            </div>
          </div>

          <div className="poster-form-row">
            <div className="form-field">
              <label htmlFor="genOffer">Offer</label>
              <input id="genOffer" type="text" value={offer} onChange={update(setOffer)} />
            </div>
            <div className="form-field">
              <label htmlFor="genCta">Call-to-Action</label>
              <select id="genCta" value={cta} onChange={update(setCta)}>
                <option>Learn More</option>
                <option>Shop Now</option>
                <option>Register Now</option>
                <option>Contact Us</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="genDisclaimer">Disclaimer / T&amp;C (optional)</label>
              <input
                id="genDisclaimer"
                type="text"
                value={disclaimer}
                onChange={update(setDisclaimer)}
                placeholder="e.g. T&C apply. Valid till 30 Nov."
              />
            </div>
          </div>

          <div className="poster-form-row">
            <div className="form-field">
              <label htmlFor="genStyle">Style</label>
              <select id="genStyle" value={style} onChange={update(setStyle)}>
                {STYLES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="genSize">Poster Size</label>
              <select id="genSize" value={size} onChange={update(setSize)}>
                {SIZES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="genTheme">Colour Theme</label>
              <select id="genTheme" value={colourTheme} onChange={update(setColourTheme)}>
                {THEMES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>

          <button
            type="submit"
            className="primary-button"
            disabled={loading}
            style={{ marginTop: '0', width: '100%' }}
          >
            {loading ? 'Generating…' : 'Generate Poster'}
          </button>

          {error && <p className="upload-error" role="alert">{error}</p>}
        </form>

        <section className="preview-panel" aria-label="Generated poster">
          <p className="preview-label">Generated Poster</p>

          {poster ? (
            <>
              <img
                className="generated-poster"
                src={`data:image/png;base64,${poster.image_base64}`}
                alt={`Generated poster for ${brandName || 'your brand'}`}
              />
              <button className="primary-button" onClick={download} disabled={!approved} style={{ marginTop: '14px' }}>
                ⬇ Download PNG
              </button>
              <label className="approval-check"><input type="checkbox" checked={approved} onChange={(event) => setApproved(event.target.checked)} /> I reviewed the editable copy and approve this preview for export.</label>
              <p className="preview-note">
                {poster.generator} · {poster.width}×{poster.height}px ·
                AI enrichment: {poster.ai_enrichment_used ? 'enabled' : 'not configured (offline engine used)'}
              </p>
              <p className="preview-note">{poster.disclaimer}</p>
            </>
          ) : (
            <div className="preview-placeholder">
              <p>Your generated poster will appear here.</p>
              <p>Fill in the brief and press Generate Poster.</p>
            </div>
          )}
        </section>
      </div>

      <footer className="footer">
        <p>BrandGuard © 2026 · Built by Team Verifex</p>
        <span>Human review is required for final approval.</span>
      </footer>
    </>
  )
}

export default PosterGenerator
