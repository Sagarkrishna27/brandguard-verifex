/*
  Tools.jsx
  ---------
  One page hosting the six upload/text tool features (roadmap items
  3, 4, 5, 6, 8 and 9). Each card calls its real backend endpoint and
  displays the genuine result — loading and error states included.
  Nothing here simulates success.
*/

import { useRef, useState } from 'react'
import { API_BASE_URL, apiRequest } from '../lib/api.js'

const API = API_BASE_URL

// Small reusable image-analysis runner used by the four upload tools.
function ImageToolCard({ title, endpoint, children }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const requestInFlightRef = useRef(false)

  const handleFile = (event) => {
    const chosen = event.target.files[0]
    setError('')
    setResult(null)

    if (!chosen) return

    if (!['image/png', 'image/jpeg'].includes(chosen.type)) {
      setError('Please choose a PNG, JPG or JPEG image.')
      return
    }

    if (preview) URL.revokeObjectURL(preview)
    setFile(chosen)
    setPreview(URL.createObjectURL(chosen))
  }

  const analyse = async () => {
    if (requestInFlightRef.current) return

    if (!file) {
      setError('Choose an image first.')
      return
    }

    requestInFlightRef.current = true
    setLoading(true)
    setError('')

    try {
      const formData = new FormData()
      formData.append('file', file)

      const data = await apiRequest(`${API}/api/${endpoint}`, {
        method: 'POST',
        body: formData,
      }, {
        timeoutMs: 60_000,
        fallbackMessage: 'Analysis failed. Please try again.',
      })

      setResult(data)
    } catch (err) {
      setError(err.message || 'Cannot reach the BrandGuard backend.')
    } finally {
      requestInFlightRef.current = false
      setLoading(false)
    }
  }

  return (
    <section className="evaluator-card">
      <h2>{title}</h2>
      {children}

      <label className="upload-area" style={{ marginTop: '14px' }}>
        <span className="upload-title">Choose a poster image</span>
        <input type="file" accept=".png,.jpg,.jpeg" onChange={handleFile} />
      </label>

      {preview && (
        <img
          className="evaluator-preview"
          src={preview}
          alt="Selected poster preview"
          style={{ marginTop: '12px' }}
        />
      )}

      <button
        className="primary-button"
        onClick={analyse}
        disabled={!file || loading}
        style={{ marginTop: '12px', width: '100%' }}
      >
        {loading ? 'Analyzing…' : 'Analyze'}
      </button>

      {error && <p className="upload-error" role="alert">{error}</p>}

      {result && (
        <div className="tool-result">
          <ResultRenderer endpoint={endpoint} result={result} />
        </div>
      )}
    </section>
  )
}

// Renders the genuine backend result for each tool type.
function ResultRenderer({ endpoint, result }) {
  if (endpoint === 'video-check') {
    return (
      <>
        {result.extracted_text && (
          <p><strong>Frame text:</strong> {result.extracted_text}</p>
        )}
        <ul>
          {result.checks.map((check) => (
            <li key={check.check}>
              <strong style={{ color: check.passed ? 'var(--success)' : 'var(--danger)' }}>
                {check.passed ? '✓' : '✗'}
              </strong>{' '}
              {check.check} — {check.explanation}
            </li>
          ))}
        </ul>
        <p className="tool-note">{result.note}</p>
      </>
    )
  }

  if (endpoint === 'detect-disclaimer') {
    return (
      <>
        <p><strong>Finding:</strong> {result.finding.replaceAll('_', ' ')}</p>
        <p>{result.detail}</p>
        <p><strong>Bottom-area text:</strong> {result.bottom_text_extracted || 'None detected'}</p>
        <p className="tool-note">Contrast ratio (bottom vs headline): {result.bottom_vs_headline_ratio}</p>
      </>
    )
  }

  if (endpoint === 'detect-qr') {
    return (
      <>
        <p><strong>QR status:</strong> {result.status === 'QR_DETECTED' ? 'QR detected' : result.status === 'DECODER_UNAVAILABLE' ? 'Decoder unavailable' : 'No QR code found'}</p>
        {result.decoded_value && (
          <p><strong>Decoded:</strong> <span className="hash-text">{result.decoded_value}</span></p>
        )}
        {result.is_trust_passport_link && (
          <p style={{ color: 'var(--success)' }}>
            ✓ This QR links to a Trust Passport verification record.
          </p>
        )}
        {result.note && <p className="tool-note">{result.note}</p>}
      </>
    )
  }

  if (endpoint === 'manipulation-check') {
    return (
      <>
        <p>
          <strong>Flags raised:</strong> {result.flags_raised} of 3 ·{' '}
          <strong>Risk:</strong> {result.risk_level.replaceAll('_', ' ')}
        </p>
        <ul>
          {result.findings.map((f) => (
            <li key={f.heuristic}>
              <strong>{f.heuristic}</strong> (score {f.score}) — {f.reading}
            </li>
          ))}
        </ul>
        <p className="tool-note">{result.note}</p>
      </>
    )
  }

  return null
}

// Text-input tool card (truth checker / fake reviews).
function TextToolCard({ title, endpoint, placeholder, resultNote }) {
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const requestInFlightRef = useRef(false)

  const analyse = async (event) => {
    event.preventDefault()
    if (requestInFlightRef.current) return
    setError('')

    if (!text.trim()) {
      setError('Please enter some text first.')
      return
    }

    requestInFlightRef.current = true
    setLoading(true)

    try {
      const payload = endpoint === 'truth-check'
        ? { text, url }
        : { text }

      const data = await apiRequest(`${API}/api/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }, {
        timeoutMs: 60_000,
        fallbackMessage: 'Analysis failed. Please try again.',
      })

      setResult(data)
    } catch (err) {
      setError(err.message || 'Cannot reach the BrandGuard backend.')
    } finally {
      requestInFlightRef.current = false
      setLoading(false)
    }
  }

  return (
    <section className="evaluator-card">
      <h2>{title}</h2>
      <form onSubmit={analyse}>
        <div className="form-field">
          <label htmlFor={`${endpoint}-text`}>{placeholder}</label>
          <textarea
            id={`${endpoint}-text`}
            rows="4"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>

        {endpoint === 'truth-check' && (
          <div className="form-field" style={{ marginTop: '10px' }}>
            <label htmlFor="truthUrl">Brand website URL</label>
            <input
              id="truthUrl"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.example.com"
            />
          </div>
        )}

        <button
          type="submit"
          className="primary-button"
          disabled={loading}
          style={{ marginTop: '12px', width: '100%' }}
        >
          {loading ? 'Checking…' : 'Check'}
        </button>
      </form>

      {error && <p className="upload-error" role="alert">{error}</p>}

      {result && (
        <div className="tool-result">
          {endpoint === 'truth-check' && result.success && (
            <>
              <p>
                <strong>Checked:</strong> {result.checked_url}
                {result.website_title ? ` ("${result.website_title}")` : ''}
              </p>
              {Object.entries(result.comparison).map(([type, data]) => (
                <div key={type} style={{ marginBottom: '10px' }}>
                  <strong>{type.replaceAll('_', ' ')}:</strong>{' '}
                  <span style={{
                    color: data.status === 'MATCHED' ? 'var(--success)'
                      : data.status === 'NOT_FOUND_ON_WEBSITE' ? 'var(--danger)'
                        : 'var(--muted)',
                  }}>
                    {data.status.replaceAll('_', ' ')}
                  </span>
                  {data.in_advertisement.length > 0 && (
                    <small> · in ad: {data.in_advertisement.join(', ')}</small>
                  )}
                </div>
              ))}
              <p className="tool-note">{result.note}</p>
            </>
          )}

          {endpoint === 'truth-check' && !result.success && (
            <p className="upload-error">{result.error}</p>
          )}

          {endpoint === 'fake-reviews' && (
            <>
              <p>
                {result.suspicious_count} of {result.reviews_analyzed} review(s)
                flagged for verification.
              </p>
              {result.suspicious_reviews.map((item, index) => (
                <div key={index} className="claim-card" style={{ marginBottom: '10px' }}>
                  <p>"{item.review}"</p>
                  {item.flags.map((f) => (
                    <p key={f.flag}>
                      <strong>{f.flag.replaceAll('_', ' ')}:</strong> {f.detail}
                    </p>
                  ))}
                </div>
              ))}
              <p className="tool-note">{result.note}</p>
            </>
          )}

          {endpoint === 'improve-ad' && result.success && (
            <>
              <p><strong>{result.assistant_type}</strong></p>
              {result.suggestions.map((item) => (
                <div key={item.issue} className="claim-card" style={{ marginBottom: '10px' }}>
                  <p><strong>{item.issue}</strong></p>
                  <p>{item.suggestion}</p>
                  <small>{item.rule}</small>
                </div>
              ))}
              <p className="tool-note">Suggestions are editable review guidance; the original advertisement is never changed automatically.</p>
            </>
          )}
        </div>
      )}

      <p className="tool-note" style={{ marginTop: '10px' }}>{resultNote}</p>
    </section>
  )
}

function BrandDnaCard() {
  const [history, setHistory] = useState('[{"text":"Paste a prior analysed ad here","claims":[]}]')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const analyse = async (event) => {
    event.preventDefault(); setError(''); setResult(null)
    try {
      const scanHistory = JSON.parse(history)
      if (!Array.isArray(scanHistory) || scanHistory.length === 0) throw new Error('Enter a non-empty JSON array of prior scan summaries.')
      setLoading(true)
      const response = await fetch(`${API}/api/brand-dna`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scan_history: scanHistory }) })
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || 'Brand DNA analysis failed.')
      setResult(data)
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }
  return <section className="evaluator-card"><h2>7 · Brand DNA Analysis</h2><form onSubmit={analyse}><div className="form-field"><label htmlFor="brand-dna-history">Prior scan summaries (JSON)</label><textarea id="brand-dna-history" rows="6" value={history} onChange={(event) => setHistory(event.target.value)} /></div><button className="primary-button" disabled={loading}>{loading ? 'Analysing…' : 'Build Brand DNA'}</button></form>{error && <p className="upload-error" role="alert">{error}</p>}{result?.success && <div className="tool-result"><p><strong>Scans analysed:</strong> {result.scans_analyzed}</p><p><strong>Tone:</strong> {result.tone_profile.join(', ')}</p><p><strong>Value emphasis:</strong> {Object.entries(result.value_emphasis).map(([key, value]) => `${key}: ${value}`).join(' · ')}</p><p className="tool-note">{result.note}</p></div>}</section>
}

function Tools({ onNavigate }) {
  return (
    <>
      <header className="page-header">
        <button className="back-button" onClick={() => onNavigate('dashboard')}>
        ← Back to Dashboard
      </button>
      <h1>Advertisement Tools</h1>
    </header>

      <p className="page-intro">
        Every tool on this page runs a genuine analysis on your poster image,
        video frame or text through the BrandGuard backend, and shows the
        real result — including honest "unable to check" states. Each flag
        is a review indicator for a human, never an automatic verdict.
      </p>

      <div className="evaluator-layout">
        <div style={{ display: 'grid', gap: '20px' }}>
          <ImageToolCard title="3 · Video Advertisement Checker" endpoint="video-check">
            <p className="tool-note">
              Upload the first frame (or a still) of a video advertisement.
              Checks offer text, disclaimers, validity and contact details.
            </p>
          </ImageToolCard>

          <ImageToolCard title="4 · Hidden Disclaimer Detector" endpoint="detect-disclaimer">
            <p className="tool-note">
              Measures fine-print contrast in the lower poster area against
              the headline area — the measurable pattern of hidden disclaimers.
            </p>
          </ImageToolCard>

          <ImageToolCard title="8 · AI Ad Manipulation Detector" endpoint="manipulation-check">
            <p className="tool-note">
              Classical image-forensics heuristics (compression, sharpness,
              colour-channel checks). Not deepfake AI — results are review flags.
            </p>
          </ImageToolCard>
        </div>

        <div style={{ display: 'grid', gap: '20px' }}>
          <ImageToolCard title="5 · Embedded QR Detector" endpoint="detect-qr">
            <p className="tool-note">
              Detects a QR code inside a poster and checks whether it links
              to a Trust Passport verification record.
            </p>
          </ImageToolCard>

          <TextToolCard
            title="6 · Ad-to-Website Truth Checker"
            endpoint="truth-check"
            placeholder="Paste the advertisement text"
            resultNote="Compares the ad's numbers and claims against the brand's live website. A mismatch is a review flag, not proof of a false claim."
          />

          <TextToolCard
            title="9 · Fake Review Detector"
            endpoint="fake-reviews"
            placeholder="Paste reviews (one per line)"
            resultNote="Linguistic analysis for unspecific praise, template names and uniform sentiment. Flags are indicators — humans decide."
          />
          <TextToolCard
            title="11 · Advertisement Improvement Assistant"
            endpoint="improve-ad"
            placeholder="Paste advertisement copy for review suggestions"
            resultNote="Returns rule-based claim wording, disclaimer and visual/layout suggestions for human editing."
          />
          <BrandDnaCard />
        </div>
      </div>

      <footer className="footer">
        <p>BrandGuard © 2026 · Built by Team Verifex</p>
        <span>Human review is required for final approval.</span>
      </footer>
    </>
  )
}

export default Tools
