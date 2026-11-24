import { useEffect, useRef, useState } from 'react'
import { apiRequest, apiUrl } from '../lib/api.js'
import PosterCorrectionEditor from './PosterCorrectionEditor.jsx'

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
  const [correctedFile, setCorrectedFile] = useState(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [editorImage, setEditorImage] = useState('')
  const [editorLoading, setEditorLoading] = useState(false)
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

  async function analyze(event, revisionOf = '', selectedFile = file) {
    event.preventDefault()
    if (requestInFlightRef.current) return
    setError('')
    if (!selectedFile) {
      setError('Choose one poster image or video first.')
      return
    }
    if (!(selectedFile.type.startsWith('image/') || selectedFile.type.startsWith('video/'))) {
      setError('Choose a supported image or video file.')
      return
    }

    requestInFlightRef.current = true
    setLoading(true)
    try {
      const form = new FormData()
      form.append('file', selectedFile)
      if (revisionOf) form.append('revision_of', revisionOf)
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
  const improvement = report?.improvement_report
  const modules = job?.modules || []
  const statusClass = (status) => `analysis-status analysis-status-${String(status || '').toLowerCase().replaceAll('_', '-')}`

  async function openCorrectionEditor() {
    setError('')
    setEditorLoading(true)
    try {
      const reportId = report?.verification?.id
      if (!reportId) throw new Error('The report ID is not available yet.')
      const saved = await apiRequest(apiUrl('/api/analysis-reports/' + encodeURIComponent(reportId)), {}, {
        timeoutMs: 120_000,
        fallbackMessage: 'Could not load the original poster for editing.',
      })
      if (!saved.poster_data_url) throw new Error('The original poster image is unavailable for editing.')
      setEditorImage(saved.poster_data_url)
      setEditorOpen(true)
    } catch (requestError) {
      setError(requestError.message || 'Could not open the poster editor.')
    } finally {
      setEditorLoading(false)
    }
  }

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


          {improvement && (
            <section className="evaluator-card improvement-report-card">
              <div className="analysis-module-heading">
                <div><span className="ocr-region-kicker">CONSOLIDATED REPORT</span><h2>{improvement.title}</h2></div>
                <button type="button" className="primary-button" onClick={() => window.print()}>Download / Save PDF</button>
              </div>
              <p>{improvement.summary}</p>
              {improvement.risk_summary && <p><strong>Risk signal:</strong> {improvement.risk_summary}</p>}
              {improvement.sections?.map((section) => (
                <section key={section.title}>
                  <h3>{section.title}</h3>
                  {section.checks.map((check) => (
                    <article className="analysis-module-card" key={check.feature}>
                      <div className="analysis-module-heading"><strong>{check.feature}</strong><span className={statusClass(check.status)}>{MODULE_STATUS_LABELS[check.status] || check.status}</span></div>
                      {check.message && <p>{check.message}</p>}
                      {check.findings?.length > 0 && <ul>{check.findings.map((finding, index) => <li key={index}>{finding}</li>)}</ul>}
                    </article>
                  ))}
                </section>
              ))}
              {improvement.action_plan?.length > 0 && <section><h3>Priority action plan</h3><ol>{improvement.action_plan.map((item, index) => <li key={index}><strong>{item.priority}: {item.action}</strong><p>{item.reason}</p><small>Source: {item.source}</small></li>)}</ol></section>}
              {improvement.limitations?.length > 0 && <section><h3>Checks needing attention</h3><ul>{improvement.limitations.map((item, index) => <li key={index}><strong>{item.feature} — {item.status}:</strong> {item.message}</li>)}</ul></section>}
              <p className="tool-note">{improvement.disclaimer}</p>
            </section>
          )}
          {report?.verification && (
            <section className="evaluator-card">
              <h3>Correct and re-analyse the poster</h3>
              <p>Open the correction workspace to add replacement wording or disclaimers on top of the original poster, or upload a poster corrected in another editor. Then run all checks again.</p>
              <button type="button" className="primary-button" disabled={editorLoading || loading} onClick={openCorrectionEditor}>
                {editorLoading ? 'Loading original poster…' : 'Open poster correction workspace'}
              </button>
              <label className="upload-area">
                <span className="upload-title">Or upload a corrected poster</span>
                <input type="file" accept="image/png,image/jpeg" onChange={(event) => setCorrectedFile(event.target.files?.[0] || null)} />
              </label>
              {correctedFile && <p>Selected corrected poster: <strong>{correctedFile.name}</strong></p>}
              <button type="button" className="primary-button" disabled={!correctedFile || loading} onClick={() => analyze({ preventDefault() {} }, report.verification.id, correctedFile)}>
                {loading ? 'Re-analysing corrected poster…' : 'Upload corrected poster & re-analyse'}
              </button>
              {editorOpen && editorImage && (
                <PosterCorrectionEditor
                  imageUrl={editorImage}
                  onClose={() => setEditorOpen(false)}
                  onExport={(exportedFile) => {
                    setCorrectedFile(exportedFile)
                    setEditorOpen(false)
                  }}
                />
              )}
              {report.revision_of && <p>Revision of previous report: <code>{report.revision_of}</code></p>}
              {report.revision_comparison && (
                <section className="revision-comparison">
                  <h4>Original vs corrected poster</h4>
                  <p>{report.revision_comparison.note}</p>
                  <div className="analysis-module-card">
                    <strong>Findings no longer returned ({report.revision_comparison.resolved_findings?.length || 0})</strong>
                    {report.revision_comparison.resolved_findings?.length
                      ? <ul>{report.revision_comparison.resolved_findings.map((item, index) => <li key={index}>{item}</li>)}</ul>
                      : <p>No textual findings disappeared between these reports.</p>}
                  </div>
                  <div className="analysis-module-card">
                    <strong>Findings still present ({report.revision_comparison.remaining_findings?.length || 0})</strong>
                    {report.revision_comparison.remaining_findings?.length
                      ? <ul>{report.revision_comparison.remaining_findings.map((item, index) => <li key={index}>{item}</li>)}</ul>
                      : <p>No exact matching findings were returned.</p>}
                  </div>
                  <div className="analysis-module-card">
                    <strong>New findings ({report.revision_comparison.new_findings?.length || 0})</strong>
                    {report.revision_comparison.new_findings?.length
                      ? <ul>{report.revision_comparison.new_findings.map((item, index) => <li key={index}>{item}</li>)}</ul>
                      : <p>No new textual findings were returned.</p>}
                  </div>
                </section>
              )}
            </section>
          )}

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
                  <details className="analysis-module-details">
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
