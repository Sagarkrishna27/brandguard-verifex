import { useEffect, useRef, useState } from 'react'
import { apiRequest, apiUrl } from '../lib/api.js'

const MODULE_STATUS_LABELS = {
  PENDING: 'Waiting',
  RUNNING: 'Running',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
  SKIPPED: 'Skipped',
  UNABLE_TO_VERIFY: 'Unable to verify',
  NOT_CONFIGURED: 'Not configured',
}

function UnifiedAnalysis({ onNavigate }) {
  const [file, setFile] = useState(null)
  const [evidenceFiles, setEvidenceFiles] = useState([])
  const [preview, setPreview] = useState('')
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const requestInFlightRef = useRef(false)

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview)
  }, [preview])

  const chooseFile = (event) => {
    const selected = event.target.files?.[0] || null
    if (preview) URL.revokeObjectURL(preview)
    setPreview(selected?.type.startsWith('image/') ? URL.createObjectURL(selected) : '')
    setFile(selected)
    setJob(null)
    setError('')
  }

  async function pollJob(jobId) {
    const deadline = Date.now() + 6 * 60 * 1000
    while (Date.now() < deadline) {
      const data = await apiRequest(apiUrl(`/api/unified-analysis/${encodeURIComponent(jobId)}`), {}, {
        timeoutMs: 120_000,
        fallbackMessage: 'Could not read analysis progress.',
      })
      setJob(data)
      if (['COMPLETED', 'COMPLETED_WITH_FAILURES', 'FAILED'].includes(data.status)) return data
      await new Promise((resolve) => window.setTimeout(resolve, 1000))
    }
    throw new Error('Analysis is taking longer than expected. You can retry by starting a new analysis.')
  }

  async function analyze(event) {
    event.preventDefault()
    if (requestInFlightRef.current) return
    setError('')
    if (!file) {
      setError('Choose one poster image or video first.')
      return
    }
    if (!(file.type.startsWith('image/') || file.type.startsWith('video/'))) {
      setError('Choose a supported image or video file.')
      return
    }

    requestInFlightRef.current = true
    setLoading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      evidenceFiles.forEach((evidenceFile) => form.append('evidence_files', evidenceFile))
      const settings = JSON.parse(localStorage.getItem('brandguard-settings') || '{}')
      form.append('languages', settings.defaultLanguage || 'eng')
      const initial = await apiRequest(apiUrl('/api/unified-analysis'), {
        method: 'POST',
        body: form,
      }, {
        timeoutMs: 120_000,
        fallbackMessage: 'Could not start analysis.',
      })
      setJob(initial)
      await pollJob(initial.job_id)
    } catch (requestError) {
      setError(requestError.message || 'The BrandGuard API could not complete this request.')
    } finally {
      requestInFlightRef.current = false
      setLoading(false)
    }
  }

  const report = job?.report
  const modules = job?.modules || []
  const statusClass = (status) => `analysis-status analysis-status-${String(status || '').toLowerCase().replaceAll('_', '-')}`

  function openEvidence() {
    const extracted = report?.ocr?.original_extracted_text || report?.video?.sampled_frames?.map((frame) => frame.text).filter(Boolean).join('\n') || ''
    sessionStorage.setItem('brandguard-evidence-prefill', extracted)
    onNavigate('evidence')
  }

  return (
    <>
      <header className="page-header">
        <button className="back-button" onClick={() => onNavigate('dashboard')}>← Back to Dashboard</button>
        <h1>One-Upload Advertisement Review</h1>
      </header>
      <p className="page-intro">
        Upload one poster or video. Verifex runs the applicable checks, including media-forensics triage, and keeps failures and verification limits visible.
      </p>

      <form className="evaluator-card unified-upload" onSubmit={analyze}>
        <label className="upload-area">
          <span className="upload-title">Choose one advertisement image or video</span>
          <span className="upload-hint">PNG/JPG up to 15 MB · video up to 200 MB</span>
          <input type="file" accept="image/png,image/jpeg,video/*" onChange={chooseFile} />
        </label>
        <label className="upload-area evidence-upload-area">
          <span className="upload-title">Add supporting evidence (optional)</span>
          <span className="upload-hint">PDF, TXT, CSV, JSON or image files ? Up to 10 documents, 10 MB each</span>
          <input
            type="file"
            multiple
            accept=".pdf,.txt,.md,.csv,.json,image/*"
            onChange={(event) => setEvidenceFiles(Array.from(event.target.files || []))}
          />
        </label>
        {evidenceFiles.length > 0 && (
          <p className="upload-file-name">
            Evidence selected: <strong>{evidenceFiles.map((item) => item.name).join(', ')}</strong>
          </p>
        )}
        {file && <p className="upload-file-name">Selected: <strong>{file.name}</strong> · {(file.size / (1024 * 1024)).toFixed(2)} MB</p>}
        {preview && <img className="unified-preview" src={preview} alt="Selected advertisement preview" />}
        <button className="primary-button" disabled={!file || loading}>
          {loading ? 'Analyzing one upload…' : 'Analyze advertisement'}
        </button>
        {error && <p className="upload-error" role="alert">{error}</p>}
      </form>

      {job && (
        <section className="unified-report" aria-live="polite">
          <div className="unified-report-heading">
            <div>
              <span className="ocr-region-kicker">ANALYSIS STATUS</span>
              <h2>{report?.overall_status || job.status.replaceAll('_', ' ')}</h2>
              <p>{job.filename || file?.name} · {modules.filter((item) => item.status === 'COMPLETED').length} of {modules.length} checks completed</p>
            </div>
            {report?.risk_summary && <span className={statusClass('COMPLETED')}>Risk: {report.risk_summary.replaceAll('_', ' ')}</span>}
          </div>

          <div className="analysis-module-list">
            {modules.map((module) => (
              <article className="analysis-module-card" key={module.id}>
                <div className="analysis-module-heading">
                  <h3>{module.label}</h3>
                  <span className={statusClass(module.status)}>{MODULE_STATUS_LABELS[module.status] || module.status}</span>
                </div>
                <p>{module.message}</p>
                {module.id === 'media_forensics' && (
                  <p className="tool-note">
                    Forensic signals and face-region detection are review aids only. AI-generated image/video and deepfake voice verdicts are not configured; no result certifies authenticity.
                  </p>
                )}
                {module.id === 'ocr' && module.result?.original_extracted_text && (
                  <blockquote className="analysis-extracted-text">{module.result.original_extracted_text}</blockquote>
                )}
                {module.id === 'proof_claim' && module.result?.claims?.length > 0 && (
                  <button type="button" className="text-button" onClick={openEvidence}>Open these claims in Evidence Verification</button>
                )}
                {module.result && (
                  <details open className="analysis-module-details">
                    <summary>View module details</summary>
                    <pre>{JSON.stringify(module.result, null, 2)}</pre>
                  </details>
                )}
              </article>
            ))}
          </div>

          {report?.verification && (
            <section className="verification-card">
              <h3>Report verification</h3>
              <p><strong>ID:</strong> <code>{report.verification.id}</code></p>
              <p>{report.verification.message}</p>
              {report.verification.status === 'READY' ? (
                <div className="verification-qr">
                  <img src={`data:image/png;base64,${report.verification.qr_code_base64}`} alt="QR code for this analysis report" />
                  <a href={report.verification.url} target="_blank" rel="noreferrer">Open public report</a>
                </div>
              ) : <p className="tool-note">No public QR was issued because a public HTTPS frontend URL is not configured.</p>}
            </section>
          )}
          <p className="tool-note">A report ID confirms the stored report record only. It does not certify claim truth or legal compliance.</p>
        </section>
      )}
    </>
  )
}

export default UnifiedAnalysis
