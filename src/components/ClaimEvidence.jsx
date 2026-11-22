import { useRef, useState } from 'react'
import { apiRequest, apiUrl } from '../lib/api.js'

function ClaimEvidence({ onNavigate }) {
  const [text, setText] = useState(() => {
    const prefill = sessionStorage.getItem('brandguard-evidence-prefill') || ''
    sessionStorage.removeItem('brandguard-evidence-prefill')
    return prefill
  })
  const [files, setFiles] = useState([])
  const [result, setResult] = useState(null)
  const [investigationResult, setInvestigationResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [investigating, setInvestigating] = useState(false)
  const requestInFlightRef = useRef(false)
  const investigationInFlightRef = useRef(false)

  async function verify(event) {
    event.preventDefault()
    if (requestInFlightRef.current) return
    if (!text.trim()) return setError('Paste advertisement copy or run OCR first.')
    requestInFlightRef.current = true
    setLoading(true); setError('')
    try {
      const body = new FormData(); body.append('text', text)
      files.forEach((file) => body.append('evidence_files', file))
      const data = await apiRequest(apiUrl('/api/verify-claims-evidence'), {
        method: 'POST',
        body,
      }, {
        timeoutMs: 120_000,
        fallbackMessage: 'Evidence verification failed.',
      })
      setResult(data)
    } catch (err) { setError(err.message) } finally {
      requestInFlightRef.current = false
      setLoading(false)
    }
  }

  async function investigate() {
    if (investigationInFlightRef.current) return
    if (!text.trim()) return setError('Paste advertisement copy or run OCR first.')
    investigationInFlightRef.current = true
    setInvestigating(true); setError('')
    try {
      const data = await apiRequest(apiUrl('/api/investigate-claims'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      }, {
        timeoutMs: 120_000,
        fallbackMessage: 'Claim investigation failed.',
      })
      setInvestigationResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      investigationInFlightRef.current = false
      setInvestigating(false)
    }
  }

  return <>
    <header className="page-header"><button className="back-button" onClick={() => onNavigate('dashboard')}>← Back</button><h1>Evidence-Based Claim Verification</h1></header>
    <p className="page-intro">Claims are extracted from the ad and compared with the evidence you provide. Text overlap is a review cue only; uploaded documents are not authenticated or automatically accepted as proof.</p>
    <form className="evaluator-card round3-form" onSubmit={verify}>
      <label className="form-field"><span>Advertisement text</span><textarea rows="8" value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste OCR output or advertising copy…" /></label>
      <label className="form-field"><span>Supporting certificates or documents</span><input type="file" multiple accept=".txt,.md,.json,.csv,.pdf,image/png,image/jpeg" onChange={(e) => setFiles([...e.target.files])} /><small>{files.length ? `${files.length} file(s) selected` : 'Selectable PDF text, UTF-8 text, and image OCR are supported. Scanned PDFs need OCR.'}</small></label>
      <button className="primary-button" disabled={loading}>{loading ? 'Checking evidence…' : 'Verify claims against evidence'}</button>
      <button type="button" className="primary-button" disabled={investigating || loading} onClick={investigate}>{investigating ? 'Investigating claims…' : 'Investigate claims using public sources'}</button>
    </form>
    {error && <p className="upload-error" role="alert">{error}</p>}
    {result && <section className="tool-result evidence-results"><div className="result-summary"><strong>{result.summary.review_required ? 'REVIEW REQUIRED' : 'NO CLAIMS DETECTED'}</strong><span>{result.summary.claim_count} claims · {result.summary.UNDER_REVIEW} under review · {result.summary.INSUFFICIENT} insufficient · {result.summary.MISSING} missing</span></div>{result.documents?.map((document) => <p className="tool-note" key={document.name}>{document.name}: {document.extraction_status} · {document.message}</p>)}{result.claims.map((claim) => <article className="claim-card" key={claim.id}><div className="claim-card-heading"><strong>{claim.claim}</strong>{claim.category && <span className="claim-category">{claim.category.replaceAll('_', ' ')}</span>}</div><p><b>{claim.status}</b> — {claim.explanation}</p>{claim.matched_evidence.length > 0 && <small>Matched documents: {claim.matched_evidence.join(', ')}</small>}</article>)}</section>}
    {investigationResult && <section className="tool-result evidence-results">
      <div className="result-summary">
        <strong>PRELIMINARY INVESTIGATION</strong>
        <span>{investigationResult.claims_investigated} claims investigated · {investigationResult.claims_omitted_limit} omitted by investigation limit</span>
      </div>
      <p className="tool-note">{investigationResult.message}</p>
      {investigationResult.claims.map((claim, index) => <article className="claim-card" key={`${claim.text}-${index}`}>
        <div className="claim-card-heading">
          <strong>{claim.text}</strong>
          {claim.category && <span className="claim-category">{claim.category.replaceAll('_', ' ')}</span>}
        </div>
        <p><b>{claim.investigation_status}</b></p>
        {claim.ai_assessment && <>
          <p>{claim.ai_assessment.reasoning}</p>
          {claim.ai_assessment.limitations && <small>Limitations: {claim.ai_assessment.limitations}</small>}
        </>}
        {claim.sources?.length > 0 ? <div className="tool-note">
          <strong>Public sources found</strong>
          {claim.sources.map((source, sourceIndex) => <p key={`${source.url}-${sourceIndex}`}>
            <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
            {source.snippet && <small> — {source.snippet}</small>}
          </p>)}
        </div> : <p className="tool-note">No public sources available. Search status: {claim.search_status || claim.investigation_status}</p>}
        <small>Human review required. This claim has not been verified.</small>
      </article>)}
    </section>}
  </>
}

export default ClaimEvidence
