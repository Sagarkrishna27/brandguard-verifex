/*
  TrustPassport.jsx
  -----------------
  Frontend for the existing Trust Passport backend endpoints:
    POST /api/trust-passport/        -> create a passport (upload image)
    GET  /api/trust-passport/{id}    -> verify a passport
    GET  /api/trust-passport/{id}/qr -> download the QR code image
    GET  /api/trust-passport/        -> list all passports

  Flow: upload an advertisement + details -> get a passport with a QR code
  -> scan the QR (or paste the ID) -> see the verification record.
  This record proves the image bytes exist in the BrandGuard database —
  it is NOT a guarantee of legal compliance.
*/

import { useRef, useState } from 'react'
import { apiRequest, apiUrl } from '../lib/api.js'

const API_BASE = apiUrl('/api/trust-passport')

const STATUS_OPTIONS = ['VERIFIED', 'NEEDS REVIEW', 'UNSUPPORTED', 'REJECTED']

function TrustPassport({ onNavigate }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [fileName, setFileName] = useState('')
  const [advertisementName, setAdvertisementName] = useState('')
  const [reviewStatus, setReviewStatus] = useState('NEEDS REVIEW')
  const [riskScore, setRiskScore] = useState(0)
  const [reviewer, setReviewer] = useState('Team Verifex')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [passport, setPassport] = useState(null) // creation response (QR etc.)
  const [verifyId, setVerifyId] = useState('')
  const [verifyResult, setVerifyResult] = useState(null)
  const [verifyError, setVerifyError] = useState('')
  const [verifyLoading, setVerifyLoading] = useState(false)
  const [reviewerToken, setReviewerToken] = useState('')
  const [officialReviewStatus, setOfficialReviewStatus] = useState('VERIFIED')
  const [reviewRiskScore, setReviewRiskScore] = useState(0)
  const [reviewerName, setReviewerName] = useState('')
  const [reviewNotes, setReviewNotes] = useState('')
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewMessage, setReviewMessage] = useState('')
  const [reviewError, setReviewError] = useState('')

  const fileInputRef = useRef(null)

  const handleFileChange = (event) => {
    const chosen = event.target.files[0]
    setError('')

    if (!chosen) return

    if (!['image/png', 'image/jpeg'].includes(chosen.type)) {
      setError('Please choose a PNG, JPG or JPEG image.')
      return
    }

    if (chosen.size > 15 * 1024 * 1024) {
      setError('Image size must be below 15 MB.')
      return
    }

    if (preview) URL.revokeObjectURL(preview)
    setFile(chosen)
    setPreview(URL.createObjectURL(chosen))
    setFileName(chosen.name)
  }

  const handleCreate = async (event) => {
    event.preventDefault()

    if (!file) {
      setError('Please upload the advertisement image first.')
      return
    }

    if (!advertisementName.trim()) {
      setError('Advertisement name is required.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('advertisement_name', advertisementName.trim())
      formData.append('review_status', reviewStatus)
      formData.append('risk_score', String(riskScore))
      formData.append('reviewer', reviewer.trim() || 'Team Verifex')
      formData.append('notes', notes.trim())
      formData.append('version', '1')

      const data = await apiRequest(API_BASE + '/', {
        method: 'POST',
        body: formData,
      }, {
        timeoutMs: 120_000,
        fallbackMessage: 'Could not create the Trust Passport.',
      })

      setPassport(data)
    } catch (err) {
      setError(
        err.message ||
        'Cannot connect to BrandGuard backend. Check that the backend is running.'
      )
    } finally {
      setLoading(false)
    }
  }

  const handleVerify = async (event) => {
    event.preventDefault()

    const id = verifyId.trim()
    if (!id) {
      setVerifyError('Paste a passport ID to verify.')
      return
    }

    setVerifyLoading(true)
    setVerifyError('')
    setVerifyResult(null)

    try {
      const data = await apiRequest(`${API_BASE}/${encodeURIComponent(id)}`, {}, {
        timeoutMs: 120_000,
        fallbackMessage: 'Verification failed.',
      })

      setVerifyResult(data)
    } catch (err) {
      setVerifyError(
        err.message ||
        'Cannot connect to BrandGuard backend. Check that the backend is running.'
      )
    } finally {
      setVerifyLoading(false)
    }
  }

  const handleReset = () => {
    if (preview) URL.revokeObjectURL(preview)
    setFile(null)
    setPreview(null)
    setFileName('')
    setAdvertisementName('')
    setNotes('')
    setPassport(null)
    setError('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleReview = async (event) => {
    event.preventDefault()
    setReviewError('')
    setReviewMessage('')
    if (!verifyId.trim()) return setReviewError('Verify or enter a passport ID before reviewing.')
    if (!reviewerToken.trim()) return setReviewError('Reviewer token is required.')
    if (!reviewerName.trim()) return setReviewError('Reviewer name is required.')

    setReviewLoading(true)
    try {
      const formData = new FormData()
      formData.append('review_status', officialReviewStatus)
      formData.append('risk_score', String(reviewRiskScore))
      formData.append('reviewer', reviewerName.trim())
      formData.append('notes', reviewNotes.trim())
      const data = await apiRequest(`${API_BASE}/${encodeURIComponent(verifyId.trim())}/review`, {
        method: 'PATCH',
        headers: { 'X-Reviewer-Token': reviewerToken.trim() },
        body: formData,
      }, {
        timeoutMs: 120_000,
        fallbackMessage: 'Review update failed.',
      })
      setVerifyResult(data)
      setReviewMessage('Official review outcome saved.')
    } catch (err) {
      setReviewError(err.message || 'Cannot reach the reviewer endpoint.')
    } finally {
      setReviewLoading(false)
    }
  }

  return (
    <>
      <header className="page-header">
        <button className="back-button" onClick={() => onNavigate('dashboard')}>
          ← Back to Dashboard
        </button>
        <h1>Trust Passport</h1>
      </header>

      <p className="page-intro">
        Issue a verifiable Trust Passport for a reviewed advertisement. Each
        passport stores a SHA-256 hash of the exact image bytes and a QR code
        linking to its verification record. A passport record is evidence of
        review — it is <strong>not</strong> a guarantee of legal compliance.
      </p>

      <div className="evaluator-layout">
        {/* ---------- CREATE PASSPORT ---------- */}
        <section className="evaluator-card" aria-label="Create Trust Passport">
          <h2>1. Issue a Trust Passport</h2>

          {!passport ? (
            <form onSubmit={handleCreate}>
              <label className="upload-area" htmlFor="passportUpload">
                <span className="upload-icon" aria-hidden="true">⬆</span>
                <span className="upload-title">Choose the advertisement image</span>
                <span className="upload-hint">PNG, JPG or JPEG · Maximum 15 MB</span>
                <input
                  id="passportUpload"
                  ref={fileInputRef}
                  type="file"
                  accept=".png,.jpg,.jpeg,image/png,image/jpeg"
                  onChange={handleFileChange}
                />
              </label>

              {fileName && (
                <p className="upload-file-name">
                  Selected: <strong>{fileName}</strong>
                </p>
              )}

              {error && (
                <p className="upload-error" role="alert">{error}</p>
              )}

              <div className="form-field" style={{ marginTop: '16px' }}>
                <label htmlFor="adName">Advertisement Name</label>
                <input
                  id="adName"
                  type="text"
                  value={advertisementName}
                  onChange={(e) => setAdvertisementName(e.target.value)}
                  placeholder="e.g. Diwali Sale Poster v2"
                />
              </div>

              <div className="form-field" style={{ marginTop: '12px' }}>
                <p className="tool-note">Public submissions are always stored as NEEDS REVIEW with an unassigned reviewer. Only an authorized reviewer workflow can assign an official outcome.</p>
                <label htmlFor="reviewStatus">Review Status</label>
                <select
                  id="reviewStatus"
                  value={reviewStatus}
                  disabled
                  onChange={(e) => setReviewStatus(e.target.value)}
                >
                  {STATUS_OPTIONS.map((status) => (
                    <option key={status} value={status}>{status}</option>
                  ))}
                </select>
              </div>

              <div className="form-field" style={{ marginTop: '12px' }}>
                <label htmlFor="riskScore">Risk Score (0–100)</label>
                <input
                  id="riskScore"
                  type="number"
                  min="0"
                  max="100"
                  value={riskScore}
                  disabled
                  onChange={(e) => setRiskScore(Number(e.target.value))}
                />
              </div>

              <div className="form-field" style={{ marginTop: '12px' }}>
                <label htmlFor="reviewer">Reviewer</label>
                <input
                  id="reviewer"
                  type="text"
                  value={reviewer}
                  disabled
                  onChange={(e) => setReviewer(e.target.value)}
                />
              </div>

              <div className="form-field" style={{ marginTop: '12px' }}>
                <label htmlFor="notes">Review Notes</label>
                <textarea
                  id="notes"
                  rows="3"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Reviewer observations, evidence checked, decisions made..."
                />
              </div>

              <button
                type="submit"
                className="primary-button"
                disabled={loading}
                style={{ marginTop: '18px', width: '100%' }}
              >
                {loading ? 'Creating passport...' : 'Create Trust Passport'}
              </button>
            </form>
          ) : (
            /* ---------- SUCCESS: SHOW THE QR ---------- */
            <div style={{ textAlign: 'center' }}>
              <h3 style={{ color: 'var(--success)' }}>
                ✓ Trust Passport created
              </h3>

              <img
                src={`data:image/png;base64,${passport.qr_code_base64}`}
                alt={`QR code linking to verification record ${passport.passport_id}`}
                style={{ width: '220px', height: '220px', margin: '10px auto' }}
              />

              <dl className="passport-details">
                <dt>Advertisement</dt>
                <dd>{passport.advertisement_name}</dd>
                <dt>Status</dt>
                <dd>{passport.review_status}</dd>
                <dt>Risk Score</dt>
                <dd>{passport.risk_score}</dd>
                <dt>Reviewer</dt>
                <dd>{passport.reviewer}</dd>
                <dt>SHA-256</dt>
                <dd className="hash-text">{passport.sha256}</dd>
                <dt>Verification URL</dt>
                <dd className="hash-text">{passport.verification_url}</dd>
              </dl>

              <a
                className="primary-button"
                href={`${API_BASE}/${passport.passport_id}/qr`}
                download={`trust-passport-${passport.passport_id}.png`}
                style={{ display: 'inline-block', marginTop: '12px' }}
              >
                ⬇ Download QR Code
              </a>

              <br />

              <button
                className="secondary-button"
                onClick={handleReset}
                style={{ marginTop: '10px' }}
              >
                Issue another passport
              </button>
            </div>
          )}

          {preview && !passport && (
            <img
              className="evaluator-preview"
              src={preview}
              alt={`Advertisement preview: ${fileName}`}
              style={{ marginTop: '14px' }}
            />
          )}
        </section>

        {/* ---------- VERIFY PASSPORT ---------- */}
        <section className="evaluator-card" aria-label="Verify Trust Passport">
          <h2>2. Verify a passport</h2>

          <p style={{ fontSize: '13px', color: 'var(--muted)' }}>
            Paste a passport ID (from a QR scan or a reviewer) to load its
            verification record.
          </p>

          <form onSubmit={handleVerify}>
            <div className="form-field">
              <label htmlFor="verifyId">Passport ID</label>
              <input
                id="verifyId"
                type="text"
                value={verifyId}
                onChange={(e) => setVerifyId(e.target.value)}
                placeholder="e.g. 3f2a...-uuid-from-the-qr-code"
              />
            </div>

            <button
              type="submit"
              className="primary-button"
              disabled={verifyLoading}
              style={{ marginTop: '12px', width: '100%' }}
            >
              {verifyLoading ? 'Verifying...' : 'Verify Passport'}
            </button>
          </form>

          {verifyError && (
            <p className="upload-error" role="alert">{verifyError}</p>
          )}

          {verifyResult && (
            <div className="verification-result">
              <h3 style={{ color: 'var(--success)', marginTop: 0 }}>
                ✓ Record found in BrandGuard database
              </h3>

              <dl className="passport-details">
                <dt>Advertisement</dt>
                <dd>{verifyResult.advertisement_name}</dd>
                <dt>Verification Status</dt>
                <dd>{verifyResult.review_status}</dd>
                <dt>Risk Score</dt>
                <dd>{verifyResult.risk_score}</dd>
                <dt>Reviewer</dt>
                <dd>{verifyResult.reviewer}</dd>
                <dt>Date</dt>
                <dd>{new Date(verifyResult.created_at).toLocaleString()}</dd>
                <dt>Version</dt>
                <dd>{verifyResult.version}</dd>
                <dt>SHA-256 Hash</dt>
                <dd className="hash-text">{verifyResult.sha256}</dd>
              </dl>

              <p style={{ fontSize: '12px', color: 'var(--muted)' }}>
                {verifyResult.message}
              </p>
            </div>
          )}
        </section>

        <section className="evaluator-card reviewer-card" aria-label="Authorized Trust Passport review">
          <h2>3. Authorized review</h2>
          <p className="tool-note">This protected workflow is separate from public submission. The backend must be configured with <code>BRANDGUARD_REVIEWER_TOKEN</code>.</p>
          <form onSubmit={handleReview}>
            <div className="form-field">
              <label htmlFor="reviewerToken">Reviewer token</label>
              <input id="reviewerToken" type="password" value={reviewerToken} onChange={(e) => setReviewerToken(e.target.value)} autoComplete="off" placeholder="Set by the backend operator" />
            </div>
            <div className="form-field">
              <label htmlFor="officialReviewStatus">Official outcome</label>
              <select id="officialReviewStatus" value={officialReviewStatus} onChange={(e) => setOfficialReviewStatus(e.target.value)}>
                {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{status}</option>)}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="officialRiskScore">Risk score (0–100)</label>
              <input id="officialRiskScore" type="number" min="0" max="100" value={reviewRiskScore} onChange={(e) => setReviewRiskScore(Number(e.target.value))} />
            </div>
            <div className="form-field">
              <label htmlFor="officialReviewerName">Reviewer name</label>
              <input id="officialReviewerName" value={reviewerName} onChange={(e) => setReviewerName(e.target.value)} maxLength="80" />
            </div>
            <div className="form-field">
              <label htmlFor="officialReviewNotes">Review notes</label>
              <textarea id="officialReviewNotes" rows="3" value={reviewNotes} onChange={(e) => setReviewNotes(e.target.value)} />
            </div>
            <button type="submit" className="primary-button" disabled={reviewLoading} style={{ marginTop: '12px', width: '100%' }}>
              {reviewLoading ? 'Saving review...' : 'Save official review'}
            </button>
          </form>
          {reviewError && <p className="upload-error" role="alert">{reviewError}</p>}
          {reviewMessage && <p className="success-note" role="status">{reviewMessage}</p>}
        </section>
      </div>

      <footer className="footer">
        <p>BrandGuard © 2026 · Built by Team Verifex</p>
        <span>Human review is required for final approval.</span>
      </footer>
    </>
  )
}

export default TrustPassport
