import { useState } from 'react'
import { apiUrl } from '../lib/api.js'

function ClaimEvidence({ onNavigate }) {
  const [text, setText] = useState(() => {
    const prefill = sessionStorage.getItem('brandguard-evidence-prefill') || ''
    sessionStorage.removeItem('brandguard-evidence-prefill')
    return prefill
  })
  const [files, setFiles] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function verify(event) {
    event.preventDefault()
    if (!text.trim()) return setError('Paste advertisement copy or run OCR first.')
    setLoading(true); setError(''); setResult(null)
    try {
      const body = new FormData(); body.append('text', text)
      files.forEach((file) => body.append('evidence_files', file))
      const response = await fetch(apiUrl('/api/verify-claims-evidence'), { method: 'POST', body })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Evidence verification failed.')
      setResult(data)
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }

  return <>
    <header className="page-header"><button className="back-button" onClick={() => onNavigate('dashboard')}>← Back</button><h1>Evidence-Based Claim Verification</h1></header>
    <p className="page-intro">Claims are extracted from the ad and compared with the evidence you provide. Missing, expired and questionable evidence is explained for human review.</p>
    <form className="evaluator-card round3-form" onSubmit={verify}>
      <label className="form-field"><span>Advertisement text</span><textarea rows="8" value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste OCR output or advertising copy…" /></label>
      <label className="form-field"><span>Supporting certificates or documents</span><input type="file" multiple accept=".txt,.md,.json,.csv,.pdf,image/png,image/jpeg" onChange={(e) => setFiles([...e.target.files])} /><small>{files.length ? `${files.length} file(s) selected` : 'Text and image evidence are supported locally.'}</small></label>
      <button className="primary-button" disabled={loading}>{loading ? 'Checking evidence…' : 'Verify claims against evidence'}</button>
    </form>
    {error && <p className="upload-error" role="alert">{error}</p>}
    {result && <section className="tool-result evidence-results"><div className="result-summary"><strong>{result.summary.review_required ? 'REVIEW REQUIRED' : 'SUPPORTED'}</strong><span>{result.summary.claim_count} claim categories · {result.summary.supported_count} supported · {result.summary.flagged_count} flagged</span></div>{result.claims.map((claim) => <article className="claim-card" key={claim.id}><div className="claim-card-heading"><strong>{claim.claim}</strong>{claim.category && <span className="claim-category">{claim.category.replaceAll('_', ' ')}</span>}</div><p><b>{claim.status}</b> — {claim.explanation}</p>{claim.matched_evidence.length > 0 && <small>Evidence: {claim.matched_evidence.join(', ')}</small>}</article>)}</section>}
  </>
}

export default ClaimEvidence
